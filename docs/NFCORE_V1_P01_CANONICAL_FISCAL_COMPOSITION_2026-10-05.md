# FM NFCORE V1 — P1 Canonical Fiscal Composition

**Task:** NFV1-P01-T01 — Identificar composição canônica  
**Data da auditoria:** 2026-10-05  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**CURRENT auditado:** `main@7e98877c2187920755c1e9db990220e58d4a8cae`  
**CI CURRENT de origem:** FM NFCORE V1 CI #600 — SUCCESS  
**Plan Governance CURRENT de origem:** #29 — SUCCESS  
**Escopo:** identificar as autoridades/executores existentes e congelar a composição correta para P1-T02. Nenhuma composição funcional é implementada nesta tarefa.

## 1. Conclusão executiva

A composição canônica do NFCore deve continuar usando o mesmo entrypoint e o mesmo runtime:

`kordena_fiscal.runtime.api:create_runtime_app` / `kordena_fiscal.runtime.api:app`.

O composition root existente:

`src/kordena_fiscal/runtime/composition.py::build_postgres_runtime_composition`

é a autoridade de composição durável a ser **estendida**, não substituída.

Não existe no CURRENT um executor fiscal produtivo concreto que implemente diretamente:

- `BridgeSecurityBoundary`;
- `BridgeRequestExecutor`;
- `PortalOperationExecutor`.

`BridgeSecurityBoundary`, `BridgeRequestExecutor` e `PortalOperationExecutor` são protocols de ingresso. Os testes HTTP usam test doubles (`AllowingSecurity`, `RecordingExecutor`). Portanto, P1-T02 deve ligar esses ports às autoridades existentes; não deve criar um segundo domínio fiscal.

## 2. CURRENT — composição existente

### 2.1 Runtime canônico

Arquivo:

`src/kordena_fiscal/runtime/api.py`

Fatos confirmados:

- `RuntimeApi` abre/inicializa o `PostgresFiscalDatabase`;
- `build_postgres_runtime_composition(...)` compõe identidade humana, recovery, comercial e Portal durável;
- `create_runtime_app(...)` é a montagem container-facing do produto;
- o global `app` é construído por `create_runtime_app(...)`;
- `production_authority` e `portal_operation_executor` já são ports injetáveis do runtime;
- o runtime monta `web.app:create_app(...)` no mesmo processo;
- a montagem atual passa identidade/portal/comercial, mas **não passa** `security` nem `executor` do Bridge fiscal.

Consequência CURRENT:

as rotas fiscais existem, mas permanecem fail-closed com `RUNTIME_NOT_READY`.

### 2.2 Composition root durável atual

Arquivo:

`src/kordena_fiscal/runtime/composition.py`

`RuntimeComposition` é a composição canônica durável atual e contém:

- `HumanIdentityService`;
- `PasswordRecoveryService`;
- commercial provisioning/fulfillment/claim/activation/trial;
- pricing administration;
- commercial release administration;
- Cakto checkout administration opcional;
- `DurableHumanPortalExecutor`.

O próprio módulo declara que não cria segunda auth, portal, billing, fiscal authority ou secret system.

**Decisão vinculante:** P1-T02 deve evoluir este composition root; não criar `runtime/fiscal_composition_v2.py`, segundo app, segunda API ou runtime paralelo.

## 3. Autoridades canônicas que devem ser reutilizadas

### 3.1 Persistência e estado fiscal

Autoridade:

- `PostgresFiscalDatabase`;
- `FiscalUnitOfWorkFactory`;
- repositories já expostos pelo UoW.

Serviço de aplicação:

`src/kordena_fiscal/application/service.py::FiscalApplicationService`

Responsabilidades já existentes:

- binding;
- idempotency/reservation;
- lifecycle;
- numbering;
- inbox/outbox;
- archive;
- reconciliation.

**Classificação:** executor/aplicação válido para estado durável fiscal, mas não é `BridgeRequestExecutor` pronto.

### 3.2 Host -> tenant/unit fiscal

Autoridades:

- `FiscalAccountBinding`;
- `FiscalBindingRepository.resolve(HostScope)`;
- `FiscalAccountBinding.to_execution_scope(...)`.

O `FiscalBindingRegistry` define semanticamente o comportamento exact-match, mas é in-memory.

Para produção, a resolução deve ler o binding durável do UoW/Postgres e produzir `ExecutionScope` sem permitir que headers externos se tornem autoridade interna.

