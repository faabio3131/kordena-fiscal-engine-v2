# NFV1-P05-T01 — Revalidação READ-ONLY do pré-deploy — 2026-10-10

**Classificação:** PENDING / BLOCKED_EXTERNAL. Este checkpoint é uma atualização da **mesma tarefa canônica P05-T01**, não uma nova fase nem uma certificação de staging. Operação autorizada pelo dono ("Executar a próxima etapa") somente na parte não destrutiva. **Nenhum deploy, migration de staging, acesso SQL, backup, IAM ou credencial real foi executado.**

## 1. CURRENT verificável

- Repositório `faabio3131/kordena-fiscal-engine-v2`: `main` `088735ed2a34ed1f372e62e4208cad3389c48f1d`, PR #160 MERGED; CI main #751/run38071518049 e Governance #172/run38071518015 **SUCCESS**, 41/41; 2.022 Python/PostgreSQL, 14 frontend, 28 Playwright PASS. Nenhuma PR aberta no início da auditoria. Plano/ledger: 59 IDs na mesma ordem, **27/59 concluídas**, primeira pendente **NFV1-P05-T01** em `bloqueado externo`. T04/P6 completou certificação **interna**; `EXTERNAL_SECRET_BACKEND_CERTIFIED=NOT MET`.
- Railway: projeto **FM NFCORE Staging** `b84b290d-f3b4-46a1-9023-0b761cb96b0d`, ambiente `c9878b9b-62b2-4a97-b8ba-743c8a3e99ec`, rotulado `production` dentro do projeto de staging; a palavra `production` **não autoriza produção**. Região `sfo`. Inspeção feita por `describe_environment`, `environment_status`, `list_deployments` e `describe_service` **somente leitura**.
- **API**: deployment `c0f8fb2b-30e3-45f8-a814-73c0ba97506b`, revisão `f9b5b2c5b436045947159f1e76be9303f5a95d90`, `SUCCESS`, **1/1 running**.
- **Portal**: deployment `35b7aafc-b509-4851-a572-c0bd46781977`, mesma revisão antiga `f9b5b2c5b436045947159f1e76be9303f5a95d90`, `SUCCESS`, **1/1 running**.
- **Worker**: deployment `3215f498-0aa1-4ce3-8e61-cc74b72b68b6`, revisão `1c34ba001935952f83ec0b065144e0b8311a5650`, `SUCCESS`/`Online` segundo status Railway, mas **0/1 running**. Serviço com `restartPolicyType=NEVER`, fonte `main`, variável de **nome** `NFCORE_WORKER_ONESHOT` presente; **valor não consultado**. `NFCORE_DEPLOY_REVISION` ausente da lista de nomes do Worker. Ausência de crashes recentes não prova execução contínua.
- **Postgres**: deployment `ce9b66e7-6de7-4c70-9852-8ca1936a719b`, imagem `ghcr.io/railwayapp-templates/postgres-ssl:18`, **1/1 running**, volume `postgres-volume` `c36ea345-b082-4379-9407-c94e9918a01c`, 5.000 MB, região `sfo`. Sem leitura SQL, schema version ou prova de backup concluído.
- Ambiente sem patch staged efetivo segundo `describe_environment` (`staged=null`); `environment_status` ainda expõe operação histórica `patch:8d720a42-c942-4afb-8bf5-cc22fce595cd` com `changes=[]`: diferença observacional, **não é autorização de commit**.
- `scripts/ci/run_staging_deploy.sh` chama `prepare-rollback → backup → migration_guard.py --apply → deploy`; entretanto `scripts/deploy/drivers/railway.sh` no passo `backup` imprime `BACKUP_REQUESTED`, **sem aguardar recibo de conclusão**; `wait_for_success` aceita apenas `railway deployment list` status `SUCCESS`, sem validar réplica ativa, operação atual, SHA da aplicação ou readiness.
- Configuração runtime Railway da **API** ainda possui `preDeployCommand=["python scripts/ci/migration_guard.py --apply"]`. Esta segunda rota potencial de aplicação de migrations pode executar antes da confirmação de backup, portanto deve ser reconciliada **antes de qualquer T02/deploy**, sem alterar configuração agora.
- Suite PostgreSQL da CI roda banco descartável sintético; **não prova compatibilidade do restore com a instância real PostgreSQL 18 do Railway**, nem estado de migrations, PITR, retenção ou rollback do staging.

## 2. Matriz de gate / riscos

