"""wiki 仓库定位、页面遍历、git 新鲜度检查。"""
from __future__ import annotations

import os
import subprocess
from typing import Dict, Iterator, List, Optional, Tuple

# 识别 wiki 根的标记文件(任一存在即认为是 wiki 根)
ROOT_MARKERS = ("AGENTS.md", "_routes.md", "_vocabulary.md")

# 遍历页面时排除的目录
EXCLUDE_DIRS = {".git", ".obsidian", ".idea", ".claude", "raw", "node_modules"}

# 约定兜底路径:WIKI_ROOT 未注入时(典型:GUI/Desktop 启动不继承 shell env)的安全兜底。
# team-default 排在 personal 之前,确保团队成员丢 env 时落到团队库而非维护者私有个人库。
# 测试可 monkeypatch 这两个常量。
TEAM_WIKI_FALLBACK = os.path.expanduser("~/AI/team-wiki")
PERSONAL_WIKI_FALLBACK = os.path.expanduser("~/AI/wiki")

# 个人库下存放"团队仓镜像"的保留子目录(content_dir 下,即 wiki/team/)。
# sync-team 把团队仓内容镜像到这里:可被 search 检索(查个人库即查到团队知识),
# 但 lint 跳过它(团队页的 domain/frontmatter 不必符合个人库的受控词表,它是只读镜像)。
TEAM_MIRROR_SUBDIR = "team"


def find_wiki_root_verbose(start: Optional[str] = None) -> Tuple[Optional[str], str]:
    """查找 wiki 根并返回来源,便于成员自查"我连到的是哪个库"。

    返回 (root, source),source ∈
        {start, env, env-invalid, team-default, cwd, personal-fallback, none}。
    优先级:
      1. 显式 start(CLI --root / 调用方传入)
      2. $WIKI_ROOT 非空:合法→env;非法→(None,'env-invalid') 硬失败,绝不静默回退
      3. 约定团队路径 ~/AI/team-wiki(TEAM_WIKI_FALLBACK):GUI/Desktop 启动丢 env 时的
         安全兜底,落到团队库而非个人库 —— 这是"零环境变量新用户/GUI 也能连上团队库"的关键
      4. 从 cwd 向上找标记(便利路径,但 server 端会对此 source 发 ⚠)
      5. 个人库 ~/AI/wiki(PERSONAL_WIKI_FALLBACK):向后兼容个人库用户,server 端发 ⚠
    关键安全点:显式配了 WIKI_ROOT 却无效 → (None,'env-invalid'),不静默回退,
    避免团队成员配错路径时悄悄拿到别的库。
    """
    if start:
        cand = os.path.abspath(start)
        if _is_root(cand):
            return cand, "start"

    env_root = os.environ.get("WIKI_ROOT")
    if env_root:
        cand = os.path.abspath(os.path.expanduser(env_root))
        if _is_root(cand):
            return cand, "env"
        return None, "env-invalid"

    # 约定团队路径:env 未注入(典型 GUI/Desktop 启动)时优先落团队库,不落个人库
    if _is_root(TEAM_WIKI_FALLBACK):
        return TEAM_WIKI_FALLBACK, "team-default"

    cur = os.path.abspath(start or os.getcwd())
    while True:
        if _is_root(cur):
            return cur, "cwd"
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    if _is_root(PERSONAL_WIKI_FALLBACK):
        return PERSONAL_WIKI_FALLBACK, "personal-fallback"
    return None, "none"


def find_wiki_root(start: Optional[str] = None) -> Optional[str]:
    """find_wiki_root_verbose 的薄封装,只返回 root。"""
    return find_wiki_root_verbose(start)[0]


def resolve_in_root(root: str, p: str) -> Optional[str]:
    """把入参路径安全解析到 root 内,防 '../' 穿越与越界绝对路径。

    允许:相对 root 的路径、落在 root 内的绝对路径。
    拒绝(返回 None):解析后跑到 root 之外的任何路径。
    各子命令共用此围栏,一处修复全局生效。
    """
    if not root:
        return None
    candidate = p if os.path.isabs(p) else os.path.join(root, p)
    real_root = os.path.realpath(root)
    real_full = os.path.realpath(candidate)
    try:
        if os.path.commonpath([real_root, real_full]) == real_root:
            return real_full
    except ValueError:
        # 不同盘符等 → commonpath 抛错,视为越界
        return None
    return None


