<div align="center">

# PM Field Guide｜PM 生存指南

**一本會自己翻到對的那一頁的 PM 生存指南**

50 項軟體 PM 核心能力，做成一個 [Claude Code](https://claude.com/claude-code) skill。<br>
你描述眼前的狀況，它找出該用的方法，先問清楚，再交出能直接拿去開會的東西。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Guides](https://img.shields.io/badge/guides-50-green)
![Tools](https://img.shields.io/badge/%E5%B7%A5%E5%85%B7-4_%E8%85%B3%E6%9C%AC_%2B_3_%E8%A1%A8%E5%96%AE-yellow)
![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-skill-orange)

**50 份指南 · 4 支計算腳本 · 3 份 Excel 表單**

**繁體中文** ｜ [English](README.en.md)

[為什麼需要它](#為什麼需要它) · [看它怎麼做](#看它怎麼做) · [情境對照](#你現在在哪個狀況) · [安裝](#安裝) · [內附工具](#內附工具會算的就不靠感覺) · [客製化](#改成你們團隊的版本)

</div>

---

## 為什麼需要它

你一定遇過這些時刻：

- 業務第三次來說「客戶要這個功能，不做會掉單」，RD 卻排滿到下一季。
- 老闆在週會上說「一個月後上線」，RD 估要三個月，你夾在中間。
- A/B 測試跑出來，行銷說 B 明顯贏了，要你今天就全量。
- 寫好的 PRD 沒人讀，開發到一半才發現大家理解的不一樣。

直接問 AI，通常會拿到一份格式漂亮、但套到你身上不太對的通用答案。PM Field Guide 的做法不一樣：

<table width="100%">
<tr><th width="418">一般 AI 回答</th><th width="418">用 PM Field Guide</th></tr>
<tr><td>直接開始寫</td><td><b>先追問</b>缺的關鍵資訊：誰要、拿去做什麼、證據在哪</td></tr>
<tr><td>數字自己補，看起來很合理</td><td><b>不編數字</b>：沒給的留 <code>____</code> 或標「假設值」</td></tr>
<tr><td>列一堆框架讓你自己選</td><td><b>給結論</b>：要做什麼、不做什麼、依據是什麼</td></tr>
<tr><td>「下一步：持續追蹤」</td><td>下一步寫<b>負責人和日期</b>，日期附星期並用腳本核對</td></tr>
<tr><td>憑感覺說「B 組比較好」</td><td>用內附腳本<b>實際計算</b>顯著性、樣本比例失衡、樣本數</td></tr>
</table>

## 看它怎麼做

> **你：** 業務第三次跟我說，客戶要能把記帳 SaaS 的交易紀錄匯出成 Excel，說不做會掉單。RD 排滿到 Q1，我該怎麼評估？

Claude 會依序讀三份指南：「需求分析」「需求排序」「Business 溝通」。然後：

1. **拆開「解法式需求」**：客戶要的是 Excel，還是給會計師對帳？用 CSV 或既有報表能不能解決？
2. **要求證據**：哪幾家客戶、合約金額多少、續約日在什麼時候。「會掉單」要能被驗證。
3. **評估與排序**：用 RICE 和其他候選需求放在一起比，影響範圍用 B2B 的單位（客戶家數、合約金額）。
4. **給業務的回覆話術**：不直接答應，也不直接拒絕。
5. **下一步**：每一項都有負責人和日期。

## 你現在在哪個狀況？

找到最像你的那一句，右邊就是 Claude 會用到的指南。你不用記編號，直接用自己的話講就好。

### 方向還沒定

<table width="100%">
<tr><th width="260">你可能會說</th><th width="210">用到的指南</th><th width="366">你會拿到</th></tr>
<tr><td>「老闆問這個市場有多大、值不值得進」</td><td><a href="references/01-market-research.md">01 市場調查</a></td><td>TAM／SAM／SOM 推估、敏感度分析、建議與待驗證的假設</td></tr>
<tr><td>「我們跟對手到底差在哪？」</td><td><a href="references/02-competitive-analysis.md">02 競品分析</a></td><td>比較矩陣、差異化機會、要避開的正面對決</td></tr>
<tr><td>「方案要怎麼定價、怎麼賺錢？」</td><td><a href="references/03-business-model.md">03 商業模式</a></td><td>收入結構、單位經濟（LTV／CAC）、最脆弱的假設</td></tr>
<tr><td>「明年產品要往哪走？」</td><td><a href="references/04-product-strategy.md">04 產品策略</a><br>→ <a href="references/05-roadmap-planning.md">05 Roadmap</a></td><td>策略一頁版（含「不做什麼」）、Now／Next／Later 路線圖</td></tr>
<tr><td>「這個功能成功的標準是什麼？」</td><td><a href="references/07-kpi-setting.md">07 KPI 設定</a></td><td>北極星指標、護欄指標、事前寫定的成功門檻</td></tr>
</table>

### 需求一直湧進來

<table width="100%">
<tr><th width="260">你可能會說</th><th width="210">用到的指南</th><th width="366">你會拿到</th></tr>
<tr><td>「業務／大客戶／老闆要插單，要不要做？」</td><td><a href="references/11-requirement-analysis.md">11 需求分析</a><br>→ <a href="references/08-requirement-prioritization.md">08 需求排序</a><br>→ <a href="references/41-business-communication.md">41 Business 溝通</a></td><td>真正的問題、RICE 排序、給需求方的回覆話術</td></tr>
<tr><td>「需求太多，排不完」</td><td><a href="references/08-requirement-prioritization.md">08 需求排序</a></td><td>RICE／ICE／MoSCoW 排序表，加上產能線</td></tr>
<tr><td>「主管說要做一個儀表板，但我不知道他要看什麼」</td><td><a href="references/10-stakeholder-interview.md">10 利害關係人訪談</a></td><td>利害關係人盤點、訪談題綱、對齊紀錄（含分歧與待決事項）</td></tr>
<tr><td>「想知道用戶實際怎麼用」</td><td><a href="references/09-user-research.md">09 用戶研究</a><br>→ <a href="references/12-behavior-analysis.md">12 行為分析</a></td><td>研究計畫、篩選題、事件埋點規劃</td></tr>
</table>

### 要把想法變成規格

<table width="100%">
<tr><th width="260">你可能會說</th><th width="210">用到的指南</th><th width="366">你會拿到</th></tr>
<tr><td>「幫我寫 PRD，下週要跟 RD 對」</td><td><a href="references/21-prd-writing.md">21 PRD</a><br>→ <a href="references/23-acceptance-criteria.md">23 驗收條件</a><br>→ <a href="references/24-system-logic.md">24 系統邏輯</a></td><td>PRD（含非目標、範圍、編號需求）、可測的驗收條件、狀態機</td></tr>
<tr><td>「這個 Epic 太大，要怎麼拆？」</td><td><a href="references/22-user-story.md">22 User Story</a></td><td>切片後的故事，每一則都能獨立交付</td></tr>
<tr><td>「要串第三方 API」</td><td><a href="references/25-api-integration.md">25 API 與系統整合</a><br>→ <a href="references/26-data-structure.md">26 資料結構</a></td><td>資料流、錯誤與重試、冪等、對帳規則</td></tr>
<tr><td>「流程好複雜，畫不清楚」</td><td><a href="references/15-user-flow.md">15 User Flow</a><br>→ <a href="references/16-wireframe.md">16 Wireframe</a></td><td>主流程、分支、異常路徑與線框標註</td></tr>
</table>

### 時程或資源卡住了

<table width="100%">
<tr><th width="260">你可能會說</th><th width="210">用到的指南</th><th width="366">你會拿到</th></tr>
<tr><td>「老闆要的日期和 RD 估的對不上」</td><td><a href="references/48-managing-up.md">48 向上管理</a><br>→ <a href="references/38-conflict-resolution.md">38 衝突協調</a><br>→ <a href="references/27-schedule-management.md">27 時程管理</a></td><td>範圍／時程選項與各自代價、明天一對一的開場白</td></tr>
<tr><td>「兩個 BU 搶同一批 RD」</td><td><a href="references/38-conflict-resolution.md">38 衝突協調</a><br>→ <a href="references/28-resource-allocation.md">28 資源調度</a></td><td>決策框架、取捨方案、恢復條件</td></tr>
<tr><td>「感覺專案會出事，但說不出哪裡」</td><td><a href="references/30-risk-management.md">30 風險管理</a><br>→ <a href="references/29-progress-tracking.md">29 進度追蹤</a></td><td>風險登記表（機率×衝擊、早期指標）、週報格式</td></tr>
</table>

### 準備上線

<table width="100%">
<tr><th width="260">你可能會說</th><th width="210">用到的指南</th><th width="366">你會拿到</th></tr>
<tr><td>「下個月要上線，該準備什麼？」</td><td><a href="references/31-uat.md">31 UAT</a><br>→ <a href="references/44-qa-testing.md">44 QA 測試</a><br>→ <a href="references/32-gtm-launch.md">32 GTM</a></td><td>UAT 計畫、缺陷分級、上線檢查表與回滾條件</td></tr>
<tr><td>「客服要怎麼回答新功能的問題？」</td><td><a href="references/45-customer-support-communication.md">45 客服溝通</a></td><td>上線客服素材包、話術、客服回饋月報</td></tr>
<tr><td>「行銷說 B 組贏了，要全量」</td><td><a href="references/19-ab-testing.md">19 A/B 測試</a><br>→ <a href="references/20-data-analysis.md">20 數據分析</a></td><td>實際算出的顯著性、SRM 檢查，以及能不能全量的結論</td></tr>
</table>

### 上線後數字不如預期

<table width="100%">
<tr><th width="260">你可能會說</th><th width="210">用到的指南</th><th width="366">你會拿到</th></tr>
<tr><td>「新功能沒人用」</td><td><a href="references/34-performance-tracking.md">34 成效追蹤</a><br>→ <a href="references/13-funnel-analysis.md">13 漏斗分析</a><br>→ <a href="references/35-product-iteration.md">35 產品迭代</a></td><td>成效判讀、最大漏損點、下一輪要做什麼</td></tr>
<tr><td>「營收／訂閱數掉了，老闆問為什麼」</td><td><a href="references/20-data-analysis.md">20 數據分析</a></td><td>拆解路徑、要排除的干擾因素、結論的信心程度</td></tr>
<tr><td>「用戶一直卡在同一步」</td><td><a href="references/33-ux-optimization.md">33 UX 優化</a><br>→ <a href="references/18-usability-testing.md">18 易用性測試</a></td><td>摩擦點清單、本輪優化計畫、易用性測試設計</td></tr>
</table>

### 卡在人，不是卡在事

<table width="100%">
<tr><th width="260">你可能會說</th><th width="210">用到的指南</th><th width="366">你會拿到</th></tr>
<tr><td>「需要財務配合，但我沒有指揮權」</td><td><a href="references/36-cross-department-communication.md">36 跨部門溝通</a></td><td>跨部門請託範本、追蹤紀錄、話術</td></tr>
<tr><td>「RD 覺得我需求講不清楚」</td><td><a href="references/42-rd-communication.md">42 RD 溝通</a></td><td>需求講解結構、估時與取捨的談法</td></tr>
<tr><td>「要說服老闆投資源」</td><td><a href="references/47-proposal-persuasion.md">47 提案說服</a><br>→ <a href="references/40-presentation-making.md">40 簡報製作</a></td><td>提案結構、預想的反對意見與回應</td></tr>
<tr><td>「要跟海外團隊合作」</td><td><a href="references/46-cross-border-communication.md">46 跨國溝通</a></td><td>跨時區請求訊息、雙方協作約定、話術</td></tr>
</table>

### 你自己快撐不住了

<table width="100%">
<tr><th width="260">你可能會說</th><th width="210">用到的指南</th><th width="366">你會拿到</th></tr>
<tr><td>「提案被否決，同一週又被業務追著跑」</td><td><a href="references/50-emotion-management.md">50 情緒管理</a></td><td>情緒當下紀錄、跟主管一對一的準備卡、話術</td></tr>
<tr><td>「哪些工作可以交給 AI？」</td><td><a href="references/49-ai-tools.md">49 AI 工具</a></td><td>適合與不適合交給 AI 的工作、提示詞範本、資料安全界線</td></tr>
</table>

<details>
<summary><b>50 項能力完整清單（點開）</b></summary>

<br>

**A. 市場與策略**<br>
[01 市場調查](references/01-market-research.md)・[02 競品分析](references/02-competitive-analysis.md)・[03 商業模式](references/03-business-model.md)・[04 產品策略](references/04-product-strategy.md)・[05 Roadmap](references/05-roadmap-planning.md)・[06 成本評估](references/06-cost-estimation.md)・[07 KPI 設定](references/07-kpi-setting.md)

**B. 需求與研究**<br>
[08 需求排序](references/08-requirement-prioritization.md)・[09 用戶研究](references/09-user-research.md)・[10 利害關係人訪談](references/10-stakeholder-interview.md)・[11 需求分析](references/11-requirement-analysis.md)・[12 行為分析](references/12-behavior-analysis.md)・[13 漏斗分析](references/13-funnel-analysis.md)

**C. 設計與驗證**<br>
[14 資訊架構](references/14-information-architecture.md)・[15 User Flow](references/15-user-flow.md)・[16 Wireframe](references/16-wireframe.md)・[17 Prototype](references/17-prototype.md)・[18 易用性測試](references/18-usability-testing.md)・[19 A/B 測試](references/19-ab-testing.md)・[20 數據分析](references/20-data-analysis.md)

**D. 規格文件**<br>
[21 PRD](references/21-prd-writing.md)・[22 User Story](references/22-user-story.md)・[23 驗收條件](references/23-acceptance-criteria.md)・[24 系統邏輯](references/24-system-logic.md)・[25 API 與系統整合](references/25-api-integration.md)・[26 資料結構](references/26-data-structure.md)

**E. 專案管理**<br>
[27 時程管理](references/27-schedule-management.md)・[28 資源調度](references/28-resource-allocation.md)・[29 進度追蹤](references/29-progress-tracking.md)・[30 風險管理](references/30-risk-management.md)・[31 UAT](references/31-uat.md)

**F. 上線與迭代**<br>
[32 GTM 上線](references/32-gtm-launch.md)・[33 UX 優化](references/33-ux-optimization.md)・[34 成效追蹤](references/34-performance-tracking.md)・[35 產品迭代](references/35-product-iteration.md)

**G. 溝通與協作**<br>
[36 跨部門溝通](references/36-cross-department-communication.md)・[37 利害關係人管理](references/37-stakeholder-management.md)・[38 衝突協調](references/38-conflict-resolution.md)・[39 會議主持](references/39-meeting-facilitation.md)・[40 簡報製作](references/40-presentation-making.md)・[41 Business 溝通](references/41-business-communication.md)・[42 RD 溝通](references/42-rd-communication.md)・[43 UIUX 協作](references/43-uiux-collaboration.md)・[44 QA 測試](references/44-qa-testing.md)・[45 客服溝通](references/45-customer-support-communication.md)・[46 跨國溝通](references/46-cross-border-communication.md)・[47 提案說服](references/47-proposal-persuasion.md)・[48 向上管理](references/48-managing-up.md)

**H. 工具與心態**<br>
[49 AI 工具](references/49-ai-tools.md)・[50 情緒管理](references/50-emotion-management.md)

每份指南都是同一套結構：**何時用 → 動手前先問 → 做法 → 產出模板 → 品質檢查 → 常見錯誤 → 情境範例 → 相關指南**。不裝 skill，也可以直接當手冊讀。

</details>

## 安裝

只要一行：

```bash
git clone https://github.com/chengwesley/pm-field-guide.git ~/.claude/skills/pm-field-guide
```

裝好就能用，不需要下任何指令。在 Claude Code 裡用平常講話的方式描述你的狀況，它會自己判斷要用哪幾份指南。

> 只想在某個專案裡用？改放到該專案的 `.claude/skills/pm-field-guide`。

## 內附工具：會算的，就不靠感覺

<table width="100%">
<tr><th width="120">工具</th><th width="350">解決什麼</th><th width="366">範例</th></tr>
<tr><td><code>rice.py</code></td><td>需求排序：算 RICE 分數、畫產能線、做敏感度分析（估值差兩倍，結論會不會變？）</td><td><code>python3 scripts/rice.py examples/rice.csv --capacity 4.5</code></td></tr>
<tr><td><code>funnel.py</code></td><td>漏斗：各步轉換率、最大漏損點、跟前期比較是否顯著</td><td><code>python3 scripts/funnel.py examples/funnel.csv</code></td></tr>
<tr><td><code>ab_test.py</code></td><td>A/B 測試：需要多少樣本、跑幾天；結果的顯著性、信賴區間、樣本比例失衡</td><td><code>python3 scripts/ab_test.py size --baseline 12% --mde 10% --daily-traffic 3000</code></td></tr>
<tr><td><code>dates.py</code></td><td>日期：核對文件裡的星期、加減工作天、排時程</td><td><code>python3 scripts/dates.py check 草稿.md</code></td></tr>
</table>

另外附三份可以直接填的 Excel：**RICE 排序表**、**風險登記表**、**UAT 測試案例表**。

**clone 完就能試。** `examples/` 有三份範例資料，數字和指南裡的情境範例一致：

```bash
python3 scripts/rice.py examples/rice.csv --capacity 4.5
python3 scripts/funnel.py examples/funnel.csv
python3 scripts/ab_test.py analyze examples/ab_test.csv
```

第三個指令會得到下面的結果。B 組看起來贏了，但腳本會先提醒你分流有問題：

```text
卡方 = 28.508，自由度 = 1，p < 0.0001　⚠ 樣本比例失衡，先查分流再看結果

| 組別           | 訪客   | 轉換 | 轉換率 | 相對提升 | p 值   |
| A 原版（對照） | 24,180 | 512  | 2.12%  | —        | —      |
| B 新版         | 23,020 | 551  | 2.39%  | +13.0%   | 0.0433 |
```

<details>
<summary>工具細節</summary>

- 腳本只用 Python 標準函式庫，每支都有 `--help`。CSV 欄名中英文都可以，加 `--json` 會輸出機器可讀的格式。
- `dates.py` 沒有內建國定假日，因為假日不能用猜的。要跳過假日時，用 `--holidays` 和 `--makeup-workdays` 指定你自己的假日檔與補班日檔。
- 腳本附 58 個自動化測試，執行：`python3 -m pytest scripts/tests`
- 要調整 Excel 表單，改 `scripts/build_templates.py` 後重新產生。這支需要 `openpyxl`。

</details>

## 改成你們團隊的版本

範例橫跨外送平台、電商、記帳 SaaS、線上課程、預約系統、健身 App 等產業，數字一律是示意或假設值。

要更貼近你們團隊，改這兩個地方就好：

1. **`SKILL.md` 最後的「情境與合規提醒」**：換成你們的產品、適用法規與對外審核流程。
2. **各指南的「情境範例」**：換成你們自己的產品情境，Claude 舉例時就會更貼近你們的狀況。

## 品質驗證

`evals/evals.json` 有 4 個貼近實務的 PM 情境，每個都附具體的評分項目，例如：

- 有沒有寫非目標
- 驗收條件能不能測
- 有沒有捏造數字
- A/B 測試的 p 值算得對不對
- 日期的星期對不對

改了 skill 之後拿這些情境重跑一次，就知道有沒有退步。

## 授權

[MIT](LICENSE)。歡迎 fork，改成你們團隊的版本；覺得有用也歡迎給顆星。

<div align="center">
<sub>由 Wesley Cheng 製作</sub>
</div>
