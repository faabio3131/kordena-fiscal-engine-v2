# FM NFCORE V1 — Staging Drift Register

**Task:** NFV1-P00-T03 — Registrar staging drift  
**Data/hora da auditoria:** 2026-10-05  
**Repository:** `faabio3131/kordena-fiscal-engine-v2`  
**Main auditada:** `eccb40058992023514eeaac5ecfecb7e551df763`  
**Railway project:** `FM NFCORE Staging`  
**Railway environment label:** `production` — este é apenas o nome do ambiente dentro do projeto de staging e não equivale a produção aprovada.

## 1. Resumo executivo

O staging existe e possui Postgres, API, Portal e Worker, mas **não está reconciliado com a main CURRENT**.

| Componente | Estado runtime | SHA/versão implantada | Diferença para main | Observação |
|---|---|---|---:|---|
| Main GitHub | CI verde | `eccb40058992023514eeaac5ecfecb7e551df763` | 0 | autoridade de código CURRENT |
| nfcore-api | online, 1/1 | `f9b5b2c5b436045947159f1e76be9303f5a95d90` | 36 commits atrás | deploy SUCCESS |
| nfcore-portal | online, 1/1 | `f9b5b2c5b436045947159f1e76be9303f5a95d90` | 36 commits atrás | deploy SUCCESS |
| nfcore-worker | service online, 0/1 running | `1c34ba001935952f83ec0b065144e0b8311a5650` | 118 commits atrás | deploy SUCCESS, processo não rodando |
| Postgres | online, 1/1 | image `ghcr.io/railwayapp-templates/postgres-ssl:18` | N/A | volume persistente 5 GB |

Classificação global do staging:

**REAL / VERSION_DRIFT_PRESENT / NOT_CERTIFIED_AGAINST_CURRENT**

## 2. Banco e migrations

Postgres CURRENT no Railway:

- versão de imagem: PostgreSQL 18;
- região: `sfo`;
- replicas: 1;
- volume: `postgres-volume`;
- mount: `/var/lib/postgresql/data`;
- tamanho: 5000 MB;
- volume state: live.

Evidência do deploy atual da API:

- migration policy: **PASS**;
- versões: `1,2,3,4,5,6,7,8,9,10,11,12`;
- `cakto_schema=2`;
- schema migration staging: before 1–12, applied=(), after 1–12.

Portanto, o banco do staging estava migrado até a versão 12 no deploy atual da API. Isso **não prova compatibilidade com código posterior à SHA implantada**; a reconciliação dessa compatibilidade pertence ao pré-deploy/deploy governado de P5.

## 3. Domínios

### API

Railway service domain:

`nfcore-api-production.up.railway.app`

Target port: 8080.

Custom domains: nenhum.

### Portal

Railway service domain:

`nfcore-portal-production.up.railway.app`

Target port: 8081.

Custom domains: nenhum.

### Worker e Postgres

Sem HTTP custom/service domain aplicável ao uso público.

## 4. Runtime status

### API

- Railway state: online;
- replicas: 1 running / 1 total;
- latest deployment: SUCCESS;
- deployed SHA: `f9b5b2c5b436045947159f1e76be9303f5a95d90`;
- Uvicorn iniciado em `0.0.0.0:8080`;
- `GET /health/ready` retornou 200 em logs do deployment atual;
- runtime log identifica `environment=staging` durante schema migration.

### Portal

- Railway state: online;
- replicas: 1 running / 1 total;
- latest deployment: SUCCESS;
- deployed SHA: `f9b5b2c5b436045947159f1e76be9303f5a95d90`.

### Worker

- Railway service state: online;
- replicas: **0 running / 1 total**;
- latest deployment: SUCCESS;
- deployed SHA: `1c34ba001935952f83ec0b065144e0b8311a5650`;
- build do Dockerfile.worker foi concluído e o container iniciou;
- não há evidência de processo contínuo ativo no snapshot atual.

Isso coincide com o gap arquitetural já congelado em CAP-14: o entrypoint do Worker exige `handler_factory` explícita para execução contínua.

