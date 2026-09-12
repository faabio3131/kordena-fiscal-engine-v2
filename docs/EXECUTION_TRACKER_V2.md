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
| V2-08 | Events/Webhooks/Inbox/Outbox | **EM EXECUÇÃO** | PR #9 Draft; Inbox `f467d0d...` / `34662707064`; Outbox Worker `56678f7...` / `34663828770`; Signed Webhook `8321106...` / `34664214273`; 331 PASS |
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

## Checkpoint V2-08 — três blocos funcionais certificados

### Bloco 1 — Durable Inbox

- contrato e estados da inbox implementados com deduplicação, optimistic versioning e persistência SQLite;
- replay após restart, conflito semântico fail-closed, rollback conjunto e isolamento por host comprovados;
- gate `f467d0dafa70e3c0debd3aacccbb183c954c5b35`, run `34662707064` SUCCESS;
- 62 source files; Pytest 316 PASS.

### Bloco 2 — Durable Outbox Delivery + Dispatcher/Worker

- `DurableFiscalOutboxWorker` com claim/lease commitado antes do I/O externo;
- retry/backoff, crash recovery, DLQ e stale-worker fencing por `attempt_count` comprovados;
- gate `56678f730f2e7c3c235530887612a7ee71b5efc8`, run `34663828770` SUCCESS;
- 63 source files; Pytest 322 PASS.

### Bloco 3 — Signed Webhook Delivery

- `SignedWebhookOutboxHandler` integrado ao worker durável;
- assinatura usa diretamente `WebhookSecurity` certificada no V2-05, sem criptografia paralela;
- body assinado é exatamente o payload durável da outbox;
- header obrigatório permanece `X-FM-Webhook-Signature` no formato certificado;
- destino exige HTTPS absoluto e não aceita credenciais embutidas nem fragmento;
- resolver de destino e transporte permanecem host-neutral e injetáveis;
- 2xx -> sucesso; 408/425/429/5xx/<200 -> retry; demais não-2xx -> fatal/DLQ;
- ausência de destino falha fechado sem I/O;
- retry assina novamente com novo timestamp e número de tentativa;
- overlap de rotação anterior/atual comprovado end-to-end;
- teste dedicado valida compatibilidade com AsyncAPI v1.1.0 sem breaking change;
- primeira tentativa run `34664156025` falhou somente por helper de teste chamando método inexistente de conveniência; implementação passou Ruff/Mypy;
- gate definitivo `8321106338aca262a76fe2bdfa76665bdcc57950`, run `34664214273` **SUCCESS**;
- Install PASS; Ruff PASS; Mypy strict PASS — **64 source files**; Pytest **331 PASS em 1.05s**;
- baseline pós-Outbox Worker 322 testes; **+9 testes**;
- compare específico contra checkpoint anterior `6b90df9021c0f9f6fd725524027333f13f1cd596`: 5 commits à frente, 0 atrás; somente CI temporário, export, handler de webhook e testes;
- CI restaurado para `workflow_dispatch` no commit `cd1dc973e6502074e173fbc9178d1aedec0a3fe7`;
- nenhum merge, deploy ou cutover realizado.

## Escopo V2-08 ainda pendente

- auditoria durável end-to-end de cada tentativa de entrega e resultado;
- ordering governado por chave explícita sem fila global obrigatória;
- prova integrada de duplicate webhook delivery com consumer/inbox idempotente;
- revisão final de aderência AsyncAPI/Bridge e rastreabilidade;
- gate final consolidado da V2-08;
- auditoria final do diff completo contra V2-07;
- riscos residuais e limites de produção documentados;
- nenhum merge/deploy antes do fechamento formal.

## Próxima decisão

**V2-08 permanece EM EXECUÇÃO. Durable Inbox, Durable Outbox Worker e Signed Webhook Delivery estão CONCLUÍDOS E CERTIFICADOS. Próximo bloco: auditoria end-to-end + ordering governado + duplicate-delivery idempotente, seguido do gate final consolidado da V2-08.**
