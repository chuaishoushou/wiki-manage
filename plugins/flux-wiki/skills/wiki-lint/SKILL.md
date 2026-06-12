---
name: wiki-lint
description: 给个人知识库做体检/清理。当用户说"检查 wiki/体检/清理/lint/知识库有没有问题"时使用。跑确定性检查出结构化报告,修复需用户确认。
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(python3:*), Bash(wiki-cli:*), Write
---

# wiki-lint:体检

> 工具 `wiki-cli`:shim 已装在 `~/.local/bin`(在 PATH 时直接 `wiki-cli`,否则用全路径 `~/.local/bin/wiki-cli`);都不行就读 `~/.flux-wiki.json` 的 `wiki_manage` 字段,用 `python3 <wiki_manage>/plugins/flux-wiki/tools/bin/wiki-cli`。
> 检查是确定性的;AI 负责判读 + 给修复建议;**动手修复前需用户确认**。

1. 跑 `wiki-cli guide lint` 拿当前手册照做:环境层 `wiki-cli doctor` → 内容层 `wiki-cli lint` → 判读 → 用户确认后修复。
2. 红线:涉及删页一律 `mv` 到 `archive/<YYYY-MM-DD>/`,绝不 `rm`;收尾 `log.md` 记一行。
