# CHECKPOINT — NFV1-P04-T04 — Container

## Certificação final — prevalece sobre o histórico abaixo

PR #149 MERGED; HEAD `732265ed0e7bab21b48e735ea296a2e8a3af7576`; main `d9f4d1d8c7fd60f927b2f3d3ba8f421a72c9bf82`; árvore PR/main idêntica `d7cbdf8baf65013c4f8542ac390c9c581b01ef7b`. CI #725/run37935705861 (PR) e #726/run37938638870 (main), Governance #146/run37935705764 e #147/run37938638865 SUCCESS. PR/main:41/41 etapas;1666 Python/PostgreSQL,14 frontend,28 Playwright PASS,zero FAIL/zero SKIP;29 novos casos incluídos;um warning TestClient preexistente.

Estado: INTERNALLY_CERTIFIED; fechamento documental aguardando integração/gates.
Merge #149 autorizado explicitamente pelo dono em 2026-10-09:
“Autorizo integrar a PR #149”.
Critério: “Provar processo contínuo, SIGTERM, non-root e health/runtime contract.”

CI main job113847021184; Pytest364.19s (PR323.61s).

Container real da CI: USER10001/PID1, execução contínua idle, Docker HEALTHCHECK
healthy, SIGTERM exit0; durante drain readiness invalida sem interromper o lote.
13 jobs PostgreSQL:10 claimed/succeeded,3 pending;restart termina13/13,
um attempt/audit por job e nenhum replay terminal. SIGTERM/SIGINT durante
bootstrap preservados; ONESHOT não promove continuous readiness; CMD sem
dependências continua fail-closed pelo motivo esperado.
Fixture sintética somente de CI, montada read-only e ausente da imagem.
PostgreSQL e processo/container são reais; dispatch sintético não prova
assinatura, resolver de secrets, destinatário ou efeito externo reais.
Gates integrais:lint/types/plan59/migrations1..16/secret scan/frontend/E2E,
containers/non-root/secure profile/smokes/CVE/SBOM/backup-restore/readiness PASS.
Nenhum teste existente removido, pulado ou enfraquecido.

### Gate P4 interno — matriz de evidência

| Critério | Prova |
|---|---|
| Execução sem ONESHOT | T04: processo contínuo PID1/non-root e health real no container CI |
| Registry explícito | T01/#143/#144: composição governada, mesma outbox/UOW; assinatura ausente falha antes do poll |
| Retry/dead-letter | T02/#145/#146: backoff, fatal, CAS status/attempt e persistência SQLite/PostgreSQL |
| Crash/restart | T02: recuperação por lease; T04: drain/restart de subprocesso e container PostgreSQL |
| Side effects idempotentes internos | Inbox/idempotência/terminal replay/CAS certificados; at-least-once não garante deduplicação externa |
| CI verde | PR #149 e main certificadas em todos os41 gates |

Gate CONTINUOUS_WORKER_CERTIFIED_INTERNAL: PASS condicionado à integração
e gates deste fechamento documental. P4 interno concluído;23/59 tarefas.
Próxima NFV1-P05-T01 — Pré-deploy, não iniciada até esse fechamento.

Read-only pós-merge: API/Portal/PostgreSQL1/1,Worker0/1;deployments históricos
inalterados;patch staged vazio. Nenhum deploy executado. P5/P9/P11 conservam
drift/operação como pendência; P6 conserva assinatura/backend de secrets real.
Readiness comprova poll/snapshot/freshness/lifecycle, não homologação externa.
Grace15s deve comportar lote/timeouts reais antes de implantação. Inventário
TODO/FIXME/HACK dos arquivos T04:nenhum marcador;sem migration/dependência nova.
PRODUCTION_APPROVED=NO;COMMERCIAL_LIVE=NO.

## Histórico de execução

Data:2026-10-09 (America/Sao_Paulo).
Produto:FM NFCORE V1.
Repository:faabio3131/kordena-fiscal-engine-v2.
Main/Main HEAD:`f1b8503cb8dd09325457907469ec5f049d9d5579`.
Branch:feat/nfv1-p04-t04-worker-container.
Branch HEAD/PR/CI PR:a registrar na PR publicada; certificação pendente.
Entrada:PR #148 MERGED; CI #724/run37932404603 e Governance #145/run37932404514 SUCCESS.
Estado:IN_PROGRESS;22/59 tarefas fechadas antes de T04.
Autorização:dono instruiu “Pode fazer”.
Critério:Provar processo contínuo, SIGTERM, non-root e health/runtime contract.

## CURRENT -> TARGET / causa raiz

CURRENT:imagem non-root e CMD exec-form existem; CI executa somente ONESHOT,
que prova bootstrap/DB/migrations, não continuidade. Entrypoint instala sinais
após bootstrap e limpa Event, podendo perder parada recebida durante inicialização.
Saúde T03 é interna ao processo, sem probe de container.
TARGET:mesmo entrypoint/registry/loop/outbox/UOW, processo contínuo verificável,
SIGTERM/SIGINT preservados durante bootstrap/drain, probe privado com freshness
e prova real de PID1/non-root/HEALTHCHECK no container CI.

## Mudanças / autoridades reutilizadas

