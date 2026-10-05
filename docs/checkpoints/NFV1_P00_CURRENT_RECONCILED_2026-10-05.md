# CHECKPOINT — P0 CURRENT_RECONCILED_2026_10_05

Data: 2026-10-05  
Produto: FM NFCORE V1  
Fase: P0 — RECONCILIAÇÃO DE GOVERNANÇA E CURRENT  
Status: DONE_CERTIFIED  
Gate de saída: `CURRENT_RECONCILED_2026_10_05`

## Base certificada

- repository: `faabio3131/kordena-fiscal-engine-v2`;
- main pós-T03: `3837d1e6b5a3c38e3aa2ceb032fb952fab700a4c`;
- PR #105: MERGED;
- NFCore Plan Governance #26: SUCCESS;
- FM NFCORE V1 CI #597: SUCCESS;
- PRs abertas antes deste closeout: 0.

## Tarefas do P0

- `NFV1-P00-T01 — Reconciliar documentação CURRENT`: DONE_CERTIFIED;
- `NFV1-P00-T02 — Congelar matriz de capacidades`: DONE_CERTIFIED;
- `NFV1-P00-T03 — Registrar staging drift`: DONE_CERTIFIED.

## Gate

- documentação coincide com Git/Railway: PASS;
- matriz de capacidades existe: PASS;
- blockers conhecidos possuem IDs: PASS.

## Artefatos canônicos produzidos

- `docs/NFCORE_V1_COMMERCIAL_LAUNCH_CURRENT.md`;
- `docs/NFCORE_V1_CAPABILITY_MATRIX_2026-10-05.md`;
- `docs/NFCORE_V1_STAGING_DRIFT_2026-10-05.md`;
- `docs/NFCORE_V1_EXECUTION_LEDGER.md`;
- checkpoints T01, T02 e T03.

## Railway CURRENT verificado no fechamento

Project: `FM NFCORE Staging`.

- API: online 1/1 em `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- Portal: online 1/1 no mesmo SHA;
- Worker: service online, deployment `1c34ba001935952f83ec0b065144e0b8311a5650`, 0/1 running;
- Postgres: online 1/1, volume persistente;
- tracing Railway: desabilitado;
- custom domains: nenhum;
- todos os serviços com `stagedChangeCount=0`;
- Railway ainda expõe um `EnvironmentPatch` vazio em `pendingWork` com `changes=[]`, sem alteração substantiva staged.

## Blockers carregados adiante

- STG-B01 — API drift;
- STG-B02 — Portal drift;
- STG-B03 — Worker drift;
- STG-B04 — Worker 0/1;
- STG-B05 — ausência de exact SHA único no staging;
- STG-B06 — tracing desabilitado;
- STG-B07 — ausência de custom domain;
- STG-B08 — compatibilidade de migrations com CURRENT ainda não certificada no staging.

Esses blockers têm ownership formal em P4/P5/P9/P11 e não impedem o fechamento do P0, porque o objetivo do P0 é reconciliar CURRENT e tornar as pendências explícitas, não resolvê-las antecipadamente.

## Segurança

Durante T03, CI-B01 detectou 3 CVEs CRITICAL corrigíveis na base Debian usada por API/Worker. A correção foi aplicada sem waiver e certificada em CI #596 e novamente pós-merge no CI #597, com Container vulnerability policy verde.

## Produção/comercial

- `PRODUCTION_APPROVED=NO`;
- `COMMERCIAL_LIVE=NO`;
- produção real não foi provisionada/certificada;
- homologação fiscal oficial permanece pendente;
- nenhuma ação de deploy, DNS, secret real ou produção foi executada no P0.

## Próxima ação canônica

Após o merge deste closeout documental, iniciar:

`NFV1-P01-T01 — Identificar composição canônica`

Não iniciar T02/P2 ou qualquer fase posterior antes de cumprir a ordem do ledger.
