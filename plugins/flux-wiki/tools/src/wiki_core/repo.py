"""wiki 仓库定位、配置文件、页面遍历、git 辅助。"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Iterator, List, Optional, Tuple

# 识别 wiki 根的标记文件(任一存在即认为是 wiki 根;_routes/_vocabulary 兼容 v2 旧库)
ROOT_MARKERS = ("AGENTS.md", "_routes.md", "_vocabulary.md")

# 遍历页面时排除的目录(.wiki 是工具产物区,raw 是只读原件区,revisions 是审计区,均不算知识页)
EXCLUDE_DIRS = {".git", ".obsidian", ".idea", ".claude", ".wiki", "raw", "revisions", "node_modules"}

# 库根层的协议/导航/台账文件:是基础设施不是知识(learn 不推送、search 默认不计分)
INFRA_FILES = {"AGENTS.md", "_routes.md", "_vocabulary.md", "overview.md", "log.md", "README.md"}


def is_root_infra(root: str, path: str) -> bool:
    """path 是否为「库根/内容根层」的协议文件(深层同名文件不算,域内 README 是内容)。"""
    base = os.path.basename(path)
    if base not in INFRA_FILES:
        return False
    d = os.path.realpath(os.path.dirname(path))
    return d in (os.path.realpath(root), os.path.realpath(content_dir(root)))

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


def atomic_write_text(path: str, text: str):
    """原子写(同目录 tmp + os.replace):截断式 open('w') 在进程被杀/磁盘满时会把
    文件留成空壳;配置里有 installed_files 清单,清零等于卸载/巡检失去唯一依据。"""
    tmp = path + ".tmp-flux"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _write_config(data: Dict[str, Any]):
    """整体写配置文件(覆盖)。需要删键的调用方用它,save_config 只做合并。
    旧文件在场时先留一份 .bak(配置损坏被静默读成 {} 后,一次 save 会把
    teams/manifest 全部抹掉——.bak 是最后的找回手段)。"""
    if os.path.isfile(CONFIG_PATH):
        try:
            import shutil
            shutil.copy2(CONFIG_PATH, CONFIG_PATH + ".bak")
        except OSError:
            pass
    atomic_write_text(CONFIG_PATH, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def save_config(updates: Dict[str, Any]):
    """合并写机器级配置(只更新给到的键)。"""
    data = load_config()
    data.update(updates)
    _write_config(data)


# ---------- 团队仓配置(config v2:命名多仓列表) ----------
#
# v2 形态:cfg["teams"] = [{"name", "path", "branch", "exclude": [glob...]}, ...]
# v1 兼容:只有 cfg["team_root"] 时合成单仓列表(name=目录名,无 branch/exclude)。
# 这是 learn 多仓化与 doctor 巡检的统一读取口,任何地方不要再直接读 team_root。

def get_teams(cfg: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    cfg = cfg if cfg is not None else load_config()
    teams = cfg.get("teams")
    out: List[Dict[str, Any]] = []
    if isinstance(teams, list):
        for t in teams:
            if isinstance(t, dict) and t.get("path"):
                path = os.path.abspath(os.path.expanduser(str(t["path"])))
                out.append({"name": t.get("name") or os.path.basename(path),
                            "path": path,
                            "branch": t.get("branch") or "",
                            "exclude": [str(x) for x in t.get("exclude") or []]})
        return out
    legacy = cfg.get("team_root")
    if legacy:
        path = os.path.abspath(os.path.expanduser(str(legacy)))
        out.append({"name": os.path.basename(path), "path": path, "branch": "", "exclude": []})
    return out


def resolve_team(spec: Optional[str], teams: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """把 --team 参数解析成团队仓配置:先按配置名精确匹配,再按路径;
    都不是则当作临时路径(无 branch/exclude 约束)。spec 为空返回 None。"""
    if not spec:
        return None
    for t in teams:
        if spec == t["name"]:
            return t
    ab = os.path.abspath(os.path.expanduser(spec))
    for t in teams:
        if ab == t["path"]:
            return t
    return {"name": os.path.basename(ab), "path": ab, "branch": "", "exclude": []}


def upsert_team(name: str, path: Optional[str] = None, branch: Optional[str] = None,
                exclude: Optional[List[str]] = None) -> Dict[str, Any]:
    """新增/更新一个命名团队仓配置(写 ~/.flux-wiki.json 的 teams 列表)。"""
    cfg = load_config()
    teams = [t for t in (cfg.get("teams") or []) if isinstance(t, dict)]
    if not teams and cfg.get("team_root"):
        legacy = os.path.abspath(os.path.expanduser(str(cfg["team_root"])))
        teams = [{"name": os.path.basename(legacy), "path": legacy}]
    hit = next((t for t in teams if t.get("name") == name), None)
    if hit is None:
        hit = {"name": name}
        teams.append(hit)
    if path is not None:
        hit["path"] = os.path.abspath(os.path.expanduser(path))
    if branch is not None:
        hit["branch"] = branch
    if exclude is not None:
        hit["exclude"] = exclude
    if not hit.get("path"):
        raise ValueError(f"团队仓 {name} 缺 path(新增时 --path 必填)")
    cfg["teams"] = teams
    cfg.pop("team_root", None)  # v1 键升级后移除,避免两处真源
    _write_config(cfg)
    return hit


def remove_team(name: str) -> bool:
    cfg = load_config()
    teams = [t for t in (cfg.get("teams") or []) if isinstance(t, dict)]
    if not teams and cfg.get("team_root"):
        # v1 配置(只有 team_root):合成仓名是目录名,命中即删 v1 键
        legacy = os.path.abspath(os.path.expanduser(str(cfg["team_root"])))
        if name in (os.path.basename(legacy), legacy, str(cfg["team_root"])):
            cfg.pop("team_root", None)
            cfg["teams"] = []
            _write_config(cfg)
            return True
        return False
    kept = [t for t in teams if t.get("name") != name]
    if len(kept) == len(teams):
        return False
    cfg["teams"] = kept
    _write_config(cfg)
    return True


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
    兼容 v2 旧库:始终从 content_dir 起扫(嵌套布局自动落到 <root>/wiki);
    v2 的 archive/ 在库根层,include_archive 时额外补扫——但绝不把库根层的
    协议文件 / revisions 审计记录混进结果(它们不是知识页)。
    """
    def _walk(base: str, skip_archive: bool) -> Iterator[str]:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and d != "templates"]
            parts = set(os.path.relpath(dirpath, base).split(os.sep))
            if "templates" in parts:
                continue
            if skip_archive:
                if "archive" in parts:
                    continue
                dirnames[:] = [d for d in dirnames if d != "archive"]
            for fn in filenames:
                if fn.endswith(".md"):
                    yield os.path.join(dirpath, fn)

    content = content_dir(root)
    yield from _walk(content, skip_archive=not include_archive)
    root_archive = os.path.join(root, "archive")
    if include_archive and content != root and os.path.isdir(root_archive):
        yield from _walk(root_archive, skip_archive=False)