**Proibido:** tratar `X-FM-Tenant-Id` / `X-FM-Unit-Id` como tenant/unit fiscal canônico sem binding validado.

### 3.3 Segurança S2S do Bridge

Autoridades existentes:

- `WorkloadAuthenticator`;
- `S2SAuthorizer`;
- `CallerIdentity`;
- `HostScopeGrant`;
- `FiscalCapability`;
- `AuthorizedFiscalRequest`;
- security audit/rate limiter.

`S2SAuthorizer` exige um `FiscalExecutionScopeResolver`.

**Target:** criar apenas um adapter fino de `BridgeSecurityBoundary` sobre:

`WorkloadAuthenticator -> S2SAuthorizer -> durable binding resolver`.

Esse adapter não pode possuir regra paralela de tenant, unidade, capability ou credencial.

### 3.4 Segurança humana do Portal

Autoridades existentes:

- `HumanIdentityService`;
- `AuthenticatedHuman`;
- `PortalPermission`;
- sessão opaca;
- CSRF;
- unit scope da conta;
- `portal_api._authorized(...)`.

A UI é explicitamente impedida de fornecer campos de autoridade como `tenant_id`, `account_id`, `role`, `permissions`, `authority`, `session_epoch` e `host_namespace`.

**Target:** o `PortalOperationExecutor` recebe somente a autoridade já autenticada/autorizada pelo backend e traduz a operação para o mesmo caminho fiscal usado pelo Bridge.

### 3.5 Capabilities/readiness

Autoridade:

`CapabilityReadinessService`

Arquivo:

`src/kordena_fiscal/compliance/capability_api.py`

Ela é a autoridade única para consultar/enforçar capability fiscal por:

- jurisdição;
- tipo de documento;
- ambiente;
- ação;
- versão/readiness.

`ProviderGatewayService` já chama `require_action(...)` antes de execução de provider.

**Proibido:** duplicar readiness dentro do executor HTTP ou Portal.

### 3.6 Provider routing

Autoridades:

- `ProviderDescriptor`;
- `ConfiguredProviderAdapter`;
- `ProviderRegistry`;
- `ProviderGatewayService`.

Fluxo canônico:

`ProviderRequest -> CapabilityReadinessService -> ProviderRegistry -> ConfiguredProviderAdapter -> FiscalProviderTransport`.

`ProviderRegistry` falha fechado se não houver exatamente um provider suportado/selecionado.

**CURRENT externo:** `FiscalProviderTransport` é Protocol. O repositório possui transport synthetic para testes, mas nenhuma implementação HTTP/SOAP real certificada para launch.

**Regra P1:** synthetic/fake não entra no runtime comercial real.

### 3.7 Production authority

Autoridades:

- `FiscalProductionActivationService`;
- `ProductionActivationRecord`;
- `ProductionExecutionAuthority`;
- `GovernedProviderGatewayService`.

Fluxo canônico TARGET:

`GovernedProviderGatewayService(delegate=ProviderGatewayService, production_authority=...)`.

Regras existentes:

- HOMOLOGATION não depende de production authority;
- PRODUCTION exige provider explícito;
- PRODUCTION exige grant ativo para a célula exata;
- revogação prevalece fail-closed;
- evidência oficial + decisão humana são requisitos para criar activation record.

**Decisão vinculante:** `production_authority` continua injetada de fora; P1-T02 não pode fabricar grant, ler um simples boolean de ambiente ou ativar fiscal production automaticamente.

### 3.8 Vault / secret authority

Autoridade:

`SecretResolutionService`

Fluxo canônico:

`Control Plane SecretReference -> SecretResolutionService -> FiscalSecretVault -> material efêmero`.

Production adapter já definido:

`ExternalFiscalSecretVault`

Port externo:

`ExternalSecretClient`.

Invariantes já existentes:

- SecretReference opaca persiste;
- material sensível não persiste;
- escopo tenant/unit/environment/kind/provider é validado;
- material é efêmero;
- audit sink não é autoridade.

**CURRENT externo:** não foi encontrada implementação concreta de `ExternalSecretClient` AWS/GCP/Azure/Vault no repositório.

**Decisão vinculante:** P1-T02 pode compor os ports, mas ausência de client real deve permanecer fail-closed; provider concreto pertence a P6.

### 3.9 Signing

Autoridades:

- `FiscalDocumentSigner`;
- `CryptographyFiscalDocumentSigner`;
- `SecretResolutionService`.

Fluxo:

