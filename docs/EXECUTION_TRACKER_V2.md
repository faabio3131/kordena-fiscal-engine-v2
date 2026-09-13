# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-11 — Control Plane independente**  
Fase atual: **V2-12 — Gateway/Signer/Vault production adapters — EM EXECUÇÃO**

> Snapshot imediatamente anterior à V2-12: `docs/history/EXECUTION_TRACKER_V2_PRE_V2_12.md`. Fechamento V2-11: `docs/V2_11_CLOSURE_CERTIFICATION.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. Nenhum merge, deploy, promoção ou cutover é automático.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-00 | Clone técnico + equivalência | **CONCLUÍDO** | PR #1 Draft; `9da776e353b31d03a8453a83c6e61a736e6ed00b`; 215 PASS |
| V2-01 | Identidade FM + neutralização de branding | **CONCLUÍDO** | PR #2 Draft; `ac6ad42eeacca2a84675e7e57e04b18414cadf36`; 215 PASS |
| V2-02 | Host namespace + fiscal account binding | **CONCLUÍDO** | PR #3 Draft; `4fa8a2a8c74db65622099cd7dca43d2e8d19aea3`; 239 PASS |
| V2-03 | Fiscal Operation Contract genérico | **CONCLUÍDO** | PR #4 Draft; `598a2ec83aecd27a5427f3e1e401532e8be2696a`; 262 PASS |
| V2-04 | FM Fiscal Bridge | **CONCLUÍDO** | PR #5 Draft; `86689b3d3d7d47740b56bcc22594aa8c8e0b08c7`; 269 PASS |
| V2-05 | Auth S2S + workload identity + webhook security | **CONCLUÍDO** | PR #6 Draft; `196928d1b0cfe896df0c4741839ce72258f8f4d4`; 290 PASS |
| V2-06 | Capability & Readiness API | **CONCLUÍDO** | PR #7 Draft; `e6c7b2b9e507116ef4919812153f8e54f84173f3`; 305 PASS |
| V2-07 | Application service + persistência durável | **CONCLUÍDO** | PR #8 Draft; `999ba84b9c25988441867820bfe8af0571269548`; 309 PASS |
| V2-08 | Events/Webhooks/Inbox/Outbox | **CONCLUÍDO** | PR #9 Draft; `bc77ee4cf2b7151d06c09cf32ca9168363ece1c7`; 337 PASS |
| V2-09 | Modularização de verticais | **CONCLUÍDO** | PR #10 Draft; `88071fd557199ffd6848312ea5559b0cba415ee1`; 346 PASS |
| V2-10 | Contract Packs multiproduto | **CONCLUÍDO** | PR #11 Draft; `345652ecbfc18c8bd3511cf5b9083ba0dbc259cb`; 397 PASS |
| V2-11 | Control Plane independente | **CONCLUÍDO** | PR #12 Draft; gate `eed6b056e9d1941da435179c5eaf805c261f6622`; run `34736942613`; 85 source files; 437 PASS |
| V2-12 | Gateway/Signer/Vault production adapters | **EM EXECUÇÃO** | PR #13 Draft; B1 `961ee84aa28f58ce933d2dd899bfd013c801da1c` / `34758902465` / 447 PASS; B2 `f27ae85ac1dbf0b5cf47eea96d1437585b37cb92` / `34759157421` / 91 source / 459 PASS; CI restaurado |
| V2-13 | Observabilidade + Compliance Operations | PENDENTE | depende V2-12 |
| V2-14 | Hardening sistêmico | PENDENTE | regressão/carga/falhas/segurança |
| V2-15 | Homologação + pilotos controlados | PENDENTE | depende V2-14 |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | depende do Core universal certificado e readiness dos produtos |
| V2-17 | Convergência/cutover + arquivamento original | PENDENTE | depende de equivalência e integrações certificadas |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## V2-12 — Gateway/Signer/Vault Production Adapters

### Bootstrap — CONCLUÍDO

- branch `v2/production-adapters` criada exatamente de `0439246151c7edc959615361c0275961e11c3af0`;
- snapshot pré-fase em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_12.md`;
- plano da fase em `docs/V2_12_PRODUCTION_ADAPTERS.md`;
- PR #13 Draft stacked sobre `v2/control-plane`.

### Bloco 1 — Vault/KMS abstraction + Secret Resolution Boundary — CONCLUÍDO/CERTIFICADO

- package `kordena_fiscal.vault` provider-neutral;
- `SecretResolutionContext` explícito por host/tenant/unit/environment/kind/purpose/workload;
- `FiscalSecretVault` port e `SecretResolutionService` sobre SecretReference persistida;
- material efêmero tipado e redigido em repr;
- adapter sintético em memória, sem filesystem/env/persistência;
- cross-host/cross-tenant/cross-unit/cross-environment fail-closed;
- schema Control Plane permanece reference-only;
- restart preserva reference, nunca material runtime.

Primeira tentativa `34758852638` / job `103727925782`: Ruff/Mypy verdes, 446 PASS + 1 FAIL por expectativa de erro cross-tenant. Correção passou a ocultar scopes inexistentes como reference indisponível, reduzindo enumeração administrativa.

Gate definitivo: SHA `961ee84aa28f58ce933d2dd899bfd013c801da1c`, run `34758902465`, job `103728060621`, **88 source files, 447 PASS em 2.15s**. CI restaurado em `cb399d0c74ae5925c4d89412a4760472fe7ab430`.

### Bloco 2 — Signer Boundary + assinatura por SecretReference — CONCLUÍDO/CERTIFICADO

- package `kordena_fiscal.signing` provider-neutral;
- `FiscalSignatureRequest` e `FiscalSignatureResult` tipados, com representações sanitizadas;
- signer recebe conteúdo canônico e `SecretReference`, nunca segredo direto;
- `CryptographyFiscalDocumentSigner` resolve PKCS#12 somente através de `SecretResolutionService`/Vault;
- RSA-SHA256 e ECDSA-SHA256 suportados conforme chave; NF-e/NFC-e explícitos;
- NFS-e permanece fail-closed até adapter/provider específico declarar capability adequada;
- verificação detecta tampering e valida referência/fingerprint;
- cross-tenant/cross-unit/cross-environment/kind bloqueados;
- nenhum PFX/P12/PEM/KEY persistido em fixture;
- signer sem UoW próprio e sem autoridade de readiness;
- dependência adicionada: `cryptography>=44,<48`, resolvida como 47.0.0 no gate, para evitar criptografia/PFX artesanal.

Gate definitivo: SHA `f27ae85ac1dbf0b5cf47eea96d1437585b37cb92`, run `34759157421`, job `103728746009`, **91 source files, 459 PASS em 3.05s**. Bloco 1 -> Bloco 2: +12 testes; diff do checkpoint documental do B1 ao gate B2: 8 commits à frente, 0 atrás. CI restaurado em `750dbb7e2e7f34fd55fe8a79fbda7dd422af9fb7`.

### Próximos blocos V2-12 — PENDENTES

- adapters concretos de providers/gateways;
- CSC/provider credentials por unidade/ambiente conforme provider;
- timeout/retry/circuit breaker;
- homologation gates por documento/jurisdição;
- certificação cross-provider;
- fechamento end-to-end da V2-12.

## Governança preservada

PR #13 permanece Draft. V2-12 permanece **EM EXECUÇÃO — BLOCOS 1 E 2 CERTIFICADOS**. Nenhum merge, deploy, produção real, homologação externa, promoção ou cutover foi executado.
