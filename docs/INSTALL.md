# 安装(团队成员上手 · 三平台 · 唯一 git 入口)

> **一句话**:clone 工具仓 `wiki-manage`,跑 `./install.sh` —— 它会交互配好**两个库**:个人库(日常读写主线,默认 `~/AI/wiki`,不存在自动建)+ 团队仓(团队知识源的只读 clone,默认 `~/AI/team-wiki`)。
> **约定路径**:个人库 `~/AI/wiki`、团队仓 `~/AI/team-wiki`。放在约定位置时,即使没设环境变量、从 GUI/Desktop 启动也能自动兜底连上。
> ⚠️ **本仓不是原生插件**,刻意不提供 `marketplace.json` / `plugin.json`。别用 `/plugin marketplace add`、`codex plugin install`、Cursor 扩展市场去装 —— 那些会报校验错或找不到。**唯一入口就是 `git clone` + `./install.sh`。**

---

## 第 0 步:前置条件(所有平台)

```bash
python3 --version     # 需 ≥ 3.8。没有:macOS `brew install python3` / Ubuntu `sudo apt install python3`
git --version         # 需要 git
```

- **无需 `pip install`**:工具是纯 Python 标准库,clone 下来就能跑,不装任何依赖。
- **两个仓都是 public**:直接 `git clone`,**不需要** GitHub token / 授权。

---

## 第 1 步:clone 工具仓 + clone 团队仓(个人库无需手动建)

```bash
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage   # 工具(必需:wiki-init 与 wiki-cli 都在此仓)
git clone https://github.com/chuaishoushou/team-wiki.git   ~/AI/team-wiki     # 团队知识(只读源;可选先 clone——装时不存在会提示你 clone)
# 个人库不用手动建:第 2 步的 ./install.sh 会在它不存在时自动 wiki-cli init 建好(默认 ~/AI/wiki)。
```

> ✅ `./install.sh` 不硬性要求"先 clone 团队仓":个人库会自动建,团队仓缺失只提示不阻断。先 clone 团队仓更顺(装完即可 sync),但不是硬前置。

---

## 第 2 步:跑 install.sh(一条命令,三平台全配)

在 `wiki-manage` 目录里:

```bash
# macOS / Linux
./install.sh
# Windows(cmd / PowerShell)
install.cmd
```

它会**交互询问个人库 + 团队仓两个位置**(回车用默认),然后自动探测本机的 Claude Code / Codex / Cursor 并各自配好:

- **Claude Code / Codex** → 写规则指针(`~/.claude/CLAUDE.md` / `~/.codex/AGENTS.md`)+ Claude 软链 skills/命令,重启即生效。
- **Cursor** → 打印一段 User Rules 文本,复制粘进 **设置 → Rules → User Rules**(唯一手动一步)。

**不想交互 / 只装单个平台 / CI** —— 直接调 `bin/wiki-init`,显式给两个库:

```bash
# 只配 Claude Code
python3 ~/AI/wiki-manage/bin/wiki-init --platform cc \
    --personal-root ~/AI/wiki --team-root ~/AI/team-wiki --write

# 只配 Codex
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex \
    --personal-root ~/AI/wiki --team-root ~/AI/team-wiki --write

# 只配 Cursor(打印 User Rules,粘一次;不落文件)
python3 ~/AI/wiki-manage/bin/wiki-init --platform cursor \
    --personal-root ~/AI/wiki --team-root ~/AI/team-wiki
# Cursor 项目级规则(写该项目 .cursor/rules/wiki.mdc,每项目一次,用 @wiki 触发):
python3 ~/AI/wiki-manage/bin/wiki-init --platform cursor \
    --personal-root ~/AI/wiki --team-root ~/AI/team-wiki --cursor-project <项目根> --write
```

> 去掉 `--write` 只打印不落地,先看再执行。`--no-input` 跳过交互(用默认/已给参数)。`--wiki-root` 是 `--personal-root` 的兼容别名。

---

## 第 3 步:黄金验收(命令行,不依赖先把 AI 跑起来)