| ID | Condição de saída necessária | Evidência agora | Classificação |
|---|---|---|---|
| T01-B01 | backup real concluído e recuperável com ID/status/escopo/horário/retenção comprovados, antes de migration | apenas comando de solicitação `BACKUP_REQUESTED`; nenhum recibo de backup real consultado | **BLOCKED_EXTERNAL** |
| T01-B02 | SQL `SELECT 1`, versões reais de migrations e Cakto, compatibilidade de restore/rollback e Postgres saudável | replica DB1/1 e Postgres18, sem sessão SQL/receipt; CI sintética não substitui | **BLOCKED_EXTERNAL** |
| T01-B03 | scripts de restore/checksum, SHA40 e captura de baseline seguros | correções já integradas na PR #151; CI atual #751 verde | **DONE_INTERNAL**, não cert. externa |
| T01-B04 / P6-T01-B02 | acesso real Google Secret Manager com projeto/ambiente, orçamento, identidade API/Worker, IAM mínimo, audit e bootstrap homologáveis; Worker real composto | provider/política/adapters testados **internamente**, sem prova de IAM/GSM real; Worker 0/1 | **BLOCKED_EXTERNAL** |
| T01-B05 | deploy certo com mesma revisão imutável API/Portal/Worker e réplicas saudáveis; rollback baseline ativo | driver aceita SUCCESS sem réplica/SHA; runtime Worker0/1; API/Portal old SHA | **BLOCKED_INTERNAL + EXTERNAL** |
| Ordem de migration | nunca aplicar migration antes do backup confirmado; eliminar dupla execução entre driver e preDeploy da API | preDeploy API ainda configurado; backup driver só solicita, não confirma | **BLOCKER CRÍTICO ANTES DO DEPLOY** |

**Conclusão:** `NFV1-P05-T01` continua `[ ] bloqueado externo`. `STAGING_CURRENT_SHA_E2E_CERTIFIED=NOT MET`; `EXTERNAL_SECRET_BACKEND_CERTIFIED=NOT MET`; `PRODUCTION_APPROVED=NO`; `COMMERCIAL_LIVE=NO`. Nenhum status `SUCCESS` isolado comprova runtime funcional ou rollout do SHA atual.

## 3. CURRENT → TARGET / execução permitida

**Próxima unidade de trabalho técnica, ainda dentro de T01:** especificar/implementar em PR pequena a correção **fail-closed** do contrato `scripts/deploy/drivers/railway.sh` e de seu teste canônico: exigir identidade de deployment novo, SHA exato, réplica/processo ativos e prova explícita de backup `COMPLETED` antes da migration; falhar se o provider não expuser comprovante confiável. A resposta do CLI precisa ser validada com contrato/schema real antes de conectar à automação, sem substituir por variáveis ambientais autodeclaradas. Atualizar tratamento de falha de migration/deploy parcial e reconciliar `preDeployCommand` apenas **mediante autorização operacional própria para alteração da configuração Railway**. Não fabricar CI mock como prova runtime.

**Pré-requisitos externos, não executados:** confirmar projeto Google Cloud, billing/budget/região e política operacional aprovada; identidade API e Worker; IAM secretAccessor por recurso e logs auditáveis; acesso governado apenas por canal operacional. Confirmar método de obtenção de recibo do Railway backup/PITR/retention e canal para consultas SQL **somente leitura**, sem copiar DSN ou dados de clientes para Git/chat.

**Gates para promover T01**: CI+governance do patch B05, SQL/backup/restore/rollback baseline real, identidade/GSM real e Worker verificados; documentação com evidence IDs e horários; autorização humana antes de conta/gasto/IAM/segredo, deploy, alteração externa de config/migration/produção. **Não iniciar T02 para fugir de T01.**

## 4. Fontes e limitações

Código canônico: `scripts/deploy/drivers/railway.sh`, `scripts/ci/run_staging_deploy.sh`, `scripts/ci/staging_preflight.sh`, `scripts/deploy/railway_graphql.py`, `tests/runtime/test_p05_t01_predeploy_scripts.py`, `tests/runtime/test_cl15a_railway_staging_contract.py`; plano, ledger, `docs/checkpoints/NFV1_P05_T01_PREDEPLOY_2026-10-09.md`, política `docs/NFV1_P06_T01_SECRET_PROVIDER_POLICY_PROPOSAL_2026-10-09.md`. Documentação Railway consultada sobre `deployment list --json` e `status --json` confirma distinção entre status do deployment e informações de réplicas: https://docs.railway.com/cli/deployment , https://docs.railway.com/cli/status .

**Nenhum valor de variável, credential, token, material fiscal, cliente, backup real ou conteúdo do banco foi lido.** Resultados Railway são observações de painel/plugin, não smoke E2E real nem homologação GSM.
