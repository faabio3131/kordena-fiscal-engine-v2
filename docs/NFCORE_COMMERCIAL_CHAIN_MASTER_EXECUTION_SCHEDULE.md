# FM NFCORE V1 — CRONOGRAMA MESTRE DE EXECUÇÃO DA CADEIA COMERCIAL

**Status:** MASTER EXECUTION PLAN CANDIDATE  
**Data:** 2026-09-27  
**Objetivo:** fechar integralmente a cadeia comercial do NFCore sem provider lock-in, sem perda de segurança e sem mistura de dados entre clientes.

> Este cronograma é sequencial por dependência e evidência. Não representa promessa de duração. Um bloco só avança quando seus gates estiverem verdes.

---

## CURRENT EXECUTION CHECKPOINT — 2026-10-01 — REAL RAILWAY STATE AUDIT

GitHub main: `f2fd8a875bdf8ae5327d7f716209603f60d34570` with **FM NFCORE V1 CI #519 — SUCCESS**.

Read-only Railway inspection confirms that the external staging scaffold now exists but the CL-15 completion gate remains open:

- project `FM NFCORE Staging` exists with API, worker and portal services;
- no PostgreSQL service exists;
- no runtime variables/secrets are configured on the three services;
- API is SUCCESS on older SHA `11cec7991c5345e03ef54e58b1fa6b5fbcd51801`;
- worker is CRASHED on the same older SHA because durable runtime requires PostgreSQL persistence;
- portal is SUCCESS on older SHA `5201eaa663b029d304a89131c28d501e444f730d`;
- current main `f2fd8a875bdf8ae5327d7f716209603f60d34570` is not deployed;
- no public Railway domain is attached to API or portal;
- a Railway portal change remains staged and was not applied by this audit;
- repository remains PUBLIC, therefore real secret injection remains prohibited;
- `STAGING_DEPLOYED_AND_E2E_VALIDATED=false`;
- CL-15 remains **IN_PROGRESS / BLOCKED_EXTERNAL**;
- CL-16 remains **NOT_STARTED_OPERATIONALLY**.

Detailed evidence and Current → Target are recorded in
`docs/NFCORE_CL15_STAGING_CURRENT_AUDIT_2026-10-01.md`.

The next gate requires explicit human authorization before repository privacy changes,
paid/external Railway/PostgreSQL provisioning, real secret injection or real staging deploy.

---

## CURRENT EXECUTION CHECKPOINT — 2026-09-30 — SURGICAL RECONCILIATION

Reconciliation base main: `62150240bef42918e9f04a6d5ab955ac7f9cdecb`.

This checkpoint corrects schedule semantics after a context-continuity incident. It preserves
technically useful merged work but does not promote preparatory code into completed later phases.

Canonical state:

- CL-12 — `DONE`: implemented, tested, merged and post-merge certified;
- CL-13 — `DONE`: implemented, tested, merged and post-merge certified;
- CL-14 — `DONE`: implemented, tested, merged and post-merge certified;
- CL-15 — `IN_PROGRESS / BLOCKED_EXTERNAL`:
  - Railway provider contract is prepared;
  - activation-delivery adapter is implemented/unit-tested but not wired into RuntimeComposition;
  - no real NFCore staging exists;
  - no real activation provider/credential/delivery evidence exists;
  - no real staging E2E or rollback rehearsal exists;
  - gate `STAGING_DEPLOYED_AND_E2E_VALIDATED` is **NOT MET**;
- CL-16 — `NOT_STARTED_OPERATIONALLY`:
  - internal validation harness exists as `PREPARED_NOT_ACTIVE`;
  - it cannot start real channel validation until CL-15's real staging gate is met;
  - `COMMERCIAL_CHANNEL_READY` is **NOT MET**;
- CL-17 — `NOT_STARTED_OPERATIONALLY`:
  - historical fiscal/homologation/pilot authorities may be reused later;
  - no official homologation or real controlled pilot is claimed;
- CL-18 — `NOT_STARTED`;
- `PRODUCTION_APPROVED` — **NO**;
- NFCore -> Kordena cutover — **FORBIDDEN IN THIS PHASE**.

PRs #75-#80 remain preserved as repository history. Their canonical classification is recorded in
`docs/NFCORE_CONTEXT_INCIDENT_RECONCILIATION_2026-09-30.md`.

No later phase may be treated as operationally started merely because an internal harness,
adapter or reusable authority exists. Sequential dependency gates remain mandatory.

---

## VISÃO EXECUTIVA

