# NFV1-P02-T05 — Billing / Planos / Uso — checkpoint de implementação

**Data:** 2026-10-07  
**Task ID:** NFV1-P02-T05  
**Status:** IN_PROGRESS / IMPLEMENTATION_CANDIDATE  
**Repositório:** `faabio3131/kordena-fiscal-engine-v2`  
**Branch:** `feat/nfv1-p02-t05-billing-plans-usage`  
**Base imutável:** `acc8510f3df11fb284386f951e427dffdeeef242`

## CURRENT revalidado

- T04 DONE_CERTIFIED; PR #124 mergeada;
- main `acc8510f3df11fb284386f951e427dffdeeef242`;
- CI main #654 SUCCESS e Plan Governance #75 SUCCESS;
- zero PRs abertas na entrada;
- T05 é o primeiro item incompleto do ledger;
- cronograma T05: expor estado canônico de Billing/Planos/Uso mantendo provider externo como adapter.

## CURRENT -> TARGET

CURRENT já possuía `CommercialSubscription`, `SubscriptionCheckpoint`, `CommercialPlan`,
quotas/usage, subscription durável, catálogo de pricing versionado e `billing.read`.
As três superfícies `billing`, `plans` e `usage` existiam na navegação/API/RBAC,
mas não tinham projeção durável composta.

TARGET:

`sessão -> billing.read -> tenant canônico -> canonical commercial store / published pricing -> projeção read-only`.

## Controles

- nenhuma mutação de assinatura, billing status, entitlement, usage ou pricing pelo customer Portal;
- OWNER/ADMIN/AUDITOR/BILLING usam a permissão existente `billing.read`; OPERATOR falha fechado;
- tenant vem exclusivamente da sessão;
- billing lê somente a assinatura canônica do tenant;
- usage deriva apenas do checkpoint persistido e quotas do plano canônico;
- plans usa somente catálogo de pricing publicado e resolução canônica por tenant;
- preços não são inventados nem hardcoded no runtime; valores de teste são exclusivamente sintéticos;
- provider_id, external_subscription_id, external_price_reference e contract_reference não são projetados;
- gateway/provider externo continua adapter e nunca vira autoridade de subscription/plan/usage;
- ausência de assinatura ou catálogo retorna estado vazio, não status fabricado;
- nenhum trial é inferido a partir de trial_days;
- nenhuma decisão de preço, promoção, plano real ou provider foi tomada nesta tarefa.

## Implementação candidata

- novo `CommercialPortalReadService` read-only;
- composition root injeta canonical commercial UoW + pricing administration já existentes;
- `DurableHumanPortalExecutor` expõe `billing/plans/usage` somente quando o reader canônico está composto;
- UI preserva navegação existente e explicita que providers externos são adapters;
- testes unitários para billing/usage/plans, tenant override e ausência de estado;
- teste PostgreSQL/HTTP condicionado à DSN da CI cobre persistência real e RBAC dos cinco papéis.

## Gates locais até o checkpoint

- Ruff focado: PASS;
- Mypy `src`: PASS, 186 source files;
- testes focados locais: 3 PASS + teste PostgreSQL SKIP por DSN local ausente;
- Plan Governance: PASS, 59 tasks, próximo T05;
- frontend contract atualizado; matriz integral ainda será executada antes da PR.

## Fora de escopo

Sem preço/plano real novo, alteração de catálogo real, checkout, cobrança externa, webhook comercial,
segredo, credencial, deploy, staging write, migration produtiva, fiscal real, DNS, produção ou Go-Live.
P3/P8 permanecem responsáveis pela validação operacional de aquisição/cobrança.
