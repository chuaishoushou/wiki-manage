# flux-wiki 能力清单

> 个人库 = `{{WIKI_ROOT}}`;`wiki-cli` = `{{WIKI_CLI}}`(`~/.local/bin/wiki-cli` 是同一工具的 shim)。

**两类入口**:`flux-wiki` 是**统一 skill**(查/记/体检三种意图共用:直接说"查 wiki…/把这条记进知识库/给知识库体检"即可触发,按意图路由到对应手册);`/wiki-learn` / `/wiki-help` 是**斜杠命令**(Codex/Cursor 无斜杠命令,说同样的话或跑 `wiki-cli guide <op>` 等价)。底层都是 wiki-cli + 直接读写库文件。

| 想做什么 | 怎么做 |
|---|---|
| 查知识 | 直接问(skill flux-wiki·查询意图);或 `wiki-cli search "<词>"`、直接 Grep/Read 库文件 |
| 记知识 | 直接说"记一下…"(skill flux-wiki·记入意图);轻量加页 `wiki-cli new <type> <slug> --domain <主题>` |
| 学团队知识 | `/wiki-learn`(或 `wiki-cli guide learn` 照做)—— 按 git 提交水位拿团队仓增量,逐页分类进个人库,带溯源;`learn --verify` 核销后 `--mark` 记水位 |
| 体检 | "给知识库体检"(skill flux-wiki·体检意图);环境层 `wiki-cli doctor`,内容层 `wiki-cli lint` |
| 看状态 | `wiki-cli status`(库位置/布局/页数/主题/团队仓学习水位);会话开头用 `wiki-cli context` |
| 配置 | `wiki-cli config get`;团队仓登记 `wiki-cli config team <名> --path <路径> --branch <分支> --exclude <glob,glob>` |
| 建新库 / 修结构 | `wiki-cli init <目录>`(幂等:缺啥补啥,绝不覆盖已有页) |

**结构速查**(详见 `{{WIKI_ROOT}}/AGENTS.md`):`domains/<主题>/` 知识主体(新主题直接建目录) · `inbox/` 待整理 · `raw/` 原件只读 · `archive/` 归档(删除 = mv 进来) · `.wiki/` 工具产物 · `log.md` 台账 · `revisions/` 审计(learn/lint 自动落)。
