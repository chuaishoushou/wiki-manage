#!/usr/bin/env python3
"""确定性触发回归(代理):校验每个 skill 的 description 覆盖其 must_cover 触发词。

真正的 LLM 触发命中率需用 Claude Code eval 工具或人工核对 triggers.json 的
should_trigger / should_not_trigger 用例。本脚本只做一件确定性的事:防止有人改
SKILL.md description 时漏掉关键触发词,导致 skill 在该场景不再被自动选中。

用法:python3 evals/check_descriptions.py   # 退出码 0=全覆盖,1=有缺失
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
SKILLS_DIR = os.path.join(PLUGIN, "skills")


def _read_description(skill_name):
    p = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        text = f.read()
    # 取 frontmatter 里的 description 行(可能为多行,简单取到下一个顶层 key 前)
    desc = ""
    in_fm = False
    for line in text.splitlines():
        if line.strip() == "---":
            if in_fm:
                break
            in_fm = True
            continue
        if in_fm and line.startswith("description:"):
            desc = line.split(":", 1)[1].strip()
    return desc


def main():
    with open(os.path.join(HERE, "triggers.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
    failures = []
    for case in data["skills"]:
        name = case["skill"]
        desc = _read_description(name)
        if desc is None:
            failures.append((name, "SKILL.md 不存在"))
            continue
        missing = [kw for kw in case["must_cover"] if kw.lower() not in desc.lower()]
        if missing:
            failures.append((name, f"description 未覆盖触发词: {missing}"))
        else:
            print(f"✅ {name}: description 覆盖全部 must_cover")
    if failures:
        print("\n❌ 触发词覆盖回归失败:")
        for n, why in failures:
            print(f"  - {n}: {why}")
        return 1
    print("\n✅ 全部 skill description 覆盖其触发词")
    return 0


if __name__ == "__main__":
    sys.exit(main())
