"""wiki_core —— LLM Wiki 治理工具内核(纯 Python 标准库)。

CLI(bin/wiki-cli)与 MCP server(server/wiki_mcp.py)共享本包,
确保"同一份确定性逻辑两个入口",避免 CLI↔MCP 行为漂移。

设计约束:
- 只用标准库(纯 API / 离线环境无法 pip install)。
- 全部为只读检索 + 计算 + 建议;不做落盘写入(写入走 AI 的 file tools + skill)。
"""

# 本工具支持的协议版本。与仓库 _vocabulary.md / AGENTS.md 的 protocol_version 比对。
SUPPORTED_PROTOCOL_VERSION = 2

__all__ = ["SUPPORTED_PROTOCOL_VERSION"]
