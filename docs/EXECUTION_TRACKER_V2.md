# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-09 — Modularização de verticais**  
Fase atual: **V2-10 — Product Contract Packs — EM EXECUÇÃO**

> O estado imediatamente anterior ao início do V2-10 foi preservado em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_10.md`.

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
| V2-08 | Events/Webhooks/Inbox/Outbox | **CONCLUÍDO** | PR #9 Draft; gate final `bc77ee4cf2b7151d06c09cf32ca9168363ece1c7`; run `34666753555`; 67 source files; Pytest 337 PASS; CI restaurado |
| V2-09 | Modularização de verticais | **CONCLUÍDO** | PR #10 Draft; gate `88071fd557199ffd6848312ea5559b0cba415ee1`; run `34668430831`; 71 source files; Pytest 346 PASS; CI restaurado |
| V2-10 | Contract Packs Kordena/Iron/Vendedor/CampaIA | **EM EXECUÇÃO** | branch `v2/product-contract-packs`; snapshot pré-fase preservado; PR Draft pendente de bootstrap |
| V2-11 | Control Plane independente | PENDENTE | depende core operacional |
| V2-12 | Gateway/Signer/Vault production adapters | PENDENTE | depende V2-11 |
| V2-13 | Observabilidade + Compliance Operations | PENDENTE | depende V2-07/V2-12 |
| V2-14 | Hardening sistêmico | PENDENTE | regressão/carga/falhas/segurança |
| V2-15 | Homologação + pilotos controlados | PENDENTE | depende V2-14 |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | Kordena aguarda V1 Web Premium; demais aguardam V2 universal certificado |
| V2-17 | Convergência/cutover + arquivamento original | PENDENTE | somente após equivalência e integrações certificadas |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## Fechamento V2-08 — resumo preservado

- Durable Inbox com deduplicação, lifecycle versionado e migration SQLite v2: gate `f467d0dafa70e3c0debd3aacccbb183c954c5b35`, run `34662707064`, 316 PASS.
- Durable Outbox Worker com claim/lease, retry/backoff, restart, crash recovery, DLQ e fencing: gate `56678f730f2e7c3c235530887612a7ee71b5efc8`, run `34663828770`, 322 PASS.
- Signed Webhook Delivery com HMAC V2-05, rotação e compatibilidade AsyncAPI: gate `8321106338aca262a76fe2bdfa76665bdcc57950`, run `34664214273`, 331 PASS.
- Fechamento funcional com audit, ordering e duplicate delivery idempotente: gate `bc77ee4cf2b7151d06c09cf32ca9168363ece1c7`, run `34666753555`, 337 PASS.
- CI V2-08 restaurado para `workflow_dispatch` no commit `10953d0f413ba8a4f06cc97fa924c565cd2f0b29`.

## Fechamento V2-09 — Modularização de verticais

### Arquitetura

- criada a superfície host-neutral `kordena_fiscal.verticals`;
- `VerticalModuleDescriptor` define identidade, versão e capabilities imutáveis;
- `VerticalModuleRegistry` exige registro e resolução explícitos e falha fechado para módulo/capability ausente;
- nenhuma inferência silenciosa de vertical foi adicionada ao Core.

### Restaurante

- implementação normativa migrada para `kordena_fiscal.verticals.restaurant`;
- `RestaurantVerticalModule` declara `tax.restaurant.supply-classification` e `tax.restaurant.base-adjustments`;
- `kordena_fiscal.tax.restaurant` permanece como shim de compatibilidade;
- a suíte legada do classificador de restaurante permaneceu integralmente verde;
- nenhuma regra tributária de restaurante foi alterada.

### Serviço / Fitness / SaaS

- `service` declara `operation.service`;
- `fitness` declara `operation.service`, `operation.membership` e `operation.recurring`;
- `saas` declara `operation.service`, `operation.subscription` e `operation.recurring`;
- esses módulos não importam o classificador de restaurante e não conferem readiness fiscal por si próprios;
- teste em processo Python isolado comprova que o import neutro não carrega módulos de restaurante.

### Extensibilidade

- uma vertical sintética `future-commerce` é registrada via contrato/registry, sem alteração do Core;
- isso prova extensão futura por vertical sem fork do motor fiscal.

### Gate V2-09

- SHA funcional: `88071fd557199ffd6848312ea5559b0cba415ee1`;
- Actions run: `34668430831` — **SUCCESS**;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **71 source files**;
- Pytest: **346 PASS em 1.35s**;
- baseline V2-08: 337 testes; incremento líquido V2-09: **+9**.

O fechamento documental/tracker em `9a10d1863868d92462efaecddf5d36792240798e` também passou integralmente no run `34668559367`: Install PASS, Ruff PASS, Mypy strict PASS em 71 source files e **346 PASS em 1.41s**.

### Auditoria de diff

Compare V2-08 `cc30ec3bddd2f61595c0d869f710e22d83e24743` -> gate V2-09 `88071fd557199ffd6848312ea5559b0cba415ee1`:

- **9 commits à frente, 0 atrás** no gate funcional;
- alterações limitadas a CI temporário, documentação/snapshot da fase, nova superfície `verticals`, shim de compatibilidade e testes;
- contratos OpenAPI/AsyncAPI/JSON Schema não foram alterados;
- nenhuma migration/persistência, segurança, webhook, provider fiscal, infraestrutura, segredo real, deploy ou cutover foi introduzido.

### Riscos residuais / limites

- composição operacional do registry ainda pertence às camadas superiores;
- service/fitness/SaaS ainda não são Product Contract Packs — isso é escopo V2-10;
- o shim legado de restaurante permanece intencionalmente por compatibilidade;
- mappings específicos de Kordena, Iron Fit, Vendedor IA e CampaIA não entram no Core nesta fase;
- não houve homologação externa nem produção.

## Início V2-10 — Product Contract Packs

- branch criada a partir do head final certificado da V2-09: `5d3e06be52a75b60b36640ee8a5d1869b11de928`;
- snapshot pré-fase salvo em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_10.md`;
- plano de execução da fase em `docs/V2_10_PRODUCT_CONTRACT_PACKS.md`;
- escopo vinculante: packs Kordena, Iron Fit, Vendedor IA e CampaIA, fixtures sintéticas, contract tests e matriz de documentos/eventos/capabilities;
- a fase não concede readiness/homologação e não importa repositórios privados dos SaaS.

## Governança

- PR #10 da V2-09 permanece Draft e sem merge;
- nenhum deploy, promoção ou cutover foi realizado;
- CI está em `workflow_dispatch`;
- V2-10 será executada em PR Draft própria e stacked sobre `v2/vertical-modularization`.

## Próxima decisão

**V2-10 INICIADA. Próximo bloco: Foundation do Product Contract Pack + registry explícito e fail-closed.**
