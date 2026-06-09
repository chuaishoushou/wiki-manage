---
description: (任何人)列出团队 wiki 插件的所有能力 / 命令
---

请向用户展示团队 wiki 插件的能力清单(原样呈现即可):

> 约定:下文 `wiki-cli` 均指 `python3 "${CLAUDE_PLUGIN_ROOT}/tools/bin/wiki-cli"`(插件市场 / CC 装时该变量可用);为便于阅读,命令正文沿用 `wiki-cli` 简写。

> 提示:`wiki-query` / `wiki-ingest` / `wiki-lint` 是 **skill(技能)**(直接说"查 wiki…/把这条记进 wiki/给 wiki 体检"即可触发);`/wiki-sync` / `/wiki-sync-team` / `/wiki-help` 是 **slash 命令**(`/` 直接调)。底层能力都来自 wiki-cli 纯 CLI + 直接读库文件。

**查知识(任何人)** — skill: wiki-query
- 直接问即可;底层用 `wiki-cli search` / `wiki-cli route` / `wiki-cli get`(或直接 Read/Grep 库里的 .md)

**加知识**
- 轻量(已知归属):`wiki-cli new <type> <slug> --domain <d>` —— 一条命令出合规页骨架
- 完整(新原始资料进团队仓):skill **wiki-ingest**(维护者)—— 敏感度闸 + 分类决策树

**同步团队知识**(按你的 `WIKI_ROOT` 指向分两种场景)

【`WIKI_ROOT`=个人库(常见)】把团队知识镜像进个人库,日常主线:
- `/wiki-sync-team` 或 `wiki-cli sync-team --team <团队仓clone>` — 把团队仓**原样镜像**到个人库 `wiki/team/` 只读区(可检索、增量幂等、不重分类;`--pull` 走 `git pull --ff-only`)

【`WIKI_ROOT`=团队 clone】直接消费团队 clone 本身:
- `wiki-cli changes` — 看该 clone 落后 origin 多少 / 有哪些待更新知识(只读)
- `/wiki-sync` — 确认后手动 `git pull --ff-only` 当前库;**不会自动更新**

**维护(维护者)** — skill: wiki-lint
- 体检 / git init 前安全审计;底层用 `wiki-cli lint` / `wiki-cli scan`(或直接 Read/Grep 库文件)

**命令行(纯 CLI,纯 Python 标准库)**
`wiki-cli init`(建库) `protocol` `search` `route` `get` `new`(轻量加页) `validate` `lint` `suggest` `scan`[进阶] `publish`[进阶] `sync-team`(团队→个人镜像) `changes`

**关键概念**:规则真源 = 团队仓 `AGENTS.md` + `_vocabulary.md`(受控分类清单);你的 AI 连哪个库由环境变量 `WIKI_ROOT` 决定。
新成员先看 onboarding;全新团队用 `wiki-cli init` 建库。
