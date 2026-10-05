# FM NFCORE V1 — Matriz Canônica de Capacidades

**Task:** NFV1-P00-T02 — Congelar matriz de capacidades  
**Data de auditoria:** 2026-10-05  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**CURRENT auditado:** `main@faf529a0f1852c9107858da730c6103234a30b2f`  
**CI CURRENT de origem:** FM NFCORE V1 CI #583 — SUCCESS  
**Plan Governance CURRENT de origem:** #12 — SUCCESS  
**Escopo:** classificação do que existe, está integrado, está exposto, está implantado e está comprovado. Nenhuma implementação funcional é feita nesta tarefa.

## 1. Regra de leitura

Esta matriz não usa “existe no repositório” como sinônimo de “pronto”.

Legenda:

- **OK** — implementação CURRENT existe na camada e possui evidência interna coerente.
- **PARCIAL** — existe implementação relevante, mas falta composição, superfície, adapter, jornada ou integração necessária.
- **NÃO** — não foi encontrada/provada implementação adequada na camada.
- **N/A** — camada não é autoridade relevante para a capacidade.
- **DRIFT** — existe implantação em staging, mas em SHA diferente da `main` auditada; não certifica CURRENT.
- **EXT** — depende de evidência, credencial, provider, homologação ou infraestrutura externa real ainda não comprovada.
- **PASS** — testes específicos existem e o CI CURRENT de origem está verde.
- **NO-PROD** — produção real não foi comprovada/aprovada.

Uma linha somente pode evoluir para “comercialmente pronta” quando suas camadas necessárias estiverem integradas, testadas, implantadas, observáveis e comprovadas. Simulação, fake, synthetic, unit test ou contrato interno não substitui integração externa real.

## 2. Matriz congelada — CURRENT

| ID | Capacidade | Domínio/Core | Application | Infra | Persistence | API/HTTP | Auth/RBAC | Tenant/Unit | Web/UI | Tests | CI | Staging | Production | Fase dona do gap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CAP-01 | Core fiscal: documentos, regras tributárias, vertical restaurante, XML, chave, numeração, assinatura, lifecycle/idempotência | OK | OK | OK | OK | PARCIAL | OK | OK | PARCIAL | PASS | PASS | DRIFT | NO-PROD | P1/P5/P7/P10/P11 |
| CAP-02 | Operações fiscais: emitir, consultar, cancelar, inutilizar, reconciliar, archive/capabilities | OK | OK | PARCIAL | OK | PARCIAL | PARCIAL | OK | PARCIAL | PASS | PASS | DRIFT | NO-PROD | P1/P2/P5/P7 |
| CAP-03 | Registry/routing/readiness/configuração de provider fiscal | OK | OK | PARCIAL | OK | PARCIAL | OK | OK | PARCIAL | PASS | PASS | DRIFT | EXT / NO-PROD | P2/P7/P10 |
| CAP-04 | Segredos, certificados, CSC e material criptográfico | OK | OK | PARCIAL | OK | PARCIAL | OK | OK | PARCIAL | PASS | PASS | PARCIAL | EXT / NO-PROD | P2/P6/P7 |
| CAP-05 | Identidade humana, sessão, login, recovery, RBAC e CSRF | OK | OK | OK | OK | OK | OK | OK | OK | PASS | PASS | DRIFT | NO-PROD | P5/P11 |
| CAP-06 | Tenant, unidade, onboarding e Control Plane | OK | OK | OK | OK | OK | OK | OK | PARCIAL | PASS | PASS | DRIFT | NO-PROD | P2/P5/P11 |
| CAP-07 | Portal operacional e superfícies administrativas | OK | OK | PARCIAL | OK | OK | OK | OK | PARCIAL | PASS | PASS | DRIFT | NO-PROD | P1/P2/P5 |
| CAP-08 | Pricing, catálogo comercial, Commercial Release e checkout administrativo | OK | OK | OK | OK | OK | OK | OK | OK | PASS | PASS | DRIFT / provider não comprovado | NO-PROD | P3/P5/P8/P11 |
| CAP-09 | Billing, subscription, entitlements, quotas e usage | OK | PARCIAL | OK | OK | PARCIAL | OK | OK | PARCIAL | PASS | PASS | NÃO CERTIFICADO CURRENT | NO-PROD | P2/P3/P5/P8 |
| CAP-10 | Checkout público e aquisição first-party pré-pagamento | OK | OK | PARCIAL | OK | PARCIAL | PARCIAL | OK | PARCIAL | PASS | PASS | NÃO ATIVO/COMPROVADO | NO-PROD | P3/P5/P8 |
| CAP-11 | Fulfillment, secure claim, provisioning, primeira OWNER, subscription e activation | OK | OK | OK | OK | PARCIAL | OK | OK | PARCIAL | PASS | PASS | PARCIAL / não E2E CURRENT | NO-PROD | P3/P5/P8 |
| CAP-12 | Trial governado | OK | OK | OK | OK | PARCIAL | PARCIAL | OK | PARCIAL | PASS | PASS | NÃO ATIVO/COMPROVADO | NO-PROD | P3/P5/P8 |
| CAP-13 | Adapter Cakto: checkout, webhook, inbox/reconciliation e bridge para estado canônico | OK | OK | PARCIAL | OK | PARCIAL | PARCIAL | OK | PARCIAL | PASS | PASS | NÃO CONFIGURADO/COMPROVADO | NO-PROD | P3/P5/P8 |
| CAP-14 | Worker contínuo, outbox, retries, delivery audit e webhooks assíncronos | OK | OK | PARCIAL | OK | N/A | N/A | OK | N/A | PASS | PASS | PARCIAL — Worker 0/1 | NO-PROD | P4/P5/P9 |
| CAP-15 | Observabilidade, métricas, logs, tracing, health/readiness e edge security | OK | OK | PARCIAL | OK | OK | OK | OK | PARCIAL | PASS | PASS | PARCIAL — tracing desabilitado | NO-PROD | P5/P9/P11 |
| CAP-16 | Homologação fiscal, controlled pilots e autoridade de produção fiscal | OK | OK | PARCIAL | OK | PARCIAL | OK | OK | PARCIAL | PASS | PASS | EXT / não homologado oficialmente | NO-PROD | P7/P10/P11/P12 |
| CAP-17 | Deploy governado, migrations, backup/restore, rollback e promoção de produção | N/A | N/A | OK | OK | OK | N/A | N/A | N/A | PASS | PASS | PARCIAL / DRIFT | NO-PROD | P5/P9/P11/P12 |

