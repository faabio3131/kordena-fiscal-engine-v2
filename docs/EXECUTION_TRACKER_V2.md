# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO CONTROLADA — CONVERGÊNCIA INTERNA V2-17 CERTIFICADA; CUTOVER REAL BLOQUEADO; V2-18 LIBERADA PARA CONSTRUÇÃO INTERNA**  
Fase atual: **V2-17 — TODO O TRABALHO INTERNO AUTORIZADO V2-17.1..V2-17.5 CONCLUÍDO/CERTIFICADO**

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`.
PRs permanecem Draft/não mergeadas. Deploy, produção real, cutover, migração produtiva,
freeze produtivo, segredo real e promoção real de `PRODUCTION_APPROVED` continuam proibidos
sem autorização humana específica. Homologação oficial exige evidência externa real.

## Estado por fase

| Fase | Escopo | Status | Evidência principal |
|---|---|---|---|
| V2-00..V2-11 | Equivalência → Control Plane | **CONCLUÍDO** | PRs #1-#12 / histórico certificado |
| V2-12 | Gateway/Signer/Vault | **CONCLUÍDO** | PR #13 / 508 PASS |
| V2-13 | Observabilidade/Compliance | **CONCLUÍDO** | PR #14 / 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 / 582 PASS |
| V2-15 | Homologação/pilotos | **BLOQUEADO PARCIAL — INTERNO CERTIFICADO** | PR #16 / 620 PASS / externo pendente |
| V2-16 | Integração produtos FM | **BLOQUEADO PARCIAL — INTERNO B1-B7 CERTIFICADO** | PR #17 / 646 PASS |
| V2-17.1 | Readiness + single authority | **CONCLUÍDO/CERTIFICADO** | 116 source / 651 PASS |
| V2-17.2 | Migration + rollback rehearsal | **CONCLUÍDO/CERTIFICADO SINTÉTICO** | 117 source / 660 PASS |
| V2-17.3 | Cutover rehearsal / authority transfer | **CONCLUÍDO/CERTIFICADO SINTÉTICO** | run `34787607567`, 118 source / 675 PASS |
| V2-17.4 | Consumer integration closure | **CONCLUÍDO COMO REAUDITORIA GOVERNADA** | blockers reais preservados |
| V2-17.5 | Final convergence readiness | **CONCLUÍDO/CERTIFICADO** | cutover real permanece bloqueado |
| V2-18 | Produto comercial independente | **AUTORIZADA PARA CONSTRUÇÃO INTERNA** | efeitos produtivos continuam proibidos |

## V2-15 — estado preservado

Todo o trabalho interno B0-B6 está certificado. Continuam externos certificados privados,
CSC, provider credentials, ambientes/respostas oficiais e pilotos externos autorizados.
Nenhum provider, UF ou município foi declarado oficialmente homologado sem evidência.

Documento: `docs/V2_15_CLOSURE_CERTIFICATION.md`.

## V2-16 — estado preservado

Todo o trabalho interno executável B1-B7 foi certificado. Estado dos consumidores:

- Kordena: bloqueado por Web Premium/FISC-20;
- Iron Fit: integração interna certificada;
- Vendedor IA: handoff certificado, recipient/classificação NF-e/NFC-e pendentes;
- CampaIA: own-billing boundary certificada, authority real de billing/payment pendente.

Documento: `docs/V2_16_CLOSURE_CERTIFICATION.md`.

## V2-17 — convergência

Branch: `v2/convergence-cutover`  
PR: #19 — OPEN/DRAFT/não mergeada  
Base: `v2/fm-products-integration@6998d5a4b7370621160e2520bbadabafca86bda0`

### Referência legado correta

`faabio3131/kordena-fiscal-engine`

Branch: `feat/fisc-19-rtc-multiuf-hardening`

SHA: `b336def47ad4f5188307102203f4e04b98406014`

O `main` atual do legado não é baseline funcional de convergência.

### V2-17.1

Readiness matrix fail-closed + `SingleFiscalAuthorityPlan` para sequence, idempotency,
lifecycle, archive, reconciliation, provider state, binding, capability, readiness, audit e
events. Gate: 116 source / 651 PASS.

### V2-17.2

Migration contract/rehearsal sintético com inventário de 20 categorias, dry-run,
idempotência, restart, conflito, rollback, reconciliation e sequence floor. Gate: 117 source /
660 PASS.

### V2-17.3

`kordena_fiscal.convergence.cutover_rehearsal` adiciona máquina de estados governada:
PRECHECK → freeze → snapshot → migration → reconciliation → authority transfer simulada →
post-validation → closure, com abort/rollback.

Barreiras de código rejeitam migração produtiva e ativação real de autoridade.

Gate certificado:

- run `34787607567`;
- job `103805827149`;
- Install PASS;
- Ruff PASS;
- Mypy PASS — **118 source files**;
- Pytest **675 PASS em 7.67s**.

Documento: `docs/V2_17_3_CUTOVER_REHEARSAL.md`.

### V2-17.4

Reauditoria ao vivo dos consumidores em 2026-09-13:

- Kordena PR #118: `BLOCKED_PRODUCT`, HEAD `9ee10a08...`, situação PARCIAL;
- Iron PR #48: `READY_INTERNAL`, HEAD `2be8321e...`;
- Vendedor IA PR #1: `BLOCKED_PRODUCT` parcial, HEAD `b4b7fb05...`;
- CampaIA PR #1: `BLOCKED_PRODUCT` parcial, HEAD `bdebbc35...`.

Documento: `docs/V2_17_4_CONSUMER_INTEGRATION_CLOSURE.md`.

### V2-17.5

A matriz final confirma `READY_INTERNAL` para equivalência, multiproduto, regressão,
migration/rollback rehearsal, freeze protocol, state reconciliation, archive, sequence,
idempotency, provider-state boundaries e observabilidade.

Bloqueios obrigatórios para cutover real:

1. Kordena/FISC-20;
2. inventário de writers reais do ambiente alvo;
3. evidência/homologação externa aplicável;
4. provisioning seguro de material real;
5. autorização humana específica.

Documento: `docs/V2_17_FINAL_READINESS_CERTIFICATION.md`.

## Gate humano de cutover

A V2-17 está internamente preparada para rehearsal governado, mas **NÃO está autorizada a
executar cutover real**. Não desligar legado, congelar writer real, migrar banco real, alterar
DNS/endpoint, usar segredo real ou promover `PRODUCTION_APPROVED`.

A ausência desse gate NÃO bloqueia a construção interna da V2-18.

## Próxima sequência autorizada

`V2-18.1 → V2-18.2 → V2-18.3 → V2-18.4 → V2-18.5 → V2-18.6 → V2-18.7 → V2-18.8 → V2-18.9 → V2-18.10 → V2-18.11 → AUDITORIA FINAL 0–100%`

## Governança preservada

**SEM MERGE. SEM Ready/auto-merge. SEM deploy real. SEM produção real. SEM cutover real. SEM
migração produtiva. SEM segredo real. SEM homologação externa inventada. SEM promoção indevida
de `PRODUCTION_APPROVED`.**
