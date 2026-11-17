"""estimate.py 測試。執行：在 pm-field-guide 資料夾下 `python -X utf8 -m unittest discover -s scripts/tests`。"""
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
EXAMPLES = SCRIPTS.parent / "examples"
sys.path.insert(0, str(SCRIPTS))

import estimate  # noqa: E402


def write_csv(text: str, bom: bool = True) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        f.write(text)
    return path


def run_json(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        estimate.run(argv + ["--json"])
    return json.loads(buf.getvalue())


# 手算基準：
#   甲 20/35/60：E = (20 + 140 + 60) ÷ 6 = 36.67；SD = 40 ÷ 6 = 6.67；P÷O = 3.0 → 警示
#   乙 10/15/26：E = (10 + 60 + 26) ÷ 6 = 16.0； SD = 16 ÷ 6 = 2.67；P÷O = 2.6
#   丙  8/10/12：E = ( 8 + 40 + 12) ÷ 6 = 10.0； SD =  4 ÷ 6 = 0.67；P÷O = 1.5
#   期望合計 = 62.67；合計 SD = sqrt(44.44 + 7.11 + 0.44) = sqrt(52) ≈ 7.21
#   90% 承諾值 = 62.67 + 1.28 × 7.21 ≈ 71.9
THREE = ["--item", "甲:20,35,60", "--item", "乙:10,15,26", "--item", "丙:8,10,12"]
BASE = "項目,樂觀,最可能,悲觀\n甲,20,35,60\n乙,10,15,26\n丙,8,10,12\n"


class TestPureFunctions(unittest.TestCase):
    def test_pert_reference_case(self):
        e, sd, ratio = estimate.pert(20, 35, 60)
        self.assertAlmostEqual(e, 36.67, places=2)
        self.assertAlmostEqual(sd, 6.67, places=2)
        self.assertAlmostEqual(ratio, 3.0)

    def test_combine_and_commitment(self):
        sds = [estimate.pert(*t)[1] for t in ((20, 35, 60), (10, 15, 26), (8, 10, 12))]
        total_sd = estimate.combine(sds)
        self.assertAlmostEqual(total_sd, math.sqrt(52), places=9)
        self.assertAlmostEqual(total_sd, 7.21, places=2)
        self.assertAlmostEqual(estimate.commitment(62.6667, total_sd, 90), 71.9, places=1)
        self.assertAlmostEqual(estimate.commitment(100, 10, 80), 108.4)
        self.assertAlmostEqual(estimate.commitment(100, 10, 95), 116.45)

    def test_confidence_level_three_formats(self):
        for s in ("90", "90%", "0.9", "90％", " 0.90 "):
            self.assertEqual(estimate.parse_confidence_level(s), 90)
        self.assertEqual(estimate.parse_confidence_level("80%"), 80)
        self.assertEqual(estimate.parse_confidence_level("0.95"), 95)
        for bad in ("85", "99%", "0.5", "abc", "150", ""):
            with self.assertRaises(estimate.InputError):
                estimate.parse_confidence_level(bad)

    def test_parse_item_arg(self):
        self.assertEqual(
            estimate.parse_item_arg("API: 串接：20, 35，60"),
            {"item": "API: 串接", "optimistic": "20", "likely": "35", "pessimistic": "60"},
        )
        for bad in ("甲", "甲:1,2", "甲:1,2,3,4", ":1,2,3"):
            with self.assertRaises(estimate.InputError):
                estimate.parse_item_arg(bad)


class TestRun(unittest.TestCase):
    def test_three_items_reference_case(self):
        res = run_json(THREE)
        a, b, c = res["items"]
        self.assertAlmostEqual(a["expected"], 36.67, places=2)
        self.assertAlmostEqual(a["sd"], 6.67, places=2)
        self.assertEqual(a["ratio"], 3.0)
        self.assertTrue(a["high_uncertainty"])
        self.assertIn("先拆小或先做技術探索", a["flag"])
        self.assertEqual((b["expected"], c["expected"]), (16.0, 10.0))
        self.assertFalse(b["high_uncertainty"])   # 2.6 < 3
        self.assertEqual(b["flag"], "")
        self.assertAlmostEqual(res["total"]["expected"], 62.67, places=2)
        self.assertAlmostEqual(res["total"]["sd"], 7.21, places=2)
        self.assertAlmostEqual(res["commitment"]["value"], 71.9, places=1)
        self.assertEqual(res["commitment"]["confidence"], 90)   # 預設 90
        self.assertEqual(res["commitment"]["z"], 1.28)

    def test_json_structure(self):
        res = run_json(THREE)
        self.assertEqual(set(res), {"unit", "items", "total", "commitment", "notes", "warnings", "interpretation"})
        self.assertEqual(set(res["items"][0]), {
            "item", "owner", "optimistic", "likely", "pessimistic", "expected", "sd", "ratio",
            "high_uncertainty", "flag", "note", "variance_share"})
        self.assertEqual(set(res["total"]), {"count", "expected", "sd", "independence_assumed"})
        self.assertEqual(set(res["commitment"]), {"confidence", "z", "buffer", "value"})
        self.assertEqual(res["unit"], "人天")
        self.assertAlmostEqual(sum(x["variance_share"] for x in res["items"]), 1.0, places=3)
        notes = "\n".join(res["notes"])
        self.assertIn("約有一半機率超時", notes)
        self.assertIn("常態近似", notes)
        self.assertIn("彼此獨立", notes)
        self.assertIn("實際風險會比這個數字大", notes)
        self.assertIn("經驗值，依產業而異", notes)

    def test_confidence_levels_and_formats(self):
        base = run_json(THREE)["total"]
        for arg, level, z in (("80", 80, 0.84), ("80%", 80, 0.84), ("0.8", 80, 0.84),
                              ("95%", 95, 1.645), ("0.95", 95, 1.645)):
            com = run_json(THREE + ["--confidence", arg])["commitment"]
            self.assertEqual((com["confidence"], com["z"]), (level, z))
            self.assertAlmostEqual(com["value"], base["expected"] + z * base["sd"], places=3)

    def test_single_item_has_no_independence_note(self):
        res = run_json(["--item", "甲:20,35,60"])
        self.assertFalse(res["total"]["independence_assumed"])
        self.assertNotIn("獨立", "\n".join(res["notes"] + res["interpretation"]))
        self.assertAlmostEqual(res["commitment"]["value"], 36.6667 + 1.28 * 6.6667, places=3)
        buf = io.StringIO()
        with redirect_stdout(buf):
            estimate.run(["--item", "甲:20,35,60"])
        self.assertNotIn("獨立", buf.getvalue())
        self.assertIn("約有一半機率超時", buf.getvalue())

    def test_boundaries(self):
        # O = M = P：SD 0，承諾值等於期望值，不會除以零
        res = run_json(["--item", "固定:5,5,5"])
        self.assertEqual((res["total"]["sd"], res["commitment"]["value"]), (0, 5))
        self.assertIsNone(res["items"][0]["variance_share"])
        # P÷O 2.99 不警示、3 警示（含浮點誤差：0.3 ÷ 0.1）
        res = run_json(["--item", "A:100,200,299", "--item", "B:0.1,0.2,0.3"])
        self.assertEqual([x["high_uncertainty"] for x in res["items"]], [False, True])

    def test_unit_only_changes_label(self):
        res = run_json(THREE + ["--unit", "人週"])
        self.assertEqual(res["unit"], "人週")
        self.assertTrue(any("人週" in o for o in res["interpretation"]))
        self.assertAlmostEqual(res["total"]["expected"], 62.67, places=2)

    def test_csv_chinese_headers_with_bom_and_parentheses(self):
        p = write_csv("項目,樂觀（人天）,最可能(人天),悲觀,負責人,備註,多餘欄\n甲,20,35,60,後端,沒做過,x\n乙,10,15,26,,,\n")
        try:
            res = run_json([p])
            self.assertEqual(res["items"][0]["owner"], "後端")
            self.assertEqual(res["items"][0]["note"], "沒做過")
            self.assertAlmostEqual(res["total"]["expected"], 52.67, places=2)
            self.assertTrue(any("多餘欄" in w for w in res["warnings"]))
        finally:
            os.remove(p)

    def test_csv_english_and_short_headers(self):
        for header in ("Item,Optimistic,Likely,Pessimistic,Owner,Note", "item,O,M,P,owner,note", "項目,o,m,p,負責人,備註"):
            p = write_csv(header + "\nA,20,35,60,dev,n\n", bom=False)
            try:
                res = run_json([p])
                self.assertAlmostEqual(res["items"][0]["expected"], 36.67, places=2)
                self.assertEqual(res["items"][0]["owner"], "dev")
            finally:
                os.remove(p)

    def test_csv_matches_item_args(self):
        p = write_csv(BASE)
        try:
            a, b = run_json([p]), run_json(THREE)
            self.assertEqual(a["total"], b["total"])
            self.assertEqual(a["commitment"], b["commitment"])
        finally:
            os.remove(p)

    def test_example_file(self):
        res = run_json([str(EXAMPLES / "estimate.csv")])
        self.assertIn(len(res["items"]), (4, 5))
        first = res["items"][0]
        self.assertEqual((first["optimistic"], first["likely"], first["pessimistic"]), (20, 35, 60))
        self.assertTrue(first["high_uncertainty"])
        self.assertEqual(res["warnings"], [])

    def test_input_errors_raise(self):
        with self.assertRaises(estimate.InputError) as cm:
            estimate.run(["--item", "甲:20,35,60", "--item", "反了:30,20,40"])
        self.assertIn("反了", str(cm.exception))
        self.assertNotIn("「甲」", str(cm.exception))
        with self.assertRaises(estimate.InputError):
            estimate.run([])


class TestCli(unittest.TestCase):
    def _cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "estimate.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def assertCleanError(self, proc, fragment):
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(fragment, proc.stderr)

    def test_markdown_output(self):
        proc = self._cli(*THREE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for frag in ("## 各項目", "## 合計", "## 承諾建議", "## 解讀", "| 甲 | 20 | 35 | 60 | 36.67 | 6.67 | 3 |",
                     "不確定性高，先拆小或先做技術探索", "62.67 人天", "7.21 人天", "**71.9 人天**",
                     "約有一半機率超時", "常態近似", "彼此獨立", "經驗值，依產業而異"):
            self.assertIn(frag, proc.stdout)

    def test_order_violation_names_item(self):
        proc = self._cli("--item", "好的:1,2,3", "--item", "壞的:10,5,20")
        self.assertCleanError(proc, "「壞的」")
        self.assertIn("樂觀 ≤ 最可能 ≤ 悲觀", proc.stderr)

    def test_non_positive_and_non_numeric_all_reported(self):
        p = write_csv("項目,樂觀,最可能,悲觀\nA,0,5,10\nB,-1,5,10\nC,abc,5,10\nD,1,,10\nE,5,4,3\n")
        try:
            proc = self._cli(p)
            self.assertCleanError(proc, "第 2 列「A」：樂觀「0」必須大於 0")
            self.assertIn("第 3 列「B」：樂觀「-1」必須大於 0", proc.stderr)
            self.assertIn("第 4 列「C」：樂觀「abc」不是數字", proc.stderr)
            self.assertIn("第 5 列「D」：缺少最可能", proc.stderr)
            self.assertIn("第 6 列「E」：必須符合", proc.stderr)
        finally:
            os.remove(p)

    def test_bad_confidence(self):
        self.assertCleanError(self._cli(*THREE, "--confidence", "85"), "只接受 80、90、95")
        self.assertCleanError(self._cli(*THREE, "--confidence", "abc"), "只接受 80、90、95")

    def test_input_mode_errors(self):
        self.assertCleanError(self._cli(), "請提供 CSV 檔路徑")
        self.assertCleanError(self._cli("no_such.csv"), "找不到檔案")
        self.assertCleanError(self._cli("--item", "甲:1,2"), "格式有誤")
        p = write_csv(BASE)
        try:
            self.assertCleanError(self._cli(p, "--item", "甲:1,2,3"), "只能擇一")
        finally:
            os.remove(p)

    def test_missing_column(self):
        p = write_csv("項目,樂觀,悲觀\nA,1,3\n")
        try:
            self.assertCleanError(self._cli(p), "缺少必要欄位")
        finally:
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