`FiscalSignatureRequest -> CryptographyFiscalDocumentSigner -> SecretResolutionService -> certificate material efêmero`.

Suporte explícito do adapter atual:

- NF-e;
- NFC-e.

NFS-e permanece provider/jurisdição-specific; não deve receber signer universal artificial.

**Proibido:** novo signer paralelo no Bridge/Portal.

## 4. Execução fiscal canônica — decisão de arquitetura

### 4.1 O que NÃO existe

Não há no CURRENT uma classe produtiva que seja simultaneamente o dispatcher das sete operações HTTP e a orquestração completa do domínio.

Os seguintes ports são interfaces de ingresso, não autoridades de negócio:

- `BridgeRequestExecutor`;
- `PortalOperationExecutor`.

Criar dois executores independentes, cada um com sua própria lógica fiscal, violaria a arquitetura do projeto.

### 4.2 TARGET

Deve existir **um único caminho canônico de execução fiscal de aplicação**.

Modelo lógico:

~~~text
Bridge HTTP
  -> BridgeSecurityBoundary adapter
  -> BridgeRequestExecutor adapter
                      \
                       -> CANONICAL FISCAL APPLICATION EXECUTION PATH
                      /
Portal HTTP
  -> sessão/RBAC/CSRF
  -> PortalOperationExecutor adapter

CANONICAL FISCAL APPLICATION EXECUTION PATH
  -> durable scope / application state
  -> capability readiness
  -> document-specific orchestration
  -> signer when required
  -> governed provider gateway
  -> persistence / lifecycle / archive / reconciliation / audit
~~~

Bridge e Portal podem ter adapters distintos porque seus contratos de autoridade e resposta são diferentes, mas **não podem ter regras de negócio ou domínio independentes**.

### 4.3 Operações de ingresso

Bridge HTTP possui:

- `queryArchiveReference`;
- `cancelFiscalDocument`;
- `queryCapabilities`;
- `inutilizeFiscalRange`;
- `issueFiscalDocument`;
- `queryFiscalDocument`;
- `reconcileFiscalOperation`.

Portal possui:

- `issueFiscalDocument`;
- `queryFiscalDocument`;
- `cancelFiscalDocument`;
- `inutilizeFiscalRange`;
- `reconcileFiscalOperation`.

O dispatcher canônico deve compartilhar a implementação das cinco operações comuns. Capabilities e archive read são ingressos Bridge adicionais que reutilizam suas respectivas autoridades existentes.

## 5. Componentes existentes válidos por responsabilidade

| Responsabilidade | Autoridade/componente CURRENT | Uso no TARGET |
|---|---|---|
| Runtime/container app | `runtime.api:create_runtime_app` | manter |
| Durable composition | `build_postgres_runtime_composition` / `RuntimeComposition` | estender |
| Fiscal DB/UoW | `PostgresFiscalDatabase` | manter |
| Estado fiscal | `FiscalApplicationService` | reutilizar |
| Binding host -> fiscal | `FiscalBindingRepository` + `FiscalAccountBinding` | reutilizar |
| S2S authentication | `WorkloadAuthenticator` | reutilizar |
| S2S authorization | `S2SAuthorizer` | reutilizar |
| Portal auth/RBAC | `HumanIdentityService` + `AuthenticatedHuman` | reutilizar |
| Capability authority | `CapabilityReadinessService` | reutilizar |
| Provider selection/routing | `ProviderRegistry` + `ProviderGatewayService` | reutilizar |
| Production gate | `GovernedProviderGatewayService` + `ProductionExecutionAuthority` | reutilizar |
| Secret resolution | `SecretResolutionService` | reutilizar |
| External vault adapter | `ExternalFiscalSecretVault` | reutilizar; concrete client ainda externo |
| Signing | `CryptographyFiscalDocumentSigner` | reutilizar |
| NFC-e issuance | `NfceIssuanceOrchestrator` | reutilizar quando aplicável |
| NFS-e gateway contract | `NfseGatewayClient` / provider-specific path | reutilizar sem universalizar |
| Reconciliation | `FiscalReconciliationEngine` + `FiscalApplicationService` | reutilizar |
| Archive | UoW archive + `FiscalApplicationService.archive` | reutilizar |
| HTTP Bridge port | `BridgeSecurityBoundary`, `BridgeRequestExecutor` | implementar adapters finos em T02 |
| Portal fiscal port | `PortalOperationExecutor` | implementar adapter fino em T02 |

## 6. Anti-duplicação — regras vinculantes para P1-T02

