---
name: wiki-query
description: 从团队 LLM Wiki 查询知识并按需沉淀可复用答案。当用户问及团队/项目知识、模块、客户、概念、踩坑,或命中 _routes.md 关键词时使用。先走路由表精确加载,再检索综合,引用页面路径。
allowed-tools: Read, Grep, Glob, Bash(python3:*)
---

# wiki-query:检索 + 综合 + 沉淀

> 调用约定:下文 `wiki-cli` 均指 `python3 "${CLAUDE_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-${PLUGIN_ROOT}}}/tools/bin/wiki-cli"`(插件根变量:CC/Codex=CLAUDE_PLUGIN_ROOT,Cursor=CURSOR_PLUGIN_ROOT);命令正文沿用 wiki-cli 简写。

> 只读为主。规则真源是团队仓 `AGENTS.md` + `_routes.md` + `_vocabulary.md`。检索用 `wiki-cli` 子命令,也可直接 Grep/Read 库里的 `.md` 文件查知识。

## 第 0 步:新鲜度自检

跑 `wiki-cli protocol`。若本地落后 origin → 先提示 `/wiki-sync`,否则可能基于旧库回答(尤其 Codex/Cursor 各自本地副本)。

## 第 1 步:路由优先

跑 `wiki-cli route <kw>`(传关键词):
- 命中 → 按"必加载"列用 `wiki-cli get`(或直接 Read 对应路径)读取;对话深入再读"可选加载"列。
- optional 列是相对该路由 required 文件所在目录的文件名,get 前需拼成 `<required 所在目录>/<optional 名>`。
- 报告"路由歧义"时,提示用户精确化或运行 lint。
- 未命中 → 第 2 步。

## 第 2 步:检索

跑 `wiki-cli search`(传查询词),或直接 Grep 库目录。结果按相关度排序,**注意结果里的 staleness 提示**。读最相关页(`wiki-cli get` 或直接 Read 路径)。

## 第 3 步:综合作答

- 优先 domain-local 页;仅当有明确引用或跨域复用才纳入 global 页。
- 区分事实 / 解读 / 未决问题 / 矛盾;**引用页面路径**(可点击)。
- 命中 `sensitivity=maintainer-only` 的页:若当前用户非维护者,提示其敏感性,不照搬细节。

## 第 4 步:沉淀(如答案有持久价值)

好的提问通常应留下可复用 artifact。若答案有持久价值且你是维护者:
- 走 `wiki-ingest` skill 把答案存到 `wiki/domains/<domain>/queries/`(或跨域 `wiki/queries/`)。
- 非维护者:建议把答案作为 staging 候选 PR 提给 owner。
