# PRD: Bulk Follow-up Reminders

Version: 0.2 (draft)

## Background
Front-desk staff call each patient one by one the day before a follow-up visit, about 90 calls a day (illustrative).

## Goals
- G1: Staff can send follow-up reminders to many patients in one action.

## Non-goals
- NG1: No marketing broadcasts in this release.

## Scope
| In | Out | Later |
|---|---|---|
| Bulk SMS reminders | Voice calls | Chat app push |

## Requirements

### US-01 Send reminders in bulk
As front-desk staff, I want to select several patients and send reminders at once.

- Given 3 patients are selected
- When I press Send
- Then each of the 3 patients receives 1 SMS

### US-02 See delivery results
- Given a batch has been sent, when I open the result page, then every row shows Sent or Failed.

## Edge cases
| Case | System behavior |
|---|---|
| SMS provider timeout | Nothing is charged; the list stays selected |
| No permission | The bulk send button is hidden |
| User cancels | No message is sent |

## Success metrics
| Type | Metric | Baseline | Target | Measurement | Period |
|---|---|---|---|---|---|
| Primary metric | No-show rate | 12% | 8% | event appointment_no_show | 8 weeks after launch |
| Guardrail | SMS opt-out rate | 1% | at most 2% | event sms_opt_out | 8 weeks after launch |

## Open questions
| # | Question | Owner | Due | Decision |
|---|---|---|---|---|
| Q1 | Which budget pays for SMS | Ops lead | 2030-03-15 | pending |

## Changelog
- 2030-03-01 v0.2 added guardrail metric
