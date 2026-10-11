# NFV1-P05-T01 — Worker fail-closed e Railway preDeploy audit (2026-10-11)

**Estado deste patch:** CANDIDATE_INTERNAL. Não concluir P05-T01; 27/59 tarefas certificadas internamente continuam imutáveis. PR/CI/merge exigem gates e autorização humana. Não é deploy, secret provider nem homologação fiscal.

## CURRENT comprovado

- `main` antes desta branch: `dd289995febff3e0b0f5a969a1c1c692c02382dc` (PR #163 MERGED); CI #782/run38113501690 e Governance #203/run38113501689 SUCCESS, 2050 pytest, 14 frontend, 28 E2E.
- Sem PRs abertas na entrada. Repositório canônico `faabio3131/kordena-fiscal-engine-v2`.
- Railway **FM NFCORE Staging** (project `b84b290d-f3b4-46a1-9023-0b761cb96b0d`; env ID `c9878b9b-62b2-4a97-b8ba-743c8a3e99ec`, label `production` somente nominal): API/Portal/Postgres18 1/1, Worker 0/1, drift de SHA, sem deploy da main.
- API possui `preDeployCommand=["python scripts/ci/migration_guard.py --apply"]`; duplicado da autoridade canônica pré-deploy; **não foi removido**. Candidato #163 já faz `--apply` falhar fechado quando executado no contexto do serviço Railway.
- No Worker implantado em `1c34ba001935952f83ec0b065144e0b8311a5650`, o Dockerfile chama `worker_main` sem injeção de factory; ONESHOT encerra após probe, sem ONESHOT faltam handlers e o processo falha fechado. Variável `NFCORE_WORKER_ONESHOT` presente, valor desconhecido. Logs deploy do Worker retornaram zero mensagens; não atribuir causa definitiva ao ONESHOT. `main` contém `WorkerWebhookDependencies`, `build_canonical_worker_handlers` e `build_gsm_worker_webhook_dependencies`, mas **o processo Railway ainda não recebe um bootstrap seguro/real**.

## Current → Target deste patch mínimo

**Current:** Worker pode abrir conexão ao banco e fazer checagem de schema antes de detectar ausência, ambiguidade ou invalidade de configuração de handler. API Railway possui gatilho extra de migration que o código futuro rejeita; não existe prova automatizada read-only de que o campo esteja ausente.

**Target interno:** o Worker de execução contínua falha **antes de qualquer conexão ao banco** se não houver exatamente uma composição autorizada de handler ou webhook. O modo ONESHOT continua reservado a probe e sem claims. Um gate CLI que consome snapshot **não secreto** de `Railway describe_service` valida ID do ambiente e ausência de todo `deploy.preDeployCommand`, sem ecoar comandos ou valores. O gate não executa mudança nem confere readiness externa.

## Mapa de impacto / critérios de aceite

- `src/kordena_fiscal/runtime/worker_main.py`: fail-fast antes de construir `PostgresFiscalDatabase`. Não alterar UOW, migrations, HTTP, tenant ou signing. Não usar chave mock em ambiente externo.
- `tests/runtime/test_p05_t01_worker_bootstrap_preflight.py`: ausência/ambiguidade/valor inválido rejeitados sem DB; injeção explícita aceita até o gate seguinte. Não autoriza UI ou handler fantasma.
- `scripts/ci/check_p05_t01_railway_config.py` e testes de contrato: `preDeployCommand` vazio/ausente é o único resultado de conformidade desse campo; comandos desconhecidos também falham fechado. O snapshot deve vir somente de `describe_service` com nome e environment ID exatos. Execução real não provada por testes sintéticos.
- Gates internos obrigatórios: `python3 scripts/check_nfcore_plan.py`, Ruff, Mypy, pytest SQLite/PostgreSQL, frontend lint/typecheck/tests/build, E2E, Docker, scanner de secrets, SBOM, backup/restore CI, CI remoto. Zero FAIL / zero testes mascarados.

## Remoção operacional do preDeployCommand (ainda PENDENTE)

1. Operador com autorização específica identifica projeto `FM NFCORE Staging`, environment ID acima e serviço `nfcore-api`; comprova que `main` e API estão em SHAs diferentes. **O label `production` não significa autorização de produção.**
2. Registrar snapshot *sem valores de variáveis* da configuração real do serviço API e da política de migrações. Inspecionar diff (de `["python scripts/ci/migration_guard.py --apply"]` para `[]`), impacto, rollback; nenhuma outra mudança.
3. Após nova autorização operacional, alterar **somente** `deploy.preDeployCommand` para lista vazia, com procedimento que não dispara deploy; conferir `get_staged_changes` e configurações efetivas. A mudança de config não executa migrations, nem substitui backup.
4. Rodar `python scripts/ci/check_p05_t01_railway_config.py snapshot.json --environment-id c9878b9b-62b2-4a97-b8ba-743c8a3e99ec` com snapshot JSON não secreto atualizado. Mesmo `PASS` atesta **apenas esse campo**, não o schema, Worker ou staging.
5. Se qualquer operação desencadear rollout involuntário, parar, identificar mudança real, proteger dados e acionar governança/rollback; não chamar isso de certificado.
6. Nenhum deploy da `main` antes de backup real com recibo, SQL read-only PG18, restore isolado, provedor GSM/IAM/bootstrap real, Worker autorizado e rollback baseline saudável.

## Dependências operacionais ainda bloqueadas

- **B01:** backup real Railway com status `COMPLETED`, ID/recibo, retenção e teste de recuperação. Não há acesso de backup específico no conector usado.
- **B02:** SQL read-only no PostgreSQL18, schemas NFCore1..17 e Cakto1..2, restore segregado e compatibilidade rollback.
- **B04/P6-T01-B02:** conta/projeto/região/billing/budget, IAM mínimo, workload API/Worker, Google Secret Manager real com testes read/deny, cloud Data Access audit. A conta ainda não foi confirmada; **não criar conta, custos ou credenciais neste patch**.
- **B05:** falta injetar assinatura segura e destino aprovado no processo Railway. O helper scoped GSM atual é para contexto explicitamente delimitado e **não constitui roteamento multi-tenant automático**. Nenhum handler sintético pode ser promovido como real. Worker Railway permanece 0/1, SHA antigo.
- **T02:** deploy de mesmo SHA API/Portal/Worker segue proibido até T01 com provas externas.

## Estado

`P05-T01=[ ] BLOCKED_EXTERNAL`; `EXTERNAL_SECRET_BACKEND_CERTIFIED=NOT MET`; `STAGING_CURRENT_SHA_E2E_CERTIFIED=NOT MET`; `PRODUCTION_APPROVED=NO`; `COMMERCIAL_LIVE=NO`.

Nenhuma consulta de valores secretos, autenticação de Google Cloud, IAM, SQL de staging, backup/restore externo, migration, Railway config mutation, deploy, DNS, billing ou operação fiscal executada.

**Próxima ação após CI:** revisão da PR sem merge automático; posteriormente solicitar autorização operacional específica para correção do preDeployCommand e configurar uma conta Google Cloud quando o dono decidir, respeitando orçamento e segurança.