## 3. Achados que a matriz congela

### 3.1 Runtime fiscal não está composto no entrypoint oficial

`src/kordena_fiscal/web/app.py` possui o Bridge HTTP provider-neutral e as operações:

- `/v1/archive/references/query`;
- `/v1/cancellations`;
- `/v1/capabilities/query`;
- `/v1/inutilizations`;
- `/v1/issuances`;
- `/v1/queries`;
- `/v1/reconciliations`.

Essas rotas são fail-closed quando `BridgeSecurityBoundary` ou `BridgeRequestExecutor` não estão configurados.

O entrypoint oficial em `src/kordena_fiscal/runtime/api.py` monta `create_app(...)` sem injetar `security`, `executor` ou `portal_operation_executor`. O global `app` injeta somente o delivery de reset/ativação vindo do ambiente.

**Classificação:** implementação existe, mas o caminho fiscal oficial é **IMPLEMENTED_NOT_INTEGRATED**.

### 3.2 Portal tem contrato amplo, porém projeção durável limitada

O frontend `portal/app.js` apresenta superfícies operacionais, configuração e plataforma, incluindo documentos, emissões, reconciliação, capabilities, certificados, providers, usuários, webhooks, integrações, usage, billing, planos, pricing, commercial release e checkout admin.

`src/kordena_fiscal/web/portal_api.py` possui RBAC para essas superfícies e operações fiscais.

Porém `DurableHumanPortalExecutor._DURABLE_SURFACES` em `src/kordena_fiscal/web/portal_runtime.py` contém apenas:

- overview;
- onboarding;
- companies;
- units;
- environments;
- audit;
- settings.

As demais superfícies falham fechadas como projeção durável não configurada. O executor fiscal de operação também depende de `PortalOperationExecutor`, que não é injetado no entrypoint global.

