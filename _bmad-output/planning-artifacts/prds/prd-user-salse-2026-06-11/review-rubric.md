# PRD Quality Review — 用户分销系统

## Overall verdict

The PRD delivers strong, testable execution specs for a well-understood distribution system: every FR has concrete consequences, the glossary is comprehensive, and the Vision is earned and specific. What holds up is downstream build readiness. What is at risk is decision transparency — the PRD surfaces no unresolved tensions, carries no inline assumption tags, and lacks callouts where trade-offs were made. Downstream teams will discover hidden assumptions during build, and decision-makers have no basis to evaluate trade-offs the PRD has already smoothed over. **Adequate** — buildable, but needs honest surfacing of uncertainty.

## Decision-readiness — thin

Decisions are stated clearly (v2 change summary, struck-through Open Questions), but the PRD never surfaces an actual *tension*. Every Open Question is resolved; no `[NOTE FOR PM]` callouts exist anywhere in the document. For a system handling real-money payment flows, cross-system integration, and a commission structure, the absence of unresolved items is itself a signal that tensions were smoothed rather than surfaced.

The decision log (`.decision-log.md`) records extensive iteration with rationale, but that context is largely invisible to someone reading the PRD alone. An engineer building from the PRD has no way to know that compliance analysis was deferred (§ "Noted but not applied" in decision-log), or that payment integration shifted from pure offline to online mid-stream — only the final state is visible.

### Findings
- **high** No unresolved Open Questions (§ 8) — All 10 items are struck through as resolved; zero remaining. A distribution system with payment integration, cross-system License verification, and configurable commission rates will have genuine uncertainties at PRD sign-off. *Fix:* Add 2-3 genuinely open questions (e.g., "What happens if a payment callback arrives after the session expires?" or "How are retroactive commission adjustments handled when rates change mid-cycle?").
- **high** No `[NOTE FOR PM]` callouts (§ 4 entire) — No inline markers at deferred decisions or unresolved tensions. For comparison, the decision log records "Noted but not applied" items (compliance analysis, product value proposition) that were consciously deferred but are invisible in the PRD. *Fix:* Add `[NOTE FOR PM]` at the payment integration boundary: e.g., "What guarantees does the payment provider offer for callback delivery?" and at the cross-system coupling: "How does the business system handle a License that was generated but never activated (orphan)?".
- **medium** No trade-off language with given-up alternatives (§ 1, § 4) — Decisions are stated as outcomes without what was sacrificed. E.g., "推荐码持久有效，可重复使用" (FR-3) was chosen over the one-time-use invitation model. The PRD doesn't say what was given up (e.g., usage-tracking precision, expiry-based rotation). *Fix:* For 2-3 architecturally significant decisions, add a line: "Chose X over Y because [reason]; Y would have [benefit given up]."

## Substance over theater — strong

No persona theater, innovation theater, or NFR theater detected. Each role (超管, 代理, 经销商, 终端用户) drives specific FRs. The four-persona list is at the boundary of the rubric's red-flag threshold but each is earned. NFRs are specific and testable, not boilerplate. The Vision statement is specific to this PRD's three core problems and their proposed solutions — it could not be swapped into another PRD without change.

The "分销引擎" positioning (§ 1, line 28) is a clear thesis that differentiates this system from the business system and guides architectural decisions throughout.

No findings — dimension earns its verdict.

## Strategic coherence — adequate

The thesis is clear ("分销逻辑稳定不变，业务系统可独立迭代", § 1) and the feature set follows from it. Feature grouping (user auth, roles & payments, referral chain, License, commissions, admin) maps logically to the three problems stated in Vision.

Success Metrics are specific but ungrounded: SM-1 targets >70% conversion — what baseline or benchmark justifies this? SM-2 demands zero-error commission calculation — aspirational, but no tolerance or sampling methodology defined. SM-5 targets >60% referral-code usage — no rationale. Counter-metrics are absent entirely: if conversion optimization requires friction reduction on the payment page, what fraud or abandonment risks does that introduce?

MVP scope (§ 6) is cleanly bounded with explicit In/Out lists. The scope kind (platform capability enabling a business process) matches the product type.

### Findings
- **high** SM targets lack grounding (§ 7, SM-1, SM-2, SM-5) — >70% conversion rate, zero-error commission calculation, >60% referral-code usage are stated as thresholds with no benchmark, industry reference, or rationale. *Fix:* For each SM, add 1-2 sentences on how the target was derived (e.g., "70% is based on industry average for H5 payment flows in CN market, per [source]" or zero-error defined as "no discrepancy found in quarterly audit sampling").
- **high** No counter-metrics (§ 7) — None of the 5 SMs acknowledge what optimizing for this metric might cost. *Fix:* Add counter-metrics: e.g., for SM-1 (conversion >70%), track "payment page abandonment by step" and "support tickets related to payment confusion"; for SM-5 (>60% referral usage), track "invalid referral code submissions" and "user confusion rate on referral field."

## Done-ness clarity — strong

Every FR (1-25) carries at least one testable consequence. Most carry 3-7. The Consequences format (explicit "testable:" labels) is consistent and verifiable. Ambiguous adjectives like "reasonable," "graceful," or "user-friendly" are absent. NFRs all have testable bounds rather than vague aspirations.

The only weak point: FR-24 (消息通知) has a single consequence that specifies content format ("通知内容包含事件类型、金额、时间") but does not test delivery — whether the notification was sent, reached the user, or was rendered correctly. All five trigger scenarios (§ 4.9 description) are never individually tested in the consequences.

