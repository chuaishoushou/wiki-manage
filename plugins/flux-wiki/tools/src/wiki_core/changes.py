"""changes:基于 git 提交记录,把"团队仓有哪些待更新知识"翻成知识感知的清单。

核心理念(见 docs/repos-model.md):**git 提交记录就是每条知识的状态库**,
不另造同步状态机。本模块只是 `git fetch + diff HEAD..@{u}` 的知识感知包装:
- 颗粒度:文件 = 一条知识;目录 = 一个模块。
- 区分"大模块更新 vs 单条小更新":看变更文件落在哪、几个。
- 只读:fetch 只更新引用,不动工作区、不合并。应用更新永远是用户手动 /wiki-sync(git pull)。
"""
from __future__ import annotations

from typing import Any, Dict

from . import repo

_KIND_LABEL = {"module": "模块", "concept": "概念", "entity": "实体",
               "query": "问答", "source": "源", "file": "文件"}
_TYPE_DIRS = {"concepts": "concept", "entities": "entity", "queries": "query", "sources": "source"}


def classify(rel: str):
    """把一个变更文件路径归类到 (kind, name)。纯函数,便于测试。"""
    parts = rel.replace("\\", "/").split("/")
    # 模块:.../domains/<d>/modules/<id>/...
    if "modules" in parts:
        i = parts.index("modules")
        if i + 1 < len(parts):
            dom = parts[parts.index("domains") + 1] if "domains" in parts else "?"
            return "module", f"{dom}/{parts[i + 1]}"
    # 分类页:.../<types>/<slug>.md
    for dir_name, t in _TYPE_DIRS.items():
        if dir_name in parts:
            return t, "/".join(parts)
    return "file", "/".join(parts)


def incoming(root: str, do_fetch: bool = True) -> Dict[str, Any]:
    """返回"待更新知识"报告(只读)。"""
    branch, commit = repo.git_head_info(root)
    fetched = False
    note = ""
    if do_fetch:
        ok, msg = repo.git_fetch(root)
        fetched = ok
        if not ok:
            note = f"fetch 失败({msg}),结果基于上次同步,可能不是最新"

    inc = repo.git_incoming(root)
    if inc is None:
        reason = ("非 git 仓 / 无 upstream 跟踪分支(团队仓还没 push?或本地不是 clone)。"
                  "若当前 WIKI_ROOT 是个人库,看团队更新请改用 "
                  "wiki-cli --root <团队clone> changes,或直接 sync-team --pull")
        return {"ok": False, "branch": branch, "commit": commit, "fetched": fetched,
                "reason": reason}

    behind, _ = repo.git_behind_count(root)
    groups: Dict[tuple, Dict[str, Any]] = {}
    for status, rel in inc:
        kind, name = classify(rel)
        g = groups.setdefault((kind, name), {"kind": kind, "name": name, "files": []})
        g["files"].append({"status": status, "path": rel})
    grouped = list(groups.values())
    for g in grouped:
        g["size"] = "大更新" if (g["kind"] == "module" and len(g["files"]) > 1) else "小更新"
    # 模块在前,其余按名
    grouped.sort(key=lambda x: (x["kind"] != "module", x["name"]))

    return {
        "ok": True, "branch": branch, "commit": commit, "fetched": fetched, "note": note,
        "behind_commits": behind, "changed_files": len(inc),
        "up_to_date": (not inc), "groups": grouped,
    }


def format_text(res: Dict[str, Any]) -> str:
    if not res["ok"]:
        head = f"当前 {res.get('branch') or '?'} @ {res.get('commit') or '?'}"
        return f"{head}\n无法比较:{res['reason']}"
    lines = [f"当前:{res['branch']} @ {res['commit']}" + ("  (已 fetch 最新)" if res["fetched"] else "")]
    if res["note"]:
        lines.append(f"⚠ {res['note']}")
    if res["up_to_date"]:
        lines.append("✅ 已是最新,没有待更新的团队知识")
        return "\n".join(lines)
    lines.append(f"落后 origin {res['behind_commits']} 个 commit,涉及 {res['changed_files']} 个知识文件:")
    mark = {"A": "新增", "M": "修改", "D": "删除", "R": "重命名"}
    for g in res["groups"]:
        label = _KIND_LABEL.get(g["kind"], g["kind"])
        statuses = "/".join(sorted({mark.get(f["status"][0], f["status"][0]) for f in g["files"]}))
        tag = f" [{g['size']}]" if g["kind"] == "module" else ""
        lines.append(f"  [{label}] {g['name']}{tag} — {len(g['files'])} 文件 ({statuses})")
    lines.append("\n这是只读检查,不会自动更新。确认后手动应用:/wiki-sync(= git pull)。")
    return "\n".join(lines)
