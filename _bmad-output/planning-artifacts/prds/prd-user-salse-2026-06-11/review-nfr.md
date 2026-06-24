# NFR Compliance Review

**PRD:** `prd-user-salse-2026-06-11/prd.md` section 4.12  
**Audit date:** 2026-06-24  
**Auditor:** Claude Code (subagent)  
**Scope:** 5 NFRs verified against 9 source files in `backend/app/`

---

## NFR-1: Commission Idempotency (佣金记账幂等性)

**Verdict: ✅ Compliant**

### Requirements from PRD
- Every commission record is idempotency-protected by a unique business ID
- Coverage includes: first reward, followup reward, long-term reward
- Same business operation must not produce duplicate commission records

### Evidence

| Mechanism | Location | Detail |
|-----------|----------|--------|
| Two-layer idempotency (check-then-insert + UNIQUE fallback) | `commission_service.py:38-69` | Query existing on `business_id` first; second-layer `IntegrityError` catch on UNIQUE constraint as concurrent race defense |
| DB-level UNIQUE constraint | `models/commission_record.py:17` | `business_id = Column(String(64), unique=True, nullable=False)` |
| First reward business_id | `commission_service.py:173` | `f"payment_{payment_id}"` |
| Followup reward business_id | `commission_service.py:219` | `f"payment_{payment_id}_followup_{agent.id}"` |
| Long-term reward business_id | `commission_service.py:264` | `f"settle_{user_id}_{period}"` |
| Long-term reward pre-check | `commission_service.py:267-274` | Additional idempotency check before calling `record_commission()` |
| Payment callback idempotency | `payment_service.py:285-287` | `payment.status == "paid"` early return |

### Risk Assessment: Low
- The `record_commission()` docstring explicitly documents both the happy-path idempotency (SELECT-first) and the concurrent race scenario (UNIQUE IntegrityError), including the transaction isolation note that the only production caller (`process_payment`) uses `for_update` row locking, making the UNIQUE path a defense-in-depth fallback.
- All three commission types (first_reward, followup_reward, team_bonus) are covered by unique `business_id` schemes.
- Payment callback idempotency is independently implemented via status check + row lock.

---

## NFR-2: Audit Log (审计日志)

**Verdict: ⚠️ Partial**

### Requirements from PRD
- All financial operations must record complete audit logs
- Fields: operation time, operator, operation type, before/after values, associated business ID
- Logs must be non-modifiable and non-deletable (不可删除或修改)

### Evidence

**Schema coverage:**

| Required field | AuditLog column | Present? |
|---------------|-----------------|----------|
| Operation time | `created_at` (server_default `func.now()`) | Yes |
| Operator | `operator_type` + `operator_id` | Yes |
| Operation type | `action` (String(64)) | Yes |
| Before/after values | `old_value` (JSON), `new_value` (JSON) | Yes |
| Associated business ID | `business_id` (String(64)) | Yes |

**Audit log call sites:**

| Action | Location | Flow |
|--------|----------|------|
| `commission_create` | `commission_service.py:71-86` | After commission record flush |
| `payment_callback` | `payment_service.py:300-309` | After payment status change to "paid" |
| `payment_approve` | `payment_service.py:372-382` | After admin approve |
| `payment_reject` | `payment_service.py:418-427` | After admin reject |

**Missing — Immutability (HIGH GAP):**

The PRD explicitly requires "审计日志不可删除或修改". The current implementation has **zero protection** against tampering:
- `AuditLog` uses standard SQLAlchemy model with no append-only configuration
- No database trigger preventing `UPDATE` or `DELETE` on `audit_logs` table
- No ORM-level read-only flag or event listener
- Any database user with write access can modify or delete rows directly

### Risk Assessment: Medium
- All required schema fields and business logic call sites are correctly implemented.
- The immutability gap is significant for a production financial system: audit logs currently provide evidence but not tamper-proof evidence.
- **Recommendation:** At minimum, add an ORM-level event listener that prevents updates/deletes on AuditLog; for production, add a database trigger or migrate to an append-only store.

---

## NFR-3: Referral Code Security (推荐码安全性)

**Verdict: ✅ Compliant**

### Requirements from PRD
- Codes use HMAC-SHA256 signature
- Signing key held server-side only
- Tampered codes must fail parsing

### Evidence

