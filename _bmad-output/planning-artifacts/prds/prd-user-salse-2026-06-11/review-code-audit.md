# Code Audit Report: PRD v2 Compliance

**Date:** 2026-06-24
**Scope:** Full codebase audit against PRD v2 specifications
**Previous round fixes verified:** C1-C4, S1-S8

---

## 1. Verification of Previous Round Fixes

### C1: Payment Frontend Response Interceptor (api.ts + PayPage.tsx)
**Status:** ✅ Verified
- `payment-app/src/services/api.ts` (line 10-15): Response interceptor correctly unwraps `{ data: <business_data> }` envelope, extracting nested data for consumer components.
- `payment-app/src/pages/PayPage.tsx` (line 75-77): Error handling catches `AxiosError` and displays backend error messages to user via Ant Design `message`.
- No 401 redirect interceptor present, but the previous C1 scope was about data unwrapping -- that is implemented.

### C2: Commission Seed Scene Names (recharge_* -> first_reward_*)
**Status:** ✅ Verified
- `backend/alembic/versions/004_seed_commission_configs_v2.py` (lines 35-44): All scene names use `first_reward_888`, `first_reward_5000`, `first_reward_10000` for both agent and distributor roles.
- `backend/app/services/commission_service.py` (line 159): `scene = f"first_reward_{payment_amount}"` matches the seed data query pattern.
- `grep` across entire codebase confirms zero remaining references to `recharge_reward` scene names.

### C3: Quota Replenish API
**Status:** ✅ Verified
- `backend/app/models/quota_replenishment.py`: Full model with `QuotaReplenishment` table definition (id, user_id, old_quota, requested_amount, status, reject_reason, reviewed_by, timestamps).
- `backend/app/api/v1/quota.py` (lines 53-101): User-facing endpoints: `POST /quota/replenish` (submit), `GET /quota/replenish/status` (query). Proper role check, email match verification.
- `backend/app/api/v1/admin.py` (lines 559-626): Admin endpoints: `GET /admin/quota-replenishments` (list), `POST /admin/quota-replenishments/{id}/review` (approve/reject). Both with status filtering, pagination, and error handling.

### C4: CommissionConfig Admin CRUD
**Status:** ✅ Verified
- `backend/app/api/v1/admin.py` (lines 161-295): Full CRUD implemented:
  - `GET /admin/commission-configs` -- list with optional role/scene filter, pagination (lines 174-216)
  - `GET /admin/commission-configs/{id}` -- single config detail (lines 219-238)
  - `PUT /admin/commission-configs/{id}` -- update with validation, `with_for_update` row lock, auto-logged to `ConfigChangeLog` (lines 241-295)
- Supported actions: reward_value (required), reward_type (optional, retains existing if not provided).

### S1: Auth No-Auto-Create (login)
**Status:** ✅ Verified
- `backend/app/services/auth_service.py`: Both `MockAuthService.send_email_code()` (lines 59-63) and `EmailAuthService.send_email_code()` (lines 148-151) check `scene == "login"` and raise `ValueError("用户不存在")` if the email is not found.
- No `User` creation occurs in any login path.

### S2: send_email_code User Check
**Status:** ✅ Verified
- Same code path as S1. Both auth service implementations verify user existence in the `login` scene before generating a code.

### S3: Team API Return Email
**Status:** ✅ Verified
- `backend/app/schemas/team.py` (lines 12-13, 24-25): Both `TeamNode` and `UpstreamNode` Pydantic models include `email: str` field.
- `backend/app/services/team_service.py` (line 86): `_make_node()` returns email in tree node; `get_upstream_chain()` (line 121) includes email in chain nodes.
- `backend/app/schemas/team.py` (lines 36, 40): `TeamTreeResponse` and `UpstreamChainResponse` both pass email through.

### S4: Generate-License Endpoint
**Status:** ✅ Verified
- `backend/app/api/v1/quota.py` (lines 104-181): `POST /quota/generate-license` fully implemented:
  - Role check (agent/distributor only) (line 122)
  - Quota availability check fast-fail (line 129)
  - Quota consumption with `with_for_update` row lock (line 135)
  - License generation with `source="sale"`, `user_id=None` (not bound to user) (lines 139-147)
  - Audit log recording (lines 150-163)
  - Returns `GenerateLicenseResponse` with code, remaining_quota, message.

