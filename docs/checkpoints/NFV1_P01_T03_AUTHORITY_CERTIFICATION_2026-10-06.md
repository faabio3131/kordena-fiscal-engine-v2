# CHECKPOINT — NFV1-P01-T03 — Certificar autoridade

Data: 2026-10-06  
Produto: FM NFCORE V1  
Fase: P1 — PRODUCTION FISCAL COMPOSITION ROOT  
Task: `NFV1-P01-T03 — Certificar autoridade`  
Status: `IN_PROGRESS`

## Estado confirmado antes da certificação

- repository: `faabio3131/kordena-fiscal-engine-v2`;
- main de origem: `66f21d4a3a177470946cdd5101191367e2dfdfd9`;
- PRs abertas no início: 0;
- FM NFCORE V1 CI #609: SUCCESS no exact main;
- NFCore Plan Governance #38: SUCCESS no exact main;
- P01-T02: DONE_CERTIFIED;
- staging continua em drift conhecido e não será alterado nesta tarefa.

## Objetivo

Certificar no caminho fiscal composto:

- tenant spoofing;
- unit spoofing;
- cross-tenant;
- cross-unit;
- RBAC;
- sessão;
- S2S;
- idempotência.

T03 não certifica provider fiscal real, secret manager real, homologação externa,
produção fiscal ou a completude das operações da API. Esses itens permanecem nas
tarefas/fases próprias.

## Autoridades canônicas auditadas

### Bridge / S2S

- credencial: `WorkloadAuthenticator`;
- capability + host/tenant/unit grant: `S2SAuthorizer`;
- binding externo -> fiscal interno: `FiscalApplicationService.resolve_scope`;
- binding durável exact-match: repository `bindings.resolve`;
- HTTP: `CanonicalBridgeSecurityBoundary`;
- execução: `CanonicalBridgeRequestExecutor`.

Headers HTTP são claims não confiáveis. Eles só produzem `ExecutionScope` após
autenticação, autorização e binding durável exato.

### Portal humano

- identidade: `HumanIdentityService`;
- sessão: cookie opaco + token hash persistido;
- CSRF: cookie/header + hash da sessão;
- RBAC: `PortalRole -> PortalPermission`;
- tenant: derivado exclusivamente de `AuthenticatedHuman.account.tenant_id`;
- unidade: limitada por `HumanAccount.unit_ids`;
- campos de autoridade enviados pelo browser: rejeitados por
  `_reject_browser_authority`;
- executor fiscal: `CanonicalPortalOperationExecutor`.

A UI não possui autoridade própria.

## Achado de segurança da T03

A auditoria encontrou uma divergência de exceção no caso de binding durável ausente:

1. `bindings.resolve` durável lança `PersistenceStateError`;
2. `S2SAuthorizer` normaliza/audita ausência de binding quando recebe
   `FiscalValidationError`;
3. antes desta tarefa, `FiscalApplicationService.resolve_scope` propagava diretamente
   `PersistenceStateError`.

Risco: uma requisição autenticada/autorizada para um host scope sem binding exato
poderia escapar do boundary de autoridade como erro interno em vez de recusa
fail-closed explícita.

## Correção

`FiscalApplicationService.resolve_scope` agora converte somente a ausência/estado
inválido do binding durável em `FiscalValidationError` canônico.

Com isso:

- `S2SAuthorizer` registra `binding_not_found`;
- `CanonicalBridgeSecurityBoundary` responde
  `403 FISCAL_BINDING_REQUIRED`;
- nenhum handler fiscal é executado;
- não foi criado fallback, binding implícito ou autoridade paralela.

## Matriz de certificação dirigida

### Bridge

Novos testes em `tests/runtime/test_p01_t03_bridge_authority.py`:

1. request autorizado resolve tenant/unit externos para scope fiscal interno;
2. tenant spoofing é rejeitado antes da execução;
3. unit spoofing/cross-unit é rejeitado antes da execução;
4. host namespace spoofing é rejeitado;
5. binding exato ausente falha explicitamente e audita `binding_not_found`;
6. mutação sem `Idempotency-Key` é rejeitada;
7. chave de idempotência válida é preservada até o caminho canônico.

### Portal

Novos testes em `tests/runtime/test_p01_t03_portal_authority.py`:

1. browser não pode enviar `tenant_id` como autoridade;
2. usuário restrito à unit-a não pode operar unit-b;
3. requisição sem sessão é rejeitada;
4. AUDITOR não pode emitir documento;
5. mutação fiscal sem `Idempotency-Key` é rejeitada;
6. sessão OPERATOR válida usa tenant da conta;
7. unit scope e idempotency key chegam ao mesmo caminho fiscal canônico.

## Evidência histórica reutilizada, não reimplementada

A certificação T03 também reutiliza testes existentes que já cobrem a mesma autoridade
em níveis inferiores:

- `tests/security/test_s2s.py`: segredo hash, revogação/expiração, capability,
  cross-host, cross-tenant, cross-unit, binding exact-match e rate limit;
- `tests/web/test_human_auth_routes.py`: sessão segura, tenant não spoofável por
  header, sessão obrigatória, CSRF/logout e revogação;
- `tests/web/test_portal_api.py`: authority server-side, RBAC, unit scope,
  mass-assignment de autoridade e idempotency key;
- `tests/lifecycle/test_idempotency.py`: replay semântico, conflito de conteúdo,
  partição por tenant/unit/environment/document kind e concorrência.

T03 não duplica esses mecanismos; certifica que continuam válidos no composition root
CURRENT.

## CURRENT -> TARGET

CURRENT de origem:

- T02 compôs Bridge e Portal;
- autoridades existiam e possuíam testes históricos;
- ausência de binding durável tinha uma divergência de exceção no caminho composto;
- não havia matriz T03 específica sobre os adapters CURRENT.

TARGET desta tarefa:

- ausência de binding explicitamente fail-closed;
- tenant/unit/host spoofing bloqueados;
- cross-tenant/cross-unit bloqueados;
- sessão/RBAC/CSRF permanecem server-side;
- idempotency key exigida e propagada;
- testes dirigidos + suíte inteira + CI verdes;
- nenhuma produção fiscal ativada.

## Staging — somente leitura

Projeto Railway: `FM NFCORE Staging`.

- API: `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- Portal: mesmo SHA;
- Worker: `1c34ba001935952f83ec0b065144e0b8311a5650`;
- main CURRENT: `66f21d4a3a177470946cdd5101191367e2dfdfd9`;
- drift permanece;
- nenhum deploy ou alteração foi executado.

## Produção/comercial

`PRODUCTION_APPROVED=NO`.

`COMMERCIAL_LIVE=NO`.

Nenhum secret real, certificado, CSC, provider real, homologação, migration produtiva,
DNS ou cutover foi executado.

## Gates pendentes

- Plan Governance;
- Ruff;
- Mypy;
- Pytest dirigido + suíte completa;
- dependency audits;
- frontend gates;
- E2E;
- containers/smokes;
- vulnerability policy;
- SBOM;
- PostgreSQL backup/restore;
- CI completa da PR.

## Próxima ação

Abrir PR exclusiva da T03, executar todos os gates e corrigir pela causa qualquer
falha encontrada.

Não iniciar P01-T04 antes de T03 ser mergeada e certificada.
