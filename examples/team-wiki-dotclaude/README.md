# team-wiki/.claude/ 模板

把本目录的两个文件放到**团队内容仓**根的 `.claude/` 下(即 `team-wiki/.claude/settings.json` 与 `team-wiki/.claude/CLAUDE.md`)。

## settings.json
让团队成员的 Claude Code 在信任本仓后,自动认识 marketplace 并启用 `wiki-governance` 插件。

- 把 `REPLACE_ORG/wiki-manage` 改成 wiki-manage 工具仓的实际 GitHub 仓(`owner/repo`)。
- 非 GitHub(GitLab/自建)按 Claude Code 当前版本的 `extraKnownMarketplaces` source 语法调整(`source` 可为 `github` / `git` / 本地路径)。
- ⚠ 成员首次进仓需接受 workspace trust 对话框,才会被提示安装插件。
- ⚠ 该字段 schema 随 CC 版本演进,落地前在团队实际 CC 版本上验证一次(spec §10)。

## CLAUDE.md
只做"先读 AGENTS.md/_vocabulary.md"的指针,不复制协议正文(防 CLAUDE.md↔plugin 漂移)。
