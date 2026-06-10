"""wiki_core —— 轻量个人知识库工具内核(纯 Python 标准库)。

唯一入口是 CLI(bin/wiki-cli)。AI 直接 Read/Grep 库文件查知识,
用 CLI 做确定性操作:建库(init)/加页(new)/检索(search)/体检(lint)/
团队增量学习数据(learn)/状态(status)。

设计约束:
- 只用标准库(离线环境无法 pip install)。
- 读子命令(search/lint/status/learn 不带 --mark)只读;
  写子命令(init/new/learn --mark)由 CLI 直接落盘。
"""

# 本工具支持的协议版本(v3 = 扁平结构:domains/ 直接在库根下)。
SUPPORTED_PROTOCOL_VERSION = 3

__all__ = ["SUPPORTED_PROTOCOL_VERSION"]
