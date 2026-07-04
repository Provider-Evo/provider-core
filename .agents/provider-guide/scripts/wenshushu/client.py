# -*- coding: utf-8 -*-
"""文叔叔 HTTP 客户端模块。

封装了匿名登录、文件上传(含秒传/分块)、文件下载的全部逻辑,
包括加密签名、重试、错误处理等核心业务代码。
"""
from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterator

from ._optional import _optional_import
from .container import WSS_CHUNK_SIZE, Config
from .exceptions import ExternalServiceError, ValidationError
from .logging_setup import _logger
from .utils import format_duration, format_file_size, md5_of_bytes, sha1_of_string

# ---------------------------------------------------------------------------
# 第三方可选导入与降级代理
# ---------------------------------------------------------------------------
_requests_mod = _optional_import("requests", "requests")
_base58_mod = _optional_import("base58", "base58")
_des_mod = _optional_import("Cryptodome.Cipher.DES", "pycryptodomex")
_padding_mod = _optional_import("Cryptodome.Util.Padding", "pycryptodomex")

try:
    import requests as _requests  # type: ignore[import-untyped]
    import base58 as _base58  # type: ignore[import-untyped]
    from Cryptodome.Cipher import DES as _DES  # type: ignore[import-untyped]
    from Cryptodome.Util import Padding as _Padding  # type: ignore[import-untyped]
    _HAS_CRYPTO_DEPS = True
except ImportError:
    _requests = _requests_mod  # type: ignore[assignment]
    _base58 = _base58_mod  # type: ignore[assignment]
    _DES = _des_mod  # type: ignore[assignment]
    _Padding = _padding_mod  # type: ignore[assignment]
    _HAS_CRYPTO_DEPS = False

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
WSS_DEFAULT_ACCEPT_LANG = "en-US, en;q=0.9"


# ===========================================================================
# 文叔叔客户端
# ===========================================================================

