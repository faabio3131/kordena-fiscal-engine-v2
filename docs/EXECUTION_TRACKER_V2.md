# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO — dependências externas V2-15 pendentes**  
Última fase integralmente concluída sem dependência externa: **V2-14 — Hardening sistêmico**  
Fase atual: **V2-15 — BLOQUEADA PARCIAL; B0-B6 INTERNAMENTE CONCLUÍDOS/CERTIFICADOS; EXTERNO PENDENTE**

> Snapshot pré-V2-15: `docs/history/EXECUTION_TRACKER_V2_PRE_V2_15.md`. Plano: `docs/V2_15_HOMOLOGATION_CONTROLLED_PILOTS.md`. Fechamento: `docs/V2_15_CLOSURE_CERTIFICATION.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. A PR #16 permanece OPEN/DRAFT/não mergeada. Deploy, produção real, cutover e promoção de `PRODUCTION_APPROVED` continuam proibidos. Homologação oficial externa exige evidência externa real; teste sintético não substitui resposta oficial.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-12 | Gateway/Signer/Vault adapters | **CONCLUÍDO** | PR #13 Draft; 508 PASS |
| V2-13 | Observabilidade + Compliance Operations | **CONCLUÍDO** | PR #14 Draft; 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 Draft; 582 PASS; doc gate 582 PASS |
| V2-15 | Homologação + pilotos controlados | **BLOQUEADO PARCIAL — INTERNO CERTIFICADO** | PR #16 Draft; B0-B6 internos verdes; B6 final 620 PASS; externo oficial pendente |
| V2-16 | Integração produtos FM | **BLOQUEADO PARCIAL / NÃO INICIADO** | exige nova autorização; verificar readiness real de cada produto antes de integrar |
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

CI restaurado após o gate no commit `bca2b21103e0cc9232daa33f492535cd9c0fb93e` ao blob governado exato `b161340d7164afcbf3da0eb0327135528a39450c`: `workflow_dispatch` only + `permissions: contents: read`.

## Evidência externa / bloqueios reais

Nenhum provider, UF, município ou operação foi declarado oficialmente homologado. Não foram fornecidos/consumidos segredos reais, certificados privados reais, CSC real, provider credentials reais, endpoints produtivos ou respostas externas oficiais. Nenhum piloto externo real foi executado.

Portanto a decisão formal é: **V2-15 BLOQUEADA PARCIAL — TRABALHO INTERNO CONCLUÍDO/CERTIFICADO; DEPENDÊNCIAS EXTERNAS PENDENTES.** O bloqueio restante é externo e explícito, não uma falha técnica do Core.

## Governança preservada

**SEM MERGE da PR #16. SEM Ready/auto-merge. SEM deploy. SEM produção real. SEM cutover. SEM segredo real no repositório. SEM homologação externa inventada. SEM promoção de `PRODUCTION_APPROVED`. V2-16 NÃO INICIADA e exige nova autorização explícita.**