def rel_path(root: str, path: str) -> str:
    # 双侧 realpath:root 或 path 任一经过 symlink(macOS /tmp→/private/tmp)时,
    # 避免输出 ../../../private/tmp/... 这种跨树相对路径
    return os.path.relpath(os.path.realpath(path), os.path.realpath(root))


def revisions_dir(root: str) -> str:
    """审计文件目录:v2 协议库根下已有 revisions/ 就用它,否则用 .wiki/revisions/。"""
    legacy = os.path.join(root, "revisions")
    if os.path.isdir(legacy):
        return legacy
    return os.path.join(root, ".wiki", "revisions")


def write_revision(root: str, op: str, lines: List[str]) -> str:
    """落一份审计文件(learn --mark / 全库 lint 的成功路径自动调用,续上审计链)。

    返回写入的绝对路径。文件名 <YYYY-MM-DD>-<HHMMSS>-<op>.md,与既有 revisions 命名一致。
    """
    from datetime import datetime
    now = datetime.now()
    d = revisions_dir(root)
    os.makedirs(d, exist_ok=True)
    base = os.path.join(d, f"{now.strftime('%Y-%m-%d')}-{now.strftime('%H%M%S')}-{op}")
    path = base + ".md"
    seq = 1
    while os.path.exists(path):  # 同秒同 op 不覆盖前一份审计(审计链绝不丢档)
        seq += 1
        path = f"{base}-{seq}.md"
    body = [f"# {op} | {now.strftime('%Y-%m-%d %H:%M:%S')}", "",
            "> 本文件由 wiki-cli 在操作成功后自动生成(审计链,勿手改)。", ""]
    body.extend(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n")
    return path


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


def git_diff_name_status(root: str, since: str) -> Optional[List[Tuple[str, str, Optional[str]]]]:
    """since..HEAD 的净变更 [(status, rel_path, old_rel)]。失败返回 None。

    status: A 新增 / M 修改 / D 删除 / R 重命名(带相似度,如 R100)。
    rel_path 是当前路径(D 为被删路径);old_rel 仅 R/C 有值 = 改名前路径——
    丢掉它会让「归档 = git mv 到 archive/」在调用方过滤后凭空消失,
    也会让 previous 已学映射对不上旧路径(改名被误判为全新页)。
    --relative:root 是大仓子目录时,只看子目录内的变更且路径相对 root 输出;root 即仓根时无影响。
    """
    try:
        r = _git(root, ["diff", "--relative", "--name-status", "-M", f"{since}..HEAD"], timeout=15)
        if r.returncode != 0:
            return None
        out: List[Tuple[str, str, Optional[str]]] = []
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0]
            if status[:1] in ("R", "C") and len(parts) >= 3:
                out.append((status, parts[2], parts[1]))
            else:
                out.append((status, parts[-1], None))
        return out
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def git_ls_md(root: str) -> Optional[List[str]]:
    """已跟踪的 .md 列表(相对 root)。失败/非 git 仓返回 None。

    learn 首次学习用它替代磁盘遍历:磁盘上未提交的页对增量学习者永远不可见,
    首学也只列已提交内容,两种模式才是同一事实源(水位/learned_commit 不失真)。
    """
    try:
        r = _git(root, ["ls-files", "--", "*.md"], timeout=10)
        if r.returncode != 0:
            return None
        return [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def git_rev_parse(root: str, ref: str) -> Optional[str]:
    """把 ref(短哈希/分支名)展开为完整 commit 哈希;无效返回 None。"""
    if not ref or not is_git_repo(root):
        return None
    try:
        r = _git(root, ["rev-parse", "--verify", "--quiet", ref + "^{commit}"], timeout=5)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def git_is_ancestor(root: str, ancestor: str, descendant: str) -> Optional[bool]:
    """ancestor 是否为 descendant 的祖先(水位是否还在当前分支历史上)。失败返回 None。"""
    try:
        r = _git(root, ["merge-base", "--is-ancestor", ancestor, descendant], timeout=5)
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def git_last_change(root: str, rel: str) -> Optional[str]:
    """rel(相对 root)在当前 HEAD 历史上最后一次变更的 commit。失败返回 None。

    learn --verify 用它判定 M 页是否真消化了**最新**变更:learned_commit 只比
    水位新、但比页面最后变更旧时,中间那次更新其实没学,纯水位比较会误判已核销。
    """
    try:
        r = _git(root, ["log", "-1", "--format=%H", "HEAD", "--", rel], timeout=10)
        if r.returncode != 0:
            return None
        return r.stdout.strip() or None
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
