# NFCore SP pilot — operation prohibition negative gate (2026-11-04)

## Scope and authority
- Base: `faabio3131/nf-core-v001`, PR #348 HEAD `47410f8cc13243622bae3fc15b6761d4a7546635`.
- Applies ONLY to the three SP pilot municipality codes `3509205`, `3548708`, `3550308` and only to the existing pure pilot route. This guard does not provide provider transport, signature, XML or production authorization.
- No new provider registry, tax rule engine, persistence, API, OAuth, tenant authority or fiscal status.
- Official origin: SEFAZ-SP NF-e/NFC-e service information updated for Ajustes SINIEF 38/2026 and 40/2026: SP has no inutilization of NF-e 55 or NFC-e 65 since 2026-11-01. Confirm again before any official transport release.
  https://portal.fazenda.sp.gov.br/servicos/nfce/

## Current → Target
- Before: the three-city router classified NF-e/NFC-e/NFS-e channels, but had no date-aware negative operation guard and could be misinterpreted as permissive for `inutilize`.
- Now: `require_sp_pilot_operation_policy` checks real timezone-aware execution time at the SP local 2026-11-01 boundary and raises `FiscalValidationError` for NF-e/NFC-e inutilization from that date; rejects NFS-e inutilization outright, malformed route/operation/clock, and forged inconsistent route/channel.
- Returning normally means ONLY "not prohibited by this negative guard". It is NOT positive provider approval. The **real prepared operation path must call this gate before executing the configured adapter**, after the canonical issuer/operation/jurisdiction is resolved (not from a web header).
- Full jurisdiction, regulatory-layout, provider, credentials, certificates and homologation gates remain mandatory.

## Verification and remaining gates
- Synthetic local tests: 30 PASS, including all three cities, two document models, boundary 2026-11-01, timezone-aware clock, NFS-e and rejection of inconsistent context.
- Ruff: PASS. Mypy strict: PASS (one changed source).
- No official traffic, customer secret, deployment, migration, merge, or fiscal activation.
- Require this branch's CI/Governance on exact SHA; integrate only after PR #348 is certified and an authorized integration gate has checked compatibility; do not treat SP-specific rule as general Brazil policy.
- Pending real provider operation composer wiring to use this negative gate; until then do not claim runtime enforces it.

Status: **IMPLEMENTED_NOT_CERTIFIED**, external homologation **BLOCKED_EXTERNAL**.

## Atualização — bloqueio efetivo no gateway canônico (04/11/2026)

A regra negativa de inutilização de NF-e/NFC-e paulista foi ligada ao
`ProviderGatewayService.execute`, **antes** de readiness, seleção de provider,
resolução de segredos e I/O. A aplicação da vedação é estadual, não limitada aos
três municípios do piloto. O mesmo instante do clock governado é usado na
avaliação da regra e no gate de capacidade. Casos sintéticos de duas classes
(modelos 55/65), município do piloto e fora dele, ausência de transporte,
consulta e cancelamento cobrem regressão.

Fonte oficial: https://portal.fazenda.sp.gov.br/servicos/nfe
(Ajustes SINIEF 40/2026 e 38/2026, vigência 01/11/2026).

**Escopo limitado:** essa composição só atua quando o fluxo usa o
`ProviderGatewayService` canônico. O runtime API Web continua sem transporte
oficial e sem credenciais, portanto isso não homologa nem habilita emissão real.