### Postgres

- Railway state: online;
- replicas: 1 running / 1 total;
- volume persistente presente;
- nenhum failure recente reportado no snapshot de 48 horas.

## 5. Tracing e observabilidade Railway

Tracing Railway está desabilitado para:

- nfcore-api;
- nfcore-portal;
- nfcore-worker;
- Postgres.

Auto-instrumentation também está desabilitada/inativa.

Isso não significa ausência total de observabilidade interna do NFCore; significa que a camada de tracing operacional Railway não está ativa.

## 6. Staged changes

No snapshot atual:

- `describe_environment.staged = null`;
- todos os serviços têm `stagedChangeCount = 0`;
- `get_staged_changes.staged = null`;
- nenhum recurso, shared variable ou private-network change está staged.

Um snapshot anterior da mesma sessão havia mostrado um `EnvironmentPatch` vazio em `pendingWork`; a consulta específica mais recente de staged state não confirma patch ativo. Portanto, o CURRENT persistido é **nenhuma alteração staged pendente**.

## 7. Blockers formalmente identificados

| Blocker ID | Fato | Severidade para lançamento | Tarefa dona |
|---|---|---|---|
| STG-B01 | API está 36 commits atrás da main | alta | NFV1-P05-T02 — Deploy reconciliado |
| STG-B02 | Portal está 36 commits atrás da main | alta | NFV1-P05-T02 — Deploy reconciliado |
| STG-B03 | Worker está 118 commits atrás da main | crítica para background runtime | NFV1-P04-T01 / NFV1-P04-T04 / NFV1-P05-T02 |
| STG-B04 | Worker possui 0/1 processo running | crítica para operação assíncrona | NFV1-P04-T01 / NFV1-P04-T02 / NFV1-P04-T04 |
| STG-B05 | Staging não está certificado em um único exact SHA para API/Portal/Worker | alta | NFV1-P05-T02 / NFV1-P05-T04 |
| STG-B06 | Railway tracing está desabilitado | média/alta operacional | NFV1-P09-T01 / NFV1-P11-T03 |
| STG-B07 | API/Portal não possuem custom domain | não bloqueia staging técnico; bloqueia target de produção | NFV1-P11-T02 |
| STG-B08 | Migrations 1–12 estão aplicadas no deploy atual, mas compatibilidade com o CURRENT não foi executada em staging | alta antes de deploy CURRENT | NFV1-P05-T01 / NFV1-P05-T02 |

Nenhum desses blockers é considerado resolvido por esta tarefa. T03 apenas os registra e entrega ownership formal.

## 8. O que esta auditoria NÃO prova

Esta auditoria não prova:

- que a main CURRENT funciona no staging;
- que API/Portal/Worker CURRENT compartilham o mesmo SHA no Railway;
- que o Worker contínuo está operacional;
- que uma migration nova seria segura no staging;
- que tracing/alerts externos estão operacionais;
- homologação fiscal;
- provider fiscal real;
- canal comercial real;
- infraestrutura de produção;
- DNS/TLS de produção;
- `PRODUCTION_APPROVED`;
- `COMMERCIAL_LIVE`.

## 9. Gate P0 / T03

Critérios do cronograma:

- documentação coincide com Git/Railway: **SATISFEITO NESTE SNAPSHOT**;
- matriz de capacidades existe: **SIM — `docs/NFCORE_V1_CAPABILITY_MATRIX_2026-10-05.md`**;
- blockers conhecidos possuem IDs: **SIM — STG-B01 a STG-B08, todos ligados a tarefas do cronograma**.

A certificação formal da T03 ainda depende de PR, CI, merge autorizado e CI pós-merge.

## 10. Próximo target após fechamento da T03

Com T01, T02 e T03 certificados, o gate P0 pode ser encerrado como:

`CURRENT_RECONCILED_2026_10_05`

A próxima tarefa canônica será:

`NFV1-P01-T01 — Identificar composição canônica`

Nenhum deploy Railway é autorizado ou executado por este registro.
