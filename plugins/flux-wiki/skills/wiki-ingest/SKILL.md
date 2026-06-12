---
name: wiki-ingest
description: 把知识记进个人知识库。当用户要"记一下/入库/沉淀/收录"知识、给出外部资料(docx/pdf/md/链接)、或说"这次踩坑记到 wiki"时使用。定主题落 domains/,拿不准放 inbox/,写完记台账。
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python3:*), Bash(wiki-cli:*)
---

# wiki-ingest:记知识进个人库

> 工具 `wiki-cli`:shim 已装在 `~/.local/bin`(在 PATH 时直接 `wiki-cli`,否则用全路径 `~/.local/bin/wiki-cli`);都不行就读 `~/.flux-wiki.json` 的 `wiki_manage` 字段,用 `python3 <wiki_manage>/plugins/flux-wiki/tools/bin/wiki-cli`。
> 本 skill 是入口不是手册。库的位置、写入层、流程细节都**不要凭记忆**:

1. 跑 `wiki-cli guide ingest` 拿当前手册(已注入本机真实路径),**严格照做**。
2. 手册拿不到(环境坏了)→ 跑 `wiki-cli doctor` 把问题报给用户,不要凭猜测写盘。

## 红线(即使没拿到手册也必须遵守)

- **删除任何页 = mv 到 `archive/<YYYY-MM-DD>/`,绝不 `rm`**;`raw/` 只读。
- 每次写入在库根 `log.md` 追加一行(`## [YYYY-MM-DD] ingest | <标题>` + 涉及页面)。
- 先查重(search/Grep),有相关页优先更新整合,不建重复页。
