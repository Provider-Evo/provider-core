


from datetime import datetime

__all__ = ["make_json_download_name"]


def make_json_download_name(prefix: str) -> str:
    """生成导出文件名。"""
    return "{}_{}.json".format(prefix, datetime.now().strftime("%Y%m%d_%H%M%S"))