**Classificação:** Portal shell/API/RBAC existem, mas **paridade funcional Web é parcial**.

### 3.3 Comercial canônico existe, mas aquisição/trial/webhook não estão compostos globalmente

O runtime possui:

- canonical commercial persistence;
- fulfillment;
- secure claim;
- provisioning;
- primeira conta OWNER;
- activation;
- durable subscription;
- pricing;
- release;
- Cakto admin opcional;
- trial governado;
- first-party acquisition.

`create_runtime_app(...)` aceita segurança de aquisição, segurança de trial, checkout projector/starter, `cakto_receiver` e demais dependências. Contudo o global `app = create_runtime_app(...)` não injeta essas dependências, exceto activation/password-reset delivery.

**Classificação:** core comercial forte, mas parte do ingresso comercial HTTP permanece **IMPLEMENTED_NOT_INTEGRATED**.

### 3.4 Billing possui autoridade de domínio e estado durável, mas não superfície comercial completa

`src/kordena_fiscal/product/billing.py` define planos, entitlements, quotas, estados de subscription e transições. O estado comercial canônico persiste subscriptions e sincroniza lifecycle através do fulfillment/trial.

As superfícies Portal `usage`, `billing` e `plans` possuem permissões, mas não fazem parte das superfícies duráveis implementadas pelo executor atual.

**Classificação:** domínio/persistência implementados; operação Web/HTTP comercial ainda **PARCIAL**.

### 3.5 Worker contínuo não possui handler factory no entrypoint

`src/kordena_fiscal/runtime/worker_main.py`:

- valida PostgreSQL;
- suporta probe `NFCORE_WORKER_ONESHOT=true`;
- exige `handler_factory` explícita para execução contínua;
- chama `run()` sem factory no `__main__`.

Sem factory, falha com:

`continuous worker requires an explicitly configured handler factory`.

Railway atualmente reporta o serviço Worker com deployment `SUCCESS`, porém **0 running / 1 total**.

**Classificação:** runtime/outbox implementados, composição contínua **PARCIAL**.

### 3.6 Provider fiscal real não está presente

`src/kordena_fiscal/gateway/provider.py` define `FiscalProviderTransport` e declara que implementações HTTP/SOAP de produção vivem fora do Core. O repositório contém boundary, registry, readiness, adapter configurado, synthetic transport e fake gateway, mas não há transporte real de SEFAZ/prefeitura/provider certificado neste CURRENT.

**Classificação:** arquitetura correta; integração fiscal externa real = **EXT / NÃO COMPROVADA**.

### 3.7 External Secret Manager permanece como boundary, não provider concreto

Existem:

- `SecretBackend`;
- `CallableProductionSecretBackend`;
- `ExternalSecretClient`;
- `ExternalFiscalSecretVault`;
- escopo tenant/unit/environment/provider/kind;
- fail-closed para staging/production sem backend production-safe.

Não foi comprovado neste CURRENT um cliente concreto AWS/GCP/Azure/Vault ou equivalente selecionado e integrado.

**Classificação:** boundary e segurança implementados; adapter externo concreto = **PARCIAL/EXT**.

### 3.8 Observabilidade interna existe; exportação operacional real não está ativa

Existem métricas, eventos estruturados, alertas, tracing contracts, correlação/causação e endpoints de health/runtime profile.

No Railway auditado, tracing está desabilitado nos serviços.

**Classificação:** observabilidade interna = **OK**; observabilidade operacional externa = **PARCIAL**.

### 3.9 Staging existe, mas não certifica CURRENT

Baseline desta matriz:

- main: `faf529a0f1852c9107858da730c6103234a30b2f`;
- API staging: `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- Portal staging: `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- Worker staging: `1c34ba001935952f83ec0b065144e0b8311a5650`.

A classificação `DRIFT` nesta matriz registra apenas o fato já observado em T01. O detalhamento/fechamento de drift permanece responsabilidade de **NFV1-P00-T03** e P5.

### 3.10 Produção continua NO-GO

Existe workflow fail-closed de promoção com:

- revisão fonte explícita;
- `PRODUCTION_APPROVED`;
- environment `production`;
- preflight;
- migration;
- deploy;
- smoke;
- rollback em falha;
- evidência persistível.

