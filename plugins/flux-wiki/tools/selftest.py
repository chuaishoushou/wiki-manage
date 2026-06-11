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


# ---------- 3. learn 端到端 ----------

def learn_e2e():
    print("\n== 3) learn 端到端(git fixture)==")
    with tempfile.TemporaryDirectory() as td:
        personal = os.path.join(td, "me")
        team = os.path.join(td, "team")
        run_cli(["init", personal])
        run_cli(["init", team, "--domains", "shared"])
        git(team, "init", "-q")
        git(team, "add", "-A")
        git(team, "commit", "-qm", "init team wiki")
        run_cli(["--root", team, "new", "concept", "rule-one", "--domain", "shared"])
        git(team, "add", "-A")
        git(team, "commit", "-qm", "feat: rule-one")

        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        check("learn 首学列知识页(不含协议文件)", d["ok"] and d["first_time"]
              and any(p["team_rel"].endswith("rule-one.md") for p in d["pages"])
              and not any(p["team_rel"] == "AGENTS.md" for p in d["pages"]))
        head = d["head"]

        # 模拟 AI 学习落盘(带溯源)
        learned_dir = os.path.join(personal, "domains", "shared", "concepts")
        os.makedirs(learned_dir, exist_ok=True)
        with open(os.path.join(learned_dir, "rule-one.md"), "w") as f:
            f.write(f"---\nlearned_from: domains/shared/concepts/rule-one.md\n"
                    f"learned_commit: {head}\n---\n# rule-one(已学)\n")
        r = run_cli(["--root", personal, "learn", "--team", team, "--mark", head])
        check("learn --mark", r.returncode == 0)

        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        check("学完无增量 up_to_date", d["ok"] and d["up_to_date"])

        run_cli(["--root", team, "new", "concept", "rule-two", "--domain", "shared"])
        # 同时改 rule-one,验证 previous 逆查
        with open(os.path.join(team, "domains", "shared", "concepts", "rule-one.md"), "a") as f:
            f.write("\n更新内容\n")
        git(team, "add", "-A")
        git(team, "commit", "-qm", "feat: rule-two + 更新 rule-one")
        r = run_cli(["--root", personal, "--json", "learn", "--team", team])
        d = json.loads(r.stdout)
        one = next((p for p in d["pages"] if p["team_rel"].endswith("rule-one.md")), None)
        two = next((p for p in d["pages"] if p["team_rel"].endswith("rule-two.md")), None)
        check("增量只列变化页", d["ok"] and not d["first_time"] and len(d["pages"]) == 2)
        check("已学页带 previous 落点", one and one["previous"]
              and one["previous"].endswith("rule-one.md"))
        check("新页 previous 为空", two and not two["previous"])
        check("附期间提交标题", any("rule-two" in c for c in d["commits"]))


# ---------- 4. wiki-init 端到端(隔离 HOME)----------

