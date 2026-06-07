"""YAML frontmatter 解析(标准库实现,不依赖 PyYAML)。

只解析顶层 frontmatter 块(--- 围栏之间),覆盖本 wiki 实际用到的形态:
- key: scalar
- key: [a, b, c]          (内联列表)
- key: []                 (空列表)
- key:                    (块列表,后跟 - item 行)
    - item
- key: { ... }            (嵌套 map,原样存为字符串,不深解析)

对校验目的足够:我们只需要顶层标量与列表字段。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def _parse_inline_list(s: str) -> List[str]:
    """解析 [a, b, c];空 [] 返回 []。"""
    inner = s.strip()[1:-1].strip()
    if not inner:
        return []
    return [_strip_quotes(x) for x in inner.split(",") if x.strip()]


def parse(text: str) -> Tuple[Dict[str, Any], str, bool]:
    """解析 frontmatter。

    返回 (meta, body, has_frontmatter)。
    无 frontmatter 时返回 ({}, 原文, False)。
    """
    # 去掉 UTF-8 BOM,否则首行变 "﻿---" 会被误判为无 frontmatter
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False

    # 找闭合 ---
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text, False

    meta: Dict[str, Any] = {}
    block_lines = lines[1:end]
    i = 0
    while i < len(block_lines):
        raw = block_lines[i]
        line = raw.rstrip()
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        if value == "":
            # 可能是块列表:看后续缩进的 - 行
            items: List[str] = []
            while i < len(block_lines):
                nxt = block_lines[i]
                if nxt.strip().startswith("- "):
                    items.append(_strip_quotes(nxt.strip()[2:]))
                    i += 1
                elif nxt.strip() == "":
                    i += 1
                else:
                    break
            meta[key] = items if items else ""
        elif value.startswith("[") and value.endswith("]"):
            meta[key] = _parse_inline_list(value)
        elif value.startswith("{"):
            meta[key] = value  # 嵌套 map 原样保留
        else:
            meta[key] = _strip_quotes(value)

    body = "\n".join(lines[end + 1:])
    return meta, body, True


def read_page(path: str) -> Tuple[Dict[str, Any], str, bool]:
    """读取一个 md 文件,返回 (meta, body, has_frontmatter)。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return parse(text)


def extract_json_block(text: str) -> str | None:
    """从 markdown 中抽取第一个 json 代码围栏的内容(供 _vocabulary.md 解析)。

    只认"真围栏":marker 后(去空白)紧跟换行;避免误匹配散文里内联提到的同名字样。
    """
    marker = "```json"
    pos = 0
    while True:
        start = text.find(marker, pos)
        if start == -1:
            return None
        after = start + len(marker)
        # marker 之后到行尾只能是空白,才算真围栏起始
        line_end = text.find("\n", after)
        if line_end != -1 and text[after:line_end].strip() == "":
            end = text.find("```", line_end)
            if end == -1:
                return None
            return text[line_end + 1:end].strip()
        pos = after