| Requirement | Implementation | Location |
|------------|---------------|----------|
| HMAC-SHA256 signing | `hmac.new(secret, payload, hashlib.sha256).hexdigest()[:16]` | `security.py:56` |
| Server-held secret | `settings.INVITE_CODE_SECRET` (config.py env var) | `security.py:55` |
| Tamper detection | `verify_invite_code_signature()` reconstructs HMAC, uses `hmac.compare_digest` | `security.py:60-87` |
| Cross-validation | DB lookup + signature user_id cross-check (`sig_user_id != rc.user_id`) | `referral_service.py:52-66` |
| Deactivation support | `rc.is_active` check | `referral_service.py:69-70` |
| Code format | `Base62(user_id).nonce.HMAC[:16]` | `security.py:48` |
| Default secret check | `validate_security_secrets()` rejects default `INVITE_CODE_SECRET` in production | `config.py:57-58` |

### Risk Assessment: Low
- Implementation follows standard HMAC-SHA256 pattern with constant-time comparison (prevents timing attacks).
- The two-layer validation (signature + DB cross-check) defends against both signature forgery and stale/revoked codes.
- Production environment blocks default secrets via `validate_security_secrets()`.

---

## NFR-4: License Security (License 安全性)

**Verdict: ✅ Compliant**

### Requirements from PRD
- Codes must be anti-forgery
- One-time use: once activated, cannot be reused
- Verification endpoint must use API Key authentication
- Activation binds business-system user identifier (prevent multi-device sharing)

### Evidence

| Requirement | Implementation | Location |
|------------|---------------|----------|
| Code integrity (HMAC-SHA256) | `_generate_license_code()` uses `LICENSE_SECRET` | `license_service.py:20-33` |
| Code verification | `_verify_license_code()` with constant-time compare | `license_service.py:36-62` |
| API Key auth | `x_api_key: str = Header(..., alias="X-API-Key")` + `hmac.compare_digest(x_api_key, settings.LICENSE_API_KEY)` | `license.py:53,61` (verify), `license.py:88,96` (activate) |
| One-time use (status check) | Step 3 in `verify_license()`: status must be "unused" | `license_service.py:141-145` |
| One-time use (row lock) | `with_for_update()` in `activate_license()` | `license_service.py:174-178` |
| Re-activation prevention | `if license_obj.status == "activated": return {"success": False, "message": "License 已激活"}` | `license_service.py:184-185` |
| Business user binding | `activated_user_id` + `activated_user_info` fields | `license_service.py:191-192`; `models/license.py:12-13` |
| Key versioning | `key_version` column for secret rotation | `models/license.py:26` |
| Signature verification before DB lookup | Prevents unnecessary DB queries on forged codes | `license_service.py:168-171` |
| Default key check | Production rejects default `LICENSE_SECRET` and `LICENSE_API_KEY` | `config.py:59-62` |

### Risk Assessment: Low
- Four-layer defense: HMAC integrity, API Key auth, DB status check with row lock, business-user binding.
- The `/license/verify` endpoint allows the business system to both verify and optionally activate in one call (line 67-72), which is documented behavior.
- Key version column enables rotation without invalidating existing licenses.
- **Minor observation:** The `activate_license()` uses `db.commit()` directly (line 194) rather than deferring to the caller, which differs from the pattern in `commission_service.py` where callers manage transactions. This may cause partial-activation issues if the caller needs to roll back a larger transaction. This is a code consistency concern, not a security issue.

---

## NFR-5: Payment Security (支付安全)

**Verdict: ⚠️ Partial**

### Requirements from PRD
- Callback verification using official WeChat/Alipay signatures
- Callback idempotency: same payment does not trigger duplicate processing
- `redirect` parameter whitelist validation

### Evidence

**Callback signature verification:**

| Mechanism | Location | Detail |
|-----------|----------|--------|
| HMAC-SHA256 verification | `payments.py:84-99` | Internal HMAC with `PAYMENT_CALLBACK_SECRET` |
| Constant-time comparison | `payments.py:99` | `hmac.compare_digest(expected, signature)` |
| Required header | `payments.py:106` | `x_signature: str = Header(..., alias="X-Signature")` |
| Default secret check | `config.py:63-64` | Production blocks default `PAYMENT_CALLBACK_SECRET` |

