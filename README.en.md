<div align="center">

# PM Field Guide

**A product management handbook that flips to the right page by itself**

50 core software PM competencies, packaged as one [Claude Code](https://claude.com/claude-code) skill.<br>
Describe your situation. It picks the right methods, asks what's missing, and hands you something you can take straight into the meeting.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Guides](https://img.shields.io/badge/guides-50-green)
![Tools](https://img.shields.io/badge/tools-4_scripts_%2B_3_templates-yellow)
![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-skill-orange)

**50 guides · 4 calculation scripts · 3 Excel templates**

[繁體中文](README.md) ｜ **English**

[Why](#why-it-exists) · [Example](#see-it-in-action) · [Situations](#where-are-you-right-now) · [Install](#install) · [Tools](#bundled-tools-if-it-can-be-calculated-dont-guess) · [Customize](#make-it-your-teams-own)

</div>

> **Language note:** the 50 guides are written in Traditional Chinese. If you ask in English, Claude usually answers in English. The skill's own rules default to Traditional Chinese; you can change that in `SKILL.md`.

---

## Why it exists

You've probably been here:

- Sales comes back for the third time: "The client needs this feature or we lose the deal." Engineering is booked solid until next quarter.
- Your boss announces a launch "in one month." Engineering estimates three. You're stuck in the middle.
- The A/B test is in. Marketing says variant B clearly won and wants a full rollout today.
- Nobody reads the PRD. Halfway through the build, you find out everyone understood it differently.

Ask a general AI and you get a well-formatted, generic answer that doesn't quite fit your case. PM Field Guide works differently:

<table width="100%">
<tr><th width="418">A typical AI answer</th><th width="418">With PM Field Guide</th></tr>
<tr><td>Starts writing right away</td><td><b>Asks first</b> about what's missing: who wants it, what for, where's the evidence</td></tr>
<tr><td>Fills in plausible-looking numbers</td><td><b>Never invents numbers</b>: unknowns stay as <code>____</code> or are marked as assumptions</td></tr>
<tr><td>Lists frameworks for you to choose from</td><td><b>Gives a decision</b>: what to do, what not to do, and why</td></tr>
<tr><td>"Next step: keep monitoring"</td><td>Next steps come with <b>an owner and a date</b>, and the script checks each date's weekday</td></tr>
<tr><td>"Variant B looks better"</td><td><b>Runs the numbers</b> with bundled scripts: significance, sample ratio mismatch, sample size</td></tr>
</table>

## See it in action

> **You:** Sales has asked three times now. A client wants to export transaction records from our accounting SaaS to Excel, or they'll churn. Engineering is full until Q1. How should I evaluate this?

Claude reads three guides in order: Requirement Analysis, Prioritization, and Business Communication. Then it:

1. **Unpacks the solution-shaped request.** Does the client need Excel, or do they need to reconcile with their accountant? Would CSV or an existing report do?
2. **Asks for evidence.** Which clients, what contract value, and when do they renew? "We'll lose the deal" has to be verifiable.
3. **Scores and ranks it.** It runs RICE against the other candidates, sizing impact in B2B units (number of accounts, contract value).
4. **Drafts your reply to sales.** It neither says yes nor no on the spot.
5. **Lists next steps.** Every item has an owner and a date.

## Where are you right now?

Find the line that sounds like you. The guides next to it are what Claude will use. You don't need to remember any numbers; just describe the situation in your own words.

### Direction isn't set yet

<table width="100%">
<tr><th width="260">You might say</th><th width="210">Guides used</th><th width="366">You get</th></tr>
<tr><td>"My boss wants to know how big this market is and whether we should enter"</td><td><a href="references/01-market-research.md">01 Market Research</a></td><td>TAM/SAM/SOM estimate, sensitivity analysis, recommendation, and assumptions to validate</td></tr>
<tr><td>"How are we actually different from competitors?"</td><td><a href="references/02-competitive-analysis.md">02 Competitive Analysis</a></td><td>Comparison matrix, differentiation opportunities, head-on fights to avoid</td></tr>
<tr><td>"How should we price this? How do we make money?"</td><td><a href="references/03-business-model.md">03 Business Model</a></td><td>Revenue structure, unit economics (LTV/CAC), the most fragile assumption</td></tr>
<tr><td>"Where should the product go next year?"</td><td><a href="references/04-product-strategy.md">04 Product Strategy</a><br>→ <a href="references/05-roadmap-planning.md">05 Roadmap</a></td><td>One-page strategy (including what *not* to do), Now/Next/Later roadmap</td></tr>
<tr><td>"What does success look like for this feature?"</td><td><a href="references/07-kpi-setting.md">07 KPI Setting</a></td><td>North Star metric, guardrail metrics, success thresholds set in advance</td></tr>
</table>

### Requests keep pouring in

<table width="100%">
<tr><th width="260">You might say</th><th width="210">Guides used</th><th width="366">You get</th></tr>
<tr><td>"Sales / a big client / my boss wants this squeezed in. Should we?"</td><td><a href="references/11-requirement-analysis.md">11 Requirement Analysis</a><br>→ <a href="references/08-requirement-prioritization.md">08 Prioritization</a><br>→ <a href="references/41-business-communication.md">41 Business Communication</a></td><td>The real problem, a RICE ranking, a reply script for the requester</td></tr>
<tr><td>"Too many requests, not enough capacity"</td><td><a href="references/08-requirement-prioritization.md">08 Prioritization</a></td><td>RICE/ICE/MoSCoW ranking with a capacity line</td></tr>
<tr><td>"My manager wants a dashboard, but I don't know what they want to see"</td><td><a href="references/10-stakeholder-interview.md">10 Stakeholder Interviews</a></td><td>Stakeholder map, interview guide, alignment notes (including open disagreements)</td></tr>
<tr><td>"I want to see how users actually behave"</td><td><a href="references/09-user-research.md">09 User Research</a><br>→ <a href="references/12-behavior-analysis.md">12 Behavior Analysis</a></td><td>Research plan, screener questions, event tracking plan</td></tr>
</table>

### Turning ideas into specs

<table width="100%">
<tr><th width="260">You might say</th><th width="210">Guides used</th><th width="366">You get</th></tr>
<tr><td>"Write a PRD. I'm reviewing it with engineering next week"</td><td><a href="references/21-prd-writing.md">21 PRD</a><br>→ <a href="references/23-acceptance-criteria.md">23 Acceptance Criteria</a><br>→ <a href="references/24-system-logic.md">24 System Logic</a></td><td>PRD with non-goals, scope, and numbered requirements; testable acceptance criteria; a state machine</td></tr>
<tr><td>"This epic is too big. How do I split it?"</td><td><a href="references/22-user-story.md">22 User Stories</a></td><td>Sliced stories, each independently shippable</td></tr>
<tr><td>"We need to integrate a third-party API"</td><td><a href="references/25-api-integration.md">25 API &amp; System Integration</a><br>→ <a href="references/26-data-structure.md">26 Data Structure</a></td><td>Data flows, errors and retries, idempotency, reconciliation rules</td></tr>
<tr><td>"The flow is too complex to draw clearly"</td><td><a href="references/15-user-flow.md">15 User Flow</a><br>→ <a href="references/16-wireframe.md">16 Wireframe</a></td><td>Main path, branches, error paths, annotated wireframes</td></tr>
</table>

### Stuck on schedule or resources

<table width="100%">
<tr><th width="260">You might say</th><th width="210">Guides used</th><th width="366">You get</th></tr>
<tr><td>"My boss's date and engineering's estimate don't match"</td><td><a href="references/48-managing-up.md">48 Managing Up</a><br>→ <a href="references/38-conflict-resolution.md">38 Conflict Resolution</a><br>→ <a href="references/27-schedule-management.md">27 Schedule Management</a></td><td>Scope/timeline options with their costs, and an opening line for tomorrow's 1:1</td></tr>
<tr><td>"Two business units are fighting over the same engineers"</td><td><a href="references/38-conflict-resolution.md">38 Conflict Resolution</a><br>→ <a href="references/28-resource-allocation.md">28 Resource Allocation</a></td><td>Decision framework, trade-off options, conditions for revisiting</td></tr>
<tr><td>"Something feels off with this project, but I can't say what"</td><td><a href="references/30-risk-management.md">30 Risk Management</a><br>→ <a href="references/29-progress-tracking.md">29 Progress Tracking</a></td><td>Risk register (probability × impact, early signals), status report format</td></tr>
</table>

### Getting ready to launch

<table width="100%">
<tr><th width="260">You might say</th><th width="210">Guides used</th><th width="366">You get</th></tr>
<tr><td>"We launch next month. What do I need to prepare?"</td><td><a href="references/31-uat.md">31 UAT</a><br>→ <a href="references/44-qa-testing.md">44 QA Testing</a><br>→ <a href="references/32-gtm-launch.md">32 GTM</a></td><td>UAT plan, defect severity levels, launch checklist with rollback criteria</td></tr>
<tr><td>"How should support answer questions about the new feature?"</td><td><a href="references/45-customer-support-communication.md">45 Customer Support</a></td><td>Launch support kit, scripts, monthly support feedback report</td></tr>
<tr><td>"Marketing says B won and wants a full rollout"</td><td><a href="references/19-ab-testing.md">19 A/B Testing</a><br>→ <a href="references/20-data-analysis.md">20 Data Analysis</a></td><td>Significance and SRM computed by a script, and a clear call on whether to roll out</td></tr>
</table>

### Post-launch numbers disappoint

<table width="100%">
<tr><th width="260">You might say</th><th width="210">Guides used</th><th width="366">You get</th></tr>
<tr><td>"Nobody is using the new feature"</td><td><a href="references/34-performance-tracking.md">34 Performance Tracking</a><br>→ <a href="references/13-funnel-analysis.md">13 Funnel Analysis</a><br>→ <a href="references/35-product-iteration.md">35 Product Iteration</a></td><td>Results readout, biggest drop-off point, what to do next round</td></tr>
<tr><td>"Revenue or subscriptions dropped. My boss wants to know why"</td><td><a href="references/20-data-analysis.md">20 Data Analysis</a></td><td>Breakdown path, confounders to rule out, confidence level of the conclusion</td></tr>
<tr><td>"Users keep getting stuck on the same step"</td><td><a href="references/33-ux-optimization.md">33 UX Optimization</a><br>→ <a href="references/18-usability-testing.md">18 Usability Testing</a></td><td>Friction list, optimization plan for this round, usability test design</td></tr>
</table>

### The blocker is people, not tasks

<table width="100%">
<tr><th width="260">You might say</th><th width="210">Guides used</th><th width="366">You get</th></tr>
<tr><td>"I need finance to help, but I have no authority over them"</td><td><a href="references/36-cross-department-communication.md">36 Cross-team Communication</a></td><td>Request template, follow-up log, scripts</td></tr>
<tr><td>"Engineering says my requirements are unclear"</td><td><a href="references/42-rd-communication.md">42 Working with Engineering</a></td><td>Structure for walking through requirements, how to discuss estimates and trade-offs</td></tr>
<tr><td>"I need to convince leadership to invest"</td><td><a href="references/47-proposal-persuasion.md">47 Proposals &amp; Persuasion</a><br>→ <a href="references/40-presentation-making.md">40 Presentations</a></td><td>Proposal structure, anticipated objections and responses</td></tr>
<tr><td>"I'm working with a team overseas"</td><td><a href="references/46-cross-border-communication.md">46 Cross-border Communication</a></td><td>Cross-time-zone request messages, working agreement, scripts</td></tr>
</table>

### You're running on empty

<table width="100%">
<tr><th width="260">You might say</th><th width="210">Guides used</th><th width="366">You get</th></tr>
<tr><td>"My proposal got rejected, and sales has been chasing me all week"</td><td><a href="references/50-emotion-management.md">50 Emotion Management</a></td><td>In-the-moment log, 1:1 prep card for your manager, scripts</td></tr>
<tr><td>"Which parts of my job can I hand to AI?"</td><td><a href="references/49-ai-tools.md">49 AI Tools</a></td><td>What to delegate and what not to, prompt templates, data-safety boundaries</td></tr>
</table>

<details>
<summary><b>All 50 competencies (click to expand)</b></summary>

<br>

**A. Market & Strategy**<br>
[01 Market Research](references/01-market-research.md) · [02 Competitive Analysis](references/02-competitive-analysis.md) · [03 Business Model](references/03-business-model.md) · [04 Product Strategy](references/04-product-strategy.md) · [05 Roadmap](references/05-roadmap-planning.md) · [06 Cost Estimation](references/06-cost-estimation.md) · [07 KPI Setting](references/07-kpi-setting.md)

**B. Requirements & Research**<br>
[08 Prioritization](references/08-requirement-prioritization.md) · [09 User Research](references/09-user-research.md) · [10 Stakeholder Interviews](references/10-stakeholder-interview.md) · [11 Requirement Analysis](references/11-requirement-analysis.md) · [12 Behavior Analysis](references/12-behavior-analysis.md) · [13 Funnel Analysis](references/13-funnel-analysis.md)

**C. Design & Validation**<br>
[14 Information Architecture](references/14-information-architecture.md) · [15 User Flow](references/15-user-flow.md) · [16 Wireframe](references/16-wireframe.md) · [17 Prototype](references/17-prototype.md) · [18 Usability Testing](references/18-usability-testing.md) · [19 A/B Testing](references/19-ab-testing.md) · [20 Data Analysis](references/20-data-analysis.md)

**D. Specs**<br>
[21 PRD](references/21-prd-writing.md) · [22 User Stories](references/22-user-story.md) · [23 Acceptance Criteria](references/23-acceptance-criteria.md) · [24 System Logic](references/24-system-logic.md) · [25 API & Integration](references/25-api-integration.md) · [26 Data Structure](references/26-data-structure.md)

**E. Project Management**<br>
[27 Schedule](references/27-schedule-management.md) · [28 Resource Allocation](references/28-resource-allocation.md) · [29 Progress Tracking](references/29-progress-tracking.md) · [30 Risk Management](references/30-risk-management.md) · [31 UAT](references/31-uat.md)

**F. Launch & Iteration**<br>
[32 GTM Launch](references/32-gtm-launch.md) · [33 UX Optimization](references/33-ux-optimization.md) · [34 Performance Tracking](references/34-performance-tracking.md) · [35 Product Iteration](references/35-product-iteration.md)

**G. Communication & Collaboration**<br>
[36 Cross-team](references/36-cross-department-communication.md) · [37 Stakeholder Management](references/37-stakeholder-management.md) · [38 Conflict Resolution](references/38-conflict-resolution.md) · [39 Meeting Facilitation](references/39-meeting-facilitation.md) · [40 Presentations](references/40-presentation-making.md) · [41 Business Communication](references/41-business-communication.md) · [42 Engineering](references/42-rd-communication.md) · [43 UI/UX Collaboration](references/43-uiux-collaboration.md) · [44 QA Testing](references/44-qa-testing.md) · [45 Customer Support](references/45-customer-support-communication.md) · [46 Cross-border](references/46-cross-border-communication.md) · [47 Proposals & Persuasion](references/47-proposal-persuasion.md) · [48 Managing Up](references/48-managing-up.md)

**H. Tools & Mindset**<br>
[49 AI Tools](references/49-ai-tools.md) · [50 Emotion Management](references/50-emotion-management.md)

Every guide follows the same structure: **When to use → Ask before you start → How to do it → Output template → Quality checks → Common mistakes → Worked example → Related guides**. You can also read them as a plain handbook without installing the skill.

</details>

## Install

One line:

```bash
git clone https://github.com/chengwesley/pm-field-guide.git ~/.claude/skills/pm-field-guide
```

That's it. There are no commands to learn. Describe your situation in Claude Code the way you'd tell a colleague, and it decides which guides to use.

> Only want it in one project? Clone it into that project's `.claude/skills/pm-field-guide` instead.

## Bundled tools: if it can be calculated, don't guess

<table width="100%">
<tr><th width="120">Tool</th><th width="350">What it solves</th><th width="366">Example</th></tr>
<tr><td><code>rice.py</code></td><td>Prioritization: RICE scores, capacity line, sensitivity analysis (does the ranking change if an estimate is off by 2×?)</td><td><code>python3 scripts/rice.py examples/rice.csv --capacity 4.5</code></td></tr>
<tr><td><code>funnel.py</code></td><td>Funnels: step conversion, biggest drop-off, significance vs. the previous period</td><td><code>python3 scripts/funnel.py examples/funnel.csv</code></td></tr>
<tr><td><code>ab_test.py</code></td><td>A/B tests: required sample size and duration; significance, confidence intervals, and sample ratio mismatch</td><td><code>python3 scripts/ab_test.py size --baseline 12% --mde 10% --daily-traffic 3000</code></td></tr>
<tr><td><code>dates.py</code></td><td>Dates: checks weekdays in a document, adds or subtracts business days, builds schedules</td><td><code>python3 scripts/dates.py check draft.md</code></td></tr>
</table>

It also ships three fill-in Excel templates: a **RICE scoring sheet**, a **risk register**, and a **UAT test case sheet**.

**Try it right after cloning.** `examples/` has three sample inputs whose numbers match the worked examples in the guides:

```bash
python3 scripts/rice.py examples/rice.csv --capacity 4.5
python3 scripts/funnel.py examples/funnel.csv
python3 scripts/ab_test.py analyze examples/ab_test.csv
```

The third command prints the result below (script output is in Traditional Chinese). Variant B looks like a winner, but the script first warns that the traffic split is off:

```text
卡方 = 28.508，自由度 = 1，p < 0.0001　⚠ 樣本比例失衡，先查分流再看結果   (sample ratio mismatch: check the split first)

| 組別           | 訪客   | 轉換 | 轉換率 | 相對提升 | p 值   |
| A 原版（對照） | 24,180 | 512  | 2.12%  | —        | —      |
| B 新版         | 23,020 | 551  | 2.39%  | +13.0%   | 0.0433 |
```

<details>
<summary>Tool details</summary>

- The scripts use only the Python standard library, and each one has `--help`. CSV headers can be in English or Chinese. Add `--json` for machine-readable output.
- `dates.py` has no built-in public holidays, because holidays shouldn't be guessed. To skip them, supply your own holiday and make-up workday files with `--holidays` and `--makeup-workdays`.
- The scripts ship with 58 automated tests: `python3 -m pytest scripts/tests`
- To change the Excel templates, edit `scripts/build_templates.py` and regenerate. That script needs `openpyxl`.

</details>

## Make it your team's own

The examples cover food delivery, e-commerce, accounting SaaS, online courses, booking systems, fitness apps, and more. Every number in them is illustrative or explicitly marked as an assumption.

To tailor it to your team, change two things:

1. **The "Context & compliance reminders" section at the end of `SKILL.md`:** swap in your products, applicable regulations, and external review process.
2. **The worked example in each guide:** replace it with your own product context, so Claude's examples match your reality.

## Quality checks

`evals/evals.json` contains 4 realistic PM scenarios, each with concrete grading criteria, for example:

- Are non-goals stated?
- Are acceptance criteria testable?
- Were any numbers made up?
- Is the A/B test p-value correct?
- Are the weekdays right?

After you change the skill, rerun these scenarios to catch regressions.

## License

[MIT](LICENSE). Fork it and turn it into your team's version. If it helps, a star is appreciated.

<div align="center">
<sub>Made by Wesley Cheng</sub>
</div>
