#!/usr/bin/env python3
"""A/B 測試計算工具（樣本數估算 + 結果分析），只用 Python 標準函式庫。

讓 Claude 在 PM 工作中「算出」A/B 測試數字，而不是用猜的。

用法範例：
    # 1) 估算每組樣本數：基準轉換率 12%、想偵測相對提升 10%、每天 4,000 名合格使用者
    python ab_test.py size --baseline 12% --mde 10% --daily-traffic 4000

    # 2) 絕對 MDE：基準 10%、要偵測 +2 個百分點、三組（含對照組），輸出 JSON
    python ab_test.py size --baseline 0.10 --mde 0.02 --mde-type abs --variants 3 --json

    # 3) 分析實驗結果 CSV（欄位：組別,訪客,轉換[,分群]），並提醒是否提早偷看
    python ab_test.py analyze results.csv --expected-split 50,50 --planned-n 20000

統計方法摘要：
    size     兩比例常態近似公式（虛無假設下用合併變異數，對立假設下用各組變異數；
             與 R 的 power.prop.test 相同，無連續性校正）。
    analyze  兩比例 z 檢定（合併標準誤算 p 值）、差異的信賴區間（未合併標準誤，Wald 區間）、
             樣本比例失衡（SRM）用卡方適合度檢定，卡方分配 CDF 以正規化不完全伽瑪函數自行實作。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from statistics import NormalDist

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# argparse 繁中化
# ---------------------------------------------------------------------------

_ZH_MESSAGES = {
    "usage: ": "用法：",
    "positional arguments": "位置參數",
    "options": "選項",
    "subcommands": "子命令",
    "show this help message and exit": "顯示說明後離開",
    " (default: %(default)s)": "（預設：%(default)s）",
    "argument %(argument_name)s: %(message)s": "參數 %(argument_name)s：%(message)s",
    "unrecognized arguments: %s": "無法辨識的參數：%s",
    "the following arguments are required: %s": "缺少必要參數：%s",
    "expected one argument": "需要一個值",
    "expected at most one argument": "最多只能有一個值",
    "expected at least one argument": "至少需要一個值",
    "invalid %(type)s value: %(value)r": "%(value)r 不是有效的值",
    "invalid choice: %(value)r (choose from %(choices)s)": "無效的選項 %(value)r（可選：%(choices)s）",
    "ambiguous option: %(option)s could match %(matches)s": "選項 %(option)s 不明確，可能是 %(matches)s",
    "%(prog)s: error: %(message)s\n": "%(prog)s：錯誤：%(message)s\n",
    "%(heading)s:": "%(heading)s：",
}
argparse._ = lambda s: _ZH_MESSAGES.get(s, s)  # argparse 在執行期查詢模組層級的 _()


class InputError(Exception):
    """使用者輸入錯誤：以繁中訊息、exit code 2 結束，不顯示 traceback。"""


def fail(msg: str) -> None:
    raise InputError(msg)


# ---------------------------------------------------------------------------
# 數值解析
# ---------------------------------------------------------------------------

def parse_rate(text: str, name: str, allow_ge1_plain: bool = False) -> float:
    """解析 0.12 或 12% 形式的比例。不帶 % 且 >= 1 的數字視為寫法不明確而拒絕。"""
    raw = str(text).strip().replace("％", "%")
    is_pct = raw.endswith("%")
    num = raw[:-1].strip() if is_pct else raw
    try:
        value = float(num)
    except ValueError:
        fail(f"{name} 必須是數字，例如 0.12 或 12%（收到：{text!r}）")
    if not math.isfinite(value):
        fail(f"{name} 必須是有限的數字（收到：{text!r}）")
    if is_pct:
        value /= 100.0
    elif value >= 1 and not allow_ge1_plain:
        fail(f"{name} 寫成 {text!r} 意思不明確：比例請寫 0.12 這種小數，或加上百分比符號如 12%")
    return value


def z_crit(alpha_two_sided: float) -> float:
    return NormalDist().inv_cdf(1 - alpha_two_sided / 2)


# ---------------------------------------------------------------------------
# size：樣本數
# ---------------------------------------------------------------------------

def sample_size_per_group(p1: float, p2: float, alpha: float, power: float) -> float:
    """兩比例、雙尾、常態近似的每組樣本數（未無條件進位）。

    公式（虛無假設 H0 下用合併比例 p̄ 的變異數，H1 下用各組變異數；無連續性校正）：
        n = [ z_{1-α/2} * sqrt(2 p̄ q̄) + z_{1-β} * sqrt(p1 q1 + p2 q2) ]² / (p1 - p2)²
    其中 p̄ = (p1 + p2) / 2。此為 Fleiss (1981) 不含連續性校正的版本，也是 R
    power.prop.test 的閉式解（strict=FALSE）。

    與常見線上計算機的差異：Evan Miller 的計算機在 H0 項使用 sqrt(2 p1 q1)
    （只用基準組變異數，而不是兩組平均 p̄），因此 baseline 10%、+2pp 時得到約 3,623；
    本公式用 p̄ = 11%，H0 變異數較大，得到約 3,841。兩者都是合理的近似，
    差異約 6%，源自 H0 變異數的假設不同，不是計算錯誤。
    """
    d = abs(p2 - p1)
    pbar = (p1 + p2) / 2
    za = z_crit(alpha)
    zb = NormalDist().inv_cdf(power)
    num = za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return num ** 2 / d ** 2


def cmd_size(args: argparse.Namespace) -> dict:
    p1 = parse_rate(args.baseline, "--baseline")
    if not 0 < p1 < 1:
        fail("--baseline 必須介於 0 與 1 之間（不含 0 與 100%）")
    mde = parse_rate(args.mde, "--mde")
    if mde <= 0:
        fail("--mde 必須大於 0（檢定為雙尾，方向不影響樣本數）")
    if args.mde_type == "abs":
        p2 = p1 + mde
    else:
        p2 = p1 * (1 + mde)
    if not 0 < p2 < 1:
        fail(f"基準 {p1:.2%} 加上 MDE 後的轉換率為 {p2:.2%}，超出 0～100% 範圍，請調整 --mde")
    alpha = parse_rate(args.alpha, "--alpha")
    power = parse_rate(args.power, "--power")
    if not 0 < alpha < 1:
        fail("--alpha 必須介於 0 與 1 之間")
    if not 0 < power < 1:
        fail("--power 必須介於 0 與 1 之間")
    try:
        variants = int(args.variants)
    except ValueError:
        fail("--variants 必須是整數（含對照組的組數）")
    if variants < 2:
        fail("--variants 至少為 2（對照組 + 1 個實驗組）")

    comparisons = variants - 1
    alpha_adj = alpha / comparisons if variants > 2 else alpha
    n_raw = sample_size_per_group(p1, p2, alpha_adj, power)
    n = math.ceil(n_raw - 1e-9)
    total = n * variants

    result = {
        "baseline": p1,
        "target_rate": p2,
        "mde": mde,
        "mde_type": args.mde_type,
        "absolute_difference": p2 - p1,
        "relative_difference": (p2 - p1) / p1,
        "alpha": alpha,
        "alpha_adjusted": alpha_adj,
        "bonferroni": variants > 2,
        "power": power,
        "variants": variants,
        "n_per_group": n,
        "n_per_group_unrounded": n_raw,
        "n_total": total,
        "formula": "two-proportion normal approximation, pooled variance under H0 (Fleiss, no continuity correction; = R power.prop.test)",
    }
    if args.daily_traffic is not None:
        try:
            daily = float(args.daily_traffic.replace(",", ""))
        except ValueError:
            fail("--daily-traffic 必須是數字（每天所有組別合計的合格使用者數）")
        if not math.isfinite(daily) or daily <= 0:
            fail("--daily-traffic 必須大於 0")
        days = math.ceil(total / daily - 1e-9)
        result["daily_traffic"] = daily
        result["days"] = days
        result["recommended_days"] = max(days, 7)
    return result


def render_size(r: dict) -> str:
    lines = ["# A/B 測試樣本數估算", ""]
    lines += ["| 項目 | 數值 |", "|---|---|"]
    lines.append(f"| 基準轉換率 | {r['baseline']:.2%} |")
    mde_desc = (f"{r['mde']:.2%}（絕對，百分點）" if r["mde_type"] == "abs"
                else f"{r['mde']:.2%}（相對）")
    lines.append(f"| 最小可偵測效果 MDE | {mde_desc} |")
    lines.append(f"| 目標轉換率 | {r['target_rate']:.2%}（絕對差 {r['absolute_difference'] * 100:.2f} 個百分點、相對 {r['relative_difference']:.1%}） |")
    if r["bonferroni"]:
        lines.append(f"| 顯著水準 α（雙尾） | {r['alpha']:g} → Bonferroni 校正後 {r['alpha_adjusted']:.4g}（{r['variants'] - 1} 個實驗組各與對照組比較） |")
    else:
        lines.append(f"| 顯著水準 α（雙尾） | {r['alpha']:g} |")
    lines.append(f"| 檢定力 | {r['power']:.0%} |")
    lines.append(f"| 組數（含對照組） | {r['variants']} |")
    lines.append(f"| **每組樣本數** | **{r['n_per_group']:,}** |")
    lines.append(f"| 全部組別合計 | {r['n_total']:,} |")
    if "days" in r:
        lines.append(f"| 每日合格流量（所有組別合計） | {r['daily_traffic']:,.0f} |")
        lines.append(f"| 預估天數（無條件進位） | {r['days']} 天 |")
    lines += ["", "## 解讀", ""]
    lines.append(f"- 每一組至少要 {r['n_per_group']:,} 位使用者，才有 {r['power']:.0%} 的機會在效果真的達到 MDE 時偵測出顯著差異。")
    lines.append("- 效果比 MDE 小時，這個樣本數多半測不出來；想偵測更小的效果，樣本數會以平方倍數增加。")
    if r["bonferroni"]:
        lines.append(f"- 因為有 {r['variants']} 組，已用 Bonferroni 把 α 除以 {r['variants'] - 1}，避免多組比較讓「假的顯著」變多，所以每組需要的人數比兩組時多。")
    if "days" in r:
        msg = f"- 依目前流量約需 {r['days']} 天。"
        if r["days"] < 7:
            msg += "但建議至少跑滿一整週（7 天），涵蓋平日與週末的使用差異。"
        else:
            msg += "建議以「整週」為單位安排（例如跑滿 7 的倍數天），涵蓋平日與週末的使用差異。"
        lines.append(msg)
    else:
        lines.append("- 不論算出的天數多短，都建議至少跑滿一整週，涵蓋平日與週末的使用差異。")
    lines.append("- 計算公式：兩比例常態近似（H0 用合併變異數，與 R power.prop.test 相同）。其他計算機若 H0 只用基準組變異數，數字會略小（約少 5～6%），屬公式假設差異。")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 卡方分配（自行實作）
# ---------------------------------------------------------------------------

def _gamma_p_series(a: float, x: float) -> float:
    """正規化下不完全伽瑪 P(a, x) 的級數展開（x < a + 1 時收斂快）。"""
    term = 1.0 / a
    total = term
    k = a
    for _ in range(10000):
        k += 1
        term *= x / k
        total += term
        if abs(term) < abs(total) * 1e-15:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_q_contfrac(a: float, x: float) -> float:
    """正規化上不完全伽瑪 Q(a, x) 的連分數（修正 Lentz 法，x >= a + 1 時使用）。"""
    tiny = 1e-300
    b = x + 1 - a
    c = 1 / tiny
    d = 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return h * math.exp(-x + a * math.log(x) - math.lgamma(a))


def chi2_sf(x: float, df: int) -> float:
    """卡方分配的右尾機率 P(X >= x)，df 為自由度。"""
    if x <= 0:
        return 1.0
    a = df / 2.0
    hx = x / 2.0
    if hx < a + 1:
        return max(0.0, 1.0 - _gamma_p_series(a, hx))
    return _gamma_q_contfrac(a, hx)


def chi2_cdf(x: float, df: int) -> float:
    return 1.0 - chi2_sf(x, df)


# ---------------------------------------------------------------------------
# analyze：結果分析
# ---------------------------------------------------------------------------

HEADER_ALIASES = {
    "group": {"group", "組別", "variant", "組"},
    "visitors": {"visitors", "訪客", "users", "訪客數", "visitor"},
    "conversions": {"conversions", "轉換", "轉換數", "conversion"},
    "segment": {"segment", "分群"},
}
CONTROL_NAMES = {"control", "對照", "對照組"}


def _map_headers(fieldnames: list[str]) -> dict:
    mapping = {}
    for raw in fieldnames:
        key = (raw or "").strip().lower()
        for canon, aliases in HEADER_ALIASES.items():
            if key in {a.lower() for a in aliases}:
                if canon in mapping:
                    fail(f"欄位重複：{mapping[canon]!r} 與 {raw!r} 都對應到 {canon}")
                mapping[canon] = raw
    missing = [c for c in ("group", "visitors", "conversions") if c not in mapping]
    if missing:
        names = {"group": "group／組別", "visitors": "visitors／訪客／users", "conversions": "conversions／轉換"}
        fail("CSV 缺少必要欄位：" + "、".join(names[m] for m in missing)
             + f"（目前欄位：{', '.join(fieldnames)}）")
    return mapping


def _parse_count(text: str, col: str, line: int) -> int:
    raw = (text or "").strip().replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        fail(f"第 {line} 行的「{col}」不是數字：{text!r}")
    if not math.isfinite(value) or value < 0 or value != int(value):
        fail(f"第 {line} 行的「{col}」必須是非負整數：{text!r}")
    return int(value)


def read_results_csv(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                fail(f"CSV 是空的：{path}")
            mapping = _map_headers(reader.fieldnames)
            rows = []
            for row in reader:
                line = reader.line_num
                if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                    continue
                group = (row.get(mapping["group"]) or "").strip()
                if not group:
                    fail(f"第 {line} 行缺少組別名稱")
                visitors = _parse_count(row.get(mapping["visitors"]), "訪客", line)
                conversions = _parse_count(row.get(mapping["conversions"]), "轉換", line)
                if conversions > visitors:
                    fail(f"第 {line} 行轉換數（{conversions}）大於訪客數（{visitors}）")
                seg = (row.get(mapping["segment"]) or "").strip() if "segment" in mapping else None
                if "segment" in mapping and not seg:
                    fail(f"第 {line} 行有分群欄位但值是空的")
                rows.append({"group": group, "visitors": visitors, "conversions": conversions,
                             "segment": seg, "line": line})
    except FileNotFoundError:
        fail(f"找不到檔案：{path}")
    except UnicodeDecodeError:
        fail(f"無法以 UTF-8 讀取 {path}，請另存為 UTF-8 編碼的 CSV")
    except csv.Error as e:
        fail(f"CSV 格式錯誤：{e}")
    if not rows:
        fail("CSV 沒有任何資料列")
    return rows


def aggregate_groups(rows: list[dict], has_segment: bool) -> list[dict]:
    """依組別彙總（保留第一次出現的順序）。沒有分群時同名組別重複視為錯誤。"""
    order: list[str] = []
    totals: dict[str, dict] = {}
    for r in rows:
        g = r["group"]
        if g not in totals:
            order.append(g)
            totals[g] = {"group": g, "visitors": 0, "conversions": 0}
        elif not has_segment:
            fail(f"組別 {g!r} 重複出現（第 {r['line']} 行）。沒有分群欄位時每組只能有一列")
        totals[g]["visitors"] += r["visitors"]
        totals[g]["conversions"] += r["conversions"]
    return [totals[g] for g in order]


def pick_control(groups: list[dict]) -> int:
    named = [i for i, g in enumerate(groups) if g["group"].strip().lower() in CONTROL_NAMES]
    if len(named) > 1:
        fail("有多個組別名稱像對照組（control／對照），請只保留一個")
    return named[0] if named else 0


def two_prop_test(xc: int, nc: int, xv: int, nv: int, conf: float) -> dict:
    pc = xc / nc
    pv = xv / nv
    diff = pv - pc
    pooled = (xc + xv) / (nc + nv)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / nc + 1 / nv))
    if se_pooled == 0:
        z, p = 0.0, 1.0
    else:
        z = diff / se_pooled
        p = 2 * (1 - NormalDist().cdf(abs(z)))
    se_unpooled = math.sqrt(pc * (1 - pc) / nc + pv * (1 - pv) / nv)
    zc = NormalDist().inv_cdf(1 - (1 - conf) / 2)
    return {
        "rate_control": pc,
        "rate_variant": pv,
        "abs_lift": diff,
        "rel_lift": diff / pc if pc > 0 else None,
        "z": z,
        "p_value": p,
        "ci_low": diff - zc * se_unpooled,
        "ci_high": diff + zc * se_unpooled,
    }


def analyze_groups(groups: list[dict], alpha: float) -> dict:
    for g in groups:
        if g["visitors"] == 0:
            fail(f"組別 {g['group']!r} 的訪客數為 0，無法計算轉換率")
    ci = pick_control(groups)
    control = groups[ci]
    k = len(groups)
    threshold = alpha / (k - 1) if k > 2 else alpha
    out = []
    for i, g in enumerate(groups):
        entry = {"group": g["group"], "visitors": g["visitors"], "conversions": g["conversions"],
                 "rate": g["conversions"] / g["visitors"], "is_control": i == ci}
        if i != ci:
            t = two_prop_test(control["conversions"], control["visitors"],
                              g["conversions"], g["visitors"], 1 - alpha)
            entry.update({k2: t[k2] for k2 in ("abs_lift", "rel_lift", "z", "p_value", "ci_low", "ci_high")})
            entry["significant"] = t["p_value"] < threshold
        out.append(entry)
    return {"control": control["group"], "threshold": threshold, "groups": out}


def parse_split(text: str | None, k: int) -> list[float]:
    if text is None:
        return [1.0 / k] * k
    parts = [p.strip() for p in text.replace("，", ",").replace("：", ":").replace(":", ",").split(",") if p.strip()]
    try:
        vals = [float(p.rstrip("%")) for p in parts]
    except ValueError:
        fail(f"--expected-split 格式錯誤：{text!r}，請寫成 50,50 這種以逗號分隔的數字")
    if len(vals) != k:
        fail(f"--expected-split 有 {len(vals)} 個數字，但資料有 {k} 個組別，數量必須一致（依 CSV 組別出現順序）")
    if any((not math.isfinite(v)) or v <= 0 for v in vals):
        fail("--expected-split 每個比例都必須大於 0")
    s = sum(vals)
    return [v / s for v in vals]


def srm_check(groups: list[dict], split: list[float]) -> dict:
    n = sum(g["visitors"] for g in groups)
    expected = [n * s for s in split]
    stat = sum((g["visitors"] - e) ** 2 / e for g, e in zip(groups, expected))
    df = len(groups) - 1
    p = chi2_sf(stat, df)
    return {
        "chi2": stat, "df": df, "p_value": p,
        "expected_share": split,
        "observed_share": [g["visitors"] / n for g in groups],
        "mismatch": p < 0.001,
    }


def cmd_analyze(args: argparse.Namespace) -> dict:
    alpha = parse_rate(args.alpha, "--alpha")
    if not 0 < alpha < 1:
        fail("--alpha 必須介於 0 與 1 之間")
    rows = read_results_csv(args.file)
    has_segment = rows[0]["segment"] is not None
    overall_groups = aggregate_groups(rows, has_segment)
    if len(overall_groups) < 2:
        fail("至少需要 2 個組別（對照組 + 實驗組）")
    split = parse_split(args.expected_split, len(overall_groups))
    overall = analyze_groups(overall_groups, alpha)
    srm = srm_check(overall_groups, split)

    planned = None
    if args.planned_n is not None:
        try:
            planned = int(str(args.planned_n).replace(",", ""))
        except ValueError:
            fail("--planned-n 必須是整數（每組預計樣本數）")
        if planned <= 0:
            fail("--planned-n 必須大於 0")

    result = {
        "alpha": alpha,
        "confidence_level": 1 - alpha,
        "bonferroni": len(overall_groups) > 2,
        "overall": overall,
        "srm": srm,
        "segments": None,
        "planned_n": planned,
        "below_planned_n": None,
        "methods": {
            "p_value": "two-proportion z-test, pooled SE",
            "ci": "Wald interval for difference, unpooled SE, not Bonferroni-adjusted",
            "srm": "chi-square goodness-of-fit, flagged when p < 0.001",
        },
    }
    if planned is not None:
        result["below_planned_n"] = any(g["visitors"] < planned for g in overall_groups)

    if has_segment:
        seg_order: list[str] = []
        seg_rows: dict[str, list[dict]] = {}
        for r in rows:
            if r["segment"] not in seg_rows:
                seg_order.append(r["segment"])
                seg_rows[r["segment"]] = []
            seg_rows[r["segment"]].append(r)
        segs = []
        for s in seg_order:
            names = [r["group"] for r in seg_rows[s]]
            if len(set(names)) != len(names):
                fail(f"分群 {s!r} 中有重複的組別")
            groups = aggregate_groups(seg_rows[s], has_segment=False)
            if len(groups) < 2:
                segs.append({"segment": s, "skipped": "此分群少於 2 個組別"})
                continue
            if any(g["visitors"] == 0 for g in groups):
                segs.append({"segment": s, "skipped": "此分群有組別訪客數為 0"})
                continue
            res = analyze_groups(groups, alpha)
            res["segment"] = s
            segs.append(res)
        result["segments"] = segs
    return result


def _fmt_p(p: float) -> str:
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def _p_eq(p: float) -> str:
    return "p < 0.0001" if p < 0.0001 else f"p = {p:.4f}"


def _group_table(res: dict, conf: float) -> list[str]:
    lines = [f"| 組別 | 訪客 | 轉換 | 轉換率 | 絕對提升 | 相對提升 | p 值 | 差異 {conf:.0%} 信賴區間 | 顯著？ |",
             "|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for g in res["groups"]:
        if g["is_control"]:
            lines.append(f"| {g['group']}（對照） | {g['visitors']:,} | {g['conversions']:,} | {g['rate']:.2%} | — | — | — | — | — |")
            continue
        rel = "—" if g["rel_lift"] is None else f"{g['rel_lift']:+.1%}"
        ci = f"{g['ci_low'] * 100:+.2f} ～ {g['ci_high'] * 100:+.2f} pp"
        sig = "是" if g["significant"] else "否"
        lines.append(f"| {g['group']} | {g['visitors']:,} | {g['conversions']:,} | {g['rate']:.2%} | "
                     f"{g['abs_lift'] * 100:+.2f} pp | {rel} | {_fmt_p(g['p_value'])} | {ci} | {sig} |")
    return lines


def render_analyze(r: dict) -> str:
    conf = r["confidence_level"]
    ov = r["overall"]
    srm = r["srm"]
    lines = ["# A/B 測試結果分析", ""]

    lines += ["## 樣本比例檢查（SRM）", ""]
    lines += ["| 組別 | 實際訪客佔比 | 預期佔比 |", "|---|---:|---:|"]
    for g, o, e in zip(ov["groups"], srm["observed_share"], srm["expected_share"]):
        lines.append(f"| {g['group']} | {o:.2%} | {e:.2%} |")
    lines.append("")
    lines.append(f"卡方 = {srm['chi2']:.3f}，自由度 = {srm['df']}，{_p_eq(srm['p_value'])}"
                 + ("　**⚠ 樣本比例失衡，先查分流再看結果**" if srm["mismatch"] else "（未達失衡門檻 p < 0.001）"))
    lines.append("")

    lines += ["## 整體結果", ""]
    lines += _group_table(ov, conf)
    lines.append("")
    if r["bonferroni"]:
        lines.append(f"顯著門檻：α = {r['alpha']:g}，有 {len(ov['groups']) - 1} 個實驗組，Bonferroni 校正後 p < {ov['threshold']:.4g} 才算顯著。")
    else:
        lines.append(f"顯著門檻：p < {ov['threshold']:g}（雙尾）。")
    lines.append("")

    if r["segments"] is not None:
        lines += ["## 分群結果", "",
                  "> ⚠ 同時看很多分群會讓「純屬巧合的顯著」變多。分群裡的發現只能當作假設，需要另做實驗驗證，不能直接當結論。", ""]
        for s in r["segments"]:
            lines.append(f"### 分群：{s['segment']}")
            lines.append("")
            if "skipped" in s:
                lines.append(f"（略過：{s['skipped']}）")
            else:
                lines += _group_table(s, conf)
            lines.append("")

    lines += ["## 解讀", ""]
    if srm["mismatch"]:
        lines.append("- **樣本比例失衡，先查分流再看結果。** 各組人數和預期比例差太多，通常代表分流、追蹤或資料清理出了問題，此時轉換率的比較不可信。")
    for g in ov["groups"]:
        if g["is_control"]:
            continue
        direction = "高" if g["abs_lift"] > 0 else "低" if g["abs_lift"] < 0 else "相同於"
        rel = "" if g["rel_lift"] is None else f"，相對 {g['rel_lift']:+.1%}"
        if g["significant"]:
            lines.append(f"- {g['group']} 的轉換率比對照組{direction} {abs(g['abs_lift']) * 100:.2f} 個百分點{'（' + rel.lstrip('，') + '）' if rel else ''}，達統計顯著（{_p_eq(g['p_value'])}）。"
                         f"真實差異大約落在 {g['ci_low'] * 100:+.2f} 到 {g['ci_high'] * 100:+.2f} 個百分點之間。")
        else:
            lines.append(f"- {g['group']} 與對照組的差異（{g['abs_lift'] * 100:+.2f} 個百分點{rel}）未達顯著（{_p_eq(g['p_value'])}），"
                         f"目前資料無法排除只是隨機波動；區間 {g['ci_low'] * 100:+.2f} 到 {g['ci_high'] * 100:+.2f} 個百分點都還有可能。")
    if r["bonferroni"]:
        lines.append("- 多組比較已用 Bonferroni 收緊顯著門檻；信賴區間仍是未校正的 95% 區間，僅供看效果大小。")
    if r["below_planned_n"]:
        lines.append(f"- **提醒：目前樣本尚未達到預計的每組 {r['planned_n']:,} 人。** 不要一看到顯著就提早停止實驗（peeking），"
                     "反覆偷看會讓誤判率遠高於設定的 α。請跑滿預計樣本數再下結論。")
    elif r["planned_n"] is not None:
        lines.append(f"- 各組都已達預計的每組 {r['planned_n']:,} 人。")
    if r["segments"] is not None:
        lines.append("- 分群結果是探索用的線索：分群越多，越容易純屬巧合地出現顯著，請把它當成下一輪實驗的假設。")
    lines.append("- 方法：p 值用兩比例 z 檢定（合併標準誤）；信賴區間用未合併標準誤；SRM 用卡方適合度檢定。")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ab_test.py",
        description="A/B 測試計算：樣本數估算（size）與結果分析（analyze）。數字由公式算出，不憑猜測。",
    )
    sub = parser.add_subparsers(dest="command", title="子命令", metavar="{size,analyze}")
    sub.required = True

    ps = sub.add_parser("size", help="估算轉換率實驗每組所需樣本數",
                        description="兩比例常態近似公式估算每組樣本數（雙尾）。H0 用合併變異數，與 R power.prop.test 相同。")
    ps.add_argument("--baseline", required=True, help="基準（對照組）轉換率，例如 0.12 或 12%%")
    ps.add_argument("--mde", required=True, help="最小可偵測效果，例如 10%% 或 0.1（含義依 --mde-type）")
    ps.add_argument("--mde-type", choices=["abs", "rel"], default="rel",
                    help="abs＝絕對差（百分點，0.02 代表 +2pp）；rel＝相對提升（預設，0.1 代表 +10%%）")
    ps.add_argument("--alpha", default="0.05", help="顯著水準，雙尾（預設 0.05）")
    ps.add_argument("--power", default="0.8", help="檢定力（預設 0.8）")
    ps.add_argument("--variants", default="2",
                    help="組數，含對照組（預設 2）。大於 2 時以 Bonferroni 把 α 除以（組數−1）")
    ps.add_argument("--daily-traffic", help="每天所有組別合計的合格使用者數；提供時估算所需天數（無條件進位）")
    ps.add_argument("--json", action="store_true", help="輸出 JSON")

    pa = sub.add_parser("analyze", help="分析實驗結果 CSV",
                        description="CSV 欄位：group/組別、visitors/訪客/users、conversions/轉換，可選 segment/分群。"
                                    "名為 control/對照 的組別為對照組，否則第一個組別為對照組。")
    pa.add_argument("file", help="結果 CSV（UTF-8，可含 BOM）")
    pa.add_argument("--expected-split", help="預期分流比例，依組別出現順序，例如 50,50（預設平均分配）")
    pa.add_argument("--alpha", default="0.05", help="顯著水準，雙尾（預設 0.05；超過 2 組時自動 Bonferroni 校正）")
    pa.add_argument("--planned-n", help="每組預計樣本數；目前樣本未達時會提醒不要提早停止（peeking）")
    pa.add_argument("--json", action="store_true", help="輸出 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "size":
            result = cmd_size(args)
            text = render_size(result)
        else:
            result = cmd_analyze(args)
            text = render_analyze(result)
    except InputError as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
