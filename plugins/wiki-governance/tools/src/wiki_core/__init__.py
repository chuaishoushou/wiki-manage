"""wiki_core —— LLM Wiki 治理工具内核(纯 Python 标准库)。

只有 CLI 入口(bin/wiki-cli)使用本包,
确保"同一份确定性逻辑一个入口",AI 直接读文件 + 调 wiki-cli,行为可复现。

设计约束:
- 只用标准库(纯 API / 离线环境无法 pip install)。
- 只读内核(protocol/search/route/get/validate/lint/suggest/scan/changes)= 检索 + 计算 + 建议;
  写子命令(init/scaffold、new、sync-team、publish)由 CLI 直接落盘(os.makedirs+open / shutil.copy2)。
"""

# 本工具支持的协议版本。与仓库 _vocabulary.md / AGENTS.md 的 protocol_version 比对。
SUPPORTED_PROTOCOL_VERSION = 2

__all__ = ["SUPPORTED_PROTOCOL_VERSION"]
