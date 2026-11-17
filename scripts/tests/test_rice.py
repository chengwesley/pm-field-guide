"""rice.py 測試。執行：在 pm-field-guide 資料夾下 `python -X utf8 -m unittest discover -s scripts/tests`。"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import rice  # noqa: E402


def write_csv(text: str, bom: bool = True) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        f.write(text)
    return path


def run_json(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rice.run(argv + ["--json"])
    return json.loads(buf.getvalue())


# 手算基準資料（與 fixtures/rice_sample.csv 相同的數字）：
#   甲：1000 × 2    × 0.8 ÷ 2   = 800
#   乙： 500 × 3    × 0.5 ÷ 1   = 750
#   丙：2000 × 1    × 1.0 ÷ 4   = 500
#   丁： 300 × 0.5  × 0.5 ÷ 0.5 = 150
#   戊：  40 × 0.25 × 0.8 ÷ 1   =   8
# 排名：甲 > 乙 > 丙 > 丁 > 戊；5 項分層 = 2 高、2 中、1 低。
BASE = (
    "item,reach,impact,confidence,effort,note\n"
    "甲,1000,2,80%,2,問卷\n"
    "乙,500,3,0.5,1,\n"
    "丙,2000,1,100,4,log\n"
    "丁,300,0.5,50%,0.5,\n"
    "戊,40,0.25,0.5,1,\n"
)


class TestParsing(unittest.TestCase):
    def test_confidence_formats(self):
        self.assertAlmostEqual(rice.parse_confidence("80"), 0.8)
        self.assertAlmostEqual(rice.parse_confidence("80%"), 0.8)
        self.assertAlmostEqual(rice.parse_confidence("0.8"), 0.8)
        self.assertAlmostEqual(rice.parse_confidence("100％"), 1.0)  # 全形百分號
        with self.assertRaises(ValueError):
            rice.parse_confidence("150")
        with self.assertRaises(ValueError):
            rice.parse_confidence("abc")

    def test_tier_sizes(self):
        self.assertEqual(rice.tier_sizes(5), [2, 2, 1])
        self.assertEqual(rice.tier_sizes(6), [2, 2, 2])
        self.assertEqual(rice.tier_sizes(7), [3, 2, 2])
        self.assertEqual(rice.tier_sizes(1), [1, 0, 0])


class TestScoring(unittest.TestCase):
    def setUp(self):
        self.path = write_csv(BASE)

    def tearDown(self):
        os.remove(self.path)

    def test_scores_rank_tiers(self):
        res = run_json([self.path])
        got = [(x["item"], x["score"], x["tier"]) for x in res["items"]]
        self.assertEqual(got, [("甲", 800, "高"), ("乙", 750, "高"), ("丙", 500, "中"),
                               ("丁", 150, "中"), ("戊", 5, "低")])  # 戊：40×0.25×0.5÷1 = 5

    def test_capacity_line(self):
        # 產能 4：甲 累計 2 ✓、乙 累計 3 ✓、丙 累計 7 ✗ → 停；丁、戊 也不做。
        res = run_json([self.path, "--capacity", "4"])
        self.assertEqual([x["in_plan"] for x in res["items"]], [True, True, False, False, False])
        self.assertEqual(res["capacity_used"], 3)
        self.assertEqual(res["capacity_remaining"], 1)
        self.assertEqual(res["not_in_plan"], ["丙", "丁", "戊"])
        # 剩 1 人月，丁（0.5）、戊（1）放得進 → 解讀要提到
        self.assertTrue(any("丁（0.5 人月）" in o for o in res["interpretation"]))

    def test_sensitivity_with_capacity(self):
        # 手算（產能 4）：
        #  甲 觸及×0.5 → 400：乙750、丙500、甲400 → 乙1、丙累計5>4 停 → 甲出局 → 敏感
        #  甲 工作量×2 → 4 人月、分數 400 → 同上出局
        #  乙 觸及×0.5 → 375：甲2、丙累計6 停 → 乙出局 → 敏感
        #  丙 觸及×2 → 1000：丙4 ✓、甲累計6 停 → 丙進來 → 敏感
        #  丁 觸及×2 → 300、工作量×0.5 → 300：仍在丙之後，丙擋住 → 不變
        #  戊 不變
        res = run_json([self.path, "--capacity", "4"])
        flags = {x["item"]: x["sensitive"] for x in res["items"]}
        self.assertEqual(flags, {"甲": True, "乙": True, "丙": True, "丁": False, "戊": False})
        a = {s["variant"]: s for s in res["items"][0]["sensitivity"]}
        self.assertTrue(a["觸及×0.5"]["changes_conclusion"])
        self.assertEqual(a["觸及×0.5"]["rank"], 3)
        self.assertFalse(a["觸及×2"]["changes_conclusion"])
        self.assertTrue(a["工作量×2"]["changes_conclusion"])
        self.assertAlmostEqual(a["工作量×2"]["score"], 400)

    def test_sensitivity_without_capacity_uses_tiers(self):
        # 甲 觸及×0.5 → 400 → 排第 3 → 中層（原本高）→ 敏感
        # 戊 觸及×2 → 10，仍最後 → 不變
        res = run_json([self.path])
        a = {s["variant"]: s for s in res["items"][0]["sensitivity"]}
        self.assertEqual(a["觸及×0.5"]["tier"], "中")
        self.assertTrue(a["觸及×0.5"]["changes_conclusion"])
        self.assertFalse(res["items"][-1]["sensitive"])
        self.assertIsNone(res["items"][0]["in_plan"])


class TestWarningsAndMust(unittest.TestCase):
    def test_fixture_warnings_and_must(self):
        res = run_json([str(FIXTURES / "rice_sample.csv"), "--capacity", "4"])
        self.assertEqual([m["item"] for m in res["must_items"]], ["法規更新"])
        self.assertEqual(res["must_items"][0]["effort"], 1.5)
        self.assertNotIn("法規更新", [x["item"] for x in res["items"]])
        w = "\n".join(res["warnings"])
        self.assertIn("觸及單位混用", w)
        self.assertIn("沒有依據的信心值建議最高 50%", w)
        self.assertIn("功能戊（80%）", w)        # 80% 沒依據 → 警告
        self.assertNotIn("功能甲（80%）", w)      # 有依據 → 不警告
        self.assertNotIn("功能丁", w)              # 剛好 50% 不算 > 50%

    def test_nonstandard_impact_warns_not_fails(self):
        p = write_csv("item,reach,impact,confidence,effort,note\nX,100,1.5,50,1,\n")
        try:
            res = run_json([p])
            self.assertEqual(res["items"][0]["score"], 75)  # 100 × 1.5 × 0.5 ÷ 1
            self.assertTrue(any("不在標準刻度" in w for w in res["warnings"]))
        finally:
            os.remove(p)

    def test_must_truthy_values(self):
        text = "項目,觸及,影響,信心,工作量,必做\n" + "".join(
            f"M{i},,,,,{v}\n" for i, v in enumerate(["是", "Y", "yes", "TRUE", "1"])
        ) + "S,10,1,50,1,否\n"
        p = write_csv(text)
        try:
            res = run_json([p])
            self.assertEqual(len(res["must_items"]), 5)
            self.assertEqual([x["item"] for x in res["items"]], ["S"])
        finally:
            os.remove(p)

    def test_english_aliases_case_insensitive(self):
        p = write_csv("Item,Reach,Impact,Confidence,Effort\nA,10,1,0.5,1\n", bom=False)
        try:
            self.assertEqual(run_json([p])["items"][0]["score"], 5)
        finally:
            os.remove(p)


class TestCliErrors(unittest.TestCase):
    def _cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "rice.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def assertCleanError(self, proc, fragment):
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(fragment, proc.stderr)

    def test_missing_file(self):
        self.assertCleanError(self._cli("no_such.csv"), "找不到檔案")

    def test_missing_column(self):
        p = write_csv("項目,觸及,影響,信心\nA,1,1,50\n")
        try:
            self.assertCleanError(self._cli(p), "缺少必要欄位")
        finally:
            os.remove(p)

    def test_bad_values_all_reported(self):
        p = write_csv("項目,觸及,影響,信心,工作量\nA,abc,1,50,1\nB,10,-1,50,0\nC,10,1,200,1\n")
        try:
            proc = self._cli(p)
            self.assertCleanError(proc, "觸及「abc」不是數字")
            self.assertIn("工作量必須大於 0", proc.stderr)
            self.assertIn("影響「-1」必須是正數", proc.stderr)
            self.assertIn("信心「200」無法解讀", proc.stderr)
        finally:
            os.remove(p)

    def test_bad_capacity_arg(self):
        p = write_csv(BASE)
        try:
            self.assertCleanError(self._cli(p, "--capacity", "abc"), "不是數字")
            self.assertCleanError(self._cli(p, "--capacity", "0"), "產能必須大於 0")
        finally:
            os.remove(p)

    def test_non_utf8(self):
        fd, p = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "wb") as f:
            f.write("項目,觸及,影響,信心,工作量\nA,1,1,50,1\n".encode("cp950"))
        try:
            self.assertCleanError(self._cli(p), "不是 UTF-8")
        finally:
            os.remove(p)

    def test_markdown_and_csv_out(self):
        p = write_csv(BASE)
        fd, out = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            proc = self._cli(p, "--capacity", "4", "--csv-out", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("── 產能線：4 人月 ──", proc.stdout)
            self.assertIn("## 解讀", proc.stdout)
            self.assertIn("敏感：估值差兩倍就會改變結論", proc.stdout)
            raw = Path(out).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            lines = raw.decode("utf-8-sig").splitlines()
            self.assertTrue(lines[0].startswith("排名,項目,分層,分數"))
            self.assertTrue(lines[1].startswith("1,甲,高,800"))
        finally:
            os.remove(p)
            os.remove(out)


if __name__ == "__main__":
    unittest.main()
