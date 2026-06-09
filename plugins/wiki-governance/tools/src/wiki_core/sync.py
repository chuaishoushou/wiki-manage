"""sync-team:把团队仓(上游 git 仓)的知识【镜像同步】到个人库的 team/ 区。

用户决策:团队→个人 = 同步(镜像),不重分类、不学习。
- 源:团队仓本地 clone(独立 git 仓)的 content_dir
- 目标:个人库 content_dir/team/(即 wiki/team/);可被 search 检索,但不参与 lint
- 镜像语义:新增/修改/删除都对齐(幂等 —— 再次同步只动变化的页)
- 溯源:写 team/.sync-manifest.json 记来源 repo / 分支 / commit / 时间 / 页数
- 写操作:sync-team 是写子命令(像 publish);检索/校验子命令只读
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict

from . import repo

MANIFEST_NAME = ".sync-manifest.json"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def mirror_root(personal_root: str) -> str:
    """个人库里团队镜像区的绝对路径(content_dir/team)。"""
    return os.path.join(repo.content_dir(personal_root), repo.TEAM_MIRROR_SUBDIR)


def _existing_mirror_pages(mr: str) -> Dict[str, str]:
    """镜像区现有 .md 页:相对 mirror_root 的路径 -> 绝对路径。"""
    out: Dict[str, str] = {}
    if not os.path.isdir(mr):
        return out
    for dirpath, _, filenames in os.walk(mr):
        for fn in filenames:
            if fn.endswith(".md"):
                ab = os.path.join(dirpath, fn)
                out[os.path.relpath(ab, mr)] = ab
    return out


def plan(personal_root: str, team_repo: str) -> Dict[str, Any]:
    """只读规划:对比团队仓与镜像区,算 added/updated/deleted/unchanged,不写盘。"""
    team_content = repo.content_dir(team_repo)
    mr = mirror_root(personal_root)
    team_pages: Dict[str, str] = {}
    for ab in repo.iter_pages(team_repo):
        team_pages[os.path.relpath(ab, team_content)] = ab
    existing = _existing_mirror_pages(mr)

    added, updated, unchanged, deleted = [], [], [], []
    for rel, ab in team_pages.items():
        dst = os.path.join(mr, rel)
        if rel not in existing:
            added.append(rel)
        elif _read(ab) != _read(dst):
            updated.append(rel)
        else:
            unchanged.append(rel)
    for rel in existing:
        if rel not in team_pages:
            deleted.append(rel)
    return {
        "mirror_root": mr, "team_pages": team_pages,
        "added": sorted(added), "updated": sorted(updated),
        "deleted": sorted(deleted), "unchanged": sorted(unchanged),
    }


def sync_team(personal_root: str, team_repo: str, do_pull: bool = False,
              dry_run: bool = False) -> Dict[str, Any]:
    """镜像团队仓 content 到个人库 team/ 区。返回结构化报告。"""
    team_repo = os.path.abspath(os.path.expanduser(team_repo))
    if not os.path.isdir(team_repo):
        return {"ok": False, "reason": f"团队仓路径不存在: {team_repo}"}
    if not repo._is_root(team_repo):
        return {"ok": False, "reason": (
            f"团队仓不是合法 wiki 根(缺 {'/'.join(repo.ROOT_MARKERS)} 任一标记)。"
            f"请先在团队仓初始化:wiki-cli init \"{team_repo}\"。路径:{team_repo}")}

    pull_note = ""
    if do_pull:
        ok, msg = repo.git_pull(team_repo)
        pull_note = f"git pull --ff-only: {'✅' if ok else '⚠'} {msg}"

    p = plan(personal_root, team_repo)
    branch, commit = repo.git_head_info(team_repo)

    if not dry_run:
        mr = p["mirror_root"]
        for rel in p["added"] + p["updated"]:
            _write(os.path.join(mr, rel), _read(p["team_pages"][rel]))
        for rel in p["deleted"]:
            dst = os.path.join(mr, rel)
            if os.path.isfile(dst):
                os.remove(dst)
        _prune_empty_dirs(mr)
        _write_manifest(mr, team_repo, branch, commit, p)

    return {
        "ok": True, "dry_run": dry_run, "pull_note": pull_note,
        "team_repo": team_repo, "team_branch": branch, "team_commit": commit,
        "mirror_root": p["mirror_root"],
        "added": p["added"], "updated": p["updated"], "deleted": p["deleted"],
        "unchanged_count": len(p["unchanged"]),
    }


def _prune_empty_dirs(root: str):
    """删除镜像区里因 deleted 变空的目录(自底向上;保留 root 自身)。"""
    if not os.path.isdir(root):
        return
    for dirpath, _, _ in os.walk(root, topdown=False):
        if os.path.abspath(dirpath) == os.path.abspath(root):
            continue
        if not os.listdir(dirpath):
            os.rmdir(dirpath)


def _write_manifest(mr: str, team_repo: str, branch, commit, p: Dict[str, Any]):
    manifest = {
        "source_repo": team_repo,
        "source_branch": branch,
        "source_commit": commit,
        "synced_at": datetime.now().isoformat(timespec="seconds"),
        "page_count": len(p["added"]) + len(p["updated"]) + len(p["unchanged"]),
        "note": "只读镜像,由 wiki-cli sync-team 生成。勿手改;要改团队知识请到团队仓。",
    }
    os.makedirs(mr, exist_ok=True)
    with open(os.path.join(mr, MANIFEST_NAME), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def format_text(res: Dict[str, Any]) -> str:
    if not res.get("ok"):
        return f"❌ 同步未执行:{res.get('reason')}"
    lines = ["【dry-run 预览,未写盘】" if res.get("dry_run") else "✅ 同步完成"]
    if res.get("pull_note"):
        lines.append(res["pull_note"])
    lines.append(f"团队仓:{res['team_repo']} @ {(res.get('team_branch') or '?')}/{(res.get('team_commit') or '?')}")
    lines.append(f"镜像到:{res['mirror_root']}")
    lines.append(f"  新增 {len(res['added'])} · 更新 {len(res['updated'])} · "
                 f"删除 {len(res['deleted'])} · 未变 {res['unchanged_count']}")
    for rel in res["added"]:
        lines.append(f"  + {rel}")
    for rel in res["updated"]:
        lines.append(f"  ~ {rel}")
    for rel in res["deleted"]:
        lines.append(f"  - {rel}")
    lines.append("\n团队知识已进个人库 team/ 区,查个人库即可检索到。要改请到团队仓,再 sync-team。")
    return "\n".join(lines)
