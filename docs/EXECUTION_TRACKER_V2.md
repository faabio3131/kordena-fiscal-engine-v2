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
| V2-10 | Contract Packs Kordena/Iron/Vendedor/CampaIA | **EM EXECUÇÃO** | PR #11 Draft; Foundation 354; Kordena 362; Iron 371; Vendedor IA 380; CampaIA `1e05587...` / run `34707632430` / 389 PASS; cross-product pendente |
| V2-11 | Control Plane independente | PENDENTE | depende core operacional |
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
- CI restaurado para `workflow_dispatch`.

## Fechamento V2-09 — Modularização de verticais

- `kordena_fiscal.verticals` host-neutral;
- restaurante explícito com regras preservadas;
- `service`, `fitness` e `saas` neutros;
- registry explícito/fail-closed e extensão sem fork;
- gate `88071fd557199ffd6848312ea5559b0cba415ee1`, run `34668430831`, 71 source files, 346 PASS;
- fechamento documental também verde no run `34668559367`.

## V2-10 — Product Contract Packs

### Bootstrap

- branch `v2/product-contract-packs` criada a partir de V2-09 `5d3e06be52a75b60b36640ee8a5d1869b11de928`;
- snapshot pré-fase em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_10.md`;
- plano em `docs/V2_10_PRODUCT_CONTRACT_PACKS.md`;
- PR #11 Draft, stacked sobre `v2/vertical-modularization`.

### Bloco 1 — Foundation — CONCLUÍDO/CERTIFICADO

Gate `3af9a6ded0303ca7d591bbfa69b771c4571a9cc0`, run `34672479434`: Install/Ruff/Mypy PASS, 73 source files, **354 PASS**. Registry e descriptors fail-closed; nenhuma promoção de readiness.

### Bloco 2 — KordenaFiscalContractPack — CONCLUÍDO/CERTIFICADO

`fm.kordena`; SALE + NFC-e/NF-e; vertical `restaurant` explícita; nenhuma regra tributária copiada. Gate `6fd934c024736f3d5e23aa4d1172d60caa49fb7c`, run `34672769666`: 74 source files, **362 PASS**.

### Bloco 3 — IronFiscalContractPack — CONCLUÍDO/CERTIFICADO

`fm.iron`; MEMBERSHIP/RECURRING_CHARGE/SERVICE + NFS-e; vertical `fitness` com capability por caso; sem overclaim de NFS-e. Gate `3c3f18dd77663e021424b9f32c9f1a849b001c84`, run `34672919212`: 75 source files, **371 PASS**.

### Bloco 4 — SalesFiscalContractPack / Vendedor IA — CONCLUÍDO/CERTIFICADO

`fm.vendedor-ia`; SALE + NFC-e/NF-e; sem vertical setorial; sem inferência de pagamento/settlement; cross-host fail-closed. Gate `7be9453e6757784e38e77e83928bc0f828007f90`, run `34674065346`: 76 source files, **380 PASS**.

### Bloco 5 — CampaiaFiscalContractPack — CONCLUÍDO/CERTIFICADO

- namespace obrigatório `fm.campaia`;
- `service-billing`: SERVICE + NFS-e + `service/operation.service`;
- `saas-billing`: SAAS_BILLING + NFS-e + `saas/operation.service` + `saas/operation.subscription`;
- nenhum modelo privado do CampaIA importado;
- nenhum readiness/homologação concedido;
- nenhuma inferência de pagamento, settlement, tributo municipal ou jurisdição;
- `SUBSCRIPTION` não é aceito silenciosamente no use case SAAS_BILLING;
- ausência de `service` ou `saas` falha fechado;
- cross-host com `fm.vendedor-ia` falha fechado;
- eventos inbound validados contra AsyncAPI público; sem outbound privado.

Gate CampaIA:
- SHA `1e0558773f7a39b6e5b4156f874fd201d4efdf3c`;
- run `34707632430` — **SUCCESS**;
- Install PASS;
- Ruff PASS;
- Mypy strict PASS — **77 source files**;
- Pytest **389 PASS em 2.14s**;
- checkpoint Vendedor IA 380; incremento **+9**;
- compare `def50ae4d8914ec88821309a5a31990cfdc0b879` -> `1e055877...`: **4 commits à frente, 0 atrás**;
- CI restaurado no commit `e4918e8471a3e710daab897d32ffe000bcba5212`.

## Governança

- PR #11 permanece Draft e sem merge;
- nenhum deploy, promoção, homologação externa ou cutover foi realizado;
- CI está novamente em `workflow_dispatch`;
- todos os quatro Product Contract Packs estão certificados;
- V2-10 permanece **EM EXECUÇÃO** somente até a certificação cross-product consolidada e auditoria final do diff.

## Próxima decisão

**Próximo bloco obrigatório do cronograma: Cross-product certification — matriz consolidada, isolamento entre os quatro hosts, regressão completa e auditoria final do diff contra V2-09.**
