# 安装 / 更新 / 卸载 / 排障

> 安装命令见 [README](../README.md)(人和 AI 同一条命令)。本文只放安装之外的运维信息。

## 安装产物(共 4 处)

| 位置 | 内容 |
|---|---|
| `<个人库>`(默认 `~/AI/wiki`) | v3 知识库骨架(幂等初始化,绝不覆盖已有页) |
| `~/.flux-wiki.json` | 机器级配置:personal_root / team_root / wiki-manage 位置 |
| AI 工具规则文件 | `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md` 里的 flux-wiki 标记块(begin/end 之间,重装整段替换);Cursor 为手动粘贴的 User Rules |
| `~/.claude/skills/wiki-*`、`~/.claude/commands/wiki-*.md` | 渲染后的 skill / 斜杠命令副本(仅 Claude Code) |

**本仓(wiki-manage)即运行时**:规则文件里的 `wiki-cli` 指向本仓内的脚本,装完不要删、不要移动;移动了就在新位置重跑 `./install.sh`。

## 更新

```bash
git -C ~/AI/wiki-manage pull
cd ~/AI/wiki-manage && ./install.sh
```
幂等:指针块整段替换、skill 副本覆盖、个人库只补缺失。旧版(2026-06 前)装的指针块/软链 skill 会被自动迁移并备份(`CLAUDE.md.bak-flux-*`)。

## 单平台 / 指定路径

```bash
./install.sh --platform cc --personal-root ~/AI/wiki --team-root ~/AI/team-wiki
./install.sh --platform cursor --cursor-project <项目根>   # Cursor 写项目级规则(默认打印全局 User Rules)
./install.sh --dry-run                                     # 只预览,不写任何文件
```
个人库与团队仓位置**强制必填,缺一不可**(来源:参数 / 已有配置 / 终端作答);非终端缺任一项报错退出 rc=2,不会静默用默认路径安装。
Windows 把 `./install.sh` 换成 `.\install.cmd`,其余参数相同。

## 验收(装完跑一条)

```bash
python3 ~/AI/wiki-manage/plugins/flux-wiki/tools/bin/wiki-cli status
```
预期:显示个人库路径(来源: 配置)、布局 v3 扁平、团队仓状态。安装器本身也会自验证(部署物有问题时退出码非 0,不会假成功)。

## 卸载

```bash
rm -rf ~/.claude/skills/wiki-ingest ~/.claude/skills/wiki-query ~/.claude/skills/wiki-lint
rm -f  ~/.claude/commands/wiki-help.md ~/.claude/commands/wiki-learn.md
rm -f  ~/.flux-wiki.json
# ~/.claude/CLAUDE.md 与 ~/.codex/AGENTS.md:删除 "flux-wiki begin" 到 "flux-wiki end" 整段
# Cursor:设置 → Rules → User Rules 删除粘贴的段落
# 知识库本身(~/AI/wiki)是你的数据,自行决定去留
rm -rf ~/AI/wiki-manage
```

## 排障

| 现象 | 原因 / 处理 |
|---|---|
| `wiki-cli` 报"找不到 wiki 根" | 没装或配置丢失:重跑 `./install.sh`;或临时 `--root <库路径>` |
| 指针指向的路径不存在 | 移动过库/本仓:重跑 `./install.sh`(指针整段替换,自动修正) |
| `/wiki-learn` 报"未配置团队仓" | 重跑 `./install.sh --team-root <团队仓路径>`,或本次 `wiki-cli learn --team <路径>` |
| `learn --pull` 失败 | 团队仓本地有偏离(只读 clone 不应改动):`git -C <团队仓> status` 人工处理;pull 用 `--ff-only` 不会乱合并 |
| 旧版残留(skill 是软链 / 指针含 `{{` 占位符 / `~/.flux-wiki/` 目录) | 重跑 `./install.sh` 自动清理迁移;`~/.flux-wiki/` 部署区已废弃,可直接删 |
| 安装退出码非 0 | 输出里有 ❌ 自验证清单,按条目处理后重跑 |