```text
CL-11.0  Arquitetura + Security/Data Map
   ↓
CL-11.1  Canonical Purchase/Subscription Persistence
   ↓
CL-11.2  Validated Sale Event Contract
   ↓
CL-11.3  Commercial Fulfillment Orchestrator
   ↓
CL-11.4  Customer Claim + Canonical Identity
   ↓
CL-11.5  Provisioning + OWNER + Activation
   ↓
CL-11.6  Purchase Readiness Gate
   ↓
CL-11.7  First-Party Site Purchase Journey
   ↓
CL-11.8  Cakto Adapter Reconciliation
   ↓
CL-11.9  Selected Additional Channel Adapter(s)
   ↓
CL-12    Trial
   ↓
CL-13    Security/LGPD/Observability Hardening
   ↓
CL-14    Portal/Brand/Admin UX + Site CI Governance
   ↓
CL-15    Real Staging + Activation Delivery
   ↓
CL-16    Real Commercial Channel Validation
   ↓
CL-17    Fiscal Homologation + Controlled Pilot
   ↓
CL-18    Production Readiness + Human Go/No-Go
```

---

## FASE 0 — CL-11.0 — ARQUITETURA, DADOS E THREAT MODEL

### Objetivo

Congelar autoridade, dados e segurança antes de escrever código.

### Entregas

- ADR CL-11 aprovado;
- mapa de autoridades;
- mapa de dados;
- mapa de PII/secrets;
- tenant/unit isolation map;
- provider namespace map;
- canonical event contracts;
- retention matrix;
- threat model;
- acceptance matrix.

### Security gates

- nenhuma autoridade duplicada;
- external customer ID provider-scoped;
- tenant ID NFCore-owned;
- raw token/secret proibido em log;
- política de PII definida;
- cross-tenant/cross-provider threats documentados;
- HUMAN/LEGAL REVIEW marcado quando necessário.

### Saída

`ARCHITECTURE_APPROVED`

Nenhuma implementação antes disso.

---

## FASE 1 — CL-11.1 — CANONICAL PURCHASE / SUBSCRIPTION / ENTITLEMENT DURÁVEL

### Objetivo

Transformar o billing provider-neutral já existente em autoridade comercial persistente.

### Implementar

- canonical purchase/acquisition entity;
- durable `CommercialSubscription`;
- durable entitlement state;
- repositories/UoW;
- PostgreSQL migrations;
- explicit state transitions;
- provider mapping references separadas.

### Segurança

- tenant isolation;
- provider-scoped external IDs;
- unique constraints seguras;
- nenhuma PII desnecessária;
- audit trail;
- optimistic/idempotent transitions.

### Testes

- fresh migration;
- upgrade migration;
- duplicate event;
- transition ordering;
- cancellation/refund;
- cross-tenant collision;
- same external ID across providers;
- backup/restore.

### Gate de saída

`CANONICAL_COMMERCIAL_STATE_READY`

---

## FASE 2 — CL-11.2 — VALIDATED SALE EVENT CONTRACT

### Objetivo

Criar o contrato estreito entre adapters externos e o Core comercial.

### Implementar

- provider-neutral event DTO/domain contract;
- event ID/dedup semantics;
- provider namespace;
- canonical plan/price resolution;
- authentication proof boundary;
- event normalization rules.

### Proibido

- raw provider payload como domínio;
- tenant ID vindo do provider;
- browser-originated `SaleConfirmed`;
- provider-specific fields vazando para Core.

### Testes

- forged event;
- unknown provider;
- unknown plan;
- duplicate;
- stale/out-of-order;
- wrong product mapping;
- provider collision.

### Gate de saída

`VALIDATED_SALE_EVENT_CONTRACT_READY`

---

## FASE 3 — CL-11.3 — COMMERCIAL FULFILLMENT ORCHESTRATOR

### Objetivo

Transformar venda validada em estado canônico idempotente.

### Fluxo

```text
ValidatedSale
 -> resolve canonical product/plan
 -> upsert canonical purchase
 -> transition subscription
 -> grant/revoke entitlement
 -> determine claim/provisioning next state
```

### Estados candidatos

- UNCLAIMED;
- IDENTITY_REQUIRED;
- READY_TO_PROVISION;
- PROVISIONED;
- ACTIVATION_PENDING;
- ACTIVE;
- MANUAL_REVIEW;
- REFUNDED/CANCELED commercial state.

### Testes

- repeated event;
- partial failure;
- retry after crash;
- transaction rollback;
- event ordering;
- concurrent duplicate;
- refund after provisioning;
- chargeback;
- manual-review path.

### Gate

`FULFILLMENT_CORE_READY`

---

## FASE 4 — CL-11.4 — CUSTOMER CLAIM E IDENTIDADE CANÔNICA

### Objetivo

Permitir venda iniciada fora do Site sem transformar dados do marketplace em tenant.

### Implementar

- claim token/reference segura;
- verification of buyer contact ownership;
- identity completion form/API;
- organization identity resolution;
- existing-customer link rules;
- conflict/manual-review rules;
- claim expiry/replay protection.

### Dados sensíveis

