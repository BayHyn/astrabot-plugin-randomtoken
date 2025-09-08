from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import random
import string
import json
import os
from datetime import datetime
import hashlib
import base64

# 确保数据目录存在
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 存储文件路径
STORAGE_FILE = os.path.join(DATA_DIR, 'tokens.json')

@register("randomtoken", "LumineStory", "随机Token生成与管理插件", "1.0.0", "https://github.com/oyxning/astrabot-plugin-randomtoken")
class RandomTokenPlugin(Star):
    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.tokens_data = self._load_tokens_data()
        logger.info("随机Token插件已初始化")

    def _load_tokens_data(self):
        """加载存储的token数据"""
        try:
            if os.path.exists(STORAGE_FILE):
                with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"next_id": 1, "tokens": []}
        except Exception as e:
            logger.error(f"加载token数据失败: {str(e)}")
            return {"next_id": 1, "tokens": []}

    def _save_tokens_data(self):
        """保存token数据到文件"""
        try:
            with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.tokens_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存token数据失败: {str(e)}")
            return False

    def _generate_token(self, length=None, use_special_chars=None, random_case=None):
        """生成随机token"""
        # 使用配置或默认值
        length = length or self.config.get("token_length", 30)
        use_special_chars = use_special_chars if use_special_chars is not None else self.config.get("enable_special_chars", True)
        random_case = random_case if random_case is not None else self.config.get("enable_random_case", True)

        # 定义字符集
        letters = string.ascii_letters
        digits = string.digits
        special_chars = '!@#$%^&*()_+-=[]{}|;:,.<>?~'

        # 基础字符集
        char_set = letters + digits
        if use_special_chars:
            char_set += special_chars

        # 生成token
        token = ''.join(random.choice(char_set) for _ in range(length))

        # 如果不启用随机大小写，则转为小写
        if not random_case:
            token = token.lower()

        return token

    def _hash_password(self, password):
        """哈希安全密码"""
        return hashlib.sha256(password.encode()).hexdigest()

    @filter.command("生成随机token")
    async def generate_token_command(self, event: AstrMessageEvent, seq_id: str, password: str, remark: str):
        """处理生成随机token指令"""
        try:
            # 验证参数
            if not all([seq_id, password, remark]):
                yield event.plain_result("参数错误！请使用格式: /生成随机token 序号 安全密码 备注")
                return

            # 检查序号是否已存在
            existing = next((t for t in self.tokens_data["tokens"] if t["seq_id"] == seq_id), None)
            if existing:
                yield event.plain_result(f"错误：序号 {seq_id} 已存在，请使用其他序号")
                return

            # 生成token
            token_count = self.config.get("token_count", 10)
            tokens = [self._generate_token() for _ in range(token_count)]

            # 存储token信息
            token_entry = {
                "seq_id": seq_id,
                "password_hash": self._hash_password(password),
                "remark": remark,
                "tokens": tokens,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            self.tokens_data["tokens"].append(token_entry)
            self.tokens_data["next_id"] += 1
            if self._save_tokens_data():
                # 生成带编号的token列表
                token_list = "\n".join([f"{i+1}. {token}" for i, token in enumerate(tokens)])
                # 优化token显示格式，增加分隔线和警告
                token_message = f"成功生成 {token_count} 个token！\n\n序号: {seq_id}\n备注: {remark}\n\n" + "="*40 + "\n【重要】生成的token列表：\n{token_list}\n\n".format(token_list=token_list) + "="*40 + "\n⚠️ 警告：这是您唯一一次查看这些token的机会！\n⚠️ 请立即保存并妥善保管！"
                yield event.plain_result(token_message)
            else:
                yield event.plain_result("生成token失败，请稍后重试")

        except Exception as e:
            logger.error(f"生成token错误: {str(e)}")
            yield event.plain_result("生成token时发生错误，请联系管理员")

    @filter.command("导出token")
    async def export_token_command(self, event: AstrMessageEvent, seq_id: str, password: str, confirm: str = None):
        """处理导出token指令"""
        try:
            # 查找token条目
            token_entry = next((t for t in self.tokens_data["tokens"] if t["seq_id"] == seq_id), None)
            if not token_entry:
                yield event.plain_result(f"未找到序号为 {seq_id} 的token记录")
                return

            # 验证密码
            if self._hash_password(password) != token_entry["password_hash"]:
                yield event.plain_result("安全密码不正确，无法导出token")
                return

            # 验证确认参数
            if not confirm or confirm.lower() != 'confirm':
                yield event.plain_result("⚠️ 警告：导出token会删除对应序号的token记录。\n请确认并重新运行命令: /导出token 序号 安全密码 confirm")
                return

            # 准备导出数据
            export_data = {
                "seq_id": token_entry["seq_id"],
                "remark": token_entry["remark"],
                "created_at": token_entry["created_at"],
                "tokens": token_entry["tokens"]
            }

            # 保存为JSON文件
            export_dir = os.path.join(DATA_DIR, "exports")
            os.makedirs(export_dir, exist_ok=True)
            filename = f"tokens_{seq_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            file_path = os.path.join(export_dir, filename)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            # 由于send_file不可用，改为文本形式输出token
            token_list = "\n".join([f"{i+1}. {token}" for i, token in enumerate(token_entry["tokens"])])
            export_message = f"token导出成功！文件已保存至服务器:\n{file_path}\n\n序号: {token_entry['seq_id']}\n备注: {token_entry['remark']}\n创建时间: {token_entry['created_at']}\n\n" + "="*40 + "\n【重要】Token列表：\n{token_list}\n\n".format(token_list=token_list) + "="*40 + "\n⚠️ 请立即保存并妥善保管！"
            # 导出后删除该token条目
            token_index = next((i for i, t in enumerate(self.tokens_data["tokens"]) if t["seq_id"] == seq_id), None)
            if token_index is not None:
                del self.tokens_data["tokens"][token_index]
                self._save_tokens_data()
                export_message += "\n\n⚠️ 提示：该token记录已自动删除，无法再次导出。"
            
            yield event.plain_result(export_message)

        except Exception as e:
            logger.error(f"导出token错误: {str(e)}")
            yield event.plain_result("导出token时发生错误，请联系管理员")

    @filter.command("查看token列表")
    async def view_token_list(self, event: AstrMessageEvent):
        """处理查看token列表指令"""
        try:
            if not self.tokens_data["tokens"]:
                yield event.plain_result("暂无token记录")
                return

            # 按序号排序
            sorted_tokens = sorted(self.tokens_data["tokens"], key=lambda x: x["seq_id"])

            # 生成文本形式的列表
            list_content = """Token列表\n"""
            list_content += "="*40 + "\n"
            for idx, token_info in enumerate(sorted_tokens, 1):
                list_content += f"序号: {token_info['seq_id']}\n"
                list_content += f"备注: {token_info['remark']}\n"
                list_content += f"创建时间: {token_info['created_at']}\n"
                list_content += f"Token数量: {len(token_info['tokens'])}个\n"
                list_content += "-"*40 + "\n"
            
            # 避免消息过长，只显示概览信息
            if len(list_content) > 2000:
                yield event.plain_result(f"Token列表（共{len(sorted_tokens)}条记录）\n" + "="*40 + "\n" + "\n".join([f"序号: {token['seq_id']} | 备注: {token['remark']}" for token in sorted_tokens[:10]]) + f"\n\n... 还有{max(0, len(sorted_tokens)-10)}条记录未显示\n\n" + "请使用 /导出token 序号 安全密码 命令查看完整信息")
            else:
                yield event.plain_result(list_content)

        except Exception as e:
            logger.error(f"查看token列表错误: {str(e)}")
            yield event.plain_result("查看token列表时发生错误，请联系管理员")

    @filter.command("删除token")
    async def delete_token_command(self, event: AstrMessageEvent, seq_id: str):
        """处理删除token指令"""
        try:
            if not seq_id:
                yield event.plain_result("参数错误！请使用格式: /删除token 序号")
                return

            # 查找token条目索引
            token_index = next((i for i, t in enumerate(self.tokens_data["tokens"]) if t["seq_id"] == seq_id), None)
            if token_index is None:
                yield event.plain_result(f"未找到序号为 {seq_id} 的token记录")
                return

            # 删除token条目
            del self.tokens_data["tokens"][token_index]
            if self._save_tokens_data():
                yield event.plain_result(f"成功删除序号为 {seq_id} 的token记录")
            else:
                yield event.plain_result("删除token失败，请稍后重试")

        except Exception as e:
            logger.error(f"删除token错误: {str(e)}")
            yield event.plain_result("删除token时发生错误，请联系管理员")

    @filter.command("随机生成token教程")
    async def token_tutorial(self, event: AstrMessageEvent):
        """处理随机生成token教程指令"""
        tutorial = (
            "随机生成token插件使用教程:\n"
            "1. 生成token: /生成随机token 序号 安全密码 备注\n"
            "   示例: /生成随机token 001 mypassword 我的API密钥\n"
            "2. 导出token: /导出token 序号 安全密码 confirm\n"
            "   示例: /导出token 001 mypassword confirm\n"
            "   注意：导出后该序号的token记录将自动删除，需添加confirm参数确认\n"
            "3. 删除token: /删除token 序号\n"
            "   示例: /删除token 001\n"
            "4. 查看列表: /查看token列表\n"
            "5. 查看教程: /随机生成token教程\n"
            "\n配置说明:\n"
            "- token长度: 默认30位\n"
            "- token条数: 默认10条\n"
            "- 特殊符号: 默认开启\n"
            "- 随机大小写: 默认开启"
        )
        yield event.plain_result(tutorial)

    async def terminate(self):
        """插件停止时保存数据"""
        self._save_tokens_data()
        logger.info("随机Token插件已停止")