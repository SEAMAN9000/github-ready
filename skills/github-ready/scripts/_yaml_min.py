"""YAML 子集解析器，只用标准库。

支持：
- 块映射 `key: value`、块序列 `- item`，以缩进表示嵌套
- 标量：bare string / "double" / 'single' / int / true / false / null / ~
- 行内列表 `[a, b, c]`（元素限标量）
- 注释 `#`
- 作为映射值的块标量：`>`、`>-`、`|`、`|-`

不支持：锚点与别名、tag、多文档、行内映射、块标量的 `+` 模式、序列项里的块标量。
遇到无法解析的写法抛 ValueError，并指出行号。
"""

from __future__ import annotations

import re
from pathlib import Path


_FLOW_LIST_RE = re.compile(r"^\[(.*)\]$")


def _parse_scalar(s: str):
    """把一行裸标量解析成 Python 值。"""
    s = s.strip()
    if not s:
        return None
    # 双引号
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        body = s[1:-1]
        # 只替换认得的转义序列；整体按 unicode_escape 解码会把中文解成乱码
        _esc = {"\\n": "\n", "\\t": "\t", "\\r": "\r", '\\"': '"', "\\\\": "\\"}
        return re.sub(r'\\[ntr"\\]', lambda m: _esc[m.group(0)], body)
    # 单引号（YAML：`''` 是字面 `'`）
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        body = s[1:-1]
        return body.replace("''", "'")
    # null
    if s in ("null", "~", "Null", "NULL"):
        return None
    # bool
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    # int
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    # flow list
    m = _FLOW_LIST_RE.match(s)
    if m:
        inside = m.group(1).strip()
        if not inside:
            return []
        items = _split_flow_items(inside)
        return [_parse_scalar(x) for x in items]
    # 以 [ 开头但没闭合（或跨行）的列表是解析错误，不当成普通字符串
    if s.startswith("["):
        raise ValueError(f"未闭合或跨行的 flow 列表：{s!r}")
    # bare string
    return s


def _split_flow_items(inside: str) -> list[str]:
    """切分 flow 列表内部的逗号，跳过引号内的逗号。"""
    out = []
    buf = []
    in_single = False
    in_double = False
    for ch in inside:
        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
        elif ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
        elif ch == "," and not in_single and not in_double:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf).strip())
    return out


