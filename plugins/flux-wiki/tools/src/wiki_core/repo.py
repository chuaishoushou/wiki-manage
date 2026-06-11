"""wiki 仓库定位、配置文件、页面遍历、git 辅助。"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Iterator, List, Optional, Tuple

# 识别 wiki 根的标记文件(任一存在即认为是 wiki 根;_routes/_vocabulary 兼容 v2 旧库)
ROOT_MARKERS = ("AGENTS.md", "_routes.md", "_vocabulary.md")

# 遍历页面时排除的目录(.wiki 是工具产物区,raw 是只读原件区,均不算知识页)
EXCLUDE_DIRS = {".git", ".obsidian", ".idea", ".claude", ".wiki", "raw", "node_modules"}

# 机器级配置:安装时由 wiki-init 写入,记录个人库/团队仓位置。
# 这是"裸跑 wiki-cli 不带 --root"时的兜底来源,取代旧版写死 ~/AI/wiki 的硬编码。
CONFIG_PATH = os.path.expanduser("~/.flux-wiki.json")


def load_config() -> Dict[str, Any]:
    """读机器级配置;不存在/损坏返回 {}(工具不崩,由调用方决定后续)。"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(updates: Dict[str, Any]):
    """合并写机器级配置(只更新给到的键)。"""
    data = load_config()
    data.update(updates)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def find_wiki_root_verbose(start: Optional[str] = None) -> Tuple[Optional[str], str]:
    """查找 wiki 根并返回来源,便于自查"我连到的是哪个库"。

    返回 (root, source),source ∈
        {start, start-invalid, env, env-invalid, config, config-invalid, cwd, none}。
    优先级:
      1. 显式 start(CLI --root / 调用方传入)——指了就必须有效,无效硬失败不回退
      2. $WIKI_ROOT 非空:同样无效硬失败,绝不静默回退
      3. ~/.flux-wiki.json 配置的 personal_root(安装时写入)
      4. 从 cwd 向上找标记(便利路径)
    找不到返回 (None, 'none'),由调用方给修复指引。
    """
    if start:
        cand = os.path.abspath(os.path.expanduser(start))
        if _is_root(cand):
            return cand, "start"
        return None, "start-invalid"

    env_root = os.environ.get("WIKI_ROOT")
    if env_root:
        cand = os.path.abspath(os.path.expanduser(env_root))
        if _is_root(cand):
            return cand, "env"
        return None, "env-invalid"

    cfg_root = load_config().get("personal_root")
    if cfg_root:
        cand = os.path.abspath(os.path.expanduser(cfg_root))
        if _is_root(cand):
            return cand, "config"
        # 配置了但无效:继续尝试 cwd(配置可能过期),但来源标记保留给 status 提示

    cur = os.path.abspath(os.getcwd())
    while True:
        if _is_root(cur):
            return cur, "cwd"
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    if cfg_root:
        return None, "config-invalid"
    return None, "none"


def resolve_in_root(root: str, p: str) -> Optional[str]:
    """把入参路径安全解析到 root 内,防 '../' 穿越与越界绝对路径。"""
    if not root:
        return None
    candidate = p if os.path.isabs(p) else os.path.join(root, p)
    real_root = os.path.realpath(root)
    real_full = os.path.realpath(candidate)
    try:
        if os.path.commonpath([real_root, real_full]) == real_root:
            return real_full
    except ValueError:
        return None
    return None


def _is_root(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    return any(os.path.isfile(os.path.join(path, m)) for m in ROOT_MARKERS)


def content_dir(root: str) -> str:
    """内容目录。v3 扁平库 = root 自身;v2 旧库(root 下有 wiki/ 子目录)= <root>/wiki。"""
    sub = os.path.join(root, "wiki")
    return sub if os.path.isdir(sub) else root


def is_legacy_layout(root: str) -> bool:
    """是否 v2 嵌套布局(root 下有 wiki/ 内容层)。"""
    return os.path.isdir(os.path.join(root, "wiki"))


def iter_pages(root: str, include_archive: bool = False) -> Iterator[str]:
    """遍历知识页(.md)。

    默认只扫 active 区:跳过 archive/(归档)、templates/(v2 旧库模板)、
    EXCLUDE_DIRS(.git/.wiki/raw 等)。include_archive=True 时连 archive 一起扫。
    兼容 v2 旧库:从 content_dir 起扫(嵌套布局自动落到 <root>/wiki)。
    """
    base = root if include_archive else content_dir(root)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        rel = os.path.relpath(dirpath, base)
        parts = set(rel.split(os.sep))
        if "templates" in parts:
            continue
        dirnames[:] = [d for d in dirnames if d != "templates"]
        if not include_archive:
            if "archive" in parts:
                continue
            dirnames[:] = [d for d in dirnames if d != "archive"]
        for fn in filenames:
            if fn.endswith(".md"):
                yield os.path.join(dirpath, fn)


def rel_path(root: str, path: str) -> str:
    return os.path.relpath(path, root)


# ---------- git 辅助(只读为主;pull 仅 learn --pull 使用) ----------

def _git(root, args, timeout=10):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=timeout)


