# V2-15 — HOMOLOGAÇÃO + PILOTOS CONTROLADOS

Status: **B0-B5 CONCLUÍDOS/CERTIFICADOS INTERNAMENTE — B6 EM FECHAMENTO**  
Branch: `v2/homologation-controlled-pilots`  
Base certificada: `v2/system-hardening` @ `15426a4460ed18c8861c807b92b98c6cfecb3126`  
PR: **#16 OPEN / DRAFT / NÃO MERGEADA**  
Auditoria vinculante: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

## Objetivo e regra comercial superior

A V2-15 transforma readiness técnico em readiness operacional governado sem confundir teste interno com homologação oficial. **Onboarding de cliente é configuração, não desenvolvimento.** Tudo que varia por host/tenant/unidade/ambiente/documento/jurisdição/município/provider/credencial/operação deve ser resolvido por configuração persistida quando a capacidade já existe. Regras fiscais/legais permanecem em catálogos governados/versionados; não são campos normativos livres do tenant.

Regras vinculantes: somente `HOMOLOGATION` nos pilotos desta fase; nenhum endpoint/emissão de produção; nenhum segredo real no Git; Control Plane persiste referências, não material secreto; NFS-e é município/provider-specific; ausência/ambiguidade falha fechado; `external_official` só pode ser verdadeiro com evidência externa real; readiness técnico nunca promove `PRODUCTION_APPROVED`.

## Blocos

0. **Commercial Configurability + Zero-Code Customer Onboarding — CONCLUÍDO/CERTIFICADO.**
1. **Homologation Environment Readiness — CONCLUÍDO/CERTIFICADO INTERNAMENTE.**
2. **NF-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE.**
3. **NFC-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE.**
4. **NFS-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE.**
5. **Pilotos Controlados + Go/No-Go — CONCLUÍDO/CERTIFICADO INTERNAMENTE.**
6. **Certificação/Fechamento — EM EXECUÇÃO; gate final pendente.**

## Gates certificados

- B0 recertificação limpa: SHA `87af3e9c96b135142d4ea41118c3463c4223f3d9`, run `34776022773`, job `103774161682`, Mypy **109 source files**, **592 PASS em 8.42s**.
- B1: SHA `4bd07f94db7c0d5e05c7896adbfc8ff80d377ac3`, run `34776243989`, job `103774775120`, Mypy **110 source files**, **597 PASS em 6.19s**.
- B2: SHA `ec5a00dff67710a2d20e7931665e15e94d6de77b`, run `34776372599`, job `103775124030`, Mypy **110 source files**, **601 PASS em 22.18s**.
- B3: SHA `5507d4ea4c721af4ea77b576e162c684b551eb38`, run `34776525383`, job `103775530828`, Mypy **110 source files**, **605 PASS em 6.94s**.
- B4: SHA `2c152f0a86d4a80a97f91125bc9e9bbc50ee993a`, run `34777347753`, job `103777774112`, Mypy **110 source files**, **611 PASS em 6.27s**.
- B5: SHA `d7fa063c8a842480179b178a1e45f37061fe8e18`, run `34777597412`, job `103778446003`, Mypy **111 source files**, **616 PASS em 6.82s**.

Todos esses gates tiveram Install/Ruff/Mypy/Pytest PASS. O warning GitHub Actions Node 20→24 foi informativo e não afetou os resultados.

## B4 — NFS-e

Matriz: `docs/V2_15_NFSE_HOMOLOGATION_MATRIX.md`. A certificação exige código IBGE municipal, binding/provider/operação exatos, credenciais provider-scoped, restart durability, fail-closed para município/provider/environment incompatíveis e unknown authorization outcome sem blind retry. Nenhum município/provider foi declarado oficialmente homologado.

## B5 — Pilotos controlados

Runbook: `docs/V2_15_B5_CONTROLLED_PILOTS_GO_NO_GO.md`. O runtime `controlled_pilots.py` compõe S2S autorizado, readiness técnico, provider binding exato, allowlist de operações, kill-switch durável e audit trail. Estados internos certificados: `GO_INTERNAL`, `NO_GO` e `BLOCKED_EXTERNAL`. O kill-switch `pilot.<pilot_id>` e o disable exato de provider/documento/operação são configuration-driven e sobrevivem a restart.

## Evidência externa e classificação esperada

Nenhuma credencial/certificado real, endpoint externo autorizado, resposta oficial de SEFAZ/prefeitura/provider ou piloto externo foi executado nesta autorização. Portanto, mesmo com o trabalho interno integralmente verde, o fechamento esperado é:

**V2-15 — BLOQUEADA PARCIAL — TRABALHO INTERNO CONCLUÍDO/CERTIFICADO; DEPENDÊNCIAS EXTERNAS PENDENTES.**

Esse estado não é falha de engenharia: preserva a distinção entre certificação interna e homologação oficial.

## B6 — fechamento

A suíte `tests/homologation/test_v2_15_closure.py` adiciona invariantes de fechamento para migrations, SecretReference sem material secreto, proibição de evidência oficial inventada, `HOMOLOGATION` only e ausência de promoção de produção/customer-specific branching nas superfícies novas.

O CI governado foi reconciliado ao blob histórico exato `b161340d7164afcbf3da0eb0327135528a39450c` (`workflow_dispatch` only + `permissions: contents: read`) antes do gate final. O gate B6/documental completo ainda deve ser executado e registrado em `docs/V2_15_CLOSURE_CERTIFICATION.md`.

## Governança

Mesmo após B6 verde: **não mergear PR #16, não marcar Ready, não habilitar auto-merge, não fazer deploy, produção, cutover, homologação oficial fictícia ou promoção de `PRODUCTION_APPROVED`; não iniciar V2-16 nesta autorização.**
