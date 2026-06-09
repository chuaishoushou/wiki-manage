# wiki-manage

让一个团队(~15 人)共享**同一套规范化的 AI 知识库**:统一层级 / 分类 / 入库规则,跨 Claude Code / Codex / Cursor。

## 安装(唯一方式 · git)

> ⚠️ **这不是能在插件市场安装的"原生插件"。别用** `/plugin marketplace add`、`codex plugin install`、Cursor 扩展市场 —— 那些路都走不通(会报 plugin.json 校验错或根本找不到)。**唯一安装方式就是下面这三行 git 命令。** 让 AI 替你装,也把这三行原样发给它。

**macOS / Linux**
```bash
git clone https://github.com/chuaishoushou/wiki-manage
cd wiki-manage
./install.sh
```

**Windows**(cmd 或 PowerShell)
```bat
git clone https://github.com/chuaishoushou/wiki-manage
cd wiki-manage
install.cmd
```

`install.sh` 会**交互问你两个目录**(直接回车用默认值):

1. **个人库** — 你日常读写 / 入库的知识库。不存在会**自动建好**。默认 `~/AI/wiki`。
2. **团队仓** — 团队知识源(只读)。默认 `~/AI/team-wiki`;还没 clone 也没关系,会**提示你 clone**,不阻断安装。

然后它自动探测本机装了哪些工具,各自配好规则指针(告诉该工具里的 AI:两个库在哪、怎么查/入库/同步),**重启客户端即生效**:

- **Claude Code / Codex** → 全自动(写 `~/.claude/CLAUDE.md` / `~/.codex/AGENTS.md` 规则指针;Claude 另把 skills/命令软链进 `~/.claude/`)。
- **Cursor** → 脚本打印一段「User Rules」纯文本(已填好库路径);复制 → Cursor **设置 → Rules → User Rules** → 粘一次,管所有项目。Cursor 没有可写的全局规则文件,**这是唯一的手动一步**。

> **不想交互?** 按顺序给两个路径(个人库在前、团队仓在后):`./install.sh ~/AI/wiki ~/AI/team-wiki`;或用环境变量 `PERSONAL_ROOT=… TEAM_ROOT=… ./install.sh`。
> **更新**:`git pull` 后重跑 `./install.sh`(Cursor 重新粘一次 User Rules)。
> **更新 / 卸载 / 排障 / 只装单个平台**:见 [docs/INSTALL.md](docs/INSTALL.md)。

## 两个 git 仓,别混

```
  team-wiki  (知识内容,你"读"它)            wiki-manage  (工具,你"装"它,= 本仓)
  ┌─────────────────────────────┐           ┌──────────────────────────────────┐
  │ wiki/domains/** 知识页        │  ◀─只读── │ flux-wiki: skills + wiki-cli CLI   │
  │ AGENTS.md   协议(规则真源)    │ Read/Grep │   /wiki-ingest /query /lint        │
  │ _vocabulary.md 受控词表        │  + CLI    │   wiki-cli(含 init 建库)         │
  │ _routes.md  关键词路由         │           │   规则指针(三平台告诉 AI 库在哪) │
  └─────────────────────────────┘           └──────────────────────────────────┘
       1-2 名维护者写,15 人只读                成员装它来查/维护者用它来管
```

**术语速查**:`team-wiki`=知识内容仓 · `wiki-manage`=工具仓(本仓) · `flux-wiki`=本仓里的工具集(skills + `wiki-cli` + 三平台规则指针模板) · `_vocabulary.md`=团队允许用的分类清单 · `AGENTS.md`=操作协议。

## 工作原理(为什么是 git 而不是插件市场)

跨平台一致的内核 = **确定性的 `wiki-cli`(纯 Python 标准库,零依赖)+ 本地库的 `.md` 文件**:AI 直接 Read/Grep 库文件查知识,用 CLI 做协议 / 检索 / 校验 / 同步。`install.sh`(内部调 `bin/wiki-init`)只做两件事:① 把"规则指针"写进每个平台各自认的位置(CLAUDE.md / AGENTS.md / Cursor User Rules);② 在 Claude Code 侧把 skills / 命令软链进 `~/.claude/`。

**不走插件市场是有意的**:Cursor Pro 没有自托管市场;Claude / Codex 的市场命令各不相同、还有 trust 提示和 `plugin.json` 校验坑。三平台唯一能统一的,就是 `git clone` + 一个 Python 脚本。所以本仓**不提供** `marketplace.json` / `plugin.json` —— 避免任何 AI 把它误当原生插件去装而卡住。

## 我是谁,从哪开始

