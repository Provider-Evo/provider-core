# qwen_login.py
# 账号登录测试脚本 - 尝试登录所有账号，自动重试3次
# 用于测试qwen_client.py中的账号登录功能

import asyncio
import json
import logging
import sys
from typing import List, Tuple, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("account_test")

# 导入qwen_client模块
try:
    from script.qwen.qwen_client import AsyncAccountPool, Account, AsyncQwenClient, AccountParser
    from script.qwen.qwen_client import Config, RetryManager
    try:
        from script.qwen.qwen_accounts import ACCOUNTS
    except ImportError:
        ACCOUNTS = {}
        logger.warning("未找到qwen_accounts.py，请确保账号配置文件存在")
except ImportError as e:
    logger.error(f"导入qwen_client失败: {e}")
    logger.error("请确保qwen_client.py在当前目录")
    sys.exit(1)


class AccountLoginTester:
    """账号登录测试器"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.successful_logins: List[Tuple[str, bool]] = []  # (email, success)
        self.failed_logins: List[Tuple[str, str]] = []      # (email, error_reason)
        self.account_details: Dict[str, Dict[str, Any]] = {} # 账号详情
        
    def _get_accounts_from_config(self) -> List[Tuple[str, str]]:
        """从配置中获取所有账号"""
        parsed_accounts = AccountParser.parse(ACCOUNTS)
        
        if not parsed_accounts:
            logger.error("未解析到任何有效账号，请检查qwen_accounts.py配置")
            return []
        
        logger.info(f"从配置中解析到 {len(parsed_accounts)} 个账号")
        for email, _ in parsed_accounts:
            logger.info(f"  - {email}")
        
        return parsed_accounts
    
    async def test_single_account(
        self,
        client: AsyncQwenClient,
        email: str,
        password: str,
        attempt: int = 1
    ) -> Tuple[bool, str]:
        """测试单个账号登录"""
        account = Account(email, password)
        
        try:
            logger.info(f"[尝试 {attempt}/{self.max_retries}] 正在登录: {email}")
            
            # 使用AsyncAccountPool的登录方法
            success = await client.account_pool._login_account_with_retry(account)
            
            if success:
                logger.info(f"✓ 登录成功: {email}")
                
                # 记录账号详情
                self.account_details[email] = {
                    "email": email,
                    "user_id": account.user_id,
                    "token_expires": account.token_expires,
                    "memory_disabled": account.memory_disabled,
                    "login_attempts": account.login_attempts
                }
                
                # 可选：获取账号使用状态
                try:
                    status = await client.get_account_status()
                    logger.info(f"  账号池状态: 已登录 {status.get('logged_in', 0)}/{status.get('total_accounts', 0)}")
                except:
                    pass
                
                return True, ""
            else:
                error_msg = f"登录失败，服务器未返回成功状态"
                logger.warning(f"✗ 登录失败: {email} - {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"✗ 登录异常: {email} - {error_msg}")
            return False, error_msg
    
    async def test_all_accounts(self) -> None:
        """测试所有账号登录"""
        accounts = self._get_accounts_from_config()
        
        if not accounts:
            print("\n" + "="*60)
            print("❌ 测试失败: 未找到任何账号配置")
            print("="*60)
            return
        
        # 创建客户端（使用debug模式）
        client = AsyncQwenClient(debug=True)
        
        try:
            # 初始化客户端
            logger.info("初始化Qwen客户端...")
            await client.ensure_initialized()
            logger.info("客户端初始化完成")
            
            total = len(accounts)
            logger.info(f"\n开始测试 {total} 个账号登录（最大重试次数: {self.max_retries}）")
            print("-" * 60)
            
            for idx, (email, password) in enumerate(accounts, 1):
                logger.info(f"\n[{idx}/{total}] 处理账号: {email}")
                
                success = False
                error_msg = ""
                
                # 重试循环
                for attempt in range(1, self.max_retries + 1):
                    success, error_msg = await self.test_single_account(
                        client, email, password, attempt
                    )
                    
                    if success:
                        break
                    
                    if attempt < self.max_retries:
                        wait_time = 2 ** attempt  # 指数退避
                        logger.info(f"等待 {wait_time} 秒后进行第 {attempt + 1} 次重试...")
                        await asyncio.sleep(wait_time)
                
                # 记录结果
                if success:
                    self.successful_logins.append((email, True))
                else:
                    self.failed_logins.append((email, error_msg))
                
                # 账号间稍微延迟，避免请求过快
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"测试过程发生异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 关闭客户端
            await client.close()
            logger.info("客户端已关闭")
    
    def print_report(self) -> None:
        """打印测试报告"""
        total = len(self.successful_logins) + len(self.failed_logins)
        success_count = len(self.successful_logins)
        failed_count = len(self.failed_logins)
        
        print("\n" + "="*80)
        print("📊 账号登录测试报告")
        print("="*80)
        print(f"总账号数: {total}")
        print(f"✅ 登录成功: {success_count}")
        print(f"❌ 登录失败: {failed_count}")
        print(f"成功率: {success_count/total*100:.1f}%" if total > 0 else "0%")
        print("-"*80)
        
        # 显示成功登录的账号
        if self.successful_logins:
            print("\n✅ 成功登录的账号:")
            for idx, (email, _) in enumerate(self.successful_logins, 1):
                details = self.account_details.get(email, {})
                user_id = details.get('user_id', 'N/A')[:8] + '...' if details.get('user_id') else 'N/A'
                memory = "✓" if details.get('memory_disabled') else "✗"
                print(f"  {idx:2d}. {email}")
                print(f"      用户ID: {user_id}, 记忆已关闭: {memory}")
        
        # ============ 重点：打印不能登录的账号列表（完整显示，不截断）============
        if self.failed_logins:
            print("\n" + "❌"*40)
            print("❌ 不能登录的账号列表 ❌")
            print("❌"*40)
            
            for idx, (email, error) in enumerate(self.failed_logins, 1):
                print(f"\n  {idx:2d}. 【{email}】")
                print(f"      错误原因: {error}")
            
            print("\n" + "❌"*40)
            print(f"总计 {len(self.failed_logins)} 个账号无法登录")
            print("❌"*40)
        else:
            print("\n" + "✅"*40)
            print("✅ 所有账号登录成功！ ✅")
            print("✅"*40)
        
        # 附加统计信息
        if self.account_details:
            print("\n📈 详细统计:")
            print(f"  - 记忆功能已关闭: {sum(1 for d in self.account_details.values() if d.get('memory_disabled'))}")
            print(f"  - 平均登录尝试次数: {sum(d.get('login_attempts', 0) for d in self.account_details.values()) / len(self.account_details):.1f}")
        
        print("\n" + "="*80)
    
    async def run(self) -> None:
        """运行测试"""
        print("="*80)
        print("🔐 Qwen 账号登录测试工具")
        print("="*80)
        print(f"配置最大重试次数: {self.max_retries}")
        print(f"当前时间: {asyncio.get_event_loop().time()}")
        print("="*80)
        
        await self.test_all_accounts()
        self.print_report()


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Qwen账号登录测试工具")
    parser.add_argument(
        "--retries", "-r",
        type=int,
        default=3,
        help="最大重试次数 (默认: 3)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试输出"
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    tester = AccountLoginTester(max_retries=args.retries)
    await tester.run()


def run():
    """同步运行入口"""
    asyncio.run(main())


if __name__ == "__main__":
    run()
