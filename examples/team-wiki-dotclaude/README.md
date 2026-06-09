# team-wiki/.claude/ 模板

把本目录的 `CLAUDE.md` 放到**团队内容仓**根的 `.claude/` 下(即 `team-wiki/.claude/CLAUDE.md`)。

## CLAUDE.md
只做"先读 `AGENTS.md` / `_vocabulary.md`"的指针,不复制协议正文(防 CLAUDE.md ↔ 库漂移)。作用:团队成员在 `team-wiki` 目录里打开 Claude Code 时,AI 知道"这是团队 wiki、先去读协议真源",而不是凭空猜。

> 安装工具本身(skills / `wiki-cli` / 三平台规则指针)走仓库根的 `./install.sh`,**不依赖插件市场**。本模板只是给团队内容仓额外加一个 `.claude` 指针,与安装相互独立、可选。
