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
| V2-08 | Events/Webhooks/Inbox/Outbox | **EM EXECUÇÃO** | PR #9 Draft; Inbox gate `f467d0dafa70e3c0debd3aacccbb183c954c5b35` / run `34662707064`; Outbox Worker gate `56678f730f2e7c3c235530887612a7ee71b5efc8` / run `34663828770`; 322 PASS |
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

## Checkpoint V2-08 — blocos certificados

### Bloco 1 — Durable Inbox

- superfície `kordena_fiscal.events` criada;
- `FiscalInboxEntry`, `FiscalInboxStatus`, `FiscalInboxStore` e `FiscalInboxService` implementados;
- lifecycle `RECEIVED -> PROCESSING -> PROCESSED/REJECTED` com optimistic versioning;
- identidade determinística por partição fiscal + producer + upstream `event_id`;
- replay idêntico após restart e conflito semântico fail-closed;
- payload SHA-256 + correlation/causation/idempotency preservados;
- migration SQLite v2 `v2_08_durable_inbox` integrada ao mesmo UoW do V2-07;
- rollback conjunto inbox + outbox, isolamento por host e upgrade V2-07 -> v2 comprovados;
- gate `f467d0dafa70e3c0debd3aacccbb183c954c5b35`, run `34662707064` SUCCESS;
- Install PASS; Ruff PASS; Mypy strict PASS — 62 source files; Pytest 316 PASS;
- baseline V2-07 309 testes; +7 testes.

### Bloco 2 — Durable Outbox Delivery + Dispatcher/Worker

- `DurableFiscalOutboxWorker` criado na camada de aplicação;
- claim/lease é executado e commitado em transação curta antes do I/O externo;
- handler roda fora da transação SQLite;
- success/retry/dead-letter são persistidos em nova Unit of Work;
- `attempt_count` funciona como fencing token contra worker stale;
- retry/backoff persiste `RETRY_WAIT` + `available_at` e sobrevive restart;
- lease expirada após crash é recuperada com nova tentativa;
- dois workers duráveis concorrentes não despacham a mesma lease ativa;
- exceções do handler são tratadas como falha retryable limitada e terminam em DLQ quando esgotam tentativas;
- stale worker não consegue finalizar depois que outra tentativa assumiu autoridade;
- handler de teste abre outra Unit of Work durante dispatch, comprovando ausência de transação local mantida sobre I/O;
- nenhuma nova migration necessária: o schema de outbox do V2-07 já contém estado suficiente;
- gate `56678f730f2e7c3c235530887612a7ee71b5efc8`, run `34663828770` SUCCESS;
- Install PASS; Ruff PASS; Mypy strict PASS — **63 source files sem issues**; Pytest **322 PASS em 1.16s**;
- baseline pós-Inbox 316 testes; **+6 testes** de outbox durável;
- compare no gate contra V2-07: 33 commits à frente, 0 atrás, alterações limitadas ao V2-08 e CI temporário;
- CI restaurado a `workflow_dispatch` no commit `c533bf65791025dd597f1871ee8f1572e39954ee`;
- nenhum merge, deploy ou cutover realizado.

## Escopo V2-08 ainda pendente

- webhook delivery assinado usando HMAC-SHA256, `key_id`, timestamp, anti-replay e rotação certificados no V2-05;
- handler/adaptador de webhook integrado ao `DurableFiscalOutboxWorker`;
- auditoria end-to-end de tentativas e resultado final além do estado resumido da outbox;
- ordering governado quando houver chave explícita, sem fila global obrigatória;
- validação final de aderência aos contratos AsyncAPI/Bridge existentes;
- testes de duplicate webhook delivery, assinatura, replay, rotação, falha permanente e restart;
- gate final da fase e auditoria final do diff contra V2-07;
- nenhum merge/deploy antes do fechamento formal.

## Próxima decisão

**V2-08 permanece EM EXECUÇÃO. Durable Inbox e Durable Outbox Delivery + Dispatcher/Worker estão CONCLUÍDOS E CERTIFICADOS. O próximo bloco funcional liberado é Webhook Delivery assinado, reutilizando a segurança HMAC/anti-replay/rotação certificada no V2-05.**
