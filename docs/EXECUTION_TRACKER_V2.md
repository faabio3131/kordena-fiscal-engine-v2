# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-05 — Auth S2S + Workload Identity + Webhook Security**  
Fase atual: **V2-06 — Capability & Readiness API — EM EXECUÇÃO**

> O estado imediatamente anterior ao início do V2-06 foi preservado em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_06.md`.

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
| V2-05 | Auth S2S + workload identity + webhook security | **CONCLUÍDO** | PR #6 Draft; gate `196928d1b0cfe896df0c4741839ce72258f8f4d4`; run `34656535435`; Pytest 290 PASS |
| V2-06 | Capability & Readiness API | **EM EXECUÇÃO** | branch `v2/capability-readiness-api`; implementação e testes candidatos presentes; certificação CI pendente |
| V2-07 | Application service + persistência durável | PENDENTE | depende do fechamento certificado do V2-06 |
| V2-08 | Events/Webhooks/Inbox/Outbox | PENDENTE | depende V2-07 |
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

## Checkpoint V2-06 — em execução

- baseline imediato: `v2/s2s-workload-webhook-security` com V2-05 certificado;
- branch de trabalho: `v2/capability-readiness-api`;
- `FiscalActionCapability` torna explícitas `issue`, `query`, `cancel`, `inutilize`, `contingency`, `reconcile` e `archive_reference`;
- `JurisdictionCapabilityRule` passa a carregar ações explícitas sem alterar a semântica fail-closed existente;
- `capability_version` é determinístico e não expõe diretamente o `rule_id` interno;
- `CapabilityReadinessService.query(...)` resolve a declaração efetiva sem promover readiness;
- `CapabilityReadinessService.require_action(...)` exige ação declarada e readiness mínimo por ambiente;
- homologação requer no mínimo `HOMOLOGATION_READY`;
- produção requer `PRODUCTION_APPROVED`;
- família documental não implica permissão operacional;
- regra municipal mais específica continua prevalecendo quando aplicável;
- resposta é compatível com `CapabilityResponse` do FM Fiscal Bridge V1 existente;
- testes candidatos cobrem NF-e, NFC-e, NFS-e, município, produção, homologação, ausência de ação e contrato público;
- documentação técnica registrada em `docs/V2_06_CAPABILITY_READINESS_API.md`;
- nenhum servidor HTTP produtivo, persistência, segredo, merge ou deploy foi introduzido.

## Gate pendente

Antes de marcar V2-06 como `CONCLUÍDO` ainda é obrigatório:

- abrir/manter PR Draft;
- executar Install, Ruff, Mypy strict e Pytest completos;
- obter CI definitivo verde e registrar run/SHA;
- auditar o diff contra V2-05;
- registrar riscos residuais e decisão de avanço;
- retornar o CI ao modo controlado após a certificação.

## Próxima decisão

**V2-06 permanece EM EXECUÇÃO. Não avançar para V2-07 antes do gate definitivo 100% verde e do fechamento auditável desta fase.**
