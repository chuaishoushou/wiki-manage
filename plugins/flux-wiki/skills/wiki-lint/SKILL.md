---
name: wiki-lint
description: 给个人知识库做体检/清理。当用户说"检查 wiki/体检/清理/lint/知识库有没有问题"时使用。跑确定性检查出结构化报告,修复需用户确认。
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(python3:*), Write
---

# wiki-lint:体检

> 约定:`wiki-cli` = `python3 "{{WIKI_CLI}}"`;个人库 = `{{WIKI_ROOT}}`。
> 检查是确定性的(同一库任何机器同结果);AI 负责判读 + 给修复建议;**动手修复前需用户确认**。

## 流程

1. 跑 `wiki-cli lint --out "{{WIKI_ROOT}}/.wiki/reports/<YYYY-MM-DD>-lint.md"`。检查覆盖:
   - ❌ error:`_routes.md` 指向不存在的文件(会让 AI 加载失败,唯一的硬伤级)
   - ⚠️ warn:死链 / 跨主题同名重复页 / 路由关键词歧义 / 学习页溯源残缺(有 learned_from 缺 learned_commit)/ v2 旧布局提示
   - 用户自建目录、自由组织、无 frontmatter 的页 **不算问题**(这是设计,不要"修复"它们)
2. 判读报告:逐条说明影响与建议(修 / 忽略)。
3. **用户确认后**再动手修;涉及删页一律 `mv` 到 `archive/<YYYY-MM-DD>/`,绝不 `rm`。
4. 收尾:`log.md` 追加一行 lint 记录;报告文件已在 `.wiki/reports/`,告知用户路径。
