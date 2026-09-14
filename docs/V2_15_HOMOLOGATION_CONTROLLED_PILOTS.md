# V2-15 — HOMOLOGAÇÃO + PILOTOS CONTROLADOS

Status: **BLOQUEADA PARCIAL — B0-B6 CONCLUÍDOS/CERTIFICADOS INTERNAMENTE; DEPENDÊNCIAS EXTERNAS PENDENTES**  
Branch: `v2/homologation-controlled-pilots`  
Base certificada: `v2/system-hardening` @ `15426a4460ed18c8861c807b92b98c6cfecb3126`  
PR: **#16 OPEN / DRAFT / NÃO MERGEADA**  
Auditoria vinculante: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.  
Fechamento: `docs/V2_15_CLOSURE_CERTIFICATION.md`.

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
6. **Certificação/Fechamento — CONCLUÍDO/CERTIFICADO INTERNAMENTE.**

## Gates certificados

- B0: SHA `87af3e9c96b135142d4ea41118c3463c4223f3d9`, run `34776022773`, job `103774161682`, 109 source files, 592 PASS em 8.42s.
- B1: SHA `4bd07f94db7c0d5e05c7896adbfc8ff80d377ac3`, run `34776243989`, job `103774775120`, 110 source files, 597 PASS em 6.19s.
- B2: SHA `ec5a00dff67710a2d20e7931665e15e94d6de77b`, run `34776372599`, job `103775124030`, 110 source files, 601 PASS em 22.18s.
- B3: SHA `5507d4ea4c721af4ea77b576e162c684b551eb38`, run `34776525383`, job `103775530828`, 110 source files, 605 PASS em 6.94s.
- B4: SHA `2c152f0a86d4a80a97f91125bc9e9bbc50ee993a`, run `34777347753`, job `103777774112`, 110 source files, 611 PASS em 6.27s.
- B5: SHA `d7fa063c8a842480179b178a1e45f37061fe8e18`, run `34777597412`, job `103778446003`, 111 source files, 616 PASS em 6.82s.
- B6 final: SHA `a1c539081236bb3f8df9afb096c4e78efcb8374f`, run `34777811652`, job `103779032887`, 111 source files, **620 PASS em 21.21s**.

Todos os gates tiveram Install/Ruff/Mypy/Pytest PASS. O warning GitHub Actions Node 20→24 foi informativo e não afetou a certificação.

## Resultado B4 — NFS-e

`docs/V2_15_NFSE_HOMOLOGATION_MATRIX.md` certifica internamente código IBGE municipal obrigatório, binding/provider/operação exatos, credenciais provider-scoped, restart durability, fail-closed para município/provider/environment incompatíveis e unknown authorization outcome sem blind retry. Não existe fallback município→UF, provider default, cross-provider ou `HOMOLOGATION`→`PRODUCTION`.

## Resultado B5 — Pilotos controlados

`docs/V2_15_B5_CONTROLLED_PILOTS_GO_NO_GO.md` certifica pilot scope explícito, allowlist, S2S autorizado, readiness técnico, provider binding exato, kill-switch durável, audit trail e estados `GO_INTERNAL`, `NO_GO` e `BLOCKED_EXTERNAL`. O piloto e provider/documento/operação podem ser desabilitados por configuração, sem alteração de código.

## Resultado B6 — fechamento

A suíte `tests/homologation/test_v2_15_closure.py` certifica migrations explícitas, SecretReference sem material secreto, proibição de evidência oficial inventada, `HOMOLOGATION` only e ausência de promoção automática de produção/customer-specific branching nas superfícies novas.

Após o gate final, o CI foi restaurado no commit `bca2b21103e0cc9232daa33f492535cd9c0fb93e` ao blob governado exato `b161340d7164afcbf3da0eb0327135528a39450c`: `workflow_dispatch` only + `permissions: contents: read`.

## Evidência externa e classificação final

Nenhuma credencial/certificado/CSC real, endpoint externo oficial autorizado, resposta oficial de SEFAZ/prefeitura/provider ou piloto externo foi executado. Portanto a classificação verdadeira é:

**V2-15 — BLOQUEADA PARCIAL — TRABALHO INTERNO CONCLUÍDO/CERTIFICADO; DEPENDÊNCIAS EXTERNAS PENDENTES.**

Nenhum provider, UF, município ou operação é declarado oficialmente homologado. `external_official` permanece falso sem evidência real.

## Governança de saída

**PR #16 permanece OPEN/DRAFT/não mergeada. Sem Ready, auto-merge, deploy, produção, endpoint produtivo, cutover, segredo real, homologação externa inventada ou promoção de `PRODUCTION_APPROVED`. V2-16 NÃO INICIADA nesta autorização.**