class WenShuShuClient:
    """文叔叔文件传输客户端。

    封装了匿名登录、文件上传(含秒传/分块)、文件下载的全部逻辑。

    Args:
        config: 配置对象。

    >>> client = WenShuShuClient.__new__(WenShuShuClient)
    >>> client._config = Config()
    >>> client._config.base_url
    'https://www.wenshushu.cn'
    """

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or Config()
        self._session: Any = None
        self._token: str = ""

    def _ensure_session(self) -> Any:
        """确保 HTTP 会话已初始化并登录。

        Returns:
            requests.Session 实例。
        """
        if self._session is None:
            self._session = _requests.Session()
            self._session.headers["User-Agent"] = self._config.user_agent
            self._session.headers["Accept-Language"] = WSS_DEFAULT_ACCEPT_LANG
            self._token = self._login_anonymous()
            self._session.headers["X-TOKEN"] = self._token
        return self._session

    def _login_anonymous(self) -> str:
        """匿名登录获取令牌。

        Returns:
            认证令牌字符串。

        Raises:
            ExternalServiceError: 登录失败时。
        """
        s = self._session
        try:
            r = s.post(
                url=f"{self._config.base_url}/ap/login/anonymous",
                json={"dev_info": "{}"},
            )
            rsp = r.json()
            token = rsp["data"]["token"]
            _logger.info("匿名登录成功")
            return token
        except Exception as exc:
            raise ExternalServiceError(f"匿名登录失败: {exc}") from exc

    def _get_epochtime(self) -> str:
        """获取服务器纪元时间戳。

        Returns:
            时间戳字符串。
        """
        s = self._ensure_session()
        r = s.get(
            url=f"{self._config.base_url}/ag/time",
            headers={
                "Prod": "com.wenshushu.web.pc",
                "Referer": f"{self._config.base_url}/",
            },
        )
        return r.json()["data"]["time"]

    def _get_cipher_header(self, epochtime: str, token: str, data: dict[str, Any]) -> bytes:
        """生成加密签名头。

        使用 DES/CBC/PKCS7Padding 加密方式。

        Args:
            epochtime: 服务器时间戳。
            token: 认证令牌。
            data: 请求数据。

        Returns:
            Base64 编码的密文。
        """
        json_dumps = json.dumps(data, ensure_ascii=False)
        md5_hash_code = hashlib.md5((json_dumps + token).encode()).hexdigest()
        base58_hash_code = _base58.b58encode(md5_hash_code)
        # 时间戳逆序取5位并作为时间戳字串索引再次取值,最后拼接"000"
        key_iv = (
            "".join([epochtime[int(i)] for i in epochtime[::-1][:5]]) + "000"
        ).encode()
        cipher = _DES.new(key_iv, _DES.MODE_CBC, key_iv)
        ciphertext = cipher.encrypt(
            _Padding.pad(base58_hash_code, _DES.block_size, style="pkcs7")
        )
        return base64.b64encode(ciphertext)

    def _calc_file_hash(
        self,
        file_path: str,
        hash_type: str,
        block: bytes | None = None,
        chunk_size: int = WSS_CHUNK_SIZE,
    ) -> str:
        """计算文件或数据块的哈希值。

        Args:
            file_path: 文件路径。
            hash_type: 'MD5' 或 'SHA1'。
            block: 可选的数据块,为 None 时从文件读取。
            chunk_size: 读取大小。

        Returns:
            十六进制哈希字符串。
        """
        file_size = os.path.getsize(file_path)
        is_part = file_size > chunk_size
        read_size = chunk_size if is_part else None
        if block is None:
            with open(file_path, "rb") as f:
                block = f.read(read_size) if read_size else f.read()
        if hash_type == "MD5":
            return hashlib.md5(block).hexdigest()
        elif hash_type == "SHA1":
            return hashlib.sha1(block).hexdigest()
        raise ValidationError(f"不支持的哈希类型: {hash_type}", field="hash_type", value=hash_type)

    def _read_file_chunks(self, file_path: str, block_size: int = WSS_CHUNK_SIZE) -> Iterator[tuple[bytes, int]]:
        """按块读取文件。

        Args:
            file_path: 文件路径。
            block_size: 块大小。

        Yields:
            (数据块, 块编号) 元组。
        """
        part_num = 0
        with open(file_path, "rb") as f:
            while True:
                block = f.read(block_size)
                part_num += 1
                if block:
                    yield block, part_num
                else:
                    return

    def upload(self, file_path: str) -> dict[str, Any]:
        """上传文件到文叔叔。

        支持秒传检测和分块并发上传。

        Args:
            file_path: 要上传的文件路径。

        Returns:
            包含管理链接和公共链接的字典。

        Raises:
            ExternalServiceError: 上传过程中的网络或服务错误。
        """
        s = self._ensure_session()
        cfg = self._config
        chunk_size = cfg.chunk_size
        file_size = os.path.getsize(file_path)
        is_part = file_size > chunk_size
        file_name = os.path.basename(file_path)

        # 获取用户信息和存储空间
        self._show_storage(s)

        # 创建发送任务
        bid, ufileid, tid, up_id = self._addsend(s, file_size, chunk_size)

        # 尝试秒传
        fast_result = self._try_fast_upload(s, file_path, bid, ufileid, up_id, file_size, chunk_size, is_part)
        if fast_result is not None:
            # 秒传成功
            self._wait_process(s, up_id)
            return self._copysend(s, bid, tid, ufileid)

        # 正常上传
        if is_part:
            print("文件正在被分块上传!")
            self._upload_multipart(s, file_path, file_name, up_id, file_size, chunk_size)
        else:
            print("文件被整块上传!")
            self._upload_single(s, file_path, file_name, up_id, file_size)

        # 完成上传
        self._complete_upload(s, file_name, up_id, bid, ufileid, is_part)
        result = self._copysend(s, bid, tid, ufileid)
        self._wait_process(s, up_id)
        return result

    def _show_storage(self, s: Any) -> None:
        """显示存储空间信息。

        Args:
            s: HTTP 会话。
        """
        s.post(url=f"{self._config.base_url}/ap/user/userinfo", json={"plat": "pcweb"})
        r = s.post(url=f"{self._config.base_url}/ap/user/storage", json={})
        rsp = r.json()
        rest_space = int(rsp["data"]["rest_space"])
        send_space = int(rsp["data"]["send_space"])
        total = rest_space + send_space
        print(
            f"当前已用空间:{round(send_space / 1024 ** 3, 2)}GB,"
            f"剩余空间:{round(rest_space / 1024 ** 3, 2)}GB,"
            f"总空间:{round(total / 1024 ** 3, 2)}GB"
        )

    def _addsend(
        self, s: Any, file_size: int, chunk_size: int
    ) -> tuple[str, str, str, str]:
        """创建发送任务并获取上传 ID。

        Args:
            s: HTTP 会话。
            file_size: 文件大小。
            chunk_size: 分块大小。

        Returns:
            (bid, ufileid, tid, up_id) 元组。
        """
        epochtime = self._get_epochtime()
        req_data: dict[str, Any] = {
            "sender": "",
            "remark": "",
            "isextension": False,
            "notSaveTo": False,
            "notDownload": False,
            "notPreview": False,
            "downPreCountLimit": 0,
            "trafficStatus": 0,
            "pwd": "",
            "expire": "1",
            "recvs": ["social", "public"],
            "file_size": file_size,
            "file_count": 1,
        }
        r = s.post(
            url=f"{self._config.base_url}/ap/task/addsend",
            json=req_data,
            headers={
                "A-code": self._get_cipher_header(epochtime, self._token, req_data),
                "Prod": "com.wenshushu.web.pc",
                "Referer": f"{self._config.base_url}/",
                "Origin": self._config.base_url,
                "Req-Time": epochtime,
            },
        )
        rsp = r.json()
        if rsp.get("code") == 1021:
            raise ExternalServiceError(
                f"操作太快! 请{rsp.get('message', '稍')}秒后重试",
                context={"code": 1021},
            )
        data = rsp.get("data")
        if not data:
            raise ExternalServiceError("需要滑动验证码,请稍后重试")
        bid = data["bid"]
        ufileid = data["ufileid"]
        tid = data["tid"]

        # 获取 upId
        r2 = s.post(
            url=f"{self._config.base_url}/ap/uploadv2/getupid",
            json={
                "preid": ufileid,
                "boxid": bid,
                "linkid": tid,
                "utype": "sendcopy",
                "originUpid": "",
                "length": file_size,
                "count": 1,
            },
        )
        up_id = r2.json()["data"]["upId"]
        return bid, ufileid, tid, up_id

    def _try_fast_upload(
        self,
        s: Any,
        file_path: str,
        bid: str,
        ufileid: str,
        up_id: str,
        file_size: int,
        chunk_size: int,
        is_part: bool,
    ) -> dict[str, Any] | None:
        """尝试秒传。

        Args:
            s: HTTP 会话。
            file_path: 文件路径。
            bid: Box ID。
            ufileid: 文件 ID。
            up_id: 上传 ID。
            file_size: 文件大小。
            chunk_size: 分块大小。
            is_part: 是否分块。

        Returns:
            秒传成功时返回信息字典,否则返回 None。
        """
        cm1 = self._calc_file_hash(file_path, "MD5", chunk_size=chunk_size)
        cs1 = self._calc_file_hash(file_path, "SHA1", chunk_size=chunk_size)
        cm = sha1_of_string(cm1)
        name = os.path.basename(file_path)

        payload: dict[str, Any] = {
            "hash": {"cm1": cm1, "cs1": cs1},
            "uf": {"name": name, "boxid": bid, "preid": ufileid},
            "upId": up_id,
        }
        if not is_part:
            payload["hash"]["cm"] = cm

        for _ in range(2):
            r = s.post(url=f"{self._config.base_url}/ap/uploadv2/fast", json=payload)
            rsp = r.json()
            can_fast = rsp["data"]["status"]
            ufile = rsp["data"]["ufile"]
            if can_fast and not ufile:
                # 需要计算完整分块哈希
                hash_codes = ""
                for block, _ in self._read_file_chunks(file_path, chunk_size):
                    hash_codes += md5_of_bytes(block)
                payload["hash"]["cm"] = sha1_of_string(hash_codes)
            elif can_fast and ufile:
                print(f"文件{name}可以被秒传!")
                return {"fast": True, "name": name}
        return None

    def _get_psurl(
        self, s: Any, fname: str, up_id: str, fsize: int, is_part: bool, part_num: int | None = None
    ) -> str:
        """获取预签名上传 URL。

        Args:
            s: HTTP 会话。
            fname: 文件名。
            up_id: 上传 ID。
            fsize: 文件/分块大小。
            is_part: 是否分块。
            part_num: 分块编号。

        Returns:
            预签名 URL。
        """
        payload: dict[str, Any] = {
            "ispart": is_part,
            "fname": fname,
            "fsize": fsize,
            "upId": up_id,
        }
        if is_part and part_num is not None:
            payload["partnu"] = part_num
        r = s.post(url=f"{self._config.base_url}/ap/uploadv2/psurl", json=payload)
        return r.json()["data"]["url"]

    def _upload_single(self, s: Any, file_path: str, fname: str, up_id: str, file_size: int) -> None:
        """整块上传文件。

        Args:
            s: HTTP 会话。
            file_path: 文件路径。
            fname: 文件名。
            up_id: 上传 ID。
            file_size: 文件大小。
        """
        url = self._get_psurl(s, fname, up_id, file_size, False)
        with open(file_path, "rb") as f:
            _requests.put(url=url, data=f.read())
        print("上传完成:100%")

    def _upload_multipart(
        self, s: Any, file_path: str, fname: str, up_id: str, file_size: int, chunk_size: int
    ) -> None:
        """分块并发上传文件。

        Args:
            s: HTTP 会话。
            file_path: 文件路径。
            fname: 文件名。
            up_id: 上传 ID。
            file_size: 文件大小。
            chunk_size: 分块大小。
        """

        def _put_chunk(part_index: int) -> None:
            offset = chunk_size * part_index
            ul_size = min(chunk_size, file_size - offset)
            url = self._get_psurl(s, fname, up_id, ul_size, True, part_index + 1)
            with open(file_path, "rb") as fio:
                fio.seek(offset)
                _requests.put(url=url, data=fio.read(ul_size))

        total_parts = (file_size + chunk_size - 1) // chunk_size
        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            futures = [executor.submit(_put_chunk, i) for i in range(total_parts)]
            completed = 0
            for _ in concurrent.futures.as_completed(futures):
                completed += 1
                pct = int(completed / total_parts * 100)
                print(f"分块进度:{pct}%", end="\r")
                if pct == 100:
                    print("上传完成:100%")

    def _complete_upload(
        self, s: Any, fname: str, up_id: str, bid: str, ufileid: str, is_part: bool
    ) -> None:
        """通知服务端上传完成。

        Args:
            s: HTTP 会话。
            fname: 文件名。
            up_id: 上传 ID。
            bid: Box ID。
            ufileid: 文件 ID。
            is_part: 是否分块。
        """
        s.post(
            url=f"{self._config.base_url}/ap/uploadv2/complete",
            json={
                "ispart": is_part,
                "fname": fname,
                "upId": up_id,
                "location": {"boxid": bid, "preid": ufileid},
            },
        )

    def _copysend(self, s: Any, bid: str, tid: str, ufileid: str) -> dict[str, Any]:
        """完成发送任务,获取分享链接。

        Args:
            s: HTTP 会话。
            bid: Box ID。
            tid: 任务 ID。
            ufileid: 文件 ID。

        Returns:
            包含管理链接和公共链接的字典。
        """
        r = s.post(
            url=f"{self._config.base_url}/ap/task/copysend",
            json={"bid": bid, "tid": tid, "ufileid": ufileid},
        )
        rsp = r.json()
        mgr_url = rsp["data"]["mgr_url"]
        public_url = rsp["data"]["public_url"]
        print(f"个人管理链接: {mgr_url}")
        print(f"公共链接: {public_url}")
        return {"mgr_url": mgr_url, "public_url": public_url}

    def _wait_process(self, s: Any, up_id: str) -> None:
        """等待服务端处理完成。

        Args:
            s: HTTP 会话。
            up_id: 上传 ID。
        """
        while True:
            r = s.post(
                url=f"{self._config.base_url}/ap/ufile/getprocess",
                json={"processId": up_id},
            )
            if r.json()["data"]["rst"] == "success":
                return
            time.sleep(1)

    def download(self, url: str, password: str = "") -> dict[str, Any]:
        """从文叔叔下载文件。

        Args:
            url: 文叔叔分享链接或令牌。
            password: 分享密码(可选)。

        Returns:
            包含文件名和状态的字典。

        Raises:
            ExternalServiceError: 下载过程中的网络或服务错误。
        """
        s = self._ensure_session()
        token_or_tid = url.split("/")[-1]

        if len(token_or_tid) == 16:
            # 通过 token 获取 tid
            r = s.post(
                url=f"{self._config.base_url}/ap/task/token",
                json={"token": token_or_tid},
            )
            tid = r.json()["data"]["tid"]
        elif len(token_or_tid) == 11:
            tid = token_or_tid
        else:
            raise ValidationError(
                f"无法识别的链接格式: {url}",
                field="url",
                value=url,
                reason="令牌长度应为 11 或 16",
            )

        # 获取任务信息
        r = s.post(
            url=f"{self._config.base_url}/ap/task/mgrtask",
            json={"tid": tid, "password": password},
        )
        rsp = r.json()
        expire = rsp["data"]["expire"]
        print(f"文件过期时间:{format_duration(float(expire))}")

        file_size = int(rsp["data"]["file_size"])
        print(f"文件大小:{format_file_size(file_size)}")

        bid = rsp["data"]["boxid"]
        pid = rsp["data"]["ufileid"]

        # 获取文件列表
        r = s.post(
            url=f"{self._config.base_url}/ap/ufile/list",
            json={
                "start": 0,
                "sort": {"name": "asc"},
                "bid": bid,
                "pid": pid,
                "type": 1,
                "options": {"uploader": "true"},
                "size": 50,
            },
        )
        rsp = r.json()
        file_info = rsp["data"]["fileList"][0]
        filename = file_info["fname"]
        fid = file_info["fid"]
        print(f"文件名:{filename}")

        # 获取下载签名
        r = s.post(
            url=f"{self._config.base_url}/ap/dl/sign",
            json={"consumeCode": 0, "type": 1, "ufileid": fid},
        )
        sign_data = r.json()["data"]
        if sign_data["url"] == "" and sign_data.get("ttNeed", 0) != 0:
            raise ExternalServiceError("对方的分享流量不足")

        dl_url = sign_data["url"]

        # 下载文件
        print("开始下载!", end="\r")
        r = s.get(dl_url, stream=True)
        dl_size = int(r.headers.get("Content-Length", 0))
        dl_count = 0
        block_size = self._config.chunk_size
        with open(filename, "wb") as f:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=block_size):
                f.write(chunk)
                dl_count += len(chunk)
                if dl_size > 0:
                    print(f"下载进度:{int(dl_count / dl_size * 100)}%", end="\r")
            print("下载完成:100%")

        return {"filename": filename, "size": dl_size, "status": "completed"}
