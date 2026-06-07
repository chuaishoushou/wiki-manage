"""wiki_core 单元 + 集成测试(纯标准库 unittest)。

运行:
  python3 -m unittest discover -s plugins/wiki-governance/tools/tests
或:
  python3 plugins/wiki-governance/tools/tests/test_wiki_core.py
"""
import os
import sys
import tempfile
import unittest

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(_SRC))

from wiki_core import frontmatter, routes, sensitivity, suggest, validate, lint, repo, publish, scaffold, changes  # noqa: E402
from wiki_core.vocabulary import Vocabulary, load as load_vocab  # noqa: E402


VOCAB_DATA = {
    "protocol_version": 2,
    "domains": [
        {"slug": "flux-tms", "boundary": "FLUX TMS 运输管理 客户 模块", "owners": ["alice"], "status": "active"},
        {"slug": "personal", "boundary": "个人偏好 工作流", "owners": ["self"], "status": "active", "publish": False},
    ],
    "page_types": ["source", "entity", "concept", "query", "module"],
    "sensitivity_levels": ["public", "team", "maintainer-only", "exclude"],
    "required_frontmatter": ["tags", "page_type", "domain", "shared_scope", "sensitivity", "status", "date_created"],
    "required_frontmatter_conditional": {"domain_reason": "low/medium 必填"},
    "enum_fields": {
        "page_type": ["source", "entity", "concept", "query", "module"],
        "shared_scope": ["domain", "global"],
        "sensitivity": ["public", "team", "maintainer-only", "exclude"],
        "status": ["active", "staged", "archived", "unresolved"],
        "domain_confidence": ["low", "medium", "high"],
    },
    "tag_whitelist": ["concept", "flux-tms", "timer"],
    "tag_synonyms": {"定时器": "timer"},
    "status_in_tags_forbidden": ["稳定"],
    "global_promotion": {"min_domains": 2},
    "sensitivity_rules": {
        "default_on_hit": "maintainer-only",
        "customer_names": ["客户甲", "acme-corp"],
        "secret_keywords": ["clientSecret", "密码"],
        "attack_surface_keywords": ["注入"],
    },
    "publish": {"max_sensitivity": "team"},
}


class TestFrontmatter(unittest.TestCase):
    def test_parse_basic(self):
        text = "---\ntags: [a, b]\ndomain: flux-tms\nstatus: active\n---\n# Title\nbody"
        meta, body, has = frontmatter.parse(text)
        self.assertTrue(has)
        self.assertEqual(meta["tags"], ["a", "b"])
        self.assertEqual(meta["domain"], "flux-tms")
        self.assertIn("# Title", body)

    def test_parse_block_list_and_empty(self):
        text = "---\nsource_paths: []\nowners:\n  - alice\n  - bob\n---\nx"
        meta, _, has = frontmatter.parse(text)
        self.assertTrue(has)
        self.assertEqual(meta["source_paths"], [])
        self.assertEqual(meta["owners"], ["alice", "bob"])

    def test_no_frontmatter(self):
        meta, body, has = frontmatter.parse("# just a title\ntext")
        self.assertFalse(has)
        self.assertEqual(meta, {})

    def test_extract_json_block_ignores_inline_mention(self):
        # 散文里内联提到的同名字样不应被当成围栏
        text = "前文提到 ```json 块只解析下面这个\n\n```json\n{\"k\": 1}\n```\n后文"
        block = frontmatter.extract_json_block(text)
        self.assertEqual(block, '{"k": 1}')


class TestRoutes(unittest.TestCase):
    def test_split_cells_respects_escaped_pipe(self):
        cells = routes._split_cells(r"| `A` \| `B` | `x.md` | `y.md` |")
        cells = [c for c in cells if c]
        self.assertEqual(len(cells), 3)
        self.assertIn("`A`", cells[0])
        self.assertIn("`B`", cells[0])

    def test_ambiguous_same_line_case_variants_not_flagged(self):
        r = [routes.Route(["globex", "GLOBEX"], ["a.md"], [], 5)]
        self.assertEqual(routes.find_ambiguous(r), {})

    def test_ambiguous_cross_line_flagged(self):
        r = [routes.Route(["x"], ["a.md"], [], 5), routes.Route(["X"], ["b.md"], [], 9)]
        amb = routes.find_ambiguous(r)
        self.assertEqual(amb.get("x"), [5, 9])