def _is_root(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    return any(os.path.isfile(os.path.join(path, m)) for m in ROOT_MARKERS)


def content_dir(root: str) -> str:
    """内容目录:优先 <root>/wiki,否则 root 自身。"""
    sub = os.path.join(root, "wiki")
    return sub if os.path.isdir(sub) else root


def iter_pages(root: str, include_archive: bool = False, include_team: bool = True) -> Iterator[str]:
    """遍历 .md 页面。

    include_archive=False(默认,routine):只扫 content_dir(<root>/wiki 或 root),
        跳过 archive 子树 —— 体检/检索关注 active 区。
    include_archive=True(安全审计):以 root 为遍历根,覆盖根级 archive/、log.md、
        revisions/ 等(spec §3.1 点名的"永久固化"泄密点),仅排除 EXCLUDE_DIRS。
        这修复了"双层布局(root 有 wiki/ 子目录 + 根级 archive/)下 archive 永远扫不到"。
    include_team=True(默认):包含 team/ 团队镜像区(让 search 查得到团队知识)。
        lint 传 include_team=False 跳过它 —— 团队页是只读镜像,不按个人库受控词表校验。
    """
    base = root if include_archive else content_dir(root)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        # wiki/templates 是页面模板(含占位 frontmatter),不是知识内容,任何模式都跳过
        rel = os.path.relpath(dirpath, base)
        parts = set(rel.split(os.sep))
        if "templates" in parts:
            continue
        dirnames[:] = [d for d in dirnames if d != "templates"]
        if not include_archive:
            if "archive" in parts:
                continue
            dirnames[:] = [d for d in dirnames if d != "archive"]
        if not include_team:
            # team 镜像区是 content_dir 顶层子目录(wiki/team/):根部移除阻止递归,防御性 continue
            if rel == ".":
                dirnames[:] = [d for d in dirnames if d != TEAM_MIRROR_SUBDIR]
            elif rel.split(os.sep)[0] == TEAM_MIRROR_SUBDIR:
                continue
        for fn in filenames:
            if fn.endswith(".md"):
                yield os.path.join(dirpath, fn)


def rel_path(root: str, path: str) -> str:
    return os.path.relpath(path, root)


def git_behind_count(root: str) -> Tuple[Optional[int], str]:
    """返回 (本地落后 origin 的 commit 数, 说明)。

    非 git 仓 / 无 upstream / git 不可用时返回 (None, 原因)。
    只读操作:只跑 rev-list,不 fetch(避免阻塞;fetch 由调用方/hook 决定)。
    """
    if not os.path.isdir(os.path.join(root, ".git")):
        return None, "内容仓尚未纳入 git(无 .git)"
    try:
        # 确认存在 upstream
        upstream = subprocess.run(
            ["git", "-C", root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True, text=True, timeout=5,
        )
        if upstream.returncode != 0:
            return None, "无 upstream 跟踪分支"
        res = subprocess.run(
            ["git", "-C", root, "rev-list", "--count", "HEAD..@{u}"],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode != 0:
            return None, "git rev-list 失败"
        return int(res.stdout.strip() or "0"), "ok"
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        return None, f"git 不可用: {e}"


def _git(root, args, timeout=10):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=timeout)


def git_fetch(root: str) -> Tuple[bool, str]:
    """联网拉取远端最新引用(只更新 refs,不动工作区/不合并)。"""
    if not os.path.isdir(os.path.join(root, ".git")):
        return False, "非 git 仓"
    try:
        r = _git(root, ["fetch", "--quiet"], timeout=30)
        return r.returncode == 0, (r.stderr.strip() or "ok")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"git fetch 失败: {e}"


def git_pull(root: str) -> Tuple[bool, str]:
    """git pull --ff-only:只快进,不制造合并提交。

    用于 sync-team 同步前把团队仓本地 clone 更新到 origin 最新。团队仓是只读消费源,
    成员本地不应有提交,故 --ff-only;若本地有偏离会失败而非乱合并,提示用户处理。
    """
    if not os.path.isdir(os.path.join(root, ".git")):
        return False, "非 git 仓(无 .git),跳过 pull"
    try:
        r = _git(root, ["pull", "--ff-only"], timeout=60)
        return r.returncode == 0, (r.stderr.strip() or r.stdout.strip() or "ok")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"git pull 失败: {e}"


def git_head_info(root: str) -> Tuple[Optional[str], Optional[str]]:
    """返回 (当前分支名, 短 commit 哈希)。非 git 仓返回 (None, None)。"""
    if not os.path.isdir(os.path.join(root, ".git")):
        return None, None
    try:
        b = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
        s = _git(root, ["rev-parse", "--short", "HEAD"], timeout=5)
        return (b.stdout.strip() or None), (s.stdout.strip() or None)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None


def git_incoming(root: str) -> Optional[List[Tuple[str, str]]]:
    """HEAD..@{u} 的 name-status,即"pull 后会进来的变更"列表 [(status, path)]。

    status: A 新增 / M 修改 / D 删除 / R 重命名 等。
    非 git 仓或无 upstream 返回 None。
    """
    if not os.path.isdir(os.path.join(root, ".git")):
        return None
    try:
        up = _git(root, ["rev-parse", "--abbrev-ref", "@{u}"], timeout=5)
        if up.returncode != 0:
            return None
        r = _git(root, ["diff", "--name-status", "HEAD..@{u}"], timeout=10)
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