- minimizar PII;
- não logar e-mail/telefone em claro sem necessidade;
- token raw somente no canal de ativação;
- hash de token em persistence;
- retenção definida;
- export/delete mapping.

### Testes

- token replay;
- expired claim;
- buyer email collision;
- organization conflict;
- cross-tenant claim;
- account takeover attempt;
- provider email change;
- duplicate purchase same buyer.

### Gate

`SECURE_CLAIM_READY`

---

## FASE 5 — CL-11.5 — PROVISIONING + OWNER + ACTIVATION

### Objetivo

Conectar o fulfillment ao serviço canônico já existente.

### Reutilizar

`CommercialCustomerProvisioningService`

`PasswordRecoveryService`

### Implementar

- orchestrator -> provisioning;
- idempotent OWNER creation;
- activation delivery port;
- delivery retry;
- activation state projection;
- no-account-enumeration behavior.

### Testes E2E

```text
paid sale
 -> canonical purchase
 -> claim
 -> organization
 -> OWNER
 -> activation delivered
 -> password set
 -> login
 -> portal bootstrap
 -> unit onboarding
```

### Security gates

- OWNER nunca duplicado;
- tenant nunca derivado do provider;
- activation token one-time;
- reset revoga sessions;
- delivery failure não perde purchase;
- delivery logs sem PII/secret.

### Gate

`PAID_CUSTOMER_CAN_LOGIN`

---

## FASE 6 — CL-11.6 — PURCHASE READINESS GATE

### Objetivo

Impedir venda real quando a entrega não estiver pronta.

### Atualizar

`GET /v1/commercial/offer`

`purchase_enabled` deve considerar:

- release;
- pricing;
- checkout;
- provider event receiver;
- canonical commercial persistence;
- fulfillment;
- provisioning;
- activation delivery.

### Testes

Cada dependência ausente -> `purchase_enabled=false`.

### Gate

`NO_CHARGE_WITHOUT_DELIVERY_PATH`

---

## FASE 7 — CL-11.7 — SITE FM FIRST-PARTY PURCHASE JOURNEY

### Objetivo

Oferecer UX própria sem tornar Site obrigatório.

### Fluxo

```text
Site
 -> plan selection
 -> minimum identity
 -> NFCore acquisition reference
 -> selected checkout
 -> provider payment
 -> validated event
 -> claim/activation
```

### Segurança

- BFF server-side;
- no secret no browser;
- browser não define payment success;
- browser não define tenant;
- browser não define entitlement;
- CSRF/rate-limit onde aplicável.

### Gate

Site purchase E2E verde.

---

## FASE 8 — CL-11.8 — CAKTO ADAPTER RECONCILIATION

### Objetivo

Reaproveitar o adapter já existente sem duplicar autoridade.

### Preservar

- HMAC;
- webhook receiver;
- inbox;
- retry/dead-letter;
- reconciliation;
- product/offer binding.

### Alterar

- traduzir evento para canonical `ValidatedSaleEvent`;
- provider-local entitlement deixa de ser Core authority;
- external customer mapping permanece adapter-local.

### Gates

- Cakto event -> canonical purchase;
- duplicate safe;
- refund/chargeback;
- reconciliation drift;
- no tenant identity leakage.

---

## FASE 9 — CL-11.9 — NOVOS CANAIS SELECIONADOS

### Regra

Só implementar provider decidido comercialmente.

### Para Hotmart, se aprovada

- pesquisa oficial atual;
- webhook auth;
- product/subscription mapping;
- adapter;
- tests;
- controlled external validation.

### Para Kax/outro

Mesmo processo.

### Gate

Cada adapter deve provar equivalência de contrato sem alterar Core.

---

## FASE 10 — CL-12 — TRIAL GOVERNADO

### Objetivo

Criar trial sem confundir com pricing metadata.

### Fluxo

```text
trial request
 -> trial subscription
 -> organization/OWNER
 -> activation
 -> temporary entitlement
 -> expiry/conversion
```

### Segurança

- anti-abuse;
- rate limit;
- duplicate trial policy;
- tenant identity rules;
- no production fiscal authority.

### Gate

`TRIAL_ENABLED` somente após E2E certificado.

---

## FASE 11 — CL-13 — SECURITY, PRIVACY, LGPD E OBSERVABILIDADE

### Objetivo

Certificação transversal da cadeia comercial.

### Segurança

- threat model atualizado;
- secret scan;
- PII scan/log review;
- RBAC;
- CSRF;
- session/cookie;
- rate limiting;
- webhook replay;
- tenant/unit/provider isolation;
- dead-letter redaction;
- backup confidentiality.

### LGPD técnico

Mapear:

- dados coletados;
- finalidade;
- retenção;
- exportação;
- exclusão;
- backups;
- subprocessadores;
- billing data;
- fiscal data;
- audit/log data.