class TestSensitivity(unittest.TestCase):
    def setUp(self):
        self.vocab = Vocabulary(VOCAB_DATA)

    def test_hit_customer(self):
        res = sensitivity.scan_text("这是给客户甲 acme-corp 的集成", self.vocab)
        self.assertTrue(res["any_hit"])
        self.assertEqual(res["suggested"], "maintainer-only")
        self.assertIn("客户甲", res["hits"]["customer_names"])

    def test_no_hit(self):
        res = sensitivity.scan_text("普通概念说明", self.vocab)
        self.assertFalse(res["any_hit"])
        self.assertEqual(res["suggested"], "public")

    def test_secret_and_attack(self):
        res = sensitivity.scan_text("clientSecret 配置,存在 SQL 注入面", self.vocab)
        self.assertIn("clientSecret", res["hits"]["secret_keywords"])
        self.assertIn("注入", res["hits"]["attack_surface"])


class TestSuggest(unittest.TestCase):
    def setUp(self):
        self.vocab = Vocabulary(VOCAB_DATA)

    def test_module_id_detected(self):
        res = suggest.suggest_path("T0119 入园预约改造", self.vocab, root="/nonexistent")
        self.assertEqual(res["page_type"], "module")

    def test_deterministic(self):
        a = suggest.suggest_path("flux-tms 定时器 概念", self.vocab, root="/nonexistent")
        b = suggest.suggest_path("flux-tms 定时器 概念", self.vocab, root="/nonexistent")
        self.assertEqual(a, b)


class TestValidate(unittest.TestCase):
    def setUp(self):
        self.vocab = Vocabulary(VOCAB_DATA)

    def test_missing_required(self):
        issues = validate.validate_page({"tags": ["concept"]}, True, "x.md", self.vocab)
        codes = {i["code"] for i in issues}
        self.assertIn("missing-field", codes)

    def test_bad_enum_and_page_type(self):
        meta = {"tags": ["concept"], "page_type": "bogus", "domain": "flux-tms",
                "shared_scope": "domain", "sensitivity": "team", "status": "active", "date_created": "2026-06-07"}
        issues = validate.validate_page(meta, True, "x.md", self.vocab)
        codes = {i["code"] for i in issues}
        self.assertIn("bad-page-type", codes)

    def test_status_in_tags_forbidden(self):
        meta = {"tags": ["稳定"], "page_type": "concept", "domain": "flux-tms",
                "shared_scope": "domain", "sensitivity": "team", "status": "active", "date_created": "2026-06-07"}
        issues = validate.validate_page(meta, True, "x.md", self.vocab)
        codes = {i["code"] for i in issues}
        self.assertIn("status-in-tags", codes)

    def test_clean_page_passes(self):
        meta = {"tags": ["concept"], "page_type": "concept", "domain": "flux-tms",
                "shared_scope": "domain", "sensitivity": "team", "status": "active", "date_created": "2026-06-07"}
        issues = validate.validate_page(meta, True, "x.md", self.vocab)
        errors = [i for i in issues if i["level"] == "error"]
        self.assertEqual(errors, [])