Isso é **capacidade de promoção**, não prova de infraestrutura produtiva, homologação fiscal, produção ativa ou Go-Live.

**Classificação:** `PRODUCTION_APPROVED=NO`; `COMMERCIAL_LIVE=NO`.

## 4. Evidência canônica por capacidade

### CAP-01 — Core fiscal

Fontes principais:

- `src/kordena_fiscal/tax/engine.py`;
- `src/kordena_fiscal/tax/restaurant.py`;
- `src/kordena_fiscal/documents/`;
- `src/kordena_fiscal/xml/`;
- `src/kordena_fiscal/numbering/manager.py`;
- `src/kordena_fiscal/signing/`;
- `src/kordena_fiscal/lifecycle/`;
- `src/kordena_fiscal/issuance/`.

Testes:

- `tests/tax/test_rule_engine.py`;
- `tests/tax/test_restaurant_classifier.py`;
- `tests/documents/test_canonical_document.py`;
- `tests/xml/test_access_key.py`;
- `tests/xml/test_schema_validation.py`;
- `tests/signing/test_signing_boundary.py`;
- `tests/lifecycle/test_idempotency.py`;
- `tests/lifecycle/test_state_machine.py`;
- `tests/issuance/test_nfce_orchestration.py`;
- `tests/issuance/test_nfe_nfse.py`.

### CAP-02 / CAP-03 — Operações e providers

Fontes:

- `src/kordena_fiscal/application/service.py`;
- `src/kordena_fiscal/gateway/authorization.py`;
- `src/kordena_fiscal/gateway/provider.py`;
- `src/kordena_fiscal/web/app.py`;
- `src/kordena_fiscal/runtime/api.py`;
- `src/kordena_fiscal/reconciliation/`;
- `src/kordena_fiscal/archive/`.

Testes:

- `tests/gateway/test_authorization_gateway.py`;
- `tests/gateway/test_configured_provider_selection.py`;
- `tests/gateway/test_provider_runtime.py`;
- `tests/reconciliation/test_generic_operation_reconciliation.py`;
- `tests/web/test_http_runtime.py`;
- `tests/runtime/test_cl01_production_composition.py`.

### CAP-04 — Segredos/certificados

Fontes:

- `src/kordena_fiscal/security/secrets.py`;
- `src/kordena_fiscal/security/signing.py`;
- `src/kordena_fiscal/vault/external.py`;
- `src/kordena_fiscal/product/tenant_configuration.py`.

Testes:

- `tests/security/test_production_secrets.py`;
- `tests/security/test_signing.py`;
- `tests/vault/test_external_secret_vault.py`;
- `tests/vault/test_secret_resolution.py`.

### CAP-05 / CAP-06 / CAP-07 — Auth, tenant e Portal

Fontes:

- `src/kordena_fiscal/security/human_identity.py`;
- `src/kordena_fiscal/security/human_recovery.py`;
- `src/kordena_fiscal/control_plane/`;
- `src/kordena_fiscal/web/human_auth.py`;
- `src/kordena_fiscal/web/human_recovery.py`;
- `src/kordena_fiscal/web/portal_api.py`;
- `src/kordena_fiscal/web/portal_runtime.py`;
- `portal/app.js`;
- `portal/index.html`.

Testes:

- `tests/security/test_human_identity.py`;
- `tests/security/test_human_recovery.py`;
- `tests/web/test_human_auth_routes.py`;
- `tests/web/test_human_recovery_routes.py`;
- `tests/web/test_portal_api.py`;
- `tests/runtime/test_web10_portal_security.py`;
- `tests/frontend/portal_contract.test.js`;
- `tests/e2e/portal.spec.js`.

### CAP-08 / CAP-09 — Pricing, release, billing

Fontes:

- `src/kordena_fiscal/product/pricing.py`;
- `src/kordena_fiscal/product/commercial_release.py`;
- `src/kordena_fiscal/product/checkout.py`;
- `src/kordena_fiscal/product/billing.py`;
- `src/kordena_fiscal/control_plane/pricing_admin.py`;
- `src/kordena_fiscal/control_plane/commercial_release.py`;
- `src/kordena_fiscal/persistence/pricing_catalog.py`;
- `src/kordena_fiscal/persistence/commercial_release.py`;
- `src/kordena_fiscal/persistence/commercial_fulfillment.py`.