### S5: SystemConfig Runtime Integration
**Status:** ✅ Verified
- `backend/app/services/system_config_service.py`: `get_dynamic_payment_configs()` reads payment amounts, role map, and quota from DB, falls back to `constants.py` hardcoded values.
- Applied in:
  - `payment_service.py` (line 56): `create_payment()` reads valid amounts from SystemConfig.
  - `admin.py` (lines 391-407): `create_seed_user()` reads `quota_for_agent`/`quota_for_distributor` from SystemConfig.
  - `commission_service.py` (line 383): `process_payment()` reads valid amounts via `get_dynamic_payment_configs()`.

### S6: Scheduler Reads settlement_cycle_days
**Status:** ❌ Partially Broken (config key mismatch)
- `backend/app/services/scheduler_service.py` (lines 120-159): `start_scheduler()` queries `SystemConfig.config_key == "settlement_cycle_days"` with fallback to 30 days.
- **BUG**: `system_config_service.py` (line 22) defines `DEFAULT_CONFIGS["settlement_cycle"]` (value: "monthly"), NOT `"settlement_cycle_days"`. Since `_ensure_defaults()` only initializes keys in `DEFAULT_CONFIGS`, the key `"settlement_cycle_days"` is never populated in the database. The scheduler always falls back to 30 days regardless of admin configuration.
- Additionally, `_get_cron_trigger()` (lines 29-40) is defined but **never called** -- dead code. It correctly uses `get_settlement_cycle()` from constants.py, but is unreachable.

### S7: business_user_id Optional
**Status:** ✅ Verified
- `backend/app/services/license_service.py` (line 152): `activate_license()` signature is `activate_license(self, code: str, business_user_id: str | None, business_user_info: str | None, db: Session)`. Both `business_user_id` and `business_user_info` accept None.

### S8: Dashboard License Today Stats
**Status:** ✅ Verified
- `backend/app/services/dashboard_service.py` (lines 43-49): `get_stats()` returns `license_generated_today` (count of licenses with `func.date(License.created_at) == today_str`) and `license_activated_today` (count of licenses with `License.status == "activated"` AND `func.date(License.activated_at) == today_str`).

---

## 2. Remaining Gaps (S9 and New Findings)

### CRITICAL

#### GAP-C1: Alembic Migrations Out of Sync with ORM Models

| Aspect | Migration 003 Creates | Current Model Expects | Impact |
|--------|----------------------|----------------------|--------|
| Users table | `invite_code` column | `referral_code` column | ColumnNotFound on User query |
| Users.role enum | `('user','member','distributor','agent')` | `('distributor','agent')` | Enum cast failure |
| Licenses table | `user_id` NOT NULL, `email` column exists | `user_id` NULLABLE, no `email` column | Constraint violation or ColumnNotFound |
| Licenses.source enum | `('recharge','sale','role_builtin')` | `('payment','sale','role_builtin')` | Enum cast failure |
| Payments table | Creates `recharges` (different columns) | Uses `payments` | TableNotFound on Payment query |
| Referral codes table | Creates `invite_codes` (different columns: `generator_id`, `used_by`, etc.) | Uses `referral_codes` (columns: `code`, `user_id`, `key_version`, `is_active`) | TableNotFound on ReferralCode query |
| QuotaReplenishment | Not created by any migration | `quota_replenishments` | TableNotFound on replenish operations |

**Impact:** A fresh production database initialized via `alembic upgrade head` would create tables that DO NOT MATCH the current model definitions. The application would fail with `TableNotFound` or `ColumnNotFound` errors on the very first query. Only test environments (which use `Base.metadata.create_all()` directly, bypassing alembic) work correctly.

**Files affected:** `backend/alembic/versions/003_refactor_models_v2.py` (needs replacement migration that creates current schema), `backend/app/models/payment.py`, `backend/app/models/referral_code.py`, `backend/app/models/quota_replenishment.py`, `backend/app/models/license.py`, `backend/app/models/user.py`, `backend/app/models/commission_config.py`.

