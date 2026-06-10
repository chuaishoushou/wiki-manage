---
description: 列出个人知识库插件(flux-wiki)的所有能力 / 命令
---

请向用户展示知识库插件的能力清单(原样呈现即可):

> 约定:`wiki-cli` = `python3 "{{WIKI_CLI}}"`;个人库 = `{{WIKI_ROOT}}`。

**两类入口**:`wiki-query` / `wiki-ingest` / `wiki-lint` 是 **skill**(直接说"查 wiki…/把这条记进知识库/给知识库体检"即可触发);`/wiki-learn` / `/wiki-help` 是**斜杠命令**。底层都是 wiki-cli + 直接读写库文件。

| 想做什么 | 怎么做 |
|---|---|
| 查知识 | 直接问(skill wiki-query);或 `wiki-cli search "<词>"`、直接 Grep/Read 库文件 |
| 记知识 | 直接说"记一下…"(skill wiki-ingest);轻量加页 `wiki-cli new <type> <slug> --domain <主题>` |
| 学团队知识 | `/wiki-learn` —— 按 git 提交水位拿团队仓增量,逐页分类进个人库,带溯源 |
| 体检 | "给知识库体检"(skill wiki-lint);或 `wiki-cli lint` |
| 看状态 | `wiki-cli status`(库位置/布局/页数/主题/团队仓学习水位) |
| 建新库 / 修结构 | `wiki-cli init <目录>`(幂等:缺啥补啥,绝不覆盖已有页) |

**结构速查**(详见 `{{WIKI_ROOT}}/AGENTS.md`):`domains/<主题>/` 知识主体(新主题直接建目录) · `inbox/` 待整理 · `raw/` 原件只读 · `archive/` 归档(删除 = mv 进来) · `.wiki/` 工具产物 · `log.md` 台账。
