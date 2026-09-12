# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-08 — Events/Webhooks/Inbox/Outbox**  
Fase atual: **V2-09 — Modularização de verticais — LIBERADA / PENDENTE**

> O estado imediatamente anterior ao início do V2-08 foi preservado em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_08.md`.

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
| V2-06 | Capability & Readiness API | **CONCLUÍDO** | PR #7 Draft; gate `e6c7b2b9e507116ef4919812153f8e54f84173f3`; run `34659021574` SUCCESS; 49 source files; Pytest 305 PASS |
| V2-07 | Application service + persistência durável | **CONCLUÍDO** | PR #8 Draft; gate `999ba84b9c25988441867820bfe8af0571269548`; run `34659892798` SUCCESS; 59 source files; Pytest 309 PASS; CI restaurado |
| V2-08 | Events/Webhooks/Inbox/Outbox | **CONCLUÍDO** | PR #9 Draft; gate final `bc77ee4cf2b7151d06c09cf32ca9168363ece1c7`; run `34666753555` SUCCESS; 67 source files; Pytest 337 PASS |
| V2-09 | Modularização de verticais | PENDENTE | **LIBERADA** após estabilização/certificação dos contratos core V2-08 |
| V2-10 | Contract Packs Kordena/Iron/Vendedor/CampaIA | PENDENTE | depende V2-03..V2-09 |
| V2-11 | Control Plane independente | PENDENTE | depende core operacional |
| V2-12 | Gateway/Signer/Vault production adapters | PENDENTE | depende V2-11 |
| V2-13 | Observabilidade + Compliance Operations | PENDENTE | depende V2-07/V2-12 |
| V2-14 | Hardening sistêmico | PENDENTE | regressão/carga/falhas/segurança |
| V2-15 | Homologação + pilotos controlados | PENDENTE | depende V2-14 |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | Kordena aguarda V1 Web Premium; demais aguardam V2 universal certificado |
| V2-17 | Convergência/cutover + arquivamento original | PENDENTE | somente após equivalência e integrações certificadas |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## Fechamento V2-08

### Bloco 1 — Durable Inbox

- lifecycle `RECEIVED -> PROCESSING -> PROCESSED/REJECTED` com optimistic versioning;
- identidade por partição fiscal + producer + upstream event id;
- replay após restart e conflito de conteúdo fail-closed;
- migration SQLite v2 e UoW transacional com V2-07;
- gate `f467d0dafa70e3c0debd3aacccbb183c954c5b35`, run `34662707064`, 316 PASS.

### Bloco 2 — Durable Outbox Worker

- claim/lease commitado antes do I/O externo;
- retry/backoff, restart, crash recovery, DLQ, concorrência e stale-worker fencing;
- gate `56678f730f2e7c3c235530887612a7ee71b5efc8`, run `34663828770`, 322 PASS.

### Bloco 3 — Signed Webhook Delivery

- `SignedWebhookOutboxHandler` reutiliza `WebhookSecurity` V2-05;
- HMAC-SHA256, `key_id`, timestamp, anti-replay temporal e overlap de rotação preservados;
- exact raw body signing, destino HTTPS e classificação retry/fatal;
- AsyncAPI v1.1.0 mantido sem breaking change;
- gate `8321106338aca262a76fe2bdfa76665bdcc57950`, run `34664214273`, 331 PASS.

### Bloco 4 — fechamento funcional

- migration v3 `v2_08_delivery_audit_and_ordering`;
- auditoria durável por tentativa: `CLAIMED`, `SUCCEEDED`, `RETRY_SCHEDULED`, `DEAD_LETTER`, `LEASE_EXPIRED`;
- início de audit + claim no mesmo commit; resultado de audit + mudança da outbox no mesmo commit;
- auditoria comprovada após restart, retry->success e lease-expired->success;
- ordering somente por `ordering_key` explícita e mesma partição fiscal; streams independentes continuam paralelizáveis;
- mensagem posterior da mesma stream aguarda a anterior enquanto esta não for `SUCCEEDED`/`DEAD_LETTER`;
- `SignedWebhookInboxReceiver` verifica assinatura antes de persistir na inbox;
- consumer recebe a mesma UoW da inbox e o side effect é commitado junto do `PROCESSED`;
- prova integrada `outbox -> webhook assinado -> inbox/consumer` entrega o mesmo request duas vezes e aplica o consumidor exatamente uma vez;
- assinatura inválida deixa a inbox sem registro;
- upgrade V2-07 -> migrations 2+3 e V2-08 Inbox -> migration 3 certificados.

## Gate final consolidado V2-08

- SHA: `bc77ee4cf2b7151d06c09cf32ca9168363ece1c7`;
- Actions run: `34666753555` — **SUCCESS**;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **67 source files**;
- Pytest: **337 PASS em 1.35s**;
- baseline V2-07: 309 testes; incremento líquido V2-08: **+28**.

A primeira tentativa do fechamento (`34666540502`) passou Install/Ruff/Mypy e falhou apenas porque 22 testes legados ainda esperavam `(1, 2)` após a migration v3. Os asserts e testes de upgrade foram reconciliados para `(1, 2, 3)` sem alteração regressiva do schema.

## Auditoria final de diff

Compare `v2/application-durable-persistence` (`e767ec36290f3304e495ce8fbeee6522f041d599`) -> gate final `bc77ee4...`:

- **65 commits à frente, 0 atrás**;
- alterações restritas a documentação/tracker V2-08, application/events/persistence da fase, testes e CI temporário de certificação;
- nenhum arquivo OpenAPI/AsyncAPI/JSON Schema alterado no fechamento;
- nenhum código de deploy, segredo real, provider fiscal, adapter HTTP de produção, infraestrutura ou cutover introduzido.

Compare específico do fechamento contra checkpoint pós-Webhooks `04195ca90783723ec1bb25d8806408dc2589d507`: **19 commits à frente, 0 atrás**, limitado a audit/ordering/receiving, persistência, testes e CI temporário.

## Riscos residuais / limites

- entrega externa permanece at-least-once; consumidores devem ser idempotentes;
- ordering é opt-in por chave/partição, nunca global;
- `DEAD_LETTER` é terminal e libera a stream; replay operacional controlado será tratado em camadas operacionais posteriores;
- transporte HTTP real e secret manager/vault pertencem aos adapters de produção V2-12;
- observabilidade ampla, SLOs/compliance runtime e hardening sistêmico permanecem V2-13/V2-14;
- não houve homologação fiscal externa nem produção.

## Governança

PR #9 permanece Draft. Nenhum merge, deploy, promoção ou cutover foi realizado. Após a certificação/documentação final, o workflow deve ser restaurado novamente para `workflow_dispatch` apenas.

## Próxima decisão

**V2-08 CONCLUÍDO E CERTIFICADO. V2-09 — Modularização de verticais — está LIBERADA, mas permanece PENDENTE até início formal em nova branch/PR Draft.**
