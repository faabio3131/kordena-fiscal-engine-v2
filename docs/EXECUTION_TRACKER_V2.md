# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO CONTROLADA — V2-15 externa pendente; V2-16 internamente fechada com bloqueios reais; V2-17.1/V2-17.2 certificadas; cutover real bloqueado**  
Última fase integralmente concluída sem bloqueio externo: **V2-14 — Hardening sistêmico**  
Fase atual: **V2-17 — PREPARAÇÃO DE CONVERGÊNCIA PARCIALMENTE CONCLUÍDA; B17.1+B17.2 INTERNAMENTE CERTIFICADAS**

> V2-15: `docs/V2_15_CLOSURE_CERTIFICATION.md`. V2-16: `docs/V2_16_PRODUCT_INTEGRATION_EXECUTION.md` + `docs/V2_16_CLOSURE_CERTIFICATION.md`. V2-17: `docs/V2_17_CONVERGENCE_CUTOVER.md`. Auditoria geral: `docs/V2_17_2_GENERAL_AUDIT.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. PRs permanecem Draft/não mergeadas. Deploy, produção real, cutover, migração produtiva e promoção de `PRODUCTION_APPROVED` continuam proibidos. Homologação oficial externa exige evidência externa real; teste sintético não substitui resposta oficial.

| Fase | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-00..V2-11 | Equivalência → Control Plane | **CONCLUÍDO** | PRs #1-#12 Draft; histórico certificado |
| V2-12 | Gateway/Signer/Vault adapters | **CONCLUÍDO** | PR #13 Draft; 508 PASS |
| V2-13 | Observabilidade + Compliance Operations | **CONCLUÍDO** | PR #14 Draft; 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 Draft; 582 PASS |
| V2-15 | Homologação + pilotos controlados | **BLOQUEADO PARCIAL — INTERNO CERTIFICADO** | PR #16 Draft; 620 PASS; externo oficial pendente |
| V2-16 | Integração produtos FM | **BLOQUEADO PARCIAL — INTERNO B1-B7 CERTIFICADO** | PR #17 Draft; 646 PASS; bloqueios de produto explicitados |
| V2-17.1 | Convergence readiness + single authority | **CONCLUÍDO/CERTIFICADO INTERNAMENTE** | PR #19 Draft; 116 source; 651 PASS |
| V2-17.2 | State/document migration + rollback rehearsal | **CONCLUÍDO/CERTIFICADO INTERNAMENTE — SINTÉTICO** | PR #19 Draft; 117 source; 660 PASS |
| V2-17.3 | Cutover rehearsal / authority transfer closure | **PENDENTE — NÃO AUTORIZADO** | recomendação da auditoria geral |
| V2-18 | Produto comercial independente | **PENDENTE — NÃO AUTORIZADO** | posterior à convergência real |

## V2-15 — estado preservado

B0-B6 internamente certificados, gate final 111 source / 620 PASS. Continua **BLOQUEADA PARCIAL — INTERNO CERTIFICADO; EXTERNO OFICIAL PENDENTE**. Certificados privados, CSC, provider credentials, endpoints/respostas oficiais e pilotos externos reais não foram fornecidos/executados. Nenhum provider/UF/município foi promovido sem evidência oficial.

## V2-16 — estado preservado

### B1 — Integration Contract
CONCLUÍDO/CERTIFICADO. Run `34779681157`.

### B2 — Kordena
BLOQUEADO por Web Premium/FISC-20. PR #118 permanece funcionalmente PARCIAL.

### B3 — Iron Fit
CONCLUÍDO/CERTIFICADO. SHA `2be8321eeb066f0296ba812faab0a098c32f0632`, run `34780329013`.

### B4 — Vendedor IA
BLOQUEADO PARCIAL / INTERNO CERTIFICADO. `Payment.status=CONFIRMED` é autoridade de liquidação; faltam recipient fiscal data/classificação NF-e/NFC-e. Run `34783831679`, 157 PASS + security/Docker smoke.

### B5 — CampaIA
BLOQUEADO PARCIAL / INTERNO CERTIFICADO. Own-billing boundary certificado; falta authority real de billing/payment próprio. Run `34784021431`, 347 PASS + AsyncAPI.

### B6 — Adapter Contract Pack / onboarding
CONCLUÍDO/CERTIFICADO. SHA `878738c172ab31e3f81618a95986370b17d0e602`, run `34784375685`, 114 source / 639 PASS.

### B7 — E2E + Multi-Product Cross-Certification + Closure
CONCLUÍDO/CERTIFICADO. SHA de implementação `5afb3d9af8879f17b451e757f53ca41796e843e7`, run `34785216450`, job `103799337982`: 114 source / 646 PASS. Diff V2-15→B7: 20 ahead / 0 behind. HEAD documental/base V2-17: `6998d5a4b7370621160e2520bbadabafca86bda0`.

Estado: **BLOQUEADA PARCIAL — TODO O TRABALHO INTERNO EXECUTÁVEL CONCLUÍDO/CERTIFICADO; DEPENDÊNCIAS DE PRODUTO/EXTERNAS DOCUMENTADAS.**

## V2-17 — convergência preparatória

Branch: `v2/convergence-cutover`  
PR: #19 OPEN/DRAFT/não mergeada  
Base: `v2/fm-products-integration@6998d5a4b7370621160e2520bbadabafca86bda0`

### Referência legado

O baseline fiscal legado correto é `faabio3131/kordena-fiscal-engine`, branch `feat/fisc-19-rtc-multiuf-hardening`, SHA `b336def47ad4f5188307102203f4e04b98406014`. O `main` atual do repositório legado (`b050d454...`) é placeholder e NÃO deve ser usado como baseline de convergência.

### V2-17.1 — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Foi criado `kordena_fiscal.convergence.readiness`:

- matriz de pré-condições fail-closed;
- estados `READY_INTERNAL`, `BLOCKED_PRODUCT`, `BLOCKED_EXTERNAL`, `HUMAN_APPROVAL_REQUIRED`;
- `SingleFiscalAuthorityPlan` cobrindo sequence, idempotency, lifecycle, archive, reconciliation, provider state, binding, capability, readiness, audit e events;
- proibição de legacy writer distinto permanecer `READ_WRITE` após cutover;
- `require_cutover_ready()` falha enquanto existir blocker obrigatório.

Gate: HEAD `3f5b1892a28d898b336296dcf82ea2d8ca924d4e`, run `34785466576`, job `103800032384`: Install/Ruff PASS; Mypy **116 source**; Pytest **651 PASS em 7.29s**.

### V2-17.2 — CONCLUÍDO/CERTIFICADO INTERNAMENTE EM REHEARSAL SINTÉTICO

Foi criado `kordena_fiscal.convergence.migration` com inventário de 20 categorias, dispositions migrate/reference/archive/reconcile, dry-run determinístico, fingerprint, idempotência, restart, conflict detection, rollback, reconciliation e sequence floor.

Primeiro gate: run `34785562237`, job `103800288626`: Install PASS; Ruff FAIL por 20 E501 no inventário declarativo; Mypy/Pytest skipped. Correção apenas de formatação.

Gate final: HEAD `ba979defe16102fc2163f14a6612eac1516bcaf6`, run `34785613970`, job `103800433451`: Install PASS; Ruff PASS; Mypy **117 source**; Pytest **660 PASS em 13.20s**.

Rehearsal usa somente identificadores/categorias/checksums/provenance sintéticos. Nenhuma migração produtiva foi executada.

## Auditoria geral pós-V2-17.2

Documento: `docs/V2_17_2_GENERAL_AUDIT.md`.

Classificação:

- **A — INTERNO CONCLUÍDO:** Core universal, Bridge, security, persistence/events, Control Plane, adapters, observabilidade/hardening, trabalho interno V2-15, V2-16 executável, V2-17.1 e V2-17.2 sintéticas.
- **B — INTERNO PENDENTE:** V2-17.3 Cutover Rehearsal / Authority Transfer Closure e validações finais condicionadas a snapshot/ambiente autorizado.
- **C — EXTERNO/PRODUTO/HOMOLOGAÇÃO:** Kordena FISC-20, recipient/classificação Vendedor IA, billing authority CampaIA, certificados/CSC/credentials/ambientes/evidências oficiais.
- **D — APROVAÇÃO HUMANA:** merge, production provisioning, migração real, freeze de writers, cutover, rollback operacional, archive legado e `PRODUCTION_APPROVED`.

Próxima autorização recomendada: **V2-17.3 — Cutover Rehearsal / Authority Transfer Closure**, idealmente após Kordena/FISC-20 e requisitos operacionais mínimos. NÃO executar nesta janela.

## Governança preservada

**SEM MERGE. SEM Ready/auto-merge. SEM deploy. SEM produção real. SEM cutover real. SEM migração produtiva. SEM segredo real. SEM homologação externa inventada. SEM promoção indevida de `PRODUCTION_APPROVED`. V2-17.3 NÃO INICIADA. V2-18 NÃO INICIADA.**
