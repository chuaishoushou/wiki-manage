"""publish:团队仓脱敏白名单导出。

只导出 `sensitivity <= publish_max`(默认 team)且非 `publish:false` 域的知识页,
外加结构/协议文件(AGENTS.md / _routes.md / _vocabulary.md / overview.md)。
命中敏感但声明不足的页会阻断导出(除非 --force)。

★ 含写副作用(复制文件)→ 是独立写子命令,只读检索/校验子命令【绝不】含写副作用(守只读不变量 1)。
设计依据:spec § 3.1「团队仓发布 = 白名单导出,绝不 git push 整库」。
"""
from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Tuple

from . import frontmatter, repo, sensitivity
from .vocabulary import Vocabulary

# 始终随团队仓发布的结构/协议文件(根级,非知识内容,不走敏感度白名单)
INFRA_FILES = ("AGENTS.md", "_routes.md", "_vocabulary.md", "overview.md")


def plan(root: str, vocab: Vocabulary, include_archive: bool = False) -> Dict[str, Any]:
    """规划导出:返回 included / excluded / risky,不写盘。"""
    included: List[str] = []
    excluded: List[Tuple[str, str]] = []
    risky: List[str] = []
    pub_max_rank = sensitivity._RANK.get(vocab.publish_max, 1)

    for path in repo.iter_pages(root, include_archive=include_archive):
        meta, _, _ = frontmatter.read_page(path)
        rel = repo.rel_path(root, path)
        declared = meta.get("sensitivity", "")
        domain = meta.get("domain", "")
        dom = vocab.domain(domain) if domain else None

        scan = sensitivity.scan_page(path, vocab, root)
        if scan["any_hit"] and (scan["under_declared"] or not declared):
            risky.append(rel)

        if dom and dom.get("publish") is False:
            excluded.append((rel, f"publish:false 域({domain})"))
            continue
        if not declared:
            excluded.append((rel, "无 sensitivity 声明"))
            continue
        if sensitivity._RANK.get(declared, 99) > pub_max_rank:
            excluded.append((rel, f"sensitivity={declared} > 上限 {vocab.publish_max}"))
            continue
        included.append(rel)

    return {"included": included, "excluded": excluded, "risky": risky}


def export(root: str, out_dir: str, vocab: Vocabulary, include_archive: bool = False,
           force: bool = False) -> Dict[str, Any]:
    """执行导出。存在 risky 且未 --force 时拒绝(返回 ok=False,不写盘)。"""
    p = plan(root, vocab, include_archive=include_archive)
    if p["risky"] and not force:
        return {"ok": False,
                "reason": f"{len(p['risky'])} 个页命中敏感且声明不足,先裁定 sensitivity 或加 --force",
                **p}

    out_dir = os.path.abspath(os.path.expanduser(out_dir))
    copied = 0
    for rel in p["included"]:
        src = os.path.join(root, rel)
        dst = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    infra_copied = []
    for name in INFRA_FILES:
        src = os.path.join(root, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(out_dir, name))
            infra_copied.append(name)

    return {"ok": True, "out": out_dir, "copied": copied, "infra": infra_copied, **p}