```bash
WIKI_ROOT=~/AI/wiki python3 ~/AI/wiki-manage/plugins/flux-wiki/tools/bin/wiki-cli protocol
```
看到 **「连接来源 … ✅」** + **「协议版本: … OK ✅」** = 工具与库都就绪。

再加分项(对话式探针):新开 AI 会话问「**团队 wiki 有哪些 domain?**」答得出 = 规则指针已加载。让 AI 跑 `wiki-cli protocol`,确认 `warnings` 为空。

---

## 更新

```bash
git -C ~/AI/wiki-manage pull     # 更新工具(软链的 skill / wiki-cli 即时生效)
git -C ~/AI/team-wiki  pull      # 更新团队知识(= /wiki-sync)
~/AI/wiki-manage/install.sh      # 工具更新后重跑一次(Cursor 重新粘 User Rules;其余幂等)
```
想钉到稳定版:`git -C ~/AI/wiki-manage checkout <tag>`;回滚:`git checkout <commit>`。

## 卸载(可逆)

```bash
rm ~/.claude/skills/wiki-ingest ~/.claude/skills/wiki-query ~/.claude/skills/wiki-lint
rm ~/.claude/commands/wiki-*.md   # wiki-sync.md / wiki-sync-team.md / wiki-help.md
# 删除 ~/.claude/CLAUDE.md 中以 "# === flux-wiki (auto by wiki-init) ===" 起的那一段
# Codex:删 ~/.codex/AGENTS.md 中同样标记的那段
# Cursor:在 设置→Rules→User Rules 删掉粘贴的那段;项目级则删该项目 .cursor/rules/wiki.mdc
```

---

## 三平台机制(install.sh 各做什么)

| 平台 | install.sh 怎么配 | 范围 | 组件 |
|---|---|---|---|
| **Claude Code** | 写 `~/.claude/CLAUDE.md` 指针 + 软链 skills/命令 | 用户级全局 | skills + slash 命令 |
| **Codex** | 写 `~/.codex/AGENTS.md` 指针 | 用户级全局 | 规则指针(Codex 不支持 slash command) |
| **Cursor** | 打印 User Rules 文本粘一次 / 或项目级 `.cursor/rules` | 全局(粘一次)/ 项目级 | rules(.mdc) |

**跨平台一致的内核** = `wiki-cli` + 库本地 .md,三家结果一致:AI 直接读本地 .md 查知识,用确定性的 CLI 做协议/检索/校验。

> 实测边界(诚实):本机仅 Claude Code 端到端验证过(wiki-init 落地、selftest 通过);Codex / Cursor 的真机交互需在装有对应工具的机器上确认。

## Windows 支持

- **一键安装走 `install.cmd`**(不要用 `./install.sh` —— 那是 bash,Windows 原生 cmd/PowerShell 跑不了)。`install.cmd` 自动找 `py`/`python`、交互问两个库、自动探测三平台,等价于 mac/Linux 的 `./install.sh`。
- **Python**:装 Python 3.8+(python.org 勾选 *Add to PATH*,或 Microsoft Store 版)。命令行用 `py` 或 `python` 均可;`install.cmd` 与 `wiki-init` 内部都用当前解释器绝对路径,不依赖 `python3` 这个名字。
- **符号链接**:装 Claude skill/命令时优先软链;Windows 非管理员 / 未开**开发者模式**会自动回退为**复制**(代价:`git pull` 后需重跑 `install.cmd` 才更新)。开了开发者模式则软链即时生效。
- **库路径**:`install.cmd D:\AI\wiki D:\AI\team-wiki` 按顺序传两个库(个人库在前);或 `set PERSONAL_ROOT=... & set TEAM_ROOT=... & install.cmd`。
- **Cursor**:与 mac 一致 —— `install.cmd` 打印 User Rules 文本,粘进 设置→Rules→User Rules 一次。
- 路径分隔符、`~`、`%LOCALAPPDATA%` 等已在工具内用 `os.path` / `expanduser` / `expandvars` 处理,Windows 正反斜杠混用均可。
