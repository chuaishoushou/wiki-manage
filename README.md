# wiki-manage

轻量个人知识库管理:本地 markdown 知识库 + AI 工具接入(Claude Code / Codex / Cursor)+ 从团队 git 知识仓增量学习。纯 Python 标准库,零依赖。

**v4 核心思想:部署物零路径。** 平台侧只装"静态指针 + skill 链接"(装一次管终身);路径只活在 `~/.flux-wiki.json` 一处,AI 会话用 `wiki-cli context` 运行时解析。移动个人库/团队仓 = `wiki-cli config` 改一行,不用重装;`wiki-cli doctor` 把环境漂移当场炸出来。

## 安装(人和 AI 同一条命令)

macOS / Linux:
```bash
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
cd ~/AI/wiki-manage && ./install.sh
```
Windows(cmd / PowerShell,逐行):
```bat
git clone https://github.com/chuaishoushou/wiki-manage.git %USERPROFILE%\AI\wiki-manage
cd %USERPROFILE%\AI\wiki-manage
.\install.cmd
```

- 安装**强制要求提供两个路径**:**个人库**与**团队仓**(已存在的 git clone,可给多个 `--team-root`)。终端逐项必答;AI / CI(非终端)必须带全参数,缺任一项报错 rc=2,绝不静默用默认:
  `./install.sh --personal-root ~/AI/wiki --team-root <团队仓路径>`
- 重装 / 更新不必重复给参数:`~/.flux-wiki.json` 里上次的路径直接沿用。
- 安装做的事:初始化个人库(幂等,绝不覆盖已有页)→ 写静态指针块(`~/.claude/CLAUDE.md` / `~/.codex/AGENTS.md`,重装整段替换)→ skill/命令 **symlink** 进 `~/.claude/` 与 `~/.agents/skills/`(Codex 与 Cursor 2.4+ 原生读后者,**Cursor 不再需要手动粘贴**)→ `~/.local/bin/wiki-cli` shim → Claude Code SessionStart 巡检 hook(全绿零输出,`--no-hook` 跳过)→ 写配置 + 安装清单 → **自验证**(doctor 全绿才算装好)。
- **本仓即运行时,装完不要删**。更新只需 `git -C ~/AI/wiki-manage pull`——部署物是链接,自动生效,无需重装。

## 日常使用

对 AI 说话即可(三平台同一句话):**"记一下 X" / "查一下 Y" / "学一下团队知识" / "给知识库体检"**。AI 会话首次涉及知识库会先跑 `wiki-cli context` 拿路径,再 `wiki-cli guide <op>` 拿手册照做——手册在仓内 `plugins/flux-wiki/playbooks/`,一份源三平台同体验。

`wiki-cli`(10 个子命令,`~/.local/bin/wiki-cli` 即可调):

| 命令 | 作用 |
|---|---|
| `init` | 建库 / 修结构(幂等,绝不覆盖) |
| `new` | 加页骨架 |
| `search` | 全文检索 |
| `lint` | 内容体检(死链/路由/溯源/词表闭集;全库体检自动落 `revisions/` 审计) |
| `learn` | 团队增量(`--pull` 拉最新;`--verify` 核销;`--mark` 记水位,**有核销门禁**;`--all` 看被分流页) |
| `status` | 库状态 |
| `context` | 会话入口:库位置/团队仓/约定速查(运行时解析,取代烤死路径) |
| `doctor` | 环境巡检:死路径/孤儿水位/部署物缺失,error 退出非 0(`--quick` 供 hook,零打扰) |
| `guide` | 打印操作手册(learn/ingest/lint/query/help) |
| `config` | 配置读写;多团队仓:`config team <名> --path <路径> --branch <分支> --exclude <glob,glob>` |

### 团队增量学习闭环

```
wiki-cli learn --pull        # 增量清单(exclude 自动分流机械内容)
→ AI 逐页消化进 domains/(带 learned_from/learned_commit 溯源)
→ wiki-cli learn --verify    # 核销:确定性校验每页溯源已落库
→ wiki-cli learn --mark <HEAD>  # 门禁放行才能推水位;自动落 revisions/ 审计
```
核销门禁拦两类事故:AI 漏写溯源(下次会重复导入)、AI 静默跳页。首次学习是基线策展,只提示不阻塞;确认放弃的页用 `--force`(放弃清单进审计)。水位记 commit+日期+分支三元组;团队仓被 reset/rebase 时,水位失效自动降级为全量列+已学跳过,孤儿水位会附上钉枝防 gc 的命令(`git branch rescue/<水位> <水位>`)。

## 知识库结构(v3 扁平;v2 嵌套库自动兼容)

```
~/AI/wiki/
├── AGENTS.md        # 协议(AI 操作规则,真源)
├── overview.md      # 顶层导航
├── log.md           # 操作台账
├── _routes.md       # 关键词路由(可选)
├── _vocabulary.md   # 受控词表(可选;含 ```json 规则块时 lint 才做闭集校验)
├── domains/<主题>/   # 知识主体 —— 新主题直接建目录,不受限制
├── inbox/           # 待整理
├── raw/             # 原始资料原件(只读)
├── archive/         # 归档(删除 = mv 进来,绝不 rm)
└── .wiki/           # 工具产物(学习水位 / revisions 审计 / 报告)
```

## 30 秒体验 / 自测

```bash
python3 plugins/flux-wiki/tools/bin/wiki-cli init /tmp/demo --domains backend
python3 plugins/flux-wiki/tools/bin/wiki-cli --root /tmp/demo status

# 一键自测(100 项,全部在临时目录 + 隔离 HOME,不碰真实配置)
python3 plugins/flux-wiki/tools/selftest.py
```

## 平台矩阵

| 平台 | 得到 |
|---|---|
| Claude Code | 指针块 + skill/命令链接 + SessionStart 巡检 hook(环境漂移下个会话开头报警) |
| Codex | 指针块(`~/.codex/AGENTS.md`)+ `~/.agents/skills`(原生扫描,`$wiki-ingest` 可显式调用);说同样的话走同一份手册 |
| Cursor | 2.4+ 原生读 `~/.agents/skills`,零手动步骤(旧版手动粘贴流程已移除) |

不做 plugin 打包(三家 manifest 互不兼容且 Codex 侧 schema 仍在频繁变更)、不做 MCP(对本地 markdown 是过度设计)、不做 web(建造信号未出现)。

## 文档

- [docs/INSTALL.md](docs/INSTALL.md) — 更新 / 卸载 / 排障 / v3 → v4 变化
- MIT License — [LICENSE](LICENSE)
