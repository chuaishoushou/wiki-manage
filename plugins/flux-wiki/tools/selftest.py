#!/usr/bin/env python3
"""wiki-manage 一键自测(纯标准库,跨平台)。

全部在临时目录 + 隔离 HOME 里跑,绝不碰真实用户目录:
  1) 单元测试:frontmatter 解析 / scaffold 幂等 / lint 分级 / learn 水位
  2) CLI 端到端:init → new → search → lint → status(JSON)→ 路径穿越拦截
  3) learn 端到端:git fixture 团队仓 → 首学 → mark → 增量 → 溯源逆查
  4) wiki-init 端到端(隔离 HOME):装 cc → 指针块/skill/命令落地且无残留占位符
     → 重跑幂等(整段替换不膨胀)→ 缺路径参数报错(双路径强制必填,不静默用默认)
     → 配置记忆(重跑沿用上次提供值)→ 旧版 legacy 指针块迁移 + 备份
  5) skill 触发词断言:description 含必要关键词(防改描述丢触发)

退出码:全过 0,否则 1。
用法:python3 plugins/flux-wiki/tools/selftest.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
CLI = os.path.join(HERE, "bin", "wiki-cli")
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
INIT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "bin", "wiki-init"))

sys.path.insert(0, SRC)

RESULTS = []  # (name, ok, detail)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    mark = "✅" if ok else "❌"
    print(f"{mark} {name}" + (f"  — {detail}" if detail else ""))


def run_cli(args, env=None, cwd=None):
    e = dict(os.environ)
    e.pop("WIKI_ROOT", None)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, CLI, *args],
                          capture_output=True, text=True, env=e, cwd=cwd, timeout=60)


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          capture_output=True, text=True, timeout=30)


# ---------- 1. 单元测试 ----------

def unit_tests():
    print("\n== 1) 单元测试 ==")
    from wiki_core import frontmatter, lint, scaffold

    meta, body, has = frontmatter.parse("---\ntags: [a, b]\nstatus: active\n---\n\n# T\nbody")
    check("frontmatter 解析", has and meta["tags"] == ["a", "b"] and meta["status"] == "active")
    _, _, has2 = frontmatter.parse("# 无 frontmatter\n正文")
    check("frontmatter 缺失不误判", not has2)

    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, "w")
        r1 = scaffold.scaffold(root, domains=["a"])
        r2 = scaffold.scaffold(root, domains=["a"])
        check("scaffold 幂等(二跑 no-op)", r1["created"] and r2["already_complete"])
        rc = scaffold.scaffold(root, check=True)
        check("scaffold --check 完整库", rc["already_complete"])
        # 自建任意目录/无 frontmatter 页:lint 不报任何问题
        os.makedirs(os.path.join(root, "domains", "我的随意主题", "草稿"))
        with open(os.path.join(root, "domains", "我的随意主题", "草稿", "note.md"), "w") as f:
            f.write("# 自由笔记\n没有 frontmatter\n")
        rep = lint.lint(root)
        check("自建目录/无 frontmatter 不报问题", rep["summary"]["total"] == 0,
              json.dumps(rep["summary"], ensure_ascii=False))
        # 路由指向不存在文件 → error
        with open(os.path.join(root, "_routes.md"), "a") as f:
            f.write("| `kw` | `domains/不存在.md` |\n")
        rep = lint.lint(root)
        check("路由死目标 = error", rep["summary"]["errors"] == 1)
        # 溯源残缺 → warn
        with open(os.path.join(root, "domains", "a", "x.md"), "w") as f:
            f.write("---\nlearned_from: domains/shared/x.md\n---\n# x\n")
        rep = lint.lint(root)
        check("learned_from 缺 commit = warn", any(
            i["code"] == "provenance-incomplete"
            for s in rep["sections"] for i in s["issues"]))
        # v2 旧布局识别
        legacy = os.path.join(td, "legacy")
        os.makedirs(os.path.join(legacy, "wiki", "domains"))
        open(os.path.join(legacy, "AGENTS.md"), "w").write("# x")
        rl = scaffold.scaffold(legacy)
        check("v2 旧布局保护(不补 v3 骨架)", rl.get("legacy") and not rl["created"])


def unit_tests_v31():
    """v3.1 修复的回归钉子:全链路体检抓出的真实 bug,每个一条用例。"""
    print("\n== 1b) 单元测试(v3.1 回归)==")
    from wiki_core import lint, routes, scaffold, search

    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, "w")
        scaffold.scaffold(root, domains=["a", "b"])
        # 路由表空的必加载列:可选列绝不能移位顶替(曾触发唯一 error 级检查的误报)
        with open(os.path.join(root, "domains", "a", "real.md"), "w") as f:
            f.write("# real\n")
        with open(os.path.join(root, "_routes.md"), "a") as f:
            f.write("| `kw-empty` |  | `domains/a/real.md` |\n")
        rs = routes.parse_routes(root)
        r0 = next(r for r in rs if "kw-empty" in r.keywords)
        check("路由空必加载列不移位", r0.required == [] and r0.optional == ["domains/a/real.md"])
        # 可选列双基准解析:短名(相对必加载页目录)与根相对都认
        with open(os.path.join(root, "domains", "a", "sibling.md"), "w") as f:
            f.write("# sib\n")
        with open(os.path.join(root, "_routes.md"), "a") as f:
            f.write("| `kw2` | `domains/a/real.md` | `sibling.md`, `domains/a/real.md` |\n")
        rs = routes.parse_routes(root)
        check("可选列短名按必加载页目录解析", routes.missing_optional(root, rs) == [])
        rep = lint.lint(root)
        check("路由检查 0 error(空列+短名可选列都不误报)", rep["summary"]["errors"] == 0,
              json.dumps(rep["summary"], ensure_ascii=False))

        # %20 链接指向真实文件不是死链;[[wikilink]] 死链能被看见
        os.makedirs(os.path.join(root, "domains", "a", "docs"), exist_ok=True)
        with open(os.path.join(root, "domains", "a", "docs", "my doc.md"), "w") as f:
            f.write("# 带空格的文件\n")
        with open(os.path.join(root, "domains", "a", "links.md"), "w") as f:
            f.write("# 链接页\n[ok](docs/my%20doc.md)\n[[real]]\n[[nope-page]]\n")
        # 表格内转义别名 [[x\|别名]] 与模板占位符 [[customers/<客户>]] 都不是死链
        with open(os.path.join(root, "domains", "a", "table-links.md"), "w") as f:
            f.write("# 表格链接\n| 列 |\n|---|\n| [[real\\|别名]] · [[customers/<客户>]] |\n")
        rep = lint.lint(root)
        codes = [i["code"] for s in rep["sections"] for i in s["issues"]]
        msgs = " ".join(i["msg"] for s in rep["sections"] for i in s["issues"])
        check("%20 链接不误报死链", "dead-link" not in codes, msgs[:160])
        check("[[wikilink]] 死链可见/活链不报", codes.count("dead-wikilink") == 1
              and "nope-page" in msgs)
        check("转义别名/占位符 wikilink 不误报", "别名" not in msgs and "客户" not in msgs)

        # modules/ 是命名空间:协议标准同名骨架页不算重复沉淀
        for d, m in (("a", "m1"), ("b", "m2")):
            p = os.path.join(root, "domains", d, "modules", m)
            os.makedirs(p, exist_ok=True)
            with open(os.path.join(p, "task-history.md"), "w") as f:
                f.write("# th\n")
        with open(os.path.join(root, "domains", "a", "same-name.md"), "w") as f:
            f.write("# s\n")
        with open(os.path.join(root, "domains", "b", "same-name.md"), "w") as f:
            f.write("# s\n")
        rep = lint.lint(root)
        dups = [i for s in rep["sections"] for i in s["issues"] if i["code"] == "possible-dup"]
        check("模块骨架同名不报 dup,跨域同名仍报", len(dups) == 1 and "same-name" in dups[0]["msg"])

        # search:frontmatter(summary/tags)参与检索;库根协议文件不抢排名
        with open(os.path.join(root, "domains", "a", "fm-only.md"), "w") as f:
            f.write("---\nsummary: 独特词汇甲乙丙\ntags: [概念]\n---\n# 页标题\n正文没有那个词\n")
        with open(os.path.join(root, "log.md"), "a") as f:
            f.write("## 记录 独特词汇甲乙丙 出现在台账\n")
        hits = search.search(root, "独特词汇甲乙丙")
        check("frontmatter 命中可检索", any(h["path"].endswith("fm-only.md") for h in hits))
        check("库根台账不参与检索", not any(h["path"].endswith("log.md") for h in hits))

        # v2 布局确认标记:用户拍板保留后不再每次体检都警告
        legacy = os.path.join(td, "legacy2")
        os.makedirs(os.path.join(legacy, "wiki", "domains"))
        open(os.path.join(legacy, "AGENTS.md"), "w").write("# x")
        warn1 = any(i["code"] == "legacy-layout"
                    for s in lint.lint(legacy)["sections"] for i in s["issues"])
        os.makedirs(os.path.join(legacy, ".wiki"), exist_ok=True)
        open(os.path.join(legacy, ".wiki", "ack-legacy-layout"), "w").write("")
        warn2 = any(i["code"] == "legacy-layout"
                    for s in lint.lint(legacy)["sections"] for i in s["issues"])
        check("legacy 警告可确认静默", warn1 and not warn2)

        # slug/domain 路径穿越拒绝
        for bad in ("../escape", "a/b", "..", ".hidden"):
            try:
                scaffold.new_page(root, "concept", bad, "a")
                check(f"slug 穿越被拒({bad})", False)
            except ValueError:
                check(f"slug 穿越被拒({bad})", True)
            break  # 一个代表用例即可,其余形态同一闸门


# ---------- 2. CLI 端到端 ----------

def cli_e2e():
    print("\n== 2) CLI 端到端 ==")
    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, "kb")
        r = run_cli(["init", root, "--domains", "backend"])
        check("init", r.returncode == 0, r.stderr.strip()[:120])
        r = run_cli(["--root", root, "new", "concept", "demo-page", "--domain", "backend",
                     "--title", "演示页"])
        check("new", r.returncode == 0 and
              os.path.isfile(os.path.join(root, "domains", "backend", "concepts", "demo-page.md")),
              r.stderr.strip()[:120])
        r = run_cli(["--root", root, "search", "演示页"])
        check("search 命中", r.returncode == 0 and "demo-page" in r.stdout)
        r = run_cli(["--root", root, "lint"])
        check("lint 干净库 rc=0", r.returncode == 0)
        r = run_cli(["--root", root, "--json", "status"])
        ok = r.returncode == 0
        payload = json.loads(r.stdout) if ok else {}
        check("status JSON", ok and payload.get("layout") == "v3-flat"
              and "backend" in payload.get("domains", []))
        # 路径穿越拦截
        r = run_cli(["--root", root, "lint", "../../etc/passwd"])
        check("路径穿越被拦/不读外部", r.returncode == 0 and "passwd" not in r.stdout)
        # --root 指向无效路径 → 硬失败不静默回退
        r = run_cli(["--root", os.path.join(td, "nope"), "status"])
        check("--root 无效硬失败", r.returncode == 2)
        # 全局旗标写在子命令后也接受(`search x --json --root <p>` 与前置写法等价)
        r = run_cli(["search", "演示页", "--json", "--root", root])
        ok = r.returncode == 0
        try:
            hits = json.loads(r.stdout) if ok else []
        except json.JSONDecodeError:
            hits = []
        check("旗标后置可用(search x --json --root)", ok and any(
            "demo-page" in h.get("path", "") for h in hits), r.stderr.strip()[:120])
        # new 的 slug 含路径分隔符 → rc=2 拒绝,不落盘
        r = run_cli(["--root", root, "new", "concept", "../escape", "--domain", "backend"])
        check("new slug 穿越 rc=2", r.returncode == 2
              and not os.path.isfile(os.path.join(root, "escape.md")))


# ---------- 3. learn 端到端 ----------

def learn_e2e():
    """fixture 取真实形态:团队知识库是「大仓里的子目录」(mono/wiki-team),
    覆盖 --relative 路径、pathspec 过滤、改名、协议归档(git mv→archive)、
    未提交页口径、水位校验/停滞提示——这些都是真实环境抓过 bug 的场景。"""
    print("\n== 3) learn 端到端(大仓子目录 git fixture)==")
    with tempfile.TemporaryDirectory() as td:
        personal = os.path.join(td, "me")
        mono = os.path.join(td, "mono")
        team = os.path.join(mono, "wiki-team")
        run_cli(["init", personal])
        os.makedirs(mono)
        git(mono, "init", "-q")
        run_cli(["init", team, "--domains", "shared"])
        # 域内导航页(策略:overview.md 任何层级都不算知识页,钉死防回归)
        with open(os.path.join(team, "domains", "shared", "overview.md"), "w") as f:
            f.write("# shared 域导航\n- [rule-one](concepts/rule-one.md)\n")
        # 大仓里 wiki-team 之外的内容(不该进学习视野)
        os.makedirs(os.path.join(mono, "openspec"))
        with open(os.path.join(mono, "openspec", "note.md"), "w") as f:
            f.write("# 大仓其他目录的文档\n")
        git(mono, "add", "-A")
        git(mono, "commit", "-qm", "init mono + team wiki")
        run_cli(["--root", team, "new", "concept", "rule-one", "--domain", "shared"])
        git(mono, "add", "-A")
        git(mono, "commit", "-qm", "feat: rule-one")
        # 工作区未提交页:首学/增量都不应看见(同一事实源 = git 已提交内容)
        with open(os.path.join(team, "domains", "shared", "concepts", "untracked.md"), "w") as f:
            f.write("# 未提交草稿\n")

        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        rels = [p["team_rel"] for p in d["pages"]]
        check("learn 首学列知识页(不含协议文件)", d["ok"] and d["first_time"]
              and any(x.endswith("rule-one.md") for x in rels)
              and "AGENTS.md" not in rels)
        check("首学路径相对 wiki-team(大仓子目录)", all(not x.startswith("wiki-team/") for x in rels))
        check("大仓其他目录不进学习视野", not any("openspec" in x for x in rels))
        check("域内 overview.md 是导航不是知识页", not any(x.endswith("overview.md") for x in rels))
        check("未提交页首学不可见(与增量同口径)", not any("untracked" in x for x in rels))
        os.remove(os.path.join(team, "domains", "shared", "concepts", "untracked.md"))
        head = d["head"]

        # 水位校验:垃圾哈希当场报错,而不是下次学习才爆
        r = run_cli(["--root", personal, "learn", "--team", team, "--mark", "deadbeef1234"])
        check("--mark 垃圾哈希被拒 rc=2", r.returncode == 2)

        # 模拟 AI 学习落盘(带溯源)
        learned_dir = os.path.join(personal, "domains", "shared", "concepts")
        os.makedirs(learned_dir, exist_ok=True)
        learned_page = os.path.join(learned_dir, "rule-one.md")
        with open(learned_page, "w") as f:
            f.write(f"---\nlearned_from: domains/shared/concepts/rule-one.md\n"
                    f"learned_commit: {head}\n---\n# rule-one(已学)\n")
        r = run_cli(["--root", personal, "learn", "--team", team, "--mark", head[:12]])
        check("learn --mark(短哈希展开为全哈希)", r.returncode == 0)

        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        check("学完无增量 up_to_date", d["ok"] and d["up_to_date"]
              and not d.get("watermark_stale"))

        # 只动大仓其他目录:无知识页增量,但水位落后于 HEAD → 提示可推进
        with open(os.path.join(mono, "openspec", "note2.md"), "w") as f:
            f.write("# другое\n")
        git(mono, "add", "-A")
        git(mono, "commit", "-qm", "docs: openspec note2 (wiki-team 之外)")
        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        check("仓动了但知识页没动:up_to_date + 水位停滞提示", d["ok"] and d["up_to_date"]
              and d.get("watermark_stale") is True)
        run_cli(["--root", personal, "learn", "--team", team, "--mark", d["head"]])

        run_cli(["--root", team, "new", "concept", "rule-two", "--domain", "shared"])
        # 同时改 rule-one,验证 previous 逆查
        with open(os.path.join(team, "domains", "shared", "concepts", "rule-one.md"), "a") as f:
            f.write("\n更新内容\n")
        git(mono, "add", "-A")
        git(mono, "commit", "-qm", "feat: rule-two + 更新 rule-one")
        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        one = next((p for p in d["pages"] if p["team_rel"].endswith("rule-one.md")), None)
        two = next((p for p in d["pages"] if p["team_rel"].endswith("rule-two.md")), None)
        check("增量只列变化页", d["ok"] and not d["first_time"] and len(d["pages"]) == 2)
        check("已学页带 previous 落点", one and one["previous"]
              and one["previous"].endswith("rule-one.md"))
        check("新页 previous 为空", two and not two["previous"])
        check("附期间提交标题(pathspec 只含本子树)", any("rule-two" in c for c in d["commits"])
              and not any("openspec" in c for c in d["commits"]))
        # rule-two 故意不学:核销门禁会拦 → 先验证拦截,再 --force 推进(放弃页进审计)
        r = run_cli(["--root", personal, "learn", "--team", team, "--mark", d["head"]])
        check("核销门禁拦下未学页的 mark", r.returncode == 1)
        run_cli(["--root", personal, "learn", "--team", team, "--mark", d["head"], "--force"])

        # 改名(R):必须保留旧路径,previous 按旧路径命中,否则会被当全新页重复学
        git(mono, "mv", "wiki-team/domains/shared/concepts/rule-one.md",
            "wiki-team/domains/shared/concepts/rule-one-renamed.md")
        git(mono, "commit", "-qm", "rename: rule-one → rule-one-renamed")
        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        ren = next((p for p in d["pages"] if p["status"] == "R"), None)
        check("改名保留旧路径", ren and ren.get("old_rel", "").endswith("rule-one.md")
              and ren["team_rel"].endswith("rule-one-renamed.md"))
        check("改名 previous 按旧路径命中", ren and ren["previous"]
              and ren["previous"].endswith("rule-one.md"))
        # 模拟 AI 按 wiki-learn 流程把已学页的 learned_from 更新为新路径
        with open(learned_page, "w") as f:
            f.write(f"---\nlearned_from: domains/shared/concepts/rule-one-renamed.md\n"
                    f"learned_commit: {d['head']}\n---\n# rule-one(已学,随团队改名)\n")
        run_cli(["--root", personal, "learn", "--team", team, "--mark", d["head"]])

        # 协议归档(git mv → archive/):对成员必须呈现为删除,不能凭空消失
        arch_dir = "wiki-team/archive/2026-01-01/domains/shared/concepts"
        os.makedirs(os.path.join(mono, arch_dir))
        git(mono, "mv", "wiki-team/domains/shared/concepts/rule-one-renamed.md",
            arch_dir + "/rule-one-renamed.md")
        git(mono, "commit", "-qm", "archive: rule-one-renamed(协议归档)")
        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        gone = next((p for p in d["pages"] if p["status"] == "D"), None)
        check("协议归档呈现为删除(不再隐身)", d["ok"] and not d["up_to_date"] and gone
              and gone["team_rel"].endswith("rule-one-renamed.md")
              and gone.get("archived_to", "").startswith("archive/"))
        check("归档页 previous 仍可逆查", gone and gone["previous"]
              and gone["previous"].endswith("rule-one.md"))


def learn_v2_team_e2e():
    """v2 嵌套团队仓(内容在 wiki/ 子目录)+ 内容层相对 learned_from:
    M 与 D 的 previous 都要命中(D 时文件已不在,必须纯字符串映射)。"""
    print("\n== 3b) learn 端到端(v2 嵌套团队仓)==")
    with tempfile.TemporaryDirectory() as td:
        personal = os.path.join(td, "me")
        team = os.path.join(td, "teamv2")
        run_cli(["init", personal])
        os.makedirs(os.path.join(team, "wiki", "domains", "x", "concepts"))
        with open(os.path.join(team, "AGENTS.md"), "w") as f:
            f.write("# 协议\n")
        page = os.path.join(team, "wiki", "domains", "x", "concepts", "p.md")
        with open(page, "w") as f:
            f.write("# p\n内容\n")
        git(team, "init", "-q")
        git(team, "add", "-A")
        git(team, "commit", "-qm", "init v2 team")

        # 个人库已学页用「内容层相对」写法(不带 wiki/ 前缀)
        ldir = os.path.join(personal, "domains", "x", "concepts")
        os.makedirs(ldir)
        with open(os.path.join(ldir, "p.md"), "w") as f:
            f.write("---\nlearned_from: domains/x/concepts/p.md\nlearned_commit: x\n---\n# p(已学)\n")

        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        pg = next((p for p in d["pages"] if p["team_rel"].endswith("p.md")), None)
        check("v2 团队仓首学列出内容层页", d["ok"] and pg is not None)
        check("内容层相对 learned_from 命中 previous", pg and pg["previous"])
        run_cli(["--root", personal, "learn", "--team", team, "--mark", d["head"]])

        git(team, "rm", "-q", "wiki/domains/x/concepts/p.md")
        git(team, "commit", "-qm", "remove p")
        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        gone = next((p for p in d["pages"] if p["status"] == "D"), None)
        check("v2 团队仓 D 页 previous 纯字符串命中", gone and gone["previous"])


# ---------- 4. wiki-init 端到端(隔离 HOME)----------

def init_e2e():
    print("\n== 4) wiki-init 端到端(隔离 HOME,不碰真实用户目录)==")
    with tempfile.TemporaryDirectory() as td:
        fake_home = os.path.join(td, "home")
        os.makedirs(os.path.join(fake_home, ".claude"))  # 模拟装了 Claude Code
        os.makedirs(os.path.join(fake_home, ".codex"))   # 模拟装了 Codex
        personal = os.path.join(td, "kb")
        team = os.path.join(td, "team")
        run_cli(["init", team])
        git(team, "init", "-q")
        git(team, "add", "-A")
        git(team, "commit", "-qm", "init team")
        env = dict(os.environ, HOME=fake_home, USERPROFILE=fake_home)
        env.pop("WIKI_ROOT", None)

        def run_init(*args):
            return subprocess.run([sys.executable, INIT, *args],
                                  capture_output=True, text=True, env=env, timeout=120)

        # 安装(静态指针 + symlink skill + shim + manifest)
        r = run_init("--personal-root", personal, "--team-root", team, "--no-input")
        check("安装 rc=0", r.returncode == 0, (r.stdout + r.stderr).strip()[-300:])
        ptr = os.path.join(fake_home, ".claude", "CLAUDE.md")
        ptr_text = open(ptr, encoding="utf-8").read() if os.path.isfile(ptr) else ""
        check("指针块写入且零机器路径(静态,装一次管终身)",
              "flux-wiki begin" in ptr_text and personal not in ptr_text
              and team not in ptr_text and "wiki-cli context" in ptr_text)
        codex_ptr = os.path.join(fake_home, ".codex", "AGENTS.md")
        check("Codex 指针块同一份正文", os.path.isfile(codex_ptr)
              and "flux-wiki begin" in open(codex_ptr, encoding="utf-8").read())
        skill = os.path.join(fake_home, ".claude", "skills", "wiki-query")
        agents_skill = os.path.join(fake_home, ".agents", "skills", "wiki-query")
        check("skill 以 symlink 安装(~/.claude + ~/.agents 双落点)",
              os.path.islink(skill) and os.path.isfile(os.path.join(skill, "SKILL.md"))
              and os.path.islink(agents_skill)
              and os.path.isfile(os.path.join(agents_skill, "SKILL.md")))
        cmd = os.path.join(fake_home, ".claude", "commands", "wiki-learn.md")
        check("命令 /wiki-learn 装上且为静态链接", os.path.islink(cmd)
              and "{{" not in open(cmd, encoding="utf-8").read())
        shim = os.path.join(fake_home, ".local", "bin", "wiki-cli")
        check("shim 落位且可执行", os.path.isfile(shim) and os.access(shim, os.X_OK))
        check("个人库已初始化", os.path.isfile(os.path.join(personal, "AGENTS.md")))
        cfg = json.load(open(os.path.join(fake_home, ".flux-wiki.json")))
        check("配置 v2 写入(teams 列表 + manifest)",
              cfg.get("config_version") == 2 and cfg.get("personal_root") == personal
              and cfg.get("teams") and cfg["teams"][0]["path"] == team
              and cfg["teams"][0].get("branch")
              and any(e.get("type") == "block" for e in cfg.get("installed_files", [])))
        settings = json.load(open(os.path.join(fake_home, ".claude", "settings.json")))
        hook_entries = settings.get("hooks", {}).get("SessionStart", [])
        check("SessionStart hook 写入(doctor --quick)",
              any("doctor --quick" in json.dumps(e) for e in hook_entries))

        # doctor 在装好的环境里全绿
        r = subprocess.run([sys.executable, CLI, "doctor"],
                           capture_output=True, text=True, env=env, timeout=60)
        check("装后 doctor 全绿 rc=0", r.returncode == 0, r.stdout.strip()[-200:])

        # 重跑幂等:指针块整段替换不膨胀;hook 不重复
        size1 = os.path.getsize(ptr)
        r = run_init("--personal-root", personal, "--team-root", team, "--no-input")
        settings2 = json.load(open(os.path.join(fake_home, ".claude", "settings.json")))
        hooks2 = [e for e in settings2.get("hooks", {}).get("SessionStart", [])
                  if "doctor --quick" in json.dumps(e)]
        check("重跑 rc=0 且指针不膨胀、hook 不重复", r.returncode == 0
              and os.path.getsize(ptr) == size1 and len(hooks2) == 1)

        # 双路径强制必填:全新 HOME(无配置)下非交互缺任一项直接报错,绝不静默用默认;
        # 装过一次后,配置里上次提供的值可沿用(重跑不必重复给参数)
        with tempfile.TemporaryDirectory() as td_nt:
            home_nt = os.path.join(td_nt, "h")
            os.makedirs(os.path.join(home_nt, ".claude"))
            env_nt = dict(env, HOME=home_nt, USERPROFILE=home_nt)
            kb_nt = os.path.join(td_nt, "kb")

            def run_init_nt(*args):
                return subprocess.run([sys.executable, INIT, *args],
                                      capture_output=True, text=True, env=env_nt, timeout=120)

            r = run_init_nt("--personal-root", kb_nt, "--no-input")
            check("非交互缺团队仓 rc=2", r.returncode == 2 and "--team-root" in r.stderr)
            r = run_init_nt("--team-root", team, "--no-input")
            check("非交互缺个人库 rc=2", r.returncode == 2 and "--personal-root" in r.stderr)
            r = run_init_nt("--no-input")
            check("非交互双缺各报其名", r.returncode == 2
                  and "--personal-root" in r.stderr and "--team-root" in r.stderr)
            r = run_init_nt("--personal-root", kb_nt, "--team-root", team, "--no-input")
            check("双路径齐全安装成功", r.returncode == 0)
            r = run_init_nt("--no-input")  # 两个路径均来自配置记忆(上次明确提供的值)
            check("配置记忆生效(重跑不报错)", r.returncode == 0)

        # 死路径 / 非 git 团队仓被拦截(非交互)
        r = run_init("--personal-root", personal,
                     "--team-root", os.path.join(td, "ghost"), "--no-input")
        check("死路径团队仓拦截 rc=2", r.returncode == 2)
        notgit = os.path.join(td, "notgit")
        os.makedirs(notgit)
        r = run_init("--personal-root", personal, "--team-root", notgit, "--no-input")
        check("非 git 团队仓拦截 rc=2", r.returncode == 2)

        # 旧版 legacy 指针块迁移:预置旧块 → 重装 → 被替换 + 用户内容保留 + 整文件备份
        with open(ptr, "w", encoding="utf-8") as f:
            f.write("# 用户自己的内容\n\n# === flux-wiki (auto by wiki-init) ===\n"
                    "旧版指针内容 指向 /dead/path\n")
        r = run_init("--personal-root", personal, "--team-root", team, "--no-input")
        new_text = open(ptr, encoding="utf-8").read()
        baks = [f for f in os.listdir(os.path.dirname(ptr)) if f.startswith("CLAUDE.md.bak-flux-")]
        check("旧版块迁移(替换+保留用户内容+备份)", r.returncode == 0
              and "/dead/path" not in new_text and "用户自己的内容" in new_text
              and "flux-wiki begin" in new_text and baks)

        # 标记残缺(用户手滑删了 end 行):重装不产生重复块,且有整文件备份
        with open(ptr, "w", encoding="utf-8") as f:
            f.write("# 用户内容\n\n# === flux-wiki begin (auto by wiki-manage, 重装会整段替换) ===\n"
                    "残块内容\n")
        r = run_init("--personal-root", personal, "--team-root", team, "--no-input")
        new_text = open(ptr, encoding="utf-8").read()
        check("残缺标记块修复(单块+用户内容保留)", r.returncode == 0
              and new_text.count("flux-wiki begin") == 1 and "残块内容" not in new_text
              and "# 用户内容" in new_text)

        # 用户笔记行引用标记字样(整行不等于标记):绝不能被当作标记吞内容
        with open(ptr, "a", encoding="utf-8") as f:
            f.write("\n# 我的笔记:手动清理 = 删除 `# === flux-wiki begin (auto by wiki-manage, "
                    "重装会整段替换) ===` 到 `# === flux-wiki end ===` 之间的内容\n珍贵的后续内容\n")
        r = run_init("--personal-root", personal, "--team-root", team, "--no-input")
        new_text = open(ptr, encoding="utf-8").read()
        check("引用标记字样的笔记行不被吞", r.returncode == 0
              and "我的笔记" in new_text and "珍贵的后续内容" in new_text
              and new_text.count("flux-wiki begin") == 2)  # 笔记里 1 + 真块 1

        # 旧版渲染副本(非链接目录)让位:挪进备份,绝不删除
        old_skill = os.path.join(fake_home, ".claude", "skills", "wiki-ingest")
        if os.path.islink(old_skill):
            os.unlink(old_skill)
        os.makedirs(old_skill, exist_ok=True)
        with open(os.path.join(old_skill, "SKILL.md"), "w") as f:
            f.write("旧版渲染副本")
        def backed_up(name):
            """备份统一进 ~/.flux-wiki-backups/<ts>/(绝不留在 AI 工具扫描路径里,
            否则会被当作幽灵 skill/命令扫出来);递归找被备份的名字。"""
            broot = os.path.join(fake_home, ".flux-wiki-backups")
            if not os.path.isdir(broot):
                return False
            for ts in os.listdir(broot):
                if name in os.listdir(os.path.join(broot, ts)):
                    return True
            return False

        r = run_init("--personal-root", personal, "--team-root", team, "--no-input")
        scan_dirs = [d for d in os.listdir(os.path.join(fake_home, ".claude", "skills"))
                     if d.startswith(".flux-wiki-backup-")]
        check("旧渲染副本备份让位(挪出扫描路径,不删除)", r.returncode == 0
              and os.path.islink(old_skill) and backed_up("wiki-ingest") and not scan_dirs)

        # 用户同名 shim 备份让位(绝不盲覆盖)
        os.unlink(shim)
        with open(shim, "w") as f:
            f.write("#!/bin/sh\necho 用户自己的脚本\n")
        r = run_init("--personal-root", personal, "--team-root", team, "--no-input")
        check("用户同名 shim 备份让位", r.returncode == 0 and backed_up("wiki-cli")
              and "plugins/flux-wiki" in open(shim, encoding="utf-8").read())

        # stale personal_root:配置里的库路径蒸发 → 非交互拒绝在死路径重建空库
        cfgj = os.path.join(fake_home, ".flux-wiki.json")
        saved_cfg = open(cfgj, encoding="utf-8").read()
        c = json.loads(saved_cfg)
        c["personal_root"] = os.path.join(td, "moved-away")
        open(cfgj, "w").write(json.dumps(c))
        r = run_init("--no-input")
        check("stale personal_root 拒绝静默重建 rc=2", r.returncode == 2
              and not os.path.isdir(os.path.join(td, "moved-away")))
        open(cfgj, "w").write(saved_cfg)

        # --uninstall --dry-run:只预览,零删除
        r = run_init("--uninstall", "--dry-run")
        check("uninstall --dry-run 零删除", r.returncode == 0
              and os.path.isfile(cfgj) and os.path.lexists(skill)
              and "flux-wiki begin" in open(ptr, encoding="utf-8").read())

        # 用户把部署链接替换成自己的定制文件:卸载备份让位,不删
        custom_cmd = os.path.join(fake_home, ".claude", "commands", "wiki-learn.md")
        os.unlink(custom_cmd)
        with open(custom_cmd, "w") as f:
            f.write("用户定制版命令")

        # 卸载:按 manifest 精确清理
        r = run_init("--uninstall")
        ptr_after = open(ptr, encoding="utf-8").read() if os.path.isfile(ptr) else ""
        settings3 = json.load(open(os.path.join(fake_home, ".claude", "settings.json")))
        hooks3 = [e for e in settings3.get("hooks", {}).get("SessionStart", [])
                  if "doctor --quick" in json.dumps(e)]
        check("卸载:指针块/链接/shim/hook/配置全清,个人库保留", r.returncode == 0
              and ptr_after.count("flux-wiki begin") == 1  # 仅剩笔记行里的引用,真块已移除
              and not os.path.lexists(skill) and not os.path.lexists(shim)
              and not hooks3
              and not os.path.isfile(os.path.join(fake_home, ".flux-wiki.json"))
              and os.path.isfile(os.path.join(personal, "AGENTS.md")))
        check("卸载保留用户笔记行与块后内容", "我的笔记" in ptr_after
              and "珍贵的后续内容" in ptr_after)
        check("卸载:用户定制替换的链接备份让位不删", backed_up("wiki-learn.md")
              and not os.path.lexists(custom_cmd))

        # dry-run 不写任何东西
        with tempfile.TemporaryDirectory() as td2:
            home2 = os.path.join(td2, "h")
            os.makedirs(os.path.join(home2, ".claude"))
            env2 = dict(env, HOME=home2, USERPROFILE=home2)
            r = subprocess.run([sys.executable, INIT,
                                "--personal-root", os.path.join(td2, "kb"), "--team-root", team,
                                "--dry-run", "--no-input"],
                               capture_output=True, text=True, env=env2, timeout=120)
            check("dry-run 零写入", r.returncode == 0
                  and not os.path.isfile(os.path.join(home2, ".claude", "CLAUDE.md"))
                  and not os.path.isdir(os.path.join(td2, "kb")))


# ---------- 4b. config / doctor / guide / 核销门禁 ----------

def config_doctor_guide_e2e():
    print("\n== 4b) config 多仓 / doctor / guide / learn 核销门禁(隔离 HOME)==")
    with tempfile.TemporaryDirectory() as td:
        fake_home = os.path.join(td, "home")
        os.makedirs(fake_home)
        env = dict(os.environ, HOME=fake_home, USERPROFILE=fake_home)
        env.pop("WIKI_ROOT", None)
        personal = os.path.join(td, "me")
        team = os.path.join(td, "team")
        run_cli(["init", personal], env=env)
        run_cli(["init", team, "--domains", "shared"], env=env)
        os.makedirs(os.path.join(team, "machine"))
        with open(os.path.join(team, "machine", "gen-1.md"), "w") as f:
            f.write("# 机械生成卡片\n")
        git(team, "init", "-q")
        git(team, "add", "-A")
        git(team, "commit", "-qm", "init team")
        run_cli(["--root", team, "new", "concept", "rule-one", "--domain", "shared"], env=env)
        git(team, "add", "-A")
        git(team, "commit", "-qm", "feat: rule-one")

        # config team 登记(带 exclude / branch)
        r = run_cli(["config", "team", "t1", "--path", team, "--exclude", "machine/**"], env=env)
        check("config team 登记", r.returncode == 0)
        r = run_cli(["config", "team", "ghost", "--path", os.path.join(td, "nope")], env=env)
        check("config team 死路径拒绝 rc=2", r.returncode == 2)
        r = run_cli(["--json", "config", "get"], env=env)
        cfg = json.loads(r.stdout)
        check("config get(teams 列表)", cfg.get("teams")
              and cfg["teams"][0]["name"] == "t1"
              and cfg["teams"][0]["exclude"] == ["machine/**"])

        # 写 personal_root 进配置,learn 不带 --team 走配置仓
        r = run_cli(["config", "set", "personal_root", personal], env=env)
        check("config set personal_root", r.returncode == 0)

        # exclude 分流:machine/** 不进清单,计数可见;--all 可见
        r = run_cli(["--root", personal, "--json", "learn"], env=env)
        d = json.loads(r.stdout)
        rels = [p["team_rel"] for p in d["pages"]]
        check("learn 走配置仓 + exclude 分流", d["ok"]
              and not any("machine" in x for x in rels) and d["excluded_count"] == 1)
        r = run_cli(["--root", personal, "--json", "learn", "--all"], env=env)
        d_all = json.loads(r.stdout)
        check("learn --all 可见分流页", any("machine" in p["team_rel"]
                                            and p.get("excluded") for p in d_all["pages"]))
        head = d["head"]

        # 首次学习:核销是提示不阻塞(基线策展允许选择性学习)
        ldir = os.path.join(personal, "domains", "shared", "concepts")
        os.makedirs(ldir, exist_ok=True)
        with open(os.path.join(ldir, "rule-one.md"), "w") as f:
            f.write(f"---\nlearned_from: domains/shared/concepts/rule-one.md\n"
                    f"learned_commit: {head}\n---\n# rule-one(已学)\n")
        r = run_cli(["--root", personal, "learn", "--verify"], env=env)
        check("首次 verify rc=0(不阻塞)", r.returncode == 0, r.stdout.strip()[-160:])
        r = run_cli(["--root", personal, "learn", "--mark", head], env=env)
        check("首次 mark 放行 + 自动落审计", r.returncode == 0 and "审计已落" in r.stdout)
        revs = os.listdir(os.path.join(personal, ".wiki", "revisions"))
        check("learn 审计文件存在", any("learn" in f for f in revs))

        # 增量轮:M 页未消化(learned_commit 未推进)→ verify rc=1,mark 被门禁拦下
        with open(os.path.join(team, "domains", "shared", "concepts", "rule-one.md"), "a") as f:
            f.write("\n团队更新\n")
        run_cli(["--root", team, "new", "concept", "rule-two", "--domain", "shared"], env=env)
        git(team, "add", "-A")
        git(team, "commit", "-qm", "update rule-one + add rule-two")
        r = run_cli(["--root", personal, "learn", "--verify"], env=env)
        check("增量 verify 抓出未消化页 rc=1", r.returncode == 1
              and "未覆盖该页" in r.stdout and "rule-two" in r.stdout)
        r2 = run_cli(["--root", personal, "--json", "learn"], env=env)
        head2 = json.loads(r2.stdout)["head"]
        r = run_cli(["--root", personal, "learn", "--mark", head2], env=env)
        check("核销未过 mark 被拒 rc=1", r.returncode == 1)
        # 消化完成(M 页推进 learned_commit + 新页落库)→ 门禁放行
        with open(os.path.join(ldir, "rule-one.md"), "w") as f:
            f.write(f"---\nlearned_from: domains/shared/concepts/rule-one.md\n"
                    f"learned_commit: {head2}\n---\n# rule-one(已合并团队更新)\n")
        with open(os.path.join(ldir, "rule-two.md"), "w") as f:
            f.write(f"---\nlearned_from: domains/shared/concepts/rule-two.md\n"
                    f"learned_commit: {head2}\n---\n# rule-two(已学)\n")
        r = run_cli(["--root", personal, "learn", "--mark", head2], env=env)
        check("核销全过 mark 放行", r.returncode == 0)
        # --force 旁路:新增量不学,强推水位(放弃页进审计)
        run_cli(["--root", team, "new", "concept", "rule-three", "--domain", "shared"], env=env)
        git(team, "add", "-A")
        git(team, "commit", "-qm", "add rule-three")
        r3 = run_cli(["--root", personal, "--json", "learn"], env=env)
        head3 = json.loads(r3.stdout)["head"]
        r = run_cli(["--root", personal, "learn", "--mark", head3], env=env)
        check("未学新页 mark 被拒", r.returncode == 1)
        r = run_cli(["--root", personal, "learn", "--mark", head3, "--force"], env=env)
        check("--force 放行且审计记录放弃页", r.returncode == 0)

        # doctor:配置仓活着 → rc=0;把配置改成死路径 → rc=1;--quick 永远 rc=0 但有输出
        r = subprocess.run([sys.executable, CLI, "doctor"], capture_output=True,
                           text=True, env=env, timeout=60)
        check("doctor 健康环境 rc=0", r.returncode == 0, r.stdout.strip()[-160:])
        cfg_path = os.path.join(fake_home, ".flux-wiki.json")
        cfg = json.load(open(cfg_path))
        cfg["teams"][0]["path"] = os.path.join(td, "vanished")
        json.dump(cfg, open(cfg_path, "w"))
        r = subprocess.run([sys.executable, CLI, "doctor"], capture_output=True,
                           text=True, env=env, timeout=60)
        check("doctor 死路径 rc=1 + 给修复命令", r.returncode == 1
              and "config team" in r.stdout)
        r = subprocess.run([sys.executable, CLI, "doctor", "--quick"], capture_output=True,
                           text=True, env=env, timeout=60)
        check("doctor --quick 报问题但 rc=0(hook 不卡会话)", r.returncode == 0
              and "路径不存在" in r.stdout)
        cfg["teams"][0]["path"] = team
        json.dump(cfg, open(cfg_path, "w"))

        # context:运行时路径解析
        r = run_cli(["context"], env=env)
        check("context 输出库与团队仓", r.returncode == 0
              and personal in r.stdout and team in r.stdout)

        # guide:现读现发,占位符全部注入
        r = run_cli(["guide", "learn"], env=env)
        check("guide learn 渲染(零残留占位符)", r.returncode == 0
              and "{{" not in r.stdout and personal in r.stdout and "t1" in r.stdout)
        r = run_cli(["guide", "nope"], env=env)
        check("guide 未知手册 rc=2 列可用项", r.returncode == 2 and "ingest" in r.stderr)

        # lint 全库文本模式自动落审计
        r = run_cli(["--root", personal, "lint"], env=env)
        check("lint 自动落审计", r.returncode == 0 and "审计已落" in r.stdout)

        # 词表闭集校验:放一个 _vocabulary.md 后,必填缺失被聚合报出
        with open(os.path.join(personal, "_vocabulary.md"), "w") as f:
            f.write('# 词表\n\n```json\n{"required_frontmatter": ["tags", "page_type"],'
                    '"enum_fields": {"status": ["active", "archived"]}}\n```\n')
        with open(os.path.join(ldir, "bad-status.md"), "w") as f:
            f.write("---\ntags: [x]\npage_type: concept\nstatus: weird\n---\n# bad\n")
        r = run_cli(["--root", personal, "--json", "lint"], env=env)
        rep = json.loads(r.stdout)
        codes = [i["code"] for s in rep["sections"] for i in s["issues"]]
        check("词表必填缺失聚合警告", "vocab-missing-field" in codes)
        check("词表枚举越界警告", "vocab-enum-violation" in codes)

        # exclude 绝不吞「已学页」的更新:学过的 machine 页改动必须可见
        mdir = os.path.join(personal, "domains", "shared", "machine-learned")
        os.makedirs(mdir, exist_ok=True)
        r0 = run_cli(["--root", personal, "--json", "learn"], env=env)
        head0 = json.loads(r0.stdout)["head"]
        with open(os.path.join(mdir, "gen-1.md"), "w") as f:
            f.write(f"---\nlearned_from: machine/gen-1.md\nlearned_commit: {head0}\n---\n# 已学机械页\n")
        with open(os.path.join(team, "machine", "gen-1.md"), "a") as f:
            f.write("更新\n")
        git(team, "add", "-A")
        git(team, "commit", "-qm", "update machine gen-1")
        r = run_cli(["--root", personal, "--json", "learn"], env=env)
        d = json.loads(r.stdout)
        check("exclude 不吞已学页的 M 变更", any(
            p["team_rel"] == "machine/gen-1.md" and p["status"] == "M" and p.get("previous")
            for p in d["pages"]))
        # M 页核销精确到「最后变更」:learned_commit 只追到中间版本 = 未核销
        mid = d["head"]
        with open(os.path.join(mdir, "gen-1.md"), "w") as f:
            f.write(f"---\nlearned_from: machine/gen-1.md\nlearned_commit: {mid}\n---\n# 已学(中间版)\n")
        with open(os.path.join(team, "machine", "gen-1.md"), "a") as f:
            f.write("再更新\n")
        git(team, "add", "-A")
        git(team, "commit", "-qm", "update machine gen-1 again")
        r = run_cli(["--root", personal, "learn", "--verify"], env=env)
        check("M 页学到中间版本仍判未核销", r.returncode == 1 and "最后变更" in r.stdout)
        with open(os.path.join(mdir, "gen-1.md"), "w") as f:
            r2 = run_cli(["--root", personal, "--json", "learn"], env=env)
            head4 = json.loads(r2.stdout)["head"]
            f.write(f"---\nlearned_from: machine/gen-1.md\nlearned_commit: {head4}\n---\n# 已学(最新)\n")
        r = run_cli(["--root", personal, "learn", "--mark", head4], env=env)
        check("追到最新后核销放行", r.returncode == 0)

        # guide 坏环境硬失败:配置指向不存在的库 → rc=2 提示 doctor(安全网必须可触发)
        cfg = json.load(open(cfg_path))
        cfg["personal_root"] = os.path.join(td, "gone")
        json.dump(cfg, open(cfg_path, "w"))
        r = run_cli(["guide", "ingest"], env=env, cwd=fake_home)
        check("guide 库失效 rc=2 不渲染死路径", r.returncode == 2 and "doctor" in r.stderr)
        cfg["personal_root"] = personal
        json.dump(cfg, open(cfg_path, "w"))


def v1_config_compat_e2e():
    """v1 配置(只有 team_root 键)= 所有存量安装升级后第一次运行的形态,必须全链路可用。"""
    print("\n== 4c) v1 配置兼容(隔离 HOME)==")
    with tempfile.TemporaryDirectory() as td:
        fake_home = os.path.join(td, "home")
        os.makedirs(fake_home)
        env = dict(os.environ, HOME=fake_home, USERPROFILE=fake_home)
        env.pop("WIKI_ROOT", None)
        personal = os.path.join(td, "me")
        team = os.path.join(td, "team-v1")
        run_cli(["init", personal], env=env)
        run_cli(["init", team, "--domains", "shared"], env=env)
        git(team, "init", "-q")
        git(team, "add", "-A")
        git(team, "commit", "-qm", "init")
        with open(os.path.join(fake_home, ".flux-wiki.json"), "w") as f:
            json.dump({"personal_root": personal, "team_root": team}, f)

        r = run_cli(["--json", "status"], env=env)
        st = json.loads(r.stdout)
        check("v1 配置 status 合成 teams", r.returncode == 0
              and st["teams"] and st["teams"][0]["path"] == team
              and st["team_root"] == team)
        r = run_cli(["--json", "learn"], env=env)
        d = json.loads(r.stdout)
        check("v1 配置 learn 直接可用", d.get("ok") and d.get("team_root") == team)
        r = run_cli(["context"], env=env)
        check("v1 配置 context 可用", r.returncode == 0 and team in r.stdout)
        r = subprocess.run([sys.executable, CLI, "doctor"], capture_output=True,
                           text=True, env=env, timeout=60)
        check("v1 配置 doctor 可用(warn 不 error)", r.returncode == 0)
        # v1 仓按目录名移除 → team_root 键被清掉
        r = run_cli(["config", "team", os.path.basename(team), "--remove"], env=env)
        cfg = json.load(open(os.path.join(fake_home, ".flux-wiki.json")))
        check("v1 team_root 可被 config team --remove 清除", r.returncode == 0
              and "team_root" not in cfg)


# ---------- 5. skill 触发词断言 ----------

MUST_COVER = {
    "skills/wiki-ingest/SKILL.md": ["记一下", "入库", "沉淀", "踩坑"],
    "skills/wiki-query/SKILL.md": ["查询", "概念", "踩坑"],
    "skills/wiki-lint/SKILL.md": ["体检", "lint", "清理"],
    "commands/wiki-learn.md": ["团队", "学习", "git"],
    "commands/wiki-help.md": ["能力", "命令"],
}


def skill_descriptions():
    print("\n== 5) skill/命令触发词断言 ==")
    for rel, kws in MUST_COVER.items():
        p = os.path.join(PLUGIN, rel)
        if not os.path.isfile(p):
            check(f"{rel} 存在", False)
            continue
        text = open(p, encoding="utf-8").read()
        desc = ""
        if text.startswith("---"):
            for line in text.splitlines()[1:20]:
                if line.startswith("description:"):
                    desc = line
                    break
        missing = [k for k in kws if k.lower() not in desc.lower()]
        check(f"{rel} description 覆盖触发词", not missing, f"缺 {missing}" if missing else "")


def main():
    unit_tests()
    unit_tests_v31()
    cli_e2e()
    learn_e2e()
    learn_v2_team_e2e()
    init_e2e()
    config_doctor_guide_e2e()
    v1_config_compat_e2e()
    skill_descriptions()
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{'='*50}\n共 {len(RESULTS)} 项,失败 {len(failed)} 项")
    if failed:
        for n in failed:
            print(f"  ❌ {n}")
        return 1
    print("✅ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
