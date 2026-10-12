# NFV1-P05-T01 — Execução Web: backup lógico e pré-deploy (2026-10-12)

**Estado:** CURRENT confirmado em GitHub main `019d7dcfdba7fd7d2c5604d1dcc52a9dac2367d7`, CI #818 e Governance #239 SUCCESS; Railway API/Portal ainda na revisão `f9b5b2c5b436045947159f1e76be9303f5a95d90`. Esta PR não realiza merge, migrations, deploy nem altera Railway. O usuário priorizou a paridade Web e a implantação integral do código já construído em staging.

## Evidência operacional real (não é certificação da P05 inteira)

- Banco Railway Staging PostgreSQL 18.6: consulta `SELECT 1` bem-sucedida em SSH autenticado.
- `fm_schema_migrations`: versões 1..12 confirmadas somente leitura; main requer 1..17, portanto migrations 13..17 pendentes.
- `fm_cakto_schema_migrations`: relação ausente na consulta. Governar criação/migration Cakto 1..2 pelo mesmo orquestrador, sem criar tabela ad hoc.
- Em 2026-10-12, operador realizou exportação `pg_dump --format=custom` via SSH para arquivo `*.dump.age` criptografado localmente com age. SHA256 do ciphertext: `58ae2d97cc40f26c89900e7f349211f89770255f57427231d38ac5f8bafeded6`. Tamanho informado 78.572 bytes.
- Restore real em PostgreSQL 18 isolado no Windows: `PG_RESTORE_EXIT_CODE: 0`, 34 tabelas, `RESTAURACAO_ISOLADA_OK`, `AMBIENTE_LOCAL_DESCARTADO: confirmado`. Evidência apresentada pelo operador em print no chat, **não** gerada por CI; dados do backup/chave ficam fora do repositório.
- Não foi apresentado recibo de armazenagem independente ou custódia externa da chave; não declarar RPO/RTO, retenção externa nem backup produtivo. Railway PITR e snapshots de volume continuam indisponíveis no plano atual.

## Alteração interna desta PR

- Adiciona verificador estritamente para staging e explicitamente opt-in (`NFCORE_RAILWAY_BACKUP_MODE=local-logical-attested`) que exige IDs exatos do Railway, arquivo ciphertext local atual (<=72h), SHA256 pinado, cabeçalho age, descriptografia completa em memória e cabeçalho PGDMP.
- A restauração anterior é **atestada pelo operador**, não testada novamente pelo verificador. O driver informa `LOGICAL_BACKUP_OPERATOR_ATTESTED`, distinto de um recibo PITR do Railway. O modo PITR existente permanece como padrão.
- `run_staging_deploy.sh` não habilita implicitamente `NFCORE_SCHEMA_MIGRATION_APPROVED`; a aprovação de migration deve ser explícita. Nenhum segredo ou arquivo de cliente vai para Git.
- Gates dirigidos: arquivo íntegro, adulteração de SHA/ciphertext, escopo não staging, ausência de atestado, idade do backup, descriptografia falha, driver não chamando PITR. CI/PR são necessárias para comprovação interna.

## Pendências para liberar P05-T02

1. Aprovar e integrar esta PR após CI e governança.
2. Com operador e arquivo físico local, executar o verificador de backup; confirmar também a custódia externa da chave privada.
3. Reconciliar a migration única 13..17 + Cakto 1..2 e compatibilidade dos baselines. Obter autorização humana **específica** para modificar o schema do banco de staging.
4. Confirmar composição **real** de assinatura/handler/identidade GSM do Worker e corrigir seu estado operacional; o entrypoint atual `worker_main.run()` sem handler/assinatura não pode executar continuamente. Não criar handler sintético para fingir saúde.
5. Implantar API, Worker e Portal na mesma revisão somente depois desses gates e autorização de deploy; executar smoke e E2E Web reais.

**Classificação:** B01 evidência lógica parcial real recuperável; B02 versões SQL confirmadas e migrations pendentes; B04 external GSM/Worker bloqueado. NFV1-P05-T01 continua `[ ] BLOCKED_EXTERNAL`. P05-T02 não iniciada. Sem lançamento comercial/fiscal real.
