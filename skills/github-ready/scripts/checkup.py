"""体检：检查一个 skill 项目是否符合发布标准。只读，不改目标项目。

用法：
    python checkup.py <项目路径> [--json 结果文件] [--pick SKILL.md相对路径]

退出码：0 = 体检完成（结论看 findings）；2 = 找不到 SKILL.md；
        3 = 有多个 SKILL.md 且没有用 --pick 指定（候选已打印）；
        4 = SKILL.md 头部信息无法解析（原因已打印）；
        5 = 本机没有 git。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib          # noqa: E402
import _yaml_min     # noqa: E402

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"


def F(rule, status, file, line, detail):
    return {"rule": rule, "status": status, "file": file, "line": line, "detail": detail}


def _template_to_re(tpl: str) -> re.Pattern:
    """把 'skills/<name>/SKILL.md' 这类模板转成正则。

    先按 <占位符> 切开再逐段转义：re.escape 对 < > 的处理随 Python 版本不同。
    """
    parts = re.split(r"<[^>]+>", tpl)
    return re.compile("^" + "[^/]+".join(re.escape(p) for p in parts) + "$")


def locate(root: Path, pick: str | None):
    """找到 skill 的 SKILL.md。返回 (路径或 None, 退出码)。"""
    if pick:
        p = root / pick
        if not p.is_file() or p.name != "SKILL.md":
            print(f"错误：--pick 指定的文件不存在或不是 SKILL.md：{pick}")
            return None, 2
        return p, 0
    hits = _lib.find_skill_mds(root)
    if not hits:
        print("错误：找不到 SKILL.md，这不是一个 skill 项目。")
        return None, 2
    if len(hits) > 1:
        print("找到多个 SKILL.md，请用 --pick 指定其一：")
        for h in hits:
            print("  " + h.relative_to(root).as_posix())
        return None, 3
    return hits[0], 0


GIT_NOTES = {
    "clean": "改动可以用 git 查看和撤销",
    "dirty": "项目有未存档的改动",
    "no-repo": "项目没有用 git 管理",
}


def git_state(root: Path) -> str | None:
    """返回 clean / dirty / no-repo；本机没有 git 时返回 None。

    root 自身必须是仓库顶层：嵌在别的仓库里的子文件夹按 no-repo 算。
    """
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
        if r.returncode != 0 or Path(r.stdout.strip()).resolve() != root.resolve():
            return "no-repo"
        s = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                           capture_output=True, text=True)
        return "dirty" if s.stdout.strip() else "clean"
    except FileNotFoundError:
        return None


def check_portability(root, skill_md, port, findings):
    """扫 SKILL.md 里只属于某一个工具的内容，命中的一律标成 suspect。"""
    rel = skill_md.relative_to(root).as_posix()
    text = skill_md.read_text(encoding="utf-8")
    lines = text.split("\n")
    hits = 0
    for sig in port.get("signals", []):
        seen = set()
        for lit in sig.get("literals", []):
            for i, line in enumerate(lines, start=1):
                if lit in line and (sig["id"], i) not in seen:
                    seen.add((sig["id"], i))
                    hits += 1
                    findings.append(F("PORT-" + sig["id"], "suspect", rel, i,
                                      f"{sig['display']}：「{lit}」——{sig['advice']}"))
    mp = port.get("memory_pair")
    if mp and mp["claude"] in text and mp["agents"] not in text:
        ln = next(i for i, x in enumerate(lines, start=1) if mp["claude"] in x)
        hits += 1
        findings.append(F("PORT-MEMORY", "suspect", rel, ln,
                          f"只提了 {mp['claude']}、没提 {mp['agents']}——{mp['advice']}"))
    if not hits:
        findings.append(F("PORT", "pass", rel, 1, "正文里没有写死平台专属内容"))


def check_description(root, skill_md, fm, rules, findings):
    """按 references/superpowers-standard.md 第一部分查 name 和 description。"""
    rel = skill_md.relative_to(root).as_posix()
    name = str(fm.get("name") or "")
    desc = str(fm.get("description") or "")
    if name:
        ok = bool(re.match(rules["name_pattern"], name)) and len(name) <= rules["name_max"]
        findings.append(F("NAME-FORMAT", "pass" if ok else "fail", rel, 1,
                          "" if ok else f"name「{name}」只能用小写字母、数字和连字符，"
                                        f"且不超过 {rules['name_max']} 个字符"))
    if not desc:
        return
    n, low = len(desc), desc.lower()
    if n > rules["description_max"]:
        findings.append(F("DESC-LENGTH", "fail", rel, 1,
                          f"description 有 {n} 个字符，超过上限 {rules['description_max']}"))
    elif n > rules["description_recommended"]:
        findings.append(F("DESC-LENGTH", "suspect", rel, 1,
                          f"description 有 {n} 个字符，超过建议的 {rules['description_recommended']}，"
                          "看看是否把正文的内容写进了简介"))
    else:
        findings.append(F("DESC-LENGTH", "pass", rel, 1, f"{n} 个字符"))
    if any(w in low for w in rules["when_markers"]):
        findings.append(F("DESC-WHEN", "pass", rel, 1, ""))
    else:
        findings.append(F("DESC-WHEN", "suspect", rel, 1,
                          "description 里找不到「……时使用」或 Use when 这类句式，请复查是否写了使用情形"))
    for rule, key, what in (("DESC-PERSON", "person_words", "第一人称或第二人称的词"),
                            ("DESC-WORKFLOW", "workflow_words", "表示步骤的词")):
        hits = [w.strip() for w in rules[key] if w in low]
        if hits:
            findings.append(F(rule, "suspect", rel, 1,
                              f"description 里出现{what}：{'、'.join(hits)}，请复查"))
        else:
            findings.append(F(rule, "pass", rel, 1, ""))


_LOCAL_PATH = re.compile(
    r"[A-Za-z]:[\\/][\w.-]+[\\/]|/Users/[\w.-]+/|/home/[\w.-]+/"
    r"|(?<![\\\w])[A-Za-z_][\w-]*\\[A-Za-z_][\w-]*\.[A-Za-z]{1,5}\b")
_TOC_HINT = re.compile(r"^#{1,6}\s*(目录|contents|table of contents)\b|\]\(#", re.I | re.M)


def check_body(root, skill_md, rules, findings):
    """按 references/superpowers-standard.md 第二部分查 SKILL.md 正文。"""
    rel = skill_md.relative_to(root).as_posix()
    skill_dir = skill_md.parent
    lines = skill_md.read_text(encoding="utf-8").split("\n")
    start = 0
    if lines and lines[0].lstrip("\ufeff").strip() == "---":
        start = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    body = lines[start:]

    n = len(body)
    if n > rules["body_max_lines"]:
        findings.append(F("BODY-LENGTH", "suspect", rel, 1,
                          f"正文有 {n} 行，超过 {rules['body_max_lines']} 行，看看哪些内容该放进附带文件"))
    else:
        findings.append(F("BODY-LENGTH", "pass", rel, 1, f"{n} 行"))

    # 正文提到的附带文件在不在。文件夹存在而文件不在才算必须修；
    # 连文件夹都没有的，可能说的是别的项目，标成 suspect。
    own_dirs = {d.name for d in skill_dir.iterdir() if d.is_dir() and not d.name.startswith((".", "__"))}
    names = sorted(own_dirs | set(rules["conventional_dirs"]))
    ref_re = re.compile(r"(?<![\w/.~<>\-])((?:%s)/[\w./*-]*)" % "|".join(re.escape(x) for x in names))
    missing, unsure, seen = [], [], set()
    for i, line in enumerate(body, start + 1):
        for m in ref_re.finditer(line):
            ref = m.group(1).rstrip(".")
            if ref in seen:
                continue
            seen.add(ref)
            top = ref.split("/", 1)[0]
            if "*" in ref:
                ok = any(skill_dir.glob(ref))
            else:
                ok = (skill_dir / ref).exists()
            if ok:
                continue
            (missing if top in own_dirs else unsure).append((i, ref))
    if missing:
        findings.append(F("BODY-REFS", "fail", rel, missing[0][0],
                          "正文引用的附带文件不存在：" + "、".join(f"{r}（第 {i} 行）" for i, r in missing)))
    elif unsure:
        findings.append(F("BODY-REFS", "suspect", rel, unsure[0][0],
                          "正文提到的这些路径在 skill 文件夹里找不到，请复查是不是该随 skill 附带的文件："
                          + "、".join(f"{r}（第 {i} 行）" for i, r in unsure)))
    else:
        findings.append(F("BODY-REFS", "pass", rel, 1, ""))

    hits = [(i, m.group(0)) for i, line in enumerate(body, start + 1)
            for m in [_LOCAL_PATH.search(line)] if m]
    if hits:
        findings.append(F("BODY-PATHS", "suspect", rel, hits[0][0],
                          "正文里出现本机绝对路径或反斜杠路径："
                          + "、".join(f"第 {i} 行 {s}" for i, s in hits[:5]) + "，请复查"))
    else:
        findings.append(F("BODY-PATHS", "pass", rel, 1, ""))

    long_refs = []
    for md in sorted(skill_dir.rglob("*.md")):
        if md == skill_md:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        if text.count("\n") + 1 > rules["reference_toc_lines"] and \
                not _TOC_HINT.search("\n".join(text.split("\n")[:40])):
            long_refs.append(md.relative_to(root).as_posix())
    if long_refs:
        findings.append(F("REF-TOC", "suspect", long_refs[0], 1,
                          f"这些附带文件超过 {rules['reference_toc_lines']} 行，开头没有目录："
                          + "、".join(long_refs)))
    else:
        findings.append(F("REF-TOC", "pass", rel, 1, ""))


def check_structure(root, skill_md, fm, plat, findings):
    rel = skill_md.relative_to(root).as_posix()
    # 头部信息必须有 name 和 description：安装器靠它认技能，触发靠它判断
    for key in ("name", "description"):
        if fm.get(key):
            findings.append(F("STRUCT-FRONTMATTER-" + key.upper(), "pass", rel, 1, "存在"))
        else:
            findings.append(F("STRUCT-FRONTMATTER-" + key.upper(), "fail", rel, 1,
                              f"SKILL.md 头部缺 {key}"))
    # 目录布局必须是安装器扫得到的；这里只报告，不替用户移动文件
    layouts = plat["installer"]["layouts_recognized"]
    recommended = plat["installer"]["recommended_layout"]
    if any(_template_to_re(t).match(rel) for t in layouts):
        note = "" if _template_to_re(recommended).match(rel) else f"（建议迁移为 {recommended}）"
        findings.append(F("STRUCT-LAYOUT", "pass", rel, 1, "安装器可发现" + note))
    else:
        findings.append(F("STRUCT-LAYOUT", "fail", rel, 1,
                          f"布局 {rel} 安装器扫描不到；推荐 {recommended}"))
    # LICENSE 文件
    lic = next((root / n for n in ("LICENSE", "LICENSE.md", "LICENSE.txt")
                if (root / n).is_file()), None)
    findings.append(F("STRUCT-LICENSE", "pass" if lic else "fail", "/", 1,
                      lic.name if lic else "仓库根找不到 LICENSE 文件"))
    # 中英两份 README 都要有，缺英文算待补项
    findings.append(F("README-ZH-EXISTS", "pass" if (root / "README.md").is_file() else "fail",
                      "README.md", 1, ""))
    en_ok = (root / "README.en.md").is_file()
    findings.append(F("README-EN-EXISTS", "pass" if en_ok else "fail",
                      "README.en.md", 1, "" if en_ok else "缺英文版，属于待补项"))
    return lic


def _match_sections(secs, rule_sections):
    """标准节 id -> 匹配到的 section（或 None/"suspect" 标记）。"""
    result = {}
    for rs in rule_sections:
        targets = {_lib.norm_title(rs["zh"]), _lib.norm_title(rs["en"])}
        exact = next((s for s in secs if s["level"] == 2
                      and _lib.norm_title(s["title"]) in targets), None)
        if exact:
            result[rs["id"]] = ("pass", exact)
            continue
        fuzzy = next((s for s in secs if s["level"] == 2 and any(
            t and (t in _lib.norm_title(s["title"]) or _lib.norm_title(s["title"]) in t)
            for t in targets)), None)
        if fuzzy:
            result[rs["id"]] = ("suspect", fuzzy)
            continue
        # 第三层：词级模糊——标题含标准英文名里任一 ≥4 字母的词 → suspect
        words = [w for w in re.findall(r"[a-z]+", rs["en"].lower()) if len(w) >= 4]
        wordy = next((s for s in secs if s["level"] == 2 and any(
            w in s["title"].lower() for w in words)), None)
        result[rs["id"]] = ("suspect", wordy) if wordy else ("miss", None)
    return result


# 看着像安装路径的写法：以 ~/ ./ ../ $HOME/ $env:USERPROFILE/ 开头、且路径里有 skill(s) 一段。
# 前面的 (?<![\w.]) 防止从 "github.com/acme/demo-skill" 的点上起匹配。
PATH_TOKEN = re.compile(
    r"(?<![\w.])(?:~|\.{1,2}|\$HOME|\$env:USERPROFILE)/[\w./\\$:{}-]*skills?\b[\w./-]*",
    re.IGNORECASE)


# 触发短语比对前先去掉空白与各式引号；drop_sep 再去掉并列分隔符。
# README 表格里的「排版 / 字体」与 description 里的「排版」「字体」只是写法不同，算一致。
_QUOTES = re.compile(r"[\s`「」『』\"'“”‘’]+")
_SEPS = re.compile(r"[/／、，,]")


def norm_phrase(s: str, drop_sep: bool = False) -> str:
    s = _QUOTES.sub("", s)
    return _SEPS.sub("", s) if drop_sep else s


def phrase_found(needle: str, hay: str) -> bool:
    """短语是否在 description 里找得到（容许排版差异，不容许内容差异）。"""
    if not norm_phrase(needle):
        return True
    return (norm_phrase(needle) in norm_phrase(hay)
            or norm_phrase(needle, True) in norm_phrase(hay, True))


def platform_subsection_text(s45, display: str) -> str:
    """把第 4/5 节里属于某平台的 ### 小节正文拼起来（标题含平台名即算）。

    找不到该平台的小节时返回空串，由调用方回退到整段正文。
    """
    chunks = []
    for _, sec in s45:
        raw = sec["body"].split("\n")
        safe = _lib.strip_code_blocks(sec["body"]).split("\n")
        on, cur = False, []
        for rl, sl in zip(raw, safe):
            m = re.match(r"^#{3,6}\s+(.+?)\s*$", sl)
            if m:
                if on:
                    chunks.append("\n".join(cur))
                on, cur = display.lower() in m.group(1).lower(), []
                continue
            if on:
                cur.append(rl)
        if on:
            chunks.append("\n".join(cur))
    return "\n".join(chunks)


def path_tokens(text: str) -> list[str]:
    """按出现顺序取出看着像安装路径的写法，去重。"""
    seen, out = set(), []
    for t in PATH_TOKEN.findall(text):
        t = t.rstrip("`.,;:，。；、)")
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def check_readme(root, fname, ctx, findings):
    text = (root / fname).read_text(encoding="utf-8")
    secs = _lib.split_sections(text)
    tag = ":" + fname

    # —— 第 1 节：H1 / 包含 name / 互链 / 快速安装行（标准第 1 节里脚本能检查的项目）——
    h1 = next((s for s in secs if s["level"] == 1), None)
    if h1 is None:
        findings.append(F("S1-H1" + tag, "fail", fname, 1, "没有大标题（# 一级标题）"))
    else:
        findings.append(F("S1-H1" + tag, "pass", fname, h1["start_line"], h1["title"]))
        if ctx["name"].lower() in h1["title"].lower():
            findings.append(F("S1-H1-NAME" + tag, "pass", fname, h1["start_line"], ""))
        else:
            findings.append(F("S1-H1-NAME" + tag, "fail", fname, h1["start_line"],
                              f"大标题未包含 name「{ctx['name']}」"))
        if "npx skills add" in h1["body"]:
            findings.append(F("S1-QUICKINSTALL" + tag, "pass", fname, h1["start_line"], ""))
        else:
            findings.append(F("S1-QUICKINSTALL" + tag, "fail", fname, h1["start_line"],
                              "标题区缺快速安装行（npx skills add …）"))
    other = "README.md" if fname == "README.en.md" else "README.en.md"
    link_re = r"\(\.?/?" + re.escape(other) + r"\)"
    if (root / other).is_file() or re.search(link_re, text):
        ok = re.search(link_re, text) and (root / other).is_file()
        findings.append(F("S1-XLINK" + tag, "pass" if ok else "fail", fname, 1,
                          "" if ok else f"与 {other} 的互链缺失或指向不存在的文件"))

    # —— 第 2–8 节：存在性 + 各节里脚本能检查的项目 ——
    matched = _match_sections(secs, ctx["rules"]["sections"])
    for rs in ctx["rules"]["sections"]:
        sid = rs["id"].upper()
        status, sec = matched[rs["id"]]
        if status == "miss":
            findings.append(F(sid + "-EXISTS" + tag, "fail", fname, 1,
                              f"缺节：{rs['zh']} / {rs['en']}"))
            continue
        if status == "suspect":
            findings.append(F(sid + "-EXISTS" + tag, "suspect", fname, sec["start_line"],
                              f"标题「{sec['title']}」看着像是「{rs['zh']}」，请模型复查"))
        else:
            findings.append(F(sid + "-EXISTS" + tag, "pass", fname, sec["start_line"], ""))
        # 标题拿不准的节，子项照查，但结果一律降为拿不准（复查后再判）
        cap = (lambda ok: "pass" if ok else "fail") if status == "pass" else (lambda ok: "suspect")
        note = "" if status == "pass" else "（本节标题拿不准，复查后再判）"
        body, ln = sec["body"], sec["start_line"]
        if rs["id"] == "s2":
            ok = ("✅" in body) and ("❌" in body)
            findings.append(F("S2-LISTS" + tag, cap(ok), fname, ln,
                              ("" if ok else "✅/❌ 两个清单不齐（标准第 2 节的要求）") + note))
        elif rs["id"] == "s3":
            ok = "```" in body
            findings.append(F("S3-CODE" + tag, cap(ok), fname, ln,
                              ("" if ok else "缺终端演示代码块") + note))
        elif rs["id"] == "s4":
            missing = [p["display"] for p in ctx["platforms"].values()
                       if p["display"] not in body]
            findings.append(F("S4-3NAMES" + tag, cap(not missing), fname, ln,
                              ("" if not missing else "Runtime 节缺平台：" + "、".join(missing)) + note))
        elif rs["id"] == "s5":
            ok = "npx skills add" in body
            findings.append(F("S5-ONECLICK" + tag, cap(ok), fname, ln,
                              ("" if ok else "安装节缺一键安装（npx skills add）") + note))
            missing = [p["display"] for p in ctx["platforms"].values()
                       if p["display"] not in body]
            findings.append(F("S5-3MANUAL" + tag, cap(not missing), fname, ln,
                              ("" if not missing else "手动小节缺平台：" + "、".join(missing)) + note))
        elif rs["id"] == "s6":
            rows = [x for x in body.split("\n") if x.strip().startswith("|")]
            sep = next((i for i, x in enumerate(rows)
                        if re.fullmatch(r"[|\s:-]+", x.strip())), None)
            data_rows = rows[sep + 1:] if sep is not None else rows
            phrases = []
            for x in data_rows:
                for cell in x.strip().strip("|").split("|"):
                    t = cell.strip().strip("`").strip()
                    if t and not re.fullmatch(r"[-: ]+", t):
                        phrases.append(t)
            missing = [t for t in phrases if not phrase_found(t, ctx["description"])]
            if not phrases:
                findings.append(F("S6-PHRASES" + tag, cap(False), fname, ln, "触发节没有短语表" + note))
            elif missing:
                findings.append(F("S6-PHRASES" + tag, cap(False), fname, ln,
                                  "这些短语在 SKILL.md description 里找不到：" + "；".join(missing) + note))
            else:
                findings.append(F("S6-PHRASES" + tag, cap(True), fname, ln, "" + note))
        elif rs["id"] == "s8":
            kw = next((k for k in ctx["rules"]["license_keywords"] if k in body), None)
            lic_text = ctx["license_text"]
            if kw and lic_text and kw in lic_text:
                findings.append(F("S8-MATCH" + tag, cap(True), fname, ln, kw + note))
            else:
                findings.append(F("S8-MATCH" + tag, cap(False), fname, ln,
                                  "README 所称许可证与 LICENSE 文件对不上（或未写明）" + note))

    # —— 路径与对照表一致（第 4/5 节的要求，合并查；标题拿不准的节参与，但不直接判成问题）——
    s45 = [matched[k] for k in ("s4", "s5")]
    s45 = [(st, sec) for st, sec in s45 if sec is not None]
    bodies = "\n".join(sec["body"] for _, sec in s45)
    any_suspect = any(st == "suspect" for st, _ in s45)
    if bodies:
        wrong, silent = [], []
        for p in ctx["platforms"].values():
            ptext = platform_subsection_text(s45, p["display"]) or bodies
            if any(a.rstrip("/") in ptext for a in p["accepted_dirs"]):
                continue
            cands = path_tokens(ptext)
            if cands:
                wrong.append(f"{p['display']}（写的是 {'、'.join(cands)}）")
            else:
                silent.append(p["display"])
        parts = []
        if wrong:
            parts.append("这些平台写的安装路径不在对照表里：" + "；".join(wrong))
        if silent:
            parts.append("这些平台的小节里没写安装路径：" + "、".join(silent))
        if not parts:
            findings.append(F("S45-PATHS" + tag, "pass", fname, 1, ""))
        elif any_suspect:
            findings.append(F("S45-PATHS" + tag, "suspect", fname, 1,
                              "本节标题还没复查，路径核对先不下结论；" + "　".join(parts)))
        else:
            findings.append(F("S45-PATHS" + tag, "fail", fname, 1, "　".join(parts)))

        # 某平台小节里除了对的路径之外，还写了一条不在对照表里的工具目录路径。
        # 这类写法可能是笔误，也可能是在说明别的事，所以只标 suspect，由人复查。
        lines = text.split("\n")
        odd = []
        for p in ctx["platforms"].values():
            sub = platform_subsection_text(s45, p["display"])
            for t in path_tokens(sub):
                if not re.search(r"(?:^|/)\.[A-Za-z]", t):
                    continue          # 不带工具目录（如 ./skills/<name>）的是仓库布局，不算
                if any(a.rstrip("/") in t for a in p["accepted_dirs"]):
                    continue
                ln = next((i + 1 for i, x in enumerate(lines) if t in x), 1)
                odd.append((ln, f"{p['display']} 小节第 {ln} 行写了 {t}"))
        if odd:
            findings.append(F("S45-ODDPATH" + tag, "suspect", fname, odd[0][0],
                              "这些路径不在对照表里，请确认是不是写错了：" + "；".join(d for _, d in odd)))
        else:
            findings.append(F("S45-ODDPATH" + tag, "pass", fname, 1, ""))

    # —— 仓库地址一致（第 5 节的要求）：只查安装命令，正文里引用他人仓库的链接不算 ——
    repos = set(re.findall(r"npx skills add\s+(?:-\S+\s+)*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", text))
    repos |= set(re.findall(
        r"git clone\s+(?:https?://)?(?:www\.)?github\.com[:/]([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", text))
    repos = {r.rstrip(".").removesuffix(".git").lower() for r in repos}
    if len(repos) == 1:
        findings.append(F("REPO-CONSISTENT" + tag, "pass", fname, 1, repos.pop()))
    elif not repos:
        findings.append(F("REPO-CONSISTENT" + tag, "fail", fname, 1,
                          "安装命令里没有仓库地址（npx skills add / git clone）"))
    else:
        findings.append(F("REPO-CONSISTENT" + tag, "fail", fname, 1,
                          "安装命令里的仓库地址不一致：" + "、".join(sorted(repos))))


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--pick")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    rules = _yaml_min.load(RULES_DIR / "readme.yaml")
    plat = _yaml_min.load(RULES_DIR / "platforms.yaml")
    port = _yaml_min.load(RULES_DIR / "portability.yaml")
    md_rules = _yaml_min.load(RULES_DIR / "skillmd.yaml")

    skill_md, code = locate(root, args.pick)
    if skill_md is None:
        return code

    try:
        fm = _lib.parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    except ValueError as e:
        print(f"错误：SKILL.md 头部信息无法解析：{e}")
        return 4
    git = git_state(root)
    if git is None:
        print("错误：本机没有 git，请先安装。")
        return 5
    findings = []
    lic = check_structure(root, skill_md, fm, plat, findings)
    check_description(root, skill_md, fm, md_rules, findings)
    check_body(root, skill_md, md_rules, findings)
    check_portability(root, skill_md, port, findings)
    ctx = {
        "name": str(fm.get("name", "")),
        "description": str(fm.get("description", "")),
        "rules": rules,
        "platforms": plat["platforms"],
        "license_text": lic.read_text(encoding="utf-8") if lic else "",
    }
    for fname in ("README.md", "README.en.md"):
        if (root / fname).is_file():
            check_readme(root, fname, ctx, findings)

    summary = {s: sum(1 for f in findings if f["status"] == s)
               for s in ("pass", "fail", "suspect")}
    print(f"体检完成：{summary['pass']} 项通过，{summary['fail']} 项必须修的问题，"
          f"{summary['suspect']} 项拿不准（要人复查）。")
    for f in findings:
        if f["status"] != "pass":
            print(f"[{f['status'].upper()}] {f['rule']}  {f['file']}:{f['line']}  {f['detail']}")
    print("git 状态：" + git + "（" + GIT_NOTES[git] + "）")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"root": str(root), "skill_md": skill_md.relative_to(root).as_posix(),
             "name": ctx["name"], "git": git, "findings": findings, "summary": summary},
            ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
