# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO CONTROLADA — V2-15 externa pendente; V2-16 internamente fechada com bloqueios reais de produto; V2-17 preparatória autorizada**  
Última fase integralmente concluída sem bloqueio externo: **V2-14 — Hardening sistêmico**  
Fase atual: **V2-16 — BLOQUEADA PARCIAL; TODO O TRABALHO INTERNO EXECUTÁVEL B1-B7 CONCLUÍDO/CERTIFICADO**

> Snapshot pré-V2-15: `docs/history/EXECUTION_TRACKER_V2_PRE_V2_15.md`. V2-15: `docs/V2_15_CLOSURE_CERTIFICATION.md`. V2-16: `docs/V2_16_PRODUCT_INTEGRATION_EXECUTION.md` + `docs/V2_16_CLOSURE_CERTIFICATION.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. PRs permanecem Draft/não mergeadas. Deploy, produção real, cutover, migração produtiva e promoção de `PRODUCTION_APPROVED` continuam proibidos. Homologação oficial externa exige evidência externa real; teste sintético não substitui resposta oficial.

| Fase | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-00..V2-11 | Equivalência → Control Plane | **CONCLUÍDO** | histórico preservado nas PRs #1-#12 |
| V2-12 | Gateway/Signer/Vault adapters | **CONCLUÍDO** | PR #13 Draft; 508 PASS |
| V2-13 | Observabilidade + Compliance Operations | **CONCLUÍDO** | PR #14 Draft; 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 Draft; 582 PASS |
| V2-15 | Homologação + pilotos controlados | **BLOQUEADO PARCIAL — INTERNO CERTIFICADO** | PR #16 Draft; B0-B6 verdes; 620 PASS; externo oficial pendente |
| V2-16 | Integração produtos FM | **BLOQUEADO PARCIAL — INTERNO B1-B7 CERTIFICADO** | PR #17 Draft; B7 646 PASS; bloqueios de produto explicitados |
| V2-17 | Convergência/cutover | **PREPARAÇÃO AUTORIZADA** | cutover real proibido até pré-condições + aprovação humana |
| V2-18 | Produto comercial independente | PENDENTE | não autorizado |

## V2-15 — certificação interna acumulada

- B0 Commercial Configurability + Zero-Code Onboarding: SHA `87af3e9c96b135142d4ea41118c3463c4223f3d9`, run `34776022773`, **592 PASS**.
- B1 Homologation Environment Readiness: SHA `4bd07f94db7c0d5e05c7896adbfc8ff80d377ac3`, run `34776243989`, **597 PASS**.
- B2 NF-e Matrix: SHA `ec5a00dff67710a2d20e7931665e15e94d6de77b`, run `34776372599`, **601 PASS**.
- B3 NFC-e Matrix: SHA `5507d4ea4c721af4ea77b576e162c684b551eb38`, run `34776525383`, **605 PASS**.
- B4 NFS-e Matrix: SHA `2c152f0a86d4a80a97f91125bc9e9bbc50ee993a`, run `34777347753`, **611 PASS**.
- B5 Pilotos Controlados/Go-No-Go: SHA `d7fa063c8a842480179b178a1e45f37061fe8e18`, run `34777597412`, **616 PASS**.
- B6 Closure: SHA `a1c539081236bb3f8df9afb096c4e78efcb8374f`, run `34777811652`, **620 PASS**.

Estado formal: **BLOQUEADA PARCIAL — INTERNO CERTIFICADO; EXTERNO OFICIAL PENDENTE**. Nenhum provider/UF/município é oficialmente homologado sem evidência externa.

## V2-16 — execução acumulada

### B1 — Contrato de integração — CONCLUÍDO/CERTIFICADO

SHA `c23d49997a4344363720436374a8d9476e665262`, run `34779681157`: Install/Ruff/Mypy/Pytest PASS.

### B2 — Kordena — BLOQUEADO POR PRÉ-REQUISITO REAL

PR Kordena #118 permanece OPEN/DRAFT e funcionalmente PARCIAL. Web Premium/FISC-20 ainda impede integração runtime/cutover.

### B3 — Iron Fit — CONCLUÍDO/CERTIFICADO

PR #48 Draft. SHA `2be8321eeb066f0296ba812faab0a098c32f0632`, run `34780329013`: dependency audit, Prisma, lint/typecheck, build e smoke PASS.

### B4 — Vendedor IA — BLOQUEADO PARCIAL / INTERNO CERTIFICADO

`Payment.status = CONFIRMED` é autoridade de liquidação. Handoff `fm.vendedor-ia` certificado sem adivinhar NF-e/NFC-e. Faltam CPF/CNPJ/endereço fiscal e fatos suficientes para classificação segura. PR #1 Draft. SHA `b4b7fb05236c481d5626de5386864ae6f5227418`, run `34783831679`: **157 PASS** + security/Docker smoke.

### B5 — CampaIA — BLOQUEADO PARCIAL / INTERNO CERTIFICADO

Adapter `SettledOwnBillingFact` fail-closed certificado sem transformar media spend em receita. Falta autoridade real de faturamento/pagamento próprio. PR #1 Draft. SHA `bdebbc3558ff8b07c1a38e0cb728be0dc3635c4b`, run `34784021431`: **347 PASS** + AsyncAPI 24 eventos.

### B6 — Adapter Contract Pack / novos produtos — CONCLUÍDO/CERTIFICADO

`ProductOnboardingDeclaration`, `ProductMutationPreflight` e validações fail-closed. Primeiro gate encontrou cinco Ruff; corrigido sem relaxamento. SHA `878738c172ab31e3f81618a95986370b17d0e602`, run `34784375685`: 114 source files, **639 PASS**.

### B7 — E2E + Multi-Product Cross-Certification + Closure — CONCLUÍDO/CERTIFICADO

A divergência histórica do B6 foi reconciliada sem reescrever entregas. Nova suíte `tests/test_v2_16_cross_product_closure.py` certifica quatro hosts, três document kinds, múltiplas operações, isolamento host/tenant/unit/environment, correlation/causation, idempotência, spoofing fail-closed e readiness obrigatório.

SHA de implementação `5afb3d9af8879f17b451e757f53ca41796e843e7`, run `34785216450`, job `103799337982`: Install PASS; Ruff PASS; Mypy PASS em **114 source files**; Pytest **646 PASS em 6.44s**.

Diff V2-15 → gate B7: **20 ahead / 0 behind**, merge-base exato `33e34866bc6e8c736c585c45101ce214816e0594`.

Closure: `docs/V2_16_CLOSURE_CERTIFICATION.md`.

## Estado formal da V2-16

**V2-16 — BLOQUEADA PARCIAL — TODO O TRABALHO INTERNO EXECUTÁVEL CONCLUÍDO/CERTIFICADO; DEPENDÊNCIAS DE PRODUTO/EXTERNAS DOCUMENTADAS.**

Os bloqueios de Kordena, Vendedor IA e CampaIA não são convertidos em verde. Eles também não impedem o trabalho preparatório interno da V2-17, mas continuam impedindo cutover real quando fizerem parte das pré-condições obrigatórias.

## Evidência externa / bloqueios reais

Não foram fornecidos/consumidos certificados privados reais, CSC real, provider credentials reais, endpoints produtivos ou respostas externas oficiais. Nenhum piloto externo real foi executado. Nenhuma homologação sintética é tratada como homologação oficial.

## Governança preservada

**SEM MERGE. SEM Ready/auto-merge. SEM deploy. SEM produção real. SEM cutover real. SEM migração produtiva. SEM segredo real. SEM homologação externa inventada. SEM promoção indevida de `PRODUCTION_APPROVED`. V2-18 NÃO INICIADA.**
