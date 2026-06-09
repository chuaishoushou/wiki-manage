# 安装(团队成员上手 · 三平台)

> **一句话**:`team-wiki`(知识)+ `wiki-manage`(工具)两个仓都 clone 到 `~/AI/` 下,设好库的位置,按你的平台跑一条命令。
> **约定路径**:把团队知识库 clone 到 **`~/AI/team-wiki`**。只要放在这个约定位置,即使没设环境变量、即使从 GUI/Desktop 启动,也能自动连上团队库(工具内置了对该路径的兜底)。

---

## 第 0 步:前置条件(所有平台,先确认)

```bash
python3 --version     # 需 ≥ 3.8。没有:macOS `brew install python3` / Ubuntu `sudo apt install python3`
git --version         # 需要 git
claude --version      # 仅 Claude Code 用户需要(走插件市场或 wiki-init 链接 skill/命令时用到)
```

- **无需 `pip install`**:工具是纯 Python 标准库,clone 下来就能跑,不装任何依赖。
- **两个仓都是 public**:直接 `git clone`,**不需要** GitHub token / 授权。

---

## 第 1 步:clone 两个仓 + 设库位置(所有平台通用,顺序不能反)

```bash
git clone https://github.com/chuaishoushou/team-wiki.git   ~/AI/team-wiki      # 团队知识(约定路径,所有路径都要)
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage   # 工具/插件(必需:wiki-init 与 wiki-cli 都在此仓)
echo 'export WIKI_ROOT="$HOME/AI/team-wiki"' >> ~/.zshrc && export WIKI_ROOT="$HOME/AI/team-wiki"
# bash 用户把 ~/.zshrc 换成 ~/.bashrc;Windows PowerShell 用 setx WIKI_ROOT "%USERPROFILE%\AI\team-wiki"
```

> ⚠️ 一定先 clone `team-wiki` 再跑第 2 步;反过来会因为"库还不存在"而自检失败。
> `WIKI_ROOT` 是第一道防线(终端启动时生效);把库放在约定路径 `~/AI/team-wiki` 是第二道网(GUI 启动丢环境变量时兜底)。两者都做最稳。

---

## 第 2 步:按平台安装

> **最快:一条命令搞定全部。** 在 `wiki-manage` 目录里跑 —— macOS/Linux: **`./install.sh`**;Windows: **`install.cmd`**。自动探测本机的 Claude / Codex / Cursor 并配好(Cursor 会打印 User Rules 块供你粘进 设置→Rules)。下面是各平台的细节/手动版,排障、只装单个工具、或想走插件市场时看。

### Claude Code —— 主推 wiki-init(零中断),插件市场为备选

**路 A:wiki-init(推荐,无确认弹窗)**:
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform cc --wiki-root ~/AI/team-wiki --write
```
软链 skill/命令 + 写规则指针(`~/.claude/CLAUDE.md` 告诉 AI 库在哪、查知识直接 Read/Grep + 调 wiki-cli),然后重启 Claude Code。(去掉 `--write` 只打印不落地,先看再执行。)

**路 B:插件市场(备选,有 trust/enable 提示)** —— 在 Claude Code 里输入:
```
/plugin marketplace add chuaishoushou/wiki-manage
/plugin install flux-wiki@flux-wiki-marketplace
```
重启 Claude Code 生效,skill / 命令 / hooks / 规则指针随插件一起装好。

> ⚠️ 两条路**二选一,勿同时用**(skill/命令会重复加载)。都依赖第 1 步的 `~/AI/team-wiki`;从 GUI/Desktop 启动 CC 不继承终端 `export`,但库在约定路径时 wiki-cli 仍自动兜底连上团队库。

### Codex —— 主推 wiki-init,插件市场为备选

**路 A:wiki-init(推荐,无确认弹窗)**:
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex --wiki-root ~/AI/team-wiki --write
```
写入 `~/.codex/AGENTS.md` 规则指针(告诉 AI 团队库位置 + 用 Read/Grep 查知识、用 wiki-cli 做协议/检索/校验),然后**重启 Codex**。

**路 B:插件市场(备选)** —— 本仓已备 `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json`:
```bash
codex plugin marketplace add chuaishoushou/wiki-manage   # 命令名以 `codex plugin --help` 为准
codex plugin install flux-wiki
```
重启 Codex。装的是 skills + hooks(Codex 不支持 slash command,故不含 commands)。

> ⚠️ 二选一,勿同时用。

### Cursor Pro —— 主推 User Rules(全局粘一次)

> Cursor Pro 无自托管插件市场(team marketplace 仅 Teams/Enterprise),也无可写的全局规则文件。故走 **User Rules 粘贴**(一次性全局)或项目级 `.cursor/rules/`。

**路 A:User Rules 全局(推荐,粘一次管所有项目)**:
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform cursor --wiki-root ~/AI/team-wiki
```
复制打印出的「User Rules」纯文本块(已自动填好路径,无占位符)→ Cursor **设置 → Rules → User Rules** → 粘一次。之后对话涉及 wiki 时,AI 按规则直接 Read/Grep 库文件并调 wiki-cli。

**路 B:项目级规则(版本可控,每项目一次)**:
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform cursor --wiki-root ~/AI/team-wiki --cursor-project <项目根> --write
```
写入该项目 `.cursor/rules/wiki.mdc`,重启 Cursor,用 `@wiki` 触发。每个要用团队 wiki 的项目重复一次。