Testes:

- `tests/product/test_pricing.py`;
- `tests/product/test_billing.py`;
- `tests/control_plane/test_pricing_admin.py`;
- `tests/persistence/test_cl08_pricing_catalog.py`;
- `tests/persistence/test_cl09_commercial_release.py`;
- `tests/persistence/test_cl11_commercial_state.py`.

### CAP-10 / CAP-11 / CAP-12 — Aquisição, ativação e trial

Fontes:

- `src/kordena_fiscal/application/commercial_acquisition.py`;
- `src/kordena_fiscal/application/commercial_fulfillment.py`;
- `src/kordena_fiscal/application/commercial_claim.py`;
- `src/kordena_fiscal/application/commercial_activation.py`;
- `src/kordena_fiscal/application/commercial_trial.py`;
- `src/kordena_fiscal/runtime/commercial_provisioning.py`;
- `src/kordena_fiscal/web/commercial_acquisition.py`;
- `src/kordena_fiscal/web/commercial_trial.py`.

Testes:

- `tests/application/test_cl11_first_party_fulfillment.py`;
- `tests/application/test_cl11_commercial_fulfillment_service.py`;
- `tests/application/test_cl11_secure_commercial_claim.py`;
- `tests/runtime/test_cl06_commercial_provisioning.py`;
- `tests/runtime/test_cl11_commercial_activation.py`;
- `tests/runtime/test_cl12_governed_trial.py`;
- `tests/web/test_cl12_governed_trial_http.py`;
- `tests/product/test_commercial_e2e.py`.

### CAP-13 — Cakto

Fontes:

- `src/kordena_fiscal/product/cakto.py`;
- `src/kordena_fiscal/runtime/cakto.py`;
- `src/kordena_fiscal/application/cakto_reconciliation.py`;
- `src/kordena_fiscal/persistence/cakto.py`;
- `src/kordena_fiscal/web/cakto_checkout.py`.

Testes:

- `tests/product/test_web11_cakto.py`;
- `tests/persistence/test_web11_cakto_postgres.py`;
- `tests/application/test_cl11_cakto_reconciliation.py`;
- `tests/runtime/test_web11_cakto_http.py`;
- `tests/runtime/test_cl05_cakto_commercial_composition.py`;
- `tests/web/test_cl10_cakto_checkout_http.py`.

### CAP-14 — Worker/outbox

Fontes:

- `src/kordena_fiscal/application/outbox_worker.py`;
- `src/kordena_fiscal/application/webhook_delivery.py`;
- `src/kordena_fiscal/application/webhook_receiving.py`;
- `src/kordena_fiscal/contingency/`;
- `src/kordena_fiscal/runtime/worker_composition.py`;
- `src/kordena_fiscal/runtime/worker_main.py`.

Testes:

- `tests/application/test_durable_outbox_worker.py`;
- `tests/application/test_signed_webhook_delivery.py`;
- `tests/contingency/test_outbox.py`;
- `tests/runtime/test_cl02_production_worker_runtime.py`.

### CAP-15 — Observabilidade

Fontes:

- `src/kordena_fiscal/observability/events.py`;
- `src/kordena_fiscal/observability/metrics.py`;
- `src/kordena_fiscal/observability/alerts.py`;
- `src/kordena_fiscal/observability/tracing.py`;
- `src/kordena_fiscal/runtime/observability.py`;
- `src/kordena_fiscal/runtime/api.py`;
- `src/kordena_fiscal/runtime/security.py`.

Testes:

- `tests/observability/test_structured_events.py`;
- `tests/observability/test_metrics.py`;
- `tests/observability/test_alerts.py`;
- `tests/observability/test_tracing.py`;
- `tests/runtime/test_web08_observability.py`;
- `tests/runtime/test_web10_edge_security.py`.

### CAP-16 — Homologação/piloto/produção fiscal

Fontes:

- `src/kordena_fiscal/homologation/`;
- `src/kordena_fiscal/runtime/homologation_readiness.py`;
- `src/kordena_fiscal/runtime/controlled_pilots.py`;
- `src/kordena_fiscal/gateway/production_activation.py`.