### Findings
- **medium** FR-24 delivery not tested (§ 4.9, FR-24) — The sole consequence verifies content structure, not that the notification was actually sent or delivered. For a commission/distribution system where notification timing affects user trust, this matters. *Fix:* Add consequences: "Each of the 5 trigger scenarios produces a notification record (DB) within 30s"; "Email delivery success rate >99% (non-delivery logged)".

## Scope honesty — thin

The Non-Goals section (§ 5) is present with 7 items and is explicit. MVP In/Out scope (§ 6) is clean. These are the strengths.

The weakness is the Assumptions Index roundtrip. Section 9 lists 10 assumptions with section references, but there are zero inline `[ASSUMPTION]` tags in the PRD body. A downstream consumer cannot distinguish — within any FR paragraph — which statements are confirmed facts and which are inferences from the author. The index entries paraphrase FR descriptions; they do not tag specific claims. This means the Assumptions Index cannot be validated programmatically or by inspection.

Open-items density is paradoxically *too low* for a PRD at this integration complexity: 0 Open Questions (all resolved), 0 `[NOTE FOR PM]`, 0 `[ASSUMPTION]` tags. A count of 0 suggests undetected assumptions rather than full certainty.

One explicit contradiction in scope: Section 5 Non-Goals lists "不做支付退款" (item 2) and "不做退款" (item 6) as separate entries — identical intent.

### Findings
- **high** No inline `[ASSUMPTION]` tags (§ 4, § 9) — The Assumptions Index (Section 9) exists but no body text contains `[ASSUMPTION]` markers. A reader cannot verify which statements are confirmed vs. inferred. *Fix:* Replace the current index with actual `[ASSUMPTION: …]` tags inline in the FR text (e.g., "[ASSUMPTION: 邮箱验证码 5 分钟有效期足够覆盖登录流程]" in FR-1), and cross-reference back to the index. Delete index entries that are restatements of explicit requirements.
- **low** Duplicate non-goal entries (§ 5) — Item 2 "不做支付退款" and item 6 "不做退款" describe the same constraint. *Fix:* Remove item 6.

## Downstream usability — adequate

Glossary (§ 3) is comprehensive (17 terms) and domain nouns are used consistently across FRs. ID series are contiguous: FR-1 through FR-25, UJ-1 through UJ-5, SM-1 through SM-5. Cross-references resolve.

Two issues:

UJ-3 lacks a named protagonist (§ 2.4, UJ-3). The persona is "用户在业务系统看到升级按钮" — this is a floating UJ. Every other UJ names a specific protagonist (超管小王, 李代理, 赵代理, 管理员小王). For a B2B system, unnamed protagonists create ambiguity about whose experience is being designed.

Minor glossary drift: "额度" and "可售额度" are used interchangeably. The glossary defines "可售额度" (22/11), but FR-7 uses "剩余可售额度" and "额度" in adjacent consequences; FR-11 uses "1 个可售额度" then "额度减 1". Consistent.

Glossary defines "角色" with a circular dependency: "角色由支付金额决定（5000→经销商，10000→代理）" — this is a rule, not a definition. The term "角色" is a basic concept that should be defined independently of how it's assigned.

### Findings
- **medium** UJ-3 floating protagonist (§ 2.4, UJ-3) — No named persona; uses generic "用户." The context ("用户在业务系统看到升级按钮") does not identify who the user is at this point. *Fix:* Name the protagonist (e.g., "王五, a terminal user of the business system who wants advanced features").
- **low** Glossary drift: "额度" vs "可售额度" (§ 3, § 4.2 FR-7, § 4.4 FR-11) — Glossary defines "可售额度"; FR text alternates between "可售额度" and bare "额度" within the same FR. *Fix:* Use "可售额度" consistently in all FR consequences.
- **low** Glossary circular definition (§ 3, "角色") — "角色由支付金额决定" describes assignment, not meaning. *Fix:* Define role as "分销系统用户身份（代理/经销商），决定佣金比例与可售额度." Move the assignment rule to FR-5.

## Shape fit — adequate

Product type: B2B multi-stakeholder distribution tool with payment integration. The UJ structure with named protagonists is appropriate and load-bearing. Five UJs across four roles is proportionate. The PRD's chain-top position (feeds UX → architecture → stories) is acknowledged in § 0 Document Purpose.

The PRD is slightly over-formalized given the product type — UJs exist but don't drive every decision in the PRD (e.g., UJ-2/UJ-3 cover the same License split context from different stakeholder perspectives). This is harmless at current volume.

No findings beyond the UJ-3 protagonist issue already captured under Downstream usability.

## Mechanical notes

- **Glossary drift**: "额度" vs "可售额度" used interchangeably (FR-7, FR-11). Glossary defines "可售额度." Minor.
- **ID continuity**: FR-1 through FR-25 contiguous. UJ-1 through UJ-5 contiguous. SM-1 through SM-5 contiguous. No gaps or duplicates.
- **Assumptions Index roundtrip**: Broken. Section 9 exists but has no inline `[ASSUMPTION]` tags in § 4 body to roundtrip against. Each index entry paraphrases a requirement rather than tagging an assumption.
- **UJ protagonist naming**: UJ-3 uses generic "用户" — no named protagonist. Others (UJ-1: 超管小王, UJ-2: 李代理, UJ-4: 赵代理, UJ-5: 管理员小王) are properly named.
- **Required sections**: All present — Vision (§ 1), Target User (§ 2), Glossary (§ 3), Features (§ 4), Non-Goals (§ 5), MVP Scope (§ 6), Success Metrics (§ 7), Open Questions (§ 8), Assumptions Index (§ 9).