---

### HIGH

#### GAP-H1: Notification Emails Not Sent (FR-24 Violation)
**Severity:** High

`backend/app/services/notification_service.py` defines `_send_notification_email()` (line 112) as a static method, but it is **never invoked** from any call path. The service only writes notification records to the `notification_logs` table. The PRD FR-24 requires email notification for:
- Subordinate payment
- Commission credited
- Ticket status changed
- Payment approved
- Seed user created

**Evidence:** `grep` across the entire codebase for `_send_notification_email` returns only the definition in `notification_service.py`. Zero call sites.

**Files affected:** `backend/app/services/notification_service.py`.

#### GAP-H2: Missing Dedicated referral_relationships Table (S9)
**Severity:** High

PRD FR-8 specifies that relationship data must contain: upstream user ID, downstream user ID (5000/10000 only), referral code, payment record ID, and creation time. Currently:
- Relationships are tracked only via `parent_id` on the `User` model (a nullable FK to `users.id`).
- No separate `referral_relationships` table exists (confirmed by `grep` returning zero results).
- There is no way to trace which payment established a relationship.
- `parent_id` is mutable (can be overwritten), violating FR-8's requirement that relationships "cannot be deleted or modified."
- 888 payments that establish commission-only relationships have no formal tracking.

**PRD reference:** "关系数据包含：上级用户 ID、下级用户 ID（仅 5000/10000）、推荐码、支付记录 ID、创建时间" / "关系不可删除或修改" / "支持通过关系表追溯完整链条".

**Files affected:** Missing table; would affect `backend/app/services/team_service.py`, `backend/app/services/payment_service.py` `_handle_role_payment()` (line 187-188 where parent_id is set).

#### GAP-H3: Scheduler Config Key Mismatch Makes Settlement Cycle Unconfigurable
**Severity:** High

The scheduler queries `SystemConfig.config_key == "settlement_cycle_days"` (expecting an integer number of days), but the `_ensure_defaults()` method in `system_config_service.py` initializes `"settlement_cycle"` (a string with value "monthly"/"weekly"/"daily"). These are two different keys with different value semantics. The scheduler always falls back to 30 days because `"settlement_cycle_days"` is never auto-initialized.

The `_get_cron_trigger()` dead function (lines 29-40) correctly uses the `"settlement_cycle"` key via `get_settlement_cycle()`, but it is unreachable.

**Files affected:** `backend/app/services/scheduler_service.py` (lines 104-180), `backend/app/services/system_config_service.py` (line 22).

---

### MEDIUM

#### GAP-M1: Dead Code - `_get_cron_trigger()` in scheduler
**Severity:** Medium

`backend/app/services/scheduler_service.py` defines `_get_cron_trigger()` (lines 29-40) which is imported from `get_settlement_cycle()` but never called from any code path. `start_scheduler()` independently implements its own trigger-selection logic. The dead function represents technical debt and confusion about the actual scheduling mechanism.

#### GAP-M2: PayPage Redirect Whitelist Overly Restrictive
**Severity:** Medium

`payment-app/src/pages/PayPage.tsx` (line 10): `ALLOWED_REDIRECT_HOSTS = ['localhost', '127.0.0.1']`. For production deployment, the redirect whitelist needs to include the business system's domain. Currently hardcoded with no mechanism for configuration.

**Files affected:** `payment-app/src/pages/PayPage.tsx`.

#### GAP-M3: Payment Model Includes Unused `refunded` Status
**Severity:** Medium

`backend/app/models/payment.py` (line 31): The `payment_status` enum includes `"refunded"`, but the PRD's Non-Goals explicitly state: "不做退款：支付成功后不支持退款". This unused status creates confusion and potential future misuse.

**Files affected:** `backend/app/models/payment.py`.

---

### LOW

#### GAP-L1: Commission Config `updated_at` Not Updated on Edit
**Severity:** Low

