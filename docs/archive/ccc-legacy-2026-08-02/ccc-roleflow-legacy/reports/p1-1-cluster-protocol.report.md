# P1-1 cluster-protocol.md — Implementation Report

> 2026-07-06 | phase: 3 (P1-1)

## 交付

- File: `references/cluster-protocol.md` (229 lines)
- 10 sections, all required topics covered

## Section Map

1. Topology (with diagram)
2. Endpoints (5 endpoints with full schema)
3. Capability Tags (L1/L2/L3 convention)
4. Authentication (mTLS — red line 19 enforcement)
5. Error Codes (9 codes with recovery)
6. Examples (curl)
7. Examples (Python urllib)
8. Sizing & Limits
9. Versioning
10. Related (red-lines, lessons, design-validation)

## Key Decisions

1. **mTLS > Bearer token** (red line 19)
   - 6/6 agentmesh projects surveyed had ZERO auth — explicit anti-pattern
   - mTLS = mutual cert validation, no shared secret
2. **Free-form capability tags** (convention informational, not enforced)
   - L1/L2/L3 documented as convention
   - Any string accepted (matches clawmed-ai precedent)
3. **Error codes 9 standard HTTP**
   - Includes 410 (node offline) — distinct from 404 (never registered)
4. **Sizing boundaries explicit** to prevent bus from degrading silently
   - 100 nodes soft, 1000 hard
   - 90s heartbeat TTL (clawmed-ai precedent)

## Cross-References Embedded

- Section 10 explicit pointer to:
  - `references/red-lines.md` (18, 19, 20)
  - `docs/lessons.md` (27, 29, 30)
  - `DESIGN-VALIDATION.md`

## Out of Scope (deliberate)

- mTLS wiring in cluster-bus.py — P1-2 work (test capability)
- chunk_id commit idempotency — v1.2
- Direct dispatch endpoint — dispatcher is local CLI only