---

## 第 3 步:黄金验收(命令行,不依赖先把 AI 跑起来)

```bash
WIKI_ROOT=~/AI/team-wiki python3 ~/AI/wiki-manage/plugins/flux-wiki/tools/bin/wiki-cli protocol
```
看到 **「连接来源: WIKI_ROOT 环境变量 ✅」**(或「约定团队路径 ~/AI/team-wiki ✅」)+ **「协议版本: … OK ✅」** = 工具与库都就绪。

再加分项(对话式探针):新开 AI 会话问「**团队 wiki 有哪些 domain?**」答得出 = 规则指针已加载。
让 AI 跑 `wiki-cli protocol`,确认输出里 `root_source` 是 `env` 或 `team-default`、`warnings` 为空。

> 若 `root_source` 显示 `personal-fallback` 或 `cwd` → 你连的可能不是团队库:确认 `~/AI/team-wiki` 存在,或显式 `export WIKI_ROOT`。

---

## 更新(统一,极简)

```bash
git -C ~/AI/wiki-manage pull     # 更新工具(路 B 的 skill 经符号链接即时生效;wiki-cli 即时生效)
git -C ~/AI/team-wiki  pull     # 更新团队知识(= /wiki-sync)
```
- 走插件市场(备选路)的 CC 用户:`/plugin marketplace update` 拉取工具更新。
- 想钉到稳定版:`git -C ~/AI/wiki-manage checkout <tag>`;回滚:`git checkout <commit>`。

## 卸载(可逆)

```bash
# wiki-init 装的(主路):
rm ~/.claude/skills/wiki-ingest ~/.claude/skills/wiki-query ~/.claude/skills/wiki-lint
rm ~/.claude/commands/wiki-*.md   # wiki-sync.md / wiki-sync-team.md / wiki-help.md
# 删除 ~/.claude/CLAUDE.md 中以 "# === flux-wiki (auto by wiki-init) ===" 起的那一段(规则指针)
# 插件市场装的(备选路):在 CC 里 /plugin uninstall flux-wiki@flux-wiki-marketplace
```

---

## 三平台机制(诚实)

统一主推 wiki-init(零中断),插件市场为备选。组件支持有差异:

| 平台 | 主推(wiki-init) | 备选 | 组件 |
|---|---|---|---|
| **Claude Code** | 写 CLAUDE.md 指针 + 软链 skills/命令(用户级全局) | 插件市场(有 trust 提示) | skills + slash 命令 + hooks |
| **Codex** | 写 `~/.codex/AGENTS.md` 指针(用户级全局) | `codex plugin marketplace add` | skills + hooks(**不支持 slash command**) |
| **Cursor Pro** | User Rules 全局粘一次 / 项目级 `.cursor/rules` | ❌ 无自托管市场(仅 Teams/Enterprise) | rules(.mdc);走市场时另有 skills/commands |

> 实测边界(诚实):本机仅 Claude Code 可端到端验证(`claude plugin validate` 通过、wiki-init 落地);Codex/Cursor 的真机 `marketplace add` / 安装体验需在装有对应 CLI 的机器上确认。

> **维护者 checklist**(三家 plugin.json 声明粒度不同,漏声明不报错、只静默缺功能,加/改组件时对照):
>
> | 平台 | plugin.json 需显式声明 | 靠目录自动发现 |
> |---|---|---|
> | Claude Code | (无,全自动) | `skills/` `commands/` `hooks/` |
> | Codex | `skills` | `hooks/hooks.json`(自动检测) |
> | Cursor | `skills`/`commands`/`rules`/`hooks` | (按声明,本插件 `hooks` 显式留空) |

**跨平台一致的内核** = wiki-cli + 库本地 .md,三家结果一致:AI 直接读本地 .md 查知识,用确定性的 CLI 做协议/检索/校验。

## Windows 支持

- **一键安装走 `install.cmd`**(不要用 `./install.sh` —— 那是 bash,Windows 原生 cmd/PowerShell 跑不了)。`install.cmd` 自动找 `py`/`python`、自动探测三平台,等价于 mac/Linux 的 `./install.sh`。
- **Python**:装 Python 3.8+(python.org 勾选 *Add to PATH*,或 Microsoft Store 版)。命令行直接用 `py` 或 `python`(不必是 `python3`);`install.cmd` 与 `wiki-init` 内部都用当前解释器绝对路径,不依赖 `python3` 这个名字。
- **符号链接**:装 Claude skill/命令时优先软链;Windows 非管理员 / 未开**开发者模式**会自动回退为**复制**(代价:`git pull` 后需重跑 `install.cmd` 才更新)。开了开发者模式则软链可用,`git pull` 即时生效。
- **库路径 / 环境变量**:`install.cmd D:\path\to\team-wiki` 直接传;或先 `setx WIKI_ROOT "%USERPROFILE%\AI\team-wiki"`(setx 对新开的终端生效)。默认会自动探测 `%USERPROFILE%\AI\team-wiki`。
- **Cursor**:与 mac 一致 —— `install.cmd` 打印 User Rules 文本,粘进 设置→Rules→User Rules 一次。
- 路径分隔符、`~`、`%LOCALAPPDATA%` 等已在工具内用 `os.path` / `expanduser` / `expandvars` 处理,Windows 正斜杠/反斜杠混用均可。
