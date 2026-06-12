# 安装 / 更新 / 卸载 / 排障

> 安装命令见 [README](../README.md)(人和 AI 同一条命令)。本文只放安装之外的运维信息。

## 安装产物(全部记录在 `~/.flux-wiki.json` 的 `installed_files` 清单里)

| 位置 | 内容 | 类型 |
|---|---|---|
| `<个人库>`(默认 `~/AI/wiki`) | 知识库骨架(幂等初始化,绝不覆盖已有页) | 数据,卸载不动 |
| `~/.flux-wiki.json` | 机器级配置 v2:personal_root / teams 多仓列表 / wiki_manage / 安装清单 | 配置 |
| `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md` | flux-wiki 静态指针块(begin/end 标记,**零路径**,重装整段替换) | block |
| `~/.claude/skills/wiki-*`、`~/.agents/skills/wiki-*` | skill **symlink** 指向本仓(Windows 无权限时降级 copy) | link |
| `~/.claude/commands/wiki-*.md` | 斜杠命令 symlink | link |
| `~/.local/bin/wiki-cli` | shim(2 行,指向本仓 CLI) | file |
| `~/.claude/settings.json` | SessionStart hook:`wiki-cli doctor --quick`(全绿零输出;仅当 `~/.claude` 存在且非 Windows 才装;`--no-hook` 跳过) | hook |

**本仓(wiki-manage)即运行时**:装完不要删、不要移动;移动了就在新位置重跑 `./install.sh`(`doctor` 会在所有链接断掉时第一时间报警)。

## 更新

```bash
git -C ~/AI/wiki-manage pull
```
完——skill/命令是 symlink、手册由 `wiki-cli guide` 现读现发、指针块零路径,全部即时生效。只有指针块**正文措辞**改版或新增部署物时才需要重跑 `./install.sh`(幂等)。

## 多团队仓 / 路径变更(不用重装)

```bash
wiki-cli config team global --path <团队仓路径> --branch dev --exclude "knowledge/database/**,openspec/changes/archive/**"
wiki-cli config team tm03 --path <tm03仓路径>          # 再加一个仓
wiki-cli config team tm03 --remove                     # 移除
wiki-cli config set personal_root <新位置>              # 个人库挪家
wiki-cli doctor                                        # 改完体检一遍
```

## 验收(装完跑一条)

```bash
wiki-cli doctor
```
预期 exit 0:配置路径全活、团队仓分支/水位正常、部署物在场。安装器自身也会跑同样的自验证,任一不过退出非 0,不会假成功。

## 卸载

```bash
cd ~/AI/wiki-manage && ./install.sh --uninstall
```
按安装清单精确移除:指针块、skill/命令链接、shim、hook、配置。**个人库与团队仓(你的数据)不动**;本仓自行决定去留。安装/卸载时被备份让位的旧文件在 `~/.flux-wiki-backups/<时间戳>/` 里(整文件备份在原文件旁,形如 `*.bak-flux-*`),确认无用后自行删除。

## 旧版(无清单)产物手动清理

v4 之前的安装没有 `installed_files` 清单。最省事的路:**先重跑 `./install.sh`**(自动迁移旧产物并生成清单),之后再 `--uninstall`。坚持手动清理时,v3 时代的落点是:

```bash
rm -rf ~/.claude/skills/wiki-ingest ~/.claude/skills/wiki-query ~/.claude/skills/wiki-lint   # 渲染副本目录
rm -f  ~/.claude/commands/wiki-help.md ~/.claude/commands/wiki-learn.md
rm -f  ~/.flux-wiki.json
# ~/.claude/CLAUDE.md 与 ~/.codex/AGENTS.md:删除 "flux-wiki begin" 到 "flux-wiki end" 整段
# Cursor:设置 → Rules → User Rules 删除曾手动粘贴的段落
```

## v2 → v3 迁移(库布局,老用户可选)

v2 旧库(根下嵌套 `wiki/` 内容层)**可永久继续使用**(工具自动识别;拍板保留就建空文件 `.wiki/ack-legacy-layout` 静默提示)。要迁到 v3 扁平结构:

```bash
cd <旧库>
mv wiki/domains domains && mv wiki/staging inbox 2>/dev/null
mkdir -p archive/migrate-v3 && mv wiki _vocabulary.md archive/migrate-v3/ 2>/dev/null
wiki-cli init .       # 补齐 v3 骨架(幂等,不覆盖已有)
wiki-cli lint         # 迁完体检确认
```

## v3 → v4 变化(老用户)

- 渲染复制的 skill/命令副本 → symlink(重装时旧副本自动挪进 `~/.flux-wiki-backups/<时间戳>/`,不删除;备份刻意放在 AI 工具扫描路径之外,避免被当作幽灵 skill 扫出来)。
- 指针块从"烤死绝对路径"→ 静态零路径;路径漂移由 `doctor` 巡检 + `config` 修复,不再靠重装。
- 配置 `team_root`(单仓)→ `teams` 列表(多仓,带 branch/exclude);重跑安装自动迁移。
- Cursor 手动粘贴 User Rules 步骤移除(2.4+ 原生读 `~/.agents/skills`);曾粘过的旧规则文本请自行去设置里删一次。
- `learn --mark` 新增核销门禁(`--verify` / `--force`);learn/lint 成功路径自动落 `revisions/` 审计。

## 排障

| 现象 | 原因 / 处理 |
|---|---|
| 任何"路径不存在/失效" | 先跑 `wiki-cli doctor`——每条问题都附具体修复命令(通常 `wiki-cli config ...` 改一行) |
| `wiki-cli` 命令不存在 | shim 没进 PATH:用 `python3 <wiki-manage>/plugins/flux-wiki/tools/bin/wiki-cli`,或把 `~/.local/bin` 加进 PATH |
| `learn --mark` 被拒 | 核销门禁:输出里列了未核销页——补学(带 learned_from/learned_commit),或确认放弃后 `--force` |
| 水位孤儿化(团队仓被 reset) | learn 自动降级全量列+已学跳过;按输出提示 `git branch rescue/...` 钉住旧水位防 gc |
| 团队仓拉到空内容 | 检出分支不对(如 master 近空):`wiki-cli config team <名> --branch <工作分支>` 后按 doctor 提示 switch |
| 安装/doctor 退出码非 0 | 输出里有 ❌ 清单,按条目处理后重跑 |
| skill 是普通目录不是链接(Windows) | symlink 降级 copy 属正常;更新需重跑 `./install.sh` |
