# 手册:查知识(query)

个人库 = `{{WIKI_ROOT}}`;`wiki-cli` = `{{WIKI_CLI}}`。只读为主。

已登记团队仓:
{{TEAM_LIST}}

## 流程

1. **路由优先**(若 `{{WIKI_ROOT}}/_routes.md` 有内容):关键词命中路由表 → 直接 Read 对应文件,最准。
2. **检索**:`wiki-cli search "<词>"`,或直接 Grep `{{WIKI_ROOT}}`。读最相关的页。
   - 需要**团队原文**(个人库没学过/想看团队最新口径)→ 直接 **Grep/Read 团队仓**(只读)。仅当团队仓根目录恰有 AGENTS.md 等 wiki 标记时,`wiki-cli --root "<团队仓>" search` 才可用;真实团队仓往往不是 wiki 布局,Grep 是默认手段。**绝不要因为报"不是有效 wiki 根"就对团队仓跑 init——团队仓只读。**
3. **综合作答**:区分事实 / 解读 / 未决问题;**引用页面路径**(可点击)。
   - 从团队仓学来的页带 `learned_from` 溯源,需要更深背景时可顺藤读团队仓原页。
   - 库里查不到且配了团队仓 → 可顺带提示:学一轮团队增量(`wiki-cli guide learn`)可同步最新知识。
4. **沉淀**(答案有持久价值时):征得用户同意后,把结论存进 `domains/<主题>/queries/<slug>.md`,并在 `log.md` 记一行(走 ingest 手册流程)。
