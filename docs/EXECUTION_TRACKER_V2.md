# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-14 — Hardening sistêmico**  
Fase atual: **V2-15 — Homologação + Pilotos Controlados — EM EXECUÇÃO**

> Snapshot pré-V2-15: `docs/history/EXECUTION_TRACKER_V2_PRE_V2_15.md`. Plano: `docs/V2_15_HOMOLOGATION_CONTROLLED_PILOTS.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. Nenhum merge, deploy, promoção ou cutover é automático.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-12 | Gateway/Signer/Vault adapters | **CONCLUÍDO** | PR #13 Draft; 508 PASS |
| V2-13 | Observabilidade + Compliance Operations | **CONCLUÍDO** | PR #14 Draft; 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 Draft; B6 582 PASS; doc gate 582 PASS; CI final dispatch-only |
| V2-15 | Homologação + pilotos controlados | **EM EXECUÇÃO** | branch `v2/homologation-controlled-pilots`; preparar readiness/matrizes/pilotos; evidência oficial externa obrigatória para homologação real |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | AUTORIZADA; depende de Core/homologação e readiness real dos produtos |
| V2-17 | Convergência/cutover | PENDENTE | NÃO AUTORIZADO nesta execução |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## V2-14 — Hardening sistêmico — CONCLUÍDA/CERTIFICADA

Fechamento: `docs/V2_14_CLOSURE_CERTIFICATION.md`. Branch `v2/system-hardening`, PR #15 Draft. Gate funcional B6 582 PASS; gate documental 582 PASS; CI final dispatch-only.

## V2-15 — Homologação + Pilotos Controlados — EM EXECUÇÃO

### Bootstrap — CONCLUÍDO

- branch `v2/homologation-controlled-pilots` criada exatamente do HEAD final V2-14 `15426a4460ed18c8861c807b92b98c6cfecb3126`;
- snapshot pré-fase criado;
- plano formal criado;
- PR Draft stacked sobre `v2/system-hardening` deve permanecer aberta/não mergeada.

### B1 — Homologation Environment Readiness — EM EXECUÇÃO

Auditar ambiente HOMOLOGATION, provider descriptors, Vault refs, signer, CSC, credentials, transport/TLS/schema/jurisdiction/readiness/telemetria e distinguir evidência técnica interna de evidência oficial externa.

## Governança preservada

Nenhum endpoint produtivo, emissão de produção, merge, deploy ou cutover é autorizado. Se evidência/credencial/certificado/CSC/provider externo não estiver disponível, concluir todo o trabalho interno e registrar bloqueio parcial preciso. V2-17 não iniciar.
