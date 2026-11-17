<div align="center">

# PM Field Guide

**A product management handbook that flips to the right page by itself**

50 core software PM competencies, packaged as one [Claude Code](https://claude.com/claude-code) skill.<br>
Describe your situation. It picks the right methods, asks what's missing, and hands you something you can take straight into the meeting.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Guides](https://img.shields.io/badge/guides-50-green)
![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-skill-orange)

[繁體中文](README.md) ｜ **English**

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

| A typical AI answer | With PM Field Guide |
|---|---|
| Starts writing right away | **Asks first** about what's missing: who wants it, what for, where's the evidence |
| Fills in plausible-looking numbers | **Never invents numbers**: unknowns stay as `____` or are marked as assumptions |
| Lists frameworks for you to choose from | **Gives a decision**: what to do, what not to do, and why |
| "Next step: keep monitoring" | Next steps come with **an owner and a date**, and the script checks each date's weekday |
| "Variant B looks better" | **Runs the numbers** with bundled scripts: significance, sample ratio mismatch, sample size |

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

### 🧭 Direction isn't set yet

| You might say | Guides used | You get |
|---|---|---|
| "My boss wants to know how big this market is and whether we should enter" | [01 Market Research](references/01-market-research.md) | TAM/SAM/SOM estimate, sensitivity analysis, recommendation, and assumptions to validate |
| "How are we actually different from competitors?" | [02 Competitive Analysis](references/02-competitive-analysis.md) | Comparison matrix, differentiation opportunities, head-on fights to avoid |
| "How should we price this? How do we make money?" | [03 Business Model](references/03-business-model.md) | Revenue structure, unit economics (LTV/CAC), the most fragile assumption |
| "Where should the product go next year?" | [04 Product Strategy](references/04-product-strategy.md) → [05 Roadmap](references/05-roadmap-planning.md) | One-page strategy (including what *not* to do), Now/Next/Later roadmap |
| "What does success look like for this feature?" | [07 KPI Setting](references/07-kpi-setting.md) | North Star metric, guardrail metrics, success thresholds set in advance |

### 📥 Requests keep pouring in

| You might say | Guides used | You get |
|---|---|---|
| "Sales / a big client / my boss wants this squeezed in. Should we?" | [11 Requirement Analysis](references/11-requirement-analysis.md) → [08 Prioritization](references/08-requirement-prioritization.md) → [41 Business Communication](references/41-business-communication.md) | The real problem, a RICE ranking, a reply script for the requester |
| "Too many requests, not enough capacity" | [08 Prioritization](references/08-requirement-prioritization.md) | RICE/ICE/MoSCoW ranking with a capacity line |
| "My manager wants a dashboard, but I don't know what they want to see" | [10 Stakeholder Interviews](references/10-stakeholder-interview.md) | Stakeholder map, interview guide, alignment notes (including open disagreements) |
| "I want to see how users actually behave" | [09 User Research](references/09-user-research.md) → [12 Behavior Analysis](references/12-behavior-analysis.md) | Research plan, screener questions, event tracking plan |

### ✍️ Turning ideas into specs

| You might say | Guides used | You get |
|---|---|---|
| "Write a PRD. I'm reviewing it with engineering next week" | [21 PRD](references/21-prd-writing.md) → [23 Acceptance Criteria](references/23-acceptance-criteria.md) → [24 System Logic](references/24-system-logic.md) | PRD with non-goals, scope, and numbered requirements; testable acceptance criteria; a state machine |
| "This epic is too big. How do I split it?" | [22 User Stories](references/22-user-story.md) | Sliced stories, each independently shippable |
| "We need to integrate a third-party API" | [25 API & System Integration](references/25-api-integration.md) → [26 Data Structure](references/26-data-structure.md) | Data flows, errors and retries, idempotency, reconciliation rules |
| "The flow is too complex to draw clearly" | [15 User Flow](references/15-user-flow.md) → [16 Wireframe](references/16-wireframe.md) | Main path, branches, error paths, annotated wireframes |

### ⏱️ Stuck on schedule or resources

| You might say | Guides used | You get |
|---|---|---|
| "My boss's date and engineering's estimate don't match" | [48 Managing Up](references/48-managing-up.md) → [38 Conflict Resolution](references/38-conflict-resolution.md) → [27 Schedule Management](references/27-schedule-management.md) | Scope/timeline options with their costs, and an opening line for tomorrow's 1:1 |
| "Two business units are fighting over the same engineers" | [38 Conflict Resolution](references/38-conflict-resolution.md) → [28 Resource Allocation](references/28-resource-allocation.md) | Decision framework, trade-off options, conditions for revisiting |
| "Something feels off with this project, but I can't say what" | [30 Risk Management](references/30-risk-management.md) → [29 Progress Tracking](references/29-progress-tracking.md) | Risk register (probability × impact, early signals), status report format |

### 🚀 Getting ready to launch

| You might say | Guides used | You get |
|---|---|---|
| "We launch next month. What do I need to prepare?" | [31 UAT](references/31-uat.md) → [44 QA Testing](references/44-qa-testing.md) → [32 GTM](references/32-gtm-launch.md) | UAT plan, defect severity levels, launch checklist with rollback criteria |
| "How should support answer questions about the new feature?" | [45 Customer Support](references/45-customer-support-communication.md) | Launch support kit, scripts, monthly support feedback report |
| "Marketing says B won and wants a full rollout" | [19 A/B Testing](references/19-ab-testing.md) → [20 Data Analysis](references/20-data-analysis.md) | Significance and SRM computed by a script, and a clear call on whether to roll out |

### 📉 Post-launch numbers disappoint

| You might say | Guides used | You get |
|---|---|---|
| "Nobody is using the new feature" | [34 Performance Tracking](references/34-performance-tracking.md) → [13 Funnel Analysis](references/13-funnel-analysis.md) → [35 Product Iteration](references/35-product-iteration.md) | Results readout, biggest drop-off point, what to do next round |
| "Revenue or subscriptions dropped. My boss wants to know why" | [20 Data Analysis](references/20-data-analysis.md) | Breakdown path, confounders to rule out, confidence level of the conclusion |
| "Users keep getting stuck on the same step" | [33 UX Optimization](references/33-ux-optimization.md) → [18 Usability Testing](references/18-usability-testing.md) | Friction list, optimization plan for this round, usability test design |

### 🤝 The blocker is people, not tasks

| You might say | Guides used | You get |
|---|---|---|
| "I need finance to help, but I have no authority over them" | [36 Cross-team Communication](references/36-cross-department-communication.md) | Request template, follow-up log, scripts |
| "Engineering says my requirements are unclear" | [42 Working with Engineering](references/42-rd-communication.md) | Structure for walking through requirements, how to discuss estimates and trade-offs |
| "I need to convince leadership to invest" | [47 Proposals & Persuasion](references/47-proposal-persuasion.md) → [40 Presentations](references/40-presentation-making.md) | Proposal structure, anticipated objections and responses |
| "I'm working with a team overseas" | [46 Cross-border Communication](references/46-cross-border-communication.md) | Cross-time-zone request messages, working agreement, scripts |

### 😮‍💨 You're running on empty

| You might say | Guides used | You get |
|---|---|---|
| "My proposal got rejected, and sales has been chasing me all week" | [50 Emotion Management](references/50-emotion-management.md) | In-the-moment log, 1:1 prep card for your manager, scripts |
| "Which parts of my job can I hand to AI?" | [49 AI Tools](references/49-ai-tools.md) | What to delegate and what not to, prompt templates, data-safety boundaries |

<details>
<summary><b>📚 All 50 competencies (click to expand)</b></summary>

| Area | Guides |
|---|---|
| **A. Market & Strategy** | [01 Market Research](references/01-market-research.md) · [02 Competitive Analysis](references/02-competitive-analysis.md) · [03 Business Model](references/03-business-model.md) · [04 Product Strategy](references/04-product-strategy.md) · [05 Roadmap](references/05-roadmap-planning.md) · [06 Cost Estimation](references/06-cost-estimation.md) · [07 KPI Setting](references/07-kpi-setting.md) |
| **B. Requirements & Research** | [08 Prioritization](references/08-requirement-prioritization.md) · [09 User Research](references/09-user-research.md) · [10 Stakeholder Interviews](references/10-stakeholder-interview.md) · [11 Requirement Analysis](references/11-requirement-analysis.md) · [12 Behavior Analysis](references/12-behavior-analysis.md) · [13 Funnel Analysis](references/13-funnel-analysis.md) |
| **C. Design & Validation** | [14 Information Architecture](references/14-information-architecture.md) · [15 User Flow](references/15-user-flow.md) · [16 Wireframe](references/16-wireframe.md) · [17 Prototype](references/17-prototype.md) · [18 Usability Testing](references/18-usability-testing.md) · [19 A/B Testing](references/19-ab-testing.md) · [20 Data Analysis](references/20-data-analysis.md) |
| **D. Specs** | [21 PRD](references/21-prd-writing.md) · [22 User Stories](references/22-user-story.md) · [23 Acceptance Criteria](references/23-acceptance-criteria.md) · [24 System Logic](references/24-system-logic.md) · [25 API & Integration](references/25-api-integration.md) · [26 Data Structure](references/26-data-structure.md) |
| **E. Project Management** | [27 Schedule](references/27-schedule-management.md) · [28 Resource Allocation](references/28-resource-allocation.md) · [29 Progress Tracking](references/29-progress-tracking.md) · [30 Risk Management](references/30-risk-management.md) · [31 UAT](references/31-uat.md) |
| **F. Launch & Iteration** | [32 GTM Launch](references/32-gtm-launch.md) · [33 UX Optimization](references/33-ux-optimization.md) · [34 Performance Tracking](references/34-performance-tracking.md) · [35 Product Iteration](references/35-product-iteration.md) |
| **G. Communication & Collaboration** | [36 Cross-team](references/36-cross-department-communication.md) · [37 Stakeholder Management](references/37-stakeholder-management.md) · [38 Conflict Resolution](references/38-conflict-resolution.md) · [39 Meeting Facilitation](references/39-meeting-facilitation.md) · [40 Presentations](references/40-presentation-making.md) · [41 Business Communication](references/41-business-communication.md) · [42 Engineering](references/42-rd-communication.md) · [43 UI/UX Collaboration](references/43-uiux-collaboration.md) · [44 QA Testing](references/44-qa-testing.md) · [45 Customer Support](references/45-customer-support-communication.md) · [46 Cross-border](references/46-cross-border-communication.md) · [47 Proposals & Persuasion](references/47-proposal-persuasion.md) · [48 Managing Up](references/48-managing-up.md) |
| **H. Tools & Mindset** | [49 AI Tools](references/49-ai-tools.md) · [50 Emotion Management](references/50-emotion-management.md) |

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

| Tool | What it solves | Example |
|---|---|---|
| `rice.py` | Prioritization: RICE scores, capacity line, sensitivity analysis (does the ranking change if an estimate is off by 2×?) | `python3 scripts/rice.py backlog.csv --capacity 4` |
| `funnel.py` | Funnels: step conversion, biggest drop-off, significance vs. the previous period | `python3 scripts/funnel.py funnel.csv` |
| `ab_test.py` | A/B tests: required sample size and duration; significance, confidence intervals, and sample ratio mismatch | `python3 scripts/ab_test.py size --baseline 12% --mde 10% --daily-traffic 3000` |
| `dates.py` | Dates: checks weekdays in a document, adds or subtracts business days, builds schedules | `python3 scripts/dates.py check draft.md` |

It also ships three fill-in Excel templates: a **RICE scoring sheet**, a **risk register**, and a **UAT test case sheet**.

<details>
<summary>Tool details</summary>

- The scripts use only the Python standard library, and each one has `--help`. CSV headers can be in English or Chinese. Add `--json` for machine-readable output.
- `dates.py` has no built-in public holidays, because holidays shouldn't be guessed. To skip them, supply your own holiday and make-up workday files with `--holidays` and `--makeup-workdays`.
- Run the tests: `python3 -m pytest scripts/tests`
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

[MIT](LICENSE). Fork it and turn it into your team's version. If it helps, a star is appreciated ⭐

<div align="center">
<sub>Made by Wesley Cheng</sub>
</div>
