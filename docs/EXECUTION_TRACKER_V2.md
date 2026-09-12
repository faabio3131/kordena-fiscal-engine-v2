# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-07 — Application service + persistência durável**  
Fase atual: **V2-08 — Events/Webhooks/Inbox/Outbox — EM EXECUÇÃO**

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
| V2-07 | Application service + persistência durável | **CONCLUÍDO** | PR #8 Draft; gate `999ba84b9c25988441867820bfe8af0571269548`; run `34659892798` SUCCESS; 59 source files; Pytest 309 PASS; CI restaurado a `workflow_dispatch` |
| V2-08 | Events/Webhooks/Inbox/Outbox | **EM EXECUÇÃO** | PR #9 Draft; Durable Inbox **CONCLUÍDA/CERTIFICADA** no gate `f467d0dafa70e3c0debd3aacccbb183c954c5b35`, run `34662707064`; demais blocos pendentes |
| V2-09 | Modularização de verticais | PENDENTE | após contratos core estabilizados |
| V2-10 | Contract Packs Kordena/Iron/Vendedor/CampaIA | PENDENTE | depende V2-03..V2-09 |
| V2-11 | Control Plane independente | PENDENTE | depende core operacional |
| V2-12 | Gateway/Signer/Vault production adapters | PENDENTE | depende V2-11 |
| V2-13 | Observabilidade + Compliance Operations | PENDENTE | depende V2-07/V2-12 |
| V2-14 | Hardening sistêmico | PENDENTE | regressão/carga/falhas/segurança |
| V2-15 | Homologação + pilotos controlados | PENDENTE | depende V2-14 |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | Kordena aguarda V1 Web Premium; demais aguardam V2 universal certificado |
| V2-17 | Convergência/cutover + arquivamento original | PENDENTE | somente após equivalência e integrações certificadas |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## Checkpoint V2-08 — Durable Inbox concluída e certificada

- baseline imediato: `v2/application-durable-persistence`, com V2-07 certificado;
- branch: `v2/events-webhooks-inbox-outbox`;
- PR #9 permanece Draft sobre V2-07, sem merge;
- `kordena_fiscal.events` criado como superfície host-neutral para mensagens assíncronas;
- `FiscalInboxEntry`, `FiscalInboxStatus`, `FiscalInboxStore` e `FiscalInboxService` implementados;
- estados governados: `RECEIVED -> PROCESSING -> PROCESSED/REJECTED`;
- transições protegidas por versão otimista e falham fechado em versão stale ou estado inválido;
- identidade determinística usa partição fiscal + producer + upstream `event_id`;
- duplicate intake com conteúdo idêntico retorna replay da entrada original, inclusive após restart;
- mesma identidade semântica com conteúdo diferente gera `InboxConflictError`;
- payload persistido com SHA-256 validado e correlation/causation/idempotency preservados;
- migration SQLite v2 `v2_08_durable_inbox` adiciona `fm_fiscal_inbox`, constraint única de identidade e índice de status;
- migration testada sobre estado equivalente ao V2-07: somente versão 2 é aplicada e migration 1 é preservada;
- `FiscalUnitOfWork` passa a expor `inbox` dentro do mesmo `BEGIN IMMEDIATE` dos stores V2-07;
- rollback conjunto inbox + outbox foi comprovado sem commit;
- `FiscalApplicationService` recebe, inicia processamento, conclui, rejeita e consulta eventos da inbox dentro do UoW;
- mesma upstream event id permanece isolada entre hosts diferentes;
- contratos AsyncAPI/Bridge existentes não foram alterados neste bloco;
- primeira tentativa de CI falhou somente em E501/Ruff e foi corrigida sem mudança semântica;
- gate definitivo da Durable Inbox: `f467d0dafa70e3c0debd3aacccbb183c954c5b35`;
- Actions run `34662707064`: **SUCCESS**;
- Install PASS; Ruff PASS; Mypy strict PASS — **62 source files sem issues**; Pytest **316 PASS em 0.85s**;
- baseline V2-07: 309 testes; Durable Inbox adicionou 7 testes;
- diff do gate contra V2-07: 17 commits à frente, 0 atrás, limitado ao bootstrap V2-08, events/inbox, integração application/persistence, testes e CI temporário;
- CI foi restaurado a `workflow_dispatch` após o checkpoint no commit `c9e26364e2f0925439ac86e146a8ab5668f57c3b`;
- nenhum merge, deploy ou cutover realizado.

## Escopo V2-08 ainda pendente

- Durable Outbox Delivery sobre o estado persistido do V2-07;
- dispatcher/worker com claim e lease;
- retry/backoff limitado e auditável;
- recovery de lease expirado após crash;
- DLQ/dead-letter para falha permanente;
- webhook delivery assinado usando a segurança certificada no V2-05;
- auditoria end-to-end de tentativas e resultado;
- testes de concorrência, duplicate delivery, retry, lease expiry e DLQ;
- gate final da fase e auditoria final do diff contra V2-07;
- nenhum merge/deploy antes do fechamento formal.

## Próxima decisão

**V2-08 permanece EM EXECUÇÃO. Durable Inbox está CONCLUÍDA E CERTIFICADA. O próximo bloco funcional liberado é Durable Outbox Delivery + Dispatcher/Worker, incluindo claim/lease, retry/backoff e dead-letter.**
