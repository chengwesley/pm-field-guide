<div align="center">

# PM Field Guide

**一本會自己翻到對的那一頁的 PM 實戰手冊**

把軟體 PM 的 50 項核心能力做成一個 [Claude Code](https://claude.com/claude-code) skill。<br>
描述你眼前的狀況，它會找出該用的方法，先問清楚，再交出能直接拿去開會的東西。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Guides](https://img.shields.io/badge/%E6%8C%87%E5%8D%97-50_%E4%BB%BD-green)
![Tools](https://img.shields.io/badge/%E5%B7%A5%E5%85%B7-4_%E8%85%B3%E6%9C%AC_%2B_3_%E8%A1%A8%E5%96%AE-yellow)
![Claude Code Skill](https://img.shields.io/badge/Claude_Code-skill-orange)

**繁體中文** ｜ [English](README.en.md)

[快速開始](#-快速開始) · [為什麼用它](#-為什麼不直接問-ai) · [情境地圖](#-情境地圖你現在在哪個狀況) · [50 項清單](#-50-項能力清單) · [內附工具](#-內附工具) · [客製化](#-改成你們團隊的版本)

</div>

---

## 📦 裡面有什麼

| | 數量 | 內容 |
|---|:---:|---|
| 📘 **指南** | 50 份 | 一項能力一份，從市場調查到情緒管理 |
| 🧮 **計算腳本** | 4 支 | RICE 排序、漏斗分析、A/B 測試、日期核對 |
| 📊 **Excel 表單** | 3 份 | RICE 排序表、風險登記表、UAT 測試案例表 |
| ✅ **品質驗證** | 4 題 | 附評分項目的 PM 情境，改版後可以重跑比較 |

## 🚀 快速開始

```bash
git clone https://github.com/chengwesley/pm-field-guide.git ~/.claude/skills/pm-field-guide
```

裝好就能用，沒有指令要記。直接在 Claude Code 裡描述你的狀況，例如：

```
業務第三次來要匯出 Excel，RD 排滿到 Q1，我該怎麼評估？
老闆要 12 月上線，RD 估要到 2 月，明天一對一我要怎麼談？
A/B 測試出來了，行銷說 B 贏了要全量，幫我看這組數字
```

> 只想在某個專案裡用？改 clone 到該專案的 `.claude/skills/pm-field-guide`。

## 💡 為什麼不直接問 AI？

直接問 AI，通常會拿到格式漂亮、但套到你身上不太對的通用答案。

| | 一般 AI 回答 | PM Field Guide |
|---|---|---|
| **開始前** | 直接開寫 | 先追問缺的關鍵資訊：誰要、拿去做什麼、證據在哪 |
| **數字** | 自己補一個看起來合理的 | 不編數字，沒給的留 `____` 或標「假設值」 |
| **結論** | 列一堆框架讓你挑 | 直接說要做什麼、不做什麼、依據是什麼 |
| **下一步** | 「持續追蹤」 | 寫出負責人和日期，日期附星期並用腳本核對 |
| **數據判讀** | 「B 組看起來比較好」 | 用腳本實際算顯著性、樣本比例失衡、樣本數 |

<details>
<summary><b>👀 實際走一遍：業務插單要不要做？</b></summary>

<br>

> **你：** 業務第三次跟我說，客戶要能把記帳 SaaS 的交易紀錄匯出成 Excel，說不做會掉單。RD 排滿到 Q1，我該怎麼評估？

Claude 會依序讀「需求分析 → 需求排序 → Business 溝通」三份指南，然後：

1. **拆開「解法式需求」**：客戶要的是 Excel，還是要給會計師對帳？CSV 或既有報表能不能先解決？
2. **要求證據**：是哪幾家客戶、合約金額多少、續約日在什麼時候。「會掉單」要能被驗證。
3. **評估與排序**：用 RICE 跟其他候選需求放在一起比，影響範圍用 B2B 的單位（客戶家數、合約金額）。
4. **給業務的回覆話術**：不當場答應，也不直接拒絕。
5. **下一步**：每一項都寫出負責人和日期。

</details>

## 📍 情境地圖：你現在在哪個狀況？

不用記編號，用自己的話講就好。下表是總覽，點開各狀態可以看到完整對照。

| 狀態 | 典型情境 | 主要指南 |
|---|---|---|
| 🧭 方向還沒定 | 市場多大、怎麼定價、明年往哪走 | 01–05、07 |
| 📥 需求一直湧進來 | 插單、需求排不完、不知道主管要什麼 | 08–12、41 |
| ✍️ 想法要變成規格 | 寫 PRD、拆 Epic、串 API、畫流程 | 15–16、21–26 |
| ⏱️ 時程或資源卡住 | 老闆日期對不上、兩個 BU 搶 RD | 27–30、38、48 |
| 🚀 準備上線 | UAT、QA、客服素材、A/B 要不要全量 | 19–20、31–32、44–45 |
| 📉 上線後數字不好 | 沒人用、營收掉、用戶卡關 | 13、18、20、33–35 |
| 🤝 卡在人 | 跨部門、RD、提案、海外團隊 | 36、40、42、46–47 |
| 😮‍💨 你自己快撐不住 | 被否決、被追著跑、想交給 AI | 49–50 |

<details>
<summary><b>🧭 方向還沒定</b></summary>

| 你可能會說 | 用到的指南 | 你會拿到 |
|---|---|---|
| 「老闆問這個市場有多大、值不值得進」 | [01 市場調查](references/01-market-research.md) | TAM／SAM／SOM 推估、敏感度分析、待驗證的假設 |
| 「我們跟對手到底差在哪？」 | [02 競品分析](references/02-competitive-analysis.md) | 比較矩陣、差異化機會、要避開的正面對決 |
| 「方案要怎麼定價、怎麼賺錢？」 | [03 商業模式](references/03-business-model.md) | 收入結構、單位經濟（LTV／CAC）、最脆弱的假設 |
| 「明年產品要往哪走？」 | [04 產品策略](references/04-product-strategy.md) → [05 Roadmap](references/05-roadmap-planning.md) | 策略一頁版（含「不做什麼」）、Now／Next／Later 路線圖 |
| 「這個功能怎樣才算成功？」 | [07 KPI 設定](references/07-kpi-setting.md) | 北極星指標、護欄指標、事前寫定的成功門檻 |

</details>

<details>
<summary><b>📥 需求一直湧進來</b></summary>

| 你可能會說 | 用到的指南 | 你會拿到 |
|---|---|---|
| 「業務、大客戶或老闆要插單，要不要做？」 | [11 需求分析](references/11-requirement-analysis.md) → [08 需求排序](references/08-requirement-prioritization.md) → [41 Business 溝通](references/41-business-communication.md) | 真正的問題、RICE 排序、給需求方的回覆話術 |
| 「需求太多，排不完」 | [08 需求排序](references/08-requirement-prioritization.md) | RICE／ICE／MoSCoW 排序表加產能線 |
| 「主管要一個儀表板，但我不知道他要看什麼」 | [10 利害關係人訪談](references/10-stakeholder-interview.md) | 利害關係人盤點、訪談題綱、對齊紀錄 |
| 「想知道用戶實際怎麼用」 | [09 用戶研究](references/09-user-research.md) → [12 行為分析](references/12-behavior-analysis.md) | 研究計畫、篩選題、事件埋點規劃 |

</details>

<details>
<summary><b>✍️ 想法要變成規格</b></summary>

| 你可能會說 | 用到的指南 | 你會拿到 |
|---|---|---|
| 「幫我寫 PRD，下週要跟 RD 對」 | [21 PRD](references/21-prd-writing.md) → [23 驗收條件](references/23-acceptance-criteria.md) → [24 系統邏輯](references/24-system-logic.md) | 含非目標與編號需求的 PRD、可測的驗收條件、狀態機 |
| 「這個 Epic 太大，要怎麼拆？」 | [22 User Story](references/22-user-story.md) | 切好的故事，每一則都能獨立交付 |
| 「要串第三方 API」 | [25 API 與系統整合](references/25-api-integration.md) → [26 資料結構](references/26-data-structure.md) | 資料流、錯誤與重試、冪等、對帳規則 |
| 「流程好複雜，畫不清楚」 | [15 User Flow](references/15-user-flow.md) → [16 Wireframe](references/16-wireframe.md) | 主流程、分支、異常路徑，以及加了標註的線框 |

</details>

<details>
<summary><b>⏱️ 時程或資源卡住</b></summary>

| 你可能會說 | 用到的指南 | 你會拿到 |
|---|---|---|
| 「老闆要的日期和 RD 估的對不上」 | [48 向上管理](references/48-managing-up.md) → [38 衝突協調](references/38-conflict-resolution.md) → [27 時程管理](references/27-schedule-management.md) | 幾種範圍或時程選項與各自代價、一對一的開場白 |
| 「兩個 BU 搶同一批 RD」 | [38 衝突協調](references/38-conflict-resolution.md) → [28 資源調度](references/28-resource-allocation.md) | 決策框架、取捨方案、何時重新評估的條件 |
| 「感覺專案會出事，但說不出哪裡」 | [30 風險管理](references/30-risk-management.md) → [29 進度追蹤](references/29-progress-tracking.md) | 風險登記表（機率×衝擊、早期指標）、週報格式 |

</details>

<details>
<summary><b>🚀 準備上線</b></summary>

| 你可能會說 | 用到的指南 | 你會拿到 |
|---|---|---|
| 「下個月要上線，該準備什麼？」 | [31 UAT](references/31-uat.md) → [44 QA 測試](references/44-qa-testing.md) → [32 GTM](references/32-gtm-launch.md) | UAT 計畫、缺陷分級、上線檢查表與回滾條件 |
| 「客服要怎麼回答新功能的問題？」 | [45 客服溝通](references/45-customer-support-communication.md) | 上線客服素材包、話術、客服回饋月報 |
| 「行銷說 B 組贏了，要全量」 | [19 A/B 測試](references/19-ab-testing.md) → [20 數據分析](references/20-data-analysis.md) | 實際算出的顯著性與 SRM 檢查、能不能全量的結論 |

</details>

<details>
<summary><b>📉 上線後數字不好</b></summary>

| 你可能會說 | 用到的指南 | 你會拿到 |
|---|---|---|
| 「新功能沒人用」 | [34 成效追蹤](references/34-performance-tracking.md) → [13 漏斗分析](references/13-funnel-analysis.md) → [35 產品迭代](references/35-product-iteration.md) | 成效判讀、最大漏損點、下一輪要做什麼 |
| 「營收或訂閱數掉了，老闆問為什麼」 | [20 數據分析](references/20-data-analysis.md) | 拆解路徑、要排除的干擾因素、結論有多可靠 |
| 「用戶一直卡在同一步」 | [33 UX 優化](references/33-ux-optimization.md) → [18 易用性測試](references/18-usability-testing.md) | 摩擦點清單、本輪優化計畫、易用性測試設計 |

</details>

<details>
<summary><b>🤝 卡在人</b></summary>

| 你可能會說 | 用到的指南 | 你會拿到 |
|---|---|---|
| 「需要財務配合，但我沒有指揮權」 | [36 跨部門溝通](references/36-cross-department-communication.md) | 跨部門請託範本、追蹤紀錄、話術 |
| 「RD 覺得我需求講不清楚」 | [42 RD 溝通](references/42-rd-communication.md) | 講需求的順序，以及怎麼談估時與取捨 |
| 「要說服老闆投資源」 | [47 提案說服](references/47-proposal-persuasion.md) → [40 簡報製作](references/40-presentation-making.md) | 提案結構、預想的反對意見與回應 |
| 「要跟海外團隊合作」 | [46 跨國溝通](references/46-cross-border-communication.md) | 跨時區請求訊息、雙方協作約定、話術 |

</details>

<details>
<summary><b>😮‍💨 你自己快撐不住</b></summary>

| 你可能會說 | 用到的指南 | 你會拿到 |
|---|---|---|
| 「提案被否決，同一週又被業務追著跑」 | [50 情緒管理](references/50-emotion-management.md) | 當下的情緒紀錄、跟主管一對一的準備卡、話術 |
| 「哪些工作可以交給 AI？」 | [49 AI 工具](references/49-ai-tools.md) | 哪些適合、哪些不適合交給 AI，提示詞範本，資料安全界線 |

</details>

## 📚 50 項能力清單

每份指南都是同一套結構：**何時用 → 動手前先問 → 做法 → 產出模板 → 品質檢查 → 常見錯誤 → 情境範例 → 相關指南**。沒有安裝 skill，也能直接當手冊讀。

<details>
<summary><b>展開完整清單</b></summary>

<br>

**A. 市場與策略**
[01 市場調查](references/01-market-research.md) · [02 競品分析](references/02-competitive-analysis.md) · [03 商業模式](references/03-business-model.md) · [04 產品策略](references/04-product-strategy.md) · [05 Roadmap](references/05-roadmap-planning.md) · [06 成本評估](references/06-cost-estimation.md) · [07 KPI 設定](references/07-kpi-setting.md)

**B. 需求與研究**
[08 需求排序](references/08-requirement-prioritization.md) · [09 用戶研究](references/09-user-research.md) · [10 利害關係人訪談](references/10-stakeholder-interview.md) · [11 需求分析](references/11-requirement-analysis.md) · [12 行為分析](references/12-behavior-analysis.md) · [13 漏斗分析](references/13-funnel-analysis.md)

**C. 設計與驗證**
[14 資訊架構](references/14-information-architecture.md) · [15 User Flow](references/15-user-flow.md) · [16 Wireframe](references/16-wireframe.md) · [17 Prototype](references/17-prototype.md) · [18 易用性測試](references/18-usability-testing.md) · [19 A/B 測試](references/19-ab-testing.md) · [20 數據分析](references/20-data-analysis.md)

**D. 規格文件**
[21 PRD](references/21-prd-writing.md) · [22 User Story](references/22-user-story.md) · [23 驗收條件](references/23-acceptance-criteria.md) · [24 系統邏輯](references/24-system-logic.md) · [25 API 與系統整合](references/25-api-integration.md) · [26 資料結構](references/26-data-structure.md)

**E. 專案管理**
[27 時程管理](references/27-schedule-management.md) · [28 資源調度](references/28-resource-allocation.md) · [29 進度追蹤](references/29-progress-tracking.md) · [30 風險管理](references/30-risk-management.md) · [31 UAT](references/31-uat.md)

**F. 上線與迭代**
[32 GTM 上線](references/32-gtm-launch.md) · [33 UX 優化](references/33-ux-optimization.md) · [34 成效追蹤](references/34-performance-tracking.md) · [35 產品迭代](references/35-product-iteration.md)

**G. 溝通與協作**
[36 跨部門溝通](references/36-cross-department-communication.md) · [37 利害關係人管理](references/37-stakeholder-management.md) · [38 衝突協調](references/38-conflict-resolution.md) · [39 會議主持](references/39-meeting-facilitation.md) · [40 簡報製作](references/40-presentation-making.md) · [41 Business 溝通](references/41-business-communication.md) · [42 RD 溝通](references/42-rd-communication.md) · [43 UIUX 協作](references/43-uiux-collaboration.md) · [44 QA 測試](references/44-qa-testing.md) · [45 客服溝通](references/45-customer-support-communication.md) · [46 跨國溝通](references/46-cross-border-communication.md) · [47 提案說服](references/47-proposal-persuasion.md) · [48 向上管理](references/48-managing-up.md)

**H. 工具與心態**
[49 AI 工具](references/49-ai-tools.md) · [50 情緒管理](references/50-emotion-management.md)

</details>

## 🧮 內附工具

能算的就不靠感覺。下面 4 支腳本只用 Python 標準函式庫，裝好就能跑：

| 腳本 | 解決什麼 | 範例 |
|---|---|---|
| `rice.py` | 需求排序：RICE 分數、產能線、敏感度（估值差兩倍，排名會不會變） | `python3 scripts/rice.py 需求.csv --capacity 4` |
| `funnel.py` | 漏斗：各步轉換率、最大漏損點、跟前期比較是否顯著 | `python3 scripts/funnel.py 漏斗.csv` |
| `ab_test.py` | A/B 測試：需要多少樣本、要跑幾天；結果的顯著性與樣本比例失衡 | `python3 scripts/ab_test.py size --baseline 12% --mde 10% --daily-traffic 3000` |
| `dates.py` | 日期：核對文件裡的星期、加減工作天、排時程 | `python3 scripts/dates.py check 草稿.md` |

另外有 3 份可以直接填的 Excel 表單，放在 `assets/`：**RICE 排序表**、**風險登記表**、**UAT 測試案例表**。

<details>
<summary>細節與測試</summary>

- 每支腳本都有 `--help`。CSV 欄名中英文都可以，加 `--json` 會輸出機器可讀格式。
- `dates.py` 沒有內建國定假日，因為假日不能用猜的。要跳過假日時，用 `--holidays` 和 `--makeup-workdays` 指定你自己的假日檔與補班日檔。
- 腳本附 58 個自動化測試：`python3 -m pytest scripts/tests`
- 要調整 Excel 表單，修改 `scripts/build_templates.py` 後重新產生。這支需要 `openpyxl`。

</details>

## 🔧 改成你們團隊的版本

範例橫跨外送平台、電商、記帳 SaaS、線上課程、預約系統、健身 App 等產業，數字都是示意或假設值。要更貼近你們的團隊，改兩個地方就好：

1. **`SKILL.md` 最後的「情境與合規提醒」**：換成你們的產品、適用的法規與對外審核流程。
2. **各指南的「情境範例」**：換成你們自己的產品情境，Claude 舉的例子就會更貼近你們的狀況。

## ✅ 品質驗證

`evals/evals.json` 有 4 個貼近實務的 PM 情境，每個都附具體的評分項目，例如有沒有寫非目標、驗收條件能不能測、有沒有捏造數字、p 值算得對不對、日期的星期對不對。改了 skill 之後拿來重跑一次，就知道有沒有退步。

## 📄 授權

[MIT](LICENSE)。歡迎 fork 改成你們團隊的版本，覺得有用也歡迎給顆星 ⭐

<div align="center">
<sub>由 Wesley Cheng 製作</sub>
</div>
