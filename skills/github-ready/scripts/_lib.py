"""共用函数：找 SKILL.md、读头部信息、把 README 按标题分节。"""
from __future__ import annotations

import re
from pathlib import Path

import _yaml_min

# 找 SKILL.md 时跳过这些文件夹，里面的是产出物或备份的副本
DERIVED_DIRS = {"output", "backup", "node_modules", ".git", "dist", "__pycache__"}


def find_skill_mds(root: Path) -> list[Path]:
    """找 root 下全部 SKILL.md，排除派生目录。"""
    hits = []
    for p in root.rglob("SKILL.md"):
        parts = p.relative_to(root).parts[:-1]
        if any(x in DERIVED_DIRS for x in parts):
            continue
        hits.append(p)
    return sorted(hits)


def parse_frontmatter(text: str) -> dict:
    """取文件顶部两条 --- 之间的 YAML；没有则返回 {}。"""
    m = re.match(r"\ufeff?---\s*\n(.*?)\n---\s*(\n|$)", text, flags=re.S)
    if not m:
        return {}
    data = _yaml_min.loads(m.group(1))
    return data if isinstance(data, dict) else {}


def strip_code_blocks(md: str) -> str:
    """把 ``` 围栏代码块换成等行数的空行——行号不变，标题检测不受代码块干扰。

    未闭合的围栏按 CommonMark 语义延伸到文末，同样按代码处理。
    """
    out = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), md, flags=re.S)
    m = re.search(r"```", out)
    if m:  # 配对替换后仍剩围栏 → 奇数个：从未配对处到文末全按代码抹掉
        tail = out[m.start():]
        out = out[: m.start()] + "\n" * tail.count("\n")
    return out


def split_sections(md: str) -> list[dict]:
    """按 # 与 ## 标题切分（### 留在上级 body 里）。

    返回 [{title, level, start_line, body}]，行号从 1 起；开头无标题的部分
    title 为 "_preamble"。body 保留原始行（含代码块）。
    """
    md = md.replace("\r\n", "\n")
    raw_lines = md.split("\n")
    safe_lines = strip_code_blocks(md).split("\n")
    sections = []
    cur = {"title": "_preamble", "level": 0, "start_line": 1, "_body": []}
    for idx, (raw, safe) in enumerate(zip(raw_lines, safe_lines), start=1):
        m = re.match(r"^(#{1,2})\s+(.+?)\s*$", safe)
        if m:
            sections.append(cur)
            cur = {"title": m.group(2), "level": len(m.group(1)),
                   "start_line": idx, "_body": []}
        else:
            cur["_body"].append(raw)
    sections.append(cur)
    for s in sections:
        s["body"] = "\n".join(s.pop("_body"))
    return sections


def norm_title(t: str) -> str:
    """标题归一：去掉 emoji/标点/空白，转小写。中英皆适用。"""
    return re.sub(r"[^\w一-鿿]+", "", t).lower()
