# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-10 — Product Contract Packs**  
Fase atual: **V2-11 — Control Plane independente — EM EXECUÇÃO**

> O estado imediatamente anterior ao início do V2-11 foi preservado em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_11.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`.

Nenhum bloco é `CONCLUÍDO` sem branch, SHA, PR Draft, CI, testes/gates, auditoria de diff e riscos residuais documentados. Nenhum merge, deploy, promoção ou cutover é automático.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-00 | Clone técnico + equivalência | **CONCLUÍDO** | PR #1 Draft; gate `9da776e353b31d03a8453a83c6e61a736e6ed00b`; run `34633874565`; Pytest 215 PASS |
| V2-01 | Identidade FM + neutralização de branding | **CONCLUÍDO** | PR #2 Draft; gate `ac6ad42eeacca2a84675e7e57e04b18414cadf36`; run `34635131000`; Pytest 215 PASS |
| V2-02 | Host namespace + fiscal account binding | **CONCLUÍDO** | PR #3 Draft; gate `4fa8a2a8c74db65622099cd7dca43d2e8d19aea3`; run `34637445978`; Pytest 239 PASS |
| V2-03 | Fiscal Operation Contract genérico | **CONCLUÍDO** | PR #4 Draft; gate `598a2ec83aecd27a5427f3e1e401532e8be2696a`; run `34645939363`; Pytest 262 PASS |
| V2-04 | FM Fiscal Bridge — OpenAPI/JSON Schema/AsyncAPI | **CONCLUÍDO** | PR #5 Draft; gate `86689b3d3d7d47740b56bcc22594aa8c8e0b08c7`; run `34655024269`; Pytest 269 PASS |
| V2-05 | Auth S2S + workload identity + webhook security | **CONCLUÍDO** | PR #6 Draft; gate `196928d1b0cfe896df0c4741839ce72258f8f4d4`; run `34656535435`; 48 source files; Pytest 290 PASS |
| V2-06 | Capability & Readiness API | **CONCLUÍDO** | PR #7 Draft; gate `e6c7b2b9e507116ef4919812153f8e54f84173f3`; run `34659021574`; 49 source files; Pytest 305 PASS |
| V2-07 | Application service + persistência durável | **CONCLUÍDO** | PR #8 Draft; gate `999ba84b9c25988441867820bfe8af0571269548`; run `34659892798`; 59 source files; Pytest 309 PASS; CI restaurado |
| V2-08 | Events/Webhooks/Inbox/Outbox | **CONCLUÍDO** | PR #9 Draft; gate `bc77ee4cf2b7151d06c09cf32ca9168363ece1c7`; run `34666753555`; 67 source files; Pytest 337 PASS; CI restaurado |
| V2-09 | Modularização de verticais | **CONCLUÍDO** | PR #10 Draft; gate `88071fd557199ffd6848312ea5559b0cba415ee1`; run `34668430831`; 71 source files; Pytest 346 PASS; CI restaurado |
| V2-10 | Contract Packs Kordena/Iron/Vendedor/CampaIA | **CONCLUÍDO** | PR #11 Draft; fechamento `345652ecbfc18c8bd3511cf5b9083ba0dbc259cb`; run `34707976358`; 78 source files; Pytest 397 PASS; CI restaurado |
| V2-11 | Control Plane independente | **EM EXECUÇÃO** | PR #12 Draft; Block 1 `eaeca06739f756d31085617c1eecabebcc846dd7` / `34708472525` / 406 PASS; Block 2 `fb485d180a2fba689c0465b61fbec206c02c3cf4` / `34709564947` / 83 source / 416 PASS; CI restaurado |
| V2-12 | Gateway/Signer/Vault production adapters | PENDENTE | depende V2-11 |
| V2-13 | Observabilidade + Compliance Operations | PENDENTE | depende V2-07/V2-12 |
| V2-14 | Hardening sistêmico | PENDENTE | regressão/carga/falhas/segurança |
| V2-15 | Homologação + pilotos controlados | PENDENTE | depende V2-14 |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | Kordena aguarda V1 Web Premium; demais aguardam V2 universal certificado |
| V2-17 | Convergência/cutover + arquivamento original | PENDENTE | somente após equivalência e integrações certificadas |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## Fechamento V2-08 — resumo preservado

- Durable Inbox: gate `f467d0dafa70e3c0debd3aacccbb183c954c5b35`, run `34662707064`, 316 PASS.
- Durable Outbox Worker: gate `56678f730f2e7c3c235530887612a7ee71b5efc8`, run `34663828770`, 322 PASS.
- Signed Webhook Delivery: gate `8321106338aca262a76fe2bdfa76665bdcc57950`, run `34664214273`, 331 PASS.
- audit + ordering + duplicate delivery: gate `bc77ee4cf2b7151d06c09cf32ca9168363ece1c7`, run `34666753555`, 337 PASS.

## Fechamento V2-09 — resumo preservado

- `kordena_fiscal.verticals` host-neutral;
- restaurante explícito com regras preservadas;
- `service`, `fitness` e `saas` neutros;
- registry explícito/fail-closed e extensão sem fork;
- gate `88071fd557199ffd6848312ea5559b0cba415ee1`, run `34668430831`, 71 source files, 346 PASS.

## Fechamento V2-10 — resumo preservado

- Foundation + Product Contract Packs Kordena, Iron Fit, Vendedor IA e CampaIA;
- catálogo governado com quatro hosts e matriz derivada de 9 casos de uso;
- isolamento cross-host/imports certificado;
- gate funcional cross-product `44941004207d2991fccfd0f28b402bc3cda9357f`, run `34707834828`, 397 PASS;
- regressão final de fechamento `345652ecbfc18c8bd3511cf5b9083ba0dbc259cb`, run `34707976358`, 397 PASS;
- diff final documental V2-09 -> V2-10: 56 commits à frente, 0 atrás, 16 arquivos líquidos;
- PR #11 permaneceu Draft e sem merge; CI restaurado.

## V2-11 — Control Plane independente

### Bootstrap — CONCLUÍDO

- branch `v2/control-plane` criada a partir do fechamento V2-10 `156a945cc8e2708eba21551b128ac3d673bb0cdc`;
- snapshot pré-fase em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_11.md`;
- plano da fase em `docs/V2_11_CONTROL_PLANE.md`;
- PR #12 Draft stacked sobre `v2/product-contract-packs`.