Testes:

- `tests/homologation/test_v2_15_b1_environment_readiness.py`;
- `tests/homologation/test_v2_15_b2_nfe_matrix.py`;
- `tests/homologation/test_v2_15_b3_nfce_matrix.py`;
- `tests/homologation/test_v2_15_b4_nfse_matrix.py`;
- `tests/homologation/test_v2_15_b5_controlled_pilots.py`;
- `tests/runtime/test_post_web12_external_readiness.py`;
- `tests/runtime/test_post_web12_controlled_pilot_scope.py`;
- `tests/gateway/test_web12_production_activation.py`.

### CAP-17 — Deploy/backup/promoção

Fontes:

- `.github/workflows/ci.yml`;
- `.github/workflows/staging.yml`;
- `.github/workflows/promote-production.yml`;
- `scripts/ci/staging_preflight.sh`;
- `scripts/ci/staging_smoke.sh`;
- `scripts/ci/run_staging_deploy.sh`;
- `scripts/ci/run_production_promotion.sh`.

O CI CURRENT executa build de imagens, non-root, vulnerability policy, SBOM, PostgreSQL backup/restore rehearsal e readiness contra banco restaurado.

## 5. Autoridades que NÃO devem ser reconstruídas

A matriz congela como autoridades reutilizáveis:

- documentos/lifecycle/idempotência fiscal;
- engine tributária;
- XML/chave/assinatura;
- Postgres/migrations;
- HumanIdentity/RBAC/session/recovery;
- tenant/unit/Control Plane;
- provider registry/readiness/bindings;
- secret/vault contracts;
- pricing/catalog;
- commercial release;
- checkout provider-neutral;
- canonical commercial purchase/subscription state;
- fulfillment/claim/provisioning/activation/trial;
- Cakto como adapter;
- outbox/retry/webhook contracts;
- observability contracts;
- homologation/pilot/production-activation governance;
- CI/Docker/backup-restore/promotion contracts.

As fases P1-P11 devem **compor, completar ou fornecer adapters reais** sobre essas autoridades. Não criar versões paralelas.

## 6. Mapa Current -> Target por fase

| Fase | Gap congelado pela matriz | Target |
|---|---|---|
| P1 | CAP-01/02/07: Bridge fiscal e PortalOperationExecutor sem composition root oficial | runtime fiscal oficial composto e certificado internamente |
| P2 | CAP-04/06/07/09: superfícies Web/admin não duráveis ou incompletas | paridade comercial/operacional do Portal |
| P3 | CAP-08/09/10/11/12/13: aquisição/trial/webhook/comercial não compostos globalmente | runtime comercial canônico integrado |
| P4 | CAP-14: Worker sem handler factory real | Worker contínuo composto e certificado |
| P5 | todas as capacidades: staging em SHA divergente | API/Portal/Worker no mesmo exact SHA + E2E real |
| P6 | CAP-04: boundary external secret sem client concreto | Secret Manager real certificado |
| P7 | CAP-02/03/04/16: sem transporte fiscal real | provider fiscal real pronto para homologação |
| P8 | CAP-08-13: canal comercial real não validado | compra/lifecycle/reconciliation reais |
| P9 | CAP-14/15/17: observabilidade/backup/operação incompletos | readiness operacional certificado |
| P10 | CAP-16: sem evidência oficial/piloto | launch matrix homologada e piloto governado |
| P11 | CAP-15/16/17: produção não provisionada/provada | infraestrutura produtiva pronta para promoção |
| P12 | matriz A-E ainda não certificada | Go/No-Go humano final |

## 7. Critério de congelamento da T02

A matriz é considerada congelada para execução quando:

1. todas as famílias relevantes do CURRENT possuem linha própria;
2. nenhuma linha confunde código com integração, deploy, homologação ou produção;
3. cada gap tem fase dona no cronograma;
4. staging/prod são classificados por evidência atual, não por intenção;
5. autoridades existentes estão listadas para impedir reconstrução paralela;
6. futuras descobertas relevantes devem atualizar esta matriz ou receber nova tarefa formal antes de execução.

Esta matriz **não fecha T03** e não certifica staging ou produção.
