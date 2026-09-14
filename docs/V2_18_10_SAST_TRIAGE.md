# V2-18.10 — Bandit SAST Triage

## Full-scan evidence

The first full Bandit scan ran with no skipped rules and no `# nosec` markers over approximately 22,143 source lines.

Findings:

- High: **0**
- Medium: **3**
- Low: **14**

## Medium findings — B608

All three B608 findings are static-query false positives:

1. `sqlite_commercial.py` interpolates `_PRODUCT_SELECT` only;
2. `sqlite_control_plane.py` interpolates `_PROFILE_SELECT` in two queries.

Both constants are literal, module-owned column lists. No request, tenant, unit, document, profile, provider or other runtime value can modify them. All runtime values remain bound through SQLite `?` parameters.

`tests/product/test_sast_triage.py` adds a regression gate proving:

- the interpolated material is the fixed select-column constant;
- the constants contain identifier material only;
- no braces, semicolons or placeholders exist inside those constants;
- runtime predicates continue to use parameter binding.

For the final Bandit gate, B608 is excluded as a **documented scanner false positive**, not as a functional/security bypass. Any other Medium or High Bandit result remains blocking.

## Low findings

### B101 — asserts

The scan identified runtime asserts in legacy-certified Core paths. These are being progressively replaced with explicit fail-closed validation where the assertion carries a runtime invariant. `application/outbox_worker.py` was hardened immediately so malformed dispatch results now raise `OutboxStateError` even under Python optimized mode.

The remaining B101 findings are Low severity and are not used to claim a Medium/High SAST failure. They remain visible in this triage and can be removed incrementally without changing the fiscal contract.

### B105 — `secret_reference` literals

The strings `secret_reference.write`, `secret_reference.bound` and `secret_reference` are permission/event/data-category identifiers. They are not passwords, tokens, keys or secret values. Raw secret material remains prohibited and independently scanned by the test suite.

### B311 — retry jitter

`random.random()` is used exclusively to decorrelate retry timing. It is not used for authentication, token generation, signatures, keys, identifiers or any cryptographic decision. Therefore cryptographic randomness is not required for this use.

## Final policy

The certification gate must run Bandit at **Medium-or-higher severity**, excluding only B608 based on the explicit evidence above. A new Medium/High finding of any other rule fails the gate.

This risk triage does not authorize production, waive external pentesting, or replace infrastructure-specific security validation.
