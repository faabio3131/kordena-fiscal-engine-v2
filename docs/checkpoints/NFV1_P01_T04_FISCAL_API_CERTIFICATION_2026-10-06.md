# CHECKPOINT — NFV1-P01-T04 — Certificar API fiscal

Data: 2026-10-06  
Produto: FM NFCORE V1  
Fase: P1 — PRODUCTION FISCAL COMPOSITION ROOT  
Task: `NFV1-P01-T04 — Certificar API fiscal`  
Status: `IN_PROGRESS`

## Estado confirmado antes da certificação

- repository: `faabio3131/kordena-fiscal-engine-v2`;
- main de origem: `f7ecbe5afc10e1157d465da489cb285c74de77b0`;
- PRs abertas no início: 0;
- FM NFCORE V1 CI #614: SUCCESS no exact main;
- NFCore Plan Governance #43: SUCCESS no exact main;
- P01-T03: DONE_CERTIFIED;
- staging revalidado somente leitura e permanece em drift conhecido.

## Objetivo

Certificar o contrato HTTP e o encaminhamento interno das operações fiscais do
launch-scope:

1. `queryArchiveReference`;
2. `cancelFiscalDocument`;
3. `queryCapabilities`;
4. `inutilizeFiscalRange`;
5. `issueFiscalDocument`;
6. `queryFiscalDocument`;
7. `reconcileFiscalOperation`.

A T04 certifica API e composição interna. Não certifica transporte fiscal externo,
secret manager externo, credencial real, homologação oficial ou produção.

## Autoridades e caminhos reutilizados

A certificação usa somente as autoridades canônicas já existentes:

- `web.app:create_app`;
- `CanonicalBridgeSecurityBoundary`;
- `WorkloadAuthenticator`;
- `S2SAuthorizer`;
- binding durável exact-match;
- `CanonicalBridgeRequestExecutor`;
- `CanonicalFiscalOperationPath`;
- `FiscalApplicationService`.

Nenhum segundo app, segundo executor de domínio, segunda API ou segunda autoridade
fiscal foi criado.

## Contrato launch-scope auditado

Bridge expõe exatamente:

- `POST /v1/archive/references/query` -> `queryArchiveReference` -> 200;
- `POST /v1/cancellations` -> `cancelFiscalDocument` -> 202;
- `POST /v1/capabilities/query` -> `queryCapabilities` -> 200;
- `POST /v1/inutilizations` -> `inutilizeFiscalRange` -> 202;
- `POST /v1/issuances` -> `issueFiscalDocument` -> 202;
- `POST /v1/queries` -> `queryFiscalDocument` -> 200;
- `POST /v1/reconciliations` -> `reconcileFiscalOperation` -> 200.

Mutações exigem `Idempotency-Key`:

- cancelamento;
- inutilização;
- emissão;
- reconciliação.

Consultas/archive/capabilities não exigem chave de idempotência no contrato HTTP.

## Matriz integrada adicionada

Arquivo:

`tests/runtime/test_p01_t04_fiscal_api_certification.py`

A matriz prova para cada uma das sete operações:

- autenticação/autorização S2S real do boundary;
- resolução do host scope para scope fiscal interno;
- operation ID canônico;
- status HTTP esperado;
- payload encaminhado ao mesmo caminho canônico;
- idempotency key preservada quando aplicável;
- correlation ID preservado;
- nenhuma execução sem dependência explicitamente configurada.

Também prova para todas as sete rotas que, sem handler fiscal disponível:

`503 FISCAL_RUNTIME_NOT_READY`

é retornado após o boundary de autoridade, sem fallback ou resultado sintético.

Para as quatro mutações prova adicionalmente que ausência de
`Idempotency-Key` bloqueia antes da execução.

## Evidência de domínio reutilizada

A T04 não usa test doubles como prova de provider real.

Os handlers controlados da nova matriz provam somente o contrato de ingresso e o
dispatcher interno. A capacidade de domínio já existente continua coberta por sua
suíte própria, incluindo:

- emissão NFC-e;
- emissão NF-e/NFS-e e boundaries correspondentes;
- provider gateway/readiness;
- reconciliação;
- archive;
- capability readiness;
- lifecycle/idempotência.

Provider synthetic/fake permanece exclusivamente como evidência de contrato de teste,
nunca como prova de integração externa real.

## Readiness — lacuna encontrada e corrigida

A T01 exigiu que o runtime profile diferenciasse explicitamente:

- composition interna;
- provider transport real;
- secret backend externo concreto;
- signer composto;
- production authority.

Antes da T04, o profile já mostrava composition/handlers e production authority, mas
não declarava separadamente provider transport real, external secret client e signer.

A T04 adiciona ao `/runtime/profile`:

- `fiscal_provider_transport_real_configured = false`;
- `fiscal_external_secret_client_configured = false`;
- `fiscal_signer_configured = false`;
- `fiscal_runtime_external_execution_ready = false`.

Esses valores são deliberadamente fail-closed no CURRENT. Eles não transformam
ausência de dependência em readiness.

As fases P6/P7 deverão substituir essa ausência por composição real e evidência
própria, em vez de simplesmente promover booleanos.

## Staging — somente leitura

Projeto Railway: `FM NFCORE Staging`.

- API: `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- Portal: mesmo SHA;
- Worker: `1c34ba001935952f83ec0b065144e0b8311a5650`;
- main CURRENT de origem da T04:
  `f7ecbe5afc10e1157d465da489cb285c74de77b0`;
- EnvironmentPatch staged permanece vazio;
- nenhum deploy ou alteração Railway foi executado.

Classificação permanece:

`STAGING_REAL / VERSION_DRIFT_PRESENT / NOT_CERTIFIED_AGAINST_CURRENT`.

## Dependências externas preservadas

Continuam fora da T04:

- concrete `ExternalSecretClient`: P6;
- real `FiscalProviderTransport`: P7;
- credenciais/certificados/CSC reais: P6/P7/P10;
- homologação oficial: P10;
- production grants reais: P10/P11/P12.

## Produção/comercial

`PRODUCTION_APPROVED=NO`.

`COMMERCIAL_LIVE=NO`.

Nenhum provider real, segredo real, certificado, CSC, homologação, migration produtiva,
DNS, cutover ou deploy foi executado.

## Gates pendentes

- `python3 scripts/check_nfcore_plan.py`;
- Ruff;
- Mypy;
- Pytest completo;
- Bridge contract tests;
- frontend lint/typecheck/tests/build;
- E2E;
- containers e smokes;
- vulnerability policy;
- SBOM;
- PostgreSQL backup/restore;
- CI completa da PR.

## Gate de fase

O gate de saída do P1 permanece:

`FISCAL_RUNTIME_COMPOSED_AND_CERTIFIED_INTERNAL = NOT MET`

até a T04 ser mergeada, certificada pós-merge e formalmente fechada.

## Próxima ação

Abrir PR exclusiva da T04, executar todos os gates, corrigir qualquer falha pela causa
e aguardar autorização humana de merge.

Não iniciar P2 antes do closeout completo da T04.
