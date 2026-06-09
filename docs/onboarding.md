# 团队成员 onboarding

> 按角色分轨。**大多数人是只读成员,先看第一节就够。**
> **最快(所有人)**:`git clone …/wiki-manage && cd wiki-manage && ./install.sh`(Windows `install.cmd`)—— 交互配好**个人库 + 团队仓**两个位置,三平台自动落地。详见 [README](../README.md) / [INSTALL](INSTALL.md)。
> ⚠️ 本仓**不是原生插件**:别用 `/plugin`、`codex plugin install`、Cursor 扩展市场 —— 唯一入口是 git + `install.sh`。

---

## A. 只读成员最短路径(15 人里的多数)

你只想偶尔查知识,不写库。前置:`python3` ≥3.8、`git`。

```bash
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
cd ~/AI/wiki-manage
./install.sh         # Windows: install.cmd
```

交互会问两个目录(回车用默认):个人库(默认 `~/AI/wiki`,自动建)、团队仓(默认 `~/AI/team-wiki`)。只读成员主要查团队仓,把它 clone 下来即可:

```bash
git clone https://github.com/chuaishoushou/team-wiki.git ~/AI/team-wiki
```

装完**重启** AI 客户端(Claude Code / Codex);**Cursor** 把打印的「User Rules」粘进 设置 → Rules → User Rules。

**验收**:新开会话问 AI「**团队 wiki 有哪些 domain?**」——答得出 = 成了。

---

## B. 维护者 / 从零建库

### B-1. 全新团队,还没有 wiki
```bash
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
python3 ~/AI/wiki-manage/plugins/flux-wiki/tools/bin/wiki-cli \
    init ~/AI/team-wiki --domains backend,frontend,ops --owner 你的名字
```
一条命令建出合规空库(目录骨架 + AGENTS.md + _vocabulary.md + _routes.md + overview.md),并自检 lint=0。然后编辑 `_vocabulary.md` 填 domain 边界,用 `/wiki-ingest` 收录第一篇。详见 [migration-runbook](migration-runbook.md)。

### B-2. 从已有个人库迁团队
见 [migration-runbook](migration-runbook.md)(含安全审计 / 脱敏 / publish 流程)。

---

## C. 只装单个平台(直接调 wiki-init)

`./install.sh` 已三平台全配。只想配某一个、或在 CI 里非交互时,直接调 `bin/wiki-init` 并显式给两个库:

```bash
# Claude Code(写 ~/.claude/CLAUDE.md 指针 + 软链 skills/命令)
python3 ~/AI/wiki-manage/bin/wiki-init --platform cc \
    --personal-root ~/AI/wiki --team-root ~/AI/team-wiki --write

# Codex(写 ~/.codex/AGENTS.md 指针)
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex \
    --personal-root ~/AI/wiki --team-root ~/AI/team-wiki --write

# Cursor(打印 User Rules,粘进 设置→Rules→User Rules;不落文件)
python3 ~/AI/wiki-manage/bin/wiki-init --platform cursor \
    --personal-root ~/AI/wiki --team-root ~/AI/team-wiki
```
去掉 `--write` 只打印不落地;`--no-input` 跳过交互;`--cursor-project <项目根> --write` 写项目级 `.cursor/rules/wiki.mdc`。详见 [INSTALL.md](INSTALL.md)。

---

## 通用验收清单(任何平台)

- [ ] `WIKI_ROOT=~/AI/wiki python3 …/wiki-cli protocol` 显示「连接来源 … ✅」+「协议版本: … OK ✅」
- [ ] AI 能跑 `wiki-cli protocol` 且 `warnings` 为空
- [ ] AI 能 `wiki-cli search`(或直接 Grep 库 .md)检索到一条已知内容
- [ ] 探针:问 AI「团队 wiki 有哪些 domain?」答得出 = 规则指针已加载

## 常见卡点
| 现象 | 原因 / 解法 |
|---|---|
| `[wiki] 未连接` | 库路径不存在,或 `WIKI_ROOT` 指向的不是 wiki 根(缺 AGENTS.md 等) |
| protocol 的 `root_source` 非预期 | 没设 `WIKI_ROOT` 且约定路径缺失;重跑 `install.sh` 配好,或 `export WIKI_ROOT` |
| GUI/Desktop 启动连不上,终端能连 | GUI 不继承 shell 的 `export`;把库放约定路径 `~/AI/wiki`、`~/AI/team-wiki` 即可兜底 |
| Windows `python3` 找不到 | 装 Microsoft Store 版 Python(带 python3 别名),或用 `py` / `python` |

## 我想贡献新知识(只读成员)
你不能直接写中心仓。把资料提 **PR 到 `staging/`** 或开 issue,由该 domain owner 审核晋升。被拒会归档到 `archive/rejected-*/` 并写明原因。
