# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **TODO O TRABALHO INTERNO AUTORIZADO V2-00..V2-18.11 CONCLUÍDO; AGUARDANDO AUDITORIA FINAL 0–100% E GATE DO HEAD DOCUMENTAL**  
Fase atual: **V2-18.11 — RELEASE CANDIDATE TÉCNICO INTERNO**

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
| V2-18.1 | Product identity + packaging | **CONCLUÍDO/CERTIFICADO** | catálogo configurável / 120 source / 681 PASS |
| V2-18.2 | Public developer documentation | **CONCLUÍDO/CERTIFICADO** | docs públicas/sintéticas |
| V2-18.3 | Self-service onboarding | **CONCLUÍDO/CERTIFICADO** | idempotent/checkpoint/fail-closed |
| V2-18.4 | Plans + entitlements + billing foundation | **CONCLUÍDO/CERTIFICADO** | commercial billing separado da authority fiscal |
| V2-18.5 | SDKs | **CONCLUÍDO/CERTIFICADO** | Python + TypeScript reference / Bridge público |
| V2-18.6 | SLA + support + operations | **CONCLUÍDO/CERTIFICADO** | SEV1–SEV4 + runbooks + health |
| V2-18.7 | LGPD + retention + compliance técnico | **CONCLUÍDO/CERTIFICADO** | `LEGAL_VALIDATION_REQUIRED` preservado |
| V2-18.8 | Premium Product Experience | **CONCLUÍDO/CERTIFICADO** | run `34791085676`, 126 source / 724 PASS |
| V2-18.9 | Commercial End-to-End | **CONCLUÍDO/CERTIFICADO** | run `34791237542`, 126 source / 730 PASS |
| V2-18.10 | Security + Performance + DR | **CONCLUÍDO/CERTIFICADO** | run `34791936752`, Bandit + pip-audit + 741 PASS |
| V2-18.11 | Release Candidate Closure | **CONCLUÍDO INTERNAMENTE** | `2.18.0-rc.1` / aguardando gate documental final |

## V2-15 — estado preservado

Todo o trabalho interno B0-B6 está certificado. Continuam externos certificados privados,
CSC, provider credentials, ambientes/respostas oficiais e pilotos externos autorizados.
Nenhum provider, UF ou município foi declarado oficialmente homologado sem evidência.

Documento: `docs/V2_15_CLOSURE_CERTIFICATION.md`.

## V2-16 — estado preservado

Todo o trabalho interno executável B1-B7 foi certificado. Revalidação ao vivo de 2026-09-13/14:

- Kordena PR #118: OPEN/DRAFT, HEAD `9ee10a08cf445cc7233cde5b70564f8feade315c`, situação funcional PARCIAL;
- Iron Fit PR #48: OPEN/DRAFT, HEAD `2be8321eeb066f0296ba812faab0a098c32f0632`, integração interna certificada;
- Vendedor IA PR #1: OPEN/DRAFT, HEAD `b4b7fb05236c481d5626de5386864ae6f5227418`, handoff certificado e recipient/classificação NF-e/NFC-e pendentes;
- CampaIA PR #1: OPEN/DRAFT, HEAD `bdebbc3558ff8b07c1a38e0cb728be0dc3635c4b`, adapter certificado e authority real de own billing/payment pendente.

Documento: `docs/V2_16_CLOSURE_CERTIFICATION.md`.

## V2-17 — convergência

Branch: `v2/convergence-cutover`  
PR: #19 — OPEN/DRAFT/não mergeada  
HEAD final certificado: `cfd58c3249a5601dc62088eee7327dfe02759646`

### Referência legado correta

`faabio3131/kordena-fiscal-engine`

Branch: `feat/fisc-19-rtc-multiuf-hardening`

SHA: `b336def47ad4f5188307102203f4e04b98406014`

O `main` atual do legado não é baseline funcional de convergência.

### Resultado

V2-17.1..V2-17.5 estão internamente certificadas: readiness/single authority, migration + rollback rehearsal, cutover/authority-transfer rehearsal, consumer reauditoria e final readiness.

Gate final V2-17:

- run `34787708874`;
- job `103806110253`;
- Install/Ruff/Mypy PASS;
- **118 source files**;
- Pytest **675 PASS**.

Bloqueios obrigatórios para cutover real continuam:

1. Kordena/FISC-20 e consumer prerequisites aplicáveis;
2. inventário de writers reais do ambiente alvo;
3. evidência/homologação externa aplicável;
4. provisioning seguro de material real;
5. snapshot/migração produtiva autorizada;
6. autorização humana específica.

## V2-18 — produto comercial independente

Branch: `v2/commercial-independent-product`  
PR: #22 — OPEN/DRAFT/não mergeada  
Base: `v2/convergence-cutover@cfd58c3249a5601dc62088eee7327dfe02759646`

Release Candidate técnico interno:

`FM Fiscal 2.18.0-rc.1`

Manifesto: `docs/V2_18_RELEASE_CANDIDATE_MANIFEST.md`  
Closure: `docs/V2_18_CLOSURE_CERTIFICATION.md`

### Security gate V2-18.10

O dependency audit detectou vulnerabilidades reais em `cryptography 47.0.0`. A faixa foi elevada para `cryptography>=50,<51`, e o gate final instalou `50.0.1`.

Gate final do bloco:

- run `34791936752`;
- job `103817664298`;
- Ruff PASS;
- Mypy PASS — **126 source files**;
- Bandit Medium/High PASS com triagem B608 documentada/protegida por regressão;
- pip-audit PASS — **No known vulnerabilities found** no runtime auditado;
- Pytest **741 PASS em 5.43s**.

## Gate humano de produção/cutover

A V2 está internamente preparada para Release Candidate e rehearsal governado, mas **NÃO está autorizada a executar produção/cutover real**.

Não desligar legado, congelar writer real, migrar banco real, alterar DNS/endpoint, usar segredo real, emitir documento real ou promover `PRODUCTION_APPROVED` sem autorização humana específica e pré-condições reais satisfeitas.

## Sequência restante

`AUDITORIA FINAL 0–100% → GATE FINAL DO HEAD DOCUMENTAL → FECHAR PR CI #23 SEM MERGE → NEUTRALIZAR BRANCH CI → PARAR`

## Governança preservada

**SEM MERGE. SEM Ready/auto-merge. SEM deploy real. SEM produção real. SEM cutover real. SEM migração produtiva. SEM segredo real. SEM homologação externa inventada. SEM promoção indevida de `PRODUCTION_APPROVED`.**
