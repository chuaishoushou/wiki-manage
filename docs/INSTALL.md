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
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage   # 工具/插件(仅路 B/wiki-init 需要;路 A 插件市场自带 wiki-cli,可跳过)
echo 'export WIKI_ROOT="$HOME/AI/team-wiki"' >> ~/.zshrc && export WIKI_ROOT="$HOME/AI/team-wiki"
# bash 用户把 ~/.zshrc 换成 ~/.bashrc;Windows PowerShell 用 setx WIKI_ROOT "%USERPROFILE%\AI\team-wiki"
```

> ⚠️ 一定先 clone `team-wiki` 再跑第 2 步;反过来会因为"库还不存在"而自检失败。
> `WIKI_ROOT` 是第一道防线(终端启动时生效);把库放在约定路径 `~/AI/team-wiki` 是第二道网(GUI 启动丢环境变量时兜底)。两者都做最稳。

---

## 第 2 步:按平台安装

### Claude Code —— 两条路,任选其一

**路 A:插件市场(推荐,最接近"一个链接")** —— 在 Claude Code 里输入:
```
/plugin marketplace add chuaishoushou/wiki-manage
/plugin install flux-wiki@flux-wiki-marketplace
```
重启 Claude Code 生效。skill / 命令 / hooks / 规则指针随插件一起装好。

**路 B:wiki-init(不走市场,git 手动)**:
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform cc --wiki-root ~/AI/team-wiki --write
```
链接 skill/命令 + 写规则指针(`~/.claude/CLAUDE.md` 告诉 AI 库在哪、查知识直接 Read/Grep + 调 wiki-cli),然后重启 Claude Code。(去掉 `--write` 只打印不落地,先看再执行。)

> 两条路都依赖第 1 步的 `~/AI/team-wiki`。从 GUI/Desktop 启动 CC 时不会继承终端的 `export`,但因为库在约定路径,wiki-cli 仍能自动兜底连上团队库。

### Codex —— 两条路,任选其一

**路 A:插件市场(推荐)** —— 本仓已备 `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json`:
```bash
codex plugin marketplace add chuaishoushou/wiki-manage   # 命令名以 `codex plugin --help` 为准
```
然后在 Codex 里 `/plugin install flux-wiki`,**重启 Codex**。装的是 skills + hooks(Codex 不支持 slash command,故不含 commands)。

**路 B:wiki-init(不走市场,git 手动)**:
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex --wiki-root ~/AI/team-wiki --write
```
写入 `~/.codex/AGENTS.md` 规则指针(告诉 AI 团队库位置 + 用 Read/Grep 查知识、用 wiki-cli 做协议/检索/校验),然后**重启 Codex**。

### Cursor —— 两条路,任选其一

**路 A:插件市场(推荐)** —— 本仓已备 `.cursor-plugin/plugin.json` + `.cursor-plugin/marketplace.json` + `rules/wiki.mdc`。Cursor 经**市场面板安装**(官方暂无 CLI 装命令;提交市场见 `cursor.com/marketplace/publish`)。装好后用 `@wiki` 触发规则,让 AI 直接 Read/Grep 库文件并调 wiki-cli。

**路 B:wiki-init(每个项目配一次)**:
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform cursor --wiki-root ~/AI/team-wiki --cursor-project <项目根> --write
```
写入该项目的 `.cursor/rules/wiki.mdc` 规则指针,然后重启 Cursor。每个要用团队 wiki 的项目重复一次;在 Cursor 里用 `@wiki` 触发,让 AI 直接 Read/Grep 库文件并调 wiki-cli。

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
- 走插件市场(路 A)的 CC 用户:`/plugin marketplace update` 拉取工具更新。
- 想钉到稳定版:`git -C ~/AI/wiki-manage checkout <tag>`;回滚:`git checkout <commit>`。

## 卸载(可逆)

```bash
# 路 A:在 CC 里 /plugin uninstall flux-wiki@flux-wiki-marketplace
# 路 B:
rm ~/.claude/skills/wiki-ingest ~/.claude/skills/wiki-query ~/.claude/skills/wiki-lint
rm ~/.claude/commands/wiki-*.md   # wiki-sync.md / wiki-sync-team.md / wiki-help.md
# 删除 ~/.claude/CLAUDE.md 中 "wiki-init" 标记的那一段(规则指针)
```

---

## 平台成熟度(诚实)

三平台都有插件市场、清单格式高度一致,本仓同时提供三家清单。组件支持有差异:

| 平台 | 安装 | 组件 |
|---|---|---|
| **Claude Code** | 插件市场(路 A)或 wiki-init(路 B) | skills + slash 命令 + hooks 自动加载 |
| **Codex** | 插件市场(路 A,`codex plugin marketplace add`)或 wiki-init(路 B) | skills + hooks(**不支持 slash command**) |
| **Cursor** | 市场面板安装(路 A,无 CLI 命令)或 wiki-init(路 B) | skills + commands + rules(.mdc);**hooks 留空**(规避跨平台格式差异,开场指引交给 `@wiki` 规则) |

> 实测边界(诚实):本机仅 Claude Code 可端到端验证(`claude plugin validate` 通过);Codex/Cursor 清单已逐字段对官方文档核实,但真机 `marketplace add` / 安装体验需在装有对应 CLI 的机器上确认。

> **维护者 checklist**(三家 plugin.json 声明粒度不同,漏声明不报错、只静默缺功能,加/改组件时对照):
>
> | 平台 | plugin.json 需显式声明 | 靠目录自动发现 |
> |---|---|---|
> | Claude Code | (无,全自动) | `skills/` `commands/` `hooks/` |
> | Codex | `skills` | `hooks/hooks.json`(自动检测) |
> | Cursor | `skills`/`commands`/`rules`/`hooks` | (按声明,本插件 `hooks` 显式留空) |

**跨平台一致的内核** = wiki-cli + 库本地 .md,三家结果一致:AI 直接读本地 .md 查知识,用确定性的 CLI 做协议/检索/校验。

## Windows 已知限制

- 命令里的 `python3` 在标准 Windows(python.org 安装器只给 `python`/`py`)可能找不到 → 装 Microsoft Store 版 Python(自带 `python3` 别名),或为 `python` 建一个 `python3` 别名。`wiki-init` 生成规则指针时已改用当前解释器的绝对路径,规避该问题。
- 路 B 链接 skill/命令用符号链接;Windows 非管理员/未开开发者模式时会自动回退为**复制**(代价:`git pull` 后需重跑 `wiki-init` 才更新)。
- 环境变量:PowerShell 用 `setx WIKI_ROOT "%USERPROFILE%\AI\team-wiki"`。
