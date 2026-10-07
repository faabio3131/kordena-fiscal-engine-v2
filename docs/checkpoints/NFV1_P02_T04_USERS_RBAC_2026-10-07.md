# NFV1-P02-T04 — Usuários e RBAC — checkpoint de implementação

**Data:** 2026-10-07
**Task ID:** NFV1-P02-T04
**Status:** IN_PROGRESS / IMPLEMENTATION_CANDIDATE
**Repositório:** `faabio3131/kordena-fiscal-engine-v2`
**Branch:** `feat/nfv1-p02-t04-users-rbac`
**Base imutável:** `d8d958a33a7a2364e005cb5742baecae9ed1e341`

## CURRENT revalidado antes da alteração

- `main` em `d8d958a33a7a2364e005cb5742baecae9ed1e341`;
- zero PRs abertas;
- FM NFCORE V1 CI #650 SUCCESS no exact main;
- NFCore Plan Governance #71 SUCCESS no exact main;
- NFV1-P02-T03 DONE_CERTIFIED;
- NFV1-P02-T04 era o primeiro item pendente do ledger;
- staging Railway permaneceu somente leitura e sem novo deploy nesta tarefa.

## CURRENT -> TARGET

CURRENT tinha `HumanAccount`, cinco `PortalRole`, permissões, sessão, CSRF,
`HumanAccountRepository`, recuperação de senha e `user.manage`, mas nenhuma
projeção durável `users` nem comandos de administração no Portal.

TARGET desta tarefa é administrar usuários do tenant pelo mesmo sistema de identidade,
sem segunda autenticação e sem autoridade do browser:

`sessão -> user.manage -> tenant/unit scope -> HumanAdministrationService -> store durável -> audit`.

## Controles implementados

- política T04 aprovada pelo dono em 2026-10-07 como conjunto;
- OWNER pode administrar OWNER, ADMIN, OPERATOR, AUDITOR e BILLING do próprio tenant;
- ADMIN pode administrar somente OPERATOR, AUDITOR e BILLING; não pode criar/promover OWNER ou ADMIN;
- OPERATOR, AUDITOR e BILLING falham fechado para administração de usuários;
- tenant vem exclusivamente da sessão autenticada;
- escopo de unidades nunca pode exceder o escopo do ator nem referenciar unidade indisponível;
- `platform_admin` continua flag canônica separada e não é concedível/mutável por esta superfície;
- contas `platform_admin` e a própria conta do ator são somente leitura pela administração de tenant;
- criação usa ID determinístico e senha inicial aleatória que nunca é retornada; ativação usa o fluxo
  existente de recuperação de senha;
- atualização usa `session_epoch` como versão, revoga sessões e resets anteriores e é replay-safe;
- PostgreSQL serializa Idempotency-Key por advisory lock e registra audit no mesmo transaction scope;
- alteração que removeria o último OWNER habilitado é negada;
- e-mail/senha/token não entram no audit;
- navegação `available_surfaces` passa a ser filtrada por permissão no backend;
- nenhuma nova categoria de papel, segunda RBAC, segundo tenant store ou novo auth foi criada.

## Arquivos de implementação

- `src/kordena_fiscal/security/human_administration.py`;
- `src/kordena_fiscal/persistence/postgres.py`;
- `src/kordena_fiscal/control_plane/models.py`;
- `src/kordena_fiscal/runtime/composition.py`;
- `src/kordena_fiscal/web/portal_runtime.py`;
- `src/kordena_fiscal/web/portal_api.py`;
- `portal/app.js`;
- testes de policy, HTTP/runtime, PostgreSQL condicional e frontend.

## Gates locais já executados

- Ruff dos arquivos alterados: PASS;
- Mypy de `src`: PASS, 185 source files;
- Plan Governance local: PASS, 59 tasks, próximo item T04;
- testes focados de identidade/administração/Portal: PASS;
- frontend lint/typecheck/test/build: PASS, 13 testes;
- teste T04 SQLite/HTTP: PASS; variante PostgreSQL está preparada e é executada na CI quando
  `NFCORE_TEST_POSTGRES_DSN` estiver disponível.

A suíte Python completa está sendo executada antes da PR. T04 não será marcada
DONE_CERTIFIED antes de PR, CI, merge protegido, CI da main e closeout.

## Fora de escopo / proibido

Sem deploy, migration externa, staging write, segredo/credencial real, e-mail real,
alteração DNS, operação fiscal real, produção, homologação, custo ou Go-Live.
T05 e tarefas posteriores não foram iniciadas.
