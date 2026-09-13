# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase totalmente concluída: **V2-14 — Hardening sistêmico**  
Fase atual: **V2-15 — B0-B5 CERTIFICADOS INTERNAMENTE / B6 EM FECHAMENTO**

> Snapshot pré-V2-15: `docs/history/EXECUTION_TRACKER_V2_PRE_V2_15.md`. Plano: `docs/V2_15_HOMOLOGATION_CONTROLLED_PILOTS.md`. Auditoria vinculante: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. A PR #16 permanece OPEN/DRAFT/não mergeada. Deploy, produção real, cutover e promoção de `PRODUCTION_APPROVED` continuam proibidos. Homologação oficial externa exige evidência externa real; teste sintético não substitui resposta oficial.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-12 | Gateway/Signer/Vault adapters | **CONCLUÍDO** | PR #13 Draft; 508 PASS |
| V2-13 | Observabilidade + Compliance Operations | **CONCLUÍDO** | PR #14 Draft; 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 Draft; 582 PASS; doc gate 582 PASS |
| V2-15 | Homologação + pilotos controlados | **EM EXECUÇÃO / FECHAMENTO** | PR #16 Draft; B0-B5 verdes; B6 gate final pendente |
| V2-16 | Integração produtos FM | **BLOQUEADO PARCIAL** | NÃO INICIAR nesta autorização; depende do fechamento V2-15 + readiness dos produtos |
| V2-17 | Convergência/cutover | PENDENTE | NÃO AUTORIZADO |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## V2-15 — estado acumulado

### B0 — Commercial Configurability + Zero-Code Onboarding — CONCLUÍDO/CERTIFICADO

Novo cliente = configuração, não desenvolvimento. SecretReference provider-scoped para CREDENTIALS/CSC, ProviderBinding durável, perfis fiscais, módulos, webhooks, workload identity/grants, homologation evidence, numbering e runtime policies persistidos/governados. Runtime concreto separado do núcleo do Control Plane.

Gate limpo: SHA `87af3e9c96b135142d4ea41118c3463c4223f3d9`, run `34776022773`, job `103774161682`: Install/Ruff/Mypy PASS, **109 source files**, **592 PASS em 8.42s**.

### B1 — Homologation Environment Readiness — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Gate: SHA `4bd07f94db7c0d5e05c7896adbfc8ff80d377ac3`, run `34776243989`, job `103774775120`: **110 source files**, **597 PASS em 6.19s**.

### B2 — NF-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Gate: SHA `ec5a00dff67710a2d20e7931665e15e94d6de77b`, run `34776372599`, job `103775124030`: **110 source files**, **601 PASS em 22.18s**.

### B3 — NFC-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Gate: SHA `5507d4ea4c721af4ea77b576e162c684b551eb38`, run `34776525383`, job `103775530828`: **110 source files**, **605 PASS em 6.94s**.

### B4 — NFS-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Documento: `docs/V2_15_NFSE_HOMOLOGATION_MATRIX.md`.

Certificado: município IBGE obrigatório, provider/operação/jurisdição exatos, sem fallback município→UF/provider-default/cross-provider/HOMOLOGATION→PRODUCTION, credenciais provider-scoped, restart durability e unknown outcome sem retry cego. `external_official=false` sem evidência real.

Gate: SHA `2c152f0a86d4a80a97f91125bc9e9bbc50ee993a`, run `34777347753`, job `103777774112`: Install/Ruff/Mypy PASS, **110 source files**, **611 PASS em 6.27s**.

### B5 — Pilotos Controlados + Go/No-Go — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Documento: `docs/V2_15_B5_CONTROLLED_PILOTS_GO_NO_GO.md`.

Certificado: pilot scope explícito, allowlist, HOMOLOGATION-only, S2S AuthorizedFiscalRequest, technical readiness, provider binding exato, kill-switch durável por piloto/unidade e por provider/documento/operação, audit trail, restart fail-closed e estados `GO_INTERNAL`, `NO_GO`, `BLOCKED_EXTERNAL`.

Gate: SHA `d7fa063c8a842480179b178a1e45f37061fe8e18`, run `34777597412`, job `103778446003`: Install/Ruff/Mypy PASS, **111 source files**, **616 PASS em 6.82s**.

### B6 — Certificação/Fechamento — EM EXECUÇÃO

Suíte de fechamento adicionada em `tests/homologation/test_v2_15_closure.py`. Antes do gate final, o CI foi restaurado ao conteúdo governado histórico exato, blob `b161340d7164afcbf3da0eb0327135528a39450c`, dispatch-only + `permissions: contents: read`, no commit `474155693199905ac42b3aebdc75f6ccfa05bdc3`.

O gate final B6/documental ainda será executado. Se permanecer integralmente verde, o fechamento da fase deve registrar **BLOQUEADA PARCIAL — TRABALHO INTERNO CONCLUÍDO/CERTIFICADO; DEPENDÊNCIAS EXTERNAS PENDENTES**, pois nenhuma homologação oficial externa/piloto externo foi executado nesta autorização.

## Evidência externa / bloqueios reais

Nenhum provider, UF, município ou operação foi declarado oficialmente homologado. Não foram fornecidos/consumidos segredos reais, certificados reais, CSC real, endpoints oficiais autorizados ou respostas externas oficiais. Portanto, o bloqueio restante é externo e explícito, não uma falha técnica do Core.

## Governança preservada

SEM MERGE da PR #16. SEM deploy. SEM produção real. SEM cutover. SEM segredo real no repositório. SEM homologação externa inventada. SEM promoção de `PRODUCTION_APPROVED`. **V2-16 NÃO INICIADA.**
