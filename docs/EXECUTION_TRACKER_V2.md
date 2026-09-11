# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-06 — Capability & Readiness API**  
Fase atual: **V2-07 — Application service + persistência durável — EM EXECUÇÃO**

> O estado imediatamente anterior ao início do V2-07 foi preservado em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_07.md`.

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
| V2-07 | Application service + persistência durável | **EM EXECUÇÃO** | branch `v2/application-durable-persistence`; implementação e testes candidatos presentes; certificação CI pendente |
| V2-08 | Events/Webhooks/Inbox/Outbox | PENDENTE | depende do fechamento certificado do V2-07 |
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

## Checkpoint V2-07 — em execução

- baseline imediato: `v2/capability-readiness-api`, com V2-06 certificado;
- branch de trabalho: `v2/application-durable-persistence`;
- novas portas: binding repository, lifecycle repository, reconciliation repository e Unit of Work;
- stores certificados existentes de idempotência, sequência, outbox e archive são reutilizados por contrato;
- `FiscalApplicationService` introduz coordenação host-neutral sem mover regras fiscais para persistence/controller;
- reserva de emissão persiste idempotência + lifecycle inicial antes de qualquer side effect externo;
- replay de tentativa ainda `RESERVED` retorna `RECOVERY_REQUIRED`, proibindo reemissão silenciosa após crash;
- finalização autorizada/rejeitada acopla lifecycle terminal e idempotência na mesma transação;
- adapter SQLite filesystem-backed com migration controlada v1 e `BEGIN IMMEDIATE` implementado como referência durável;
- `:memory:` é rejeitado na superfície durável;
- estados duráveis cobertos: idempotência, sequência, lifecycle, bindings, outbox, archive e reconciliação;
- testes candidatos simulam restart de processo, replay, continuidade de sequência, rollback de UoW e recuperação após crash em `TRANSMITTING`;
- documentação técnica: `docs/V2_07_APPLICATION_DURABLE_PERSISTENCE.md`;
- nenhum contrato Bridge, provider, segredo, homologação externa, merge ou deploy foi alterado.

## Gate pendente

Antes de marcar V2-07 como `CONCLUÍDO` ainda é obrigatório:

- abrir/manter PR Draft;
- executar Install, Ruff, Mypy strict e Pytest completos;
- corrigir qualquer regressão encontrada pelo CI;
- obter CI definitivo verde e registrar run/SHA;
- auditar o diff contra V2-06;
- registrar riscos residuais e decisão de avanço;
- retornar o CI ao modo controlado após certificação.

## Próxima decisão

**V2-07 permanece EM EXECUÇÃO. Não avançar para V2-08 antes do gate definitivo 100% verde e do fechamento auditável desta fase.**
