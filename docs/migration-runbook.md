# 维护者迁移 runbook(从个人单库 → 团队仓)

> **全新团队没有要迁移的库** → 不用看本文,直接 `wiki-cli init <目录>` 建合规空库(见 [onboarding](onboarding.md) B-1),跳到下面第 7 步即可。
> 本文针对**已有个人/单人库要迁成团队仓**的场景,给 1-2 名维护者执行。
> 每步独立可验收。**当前阶段(本次)暂不脱敏、暂不 push** —— 标 ⏸ 的步骤先跳过,工具与协议已就绪,随时可执行。

## 现状(已核实)
- `~/AI/wiki`:无 `.git`,57 active 页 + 44 archive 页,含敏感内容。
- `~/AI/wiki-manage`:已是 git 仓,工具/插件已实现(本仓)。
- 协议已升级:`AGENTS.md` protocol_version=2、`_vocabulary.md` 已建。

## 步骤

### 1. 工具自测(随时可做,无副作用)
```bash
python3 ~/AI/wiki-manage/plugins/flux-wiki/tools/selftest.py   # 期望全部通过(末行 ✅ 全部通过)
```

### 2. 体检现库(只读)
```bash
export WIKI_ROOT=~/AI/wiki
CLI=~/AI/wiki-manage/plugins/flux-wiki/tools/bin/wiki-cli
python3 $CLI lint --out ~/AI/wiki-manage/docs/lint-baseline-$(date +%F).md
```
当前基线:235 error / 202 warn(绝大多数是存量页缺 `page_type`/`sensitivity`)。

### 3. 回填存量 frontmatter(把基线拉到清洁)
- 用 `/wiki-lint` 让 AI 按报告逐页补 `page_type`(从目录推断)、`sensitivity`、缺失必填字段。
- 归并 77 个乱 tag 到 `_vocabulary.md` 白名单。
- ⚠ 修改需 owner 确认;改完重跑 lint 直到 error→0。

### 4. ⏸ 安全审计 + 脱敏(本次暂跳过,按用户指示)
```bash
python3 $CLI scan --out ~/AI/wiki-manage/docs/security-audit-$(date +%F).md   # 只读,可随时跑
```
- 跑一次看当前高风险页数(`scan` 默认含 archive)。真正要建团队仓前,逐条裁定 `sensitivity`(客户真名/凭证/攻击面 → maintainer-only 或 exclude)。
- 本阶段用户明确**暂不脱敏**,故 ⏸。

### 5. ⏸ 内容仓 git 化(本次暂不 push)
```bash
# .gitignore 先定稿(避免敏感/大文件进历史)
printf '%s\n' '.obsidian/' '.idea/' '.claude/' '__pycache__/' '*.pyc' raw/ > ~/AI/wiki/.gitignore
git -C ~/AI/wiki init
# ⚠ 脱敏完成前不要 add 全部;不要 push。commit 0 应是脱敏后的干净快照。
```
本阶段用户明确**暂不 git init/push**,故 ⏸。

### 6. ⏸ 团队仓发布(脱敏后)
```bash
python3 $CLI publish --out /path/to/team-wiki-export    # 只导 sensitivity<=team,排除 personal/maintainer-only
# 有风险页会被阻断,需先在第 4 步裁定 sensitivity
```

### 7. 协议从个人 CLAUDE.md 抽离(可现在做)
- 把 `~/.claude/CLAUDE.md` 里 wiki 协议正文(入场加载/写入纪律/路径速查)抽进团队仓 `AGENTS.md`(已大部分就绪)。
- 个人 `~/.claude/CLAUDE.md` 只留指针 + 个人专属(FLUX 路径/偏好);用户级指针跨工作区生效。
- 团队仓内放 `.claude/CLAUDE.md` 指针(模板见 `examples/team-wiki-dotclaude/`)。

### 8. 维护者本机装写入闸(脱敏+git 化后)
```bash
# 把 adapters/git-hooks/pre-commit 的 {{WIKI_MANAGE}} 替换为本机路径后:
cp ~/AI/wiki-manage/adapters/git-hooks/pre-commit ~/AI/wiki/.git/hooks/pre-commit
chmod +x ~/AI/wiki/.git/hooks/pre-commit
```
commit 时自动跑 `wiki-cli lint --staged`,frontmatter/敏感度不过不让提交。本地、不影响只读成员。

### 9. 团队装载
- CC 成员:`team-wiki/.claude/settings.json` 配 `extraKnownMarketplaces`+`enabledPlugins`(模板见 examples/),信任文件夹后被提示装。
- Codex/Cursor 成员:`bin/wiki-init --write` 生成配置。
- 见 [onboarding.md](onboarding.md)。

## 本次(用户指示)实际执行范围
✅ 1 自测 · 2 体检 · (4 scan 只读可跑) · 7 协议抽离(可选) · 工具/文档全就绪
⏸ 4 脱敏 · 5 git init · 6 publish · 8 pre-commit(依赖 git) —— 待后续启动