def _strip_comment(line: str) -> str:
    """去掉行尾注释，注意引号内的 # 不算注释。"""
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            # YAML 中 '' 是字面单引号；不切换状态
            if in_single and i + 1 < len(line) and line[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
        i += 1
    return line


def _indent_of(line: str) -> int:
    n = 0
    for ch in line:
        if ch == " ":
            n += 1
        elif ch == "\t":
            raise ValueError("YAML 解析器不支持 tab 缩进")
        else:
            break
    return n


def _next_significant(lines, i: int):
    """返回 (i, ind) 跳过空行与注释行；到末尾返回 (len(lines), -1)。"""
    while i < len(lines):
        stripped = _strip_comment(lines[i]).rstrip()
        if stripped.strip():
            return i, _indent_of(stripped)
        i += 1
    return len(lines), -1


def _parse_block(lines, start: int, parent_indent: int):
    """从 lines[start] 开始解析一个块；要求下一非空行缩进 > parent_indent。
    返回 (value, next_index)；若没有有效子块返回 (None, start)。
    """
    i, ind = _next_significant(lines, start)
    if i >= len(lines) or ind <= parent_indent:
        return None, i
    stripped = _strip_comment(lines[i]).rstrip()
    rest = stripped[ind:]
    if rest.startswith("- "):
        return _parse_sequence(lines, i, ind)
    else:
        return _parse_mapping(lines, i, ind)


def _parse_block_scalar(lines, start: int, parent_indent: int, indicator: str):
    """解析块标量正文。

    收集 start 起缩进 > parent_indent 的行（空行不终止块），去公共缩进后：
    - `|` / `|-`：行间保留换行；
    - `>` / `>-`：单个换行折叠成空格，空行折叠成换行；
    - 收尾：裸 `|` / `>` 保留恰好一个结尾换行；`|-` / `>-` 去掉结尾换行。
    返回 (文本, 下一行号)。不支持 `+` 保留模式与序列项里的块标量。
    """
    block = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            block.append("")
            i += 1
            continue
        if _indent_of(line) <= parent_indent:
            break
        block.append(line)
        i += 1
    while block and not block[-1].strip():
        block.pop()
    if not block:
        return "", i
    common = min(_indent_of(x) for x in block if x.strip())
    content = [x[common:] if x.strip() else "" for x in block]
    if indicator.startswith("|"):
        body = "\n".join(content)
    else:
        paras, cur = [], []
        for x in content:
            if x == "":
                paras.append(" ".join(cur))
                cur = []
            else:
                cur.append(x)
        paras.append(" ".join(cur))
        body = "\n".join(paras)
    return (body + "\n" if indicator in (">", "|") else body), i


def _parse_mapping(lines, start: int, base_indent: int):
    out = {}
    i = start
    while i < len(lines):
        stripped = _strip_comment(lines[i]).rstrip()
        if not stripped.strip():
            i += 1
            continue
        ind = _indent_of(stripped)
        if ind < base_indent:
            return out, i
        if ind > base_indent:
            raise ValueError(f"行 {i+1}: 意外缩进 {ind} > 期望 {base_indent}（mapping）")
        content = stripped[ind:]
        if ":" not in content:
            raise ValueError(f"行 {i+1}: mapping 期望 key:value，得到 {content!r}")
        # 注意：value 中可能有 ':'。我们只切第一个未引用的 ':'。
        key, _, value = _split_first_colon(content)
        key = key.strip()
        value = value.strip()
        if value in (">", ">-", "|", "|-"):
            out[key], i = _parse_block_scalar(lines, i + 1, base_indent, value)
        elif value:
            out[key] = _parse_scalar(value)
            i += 1
        else:
            child, i = _parse_block(lines, i + 1, base_indent)
            out[key] = child  # None 表示空值
    return out, i


def _split_first_colon(s: str):
    """切分 key: value，忽略引号内的 ':'."""
    in_single = False
    in_double = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            if in_single and i + 1 < len(s) and s[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
        elif ch == ":" and not in_single and not in_double:
            return s[:i], ":", s[i + 1:]
        i += 1
    return s, "", ""


def _parse_sequence(lines, start: int, base_indent: int):
    out = []
    i = start
    while i < len(lines):
        stripped = _strip_comment(lines[i]).rstrip()
        if not stripped.strip():
            i += 1
            continue
        ind = _indent_of(stripped)
        if ind < base_indent:
            return out, i
        if ind > base_indent:
            raise ValueError(f"行 {i+1}: 意外缩进 {ind} > 期望 {base_indent}（sequence）")
        content = stripped[ind:]
        if not content.startswith("- "):
            return out, i
        item = content[2:].strip()
        if not item:
            child, i = _parse_block(lines, i + 1, base_indent)
            out.append(child)
            continue
        # 判断是否是内联 mapping：以非引号开头、含未引用的 ':'、且不是 flow list
        if item[0] not in '"\'[' and _has_unquoted_colon(item) and not _FLOW_LIST_RE.match(item):
            # 构造虚拟 mapping 块：当前行重写为同缩进 mapping 第一行
            virtual_indent = base_indent + 2
            lines_mod = list(lines)
            lines_mod[i] = " " * virtual_indent + item
            sub_map, i = _parse_mapping(lines_mod, i, virtual_indent)
            out.append(sub_map)
        else:
            out.append(_parse_scalar(item))
            i += 1
    return out, i


def _has_unquoted_colon(s: str) -> bool:
    in_single = False
    in_double = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            if in_single and i + 1 < len(s) and s[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
        elif ch == ":" and not in_single and not in_double:
            return True
        i += 1
    return False


def loads(text: str):
    """从字符串解析 YAML。"""
    lines = text.splitlines()
    i, ind = _next_significant(lines, 0)
    if i >= len(lines):
        return None
    # 跳过 ---
    if _strip_comment(lines[i]).strip() == "---":
        i, ind = _next_significant(lines, i + 1)
        if i >= len(lines):
            return None
    value, _ = _parse_block(lines, i, ind - 1)
    return value


def load(path) -> object:
    p = Path(path)
    return loads(p.read_text(encoding="utf-8"))

