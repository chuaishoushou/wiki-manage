#!/usr/bin/env python3
"""wiki-manage 一键自测(纯标准库,跨平台)。

端到端验证工具链,不依赖真实 wiki(自建临时干净 fixture,结果确定性):
  1) unittest 全套
  2) CLI 端到端:protocol / suggest / lint(干净库应 0 error)/ scan(归档密钥应命中)/
     validate / route / publish(dry-run)/ 路径穿越拦截
  3) sync-team 团队→个人镜像 / WIKI_ROOT 解析链
  4) wiki-init 自检

退出码:全过 0,否则 1。
用法:python3 plugins/wiki-governance/tools/selftest.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
CLI = os.path.join(HERE, "bin", "wiki-cli")
TESTS = os.path.join(HERE, "tests")
INIT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "bin", "wiki-init"))

sys.path.insert(0, SRC)

RESULTS = []  # (name, ok, detail)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    mark = "✅" if ok else "❌"
    print(f"{mark} {name}" + (f"  — {detail}" if detail else ""))


# ---------- 构造临时干净 wiki fixture ----------

VOCAB = {
    "protocol_version": 2,
    "domains": [
        {"slug": "flux-tms", "boundary": "FLUX TMS 运输管理 客户 模块 定时器", "owners": ["alice"], "status": "active"},
        {"slug": "personal", "boundary": "个人偏好", "owners": ["self"], "status": "active", "publish": False},
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
    "sensitivity_rules": {"default_on_hit": "maintainer-only",
                          "customer_names": ["客户甲"], "secret_keywords": ["clientSecret"],
                          "attack_surface_keywords": ["注入"]},
    "publish": {"max_sensitivity": "team"},
}

CLEAN_PAGE = ("---\ntags: [concept, timer]\npage_type: concept\ndomain: flux-tms\n"
              "shared_scope: domain\nsensitivity: team\nstatus: active\ndate_created: 2026-06-07\n---\n"
              "# 定时器机制\n正常内容。\n")


def build_fixture(root):
    with open(os.path.join(root, "_vocabulary.md"), "w", encoding="utf-8") as f:
        f.write("# vocab\n\n```json\n" + json.dumps(VOCAB, ensure_ascii=False) + "\n```\n")
    with open(os.path.join(root, "AGENTS.md"), "w", encoding="utf-8") as f:
        f.write("# protocol\n协议正文。\n")
    with open(os.path.join(root, "overview.md"), "w", encoding="utf-8") as f:
        f.write("# overview\n")
    cdir = os.path.join(root, "wiki", "domains", "flux-tms", "concepts")
    os.makedirs(cdir)
    with open(os.path.join(cdir, "timer.md"), "w", encoding="utf-8") as f:
        f.write(CLEAN_PAGE)
    # 路由覆盖该页(否则 orphan 警告)
    with open(os.path.join(root, "_routes.md"), "w", encoding="utf-8") as f:
        f.write("| 触发关键词 | 必加载 | 可选加载 |\n|---|---|---|\n"
                "| `timer` \\| `定时器` | `wiki/domains/flux-tms/concepts/timer.md` | |\n")
    # 根级 archive,含敏感(测 scan 是否覆盖 archive)
    adir = os.path.join(root, "archive", "old-2026")
    os.makedirs(adir)
    with open(os.path.join(adir, "leak.md"), "w", encoding="utf-8") as f:
        f.write("# 客户甲 集成\nclientSecret=xxx,存在注入面。\n")


def run_cli(root, *args):
    env = dict(os.environ, WIKI_ROOT=root)
    return subprocess.run([sys.executable, CLI, "--json", *args],
                          capture_output=True, text=True, env=env, timeout=30)


def cli_checks(root):
    # protocol
    r = run_cli(root, "protocol")
    try:
        d = json.loads(r.stdout)
        check("CLI protocol", d["repo_protocol_version"] == 2 and d["version_ok"] and d["root_source"] == "env",
              f"pv={d['repo_protocol_version']} source={d['root_source']}")
    except Exception as e:
        check("CLI protocol", False, f"{e}: {r.stdout[:80]}{r.stderr[:80]}")

    # lint:干净库应 0 error
    r = run_cli(root, "lint")
    try:
        d = json.loads(r.stdout)
        check("CLI lint(干净库 0 error)", d["summary"]["errors"] == 0, f"errors={d['summary']['errors']}")
    except Exception as e:
        check("CLI lint", False, f"{e}: {r.stdout[:120]}")

    # scan:必须扫到 archive 里的 clientSecret + 客户甲
    r = run_cli(root, "scan")
    try:
        d = json.loads(r.stdout)
        hit = any("archive" in f["path"] and (f["hits"]["secret_keywords"] or f["hits"]["customer_names"])
                  for f in d["findings"])
        check("CLI scan(覆盖 archive 敏感)", hit, f"findings={d['total_findings']} risky={d['risky_count']}")
    except Exception as e:
        check("CLI scan", False, f"{e}: {r.stdout[:120]}")

    # suggest:T0119 → module
    r = run_cli(root, "suggest", "T0119 入园预约")
    try:
        d = json.loads(r.stdout)
        check("CLI suggest(模块号→module)", d["page_type"] == "module", f"type={d['page_type']} conf={d['confidence']}")
    except Exception as e:
        check("CLI suggest", False, str(e))

    # route:timer 命中
    r = run_cli(root, "route", "定时器")
    try:
        d = json.loads(r.stdout)
        check("CLI route(关键词命中)", len(d["hits"]) == 1 and not d["hits"][0].get("ambiguous", False),
              f"hits={len(d['hits'])}")
    except Exception as e:
        check("CLI route", False, str(e))

    # validate:干净页 ok
    r = run_cli(root, "validate", "wiki/domains/flux-tms/concepts/timer.md")
    try:
        d = json.loads(r.stdout)
        check("CLI validate(干净页无 error)", not any(i["level"] == "error" for i in d["issues"]))
    except Exception as e:
        check("CLI validate", False, str(e))

    # 路径穿越拦截(非 JSON 路径,看退出码 2)
    env = dict(os.environ, WIKI_ROOT=root)
    r = subprocess.run([sys.executable, CLI, "get", "../../etc/passwd"],
                       capture_output=True, text=True, env=env, timeout=30)
    check("CLI 路径穿越拦截", r.returncode == 2, f"exit={r.returncode}")

    # new:轻量建页应产出 0-error 合规页
    r = run_cli(root, "new", "concept", "selftest-newpage", "--domain", "flux-tms", "--title", "自测页")
    try:
        d = json.loads(r.stdout)
        check("CLI new(建合规页)", d.get("ok") is True, f"path={d.get('path')}")
    except Exception as e:
        check("CLI new", False, f"{e}: {r.stdout[:120]}{r.stderr[:120]}")

    # publish dry-run:干净 team 页应 included,personal/archive 应排除
    r = run_cli(root, "publish")
    try:
        d = json.loads(r.stdout)
        ok = any("timer.md" in p for p in d["included"]) and len(d["risky"]) >= 1
        check("CLI publish(白名单规划)", ok, f"included={len(d['included'])} excluded={len(d['excluded'])} risky={len(d['risky'])}")
    except Exception as e:
        check("CLI publish", False, f"{e}: {r.stdout[:120]}")


def root_resolution_checks():
    """单元测试 WIKI_ROOT 解析优先级链(不依赖真实 ~/AI 库,monkeypatch 兜底常量)。

    覆盖本次上线的关键修复:env 未设时优先 team-default(团队库)而非 personal-fallback
    (个人库);env 配错时 env-invalid 硬失败、绝不静默回退。
    """
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
    from wiki_core import repo
    orig_team, orig_personal = repo.TEAM_WIKI_FALLBACK, repo.PERSONAL_WIKI_FALLBACK
    orig_env, orig_cwd = os.environ.get("WIKI_ROOT"), os.getcwd()
    with tempfile.TemporaryDirectory() as team, \
            tempfile.TemporaryDirectory() as personal, \
            tempfile.TemporaryDirectory() as envroot, \
            tempfile.TemporaryDirectory() as neutral:
        for d in (team, personal, envroot):
            open(os.path.join(d, "AGENTS.md"), "w").close()  # 造合法 wiki 根标记
        try:
            os.chdir(neutral)  # 隔离 cwd 上溯,避免命中真实库
            repo.TEAM_WIKI_FALLBACK, repo.PERSONAL_WIKI_FALLBACK = team, personal
            os.environ.pop("WIKI_ROOT", None)
            r, s = repo.find_wiki_root_verbose()
            check("解析链:env 未设→team-default(不落个人库)",
                  s == "team-default" and r == os.path.abspath(team), f"got source={s}")
            repo.TEAM_WIKI_FALLBACK = os.path.join(team, "absent")
            r, s = repo.find_wiki_root_verbose()
            check("解析链:team 缺→personal-fallback",
                  s == "personal-fallback" and r == os.path.abspath(personal), f"got source={s}")
            os.environ["WIKI_ROOT"] = envroot
            r, s = repo.find_wiki_root_verbose()
            check("解析链:env 合法→env", s == "env", f"got source={s}")
            os.environ["WIKI_ROOT"] = os.path.join(envroot, "bad")
            r, s = repo.find_wiki_root_verbose()
            check("解析链:env 非法→env-invalid 硬失败(不静默回退)",
                  s == "env-invalid" and r is None, f"got source={s}")
        finally:
            repo.TEAM_WIKI_FALLBACK, repo.PERSONAL_WIKI_FALLBACK = orig_team, orig_personal
            if orig_env is None:
                os.environ.pop("WIKI_ROOT", None)
            else:
                os.environ["WIKI_ROOT"] = orig_env
            os.chdir(orig_cwd)


def sync_checks():
    """测 sync-team:团队仓→个人库 team/ 镜像(首次/幂等/增量删除/检索可达/lint 跳过)。"""
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
    from wiki_core import sync, search as search_mod, lint as lint_mod

    def _w(p, c):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(c)

    with tempfile.TemporaryDirectory() as team, tempfile.TemporaryDirectory() as personal:
        open(os.path.join(team, "AGENTS.md"), "w").close()  # 团队仓 = 合法 wiki 根
        tc = os.path.join(team, "wiki", "domains", "ops", "concepts")
        _w(os.path.join(tc, "deploy.md"), "# 部署\n团队部署知识")
        _w(os.path.join(tc, "alert.md"), "# 告警\n团队告警知识")
        open(os.path.join(personal, "AGENTS.md"), "w").close()  # 个人库 = 合法 wiki 根
        os.makedirs(os.path.join(personal, "wiki"))

        r1 = sync.sync_team(personal, team)
        check("sync:首次镜像 2 页", r1.get("ok") and len(r1["added"]) == 2, f"added={r1.get('added')}")
        mr = sync.mirror_root(personal)
        check("sync:镜像文件落地", os.path.isfile(os.path.join(mr, "domains/ops/concepts/deploy.md")))

        r2 = sync.sync_team(personal, team)
        check("sync:幂等(再同步全 unchanged)",
              not r2["added"] and not r2["updated"] and r2["unchanged_count"] == 2,
              f"a={r2['added']} u={r2['updated']} unch={r2['unchanged_count']}")

        _w(os.path.join(tc, "deploy.md"), "# 部署\n更新后的部署知识")
        os.remove(os.path.join(tc, "alert.md"))
        _w(os.path.join(tc, "rollback.md"), "# 回滚\n新增")
        r3 = sync.sync_team(personal, team)
        check("sync:增量对齐(改1/删1/增1)",
              r3["updated"] == ["domains/ops/concepts/deploy.md"]
              and r3["deleted"] == ["domains/ops/concepts/alert.md"]
              and r3["added"] == ["domains/ops/concepts/rollback.md"],
              f"u={r3['updated']} d={r3['deleted']} a={r3['added']}")
        check("sync:删除页镜像已移除",
              not os.path.isfile(os.path.join(mr, "domains/ops/concepts/alert.md")))

        res = search_mod.search(personal, "回滚", limit=10)
        in_team = [r for r in res if "team" in r["path"].replace("\\", "/").split("/")]
        check("sync:个人库 search 检索到 team 镜像", bool(in_team), f"paths={[r['path'] for r in res]}")

        rep = lint_mod.lint(personal)
        team_errs = [i for s in rep["sections"] for i in s["issues"]
                     if "team" in (i.get("path") or "").replace("\\", "/").split("/")]
        check("sync:lint 跳过 team 镜像区", not team_errs, f"team_errs={team_errs}")


def main():
    print("=" * 60)
    print("wiki-manage 自测")
    print("=" * 60)

    # 1) unittest
    print("\n[1/6] unittest")
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", TESTS],
                       capture_output=True, text=True, cwd=HERE)
    last = (r.stderr.strip().splitlines() or ["?"])[-1]
    check("unittest 全套", r.returncode == 0, last)

    print("\n[1b/6] WIKI_ROOT 解析优先级链(团队库优先于个人库兜底)")
    root_resolution_checks()

    print("\n[1c/6] sync-team 团队→个人镜像同步")
    sync_checks()

    # 2-4) 端到端(临时 fixture)
    with tempfile.TemporaryDirectory(prefix="wiki-selftest-") as root:
        build_fixture(root)
        print("\n[2/6] CLI 端到端")
        cli_checks(root)
        print("\n[4/6] wiki-init 自检")
        env = dict(os.environ, WIKI_ROOT=root)
        r = subprocess.run([sys.executable, INIT, "--platform", "codex", "--wiki-root", root],
                           capture_output=True, text=True, env=env, timeout=30)
        check("wiki-init 自检", r.returncode == 0 and "自检通过" in r.stdout)

    print("\n[5/6] skill 触发词覆盖(evals)")
    evals = os.path.abspath(os.path.join(HERE, "..", "evals", "check_descriptions.py"))
    r = subprocess.run([sys.executable, evals], capture_output=True, text=True, timeout=30)
    check("evals description 覆盖", r.returncode == 0)

    print("\n[6/6] scaffolder(wiki-cli init 冷启动建库)")
    with tempfile.TemporaryDirectory(prefix="wiki-init-") as d:
        target = os.path.join(d, "newlib")
        env = dict(os.environ)
        env.pop("WIKI_ROOT", None)
        r = subprocess.run([sys.executable, CLI, "--json", "init", target, "--domains", "a,b", "--owner", "x"],
                           capture_output=True, text=True, env=env, timeout=30)
        try:
            out = json.loads(r.stdout)
            check("wiki-cli init 建出 0-error 合规库",
                  out.get("ok") and out.get("lint_errors") == 0,
                  f"errors={out.get('lint_errors')} warns={out.get('lint_warns')}")
        except Exception as e:
            check("wiki-cli init", False, f"{e}: {r.stdout[:120]}{r.stderr[:120]}")

    # 汇总
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print("\n" + "=" * 60)
    print(f"结果:{passed}/{total} 通过")
    print("=" * 60)
    if passed != total:
        print("失败项:")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"  ❌ {name}  {detail}")
        return 1
    print("✅ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