### Bloco 1 — Foundation administrativa — CONCLUÍDO/CERTIFICADO

- `kordena_fiscal.control_plane` host-neutral;
- `AdminPrincipal` + RBAC explícito e tenant/global scope fail-closed;
- `FiscalOrganization` e `FiscalUnitRegistration` para onboarding;
- environments explicitamente habilitados, default somente HOMOLOGATION;
- `SecretReference` armazena apenas referências opacas `ref:...`, nunca segredo bruto;
- `ControlPlaneAuditEvent` sem payload livre e audit trail para mutações;
- serviço in-memory certifica invariantes antes da persistência durável;
- duplicate org/unit e secret binding conflitante falham fechado;
- audit read é permissionado e isolado por tenant.

Primeiro CI `34708348014`: falha de coleta por basename duplicado de teste. Segundo CI `34708391513`: 405 PASS, 1 FAIL por fixture que misturava duas invariantes RBAC. Fixture corrigido sem mudança semântica.

Gate definitivo:
- SHA `eaeca06739f756d31085617c1eecabebcc846dd7`;
- run `34708472525` — **SUCCESS**;
- Install/Ruff PASS;
- Mypy strict PASS — **81 source files**;
- Pytest **406 PASS em 1.46s**;
- baseline V2-10 397; incremento **+9**;
- CI restaurado em `71823391c456b120ae5a4cf35d599caea0df353d`.

### Bloco 2 — Persistência durável + perfis fiscais — CONCLUÍDO/CERTIFICADO

- migration V4 `v2_11_control_plane_durable_state`;
- `SqliteControlPlaneStore` integrado ao `SqliteFiscalUnitOfWork`;
- onboarding, environments, secret references, perfis e audit trail duráveis;
- `DurableControlPlaneService` com RBAC e atomicidade no UoW comum;
- reutilização do `FiscalProfile` já certificado, sem segunda fonte de verdade;
- vigências sobrepostas na mesma partição falham fechado; intervalos adjacentes são aceitos;
- resolução de perfil efetivo falha fechado se persistência estiver ambígua;
- restart safety para organização/unidade/referências/perfil/auditoria;
- schema de secret references certificado sem campos de segredo/material;
- caminhos históricos V2-07/V2-08 -> V2-11 testados.

Tentativas intermediárias localizaram apenas: Ruff/import order, ciclo de import provocado por export eager e expectativas legadas de migrations V1-V3; todos foram corrigidos sem regressão semântica. A última falha antes do gate foi restrita a duas asserções que presumiam ordem de eventos com timestamp sintético idêntico.

Gate definitivo:
- SHA `fb485d180a2fba689c0465b61fbec206c02c3cf4`;
- run `34709564947` — **SUCCESS**;
- Install PASS;
- Ruff PASS;
- Mypy strict PASS — **83 source files**;
- Pytest **416 PASS em 1.67s**;
- baseline Block 1 406; incremento líquido **+10**;
- CI restaurado em `7c3177dfe7f95cd7cf472c88d16ae8ac40d605af`.

## Governança

- PR #12 permanece Draft e sem merge;
- nenhum deploy, promoção, homologação externa ou cutover foi realizado;
- V2-11 permanece **EM EXECUÇÃO**.

## Próxima decisão

**Bloco 3 obrigatório: Capability/Readiness governance, associando configuração administrativa à autoridade certificada de Capability & Readiness sem criar readiness paralelo ou conceder `PRODUCTION_APPROVED`.**
