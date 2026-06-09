# wiki-manage

让一个团队(~15 人)共享**同一套规范化的 AI 知识库**:统一层级 / 分类 / 入库规则,跨 Claude Code / Codex / Cursor。

## 安装

> ⚠️ **这不是能在插件市场安装的"原生插件"。** 别用 `/plugin marketplace add`、`codex plugin install`、Cursor 扩展市场 —— 那些路都走不通(本仓刻意不含 `marketplace.json` / `plugin.json`)。**唯一安装方式是 `git clone` + 安装脚本。** 三平台(Claude Code / Codex / Cursor)同一套,只是装完收尾不同。

### A. 给 AI 助手的执行指令(把本节整段发给任意平台的 AI)

> 你(AI)被用户要求安装这个工具。按步骤做,**不要跳步**。

**第 0 步 · 你不是终端用户。** 你执行 shell 时 stdin 不是交互终端,本仓脚本的交互提问(`input()`)对你会直接 EOF —— 你问不到用户。所以**绝不要裸跑 `./install.sh` / `install.cmd` 等它问你**(那样会被脚本以退出码 2 拦截)。正确做法:先在对话里问用户,再用命令行参数把答案传进去。

**第 1 步 · 先在对话里问用户这三个问题**(每次都必须问,无论磁盘上是否已有 `~/AI/wiki`、`~/.claude` —— 检测只决定"配哪个平台",不决定"是否提问"):
1. 个人库放哪个目录?(你日常读写/入库的主库;默认 `~/AI/wiki`)
2. 团队仓在哪个目录?(团队知识源的本地 git clone,只读;默认 `~/AI/team-wiki`)
3. 现在就初始化个人库吗?(选"是"→下面用 `--init`;选"否"→用 `--no-init`;默认否)

**第 2 步 · 确认你当前所在平台**(你自己知道:Claude Code / Codex / Cursor),下面用 `--platform` 显式指定,别依赖自动探测(新机/容器可能探测不到而被跳过)。

**第 3 步 · clone 工具仓到固定目录**(已存在就 `git -C ~/AI/wiki-manage pull`,别重复 clone):

macOS / Linux:
```bash
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage && cd ~/AI/wiki-manage
```
Windows(cmd / PowerShell,逐行,**别用 `&&`**):
```bat
git clone https://github.com/chuaishoushou/wiki-manage.git %USERPROFILE%\AI\wiki-manage
cd %USERPROFILE%\AI\wiki-manage
```

**第 4 步 · 按平台运行**(填入第 1 步回答;路径一律加引号;选了初始化把 `--no-init` 换成 `--init`)。**直接调 `bin/wiki-init`,不走 install.sh** —— 这样 `--platform` / `--init` 才能精确传达。

Claude Code(macOS/Linux):
```bash
python3 bin/wiki-init --platform cc --personal-root "$HOME/AI/wiki" --team-root "$HOME/AI/team-wiki" --write --no-input --no-init
```
Codex(macOS/Linux):
```bash
python3 bin/wiki-init --platform codex --personal-root "$HOME/AI/wiki" --team-root "$HOME/AI/team-wiki" --write --no-input --no-init
```
Cursor(macOS/Linux,**不要 `--write`** —— Cursor 没有可写的全局规则文件,脚本会把 User Rules 文本打到 stdout):
```bash
python3 bin/wiki-init --platform cursor --personal-root "$HOME/AI/wiki" --team-root "$HOME/AI/team-wiki" --no-input --no-init
```
**Windows**:把 `python3` 换成 `py -3`(没有 `py` 用 `python`),`$HOME/AI/...` 换成 `"%USERPROFILE%\AI\..."`;**绝不要用 `bash ./install.sh` 或 `./install.sh`**(那是 bash,cmd/PowerShell 跑不了)。

**第 5 步 · 收尾(按平台):**
- **Claude Code**:已写 `~/.claude/CLAUDE.md` 指针 + 软链 skills/命令。让用户**重启 Claude Code**。
- **Codex**:已写 `~/.codex/AGENTS.md` 指针。让用户**重启 Codex**。(Codex 不支持 slash 命令,只装指针,别承诺 `/wiki-*`。)
- **Cursor**:从输出里两条 `────` 分隔线之间取出整段文本,**原样逐字**转述给用户,让他粘进 **Cursor 设置 → Rules → User Rules**(一次,管所有项目)—— 这是 Cursor 唯一的手动步骤。

**第 6 步 · 报告。** 退出码 0 即成功(用户选"暂不初始化"时退出码也是 0);若非 0,把完整输出贴给用户,别擅自重试。

> 诚实声明:本工具目前仅在 Claude Code 端做过端到端真机验证;Codex / Cursor 的 AI 自安装属设计成立、真机待验。在那两个平台若行为异常,把输出反馈用户。

### B. 人工终端安装(人在终端自己敲,交互式)

> 这条路才用脚本的交互问答:逐项问两个库的位置(回车用默认),写完指针后再问是否初始化个人库(默认否)。**别预先 `export`/`set` `PERSONAL_ROOT`/`TEAM_ROOT`/`WIKI_ROOT`**,否则会被当默认值。

macOS / Linux:
```bash
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
cd ~/AI/wiki-manage
./install.sh
```
Windows(cmd / PowerShell,逐行;**禁止** `bash ./install.sh`,一律 `.\install.cmd`):
```bat
git clone https://github.com/chuaishoushou/wiki-manage.git %USERPROFILE%\AI\wiki-manage
cd %USERPROFILE%\AI\wiki-manage
.\install.cmd
```
收尾同上(A 第 5 步):Claude Code / Codex 重启即生效;Cursor 把打印的 User Rules 粘进 设置 → Rules → User Rules。

> 团队仓还没 clone 也不阻断,脚本会提示你 clone 命令(`git clone https://github.com/chuaishoushou/team-wiki.git ~/AI/team-wiki`)。
> 更新 / 卸载 / 排障 / 只装单平台:见 [docs/INSTALL.md](docs/INSTALL.md)。

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
