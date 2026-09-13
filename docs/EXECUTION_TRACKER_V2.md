# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO CONTROLADA — V2-15 externa pendente; V2-16 parcialmente certificada**  
Última fase integralmente concluída sem bloqueio externo: **V2-14 — Hardening sistêmico**  
Fase atual: **V2-16 — BLOQUEADA PARCIAL; B1/B3 CERTIFICADOS; B2 KORDENA BLOQUEADO; B4/B5 INTERNAMENTE CERTIFICADOS COM BLOQUEIOS DE DOMÍNIO; B6 EM CERTIFICAÇÃO**

> Snapshot pré-V2-15: `docs/history/EXECUTION_TRACKER_V2_PRE_V2_15.md`. Plano V2-15: `docs/V2_15_HOMOLOGATION_CONTROLLED_PILOTS.md`. Fechamento V2-15: `docs/V2_15_CLOSURE_CERTIFICATION.md`. Execução V2-16: `docs/V2_16_PRODUCT_INTEGRATION_EXECUTION.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. A PR #16 permanece OPEN/DRAFT/não mergeada e preserva o checkpoint certificado da V2-15. PRs de integração da V2-16 também permanecem Draft/não mergeadas. Deploy, produção real, cutover e promoção de `PRODUCTION_APPROVED` continuam proibidos. Homologação oficial externa exige evidência externa real; teste sintético não substitui resposta oficial.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-12 | Gateway/Signer/Vault adapters | **CONCLUÍDO** | PR #13 Draft; 508 PASS |
| V2-13 | Observabilidade + Compliance Operations | **CONCLUÍDO** | PR #14 Draft; 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 Draft; 582 PASS; doc gate 582 PASS |
| V2-15 | Homologação + pilotos controlados | **BLOQUEADO PARCIAL — INTERNO CERTIFICADO** | PR #16 Draft; B0-B6 internos verdes; B6 final 620 PASS; externo oficial pendente |
| V2-16 | Integração produtos FM | **BLOQUEADO PARCIAL / EM CERTIFICAÇÃO B6** | Core PR #17 Draft; Kordena bloqueado; Iron certificado; Vendedor/CampaIA parciais; B6 em gate |
| V2-17 | Convergência/cutover | PENDENTE | NÃO AUTORIZADO |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## V2-15 — certificação interna acumulada

### B0 — Commercial Configurability + Zero-Code Onboarding — CONCLUÍDO/CERTIFICADO

Novo cliente = configuração, não desenvolvimento. SecretReference provider-scoped para CREDENTIALS/CSC, ProviderBinding durável, perfis fiscais, módulos, webhooks, workload identity/grants, homologation evidence, numbering e runtime policies persistidos/governados. Runtime concreto separado do núcleo do Control Plane.

Gate: SHA `87af3e9c96b135142d4ea41118c3463c4223f3d9`, run `34776022773`, job `103774161682`: 109 source files, **592 PASS em 8.42s**.

### B1 — Homologation Environment Readiness — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Gate: SHA `4bd07f94db7c0d5e05c7896adbfc8ff80d377ac3`, run `34776243989`, job `103774775120`: 110 source files, **597 PASS em 6.19s**.

### B2 — NF-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Gate: SHA `ec5a00dff67710a2d20e7931665e15e94d6de77b`, run `34776372599`, job `103775124030`: 110 source files, **601 PASS em 22.18s**.

### B3 — NFC-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Gate: SHA `5507d4ea4c721af4ea77b576e162c684b551eb38`, run `34776525383`, job `103775530828`: 110 source files, **605 PASS em 6.94s**.

### B4 — NFS-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Documento: `docs/V2_15_NFSE_HOMOLOGATION_MATRIX.md`. Município IBGE obrigatório, provider/operação/jurisdição exatos, sem fallback município→UF/provider-default/cross-provider/HOMOLOGATION→PRODUCTION, credenciais provider-scoped, restart durability e unknown outcome sem retry cego.

Gate: SHA `2c152f0a86d4a80a97f91125bc9e9bbc50ee993a`, run `34777347753`, job `103777774112`: 110 source files, **611 PASS em 6.27s**.

### B5 — Pilotos Controlados + Go/No-Go — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Documento: `docs/V2_15_B5_CONTROLLED_PILOTS_GO_NO_GO.md`. Pilot scope explícito, allowlist, HOMOLOGATION-only, S2S autorizado, technical readiness, provider binding exato, kill-switch durável, audit trail e estados `GO_INTERNAL`, `NO_GO`, `BLOCKED_EXTERNAL`.

Gate: SHA `d7fa063c8a842480179b178a1e45f37061fe8e18`, run `34777597412`, job `103778446003`: 111 source files, **616 PASS em 6.82s**.

### B6 — Certificação/Fechamento — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Suíte: `tests/homologation/test_v2_15_closure.py`. Gate final SHA `a1c539081236bb3f8df9afb096c4e78efcb8374f`, run `34777811652`, job `103779032887`: Install PASS, Ruff PASS, Mypy PASS em **111 source files**, Pytest **620 PASS em 21.21s**.

CI restaurado após o gate ao blob governado `b161340d7164afcbf3da0eb0327135528a39450c`: `workflow_dispatch` only + `permissions: contents: read`.

## V2-16 — execução acumulada

### B1 — Contrato de integração — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Fronteira `kordena_fiscal.integrations` ligada aos Product Contract Packs certificados e ao OpenAPI atual do FM Fiscal Bridge v1. Gate certificado: SHA `c23d49997a4344363720436374a8d9476e665262`, run `34779681157`: Install/Ruff/Mypy/Pytest PASS.

### B2 — Integração Kordena — BLOQUEADA POR PRÉ-REQUISITO REAL

O Plano Mestre exige V1 Web Premium liberada para FISC-20. A PR Kordena #118 permanece OPEN/DRAFT. Nenhum acoplamento runtime foi introduzido e nenhum verde artificial foi declarado.

### B3 — Integração Iron Fit — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Branch `feat/fisc-v2-16-iron-integration`, PR #48 OPEN/DRAFT. Gate final SHA `2be8321eeb066f0296ba812faab0a098c32f0632`, run `34780329013`: npm ci, dependency audit, Prisma generate, lint/typecheck, build e smoke tests PASS.

### B4 — Integração Vendedor IA — BLOQUEADO PARCIAL / INTERNO CERTIFICADO

Autoridade de liquidação: `Payment.status = CONFIRMED`, com Quote ACCEPTED e snapshot de itens como fonte comercial. Handoff `fm.vendedor-ia` + pack `sales` implementado sem adivinhar NF-e/NFC-e. Produtos liquidados ficam `PENDING_FISCAL_CLASSIFICATION`; SERVICE fica `BLOCKED_UNSUPPORTED_SALE_CONTENT`.

Bloqueio real: Customer não possui CPF/CNPJ/endereço fiscal e o domínio atual não contém fatos suficientes para escolher NF-e versus NFC-e.

Branch `feat/fisc-v2-16-vendedor-integration`, PR Vendedor IA #1 OPEN/DRAFT. HEAD `b4b7fb05236c481d5626de5386864ae6f5227418`, run `34783831679`, job `103795573887`: install/build/typecheck PASS; **34 arquivos / 157 testes PASS**; runtime security PASS; Docker smoke PASS.

### B5 — Integração CampaIA — BLOQUEADO PARCIAL / INTERNO CERTIFICADO

O produto não possui ainda autoridade de faturamento/assinatura/pagamento próprio. Campanha, orçamento e media spend não foram convertidos artificialmente em receita. Foi implementada seam fail-closed `SettledOwnBillingFact` para futuro evento autoritativo, mapeando somente service-billing/saas-billing para NFS-e com idempotência, binding e readiness obrigatórios.

Branch `feat/fisc-v2-16-campaia-integration`, PR CampaIA #1 OPEN/DRAFT. HEAD `bdebbc3558ff8b07c1a38e0cb728be0dc3635c4b`, run `34784021431`, job `103796103296`: **267 core tests PASS + 80 API tests PASS = 347 PASS**; AsyncAPI PASS com 24 eventos verificados end-to-end.

### B6 — Adapter Contract Pack / novos produtos FM — EM CERTIFICAÇÃO

A fundação existente foi reutilizada; não foi criado framework paralelo. Foram adicionados:

- `ProductOnboardingDeclaration` + `certify_product_onboarding(...)`;
- `ProductMutationPreflight` + `validate_product_mutation_preflight(...)`;
- fail-closed para pack/host/use case/operação/documento/ação/escopo/idempotência/binding/capability/readiness;
- prova sintética não registrada no catálogo real;
- `docs/V2_16_ADAPTER_PACK_ONBOARDING.md`.

O primeiro gate de B6, run `34784287287`, encontrou Ruff vermelho por cinco violações de qualidade (import de Mapping, duas linhas longas e duas assertions genéricas de Exception). O código/testes foram corrigidos sem relaxar regra ou gate. Um segundo run intermediário ainda avaliou commit anterior à correção completa; a certificação final permanece pendente do próximo gate sobre o HEAD integral corrigido.

## Estado formal provisório da V2-16

**V2-16 — BLOQUEADA PARCIAL — B1/B3 INTERNAMENTE CONCLUÍDOS; B2 KORDENA BLOQUEADO; B4/B5 INTERNAMENTE CERTIFICADOS COM BLOQUEIOS REAIS DE DOMÍNIO; B6 EM CERTIFICAÇÃO.**

## Evidência externa / bloqueios reais

Nenhum provider, UF, município ou operação foi declarado oficialmente homologado. Não foram fornecidos/consumidos segredos reais, certificados privados reais, CSC real, provider credentials reais, endpoints produtivos ou respostas externas oficiais. Nenhum piloto externo real foi executado.

A V2-15 continua formalmente **BLOQUEADA PARCIAL — TRABALHO INTERNO CONCLUÍDO/CERTIFICADO; DEPENDÊNCIAS EXTERNAS PENDENTES**.

## Governança preservada

**SEM MERGE da PR #16, PR #17, Iron #48, Vendedor IA #1 ou CampaIA #1. SEM Ready/auto-merge. SEM deploy. SEM produção real. SEM cutover. SEM segredo real no repositório. SEM homologação externa inventada. SEM promoção de `PRODUCTION_APPROVED`. V2-17 NÃO INICIADA.**
