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
| V2-08 | Events/Webhooks/Inbox/Outbox | **EM EXECUÇÃO** | PR #9 Draft; branch `v2/events-webhooks-inbox-outbox`; bootstrap documental/governança concluído; implementação funcional pendente |
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

## Checkpoint V2-08 — bootstrap iniciado

- baseline imediato: `v2/application-durable-persistence`, com V2-07 certificado;
- CI do V2-07 restaurado ao modo controlado `workflow_dispatch` antes da abertura da nova fase;
- branch criada: `v2/events-webhooks-inbox-outbox`;
- PR #9 aberta em Draft sobre V2-07, sem merge;
- snapshot pré-fase preservado em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_08.md`;
- escopo governado registrado em `docs/V2_08_EVENTS_WEBHOOKS_INBOX_OUTBOX.md`;
- objetivos centrais: durable inbox, durable outbox delivery, dispatcher/workers, retries/backoff, lease recovery, DLQ, webhook delivery assinado, auditoria e idempotência end-to-end;
- segurança de webhook deve reutilizar as garantias HMAC-SHA256, `key_id`, timestamp/anti-replay e rotação certificadas no V2-05;
- persistência deve reutilizar as portas e o estado durável certificados no V2-07;
- contratos AsyncAPI/Bridge existentes devem ser preservados, salvo mudança explicitamente versionada e auditada;
- workflow herdado permanece em modo controlado `workflow_dispatch`; ativação temporária do CI de PR será feita somente quando a fase entrar em certificação;
- nenhuma implementação funcional foi declarada concluída neste bootstrap;
- nenhum merge, deploy ou cutover realizado.

## Gate pendente

Antes de marcar V2-08 como `CONCLUÍDO` será obrigatório:

- implementação e testes de inbox/outbox/webhook delivery/workers/retries/DLQ;
- restart/replay/lease-expiry/concurrency testados;
- ativação controlada do CI de PR para certificação;
- Install, Ruff, Mypy strict e Pytest completos;
- CI definitivo verde com run/SHA registrados;
- diff auditado contra V2-07;
- riscos residuais documentados;
- CI retornado ao modo controlado após a certificação;
- nenhum merge/deploy antes do fechamento formal.

## Próxima decisão

**V2-08 está EM EXECUÇÃO com branch e PR #9 Draft abertas. O próximo passo é iniciar o primeiro bloco funcional, começando pelo contrato/estado da durable inbox e sua integração transacional com a persistência V2-07.**
