"""dates.py 的單元測試。

執行（在 pm-field-guide 資料夾）：python -X utf8 -m unittest discover -s scripts/tests
"""

import contextlib
import io
import json
import os
import sys
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
FIX = os.path.join(HERE, "fixtures")

import dates  # noqa: E402

TODAY = "2026-11-13"


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = dates.main(argv)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def zeller_weekday_zh(y, m, d):
    """Zeller 同餘公式（格里曆），與 datetime 無關的獨立推算。h: 0=週六, 1=週日, 2=週一 ..."""
    if m < 3:
        m += 12
        y -= 1
    k, j = y % 100, y // 100
    h = (d + (13 * (m + 1)) // 5 + k + k // 4 + j // 4 + 5 * j) % 7
    return ["週六", "週日", "週一", "週二", "週三", "週四", "週五"][h]


class TestWeekday(unittest.TestCase):
    def test_known_dates(self):
        # 已知錨點：2026-11-14 是週六（任務說明）；2026-01-01 是週四；2000-01-01 是週六；
        # 2024-02-29 是週四。另以 Zeller 公式交叉驗證。
        known = {"2026-11-14": "週六", "2026-01-01": "週四", "2000-01-01": "週六", "2024-02-29": "週四",
                 "2026-11-17": "週二", "2026-12-25": "週五"}
        code, out, _ = run(["weekday", *known, "--json"])
        self.assertEqual(code, 0)
        got = {it["date"]: it["weekday"] for it in json.loads(out)["dates"]}
        for ds, wd in known.items():
            self.assertEqual(got[ds], wd, ds)
            y, m, d = map(int, ds.split("-"))
            self.assertEqual(zeller_weekday_zh(y, m, d), wd, ds)

    def test_zeller_agreement_whole_range(self):
        # 2025-01-01 到 2028-12-31 每一天都與 Zeller 公式一致（排除整串差一天的錯誤）
        d = date(2025, 1, 1)
        while d <= date(2028, 12, 31):
            self.assertEqual(dates.zh_weekday(d), zeller_weekday_zh(d.year, d.month, d.day), d)
            d = date.fromordinal(d.toordinal() + 1)

    def test_formats_and_year_rule(self):
        code, out, _ = run(["weekday", "2026-11-17", "2026/11/17", "11/17", "1/5", "6/1", "--today", TODAY, "--json"])
        r = [it["date"] for it in json.loads(out)["dates"]]
        # 11/17 → 今年；1/5 比今天早 312 天（>183）→ 明年；6/1 早 165 天 → 今年
        self.assertEqual(r, ["2026-11-17", "2026-11-17", "2026-11-17", "2027-01-05", "2026-06-01"])

    def test_invalid(self):
        for argv in (["weekday", "2026-02-30"], ["weekday", "13/40", "--today", TODAY],
                     ["weekday", "abc"], ["weekday", "11/17", "--today", "11/13"], ["weekday"]):
            code, _, err = run(argv)
            self.assertEqual(code, 2, argv)
            self.assertNotIn("Traceback", err)


class TestCheck(unittest.TestCase):
    def test_sample_with_wrong_label(self):
        code, out, _ = run(["check", os.path.join(FIX, "schedule_sample.md"), "--today", TODAY, "--json"])
        self.assertEqual(code, 1)  # 有錯 → exit 1
        r = json.loads(out)
        self.assertEqual(r["errors"], 1)
        wrong = [c for c in r["checked"] if c["status"] != "OK"]
        self.assertEqual(wrong[0]["date"], "2026-11-14")
        self.assertEqual(wrong[0]["labeled"], "週五")
        self.assertEqual(wrong[0]["actual"], "週六")
        # 所有格式都被辨識：（一）、(二)、（週三）、11-19（四）、週五、（星期一）、2026/12/25、12月1日、跨年 1/4
        self.assertEqual(len(r["checked"]), 10)
        texts = [c["text"] for c in r["checked"]]
        for t in ("11/17(二)", "2026-11-18（週三）", "11-19（四）", "11/20 週五", "11/23（星期一）", "12月1日（二）"):
            self.assertIn(t, texts)
        jan = [c for c in r["checked"] if c["text"].startswith("1/4")][0]
        self.assertEqual(jan["date"], "2027-01-04")  # 2027-01-01 是週五（2026 年 365 天，1/1 週四 +1），所以 1/4 是週一
        self.assertEqual(jan["status"], "OK")
        # 未標星期：11/30 要列出；「3-5 天」不列；網址內的數字不列
        unl = [u["text"] for u in r["unlabeled"]]
        self.assertIn("11/30", unl)
        self.assertNotIn("3-5", unl)
        self.assertFalse(any(u["line"] == 15 for u in r["unlabeled"]))

    def test_all_ok_exit_0(self):
        code, out, _ = run(["check", os.path.join(FIX, "schedule_ok.md"), "--today", TODAY])
        self.assertEqual(code, 0)
        self.assertIn("全部正確", out)

    def test_off_by_one_document(self):
        # 模擬「每個星期都差一天」的時程：每一個都要被抓出來
        import tempfile
        text = "11/16（二）\n11/17（三）\n11/18（四）\n11/19（五）\n11/20（六）\n"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(text)
            path = f.name
        try:
            code, out, _ = run(["check", path, "--today", TODAY, "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out)["errors"], 5)
        finally:
            os.remove(path)

    def test_english_weekday_labels(self):
        # 英文回覆常寫成 2026-11-23 (Mon)；要能核對，寫錯也要抓得到
        import tempfile
        text = ("Kickoff 2026-11-23 (Mon)\n"        # 正確
                "Review 2026-11-27 (Thu)\n"         # 實際是週五
                "Due 2026-12-22, Tuesday\n"         # 正確，逗號加全名
                "Ship 11/20 (Fri.)\n"               # 正確，縮寫帶句點
                "Sync 2026-11-18 (Wednesday)\n"     # 正確，全名
                "Demo 2026-11-19 (Tues)\n")         # 實際是週四
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(text)
            path = f.name
        try:
            code, out, _ = run(["check", path, "--today", "2026-11-17", "--json"])
            res = json.loads(out)
            self.assertEqual(code, 1)
            self.assertEqual(len(res["checked"]), 6)
            self.assertEqual(res["errors"], 2)
            wrong = sorted(c["line"] for c in res["checked"] if c["status"] != "OK")
            self.assertEqual(wrong, [2, 6])
            self.assertEqual(res["unlabeled"], [])
        finally:
            os.remove(path)

    def test_english_word_after_date_is_not_a_label(self):
        # 日期後面接的一般英文字（非星期）不可被當成星期標註
        import tempfile
        text = "Launch 2026-11-23 Monitoring starts\nFreeze 2026-11-24 Sunset the old flow\n"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(text)
            path = f.name
        try:
            code, out, _ = run(["check", path, "--today", "2026-11-17", "--json"])
            res = json.loads(out)
            self.assertEqual(code, 0)
            self.assertEqual(res["checked"], [])
            self.assertEqual(len(res["unlabeled"]), 2)
        finally:
            os.remove(path)

    def test_missing_file(self):
        code, _, err = run(["check", os.path.join(FIX, "nope.md")])
        self.assertEqual(code, 2)
        self.assertIn("找不到", err)


class TestAdd(unittest.TestCase):
    def test_plain_weekends(self):
        # 2026-11-13（五）+10 工作天：11/16–20（5 天）、11/23–27（5 天）→ 11/27（五）
        _, out, _ = run(["add", "2026-11-13", "10", "--json"])
        r = json.loads(out)
        self.assertEqual((r["result"], r["result_weekday"]), ("2026-11-27", "週五"))
        self.assertTrue(any("未提供假日檔" in n for n in r["notes"]))

    def test_holidays_and_makeup(self):
        # 虛構假日 11/19、11/20；虛構補班 11/21（六）。
        # 工作天依序：16,17,18,21(補班),23,24,25,26,27,30 → 第 10 天 = 11/30（一）
        _, out, _ = run(["add", "2026-11-13", "10", "--holidays", os.path.join(FIX, "holidays_fake.txt"),
                         "--makeup-workdays", os.path.join(FIX, "makeup_fake.txt"), "--json"])
        r = json.loads(out)
        self.assertEqual((r["result"], r["result_weekday"]), ("2026-11-30", "週一"))
        self.assertEqual(r["makeup_workdays_used"], ["2026-11-21"])

    def test_negative_and_zero(self):
        # 2026-11-16（一）−1 → 11/13（五）；−6 → 11/6（五）
        _, out, _ = run(["add", "2026-11-16", "-1", "--json"])
        self.assertEqual(json.loads(out)["result"], "2026-11-13")
        _, out, _ = run(["add", "2026-11-16", "-6", "--json"])
        self.assertEqual(json.loads(out)["result"], "2026-11-06")
        _, out, _ = run(["add", "2026-11-16", "0", "--json"])
        self.assertEqual(json.loads(out)["result"], "2026-11-16")

    def test_invalid(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("11/20\n")  # 沒有年份 → 拒絕
            bad = f.name
        try:
            for argv in (["add", "2026-11-13", "x"], ["add", "2026-11-13", "1.5"],
                         ["add", "2026-11-13", "3", "--holidays", bad],
                         ["add", "2026-11-13", "3", "--holidays", os.path.join(FIX, "holidays_fake.txt"),
                          "--makeup-workdays", os.path.join(FIX, "holidays_fake.txt")]):
                code, _, err = run(argv)
                self.assertEqual(code, 2, argv)
                self.assertNotIn("Traceback", err)
        finally:
            os.remove(bad)


class TestPlan(unittest.TestCase):
    def test_fixture_schedule(self):
        # 手算（無假日，--start 2026-11-16 週一）：
        #   需求訪談 3+1：11/16–11/19
        #   設計稿 5+2：11/20、23–27、30 → 結束 11/30，工作完成 11/26
        #   前端 8+2（前置 設計稿）：12/1–4、7–11、14 → 結束 12/14
        #   後端 6+1（前置 設計稿）：12/1–4、7–9 → 結束 12/9
        #   整合測試 4+1（前置 前端;後端，取最晚 12/14）：12/15–18、21 → 結束 12/21（一）
        #   緩衝 7 / 排定 33 = 21.2%；整體 11/16–12/21 共 26 個工作天
        code, out, _ = run(["plan", os.path.join(FIX, "plan_fake.csv"), "--start", "2026-11-16", "--json"])
        self.assertEqual(code, 0)
        r = json.loads(out)
        t = {x["task"]: x for x in r["tasks"]}
        self.assertEqual((t["虛構需求訪談"]["start"], t["虛構需求訪談"]["end"]), ("2026-11-16", "2026-11-19"))
        self.assertEqual((t["虛構設計稿"]["start"], t["虛構設計稿"]["work_end"], t["虛構設計稿"]["end"]),
                         ("2026-11-20", "2026-11-26", "2026-11-30"))
        self.assertEqual((t["虛構前端開發"]["start"], t["虛構前端開發"]["end"]), ("2026-12-01", "2026-12-14"))
        self.assertEqual((t["虛構後端開發"]["start"], t["虛構後端開發"]["end"]), ("2026-12-01", "2026-12-09"))
        self.assertEqual((t["虛構整合測試"]["start"], t["虛構整合測試"]["end"]), ("2026-12-15", "2026-12-21"))
        self.assertEqual((r["final_end"], r["final_end_weekday"]), ("2026-12-21", "週一"))
        self.assertEqual(r["total_buffer"], 7)
        self.assertAlmostEqual(r["buffer_share"], 7 / 33)
        self.assertEqual(r["span_workdays"], 26)
        self.assertTrue(r["has_parallel_tasks"])

    def test_markdown_has_weekday_on_every_date(self):
        _, md, _ = run(["plan", os.path.join(FIX, "plan_fake.csv"), "--start", "2026-11-16"])
        import re
        rows = [ln for ln in md.splitlines() if ln.startswith("| 虛構")]
        self.assertEqual(len(rows), 5)
        for ln in rows:
            ds = re.findall(r"\d{4}-\d{2}-\d{2}(?!（)", ln)
            self.assertEqual(ds, [], f"日期沒有標星期：{ln}")
        self.assertIn("緩衝佔排定天數的 21.2%", md)

    def test_start_on_weekend_and_holidays(self):
        # --start 11/14（六）→ 順延到 11/16；假日 11/19、11/20 使需求訪談（4 天）落在 16,17,18,23
        _, out, _ = run(["plan", os.path.join(FIX, "plan_fake.csv"), "--start", "2026-11-14",
                         "--holidays", os.path.join(FIX, "holidays_fake.txt"), "--json"])
        r = json.loads(out)
        self.assertEqual(r["tasks"][0]["start"], "2026-11-16")
        self.assertEqual(r["tasks"][0]["end"], "2026-11-23")

    def test_bad_plans(self):
        import tempfile
        bodies = [
            "task,workdays,depends_on\nA,3,\nB,2,不存在\n",      # 前置不存在
            "task,workdays,depends_on\nA,3,B\nB,2,A\n",          # 循環
            "task,workdays\nA,3\nA,2\n",                          # 名稱重複
            "task,workdays\nA,0.5\n",                             # 非整數
            "name,days\nA,3\n",                                   # 缺欄位
        ]
        for body in bodies:
            with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
                f.write(body)
                path = f.name
            try:
                code, _, err = run(["plan", path, "--start", "2026-11-16"])
                self.assertEqual(code, 2, body)
                self.assertNotIn("Traceback", err)
            finally:
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