class TestIntegrationFixture(unittest.TestCase):
    """在临时 fixture wiki 上跑 repo 遍历 + lint。"""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wikitest-")
        # 最小 wiki:_vocabulary.md(JSON 块)、_routes.md、一个页面
        import json
        with open(os.path.join(self.dir, "_vocabulary.md"), "w", encoding="utf-8") as f:
            f.write("# vocab\n\n```json\n" + json.dumps(VOCAB_DATA, ensure_ascii=False) + "\n```\n")
        with open(os.path.join(self.dir, "_routes.md"), "w", encoding="utf-8") as f:
            f.write("| kw | req | opt |\n|---|---|---|\n| `timer` | `wiki/domains/flux-tms/concepts/timer.md` | |\n")
        os.makedirs(os.path.join(self.dir, "wiki", "domains", "flux-tms", "concepts"))
        page = os.path.join(self.dir, "wiki", "domains", "flux-tms", "concepts", "timer.md")
        with open(page, "w", encoding="utf-8") as f:
            f.write("---\ntags: [concept]\npage_type: concept\ndomain: flux-tms\n"
                    "shared_scope: domain\nsensitivity: team\nstatus: active\ndate_created: 2026-06-07\n---\n# Timer\nok\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_find_root_and_vocab(self):
        root = repo.find_wiki_root(self.dir)
        self.assertEqual(root, self.dir)
        vocab = load_vocab(root)
        self.assertEqual(vocab.protocol_version, 2)
        self.assertIn("flux-tms", vocab.domain_slugs)

    def test_lint_clean_fixture(self):
        report = lint.lint(self.dir)
        # 干净 fixture:无 error(timer.md 被路由覆盖、frontmatter 齐全)
        self.assertEqual(report["summary"]["errors"], 0, msg=str(report["sections"]))


class TestSecurityFixes(unittest.TestCase):
    """对抗审查确认问题的回归测试(frontmatter 密钥 / archive 审计 / 路径穿越 / publish)。"""

    def setUp(self):
        import json
        self.dir = tempfile.mkdtemp(prefix="wikisec-")
        with open(os.path.join(self.dir, "_vocabulary.md"), "w", encoding="utf-8") as f:
            f.write("# v\n\n```json\n" + json.dumps(VOCAB_DATA, ensure_ascii=False) + "\n```\n")
        with open(os.path.join(self.dir, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# protocol\n")
        # 双层布局:root 有 wiki/ 子目录 + 根级 archive/(复现 include_archive 失效场景)
        cdir = os.path.join(self.dir, "wiki", "domains", "flux-tms", "concepts")
        os.makedirs(cdir)
        os.makedirs(os.path.join(self.dir, "archive", "old-2026"))
        self.vocab = Vocabulary(VOCAB_DATA)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, rel, content):
        p = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return p

    def test_secret_in_frontmatter_detected(self):
        # 密钥只写在 frontmatter,body 干净,声明 public → 必须被判敏感
        p = self._write("wiki/domains/flux-tms/concepts/leak.md",
                        "---\ntitle: 配置 clientSecret=abc\nsensitivity: public\n---\n# clean body\n")
        res = sensitivity.scan_page(p, self.vocab, self.dir)
        self.assertTrue(res["any_hit"])
        self.assertIn("clientSecret", res["hits"]["secret_keywords"])
        self.assertTrue(res["under_declared"])

    def test_archive_scanned_when_include_archive(self):
        self._write("archive/old-2026/secret.md", "# 客户甲 集成\nclient_secret=x\n")
        active = list(repo.iter_pages(self.dir, include_archive=False))
        full = list(repo.iter_pages(self.dir, include_archive=True))
        self.assertFalse(any("archive" in p for p in active), "active 遍历不应含 archive")
        self.assertTrue(any("archive" in p for p in full), "include_archive=True 必须覆盖根级 archive")

    def test_resolve_in_root_blocks_traversal(self):
        self.assertIsNone(repo.resolve_in_root(self.dir, "../../etc/passwd"))
        self.assertIsNone(repo.resolve_in_root(self.dir, "/etc/passwd"))
        ok = repo.resolve_in_root(self.dir, "wiki/domains/flux-tms/concepts")
        self.assertIsNotNone(ok)

    def test_find_root_env_invalid_returns_none(self):
        old = os.environ.get("WIKI_ROOT")
        os.environ["WIKI_ROOT"] = os.path.join(self.dir, "nonexistent-xyz")
        try:
            root, source = repo.find_wiki_root_verbose()
            self.assertIsNone(root)
            self.assertEqual(source, "env-invalid")
        finally:
            if old is None:
                os.environ.pop("WIKI_ROOT", None)
            else:
                os.environ["WIKI_ROOT"] = old

    def test_publish_excludes_sensitive_and_personal(self):
        ok_page = "---\ntags: [concept]\npage_type: concept\ndomain: flux-tms\nshared_scope: domain\nsensitivity: team\nstatus: active\ndate_created: 2026-06-07\n---\n# ok\n"
        self._write("wiki/domains/flux-tms/concepts/ok.md", ok_page)
        self._write("wiki/domains/flux-tms/concepts/secret-page.md",
                    "---\ntags: [concept]\npage_type: concept\ndomain: flux-tms\nshared_scope: domain\nsensitivity: maintainer-only\nstatus: active\ndate_created: 2026-06-07\n---\n# s\n")
        os.makedirs(os.path.join(self.dir, "wiki", "domains", "personal"))
        self._write("wiki/domains/personal/me.md",
                    "---\ntags: [concept]\npage_type: concept\ndomain: personal\nshared_scope: domain\nsensitivity: team\nstatus: active\ndate_created: 2026-06-07\n---\n# me\n")
        plan = publish.plan(self.dir, self.vocab)
        inc = plan["included"]
        exc_paths = [e[0] for e in plan["excluded"]]
        self.assertTrue(any("ok.md" in p for p in inc))
        self.assertTrue(any("secret-page.md" in p for p in exc_paths), "maintainer-only 必须被排除")
        self.assertTrue(any("personal/me.md" in p for p in exc_paths), "publish:false 域必须被排除")


class TestMiscFixes(unittest.TestCase):
    def setUp(self):
        self.vocab = Vocabulary(VOCAB_DATA)

    def test_suggest_plural_dirs(self):
        r = suggest.suggest_path("flux-tms 客户 客户乙 概念", self.vocab, root="/nonexistent")
        # entity → entities,不能是 entitys
        if r["page_type"] == "entity":
            self.assertIn("/entities/", r["suggested_path"])

    def test_frontmatter_bom(self):
        text = "﻿---\ntags: [concept]\nstatus: active\n---\nbody"
        meta, _, has = frontmatter.parse(text)
        self.assertTrue(has, "BOM 不应导致误判无 frontmatter")
        self.assertEqual(meta["status"], "active")

    def test_validate_enum_as_list_flagged(self):
        meta = {"tags": ["concept"], "page_type": "concept", "domain": "flux-tms",
                "shared_scope": "domain", "sensitivity": "team", "status": ["active"], "date_created": "2026-06-07"}
        issues = validate.validate_page(meta, True, "x.md", self.vocab)
        self.assertIn("enum-is-list", {i["code"] for i in issues})


class TestScaffold(unittest.TestCase):
    """冷启动 scaffolder 回归。"""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wikiscaf-")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_init_creates_clean_lib(self):
        target = os.path.join(self.dir, "lib")
        res = scaffold.scaffold(target, domains=["backend", "frontend"], owner="alice",
                                profile="standard", date="2026-06-07")
        self.assertTrue(res["ok"], msg=str(res.get("lint_report")))
        self.assertEqual(res["lint_errors"], 0)
        for f in ["AGENTS.md", "_vocabulary.md", "_routes.md", "overview.md", "log.md"]:
            self.assertTrue(os.path.isfile(os.path.join(target, f)), f)
        v = load_vocab(target)
        self.assertEqual(v.protocol_version, scaffold.SUPPORTED_PROTOCOL_VERSION)
        self.assertEqual(set(v.domain_slugs), {"backend", "frontend"})
        self.assertFalse(v.parse_error)

    def test_init_minimal_drops_sensitivity_required(self):
        target = os.path.join(self.dir, "lib")
        res = scaffold.scaffold(target, domains=["kb"], profile="minimal", date="2026-06-07")
        self.assertTrue(res["ok"])
        v = load_vocab(target)
        self.assertNotIn("sensitivity", v.required_fields)

    def test_init_idempotent_norepeat(self):
        target = os.path.join(self.dir, "lib")
        r1 = scaffold.scaffold(target, domains=["kb"], date="2026-06-07")
        self.assertTrue(r1["ok"])
        self.assertFalse(r1["already_complete"])  # 首次有新建
        r2 = scaffold.scaffold(target, domains=["kb"], date="2026-06-07")
        self.assertTrue(r2["ok"])
        self.assertTrue(r2["already_complete"])    # 再跑 = no-op
        self.assertEqual(r2["created"], [])

    def test_init_repairs_missing_pieces(self):
        target = os.path.join(self.dir, "lib")
        scaffold.scaffold(target, domains=["kb"], date="2026-06-07")
        # 模拟层级损坏:删掉 _routes.md 和 archive/ 目录
        os.remove(os.path.join(target, "_routes.md"))
        import shutil
        shutil.rmtree(os.path.join(target, "archive"))
        r = scaffold.scaffold(target, date="2026-06-07")  # 修复(不传 domains,从现有词表读)
        self.assertTrue(r["ok"])
        self.assertIn("_routes.md", r["created"])
        self.assertTrue(any("archive" in c for c in r["created"]))
        self.assertTrue(os.path.isfile(os.path.join(target, "_routes.md")))

    def test_init_does_not_overwrite_existing(self):
        target = os.path.join(self.dir, "lib")
        scaffold.scaffold(target, domains=["kb"], date="2026-06-07")
        # 改一个已存在文件,再跑 init,内容不应被覆盖
        ov = os.path.join(target, "overview.md")
        with open(ov, "a", encoding="utf-8") as f:
            f.write("\nMY EDIT KEEP ME\n")
        scaffold.scaffold(target, date="2026-06-07")
        self.assertIn("MY EDIT KEEP ME", open(ov, encoding="utf-8").read())

    def test_check_mode_reports_missing_no_write(self):
        target = os.path.join(self.dir, "lib")
        res = scaffold.scaffold(target, domains=["kb"], date="2026-06-07", check=True)
        self.assertFalse(res["already_complete"])
        self.assertTrue(res["missing"])
        self.assertFalse(os.path.exists(os.path.join(target, "AGENTS.md")))  # check 不写盘


    def test_new_page_concept_is_valid(self):
        target = os.path.join(self.dir, "lib")
        scaffold.scaffold(target, domains=["backend"], date="2026-06-07")
        rel, content = scaffold.new_page(target, "concept", "redis-cache", "backend",
                                         title="Redis", date="2026-06-07")
        self.assertEqual(rel, os.path.join("wiki", "domains", "backend", "concepts", "redis-cache.md"))
        full = os.path.join(target, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        meta, _, has_fm = frontmatter.read_page(full)
        v = load_vocab(target)
        errs = [i for i in validate.validate_page(meta, has_fm, rel, v) if i["level"] == "error"]
        self.assertEqual(errs, [], msg=str(errs))

    def test_new_page_module_path(self):
        rel, _ = scaffold.new_page("/x", "module", "t0119-appt", "backend", date="2026-06-07")
        self.assertTrue(rel.endswith(os.path.join("modules", "t0119-appt", "README.md")))


class TestVocabParseError(unittest.TestCase):
    def test_broken_json_sets_parse_error(self):
        d = tempfile.mkdtemp(prefix="wikivocab-")
        try:
            with open(os.path.join(d, "_vocabulary.md"), "w", encoding="utf-8") as f:
                f.write("# v\n\n```json\n{ broken json ,, }\n```\n")
            v = load_vocab(d)
            self.assertTrue(v.parse_error)
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)


class TestStructureCheck(unittest.TestCase):
    """补盲回归:lint 必须能抓到空壳目录 / 放错层级的游离内容目录。"""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="wikistruct-")
        scaffold.scaffold(self.dir, domains=["backend"], date="2026-06-07")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_clean_lib_no_structure_issue(self):
        report = lint.lint(self.dir)
        struct = next(s for s in report["sections"] if s["name"] == "structure")
        self.assertEqual(struct["issues"], [], msg=str(struct["issues"]))

    def test_detects_stray_content_dir_at_root(self):
        # 复现用户的真实问题:仓库根冒出一个游离 domains/(内容应在 wiki/domains/)
        os.makedirs(os.path.join(self.dir, "domains", "flux-tms", "concepts"))
        report = lint.lint(self.dir)
        codes = {i["code"] for s in report["sections"] for i in s["issues"]}
        self.assertIn("stray-content-dir", codes)
        self.assertGreaterEqual(report["summary"]["errors"], 1)

    def test_detects_empty_domain_dir(self):
        os.makedirs(os.path.join(self.dir, "wiki", "domains", "backend", "concepts", "ghost"))
        report = lint.lint(self.dir)
        codes = {i["code"] for s in report["sections"] for i in s["issues"]}
        self.assertIn("empty-dir", codes)


class TestChanges(unittest.TestCase):
    def test_classify_granularity(self):
        k, n = changes.classify("wiki/domains/flux-tms/modules/t0119-appt/code-map.md")
        self.assertEqual((k, n), ("module", "flux-tms/t0119-appt"))
        self.assertEqual(changes.classify("wiki/domains/flux-tms/concepts/timer.md")[0], "concept")
        self.assertEqual(changes.classify("wiki/domains/flux-tms/entities/yum.md")[0], "entity")
        self.assertEqual(changes.classify("log.md")[0], "file")

    def test_incoming_detects_upstream(self):
        import shutil
        import subprocess
        git = shutil.which("git")
        if not git:
            self.skipTest("git 不可用")
        d = tempfile.mkdtemp(prefix="wikichg-")

        def run(*a, cwd):
            subprocess.run([git, "-c", "user.email=t@t.io", "-c", "user.name=t",
                            "-c", "commit.gpgsign=false", *a], cwd=cwd,
                           capture_output=True, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        try:
            team = os.path.join(d, "team")
            scaffold.scaffold(team, domains=["ops"], date="2026-06-07")
            run("init", "-q", "-b", "main", cwd=team)
            run("add", "-A", cwd=team)
            run("commit", "-qm", "init", cwd=team)
            member = os.path.join(d, "member")
            run("clone", "-q", team, member, cwd=d)
            # 团队再加一页 concept + commit
            rel, content = scaffold.new_page(team, "concept", "x", "ops", date="2026-06-07")
            full = os.path.join(team, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            run("add", "-A", cwd=team)
            run("commit", "-qm", "add x", cwd=team)
            # 成员 incoming(会 fetch)→ 应检测到落后 1 + 一条 concept 待更新
            res = changes.incoming(member, do_fetch=True)
            self.assertTrue(res["ok"], msg=str(res))
            self.assertEqual(res["behind_commits"], 1)
            self.assertFalse(res["up_to_date"])
            self.assertTrue(any(g["kind"] == "concept" for g in res["groups"]))
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
