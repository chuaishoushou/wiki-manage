---
name: wiki-query
description: 从个人知识库查询知识并按需沉淀可复用答案。当用户问及项目知识、模块、概念、踩坑,或命中 _routes.md 关键词时使用。先走路由表精确加载,再全文检索综合,引用页面路径。
allowed-tools: Read, Grep, Glob, Bash(python3:*), Bash(wiki-cli:*)
---

# wiki-query:检索 + 综合 + 沉淀

> 工具 `wiki-cli`:shim 已装在 `~/.local/bin`(在 PATH 时直接 `wiki-cli`,否则用全路径 `~/.local/bin/wiki-cli`);都不行就读 `~/.flux-wiki.json` 的 `wiki_manage` 字段,用 `python3 <wiki_manage>/plugins/flux-wiki/tools/bin/wiki-cli`。只读为主。

1. 会话首次涉及知识库:先跑 `wiki-cli context` 拿库位置/团队仓(路径以它的输出为准,不要凭记忆)。
2. 跑 `wiki-cli guide query` 拿检索手册照做:路由表优先 → `wiki-cli search` / Grep → 综合作答引用页面路径 → 有持久价值的结论征得同意后沉淀进 queries/。
