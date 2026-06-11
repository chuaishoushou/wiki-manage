## 个人知识库(flux-wiki)

- **个人库**(日常读写,本地 markdown,直接 Read/Grep + 写文件):`{{WIKI_ROOT}}`
{{TEAM_LINE}}
- 工具:`wiki-cli` = `python3 "{{WIKI_CLI}}"`(纯标准库;下文沿用 `wiki-cli` 简写)

操作约定(详细规则以 `{{WIKI_ROOT}}/AGENTS.md` 为准):
- **查知识**:直接 Grep/Read 个人库下的 `.md`,或 `wiki-cli search "<词>"`。
- **记知识**:写入 `{{WIKI_CONTENT}}/domains/<主题>/`(新主题直接建目录,不受限制;拿不准放 `{{WIKI_CONTENT}}/inbox/`),并在 `{{WIKI_ROOT}}/log.md` 追加一行。
- **学团队知识**:斜杠命令 `/wiki-learn`;无斜杠命令的工具用 CLI 等价流程——`wiki-cli learn --pull` 看增量 → 逐页读原文分类写入 `{{WIKI_CONTENT}}/domains/`(页内带 `learned_from`/`learned_commit` 溯源)→ `wiki-cli learn --mark <commit>` 记水位。
- **体检**:`wiki-cli lint`(只报告;修复需用户确认)。
- **删除 = 归档**:`mv` 到 `archive/<YYYY-MM-DD>/`,绝不 `rm`。
