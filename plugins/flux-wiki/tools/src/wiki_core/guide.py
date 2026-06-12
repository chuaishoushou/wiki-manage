"""guide:现读现发操作手册(playbooks),三平台拿到逐字相同的流程。

手册是「AI 怎么操作知识库」的唯一真源,活在仓内 plugins/flux-wiki/playbooks/,
git pull 即更新——平台侧的 skill/指针永远只是一句「跑 wiki-cli guide <op> 照做」,
不再渲染复制任何流程文本,渲染副本与仓内源漂移的问题结构性消失。

占位符在发牌瞬间按当前配置注入(运行时解析,非安装时烤死):
  {{WIKI_ROOT}} / {{WIKI_CONTENT}} / {{WIKI_CLI}} / {{TEAM_LIST}}
"""
from __future__ import annotations

import os
from typing import List, Optional

from . import repo

PLAYBOOKS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", "..", "..", "playbooks"))
CLI_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        "..", "..", "bin", "wiki-cli"))


def available() -> List[str]:
    if not os.path.isdir(PLAYBOOKS):
        return []
    return sorted(f[:-3] for f in os.listdir(PLAYBOOKS)
                  if f.endswith(".md") and not f.startswith("_"))


def _team_list_text() -> str:
    teams = repo.get_teams()
    if not teams:
        return "(未配置团队仓;wiki-cli config team <名> --path <路径> 登记)"
    lines = []
    for t in teams:
        extra = []
        if t["branch"]:
            extra.append(f"工作分支 {t['branch']}")
        if t["exclude"]:
            extra.append(f"exclude {len(t['exclude'])} 条")
        suffix = f"({', '.join(extra)})" if extra else ""
        lines.append(f"- [{t['name']}] `{t['path']}` {suffix}")
    return "\n".join(lines)


def render(op: str, root: Optional[str] = None) -> Optional[str]:
    """读 playbooks/<op>.md 并注入运行时值。手册不存在返回 None。"""
    path = os.path.join(PLAYBOOKS, op + ".md")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if root is None:
        cfg_root = repo.load_config().get("personal_root")
        root = os.path.abspath(os.path.expanduser(cfg_root)) if cfg_root else "<个人库未配置>"
    content = repo.content_dir(root) if os.path.isdir(root) else root
    return (text.replace("{{WIKI_ROOT}}", root)
                .replace("{{WIKI_CONTENT}}", content)
                .replace("{{WIKI_CLI}}", f'python3 "{CLI_PATH}"')
                .replace("{{TEAM_LIST}}", _team_list_text()))