**Critical Gap (MEDIUM):** The verification uses a **custom internal HMAC-SHA256 scheme**, not the official WeChat/Alipay signature algorithms. The code itself acknowledges this at `payments.py:87-91`:
```python
TODO: 对接真实微信/支付宝支付网关时，需替换为官方签名验证：
- 微信支付 V3: RSA-SHA256 签名验证（使用微信平台公钥）
- 支付宝: RSA2 签名验证（使用支付宝公钥）
当前为内部 webhook 签名机制，适用于模拟支付或内部支付网关。
```
This means the current implementation only protects against trivial forgery; anyone who discovers `PAYMENT_CALLBACK_SECRET` can forge valid callbacks. For a production deployment with a real payment gateway, this must be replaced.

**Callback idempotency:**

| Mechanism | Location | Detail |
|-----------|----------|--------|
| Row lock | `payment_service.py:280` | `for_update=True` on payment query |
| Status guard | `payment_service.py:285-287` | Already "paid" → return early |
| Status validation | `payment_service.py:289-290` | Must be "pending" or error |
| Audit log after idempotent skip | Not logged separately | Logged only on successful processing |

**Redirect whitelist:**

| Mechanism | Location | Detail |
|-----------|----------|--------|
| Hostname whitelist | `schemas/payment.py:18-22` | Read from `REDIRECT_ALLOWED_HOSTS` env var (default: localhost, 127.0.0.1) |
| URL scheme validation | `schemas/payment.py:52-53` | Must be http or https |
| Hostname extraction + validation | `schemas/payment.py:54-61` | Parsed, lowercased, checked against set |
| Error message | `schemas/payment.py:58-61` | Returns allowed hosts on failure |
| Applied at request creation | `schemas/payment.py:42-62` | `field_validator("redirect_url")` |

### Risk Assessment: Medium
- Callback signature verification is the weakest link. The current HMAC scheme is adequate for the mock/internal-payment-gateway scenario described in the codebase, but **must** be upgraded to real WeChat/Alipay verification before production deployment with real payment providers.
- Callback idempotency is solid: row lock + status check forms a robust defense.
- Redirect whitelist is well-implemented: scheme validation + hostname whitelist with configurable env var.

---

## Cross-Cutting Observations

### 1. Default Secret Protection
`config.py:48-72` implements a production startup guard that rejects all five secrets if they still use defaults. This is good security hygiene and applies to NFR-3, NFR-4, and NFR-5.

### 2. Audit Log Coverage Gap
Although NFR-2 is primarily about audit logging, NFR-1 references `commission_create` audit entries (implemented), but there is no audit log for:
- Referral code revocation / deactivation
- License key version change
- Config changes (commission rates, payment amounts)
These may be out of scope for v1, but worth noting.

### 3. Database-Level Immutability
NFR-2's immutability requirement is the only NFR with a structural gap that cannot be closed by code changes alone — it requires either database-level DDL (triggers, event-driven enforcement) or an append-only storage backend.

### 4. Transaction Pattern Inconsistency
`license_service.py:194` calls `db.commit()` directly, while `commission_service.py` specifically delegates commit to the caller. If license activation is ever composed within a larger transaction, this will cause premature commits. This is a code-quality issue rather than an NFR compliance issue.

---

## Summary

| NFR | Verdict | Key Strengths | Key Gaps | Risk |
|-----|---------|---------------|----------|------|
| NFR-1: Commission idempotency | ✅ Compliant | Two-layer check+UNIQUE, all 3 types covered, row-lock caller | None | Low |
| NFR-2: Audit log | ⚠️ Partial | Schema covers all PRD fields, 4 call sites | **No immutability protection** — logs can be modified/deleted | Medium |
| NFR-3: Referral code security | ✅ Compliant | HMAC-SHA256, constant-time compare, DB cross-validation, deactivation support | None | Low |
| NFR-4: License security | ✅ Compliant | 4-layer defense, one-time use enforced, API Key auth, business-user binding | Minor: direct commit in activate_license() | Low |
| NFR-5: Payment security | ⚠️ Partial | Idempotency solid, redirect whitelist well-implemented | **Callback uses custom HMAC, not real WeChat/Alipay signatures** (acknowledged in TODO) | Medium |

**Files examined:**
- `backend/app/services/commission_service.py`
- `backend/app/services/audit_service.py`
- `backend/app/services/payment_service.py`
- `backend/app/services/license_service.py`
- `backend/app/services/referral_service.py`
- `backend/app/core/security.py`
- `backend/app/core/config.py`
- `backend/app/api/v1/payments.py`
- `backend/app/api/v1/license.py`
- `backend/app/schemas/payment.py`
- `backend/app/models/commission_record.py`
- `backend/app/models/audit_log.py`
- `backend/app/models/license.py`
