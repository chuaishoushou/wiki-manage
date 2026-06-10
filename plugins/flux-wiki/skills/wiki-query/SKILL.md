---
name: wiki-query
description: 从个人知识库查询知识并按需沉淀可复用答案。当用户问及项目知识、模块、概念、踩坑,或命中 _routes.md 关键词时使用。先走路由表精确加载,再全文检索综合,引用页面路径。
allowed-tools: Read, Grep, Glob, Bash(python3:*)
---

# wiki-query:检索 + 综合 + 沉淀

> 约定:`wiki-cli` = `python3 "{{WIKI_CLI}}"`;个人库 = `{{WIKI_ROOT}}`。只读为主。

## 流程

1. **路由优先**(若 `{{WIKI_ROOT}}/_routes.md` 有内容):关键词命中路由表 → 直接 Read 对应文件,最准。
2. **检索**:`wiki-cli search "<词>"`,或直接 Grep `{{WIKI_ROOT}}`。读最相关的页。
3. **综合作答**:区分事实 / 解读 / 未决问题;**引用页面路径**(可点击)。
   - 从团队仓学来的页带 `learned_from` 溯源,需要更深背景时可顺藤读团队仓原页。
   - 库里查不到且配了团队仓 → 可顺带提示:`/wiki-learn` 可同步团队最新知识。
4. **沉淀**(答案有持久价值时):征得用户同意后,把结论存进 `domains/<主题>/queries/<slug>.md`,并在 `log.md` 记一行(走 wiki-ingest 流程)。