P1-T02 não pode criar:

1. segundo FastAPI app como autoridade funcional paralela;
2. segundo banco/UoW fiscal;
3. segundo tenant/unit resolver;
4. segundo S2S auth;
5. segundo HumanIdentity/RBAC;
6. segundo capability/readiness service;
7. segundo provider registry;
8. segundo vault/secret resolution;
9. segundo signer;
10. segundo production approval/activation authority;
11. executor Bridge com regra fiscal própria;
12. executor Portal com regra fiscal própria.

Adapters são permitidos somente para traduzir contratos de ingresso/saída e delegar para as autoridades canônicas.

## 7. Readiness — risco confirmado

O runtime externo possui seu próprio `/health/ready` baseado em DB/composition.

O Bridge montado possui outro `/health/ready` que falha quando `security` ou `executor` estão ausentes.

Como o endpoint do runtime principal é a superfície efetiva do container, o CURRENT pode reportar runtime ready mesmo enquanto o Bridge fiscal continua fail-closed.

Também o campo atual:

`portal_executor_configured = composition is not None`

prova a presença do executor durável do Portal, mas não prova que `PortalOperationExecutor` fiscal foi injetado.

**Target de P1-T02/P1-T04:** readiness/profile precisam distinguir explicitamente:

- durable runtime composition;
- Bridge security configurada;
- Bridge fiscal executor configurado;
- Portal fiscal operation executor configurado;
- provider transport real/configurado;
- signer/vault readiness;
- production authority ativa somente quando realmente aplicável.

Nenhum desses estados pode ser inferido de `composition is not None`.

## 8. Dependências externas que continuam fail-closed

Não são pré-condição para identificar a composição, mas não podem ser falsificadas em P1:

- concrete `ExternalSecretClient`: P6;
- real `FiscalProviderTransport`: P7;
- credenciais/certificados/CSC reais: P6/P7/P10;
- homologação oficial: P10;
- production grants reais: P10/P11/P12.

P1 deve ser certificável internamente com ports/fakes somente nos testes, mantendo runtime real fail-closed quando dependências reais não existem.

## 9. Current -> Target para P1-T02

### CURRENT

~~~text
runtime.api:app
  -> RuntimeComposition (human/commercial/portal durable)
  -> web.app:create_app(
       human/commercial dependencies,
       security=None,
       executor=None,
       portal_executor=DurableHumanPortalExecutor
     )

Fiscal HTTP operations -> RUNTIME_NOT_READY
Portal fiscal operations -> PORTAL_RUNTIME_NOT_READY
~~~

### TARGET

~~~text
runtime.api:app
  -> RuntimeComposition (mesmo root, ampliado)
      -> durable fiscal state/application services
      -> canonical scope/binding resolver
      -> S2S security adapter
      -> canonical fiscal operation path
      -> BridgeRequestExecutor adapter
      -> PortalOperationExecutor adapter
      -> capability readiness
      -> signer
      -> governed provider gateway
      -> vault/secret resolution
      -> injected ProductionExecutionAuthority (optional/fail-closed)

  -> web.app:create_app(
       security=<canonical bridge security adapter>,
       executor=<canonical bridge executor adapter>,
       portal_executor=<DurableHumanPortalExecutor using same canonical operation path>
     )
~~~

## 10. Critérios de aceite congelados para P1-T02

P1-T02 somente poderá ser aceita se provar:

- um único runtime entrypoint;
- um único composition root;
- um único caminho fiscal de aplicação;
- Bridge e Portal delegam ao mesmo caminho;
- S2S usa `WorkloadAuthenticator + S2SAuthorizer`;
- binding é durável e exact-match;
- Portal continua usando sessão/RBAC/CSRF existentes;
- capability/readiness não é duplicada;
- provider routing não é duplicado;
- signing não é duplicado;
- secret resolution não é duplicada;
- production authority é somente injetada e fail-closed;
- ausência de provider/secret/production real continua fail-closed;
- synthetic/fake existe somente em testes;
- readiness/profile não afirmam fiscal-ready sem composição real;
- nenhum tenant/unit/header/browser payload consegue criar autoridade.

## 11. Resultado da T01

**CANONICAL COMPOSITION IDENTIFIED.**

A implementação ainda não foi feita.

Próxima tarefa após merge/certificação desta T01:

`NFV1-P01-T02 — Implementar composition root`.

Nenhuma tarefa P1-T02 ou posterior é considerada iniciada por este documento.
