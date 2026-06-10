---
name: wiki-ingest
description: 把知识记进个人知识库。当用户要"记一下/入库/沉淀/收录"知识、给出外部资料(docx/pdf/md/链接)、或说"这次踩坑记到 wiki"时使用。定主题落 domains/,拿不准放 inbox/,写完记台账。
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python3:*)
---

# wiki-ingest:记知识进个人库

> 约定:`wiki-cli` = `python3 "{{WIKI_CLI}}"`;个人库 = `{{WIKI_ROOT}}`。
> 规则真源是 `{{WIKI_ROOT}}/AGENTS.md`,有分歧以它为准。

## 流程(轻量,通常 4 步)

1. **找落点**:看 `{{WIKI_ROOT}}/domains/` 现有主题(目录即主题),判断归属。
   - 命中已有主题 → 落 `domains/<主题>/`(主题内子目录自由;常用 concepts/ queries/ sources/ modules/)。
   - 是新主题 → **直接建目录**,不需要登记审批;顺手在 `overview.md` 加一行导航。
   - 拿不准 → 放 `inbox/`,留给用户日后定。
2. **先查重**:`wiki-cli search "<关键词>"`(或 Grep)。已有相关页 → **优先更新整合**,不新建重复页。
3. **写盘**:直接 Write,或 `wiki-cli new <type> <slug> --domain <主题>` 生成骨架再填正文。
   - 文件名小写 kebab-case;frontmatter 推荐带 `tags / status / date_created`(非强制)。
   - 外部资料:原件存 `raw/`(只读区,之后不改),消化后的摘要/要点写进 domains/。
4. **记台账**:`{{WIKI_ROOT}}/log.md` 追加一行:`## [YYYY-MM-DD] ingest | <标题>` + 涉及页面路径。
   重要页可在 `_routes.md` 登记一个触发关键词(可选,登记后 AI 检索更准)。

## 红线

- `raw/` 只进不改;**删除任何页 = mv 到 `archive/<YYYY-MM-DD>/`,绝不 `rm`**。
- 写完如改动较多,可 `wiki-cli lint` 自检一遍(只报告,无侵入)。
