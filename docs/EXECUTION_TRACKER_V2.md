# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-10 — Product Contract Packs**  
Próxima fase: **V2-11 — Control Plane independente — PENDENTE**

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
| V2-08 | Events/Webhooks/Inbox/Outbox | **CONCLUÍDO** | PR #9 Draft; gate `bc77ee4cf2b7151d06c09cf32ca9168363ece1c7`; run `34666753555`; 67 source files; Pytest 337 PASS; CI restaurado |
| V2-09 | Modularização de verticais | **CONCLUÍDO** | PR #10 Draft; gate `88071fd557199ffd6848312ea5559b0cba415ee1`; run `34668430831`; 71 source files; Pytest 346 PASS; CI restaurado |
| V2-10 | Contract Packs Kordena/Iron/Vendedor/CampaIA | **CONCLUÍDO** | PR #11 Draft; gate funcional `44941004207d2991fccfd0f28b402bc3cda9357f`; fechamento `345652ecbfc18c8bd3511cf5b9083ba0dbc259cb`; run `34707976358`; 78 source files; Pytest 397 PASS; CI restaurado |
| V2-11 | Control Plane independente | PENDENTE | próxima fase; depende core operacional multiproduto certificado |
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

## Fechamento V2-09 — Modularização de verticais

- `kordena_fiscal.verticals` host-neutral;
- restaurante explícito com regras preservadas;
- `service`, `fitness` e `saas` neutros;
- registry explícito/fail-closed e extensão sem fork;
- gate `88071fd557199ffd6848312ea5559b0cba415ee1`, run `34668430831`, 71 source files, 346 PASS.

## Fechamento V2-10 — Product Contract Packs

### Foundation

- descriptors versionados de pack/use case;
- registry explícito por `pack_id` e `host_namespace`;
- validação fail-closed de namespace, operation kind e vertical/capability;
- nenhum pack concede readiness.

Gate `3af9a6ded0303ca7d591bbfa69b771c4571a9cc0`, run `34672479434`: 73 source files, **354 PASS**.

### Kordena

- `fm.kordena`;
- SALE + NFC-e/NF-e;
- vertical `restaurant` explícita, sem duplicar regra tributária.

Gate `6fd934c024736f3d5e23aa4d1172d60caa49fb7c`, run `34672769666`: 74 source files, **362 PASS**.

### Iron Fit

- `fm.iron`;
- MEMBERSHIP / RECURRING_CHARGE / SERVICE + NFS-e;
- vertical `fitness` com capability por caso.

Gate `3c3f18dd77663e021424b9f32c9f1a849b001c84`, run `34672919212`: 75 source files, **371 PASS**.

### Vendedor IA

- `fm.vendedor-ia`;
- SALE + NFC-e/NF-e;
- sem vertical setorial e sem inferência de pagamento/settlement.

Gate `7be9453e6757784e38e77e83928bc0f828007f90`, run `34674065346`: 76 source files, **380 PASS**.

### CampaIA

- `fm.campaia`;
- SERVICE + NFS-e / vertical `service`;
- SAAS_BILLING + NFS-e / vertical `saas`;
- sem inferência de pagamento, tributo, jurisdição ou readiness.

Gate `1e0558773f7a39b6e5b4156f874fd201d4efdf3c`, run `34707632430`: 77 source files, **389 PASS**.

### Cross-product certification

- catálogo governado com os quatro packs e quatro hosts únicos;
- matriz derivada com **9 casos de uso**;
- cada pack aceita seu próprio host e rejeita os outros três;
- todas as verticais exigidas validam no registry governado;
- todos os eventos inbound existem no AsyncAPI público;
- nenhum outbound privado é inventado;
- nenhum pack ou use case contém autoridade de readiness/production approval;
- auditoria AST confirma que os módulos individuais de pack não importam packs de outros produtos nem domínios privados de SaaS.

Primeira tentativa `34707799695`: falha somente Ruff/E501 em três linhas de `catalog.py`; correção de formatação sem mudança semântica.

Gate funcional definitivo:
- SHA `44941004207d2991fccfd0f28b402bc3cda9357f`;
- run `34707834828` — **SUCCESS**;
- Install PASS;
- Ruff PASS;
- Mypy strict PASS — **78 source files**;
- Pytest **397 PASS em 1.16s**;
- baseline V2-09 346 -> V2-10 397: **+51 testes líquidos**.

### Certificação final de fechamento

Após documentação e tracker de encerramento, a matriz completa foi executada novamente:

- SHA `345652ecbfc18c8bd3511cf5b9083ba0dbc259cb`;
- run `34707976358` — **SUCCESS**;
- Install PASS;
- Ruff PASS;
- Mypy strict PASS — **78 source files**;
- Pytest **397 PASS em 1.47s**;
- CI restaurado para `workflow_dispatch` no commit `2d651bd380807cad6ad30757ad96f6c6365af709`.

### Auditoria de diff funcional contra V2-09

Compare V2-09 `5d3e06be52a75b60b36640ee8a5d1869b11de928` -> checkpoint pós-gate/restauração `fcd3fc69086c46ede94079a48da90a5ec0764572`:

- **48 commits à frente, 0 atrás**;
- **16 arquivos líquidos alterados**;
- escopo líquido restrito a documentação/snapshot V2-10, `contract_packs` e testes de contract packs;
- CI líquido restaurado ao estado governado;
- nenhum contrato OpenAPI/AsyncAPI/JSON Schema, migration, persistência, segurança S2S, webhook, provider fiscal, infraestrutura, segredo real, deploy ou cutover foi alterado.

### Riscos residuais / limites

- packs não equivalem a homologação fiscal real;
- readiness por documento/jurisdição continua sob Capability & Readiness;
- adapters reais, signer/vault e providers pertencem às fases posteriores;
- Control Plane e wiring operacional são escopo V2-11;
- NFS-e não recebe permissões genéricas apenas por pertencer a um produto.

## Governança

- PR #11 permanece Draft e sem merge;
- nenhum deploy, promoção, homologação externa ou cutover foi realizado;
- V2-10 está **CONCLUÍDA E CERTIFICADA**;
- V2-11 está formalmente liberada para ser iniciada em branch e PR Draft próprios.

## Próxima decisão

**V2-11 — Control Plane independente: iniciar somente com snapshot pré-fase, nova branch stacked sobre o fechamento V2-10 e nova PR Draft, preservando os mesmos gates de governança.**
