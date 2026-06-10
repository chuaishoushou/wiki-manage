# wiki-manage

轻量个人知识库插件:本地 markdown 知识库 + AI 工具集成(Claude Code / Codex / Cursor)+ 从团队 git 知识仓增量学习。纯 Python 标准库,零依赖。

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

- 终端里跑会逐项确认两个路径(回车用默认):**个人库**(默认 `~/AI/wiki`)和**团队仓**(可跳过,之后重跑补上)。
- AI / CI(非终端)直接用默认或参数,不会卡在交互上:
  `./install.sh --personal-root ~/AI/wiki --team-root ~/AI/team-wiki`
- 安装做的事:初始化个人库(幂等,绝不覆盖已有页)→ 写配置 `~/.flux-wiki.json` → 给探测到的 AI 工具写规则指针(**重装整段替换**,真幂等)→ Claude Code 侧复制 skills/命令 → **自验证**(任何部署物有问题退出非 0)。
- Cursor 收尾:把输出里两条分隔线之间的文本粘进 设置 → Rules → User Rules(唯一手动步骤,Cursor 不允许脚本写全局规则)。
- **本仓即运行时,装完不要删**。更新:`git -C ~/AI/wiki-manage pull && cd ~/AI/wiki-manage && ./install.sh`。

## 知识库结构(v3 扁平)

```
~/AI/wiki/
├── AGENTS.md        # 协议(AI 操作规则)
├── overview.md      # 顶层导航
├── log.md           # 操作台账
├── _routes.md       # 关键词路由(可选)
├── domains/<主题>/   # 知识主体 —— 新主题直接建目录,不受限制
├── inbox/           # 待整理
├── raw/             # 原始资料原件(只读)
├── archive/         # 归档(删除 = mv 进来,绝不 rm)
└── .wiki/           # 工具产物(lint 报告 / 学习水位)
```

## 能力

| 入口 | 类型 | 作用 |
|---|---|---|
| wiki-query / wiki-ingest / wiki-lint | skill(说话触发) | 查知识 / 记知识 / 体检 |
| `/wiki-learn` | 斜杠命令 | **学团队知识**:按 git 提交水位拿增量 → AI 逐页分类进个人库(带 `learned_from`/`learned_commit` 溯源)→ 记水位 |
| `/wiki-help` | 斜杠命令 | 能力清单 |

`wiki-cli`(底层,6 个子命令):`init` 建库/修结构(幂等) · `new` 加页骨架 · `search` 检索 · `lint` 体检(error 只留"路由指向不存在文件",自建目录/无 frontmatter 不算问题) · `learn` 团队增量/水位 · `status` 状态。

```bash
# 30 秒体验
python3 plugins/flux-wiki/tools/bin/wiki-cli init /tmp/demo --domains backend
python3 plugins/flux-wiki/tools/bin/wiki-cli --root /tmp/demo status

# 一键自测(全部在临时目录 + 隔离 HOME,不碰真实配置)
python3 plugins/flux-wiki/tools/selftest.py
```

Codex 没有斜杠命令:指针里已写等价 CLI 流程(learn → 分类 → mark),正常对话可用。

## v2 → v3 迁移(老用户)

v2 旧库(根下嵌套 `wiki/` 内容层)**仍可继续使用**(工具自动识别);要迁到扁平结构:

```bash
cd <旧库>
mv wiki/domains domains && mv wiki/staging inbox 2>/dev/null
mkdir -p archive/migrate-v3 && mv wiki _vocabulary.md archive/migrate-v3/ 2>/dev/null
python3 <wiki-manage>/plugins/flux-wiki/tools/bin/wiki-cli init .   # 补齐 v3 骨架
```
(global/ 模板等残留都进 `archive/migrate-v3/`;迁完跑 `wiki-cli lint` 确认。)

## 文档

- [docs/INSTALL.md](docs/INSTALL.md) — 更新 / 卸载 / 单平台安装 / 排障
- MIT License — [LICENSE](LICENSE)