def init_e2e():
    print("\n== 4) wiki-init 端到端(隔离 HOME,不碰真实用户目录)==")
    with tempfile.TemporaryDirectory() as td:
        fake_home = os.path.join(td, "home")
        os.makedirs(os.path.join(fake_home, ".claude"))  # 模拟装了 Claude Code
        personal = os.path.join(td, "kb")
        team = os.path.join(td, "team")
        run_cli(["init", team])
        env = dict(os.environ, HOME=fake_home, USERPROFILE=fake_home)
        env.pop("WIKI_ROOT", None)

        def run_init(*args):
            return subprocess.run([sys.executable, INIT, *args],
                                  capture_output=True, text=True, env=env, timeout=120)

        # 装 cc(带团队仓)
        r = run_init("--platform", "cc", "--personal-root", personal,
                     "--team-root", team, "--no-input")
        check("安装 rc=0", r.returncode == 0, (r.stdout + r.stderr).strip()[-200:])
        ptr = os.path.join(fake_home, ".claude", "CLAUDE.md")
        ptr_text = open(ptr, encoding="utf-8").read() if os.path.isfile(ptr) else ""
        check("指针块写入", "flux-wiki begin" in ptr_text and personal in ptr_text)
        skill = os.path.join(fake_home, ".claude", "skills", "wiki-query", "SKILL.md")
        cmd = os.path.join(fake_home, ".claude", "commands", "wiki-learn.md")
        check("skill 渲染复制(非软链,无占位符)",
              os.path.isfile(skill) and not os.path.islink(os.path.dirname(skill))
              and "{{" not in open(skill, encoding="utf-8").read())
        check("命令 /wiki-learn 装上且渲染", os.path.isfile(cmd)
              and "{{" not in open(cmd, encoding="utf-8").read()
              and team in open(cmd, encoding="utf-8").read())
        check("个人库已初始化", os.path.isfile(os.path.join(personal, "AGENTS.md")))
        cfg = json.load(open(os.path.join(fake_home, ".flux-wiki.json")))
        check("配置写入", cfg.get("personal_root") == personal and cfg.get("team_root") == team)

        # 重跑幂等:指针块整段替换,文件不膨胀
        size1 = os.path.getsize(ptr)
        r = run_init("--platform", "cc", "--personal-root", personal,
                     "--team-root", team, "--no-input")
        check("重跑 rc=0 且指针不膨胀", r.returncode == 0
              and os.path.getsize(ptr) == size1)

        # 双路径强制必填:全新 HOME(无配置)下非交互缺任一项直接报错,绝不静默用默认;
        # 装过一次后,配置里上次提供的值可沿用(重跑不必重复给参数)
        with tempfile.TemporaryDirectory() as td_nt:
            home_nt = os.path.join(td_nt, "h")
            os.makedirs(os.path.join(home_nt, ".claude"))
            env_nt = dict(env, HOME=home_nt, USERPROFILE=home_nt)
            kb_nt = os.path.join(td_nt, "kb")

            def run_init_nt(*args):
                return subprocess.run([sys.executable, INIT, "--platform", "cc", *args],
                                      capture_output=True, text=True, env=env_nt, timeout=120)

            r = run_init_nt("--personal-root", kb_nt, "--no-input")
            check("非交互缺团队仓 rc=2", r.returncode == 2 and "--team-root" in r.stderr)
            r = run_init_nt("--team-root", team, "--no-input")
            check("非交互缺个人库 rc=2", r.returncode == 2 and "--personal-root" in r.stderr)
            r = run_init_nt("--no-input")
            check("非交互双缺各报其名", r.returncode == 2
                  and "--personal-root" in r.stderr and "--team-root" in r.stderr)
            r = run_init_nt("--personal-root", kb_nt, "--team-root", team, "--no-input")
            ptr_nt = os.path.join(home_nt, ".claude", "CLAUDE.md")
            check("双路径齐全安装成功", r.returncode == 0
                  and team in open(ptr_nt, encoding="utf-8").read())
            r = run_init_nt("--no-input")  # 两个路径均来自配置记忆(上次明确提供的值)
            check("配置记忆生效(重跑不报错)", r.returncode == 0)

        # 死路径团队仓被拦截(非交互)
        r = run_init("--platform", "cc", "--personal-root", personal,
                     "--team-root", os.path.join(td, "ghost"), "--no-input")
        check("死路径团队仓拦截 rc=2", r.returncode == 2)

        # 旧版 legacy 指针块迁移:预置旧块 → 重装 → 被替换 + 有备份
        with open(ptr, "w", encoding="utf-8") as f:
            f.write("# 用户自己的内容\n\n# === flux-wiki (auto by wiki-init) ===\n"
                    "旧版指针内容 指向 /dead/path\n")
        r = run_init("--platform", "cc", "--personal-root", personal,
                     "--team-root", team, "--no-input")
        new_text = open(ptr, encoding="utf-8").read()
        baks = [f for f in os.listdir(os.path.dirname(ptr)) if f.startswith("CLAUDE.md.bak-flux-")]
        check("旧版块迁移(替换+保留用户内容+备份)", r.returncode == 0
              and "/dead/path" not in new_text and "用户自己的内容" in new_text
              and "flux-wiki begin" in new_text and baks)

        # dry-run 不写任何东西
        with tempfile.TemporaryDirectory() as td2:
            home2 = os.path.join(td2, "h")
            os.makedirs(os.path.join(home2, ".claude"))
            env2 = dict(env, HOME=home2, USERPROFILE=home2)
            r = subprocess.run([sys.executable, INIT, "--platform", "cc",
                                "--personal-root", os.path.join(td2, "kb"), "--team-root", team,
                                "--dry-run", "--no-input"],
                               capture_output=True, text=True, env=env2, timeout=120)
            check("dry-run 零写入", r.returncode == 0
                  and not os.path.isfile(os.path.join(home2, ".claude", "CLAUDE.md"))
                  and not os.path.isdir(os.path.join(td2, "kb")))


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
    cli_e2e()
    learn_e2e()
    init_e2e()
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
