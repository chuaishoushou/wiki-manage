---
name: wiki-query
description: 从团队 LLM Wiki 查询知识并按需沉淀可复用答案。当用户问及团队/项目知识、模块、客户、概念、踩坑,或命中 _routes.md 关键词时使用。先走路由表精确加载,再检索综合,引用页面路径。
allowed-tools: Read, Grep, Glob
---

# wiki-query:检索 + 综合 + 沉淀

> 只读为主。规则真源是团队仓 `AGENTS.md` + `_routes.md` + `_vocabulary.md`。MCP 工具完整名形如 `mcp__wiki__wiki_*`;无 MCP 时回退 Grep/Read。

## 第 0 步:新鲜度自检

调 `wiki_get_protocol`。若本地落后 origin → 先提示 `/wiki-sync`,否则可能基于旧库回答(尤其 Codex/Cursor 各自本地副本)。

## 第 1 步:路由优先

调 `wiki_resolve_route`(传关键词,CLI: `wiki-cli route <kw>`):
- 命中 → 按"必加载"列 `wiki_get_page` 读取;对话深入再读"可选加载"列。
- 报告"路由歧义"时,提示用户精确化或运行 lint。
- 未命中 → 第 2 步。

## 第 2 步:检索

调 `wiki_search`(传查询词)。结果按相关度排序,**注意结果里的 staleness 提示**。读最相关页(`wiki_get_page`)。

## 第 3 步:综合作答

- 优先 domain-local 页;仅当有明确引用或跨域复用才纳入 global 页。
- 区分事实 / 解读 / 未决问题 / 矛盾;**引用页面路径**(可点击)。
- 命中 `sensitivity=maintainer-only` 的页:若当前用户非维护者,提示其敏感性,不照搬细节。

## 第 4 步:沉淀(如答案有持久价值)

好的提问通常应留下可复用 artifact。若答案有持久价值且你是维护者:
- 走 `wiki-ingest` skill 把答案存到 `wiki/domains/<domain>/queries/`(或跨域 `wiki/queries/`)。
- 非维护者:建议把答案作为 staging 候选 PR 提给 owner。