Questões jurídicas -> `HUMAN/LEGAL REVIEW REQUIRED`.

### Observabilidade

Dashboards/alerts de:

- sale events;
- failures;
- backlog;
- claim;
- provisioning;
- activation;
- billing transition;
- provider drift.

### Gate

`SECURITY_PRIVACY_GATE_PASS`

---

## FASE 12 — CL-14 — UX/BRANDING E GOVERNANÇA DE CI

### Objetivo

Fechar dívidas não funcionais sem reconstruir aplicação.

### NFCore Portal

- reconciliar logo aprovada;
- Brand Kit;
- login;
- sidebar;
- favicon;
- nomenclatura NFCore/FM NFCORE;
- neutral commercial channels UX.

### Site FM

- adicionar validation em `push: main`;
- preservar PR gates;
- certificar merge commit.

### Gates

- accessibility;
- responsive;
- no auth/RBAC/API regression;
- visual identity approved;
- CI main green.

---

## FASE 13 — CL-15 — STAGING REAL

### Dependências externas

- hosting escolhido;
- PostgreSQL;
- HTTPS;
- DNS/subdomain;
- Secret Manager/Vault;
- deploy driver;
- monitoring.

### Execução

```text
preflight
 -> backup
 -> migration
 -> deploy immutable revision
 -> health/readiness
 -> API/worker/portal smoke
 -> commercial E2E
 -> rollback rehearsal
```

### Security

- repository PRIVATE antes de secrets reais;
- no secrets em artifacts;
- least privilege;
- environment separation;
- production credentials proibidas em staging.

### Gate

`STAGING_DEPLOYED_AND_E2E_VALIDATED`

---

## FASE 14 — CL-16 — REAL COMMERCIAL CHANNEL VALIDATION

### Objetivo

Configurar canais selecionados de verdade.

### Para cada canal

- real account/KYC;
- product/plan configuration;
- checkout;
- webhook secret;
- HTTPS callback;
- controlled test purchase;
- refund/cancel test quando permitido;
- reconciliation;
- evidence.

### Gate

Canal é `COMMERCIAL_CHANNEL_READY` somente com evidência real.

---

## FASE 15 — CL-17 — FISCAL HOMOLOGATION + PILOT

### Dependências

- certificates;
- CSC;
- provider credentials;
- SEFAZ/prefeitura/provider environments.

### Execução

- exact launch matrix;
- official homologation;
- evidence;
- controlled pilot;
- reconciliation;
- incident/rollback/kill-switch procedures.

### Gate

Nunca marcar célula fiscal como homologada sem prova externa real.

---

## FASE 16 — CL-18 — PRODUCTION READINESS E GO/NO-GO

### Auditoria final

Validar:

- functional journey;
- commercial journey;
- auth/RBAC;
- tenant/unit isolation;
- secrets;
- LGPD/legal reviews;
- staging evidence;
- billing;
- channels;
- fiscal homologation;
- observability;
- backup/restore;
- runbooks;
- support;
- incidents;
- premium UI;
- zero critical blockers.

### Decisão humana

Somente humano pode emitir:

`PRODUCTION_APPROVED`

### Cutover

- exact certified revision;
- production migration;
- deploy;
- smoke;
- monitoring;
- support watch;
- rollback readiness.

### Estado final

`COMMERCIAL_LIVE` somente após evidência de toda a cadeia.

---

# GATES TRANSVERSAIS QUE BLOQUEIAM TODAS AS FASES

Qualquer um bloqueia avanço:

- secret em Git/log;
- PII leakage;
- cross-tenant data access;
- tenant spoofing;
- provider ID usado como canonical tenant;
- missing idempotency;
- uncontrolled retry;
- invalid migration;
- CI red;
- checkout cobrando sem fulfillment;
- fake homologation;
- missing backup/restore evidence;
- missing human approval para irreversible action.

---

# CHECKPOINT OBRIGATÓRIO POR FASE

Registrar:

- data;
- CURRENT main;
- branch;
- HEAD;
- PR;
- arquivos alterados;
- migrations;
- testes;
- CI;
- security evidence;
- data/PII changes;
- decisions;
- risks;
- blockers;
- external dependencies;
- next action.

O projeto nunca deve depender apenas do chat.

---

# CRITÉRIO DE ÊXITO DO CRONOGRAMA

A cadeia está fechada quando conseguirmos demonstrar, de maneira reproduzível:

```text
venda real autorizada
 -> evento autenticado
 -> purchase canônica
 -> subscription/entitlement
 -> claim seguro
 -> organização
 -> OWNER
 -> ativação
 -> login
 -> onboarding
 -> uso
 -> renovação
 -> cancel/refund
 -> isolamento preservado
 -> auditoria
 -> recovery
```

sem provider lock-in, sem vazamento de dados e sem autoridade duplicada.
