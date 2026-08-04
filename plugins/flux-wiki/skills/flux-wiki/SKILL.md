---
name: flux-wiki
description: 个人知识库(flux-wiki)统一入口 skill——查询 / 记入 / 体检三种意图共用(原 wiki-query / wiki-ingest / wiki-lint 三 skill 已合并于此)。①查询:用户问及项目知识、模块、概念、踩坑,或命中 _routes.md 关键词时,先走路由表精确加载再全文检索综合,引用页面路径;②记:用户要"记一下/入库/沉淀/收录"知识、给出外部资料(docx/pdf/md/链接)、或说"这次踩坑记到 wiki"时,定主题落 domains/,拿不准放 inbox/,写完记台账;③体检:用户说"检查 wiki/体检/清理/lint/知识库有没有问题"时,跑确定性检查出结构化报告,修复需用户确认。按意图跑 wiki-cli guide <query|ingest|lint> 拿手册照做。
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python3:*), Bash(wiki-cli:*)
---

# flux-wiki:个人知识库统一入口(查 / 记 / 体检)

> 工具 `wiki-cli`:shim 已装在 `~/.local/bin`(在 PATH 时直接 `wiki-cli`,否则用全路径 `~/.local/bin/wiki-cli`);都不行就读 `~/.flux-wiki.json` 的 `wiki_manage` 字段,用 `python3 <wiki_manage>/plugins/flux-wiki/tools/bin/wiki-cli`。
> 本 skill 是入口不是手册。库的位置、写入层、流程细节都**不要凭记忆**:会话首次涉及知识库先跑 `wiki-cli context` 拿库位置/团队仓,再按下表意图取手册**严格照做**;手册拿不到(环境坏了)→ 跑 `wiki-cli doctor` 把问题报给用户,不要凭猜测写盘。

## 意图路由

| 用户意图 | 取手册 | 要点 |
|---|---|---|
| **查询**:问项目知识/模块/概念/踩坑,或命中 `_routes.md` 关键词 | `wiki-cli guide query` | 只读为主;路由表优先 → `wiki-cli search`/Grep → 综合作答引用页面路径;有持久价值的结论征得同意后沉淀进 queries/ |
| **记入**:"记一下/入库/沉淀/收录"、外部资料消化、踩坑入库 | `wiki-cli guide ingest` | 先查重,有相关页优先更新整合;定主题落 domains/,拿不准放 inbox/ |
| **体检**:"检查 wiki/体检/清理/lint" | `wiki-cli guide lint` | 环境层 `wiki-cli doctor` → 内容层 `wiki-cli lint` → 判读;**动手修复前需用户确认** |
| 学团队知识 | `wiki-cli guide learn`(或斜杠命令 /wiki-learn) | 按 git 提交水位学习并核销 |
| 能力总览 | `wiki-cli guide help` | 把能力清单原样呈现 |

## 红线(即使没拿到手册也必须遵守)

- **删除任何页 = mv 到 `archive/<YYYY-MM-DD>/`,绝不 `rm`**;`raw/` 只读。
- 每次写入在库根 `log.md` 追加一行(`## [YYYY-MM-DD] <op> | <标题>` + 涉及页面)。
- 先查重(search/Grep),有相关页优先更新整合,不建重复页。
- 查询态不落盘;要沉淀先征得用户同意。