def is_git_repo(root: str) -> bool:
    """root 是否在 git 仓内(仓根 / 大仓子目录 / worktree 均算)。

    团队仓常见形态是"团队大仓里的一个子目录"(自身无 .git),git -C 系列命令
    在其中都正常工作,因此用 rev-parse 探测而非检查 .git 存在
    (.git 在 worktree/submodule 下还是文件不是目录,目录检查本就不可靠)。
    """
    if not os.path.isdir(root):
        return False
    try:
        r = _git(root, ["rev-parse", "--git-dir"], timeout=5)
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def git_head_info(root: str) -> Tuple[Optional[str], Optional[str]]:
    """返回 (当前分支名, 完整 commit 哈希)。非 git 仓返回 (None, None)。"""
    if not is_git_repo(root):
        return None, None
    try:
        b = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
        s = _git(root, ["rev-parse", "HEAD"], timeout=5)
        return (b.stdout.strip() or None), (s.stdout.strip() or None)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None


def git_commit_exists(root: str, commit: str) -> bool:
    """commit 是否存在于该仓(水位失效检测:团队仓 force-push/重建后水位作废)。"""
    if not commit or not is_git_repo(root):
        return False
    try:
        r = _git(root, ["cat-file", "-e", commit + "^{commit}"], timeout=5)
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def git_pull(root: str) -> Tuple[bool, str]:
    """git pull --ff-only:只快进,不制造合并提交;本地有偏离则失败而非乱合并。"""
    if not is_git_repo(root):
        return False, "非 git 仓(无 .git),跳过 pull"
    try:
        r = _git(root, ["pull", "--ff-only"], timeout=60)
        return r.returncode == 0, (r.stderr.strip() or r.stdout.strip() or "ok")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"git pull 失败: {e}"


def git_behind_count(root: str) -> Tuple[Optional[int], str]:
    """(本地落后 origin 的 commit 数, 说明)。非 git 仓/无 upstream 返回 (None, 原因)。"""
    if not is_git_repo(root):
        return None, "非 git 仓"
    try:
        upstream = _git(root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], timeout=5)
        if upstream.returncode != 0:
            return None, "无 upstream 跟踪分支"
        res = _git(root, ["rev-list", "--count", "HEAD..@{u}"], timeout=5)
        if res.returncode != 0:
            return None, "git rev-list 失败"
        return int(res.stdout.strip() or "0"), "ok"
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        return None, f"git 不可用: {e}"


def git_diff_name_status(root: str, since: str) -> Optional[List[Tuple[str, str]]]:
    """since..HEAD 的净变更 [(status, rel_path)](A 新增/M 修改/D 删除/R 重命名)。失败返回 None。

    --relative:root 是大仓子目录时,只看子目录内的变更且路径相对 root 输出
    (调用方按 rel_path 拼绝对路径、做知识页过滤,都要求相对 root);root 即仓根时无影响。
    """
    try:
        r = _git(root, ["diff", "--relative", "--name-status", "-M", f"{since}..HEAD"], timeout=15)
        if r.returncode != 0:
            return None
        out: List[Tuple[str, str]] = []
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                out.append((parts[0], parts[-1]))
        return out
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def git_log_subjects(root: str, since: str, limit: int = 50) -> List[str]:
    """since..HEAD 的提交标题列表(新→旧),供 AI 理解团队改动意图。

    pathspec 限定 root 子树:大仓里只有动过团队知识目录的提交才与学习相关。
    """
    try:
        r = _git(root, ["log", "--format=%h %s", f"{since}..HEAD", f"-{limit}", "--", "."], timeout=15)
        if r.returncode != 0:
            return []
        return [ln for ln in r.stdout.splitlines() if ln.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
