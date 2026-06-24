# Validation Report — 用户分销系统

- **PRD:** `_bmad-output/planning-artifacts/prds/prd-user-salse-2026-06-11/prd.md`
- **Rubric:** `.claude/skills/bmad-prd/assets/prd-validation-checklist.md`
- **Run at:** 2026-06-24T13:36:17Z
- **Grade:** **Fair**

## Overall verdict
The PRD delivers strong, testable execution specs for a well-understood distribution system. The code audit confirms **11 of 12** previous-round fixes are correctly implemented, but reveals one **critical** production-blocking issue: the alembic migration chain is out of sync with the ORM models. Three high-severity code gaps also remain (notification emails unsent, missing referral_relationships table, scheduler config key mismatch).

## Dimension verdicts
| Dimension | Verdict |
|-----------|---------|
| Decision-readiness | **thin** |
| Substance over theater | **strong** |
| Strategic coherence | **adequate** |
| Done-ness clarity | **strong** |
| Scope honesty | **thin** |
| Downstream usability | **adequate** |
| Shape fit | **adequate** |

## Findings by severity

### Critical (1)
**Code Audit** — Alembic migrations out of sync with ORM (`backend/alembic/versions/003*.py`)
Migration 003 creates `recharges`/`invite_codes` tables; current ORM expects `payments`/`referral_codes`/`quota_replenishments`. Fresh `alembic upgrade head` fails on first query. 6 table/column/enum mismatches identified.
*Fix:* Create new migration (008) that drops old tables and creates current schema. OR refactor migrations 003-007.

### High (7)
**Decision-readiness** — No unresolved Open Questions (§ 8)
All 10 struck through; zero remaining for a payment-integrated system.
*Fix:* Add 2-3 genuinely open questions.

**Decision-readiness** — No [NOTE FOR PM] callouts (§ 4)
No inline markers at deferred tensions.
*Fix:* Add at payment and cross-system coupling points.

**Strategic coherence** — SM targets lack grounding (§ 7)
No benchmark/rationale for conversion, accuracy, or referral thresholds.
*Fix:* Add source per metric.

**Strategic coherence** — No counter-metrics (§ 7)
*Fix:* Add counter-metrics for SM-1 and SM-5.

**Scope honesty** — No inline [ASSUMPTION] tags (§ 4, § 9)
*Fix:* Place `[ASSUMPTION: ...]` tags inline in FR text.

**Code Audit** — Notification emails never sent (FR-24 violation)
`_send_notification_email()` defined but never invoked.
*Fix:* Call from `send()` or each `notify_*` method.

**Code Audit** — Missing referral_relationships table (FR-8 violation, S9)
*Fix:* Create table + migration + write on relationship establishment.

**Code Audit** — Scheduler config key mismatch (S6 regression)
*Fix:* Add `settlement_cycle_days` to `DEFAULT_CONFIGS` or route through existing `_get_cron_trigger()`.

### Medium (6)
**Done-ness** — FR-24 delivery not tested (§ 4.9)
**Downstream usability** — UJ-3 floating protagonist (§ 2.4)
**Code Audit** — PayPage redirect whitelist hardcoded
**Code Audit** — Unused "refunded" payment status enum
**NFR Audit** — NFR-2: Audit log lacks immutability protection
**NFR Audit** — NFR-5: Callback uses custom HMAC (not WeChat/Alipay)

### Low (2)
**Scope honesty** — Duplicate non-goal entries (§ 5)
**Downstream usability** — Glossary drift + circular definition (§ 3)

## Mechanical notes
- Glossary drift: "额度" vs "可售额度" used interchangeably (FR-7, FR-11)
- ID continuity: FR-1 through FR-25 contiguous; no gaps or duplicates
- Assumptions Index roundtrip broken — no inline [ASSUMPTION] tags in body
- UJ-3 uses generic "用户" — no named protagonist
- Required sections all present

## Reviewer files
- `review-rubric.md`
- `review-code-audit.md`
- `review-nfr.md`
