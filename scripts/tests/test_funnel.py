"""funnel.py 測試。執行：在 pm-field-guide 資料夾下 `python -X utf8 -m unittest discover -s scripts/tests`。"""
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

import funnel  # noqa: E402


def write_csv(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as f:
        f.write(text)
    return path


def run_json(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        funnel.run(argv + ["--json"])
    return json.loads(buf.getvalue())


class TestZTest(unittest.TestCase):
    def test_known_values(self):
        # 600/1000 vs 500/1000：合併 p = 1100/2000 = 0.55
        #   SE = sqrt(0.55 × 0.45 × (1/1000 + 1/1000)) = sqrt(0.000495) = 0.0222486
        #   z = 0.10 / 0.0222486 = 4.4947；雙尾 p ≈ 6.97e-6
        t = funnel.two_proportion_z(600, 1000, 500, 1000)
        self.assertAlmostEqual(t["z"], 4.4947, places=3)
        self.assertAlmostEqual(t["p_value"], 6.97e-6, delta=0.05e-6)
        # 55/100 vs 50/100：合併 p = 0.525；SE = sqrt(0.525 × 0.475 × 0.02) = 0.070622
        #   z = 0.05 / 0.070622 = 0.7080；p = 2 × (1 − Φ(0.708)) ≈ 0.479
        t = funnel.two_proportion_z(55, 100, 50, 100)
        self.assertAlmostEqual(t["z"], 0.7080, places=3)
        self.assertAlmostEqual(t["p_value"], 0.479, places=3)
        # 同為 50% → z = 0、p = 1
        t = funnel.two_proportion_z(300, 600, 250, 500)
        self.assertEqual(t["z"], 0)
        self.assertAlmostEqual(t["p_value"], 1.0)

    def test_untestable(self):
        self.assertIsNone(funnel.two_proportion_z(0, 0, 1, 10)["p_value"])
        self.assertIsNone(funnel.two_proportion_z(10, 10, 5, 5)["p_value"])   # 都是 100%
        self.assertIsNone(funnel.two_proportion_z(12, 10, 5, 10)["p_value"])  # 超過 100%
        self.assertTrue(funnel.two_proportion_z(1, 10, 2, 10)["small_sample"])


class TestFunnel(unittest.TestCase):
    def test_fixture_numbers(self):
        # fixtures/funnel_sample.csv：A 1000 → B 600 → C 300 → D 240
        #   步驟轉換：B 60%、C 50%、D 80%；累計：60%、30%、24%
        #   流失：B 400（40%）、C 300（50%）、D 60（20%）
        #   最大漏損：人數 → B（400）；轉換率 → C（50%）；兩者不同
        res = run_json([str(FIXTURES / "funnel_sample.csv")])
        s = res["steps"]
        self.assertEqual([r["count"] for r in s], [1000, 600, 300, 240])
        self.assertIsNone(s[0]["step_conversion"])
        self.assertAlmostEqual(s[1]["step_conversion"], 0.6)
        self.assertAlmostEqual(s[2]["step_conversion"], 0.5)
        self.assertAlmostEqual(s[3]["step_conversion"], 0.8)
        self.assertAlmostEqual(s[3]["cumulative_conversion"], 0.24)
        self.assertEqual([r["drop_off"] for r in s[1:]], [400, 300, 60])
        self.assertAlmostEqual(s[2]["drop_off_rate"], 0.5)
        b = res["biggest_drop"]
        self.assertEqual(b["by_users_lost"]["step"], "步驟B")
        self.assertEqual(b["by_step_conversion"]["step"], "步驟C")
        self.assertFalse(b["same_step"])
        self.assertAlmostEqual(res["overall_conversion"], 0.24)

    def test_fixture_comparison(self):
        # 前期 1000 → 500 → 250 → 150：前期步驟轉換 50%、50%、60%
        #   B：+10.0 pp，z ≈ 4.49，顯著
        #   C：  0.0 pp，z = 0，p = 1 → 隨機波動
        #   D：240/300 vs 150/250 → 合併 390/550 = 0.70909；SE = sqrt(0.70909×0.29091×(1/300+1/250)) = 0.038894
        #      z = 0.20 / 0.038894 = 5.142 → 顯著
        res = run_json([str(FIXTURES / "funnel_sample.csv")])
        c = {x["step"]: x for x in res["comparison"]}
        self.assertAlmostEqual(c["步驟B"]["change_pp"], 10.0)
        self.assertAlmostEqual(c["步驟B"]["z"], 4.4947, places=3)
        self.assertFalse(c["步驟B"]["random_fluctuation_likely"])
        self.assertTrue(c["步驟C"]["random_fluctuation_likely"])
        self.assertIn("差異可能只是隨機波動", c["步驟C"]["verdict"])
        self.assertAlmostEqual(c["步驟D"]["z"], 5.142, places=2)
        self.assertAlmostEqual(res["prev_overall_conversion"], 0.15)
        self.assertTrue(any("獨立" in o for o in res["interpretation"]))

    def test_increase_warns(self):
        p = write_csv("step,users\nA,100\nB,120\nC,50\n")
        try:
            res = run_json([p])
            self.assertTrue(any("比上一步" in w and "追蹤" in w for w in res["warnings"]))
            self.assertAlmostEqual(res["steps"][1]["step_conversion"], 1.2)
            self.assertEqual(res["steps"][1]["drop_off"], -20)
        finally:
            os.remove(p)

    def test_same_step_biggest(self):
        # 100 → 90 → 30 → 27：人數流失最大 C（60），轉換率最低 C（33.3%）→ 相同
        p = write_csv("步驟,人數\nA,100\nB,90\nC,30\nD,27\n")
        try:
            res = run_json([p])
            self.assertTrue(res["biggest_drop"]["same_step"])
            self.assertEqual(res["biggest_drop"]["by_users_lost"]["step"], "C")
        finally:
            os.remove(p)

    def test_zero_step_no_crash(self):
        p = write_csv("step,count\nA,10\nB,0\nC,0\n")
        try:
            res = run_json([p])
            self.assertIsNone(res["steps"][2]["step_conversion"])
        finally:
            os.remove(p)


class TestCliErrors(unittest.TestCase):
    def _cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "funnel.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def assertCleanError(self, proc, fragment):
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(fragment, proc.stderr)

    def test_invalid_counts(self):
        p = write_csv("步驟,人數\nA,100\nB,-5\nC,1.5\nD,abc\n")
        try:
            proc = self._cli(p)
            self.assertCleanError(proc, "不能是負數")
            self.assertIn("必須是整數", proc.stderr)
            self.assertIn("不是數字", proc.stderr)
        finally:
            os.remove(p)

    def test_missing_prev_value(self):
        p = write_csv("步驟,人數,前期人數\nA,100,90\nB,50,\n")
        try:
            self.assertCleanError(self._cli(p), "缺少前期人數")
        finally:
            os.remove(p)

    def test_single_step(self):
        p = write_csv("步驟,人數\nA,100\n")
        try:
            self.assertCleanError(self._cli(p), "至少要有 2 個步驟")
        finally:
            os.remove(p)

    def test_missing_args(self):
        proc = self._cli()
        self.assertCleanError(proc, "缺少必要參數")

    def test_markdown_and_csv_out(self):
        fd, out = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            proc = self._cli(str(FIXTURES / "funnel_sample.csv"), "--csv-out", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("## 最大漏損", proc.stdout)
            self.assertIn("## 與前期比較", proc.stdout)
            self.assertIn("差異可能只是隨機波動", proc.stdout)
            raw = Path(out).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            lines = raw.decode("utf-8-sig").splitlines()
            self.assertEqual(lines[2].split(",")[:6], ["步驟B", "600", "60.0", "60.0", "400", "40.0"])
        finally:
            os.remove(out)


if __name__ == "__main__":
    unittest.main()