| 你是… | 最短路径 |
|---|---|
| **全新团队(还没有 wiki)** | `wiki-cli init <目录>` 建一个合规空库 → 见 [迁移 runbook](docs/migration-runbook.md) |
| **只读成员(15 人里的多数)** | 只需查知识 → 见 [onboarding](docs/onboarding.md) 的「只读成员最短路径」 |
| **维护者(写/ingest/lint)** | 见 [迁移 runbook](docs/migration-runbook.md) + [spec](docs/specs/2026-06-07-v2-team-design.md) |

## 工具能力(只读;纯 CLI + 直接读文件)

| `wiki-cli <cmd>` | 作用 |
|---|---|
| `init <dir>` | **建库 / 层级修复(幂等,可多次跑:缺啥补啥、不覆盖已有;`--check` 只体检)** |
| `new <type> <slug> --domain` | **轻量新建一页合规骨架**(已知归属时,免手写 frontmatter) |
| `protocol` | 协议版本 + 连接来源 + 当前分支/版本 + 新鲜度 + 闭集 |
| `changes` | **检查团队仓有哪些待更新知识**(git fetch+diff,按模块/概念分组,区分大/小更新;只读不应用) |
| `search` / `route` / `get` | 检索 / 路由解析 / 取页(也可 AI 直接 Read/Grep 库 .md) |
| `validate` / `lint` | 单页校验 / 全库体检 |
| `suggest` | 入库落位建议(domain/type/slug) |
| `scan` `[进阶]` | 敏感度扫描(分享私库前用)— 写报告 |
| `publish` `[进阶]` | 脱敏白名单导出团队仓 — 含写副作用 |

## 快速开始(在本仓目录里)

```bash
# 一键自测(unittest + CLI 端到端 + wiki-init + evals,自建临时 fixture)
python3 plugins/flux-wiki/tools/selftest.py

# 体验冷启动:30 秒建一个全新合规库看看长啥样
python3 plugins/flux-wiki/tools/bin/wiki-cli init /tmp/demo-wiki --domains backend,frontend
WIKI_ROOT=/tmp/demo-wiki python3 plugins/flux-wiki/tools/bin/wiki-cli protocol

# 看三平台 onboarding 会写什么(不加 --write 只打印,不落地)
python3 bin/wiki-init --platform all --no-input
```

## 位置可配置 / 多个库

库的位置由 `WIKI_ROOT` 环境变量(或每条命令的 `--root`)决定,可指向任意路径、可有多个:
```bash
wiki-cli --root ~/AI/wiki   protocol     # 库 A
wiki-cli --root ~/AI/wiki2  protocol     # 库 B(各自独立)
wiki-cli init ~/AI/wiki2 --domains kb    # 新库不存在?init 建出来(幂等,可重复跑)
wiki-cli init ~/AI/wiki2 --check         # 结构健康检查:缺层级会报并提示修复
```
- `init` 是**幂等**的:空目录建全套,已存在则只补缺失结构(层级修复),已完整则 no-op,**绝不覆盖你已有的页**。
- 多库切换:每条命令用 `--root` 指向不同库,或切换 `WIKI_ROOT` 环境变量即可,互不干扰。

## 文档

- [安装 INSTALL](docs/INSTALL.md) — 唯一 git 安装(clone + `./install.sh` 配两个库)+ 更新 / 卸载 / 只装单平台 / 排障
- [成员 onboarding](docs/onboarding.md) — 按角色上手 + 验收清单
- [维护者迁移 runbook](docs/migration-runbook.md) — 从零建库 / 从个人库迁团队
- [仓库模型 repos-model](docs/repos-model.md) — 团队仓 vs 个人库、pull≠重 ingest、贡献走 PR(**防误用必读**)
- [v2 团队设计 spec](docs/specs/2026-06-07-v2-team-design.md) — 架构、防漂移、风险(深读)
- [skill 触发 evals](plugins/flux-wiki/evals/README.md)
- 团队仓 `.claude/` 模板:[examples/team-wiki-dotclaude/](examples/team-wiki-dotclaude/)

> 安全审计 / lint 基线报告是**针对你自己库的本地产物**(含具体内容,不随仓分发,已 gitignore)。
> 自己生成:`wiki-cli scan --out <file>` / `wiki-cli lint --out <file>`。

## ⚠️ 分享给团队前(若你迁移的是已有私库)

已有私库可能含客户名/凭证/攻击面描述。**`git init`/分享前**先 `wiki-cli scan` 裁定 `sensitivity`,用 `wiki-cli publish` 只导出 `sensitivity<=team`,**绝不 push 整库**。全新 `wiki-cli init` 建的空库无此问题。

## 路线图
v0 安全基线 → **v1 git + skill + 冷启动 scaffolder**(已实现)→ **v2 CLI + 规则指针 + 双库交互安装**(已实现)→ v3 Web(后期)。

## License
MIT — 见 [LICENSE](LICENSE)
