# CHECKPOINT — NFV1-P00-T03 — Registrar staging drift

Data: 2026-10-05  
Produto: FM NFCORE V1  
Repository: `faabio3131/kordena-fiscal-engine-v2`  
Main de origem: `eccb40058992023514eeaac5ecfecb7e551df763`  
Branch: `docs/nfv1-p00-t03-staging-drift`  
PR: registrar após abertura  
CI main de origem: FM NFCORE V1 CI #588 — SUCCESS  
Plan Governance main de origem: #17 — SUCCESS

## Objetivo

Persistir a divergência real entre GitHub CURRENT e Railway staging, incluindo:

- main SHA;
- API SHA;
- Portal SHA;
- Worker SHA;
- banco/migrations;
- domínios;
- runtime status;
- blockers formais com IDs e ownership.

## CURRENT -> TARGET

CURRENT observado:

- main: `eccb40058992023514eeaac5ecfecb7e551df763`;
- API: `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- Portal: `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- Worker: `1c34ba001935952f83ec0b065144e0b8311a5650`;
- Postgres 18, 5 GB, migrations 1–12 / cakto_schema=2;
- API/Portal 1/1 online;
- Worker 0/1 running;
- tracing Railway desabilitado;
- sem custom domain;
- sem staged changes atuais.

TARGET desta tarefa:

documentar exatamente esse estado e ligar cada blocker a uma tarefa do cronograma, sem realizar deploy nem correção.

## Entrega

Criado:

`docs/NFCORE_V1_STAGING_DRIFT_2026-10-05.md`

Blockers formais:

- STG-B01 — API drift;
- STG-B02 — Portal drift;
- STG-B03 — Worker drift;
- STG-B04 — Worker 0/1;
- STG-B05 — ausência de exact SHA único no staging;
- STG-B06 — tracing desabilitado;
- STG-B07 — ausência de custom domain;
- STG-B08 — migrations atuais não certificam compatibilidade com main CURRENT.

Todos estão mapeados para tarefas P4/P5/P9/P11.

## Segurança

Auditoria Railway somente leitura.

Nenhum valor de secret/credential foi persistido. Foram usados apenas nomes de variáveis e metadados de deployment.

## Tenant/Unit

Sem alteração.

## Railway

Nenhum deploy, redeploy, restart, variable change, domain change, staged change ou migration foi executado.

## Gate da T03

- documentação coincide com Git/Railway — satisfeito no snapshot;
- matriz de capacidades existe — sim;
- blockers conhecidos possuem IDs — sim.

## Verificações pendentes

- cronograma x ledger 59/59;
- apenas T03 em execução;
- T01/T02 concluídas;
- P01 ainda pendente;
- diff somente documental;
- Plan Governance da PR;
- CI completo da PR.

## Gate de saída

IN_PROGRESS.

## Próxima ação

Abrir PR exclusiva da T03, executar os gates e aguardar merge autorizado. Não iniciar P01-T01.
