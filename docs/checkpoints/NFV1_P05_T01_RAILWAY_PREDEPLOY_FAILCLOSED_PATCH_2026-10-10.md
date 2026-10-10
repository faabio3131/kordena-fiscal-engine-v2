# NFV1-P05-T01 — Patch B05 do driver Railway: evidência fail-closed — 2026-10-10

**Estado de implementação:** CANDIDATA EM PR — não certificada, não mergeada. Este checkpoint integra a mesma NFV1-P05-T01; não abre nova tarefa, não promove T01 para concluída e não autoriza P05-T02.

## Entrada CURRENT

- Repositório `faabio3131/kordena-fiscal-engine-v2`, main `3a14cf5dff00f892b0c8b3502fb2e12d13be6f87`; PR #161 MERGED, CI #753 e Governance #174 SUCCESS; cronograma 59 tarefas, 27 concluídas; T01 `[ ] bloqueado externo`.
- Railway projeto FM NFCORE Staging / environment label `production` (rótulo não certifica produção), API/Portal/Postgres 1/1, Worker **0/1 running** mesmo com deployment `SUCCESS`; Postgres volume 5GB, imagem `postgres-ssl:18`.
- Driver anterior admitia `SUCCESS` sem SHA, processo vivo ou identidade de deployment nova. `backup` imprimia `BACKUP_REQUESTED` sem confirmar término/retention. Captura de baseline escolhia deployment histórico com status SUCCESS mesmo se Worker0/1.

## Intervenção interna autorizada

1. Mantido `scripts/deploy/drivers/railway.sh` como **único driver canônico**. Preservados argumentos de contrato, autorização humana e `NFCORE_RAILWAY_REAL_EXECUTION_ENABLED` default false.
2. Helper puro `scripts/deploy/railway_evidence.py`, que **não acessa rede, token, banco ou secrets**: valida JSON oficial de `railway deployment list --json` (ID/status/meta.commitHash), `railway status --json` (projeto/ambiente/serviceInstances/latestDeployment/activeDeployments/instances RUNNING) e `railway postgres pitr backup create/list --json` (request id/nome exato, receipt COMPLETED/completedAt e expiresAt futura).
3. `prepare-rollback` exige evidência de baseline vivo e SHA40 por API/Worker/Portal antes de backup, escreve arquivo durável de baseline somente após todos passarem. Worker 0/1 bloqueia.
4. `backup` não confunde REQUESTED e COMPLETED; aguarda prova exata de ID, nome, término e retenção válida; schema/response desconhecida bloqueia. Sem backup comprovado, `run_staging_deploy.sh` para antes de migration.
5. `deploy` cruza SHA exato, deployment ID novo (não o existente antes do upload), status SUCCESS e réplicas realmente RUNNING no mesmo serviço/ambiente/projeto; falha/timeout/versão diferente/0 instâncias bloqueiam. `verify-worker` repete o gate. `rollback` exige revisão antiga e instâncias ativas antes de declarar READY, não apenas solicitação.
6. Testes novos: `tests/runtime/test_p05_t01_railway_evidence.py`, `tests/runtime/test_p05_t01_railway_driver_integration.py` (CLI sintético positivo/Worker0), adaptação dos testes históricos de driver que antes aceitavam SUCCESS isolado. Testes legítimos não removidos. Sem AWS/GSM/DB real, sem deploy ou migration.

## Limites e bloqueios remanescentes

- **Contrato de backup Railway real ainda NÃO validado na conta**: a documentação oficial confirma `backup create`, `backup list` e `--json`, mas não prova os campos concretos `completedAt`, `expiresAt`, nem estado `COMPLETED` do ambiente. O parser **falha fechado** se esses campos não existir ou divergirem. **Não certificar B01** até obter output/provider receipt sanitizado de operação real aprovada, revisar adapter se necessário e testar. Dados falsos não provam cloud.
- **T01-B02** SQL, migrations e restore compatível com Postgres18 real não certificados.
- **T01-B04 / P6-T01-B02** projeto/conta/orçamento/identidade/IAM/auditoria/bootstrap/acesso GSM reais não confirmados; Worker 0/1 não foi alterado.
- **T01-B05** melhoria de segurança aplicada ao código candidato, mas identidade exata do upload e contrato real `railway status --json` ainda exigem homologação operativa. `run_staging_deploy.sh` continua a invocar migration_guard após backup, porém o Railway API mantém `preDeployCommand=["python scripts/ci/migration_guard.py --apply"]`; **risco de duas autoridades/execuções, deve ser reconciliado sob autorização externa específica antes de qualquer deploy**. Não declarar pronto/seguro para deploy real por CI sintética.
- **T01-B01/B02/B04/B05** permanecem pendentes até evidência externa/operacional. `EXTERNAL_SECRET_BACKEND_CERTIFIED=NOT MET`, `STAGING_CURRENT_SHA_E2E_CERTIFIED=NOT MET`, `PRODUCTION_APPROVED=NO`, `COMMERCIAL_LIVE=NO`.
- Autorização `Pode fazer essa correção?` aplica-se a branch, implementação, testes, PR **sem merge**, NÃO a IAM/projeto/gasto, backup real, SQL, deploy, config Railway, DNS/produção ou operação fiscal.

## Matriz de aceite interno ainda pendente

- CI da PR no SHA final: Ruff, Mypy, Pytest/PostgreSQL, 14 frontend, Playwright, container, security/SBOM, backup/restore sintético e Governança.
- Asserções causais: rejeição Worker0, status-only, SHA errado, ID antigo, instância stopped/crashed, receipt pending/failed/expirada, provider malformado; caminho sintético positivo completo.
- Revisar diff, atualizar PR com IDs de CI/HEAD/Governance; **merge apenas por autorização específica**. Após merge autorizado, repetir CI completa na main.

Fontes Railway: `https://docs.railway.com/cli/deployment`, `https://docs.railway.com/cli/status`, `https://docs.railway.com/cli/postgres`, código CLI `src/commands/status.rs` e `src/commands/output/service_summary.rs`.
