# CHECKPOINT — NFV1-P01-T02 — Implementar composition root

Data: 2026-10-06  
Produto: FM NFCORE V1  
Fase: P1 — PRODUCTION FISCAL COMPOSITION ROOT  
Task: `NFV1-P01-T02 — Implementar composition root`  
Status: `IN_PROGRESS`

## Estado confirmado antes da implementação

- repository: `faabio3131/kordena-fiscal-engine-v2`;
- main de origem: `13a613a3ebe261f7880a6f8918268b922ba635c1`;
- PRs abertas no início: 0;
- FM NFCORE V1 CI #605: SUCCESS no exact main;
- NFCore Plan Governance #34: SUCCESS no exact main;
- predecessor `NFV1-P01-T01`: DONE_CERTIFIED;
- branch da tarefa: `feat/nfv1-p01-t02-composition-root`.

## Objetivo

Implementar a composição fiscal canônica identificada pela T01, sem criar segunda API,
segundo runtime, segunda autenticação, segunda autoridade de tenant/unidade, segundo
provider registry, segundo vault ou segunda autoridade de produção.

Escopo obrigatório da T02:

- injetar `BridgeSecurityBoundary`;
- injetar `BridgeRequestExecutor`;
- injetar `PortalOperationExecutor`;
- preservar fail-closed;
- não habilitar produção fiscal automaticamente.

## CURRENT técnico auditado

Antes desta tarefa:

- `runtime.api:create_runtime_app` era o entrypoint canônico;
- `build_postgres_runtime_composition` / `RuntimeComposition` já compunha o runtime
  humano/comercial;
- o Bridge HTTP recebia `security=None` e `executor=None`;
- o Portal durável recebia `PortalOperationExecutor=None`;
- `FiscalApplicationService` já era a autoridade durável de application state e binding;
- `WorkloadAuthenticator + S2SAuthorizer` já eram a autoridade S2S;
- nenhum `FiscalProviderTransport` real estava certificado;
- nenhum `ExternalSecretClient` concreto estava certificado;
- produção fiscal dependia de `ProductionExecutionAuthority` injetada e não podia ser
  fabricada pelo composition root.

## Implementação da T02

### Caminho fiscal único

Foi criado `runtime/fiscal_runtime.py` com um único
`CanonicalFiscalOperationPath`.

Ele:

- reutiliza `FiscalApplicationService.resolve_scope` para o binding durável exact-match
  do Bridge;
- não contém regra tributária, provider routing paralelo ou persistência paralela;
- aceita somente handlers explicitamente injetados para operações canônicas;
- quando um handler real não existe, responde fail-closed e não fabrica resultado.

### Bridge

`CanonicalBridgeSecurityBoundary`:

- autentica exclusivamente via `WorkloadAuthenticator`;
- autoriza exclusivamente via `S2SAuthorizer`;
- converte headers de host em `HostScope` não confiável;
- exige binding durável antes de produzir `ExecutionScope`;
- mapeia cada operation ID para a capability S2S existente;
- não aceita tenant/unidade externos como autoridade fiscal interna.

`CanonicalBridgeRequestExecutor`:

- aceita somente `AuthorizedFiscalRequest`;
- delega ao mesmo `CanonicalFiscalOperationPath`;
- mantém operação sem dependência real em `503 FISCAL_RUNTIME_NOT_READY`.

### Portal

`CanonicalPortalOperationExecutor`:

- recebe somente `AuthenticatedHuman` já produzido por sessão/RBAC/CSRF backend;
- reafirma o escopo de unidade;
- valida tenant/unidade no Control Plane canônico;
- valida ambiente habilitado;
- constrói `ExecutionScope` interno;
- delega ao mesmo `CanonicalFiscalOperationPath`;
- não cria provider, segredo ou production grant.

### Composition root

O mesmo `RuntimeComposition` foi ampliado para conter:

- `FiscalApplicationService`;
- `CanonicalFiscalOperationPath`;
- `CanonicalBridgeSecurityBoundary`;
- `CanonicalBridgeRequestExecutor`;
- `CanonicalPortalOperationExecutor`;
- `DurableHumanPortalExecutor` ligado ao executor fiscal canônico.

Não foi criado segundo composition root.

### Runtime

`create_runtime_app` agora injeta os adapters Bridge reais no mesmo `web.create_app`.

O perfil de runtime diferencia explicitamente:

- Bridge security configurada;
- Bridge executor configurado;
- workload identity configurada;
- Portal fiscal executor configurado;
- handlers fiscais realmente configurados.

A composição padrão recebe:

- zero credenciais S2S;
- zero handlers fiscais externos.

Portanto a estrutura está composta, mas autenticação/operação externa continua
fail-closed até dependências reais serem configuradas por suas fases próprias.

## Produção

Nenhuma `ProductionExecutionAuthority` é criada pela T02.

`PRODUCTION_APPROVED=NO`.

`COMMERCIAL_LIVE=NO`.

## Dependências que permanecem ausentes por design

- real `FiscalProviderTransport`: P7;
- concrete external `ExternalSecretClient`: P6;
- credenciais/certificados/CSC reais: P6/P7/P10;
- homologação oficial: P10;
- production grants reais: P10/P11/P12.

Nenhum fake/synthetic dessas dependências entra no runtime padrão.

## Railway staging revalidado — somente leitura

Project: `FM NFCORE Staging`.

- API: SUCCESS em `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- Portal: SUCCESS no mesmo SHA;
- Worker: SUCCESS em `1c34ba001935952f83ec0b065144e0b8311a5650`;
- Postgres: SUCCESS com volume persistente de 5000 MB;
- main atual: `13a613a3ebe261f7880a6f8918268b922ba635c1`;
- staging continua em VERSION DRIFT conhecido;
- nenhum staged change substantivo;
- EnvironmentPatch vazio permanece com `changes=[]`.

Nenhum deploy ou alteração Railway foi executado. O drift continua com ownership nas
fases P4/P5/P9/P11 e não é corrigido antecipadamente nesta tarefa.

## Testes dirigidos adicionados/ajustados

A matriz dirigida da T02 deve provar:

- o runtime profile expõe Bridge security/executor e Portal fiscal executor compostos;
- sem credencial S2S configurada, Bridge falha em autenticação e não executa;
- sem handler fiscal real, Portal chega ao executor canônico e falha com
  `FISCAL_RUNTIME_NOT_READY`;
- a UI continua sem criar tenant/unidade/role/permission;
- nenhum provider/secret/produção é promovido por composição.

## Gates ainda pendentes

- `python3 scripts/check_nfcore_plan.py`;
- Ruff;
- Mypy strict;
- Pytest;
- full CI;
- revisão do diff;
- PR exclusiva da T02.

## Gate da tarefa

`IN_PROGRESS`.

T02 somente poderá virar DONE_CERTIFIED após PR, CI, merge autorizado e evidência
pós-merge correspondente.

## Próxima ação

Executar os gates da branch, corrigir qualquer causa real de falha e abrir PR exclusiva
da `NFV1-P01-T02`.

Não iniciar P01-T03.
