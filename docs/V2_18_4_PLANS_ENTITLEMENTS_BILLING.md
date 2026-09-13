# V2-18.4 — PLANS + ENTITLEMENTS + BILLING FOUNDATION

Data: 2026-09-13

Status: **EM CERTIFICAÇÃO INTERNA**.

## Autoridades separadas

A implementação separa explicitamente:

**Commercial Billing Authority** — plano, entitlement, quota, usage, trial, grace, suspensão e
reativação.

**Fiscal Document Authority** — capability/readiness, emissão, lifecycle, idempotência, sequence,
archive e reconciliation.

Suspensão comercial bloqueia novas operações comerciais/uso medido, mas **não apaga nem torna
ilegítimo estado fiscal já existente**.

## Contratos internos

- `CommercialPlan`;
- `UsageQuota`;
- `CommercialSubscription`;
- `SubscriptionStatus`: trial, active, grace, suspended, canceled;
- checkpoint/restore de usage e estado.

## Invariantes

- quota falha fechado;
- entitlement ausente falha fechado;
- status suspenso/cancelado não aceita novo usage;
- reativação é transição explícita;
- cancelamento não reativa silenciosamente;
- nenhum plano contém `PRODUCTION_APPROVED` ou readiness fiscal;
- billing gateway não foi fixado nesta fase.

## Preço e gateway

Preço final continua decisão comercial do Diretor. A fundação é provider-neutral e não amarra o
produto a um gateway de cobrança antes dessa decisão.
