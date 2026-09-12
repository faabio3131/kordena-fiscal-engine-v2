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
| V2-10 | Contract Packs Kordena/Iron/Vendedor/CampaIA | **EM EXECUÇÃO** | PR #11 Draft; Foundation `3af9a6d...` / run `34672479434` / 354 PASS; Kordena `6fd934c...` / run `34672769666` / 362 PASS; CI restaurado |
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

- superfície host-neutral `kordena_fiscal.verticals`;
- restaurante como módulo explícito com classificador/regra preservados;
- `service`, `fitness` e `saas` neutros, sem import de restaurante;
- registry explícito/fail-closed e extensão futura sem fork;
- gate `88071fd557199ffd6848312ea5559b0cba415ee1`, run `34668430831`, 71 source files, 346 PASS;
- fechamento documental também verde no run `34668559367`;
- CI restaurado para `workflow_dispatch`.

## V2-10 — Product Contract Packs

### Bootstrap

- branch `v2/product-contract-packs` criada a partir do head final certificado da V2-09: `5d3e06be52a75b60b36640ee8a5d1869b11de928`;
- snapshot pré-fase salvo em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_10.md`;
- plano em `docs/V2_10_PRODUCT_CONTRACT_PACKS.md`;
- PR #11 criada em Draft, stacked sobre `v2/vertical-modularization`.

### Bloco 1 — Foundation — CONCLUÍDO/CERTIFICADO

- criada a superfície `kordena_fiscal.contract_packs`;
- `ProductUseCaseDescriptor` declara operation kinds, document kinds, ações fiscais, vertical/capabilities e eventos;
- `ProductContractPackDescriptor` valida `host_namespace` exato e operation kind por caso de uso;
- `ProductContractPackRegistry` impede colisão de pack id e host namespace e resolve fail-closed;
- contrato de vertical é validado explicitamente contra `VerticalModuleRegistry` V2-09;
- nenhum pack/foundation promove readiness ou substitui a Capability & Readiness API.

Gate Foundation:
- SHA `3af9a6ded0303ca7d591bbfa69b771c4571a9cc0`;
- run `34672479434` — **SUCCESS**;
- Install/Ruff/Mypy PASS; **73 source files**;
- Pytest **354 PASS em 1.45s**;
- baseline V2-09 346; incremento **+8**;
- CI restaurado no commit `24b54f47fad9dac11b900194d63f0803b8dfda30`.

### Bloco 2 — KordenaFiscalContractPack — CONCLUÍDO/CERTIFICADO

- namespace canônico obrigatório `fm.kordena`, conforme V2-02;
- classe concreta `KordenaFiscalContractPack` e singleton exportado;
- `restaurant-pos-sale`: SALE + NFC-e;
- `restaurant-invoice-sale`: SALE + NF-e;
- ambos exigem módulo `restaurant` e capabilities `tax.restaurant.supply-classification` + `tax.restaurant.base-adjustments`;
- nenhuma regra tributária foi copiada ou alterada;
- nenhum readiness/homologação é concedido pelo pack;
- eventos inbound são validados contra o AsyncAPI público v1.1.0;
- fixture sintética usa apenas dados fictícios;
- cross-host `fm.iron` contra Kordena falha fechado;
- descriptor não expõe namespaces dos demais produtos.

Gate Kordena:
- SHA `6fd934c024736f3d5e23aa4d1172d60caa49fb7c`;
- run `34672769666` — **SUCCESS**;
- Install PASS;
- Ruff PASS;
- Mypy strict PASS — **74 source files**;
- Pytest **362 PASS em 1.16s**;
- checkpoint Foundation 354; incremento Kordena **+8**;
- compare `532275595a5055a008eb69c46fa19400a3f790c2` -> `6fd934c...`: **4 commits à frente, 0 atrás**;
- CI restaurado a `workflow_dispatch` no commit `6a919ebdcab17b5f7b3215aa8d032abc2411afb0`.

## Governança

- PR #11 permanece Draft e sem merge;
- nenhum deploy, promoção, homologação externa ou cutover foi realizado;
- CI voltou a `workflow_dispatch` após o gate Kordena;
- V2-10 permanece **EM EXECUÇÃO** até concluir Iron Fit, Vendedor IA, CampaIA e certificação cross-product.

## Próxima decisão

**Próximo bloco: `IronFiscalContractPack` + fixtures sintéticas e contract tests Iron Fit, usando `fm.iron`, vertical `fitness` e NFS-e como família contratual sem promover readiness.**
