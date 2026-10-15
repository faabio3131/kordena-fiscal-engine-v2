# NFCore — auditoria Railway CURRENT somente leitura (2026-10-15)

**Escopo:** projeto Railway `FM NFCORE Staging`, ambiente interno denominado `production` (o nome não é prova de produção fiscal). Dados obtidos de `describe_environment`, `environment_status`, `list_deployments` e `describe_service`. Sem deploy, restart, alterações, secrets ou migrations.

## Versões LIVE confirmadas

| Serviço | ID do deployment atual | Commit do deployment | Status Railway |
| --- | --- | --- | --- |
| API | `518b5ca0-834b-46ed-98ed-aefcbc4481d0` | `22a1fbf10e6a90704dcc2d63975cb29ed1373b26` | SUCCESS / online |
| Worker | `71a196db-2f4e-4048-bdfd-e2deefb051be` | `22a1fbf10e6a90704dcc2d63975cb29ed1373b26` | SUCCESS / online |
| Portal | `35b7aafc-b509-4851-a572-c0bd46781977` | `f9b5b2c5b436045947159f1e76be9303f5a95d90` | SUCCESS / online |
| PostgreSQL | `ce9b66e7-6de7-4c70-9852-8ca1936a719b` | imagem `ghcr.io/railwayapp-templates/postgres-ssl:18` | SUCCESS / online |

**Main GitHub consultada:** `4f7d520ef66831edb56d8d68c60ca24cc17b51f4`; **PR #188 DRAFT**, ainda não mergeada. Nenhum dos três aplicativos executa o HEAD CURRENT de `main`. As revisões API/Worker e Portal são diferentes. Não presumir compatibilidade de contratos entre elas.

## Wiring Railway lido (nomes de variáveis, nunca valores)

- **API:** fonte `faabio3131/kordena-fiscal-engine-v2`, branch `main` fixada em `22a1fbf...`, `Dockerfile.api`; domínio `nfcore-api-production.up.railway.app`; nomes de variáveis incluem `DATABASE_URL`, `NFCORE_DEPLOY_REVISION`, `NFCORE_API_GSM_*`, `NFCORE_SECRET_BACKEND`, `NFCORE_ALLOWED_ORIGINS`, `NFCORE_PERSISTENCE_BACKEND`. A existência do nome não comprova valor correto, validade de segredo ou bootstrap.
- **Worker:** mesma fonte e commit da API, `Dockerfile.worker`; nomes incluem `DATABASE_URL`, `NFCORE_WORKER_GSM_*`, `NFCORE_WORKER_ONESHOT`, `NFCORE_SECRET_BACKEND`. Status online não comprova claim, assinatura, entrega ou continuidade fiscal.
- **Portal:** fonte `main`, sem commit pin explícito na configuração, `Dockerfile.portal`; última imagem é de commit antigo; domínio `nfcore-portal-production.up.railway.app`; nomes de variáveis: `NFCORE_PORTAL_API_UPSTREAM`, `NFCORE_DEPLOY_REVISION`, `NFCORE_PASSWORD_RESET_TTL_MINUTES`. O valor do upstream não foi exposto nem validado.
- **Postgres:** volume `postgres-volume`, sem evidência de schema/migrations ou conectividade de application query nesta auditoria.
- Sem staged changes. Cada serviço com uma réplica, `environment_status` classificou os quatro `online`, sem falhas recentes ou warnings/criticals no período consultado.

## Classificação factual de gaps

1. **CONFIRMADO — REVISION_SKEW:** API/Worker `22a1fbf...` ≠ Portal `f9b5b2c...` ≠ `main 4f7d520...`. Forte candidato a paridade Web deficiente; não basta para atribuir cada tela ausente à divergência.
2. **CONFIRMADO — GATE P05 PENDENTE:** API, Portal e Worker não estão publicados na mesma revisão imutável CURRENT. Não houve homologação funcional nesta inspeção.
3. **NÃO CONFIRMADO:** retorno real de `/health/ready` e login/bootstrap de usuário em runtime, sessão, RBAC/tenant, persistência, GSM real, egress, rotas comerciais e jornadas browser E2E. A tentativa pública de acesso às páginas via ferramenta externa não retornou conteúdo verificável; não interpretar como indisponibilidade do serviço.
4. **RISCO:** atualizações não coordenadas ou automatic deploy podem deixar a composição novamente divergente. Evitar redeploy isolado sem plano, SHA imutável, migrations/rollback e aprovação.

## Next gate (sem execução externa)

Conciliar revision alvo e preflight P05, confirmar backups, migrations, GSM/segredos e verificações de segurança; preparar plano de publicação coordenada API/Portal/Worker na **mesma revisão**, com health/readiness, smoke, E2E e rollback; solicitar autorização específica de deploy/migrations/segredos antes de agir. Não refazer frontend/domínio: primeiro validar a migração existente no ambiente sincronizado.
