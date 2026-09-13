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
| V2-12 | Gateway/Signer/Vault production adapters | **EM EXECUÇÃO** | PR #13 Draft; B1 447 PASS; B2 459 PASS; B3 `42f27c67145d2d4469374596d869ffc3ba05f013` / run `34760113452` / job `103731343836` / 93 source / 471 PASS; CI restaurado |
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

Gate: `961ee84aa28f58ce933d2dd899bfd013c801da1c` / run `34758902465` / job `103728060621` / **88 source files / 447 PASS em 2.15s**. CI restaurado em `cb399d0c74ae5925c4d89412a4760472fe7ab430`.

### Bloco 2 — Signer Boundary + assinatura por SecretReference — CONCLUÍDO/CERTIFICADO

Gate: `f27ae85ac1dbf0b5cf47eea96d1437585b37cb92` / run `34759157421` / job `103728746009` / **91 source files / 459 PASS em 3.05s**. CI restaurado em `750dbb7e2e7f34fd55fe8a79fbda7dd422af9fb7`.

### Bloco 3 — Provider/Gateway adapters + CSC/Credentials — CONCLUÍDO/CERTIFICADO

- `ProviderDescriptor`/`ProviderRegistry` explícitos e fail-closed;
- routing por document kind + jurisdiction + environment + operation + provider opcional explícito;
- `ProviderRequest`/`ProviderResponse` não carregam segredo;
- credentials via `SecretReferenceKind.CREDENTIALS` e CSC via `SecretReferenceKind.CSC` somente por Vault;
- transport injetável e synthetic/no-network;
- `ProviderGatewayService` consulta a autoridade `CapabilityReadinessService` sem promover readiness;
- cross-tenant/unit/environment e ambiguidade bloqueados.

Falhas intermediárias: run `34759978765` (Ruff) e run `34760070032` (ciclo de importação detectado na coleta). Correções: lint/testes específicos e exports lazy em `gateway.__init__`.

Gate definitivo: `42f27c67145d2d4469374596d869ffc3ba05f013` / run `34760113452` / job `103731343836` / **93 source files / 471 PASS em 3.27s**. CI restaurado em `9e5019d64b5174ad9fe138e52c566ec3df73af84`.

### Bloco 4 — Resilience Runtime — EM EXECUÇÃO

Próximo objetivo: timeout explícito, retry governado, backoff/jitter determinístico, circuit breaker particionado e unknown-delivery outcome sem duplicar autorização.

## Governança preservada

PR #13 permanece Draft. Nenhum merge, deploy, produção real, homologação externa, promoção ou cutover foi executado.
