"""解析 _routes.md 关键词路由表,提供解析/孤儿逆查/歧义检查。"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

_BACKTICK = re.compile(r"`([^`]+)`")


def _split_cells(row: str) -> List[str]:
    """按未转义的 | 切分 markdown 表格行(尊重 \\| 转义)。"""
    cells: List[str] = []
    buf = []
    i = 0
    while i < len(row):
        c = row[i]
        if c == "\\" and i + 1 < len(row) and row[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if c == "|":
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    cells.append("".join(buf))
    # 去掉首尾因前导/末尾 | 产生的空 cell
    return [c.strip() for c in cells]


class Route:
    def __init__(self, keywords: List[str], required: List[str], optional: List[str], lineno: int):
        self.keywords = keywords
        self.required = required
        self.optional = optional
        self.lineno = lineno


def parse_routes(root: str) -> List[Route]:
    path = os.path.join(root, "_routes.md")
    if not os.path.isfile(path):
        return []
    routes: List[Route] = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    in_table = False
    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        s = line.strip()
        if not s.startswith("|"):
            in_table = False
            continue
        # 跳过表头分隔行 |---|---|
        if set(s.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
            in_table = True
            continue
        # 只剥掉行首/行尾 | 产生的边界空 cell;**内部空 cell 必须保留**——
        # 否则 `| kw |  | x.md |`(必加载留空)会让可选列移位顶替成必加载,
        # 触发 route-missing 这一唯一 error 级检查的误报
        cells = _split_cells(s)
        if s.startswith("|") and cells and cells[0] == "":
            cells = cells[1:]
        if s.endswith("|") and cells and cells[-1] == "":
            cells = cells[:-1]
        if len(cells) < 2 or all(c == "" for c in cells):
            continue
        # 表头行在分隔行之前,此时 in_table 仍为 False → 由下行直接跳过。
        # (不再用"含'触发关键词'子串"判表头,避免误删恰好含该子串的合法数据行。)
        if not in_table:
            continue
        keywords = _BACKTICK.findall(cells[0])
        required = _BACKTICK.findall(cells[1]) if len(cells) > 1 else []
        optional = _BACKTICK.findall(cells[2]) if len(cells) > 2 else []
        if keywords or required:
            routes.append(Route(keywords, required, optional, idx))
    return routes


def resolve(routes: List[Route], keyword: str) -> List[Route]:
    """精确(大小写不敏感)匹配关键词,返回命中的 route(可能多个 = 歧义)。"""
    kw = keyword.strip().lower()
    hits = []
    for r in routes:
        if any(k.strip().lower() == kw for k in r.keywords):
            hits.append(r)
    return hits


def find_ambiguous(routes: List[Route]) -> Dict[str, List[int]]:
    """返回出现在 >1 个不同行的关键词 → 行号列表。

    同一行内的大小写变体(如 globex / GLOBEX)归一后属同一行,不算歧义。
    """
    seen: Dict[str, set] = {}
    for r in routes:
        for k in r.keywords:
            seen.setdefault(k.strip().lower(), set()).add(r.lineno)
    return {k: sorted(v) for k, v in seen.items() if len(v) > 1}


def missing_targets(root: str, routes: List[Route]) -> List[Tuple[int, str]]:
    """返回 (行号, 不存在的必加载路径)。路径相对 wiki 根。"""
    missing = []
    for r in routes:
        for p in r.required:
            full = os.path.join(root, p)
            if not os.path.isfile(full):
                missing.append((r.lineno, p))
    return missing


def _resolve_optional(root: str, r: Route, p: str) -> str:
    """可选加载路径的解析基准:**必加载页所在目录**(写短名即可,如 `code-map.md`);
    按根相对写也兼容(两种基准任一命中即有效)。"""
    if r.required:
        cand = os.path.join(root, os.path.dirname(r.required[0]), p)
        if os.path.isfile(cand):
            return cand
    return os.path.join(root, p)


def missing_optional(root: str, routes: List[Route]) -> List[Tuple[int, str]]:
    """返回 (行号, 解析不到的可选加载路径)——按可选列双基准都找不到才算。"""
    missing = []
    for r in routes:
        for p in r.optional:
            if not os.path.isfile(_resolve_optional(root, r, p)):
                missing.append((r.lineno, p))
    return missing


def covered_paths(root: str, routes: List[Route]) -> set:
    """所有被路由覆盖(必加载或可选加载)的绝对路径集合。"""
    paths = set()
    for r in routes:
        for p in r.required:
            paths.add(os.path.abspath(os.path.join(root, p)))
        for p in r.optional:
            paths.add(os.path.abspath(_resolve_optional(root, r, p)))
    return paths
