# NFV1-P05-T01 — Autoridade única de migrations, runtime e Worker — 2026-10-10

**Estado:** CANDIDATE_INTERNAL, testes/CI desta PR pendentes. A tarefa canônica **P05-T01 permanece `[ ] bloqueado externo`**; não iniciar T02, não autorizar deploy por este checkpoint.

## 1. CURRENT verificado, fonte GitHub/Railway

- GitHub `main=0fdcce7de18a779ecf7a193fbd01b83d8087c5c5`; PR #162 MERGED; CI #762/run38093599204 SUCCESS (41/41 etapas, 2038 Pytest PASS, 14 frontend PASS, 28 Playwright PASS), Governance #183/run38093599099 SUCCESS; zero PRs abertas na entrada desta intervenção. Plano/ledger 59 tarefas; 27 concluídas; próxima P05-T01.
- Railway projeto `FM NFCORE Staging` `b84b290d-f3b4-46a1-9023-0b761cb96b0d`, environment ID `c9878b9b-62b2-4a97-b8ba-743c8a3e99ec`, rotulado `production` **apenas nominalmente**: API/Portal/Postgres **1/1**, Worker **0/1 RUNNING**, mesmo que a API Railway reporte `Online` e deployment Worker `SUCCESS`. API/Portal deployados na revisão `f9b5b2c5b436045947159f1e76be9303f5a95d90`; Worker na `1c34ba001935952f83ec0b065144e0b8311a5650`. Nenhum é o SHA da main.
- Config API Railway contém `deploy.preDeployCommand=["python scripts/ci/migration_guard.py --apply"]`. O orquestrador `scripts/ci/run_staging_deploy.sh` também chama `migration_guard.py --apply` **depois** do backup comprovado. Há uma rota dupla até a mudança operacional controlada da configuração da API.
- Inspeção de código revelou **duas rotas adicionais de mutation no startup**: `RuntimeApi.__init__` e `worker_main.run` chamavam `PostgresFiscalDatabase.initialize()` mesmo em staging/produção, operação que executa DDL/advisory lock e instala migrations ausentes. Isso podia contornar o backup/orquestrador mesmo que o comando Railway fosse removido.
- Worker `worker_main.run` tem modo `NFCORE_WORKER_ONESHOT=true` que valida DB e encerra sem operar continuamente. Sem modo oneshot, exige handlers autorizados e `WebhookSecurity`; sem esse bootstrap, falha fechado. **Somente o nome da variável aparece no Railway; seu valor não foi lido.** Logs deploy do Worker atual retornaram zero entradas; portanto a causa exata de 0/1 **não está demonstrada**. Reiniciar sem prova seria inadequado.
- Postgres Railway usa `postgres-ssl:18`, volume 5 GB; não há consulta SQL, backup concluído, restauração PG18 ou GSM IAM real certificados.

## 2. Correção interna isolada proposta

1. Adicionar `PostgresFiscalDatabase.require_current_schema()` **read-only**, exigindo versões exatamente 1..17, derivadas do último versionamento `SECRET_BINDING_VERSION`; estado ausente, divergente ou adiante falha sem DDL. `migration_guard.py --check-policy` mantém o gate de catálogo e de versões contíguas.
2. Para API e Worker em staging/production: trocar `database.initialize()` por `database.require_current_schema()`, falhar fechado se DB estiver desatualizado. Em ambiente de desenvolvimento/testes preservar o bootstrap explícito existente. Sem segunda persistência/autoridade.
3. O comando canônico `migration_guard.py --apply` recusa a execução **quando detecta o contexto real `RAILWAY_SERVICE_ID`**, protegendo contra o `preDeployCommand` configurado no serviço. Isso é mitigação contra disparo acidental, **não prova de que a configuração foi removida**, nem substitui controles humanos. Um runner externo governado continua sendo o único caminho planejado.
4. Adicionar regressões contra mutação no startup, versões faltantes/extras, rollback de boot e preDeploy Railway; adaptar os doubles de staging para não mascararem mutação.
5. Executar Ruff, Mypy, Python/PostgreSQL, frontend, E2E, containers, segurança e governança na PR; sem disfarçar falhas, sem marcar P05-T01 concluída.

## 3. O que ainda bloqueia homologação operacional

- **B01:** recibo de backup real Railway com ID/status, retenção e recuperação verificáveis; confrontar schema real CLI com parser fail-closed antes de liberar migration.
- **B02:** consulta SQL **somente leitura** do PostgreSQL 18 (SELECT1/schema versions); restore/replay em instância segregada e governada; evidência de integridade.
- **B04 / P6-T01-B02:** Google Cloud Secret Manager externo — projeto/billing/budget/região aprovados, identidade API/Worker, mínimo IAM, auditoria Data Access, bootstrap e prova de leitura/negação sem expor segredo.
- **B05:** Worker0/1 sem causa confirmada, falta runtime contínuo com handlers reais e egress governado, API/Portal/Worker ainda em SHA antigo, baseline saudável, teste contrato Railway CLI real e rollback.
- **Risco de configuração:** após o patch interno certificado, remover **mediante autorização específica** o preDeployCommand redundante da API, só no ambiente FM NFCORE Staging, **sem disparar deploy**. Provar configuração efetiva por leitura; checar se existem outros gatilhos/migration autorun. A simples remoção não prova Worker/PG18/GSM/backup.
- **Operações não autorizadas neste bloco:** escrita em variável Railway, deploy/redeploy, mudança de configuração externa, SQL em staging, backup/restore reais, conta IAM/GCP, segredo, produção fiscal, DNS.

## 4. Estado/governança

`P05-T01=BLOCKED_EXTERNAL`, `EXTERNAL_SECRET_BACKEND_CERTIFIED=NOT MET`, `STAGING_CURRENT_SHA_E2E_CERTIFIED=NOT MET`, `PRODUCTION_APPROVED=NO`, `COMMERCIAL_LIVE=NO`.

**Próxima ação:** revisão CI da PR e decisão humana de merge; depois obter autorização operacional separada para leitura de valores estritamente não secretos necessários (ex. ONESHOT), retirada governada do preDeployCommand e execução real de backup/SQL/GSM com evidências. Não promover task até os comprovantes efetivos.