- worker_main usa Event por execução; instala sinais antes do bootstrap; nunca
  limpa parada recebida; fecha pool em finally e restaura handlers do chamador,
  inclusive após erro de configuração/inicialização/conexão/close.
- WorkerHealthPublisher lê somente ProductionWorkerComposition.health() da T03;
  não consulta DB nem altera fila/dispatch. Thread publica amostra atômica a cada1s.
  Sinal só altera Event; publisher invalida readiness durante drain.
- Dockerfile mantém USER10001:10001 e CMD exec-form; declara SIGTERM e HEALTHCHECK
  pelo módulo worker_health. Nenhum listener HTTP, endpoint/exporter ou dependência nova.
- CI mantém probe ONESHOT e acrescenta prova de execução contínua no mesmo gate;
  nenhuma etapa válida removida ou enfraquecida.
- Fixture sintética somente em tests/support, montada read-only em CI; não incluída
  na imagem. Injeta handler_factory já existente, sem env/dynamic import para selecionar
  handler de produção, chave em src ou factory sintética no CMD real.

## Health/runtime contract

Arquivo privado `/tmp/nfcore-worker-health.json`, modo0600, UID do processo; apenas
version,pid,sampled_at monotônico,ready,stopped. Não contém tenant/unidade/payload,
URL, DSN, erro raw ou segredo. Amostra é escrita via mkstemp+replace atômico.
Probe usa open sem seguir symlink, verifica arquivo regular/owner/permissões/tamanho,
schema/tipos exatos, PID vivo e idade menor que5s e não futura. Nenhuma consulta DB.
CLI `python -m kordena_fiscal.runtime.worker_health`:exit0 somente ready;exit1 em
missing/malformed/stale/dead/unready/stopped. Não imprime conteúdo sensível.

Publicação periódica não fabrica progresso:ready vem do poll/snapshot/freshness
monotônico da T03 (default60s). Idle com poll válido é ready; bootstrap/ONESHOT,
poll falho/snapshot inválido, heartbeat stale e parada não são ready. Fonte quebrada
produz false. Falha de publicação posterior não reentrega trabalho nem encerra loop;
amostra anterior expira. Path inicial não gravável rejeita startup antes de claim.
Docker:interval5s,timeout3s,start-period10s,retries3. Processos longos sem poll concluído
podem ficar unready conforme TTL; orçamento/tuning operacional pertencem P9.

SIGTERM/SIGINT solicitam parada; loop drena apenas lote já claimed, persiste resultados,
não faz novo claim e encerra com0. Compose mantém grace15s. Grace deve comportar o
lote/timeout reais na implantação; deadline externo forçado conserva recuperação
por lease, não promete ausência de repetição de efeito externo. Entrega at-least-once
e deduplicação de destinatário real continuam com limites T02.

## Matriz / evidências

29 novos testes Python:24 locais e5 subprocessos PostgreSQL reais.
- amostras inválidas, limites exatos de freshness, arquivo ausente/malformado/grande,
  permissões, symlink, PID morto e timestamp extremo;
- publisher usa saúde canônica, stop/close, fonte quebrada e falha periódica isolada;
- SIGTERM real durante bootstrap não perdido; configuração/DB falhos fecham pool,
  invalidam saúde antiga e restauram sinais;
- processos idle contínuos com SIGTERM/SIGINT, dois runs/restart, probe positivo/negativo;
- ONESHOT e CMD sem handlers nunca promovem continuous readiness;
- SIGTERM durante dispatch bloqueado invalida saúde mantendo processo para drain;
  13 jobs:10 claimed/succeeded,3 pending;restart termina13/13 sem replay,um attempt/audit.

Prova container CI adicional:PostgreSQL real, USER10001,PID1,HEALTHCHECK healthy,
continuidade idle, SIGTERM exit0, drain e restart duráveis; CMD real sem dependência
rejeitado pelo motivo esperado. Fixture/reset opera somente no DB sintético da CI.
Não prova entrega externa nem disponibiliza handler/assinatura real por inferência.

Dirigidos:63 PASS/19 PostgreSQL SKIP local/zero FAIL.
Ruff PASS;Mypy196 PASS;plan59 PASS;policy migrations1..16/cakto2 PASS;secret scan PASS.
Suíte local completa:1407 PASS/256 PostgreSQL SKIP/zero FAIL em115.91s,um warning
TestClient preexistente. Os três casos de fechamento do pool acrescentados após
coleta da suíte passaram no dirigido final63 PASS;CI executará todos os29 novos casos.
Cinco subprocessos PostgreSQL e Docker exigem CI;DSN/Docker não disponíveis localmente.
Nenhum teste existente removido/enfraquecido;sem migration ou mudança de dependência.

## Staging / blockers / continuidade

Read-only reconfirmado API/Portal/PostgreSQL1/1,Worker0/1;deployments históricos
inalterados;patch staged histórico vazio. Drift permanece P5/P9/P11.
CMD não configurado permanece fail-closed:assinatura/resolver concreto de secrets
P6 e composição operacional da implantação não são fabricados nesta prova interna.
P5 não iniciada;deploy/migration produtiva/credencial/fiscal/comercial real não executados.
PRODUCTION_APPROVED=NO;COMMERCIAL_LIVE=NO.
T04 somente será fechada após CI/evidência,merge específico,CI main e fechamento.