`backend/app/api/v1/admin.py` (lines 264-266): When a commission config is updated, `reward_type` and `reward_value` are changed but `config.updated_at` is not explicitly refreshed before returning. The response reads `updated_at` from the refreshed object, but the column has `onupdate=func.now()` in the model definition (`commission_config.py` line 20), so this should auto-update. However, the interplay with `db.refresh(config)` may or may not surface the updated value depending on DB driver behavior.

---

## 3. Overall Code-Health Verdict

**CSS Color: RED** -- schema mismatch prevents production deployment

### Summary

| Category | Count |
|----------|-------|
| Previous fixes verified | 11 of 12 (S6 partially broken) |
| New CRITICAL gaps | 1 |
| New HIGH gaps | 3 |
| New MEDIUM gaps | 3 |
| New LOW gaps | 1 |

### Key Actions Required

1. **IMMEDIATE**: Create a new alembic migration (008) that drops `recharges`, `invite_codes` tables and creates `payments`, `referral_codes`, `quota_replenishments` tables with correct schemas. OR refactor migrations 003-007 into a single clean migration.

2. **HIGH**: Connect `_send_notification_email()` to the notification send path (e.g., call it from `send()` or from each `notify_*` static method).

3. **HIGH**: Create `referral_relationships` table and migration to satisfy FR-8.

4. **HIGH**: Align the scheduler config key: either add `settlement_cycle_days` to `DEFAULT_CONFIGS`, or refactor the scheduler to use the existing `settlement_cycle` key via `get_settlement_cycle()`.

5. **MEDIUM**: Add production domains to PayPage redirect whitelist. Consider making it configurable.

6. **MEDIUM**: Remove the dead `_get_cron_trigger()` function.

7. **MEDIUM**: Either remove the `refunded` status from `payment_status` enum or add a comment explaining its intended use despite the PRD Non-Goal.

### Key Files Referenced

- `D:\workspace\user-salse\backend\app\services\auth_service.py` -- S1/S2 verified
- `D:\workspace\user-salse\backend\app\services\team_service.py` -- S3 verified
- `D:\workspace\user-salse\backend\app\schemas\team.py` -- S3 verified
- `D:\workspace\user-salse\backend\app\services\license_service.py` -- S7 verified
- `D:\workspace\user-salse\backend\app\services\dashboard_service.py` -- S8 verified
- `D:\workspace\user-salse\payment-app\src\services\api.ts` -- C1 verified
- `D:\workspace\user-salse\payment-app\src\pages\PayPage.tsx` -- C1 verified, GAP-M2
- `D:\workspace\user-salse\backend\alembic\versions\004_seed_commission_configs_v2.py` -- C2 verified
- `D:\workspace\user-salse\backend\app\api\v1\quota.py` -- C3+S4 verified
- `D:\workspace\user-salse\backend\app\api\v1\admin.py` -- C3+C4 verified
- `D:\workspace\user-salse\backend\app\services\system_config_service.py` -- S5 verified
- `D:\workspace\user-salse\backend\app\services\scheduler_service.py` -- S6 broken, GAP-H3, GAP-M1
- `D:\workspace\user-salse\backend\app\services\payment_service.py` -- S5 integration verified
- `D:\workspace\user-salse\backend\app\services\commission_service.py` -- C2, FR-13 verified
- `D:\workspace\user-salse\backend\app\services\notification_service.py` -- GAP-H1
- `D:\workspace\user-salse\backend\app\services\referral_service.py` -- FR-3 verified
- `D:\workspace\user-salse\backend\app\models\user.py` -- model table mismatch (GAP-C1)
- `D:\workspace\user-salse\backend\app\models\payment.py` -- GAP-M3, table mismatch (GAP-C1)
- `D:\workspace\user-salse\backend\app\models\referral_code.py` -- table mismatch (GAP-C1)
- `D:\workspace\user-salse\backend\app\models\license.py` -- table mismatch (GAP-C1)
- `D:\workspace\user-salse\backend\app\models\quota_replenishment.py` -- table mismatch (GAP-C1)
- `D:\workspace\user-salse\backend\alembic\versions\003_refactor_models_v2.py` -- GAP-C1 (source of mismatch)
- `D:\workspace\user-salse\backend\alembic\versions\006_add_pending_user_key.py` -- references old `recharges` table
