# CHECKPOINT — NFV1-P01-T01 — Identificar composição canônica

Data: 2026-10-05  
Produto: FM NFCORE V1  
Repository: `faabio3131/kordena-fiscal-engine-v2`  
Main de origem: `7e98877c2187920755c1e9db990220e58d4a8cae`  
Branch: `docs/nfv1-p01-t01-canonical-composition`  
PR: #107 — OPEN / DRAFT  
CI main de origem: FM NFCORE V1 CI #600 — SUCCESS  
Plan Governance main de origem: #29 — SUCCESS

## Objetivo

Identificar a composição fiscal canônica para o P1 sem criar executor paralelo, incluindo:

- executores/serviços válidos;
- autoridade S2S;
- autoridade humana;
- scope/binding;
- signing;
- provider;
- vault;
- production authority;
- readiness.

## Achados

1. `runtime.api:create_runtime_app` permanece o entrypoint canônico.
2. `build_postgres_runtime_composition` / `RuntimeComposition` é o composition root a estender.
3. `BridgeSecurityBoundary`, `BridgeRequestExecutor` e `PortalOperationExecutor` são ports; nenhuma implementação produtiva concreta deles foi encontrada no CURRENT.
4. `FiscalApplicationService` é a autoridade de application state/idempotency/lifecycle/outbox/archive/reconciliation a reutilizar.
5. S2S deve reutilizar `WorkloadAuthenticator + S2SAuthorizer`.
6. Host->fiscal scope deve vir de binding durável exact-match.
7. Portal deve continuar usando `HumanIdentityService + AuthenticatedHuman + PortalPermission + CSRF`.
8. Capability authority permanece `CapabilityReadinessService`.
9. Provider path canônico é `ProviderRegistry -> ProviderGatewayService`, envolvido por `GovernedProviderGatewayService` para production.
10. Secret path canônico é `SecretResolutionService -> FiscalSecretVault`; `ExternalFiscalSecretVault` já existe, concrete `ExternalSecretClient` não está presente.
11. Signing canônico é `CryptographyFiscalDocumentSigner` via `SecretResolutionService`.
12. `ProductionExecutionAuthority` permanece injetada e nunca pode ser fabricada pelo composition root.
13. Bridge e Portal devem ser adapters distintos de ingresso sobre um único caminho fiscal de aplicação.
14. Runtime readiness atual não prova Bridge fiscal ready; isso deve ser corrigido em P1-T02/P1-T04.

## Entrega

`docs/NFCORE_V1_P01_CANONICAL_FISCAL_COMPOSITION_2026-10-05.md`

## Código/runtime

Nenhuma implementação funcional nesta tarefa.

Nenhuma migration.

Nenhum deploy.

Nenhuma alteração Railway.

Nenhum secret/credential real.

## Decisões vinculantes

- não criar segundo app/runtime;
- não criar segundo composition root;
- não criar segunda auth/RBAC;
- não criar segundo tenant/unit resolver;
- não criar segundo provider registry;
- não criar segundo vault/signer/readiness/production authority;
- Bridge e Portal não podem possuir lógicas fiscais independentes.

## Gate da T01

- localizar executores válidos: PASS;
- impedir executor paralelo: decisão congelada;
- mapear signing/provider/vault/production authority: PASS.

## Verificações pendentes

- cronograma x ledger 59/59;
- apenas P01-T01 em execução;
- P01-T02 pendente;
- diff somente documental;
- Plan Governance da PR;
- CI completo da PR.

## Gate de saída

IN_PROGRESS.

## Próxima ação

Abrir PR exclusiva da T01 e executar gates. Não iniciar P01-T02.
