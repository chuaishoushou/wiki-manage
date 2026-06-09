---
description: (任何人)列出团队 wiki 插件的所有能力 / 命令
---

请向用户展示团队 wiki 插件的能力清单(原样呈现即可):

> 提示:`wiki-query` / `wiki-ingest` / `wiki-lint` 是 **skill(技能)**(直接说"查 wiki…/把这条记进 wiki/给 wiki 体检"即可触发);`wiki-sync` / `wiki-help` 是 **slash 命令**(`/` 直接调)。底层能力都来自 MCP。

**查知识(任何人)** — skill: wiki-query
- 直接问即可;底层 MCP:`wiki_search` / `wiki_resolve_route` / `wiki_get_page`

**加知识**
- 轻量(已知归属):`wiki-cli new <type> <slug> --domain <d>` —— 一条命令出合规页骨架
- 完整(新原始资料进团队仓):skill **wiki-ingest**(维护者)—— 敏感度闸 + 分类决策树

**同步团队知识**
- 团队知识镜像进个人库(`WIKI_ROOT`=个人库时用):`/wiki-sync-team` 或 `wiki-cli sync-team --team <团队仓clone>` — 把团队仓**原样镜像**到个人库 `wiki/team/` 只读区(可检索、增量幂等、不重分类)
- `wiki-cli changes`(或 MCP `wiki_changes`)— 看团队仓有哪些待更新知识(只读;`WIKI_ROOT`=团队 clone 时用)
- `/wiki-sync` — 确认后手动 `git pull` 当前库;**不会自动更新**

**维护(维护者)** — skill: wiki-lint
- 体检 / git init 前安全审计;底层 MCP `wiki_lint` / `wiki_sensitivity`

**命令行(CLI 与 MCP 同源,纯 Python 标准库)**
`wiki-cli init`(建库) `protocol` `search` `route` `get` `validate` `lint` `suggest` `scan`[进阶] `publish`[进阶] `sync-team`(团队→个人镜像) `changes`

**关键概念**:规则真源 = 团队仓 `AGENTS.md` + `_vocabulary.md`(受控分类清单);你的 AI 连哪个库由环境变量 `WIKI_ROOT` 决定。
新成员先看 onboarding;全新团队用 `wiki-cli init` 建库。
