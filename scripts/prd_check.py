#!/usr/bin/env python3
"""PRD 結構檢查（pm-field-guide）。

讀入一份 Markdown 寫的 PRD，檢查「結構與機械性問題」：該有的段落在不在、
編號需求對不對得上驗收條件、有沒有模糊用語、未填的佔位、沒有數字的指標句。
全部是關鍵字與格式比對，不判斷內容寫得好不好；內容品質仍要由人或 AI
依 PRD 撰寫指南、驗收條件指南的「品質檢查」逐條審。

輸入：Markdown 檔路徑（UTF-8，可含 BOM）。程式碼區塊（``` 圍起來的內容）不列入檢查。

結構檢查（每項回報 通過／部分／缺少，第 10 項缺少只算「建議」）：
  1. 問題或背景　2. 目標　3. 非目標　4. 範圍劃分（In／Out／Later）
  5. 編號的功能需求（FR-01、REQ-1、US-01 這類）
  6. 驗收條件，以及每條編號需求是否找得到對應的驗收條件
  7. 成功指標（主指標）與護欄指標，分開回報
  8. 異常或邊界情境　9. 未決事項（含負責人與日期）　10. 變更紀錄或版本

「標題位置」指 Markdown 標題（#）、整行粗體的小標、行首的「標籤：」、30 字以內的表格儲存格。
關鍵字只出現在內文時，多數項目回報「部分」。

需求與驗收條件的對應規則：需求編號所在的「同一表格列」或「同一段落」
（清單項目連同它縮排的子項目算一段；編號寫在標題時，整個小節算一段）
出現 AC 編號或 Given／When／Then（假設／當／則）即算有對應。

模糊用語的規則：
  - 一律列出：盡快、儘快、適當、優化體驗、提升體驗、使用者友善、易用、之後補、待補、
    TBD、TBC、ASAP、user-friendly、as needed、etc.
  - 只在「需求或驗收條件的行」才列出（避免一般敘述誤報）：快速、很快、友善、好用、方便、
    直覺、順暢、流暢、簡單、正確、正常、fast、quick、easy、simple、intuitive、properly、correctly
    「需求或驗收條件的行」＝該行有需求編號（FR-／REQ-／US-）、AC 或 R 編號、
    Given／When／Then，或位在標題含「需求／驗收／Requirements／Acceptance／User story」的段落內。
    「不正確」「不正常」、「正常流程」這類寫法，以及整格只寫「正常」的分類欄不算。

用法範例：
  python prd_check.py prd.md
  python prd_check.py prd.md --json
  python prd_check.py prd.md --strict      # 有任何「缺少」項時 exit code 1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# 共用：錯誤、參數解析
# ---------------------------------------------------------------------------

class InputError(Exception):
    """使用者輸入有誤；main() 會印出繁中訊息並以 exit code 2 結束。"""


class _ZhHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, prefix or "用法：")


_ARGPARSE_ZH = [
    ("the following arguments are required", "缺少必要參數"),
    ("unrecognized arguments", "無法辨識的參數"),
    ("expected one argument", "需要提供一個值"),
    ("invalid choice", "無效的選項"),
    ("argument ", "參數 "),
]


class _ZhArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _ZhHelpFormatter)
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self._positionals.title = "必要參數"
        self._optionals.title = "選項"
        self.add_argument("-h", "--help", action="help", help="顯示這份說明後結束")

    def error(self, message):
        for en, zh in _ARGPARSE_ZH:
            message = message.replace(en, zh)
        self.print_usage(sys.stderr)
        self.exit(2, f"錯誤：{message}\n")


def read_markdown(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise InputError(f"找不到檔案：{path}")
    try:
        text = p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise InputError(f"檔案不是 UTF-8 編碼：{path}。請用編輯器另存為 UTF-8 後再試。")
    except OSError as e:
        raise InputError(f"無法讀取檔案：{path}（{e.strerror}）")
    if not text.strip():
        raise InputError(f"檔案是空的：{path}")
    return text


# ---------------------------------------------------------------------------
# Markdown 逐行解析
# ---------------------------------------------------------------------------

LABEL_LEVEL = 7  # a bold-only line acts as a pseudo heading below h6
CELL_MAX = 30    # table cells up to this length count as a "label position"


@dataclass
class Line:
    no: int                      # 1-based line number
    raw: str
    kind: str = "text"           # blank / fence / code / heading / label / table / sep / text
    level: int = 0               # heading level (1-6), LABEL_LEVEL for bold-only lines
    title: str = ""              # heading or label text
    cells: list = field(default_factory=list)
    is_header: bool = False      # table header row
    header: list = field(default_factory=list)  # header cells of the table this row belongs to
    indent: int = 0
    is_list: bool = False
    headings: tuple = ()         # titles of enclosing headings / labels


_RE_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_RE_BOLD_ONLY = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*|__)([^*_].*?)(?:\*\*|__)\s*[:：]?\s*$")
_RE_BOLD_PREFIX = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:\*\*|__)([^*]+?)(?:\*\*|__)")
_RE_LINE_LABEL = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?([^：:|*]{1,20})[:：]")
_RE_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_RE_SEP_CELL = re.compile(r"^:?-+:?$")
_RE_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def _split_cells(s: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", s.strip())
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [c.strip() for c in parts]


def parse_lines(text: str) -> list[Line]:
    """把 Markdown 拆成逐行結構（標題、粗體小標、表格列、一般文字、程式碼區塊）。"""
    lines: list[Line] = []
    fence = None
    for no, raw in enumerate(text.splitlines(), start=1):
        ln = Line(no=no, raw=raw, indent=len(raw) - len(raw.lstrip(" \t")))
        m = _RE_FENCE.match(raw)
        if fence:
            ln.kind = "code"
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                ln.kind, fence = "fence", None
        elif m:
            ln.kind, fence = "fence", m.group(1)
        elif not raw.strip():
            ln.kind = "blank"
        elif _RE_HEADING.match(raw):
            h = _RE_HEADING.match(raw)
            ln.kind, ln.level, ln.title = "heading", len(h.group(1)), _plain(h.group(2))
        elif raw.strip().startswith("|"):
            ln.cells = [_plain(c) for c in _split_cells(raw)]
            ln.kind = "sep" if ln.cells and all(_RE_SEP_CELL.match(c.replace(" ", "")) for c in ln.cells) else "table"
        elif _RE_BOLD_ONLY.match(raw):
            ln.kind, ln.level, ln.title = "label", LABEL_LEVEL, _plain(_RE_BOLD_ONLY.match(raw).group(1))
        else:
            ln.is_list = bool(_RE_LIST.match(raw))
        lines.append(ln)

    # table headers and heading stack
    stack: list[tuple[int, str]] = []
    header: list[str] = []
    for i, ln in enumerate(lines):
        if ln.kind in ("heading", "label"):
            while stack and stack[-1][0] >= ln.level:
                stack.pop()
            stack.append((ln.level, ln.title))
        ln.headings = tuple(t for _, t in stack)
        if ln.kind == "table":
            if i + 1 < len(lines) and lines[i + 1].kind == "sep":
                ln.is_header, header = True, ln.cells
            ln.header = header
        elif ln.kind != "sep":
            header = []
    return lines


def _plain(s: str) -> str:
    """Strip inline emphasis / code marks so keywords match regardless of styling."""
    return re.sub(r"\*\*|__|`", "", s).strip()


def section_end(lines: list[Line], i: int) -> int:
    lvl = lines[i].level
    for j in range(i + 1, len(lines)):
        if lines[j].kind in ("heading", "label") and lines[j].level <= lvl:
            return j
    return len(lines)


def context_range(lines: list[Line], i: int) -> tuple[int, int]:
    """Section that line i belongs to (its own section if i is a heading / label)."""
    if lines[i].kind in ("heading", "label"):
        return i, section_end(lines, i)
    for j in range(i - 1, -1, -1):
        if lines[j].kind in ("heading", "label"):
            return j, section_end(lines, j)
    a = b = i
    while a > 0 and lines[a - 1].kind not in ("blank",):
        a -= 1
    while b + 1 < len(lines) and lines[b + 1].kind not in ("blank",):
        b += 1
    return a, b + 1


def range_text(lines: list[Line], a: int, b: int) -> str:
    return "\n".join(l.raw for l in lines[a:b] if l.kind not in ("code", "fence"))


def candidates(ln: Line) -> list[tuple[str, str]]:
    """Label positions on a line: heading, bold label, leading「標籤：」, short table cells."""
    if ln.kind in ("heading", "label"):
        return [(ln.kind, ln.title)]
    if ln.kind == "table":
        return [("cell", c) for c in ln.cells if 0 < len(c) <= CELL_MAX]
    if ln.kind == "text":
        out = []
        m = _RE_BOLD_PREFIX.match(ln.raw)
        if m:
            out.append(("label", m.group(1).strip()))
        m = _RE_LINE_LABEL.match(ln.raw)
        if m:
            out.append(("label", _plain(m.group(1))))
        return out
    return []


# ---------------------------------------------------------------------------
# 關鍵字
# ---------------------------------------------------------------------------

def _en(words: str) -> str:
    """English alternation guarded by ASCII-letter boundaries (\\b fails next to CJK)."""
    return rf"(?<![A-Za-z])(?:{words})(?![A-Za-z])"


def _rx(zh: str, en: str) -> re.Pattern:
    return re.compile(f"{zh}|{_en(en)}" if zh else _en(en), re.I)


RX_OPEN = _rx("未決|待決|待確認|待釐清", r"open\s+(?:questions?|issues?|items?)|unresolved")
RX_FAQ = _rx("常見問題", r"faq")
RX_BG = _rx("問題|背景", r"problems?|background")
RX_NONGOAL_STRONG = _rx("非目標|不做", r"non[- ]?goals?|out[- ]of[- ]scope|not\s+doing|won'?t\s+do")
RX_NONGOAL_WEAK = _rx("非目標|這版不做|本版不做|這一版不做", r"non[- ]?goals?|out[- ]of[- ]scope")
RX_NONGOAL_STRIP = _rx("非目標", r"non[- ]?goals?")
RX_GOAL = _rx("目標(?!值|上線|日|使用者|用戶|客群|對象|族群|市場)", r"goals?|objectives?")
RX_IN = re.compile(rf"^in(?![A-Za-z])|{_en(r'in[- ]scope')}|範圍內|這版做|本版做", re.I)
RX_OUT = re.compile(rf"^out(?![A-Za-z])|{_en(r'out[- ]of[- ]scope')}|範圍外", re.I)
RX_LATER = re.compile(r"^later(?![A-Za-z])|之後評估|之後再|下一版|後續評估", re.I)
RX_SCOPE = _rx("範圍", r"scope")
RX_REQ_HEADING = _rx("功能需求|需求(?!來源)|使用者故事", r"requirements?|user\s+stor(?:y|ies)")
RX_REQ_AC_SECTION = _rx("需求(?!來源)|驗收|使用者故事", r"requirements?|acceptance|user\s+stor(?:y|ies)")
RX_AC_WORD = _rx("驗收條件|驗收標準", r"acceptance\s+criteri(?:a|on)")
RX_SUCCESS = _rx("主指標|主要指標|成功指標|北極星", r"success\s+metrics?|primary\s+metrics?|north\s+star")
RX_GUARD = _rx("護欄", r"guardrails?")
RX_EDGE = _rx("異常|例外|邊界|錯誤處理", r"edge\s+cases?|errors?|exceptions?")
RX_OWNER = _rx("負責人|負責|誰決定|決定者", r"owner|assignee|dri")
RX_DUE = _rx("期限|日期|截止", r"due|deadline|date")
RX_CHANGELOG = _rx("變更紀錄|變更記錄|修訂紀錄|修訂記錄|版本", r"changelog|change\s+log|revisions?|version(?:\s+history)?")

# 主指標四要素（PRD 撰寫指南的品質檢查）
METRIC_FIELDS = [
    ("基準值", _rx("基準|現況值|目前值", r"baseline")),
    ("目標值", _rx("目標", r"target")),
    ("量測方式", _rx("量測|衡量|測量|事件|埋點|資料來源", r"measure(?:ment|d)?|events?|tracking|source")),
    ("觀察期", _rx("觀察|期間|上線後", r"period|window|timeframe")),
]
# 異常路徑三種（PRD 撰寫指南的品質檢查）
EDGE_KINDS = [
    ("失敗", _rx("失敗|逾時|超時", r"fail(?:s|ed|ure)?|time[- ]?outs?")),
    ("無權限", _rx("權限|未登入|未授權", r"permissions?|unauthori[sz]ed|forbidden|access\s+denied")),
    ("取消", _rx("取消|中斷|放棄", r"cancel(?:s|led|ed|lation)?|abort(?:s|ed)?")),
]

_ID_L, _ID_R = r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9_])"
RX_REQ_ID = re.compile(rf"{_ID_L}(?:FR|REQ|US|STORY)[-_]?\d+{_ID_R}")
RX_AC_ID = re.compile(rf"{_ID_L}AC[-_]?\d+{_ID_R}")
RX_RULE_ID = re.compile(rf"{_ID_L}R-\d+{_ID_R}")
RX_STARTS_REQ = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:\[[ xX]\]\s*)?(?:\*\*|__|`)?\s*(?:FR|REQ|US|STORY)[-_]?\d+" + _ID_R
)
RX_GWT_EN = re.compile(rf"{_en('given')}.*?{_en('when')}.*?{_en('then')}", re.I | re.S)
RX_GWT_ZH = re.compile(r"(?:假設|給定|假如).*?當.*?(?:則|那麼)", re.S)
RX_GWT_START = re.compile(
    rf"^\s*(?:[-*+]\s+)?(?:\*\*)?(?:{_en('given|when|then')}|假設|給定|當|則|那麼)", re.I
)
RX_GWT_OPEN = re.compile(rf"^\s*(?:[-*+]\s+)?(?:\*\*)?(?:{_en('given')}|假設|給定)", re.I)
RX_COL_GIVEN = _rx("假設|前置", "given")
RX_COL_WHEN = _rx("當|動作", "when")
RX_COL_THEN = _rx("則|結果", "then")
RX_EMPTY_CELL = re.compile(r"^(?:_+|-+|—+|\?+|？+|tbd|tbc|待定|待補|未定|n/?a)?$", re.I)

# 模糊用語（經驗清單，依團隊用語而異）
VAGUE_ALWAYS = re.compile(
    r"盡快|儘快|適當|(?:優化|提升|改善)(?:使用者|用戶)?體驗|使用者友善|易用|之後補|待補|"
    + _en(r"TBD|TBC|ASAP|user[- ]friendly|as\s+needed")
    + r"|(?<![A-Za-z])etc\.?(?![A-Za-z])",
    re.I,
)
VAGUE_CONTEXT = re.compile(
    r"快速|很快|友善|好用|方便|直覺|順暢|流暢|簡單|(?<!不)正確|(?<!不)正常(?!流程|情境|路徑|案例)|"
    + _en(r"fast|quick(?:ly)?|easy|easily|simple|intuitive|properly|correctly"),
    re.I,
)
RX_PLACEHOLDER = re.compile(rf"_{{4,}}|{_ID_L}TODO{_ID_R}|(?<![A-Za-z])XXX(?![A-Za-z])")
RX_HR = re.compile(r"^\s*[_\-*\s]+$")
RX_METRIC_VERB = re.compile(
    r"提升|降低|改善|增加|減少|" + _en(r"increas(?:e|es|ed|ing)|reduc(?:e|es|ed|ing)|improv(?:e|es|ed|ing)|decreas(?:e|es|ed|ing)"),
    re.I,
)
RX_STRIP_IDS = re.compile(r"[A-Za-z]+[-_]?\d+|^\s*\d+[.)、]")
RX_NUMBER = re.compile(r"[0-9０-９]|[一二兩三四五六七八九十百千萬半]\s*(?:倍|成|％|%|個百分點)")

MAX_ISSUES_SHOWN = 30


# ---------------------------------------------------------------------------
# 結構檢查
# ---------------------------------------------------------------------------

def strong_hits(lines, rx, kinds=("heading", "label", "cell"), prep=None):
    """Lines where the keyword sits in a label position. Returns [(line_index, text)]."""
    hits = []
    for i, ln in enumerate(lines):
        for kind, text in candidates(ln):
            if kind not in kinds:
                continue
            t = prep(text) if prep else text
            if t and rx.search(t):
                hits.append((i, text))
                break
    return hits


def body_hits(lines, rx):
    return [(i, ln.raw.strip()) for i, ln in enumerate(lines)
            if ln.kind not in ("code", "fence", "blank", "sep") and rx.search(ln.raw)]


def _evidence(lines, hits, limit=3):
    return [{"line": lines[i].no, "text": snippet(t, 40)} for i, t in hits[:limit]]


def _check(key, num, name, status, evidence=None, detail=""):
    return {"key": key, "no": num, "name": name, "status": status,
            "evidence": evidence or [], "detail": detail}


def _simple(lines, key, num, name, rx, kinds, prep=None, weak_rx=None, missing="缺少",
            weak_detail="只在內文提到，沒有獨立的段落或欄位。", miss_detail=""):
    hits = strong_hits(lines, rx, kinds, prep)
    if hits:
        return _check(key, num, name, "通過", _evidence(lines, hits)), hits
    if weak_rx is not None:
        weak = body_hits(lines, weak_rx)
        if weak:
            return _check(key, num, name, "部分", _evidence(lines, weak), weak_detail), []
    return _check(key, num, name, missing, [], miss_detail), []


def build_units(lines: list[Line]) -> list[tuple[int, int]]:
    """unit[i] = (start, end) of the table row / paragraph / heading section holding line i."""
    units: list[tuple[int, int]] = [(i, i + 1) for i in range(len(lines))]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.kind in ("heading", "label"):
            units[i] = (i, section_end(lines, i))
            i += 1
        elif ln.kind == "text":
            j = i
            while j < len(lines) and lines[j].kind == "text":
                j += 1
            start = i
            for k in range(i + 1, j + 1):
                boundary = k == j
                if not boundary:
                    cur, first = lines[k], lines[start]
                    # "- When ..." / "- Then ..." continue the scenario opened by "- Given ..."
                    cont = RX_GWT_START.match(cur.raw) and not RX_GWT_OPEN.match(cur.raw)
                    if cur.indent <= first.indent and not cont and (
                        (first.is_list and cur.is_list) or RX_STARTS_REQ.match(cur.raw)
                    ):
                        boundary = True
                if boundary:
                    for x in range(start, k):
                        units[x] = (start, k)
                    start = k
            i = j
        else:
            i += 1
    return units


def _has_gwt(text: str) -> bool:
    return bool(RX_GWT_EN.search(text) or RX_GWT_ZH.search(text))


def _row_gwt_by_header(ln: Line) -> bool:
    """Row sits in a table with Given / When / Then columns and all three cells are filled."""
    if ln.kind != "table" or ln.is_header or not ln.header:
        return False
    idx = []
    for rx in (RX_COL_GIVEN, RX_COL_WHEN, RX_COL_THEN):
        found = [n for n, h in enumerate(ln.header) if rx.search(h)]
        if not found:
            return False
        idx.append(found[0])
    return all(n < len(ln.cells) and not RX_EMPTY_CELL.match(ln.cells[n]) for n in idx)


def unit_has_ac(lines, unit) -> bool:
    a, b = unit
    text = range_text(lines, a, b)
    if RX_AC_ID.search(text) or _has_gwt(text):
        return True
    return any(_row_gwt_by_header(lines[x]) for x in range(a, b))


def check_requirements(lines):
    occ: dict[str, list[int]] = {}
    for i, ln in enumerate(lines):
        if ln.kind in ("code", "fence", "blank", "sep"):
            continue
        for m in RX_REQ_ID.finditer(ln.raw):
            occ.setdefault(m.group(0), []).append(i)
    name = "編號的功能需求"
    if occ:
        ids = list(occ)
        ev = [{"line": lines[v[0]].no, "text": k} for k, v in list(occ.items())[:3]]
        return _check("requirements", "5", name, "通過", ev, f"共 {len(ids)} 條：{_join_ids(ids)}"), occ
    hits = strong_hits(lines, RX_REQ_HEADING, ("heading", "label"))
    if hits:
        return _check("requirements", "5", name, "部分", _evidence(lines, hits),
                      "有需求段落，但沒有 FR-01、REQ-1、US-01 這類編號。"), occ
    return _check("requirements", "5", name, "缺少", [], "找不到 FR-01、REQ-1、US-01 這類編號。"), occ


def _join_ids(ids, limit=12):
    return "、".join(ids[:limit]) + (f" 等 {len(ids)} 條" if len(ids) > limit else "")


def check_acceptance(lines, occ):
    units = build_units(lines)
    name = "驗收條件"
    ac_ids, ac_lines, gwt_units = [], [], set()
    for i, ln in enumerate(lines):
        if ln.kind in ("code", "fence", "blank", "sep"):
            continue
        found = RX_AC_ID.findall(ln.raw)
        for a in found:
            if a not in ac_ids:
                ac_ids.append(a)
        word = RX_AC_WORD.search(ln.raw)
        if found or word:
            ac_lines.append((i, found[0] if found else word.group(0)))
        if ln.kind in ("text", "table"):
            u = units[i]
            if _has_gwt(range_text(lines, *u)) or _row_gwt_by_header(ln):
                first_seen = u not in gwt_units
                gwt_units.add(u)
                if first_seen and not found and not word:
                    ac_lines.append((i, "Given／When／Then"))
    covered = [rid for rid, idxs in occ.items() if any(unit_has_ac(lines, units[i]) for i in idxs)]
    uncovered = [rid for rid in occ if rid not in covered]
    info = {"count": len(occ), "ids": list(occ), "with_ac": len(covered), "without_ac": uncovered,
            "ac_ids": len(ac_ids), "gwt_blocks": len(gwt_units)}
    if not ac_lines:
        return _check("acceptance", "6", name, "缺少", [],
                      "找不到 AC 編號、「驗收條件」或 Given／When／Then。"), info
    found_txt = f"AC 編號 {len(ac_ids)} 個、Given／When／Then {len(gwt_units)} 處。"
    ev = _evidence(lines, ac_lines)
    if not occ:
        return _check("acceptance", "6", name, "部分", ev,
                      found_txt + "沒有編號需求，無法核對需求與驗收條件的對應。"), info
    if uncovered:
        return _check("acceptance", "6", name, "部分", ev,
                      f"{found_txt}{len(covered)}／{len(occ)} 條需求有對應；缺：{_join_ids(uncovered)}。"), info
    return _check("acceptance", "6", name, "通過", ev,
                  f"{found_txt}{len(covered)}／{len(occ)} 條需求有對應。"), info


def check_scope(lines):
    kinds = ("heading", "label", "cell")
    hin, hout, hlater = (strong_hits(lines, rx, kinds) for rx in (RX_IN, RX_OUT, RX_LATER))
    name = "範圍劃分（In／Out／Later）"
    later = "有 Later 欄。" if hlater else "沒有 Later（之後評估）欄，可視需要補。"
    if hin and hout:
        return _check("scope", "4", name, "通過", _evidence(lines, [hin[0], hout[0]] + hlater[:1]), later)
    if hin or hout:
        side = "只找到 In（範圍內），沒有 Out（範圍外）。" if hin else "只找到 Out（範圍外），沒有 In（範圍內）。"
        return _check("scope", "4", name, "部分", _evidence(lines, hin or hout), side)
    hs = strong_hits(lines, RX_SCOPE, ("heading", "label"))
    if hs:
        return _check("scope", "4", name, "部分", _evidence(lines, hs),
                      "有範圍段落，但沒有分成 In／Out（範圍內／範圍外）。")
    return _check("scope", "4", name, "缺少")


def _contexts_text(lines, hits) -> str:
    seen, parts = set(), []
    for i, _ in hits:
        r = context_range(lines, i)
        if r not in seen:
            seen.add(r)
            parts.append(range_text(lines, *r))
    return "\n".join(parts)


def check_success(lines):
    c, hits = _simple(lines, "success_metric", "7a", "成功指標（主指標）", RX_SUCCESS,
                      ("heading", "label", "cell"), weak_rx=RX_SUCCESS)
    if hits:
        text = _contexts_text(lines, hits)
        lacking = [n for n, rx in METRIC_FIELDS if not rx.search(text)]
        if lacking:
            c["status"] = "部分"
            c["detail"] = "同一段落找不到：" + "、".join(lacking) + "（指南要求基準值、目標值、量測方式、觀察期四項齊全）。"
    return c


def check_edge(lines):
    c, hits = _simple(lines, "edge_cases", "8", "異常或邊界情境", RX_EDGE,
                      ("heading", "label", "cell"), weak_rx=RX_EDGE)
    if hits:
        text = _contexts_text(lines, hits)
        lacking = [n for n, rx in EDGE_KINDS if not rx.search(text)]
        if lacking:
            c["status"] = "部分"
            c["detail"] = "相關段落找不到：" + "、".join(lacking) + "（指南要求至少涵蓋失敗、無權限、取消三種）。"
    return c


def check_open(lines):
    name = "未決事項（含負責人與日期）"
    hits = strong_hits(lines, RX_OPEN, ("heading", "label"))
    if not hits:
        return _check("open_questions", "9", name, "缺少")
    ev = _evidence(lines, hits)
    a, b = context_range(lines, hits[0][0])
    text = range_text(lines, a + 1, b)
    lacking = [n for n, rx in (("負責人", RX_OWNER), ("日期", RX_DUE)) if not rx.search(text)]
    if lacking:
        return _check("open_questions", "9", name, "部分", ev, "段落內找不到欄位：" + "、".join(lacking) + "。")
    rows = bad = 0
    for x in range(a + 1, b):
        ln = lines[x]
        if ln.kind != "table" or ln.is_header or not ln.header:
            continue
        oi = [n for n, h in enumerate(ln.header) if RX_OWNER.search(h)]
        di = [n for n, h in enumerate(ln.header) if RX_DUE.search(h)]
        if not oi or not di:
            continue
        rows += 1
        if any(n >= len(ln.cells) or RX_EMPTY_CELL.match(ln.cells[n]) for n in (oi[0], di[0])):
            bad += 1
    if bad:
        return _check("open_questions", "9", name, "部分", ev, f"{rows} 條未決事項中有 {bad} 條的負責人或日期是空的。")
    detail = f"{rows} 條未決事項都填了負責人與日期。" if rows else "有負責人與日期欄位。"
    return _check("open_questions", "9", name, "通過", ev, detail)


def run_structure_checks(lines):
    def no_open(t):
        return "" if RX_OPEN.search(t) or RX_FAQ.search(t) else t

    checks = []
    checks.append(_simple(lines, "background", "1", "問題或背景", RX_BG, ("heading", "label"), prep=no_open)[0])
    checks.append(_simple(lines, "goals", "2", "目標", RX_GOAL, ("heading", "label", "cell"),
                          prep=lambda t: RX_NONGOAL_STRIP.sub("", t))[0])
    checks.append(_simple(lines, "non_goals", "3", "非目標", RX_NONGOAL_STRONG, ("heading", "label"),
                          weak_rx=RX_NONGOAL_WEAK)[0])
    checks.append(check_scope(lines))
    req, occ = check_requirements(lines)
    checks.append(req)
    ac, req_info = check_acceptance(lines, occ)
    checks.append(ac)
    checks.append(check_success(lines))
    checks.append(_simple(lines, "guardrail", "7b", "護欄指標", RX_GUARD, ("heading", "label", "cell"),
                          weak_rx=RX_GUARD)[0])
    checks.append(check_edge(lines))
    checks.append(check_open(lines))
    checks.append(_simple(lines, "changelog", "10", "變更紀錄或版本", RX_CHANGELOG,
                          ("heading", "label", "cell"), missing="建議",
                          miss_detail="找不到；建議補上，方便追蹤改過什麼（不計入缺少）。")[0])
    return checks, req_info


# ---------------------------------------------------------------------------
# 機械性問題
# ---------------------------------------------------------------------------

def snippet(s: str, width: int = 70) -> str:
    t = re.sub(r"\s+", " ", s).strip()
    return t if len(t) <= width else t[: width - 1] + "…"


def is_req_or_ac_line(ln: Line) -> bool:
    if ln.kind not in ("text", "table") or ln.is_header:
        return False
    raw = ln.raw
    if RX_REQ_ID.search(raw) or RX_AC_ID.search(raw) or RX_RULE_ID.search(raw):
        return True
    if RX_GWT_START.match(raw) or _has_gwt(raw) or _row_gwt_by_header(ln):
        return True
    return any(RX_REQ_AC_SECTION.search(h) for h in ln.headings)


def _uniq(seq):
    out = []
    for s in seq:
        if s not in out:
            out.append(s)
    return out


def find_vague(ln: Line) -> list[str]:
    raw = ln.raw
    terms = [m.group(0) for m in VAGUE_ALWAYS.finditer(raw)]
    if is_req_or_ac_line(ln):
        masked = VAGUE_ALWAYS.sub(lambda m: "\0" * len(m.group(0)), raw)
        parts = _split_cells(masked) if ln.kind == "table" else [masked]
        for part in parts:
            for m in VAGUE_CONTEXT.finditer(part):
                if ln.kind == "table" and part.strip() == m.group(0):
                    continue  # a cell that is only the word is a category label, e.g.「正常」
                terms.append(m.group(0))
    return _uniq(terms)


def find_issues(lines: list[Line]) -> list[dict]:
    issues = []
    for ln in lines:
        if ln.kind in ("code", "fence", "blank", "sep"):
            continue
        raw = ln.raw
        vague = find_vague(ln)
        if vague:
            issues.append({"line": ln.no, "type": "模糊用語", "terms": vague, "text": snippet(raw),
                           "in_requirement": is_req_or_ac_line(ln)})
        if not RX_HR.match(raw):
            ph = _uniq("____" if m.group(0).startswith("_") else m.group(0) for m in RX_PLACEHOLDER.finditer(raw))
            if ph:
                issues.append({"line": ln.no, "type": "未填佔位", "terms": ph, "text": snippet(raw),
                               "in_requirement": is_req_or_ac_line(ln)})
        if ln.kind in ("text", "table") and not ln.is_header:
            verbs = _uniq(m.group(0) for m in RX_METRIC_VERB.finditer(raw))
            if verbs and "____" not in raw and not RX_NUMBER.search(RX_STRIP_IDS.sub("", raw)):
                issues.append({"line": ln.no, "type": "指標無數字", "terms": verbs, "text": snippet(raw),
                               "in_requirement": is_req_or_ac_line(ln)})
    return issues


# ---------------------------------------------------------------------------
# 彙整與解讀
# ---------------------------------------------------------------------------

# 依「缺了會讓 RD／QA 無法開工」的程度排序（經驗排序，依團隊而異）
FIX_PRIORITY = [
    ("requirements", "補上編號的功能需求", "沒有編號，RD 無法拆工、QA 無法對應測試案例，討論時也無法指明是哪一條。"),
    ("acceptance", "補齊驗收條件", "沒有驗收條件，QA 寫不出測試案例，RD 也不知道做到什麼程度算完成。"),
    ("scope", "寫清楚範圍 In／Out", "範圍沒劃清楚，RD 無法估工，做到一半容易被追加需求。"),
    ("non_goals", "補上非目標", "沒寫這版不做什麼，利害關係人會各自認定「應該有」，開發中途才吵範圍。"),
    ("edge_cases", "補上異常與邊界情境", "只寫正常流程，RD 得自己猜失敗、無權限、取消時的行為，QA 也測不到。"),
    ("background", "補上問題或背景", "不知道為什麼要做，RD 與設計無法判斷取捨，也難以提出更省工的解法。"),
    ("goals", "補上目標", "沒有目標，無法判斷哪些需求是必要的。"),
    ("open_questions", "列出未決事項並指定負責人與日期", "還沒決定的事沒人追，會在開發中途才卡住。"),
    ("success_metric", "補齊主指標", "不影響開工，但上線後無法判斷有沒有成功；需要埋點的話也要趁開發前講。"),
    ("guardrail", "補上護欄指標", "不影響開工，但主指標變好時無法確認沒有傷到其他指標。"),
]


def top_fixes(checks, req_info, issues) -> list[dict]:
    by_key = {c["key"]: c for c in checks}
    fixes = []
    for key, action, why in FIX_PRIORITY:
        c = by_key[key]
        if c["status"] not in ("缺少", "部分"):
            continue
        item = f"{action}（第 {c['no']} 項：{c['status']}）"
        if key == "acceptance" and req_info["without_ac"]:
            item += f"，先補 {_join_ids(req_info['without_ac'], 6)}"
        elif c["status"] == "部分" and c["detail"]:
            item += "：" + c["detail"].rstrip("。")
        fixes.append({"item": item, "reason": why})
    count = lambda t, req=False: sum(1 for i in issues if i["type"] == t and (i["in_requirement"] or not req))
    ph, vg_req, vg, mt = count("未填佔位"), count("模糊用語", True), count("模糊用語"), count("指標無數字")
    if ph:
        fixes.append({"item": f"填完 {ph} 行未填的佔位（____、TODO、XXX）",
                      "reason": "留白的地方 RD／QA 只能回頭問；還沒定案的請移到未決事項並指定負責人。"})
    if vg:
        where = f"其中 {vg_req} 行在需求或驗收條件內" if vg_req else "都不在需求或驗收條件內"
        fixes.append({"item": f"改寫 {vg} 行模糊用語（{where}）",
                      "reason": "「盡快」「適當」「快速」這類字無法驗證，請改成看得到或查得到的結果與數字。"})
    if mt:
        fixes.append({"item": f"替 {mt} 行「提升／降低」的句子補上數字",
                      "reason": "沒有基準值與目標值，就無法判斷做到了沒有。"})
    return [{"rank": n, **f} for n, f in enumerate(fixes[:3], start=1)]


SCOPE_NOTE = (
    "這份報告只檢查「結構與機械性問題」：該有的段落在不在、編號需求對不對得上驗收條件、"
    "有沒有模糊用語、未填的佔位、沒有數字的指標句。全部是關鍵字與格式比對，不判斷內容寫得好不好；"
    "「通過」只代表找得到該段落。內容品質仍要由人或 AI 依 PRD 撰寫指南（references/21-prd-writing.md）"
    "與驗收條件指南（references/23-acceptance-criteria.md）的「品質檢查」逐條審。"
)


def analyze(text: str, path: str = "", strict: bool = False) -> dict:
    lines = parse_lines(text)
    checks, req_info = run_structure_checks(lines)
    issues = find_issues(lines)
    st = [c["status"] for c in checks]
    summary = {"total": len(checks), "passed": st.count("通過"), "partial": st.count("部分"),
               "missing": st.count("缺少"), "advisory": st.count("建議")}
    by_type = {t: sum(1 for i in issues if i["type"] == t) for t in ("模糊用語", "未填佔位", "指標無數字")}
    return {
        "file": path,
        "lines": len(lines),
        "scope_note": SCOPE_NOTE,
        "checks": checks,
        "requirements": req_info,
        "issues": {"total": len(issues), "by_type": by_type, "items": issues},
        "summary": summary,
        "top_fixes": top_fixes(checks, req_info, issues),
        "strict": strict,
        "exit_code": 1 if strict and summary["missing"] else 0,
    }


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|")


def render_markdown(res: dict) -> str:
    out = ["# PRD 結構檢查", "", f"> {res['scope_note']}", "",
           f"檔案：{res['file']}（{res['lines']} 行）", "", "## 結構檢查", "",
           "| # | 檢查項目 | 結果 | 找到的位置 | 說明 |", "|---|---|---|---|---|"]
    for c in res["checks"]:
        ev = "；".join(f"L{e['line']}「{e['text']}」" for e in c["evidence"]) or "—"
        out.append(f"| {c['no']} | {c['name']} | {c['status']} | {_cell(ev)} | {_cell(c['detail']) or '—'} |")

    iss = res["issues"]
    out += ["", "## 機械性問題", ""]
    if not iss["total"]:
        out.append("沒有找到模糊用語、未填的佔位或沒有數字的指標句。")
    else:
        bt = iss["by_type"]
        out += [f"共 {iss['total']} 筆：模糊用語 {bt['模糊用語']}、未填佔位 {bt['未填佔位']}、指標無數字 {bt['指標無數字']}。",
                "", "| 行 | 類型 | 命中 | 原文片段 |", "|---|---|---|---|"]
        for i in iss["items"][:MAX_ISSUES_SHOWN]:
            out.append(f"| L{i['line']} | {i['type']} | {_cell('、'.join(i['terms']))} | {_cell(i['text'])} |")
        if iss["total"] > MAX_ISSUES_SHOWN:
            out += ["", f"（只列前 {MAX_ISSUES_SHOWN} 筆，共 {iss['total']} 筆；完整清單請用 --json。）"]

    s, r = res["summary"], res["requirements"]
    out += ["", "## 摘要", "",
            f"- 結構檢查 {s['total']} 項：通過 {s['passed']} 項、部分 {s['partial']} 項、缺少 {s['missing']} 項"
            + (f"、建議補上 {s['advisory']} 項" if s["advisory"] else "") + "。",
            f"- 編號需求 {r['count']} 條，其中 {r['with_ac']} 條找得到對應的驗收條件"
            + (f"；缺：{_join_ids(r['without_ac'])}" if r["without_ac"] else "") + "。",
            f"- 機械性問題 {iss['total']} 筆。"]
    if res["strict"]:
        out.append(f"- --strict：{'有缺少項，exit code 1' if res['exit_code'] else '沒有缺少項，exit code 0'}。")

    out += ["", "## 解讀", ""]
    if res["top_fixes"]:
        out.append("最該先補的事（依「缺了會讓 RD／QA 無法開工」的程度排序；這是經驗排序，依團隊而異）：")
        out.append("")
        for f in res["top_fixes"]:
            out.append(f"{f['rank']}. {f['item']}。{f['reason']}")
    else:
        out.append("結構齊全，也沒有找到機械性問題。這只代表格式到位，不代表內容夠好。")
    out += ["",
            "- 「通過」是關鍵字比對的結果：段落存在，不代表內容寫對了。例如有非目標段落，不代表列的是利害關係人真的要過的東西。",
            "- 需求與驗收條件的對應只認「同一表格列或同一段落內有 AC 編號或 Given／When／Then」；"
            "驗收條件寫在別份文件時，請在需求那一列填上 AC 編號。",
            "- 模糊用語清單是經驗值，依團隊用語而異；被列出的行請確認是否真的無法驗證，不必照單全改。",
            "- 下一步：請人或 AI 依兩份指南的「品質檢查」逐條審內容。", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = _ZhArgumentParser(
        prog="prd_check.py",
        description="PRD 結構檢查：檢查段落是否齊全、需求與驗收條件是否對得上、有無模糊用語與未填佔位。"
                    "只檢查結構與機械性問題，不判斷內容好壞。",
        epilog="範例：\n  python prd_check.py prd.md\n  python prd_check.py prd.md --json\n"
               "  python prd_check.py prd.md --strict",
    )
    p.add_argument("markdown", metavar="PRD.md", help="PRD 的 Markdown 檔路徑（UTF-8）")
    p.add_argument("--json", action="store_true", help="輸出 JSON（機器可讀，含完整問題清單）")
    p.add_argument("--strict", action="store_true", help="有任何「缺少」項時以 exit code 1 結束（預設一律 0）")
    return p


def run(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    res = analyze(read_markdown(args.markdown), args.markdown, args.strict)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(res), end="")
    return res


def main(argv: list[str] | None = None) -> int:
    try:
        res = run(argv)
    except InputError as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 2
    return res["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
