# CHECKPOINT — NFV1-P04-T03 — Observabilidade do Worker

Data: 2026-10-09 (America/Sao_Paulo).
Produto: FM NFCORE V1.
Repository: faabio3131/kordena-fiscal-engine-v2.
Main/Main HEAD: `ee0c14cf0979561bc20f655fd71819552f67bbdf`.
Branch: feat/nfv1-p04-t03-worker-observability.
Branch HEAD/PR/CI PR: a registrar na PR publicada; certificação pendente.
CI main de entrada: #720/run37886789334 e Governance #141/run37886789343 SUCCESS.
PR #146 MERGED; P04-T02 fechada;21 tarefas concluídas antes de T03.
Estado: IN_PROGRESS. Autorização: dono instruiu “Pode iniciar”.

## CURRENT -> TARGET / impacto

CURRENT: observer registra resultados de ciclos/duração/falha, porém não lê backlog
durável nem distingue início, parada ou ausência de progresso. Callback de observer
pode lançar exceção depois do commit e quebrar o loop ou classificar trabalho feito
como falha de ciclo.
TARGET: backlog, resultados, falhas, retry/dead-letter e heartbeat/readiness internos
medidos na composição canônica; observabilidade não governa processamento durável.
Escopo T03: mesmas outbox/UOW/loop/router/metrics/logger. Sem fila/endpoint/handler novo,
exporter externo, política de cliente, migration, deploy ou segredo real.

## Implementação e autoridades reutilizadas

- FiscalOutboxStore.counts_by_status: agregado operacional global de cinco estados;
  referência em memória sob lock; SQLite/PostgreSQL usam um GROUP BY/COUNT no banco.
  Sem payload/identidade/limite de paginação e sem escrita ou claim.
- Composição do Worker injeta reader via UOW existente; disponibiliza health() interno.
- MetricsRegistry admite gauges finitos/não negativos e collector process-local;
  callback de coleta só atualiza saúde pelo relógio, nunca consulta DB.
- WorkerObservability: resultados/duração/falhas do ciclo; jobs com retry/dead-letter
  contam falhas de tentativa; gauges da fila/backlog vêm do estado durável.
- Heartbeat usa último ciclo de poll concluído (inclui idle válido). Freshness via
  monotonic, timestamp UTC para diagnóstico; timeout finito/positivo configurável na
  composição, default60s. Antes do primeiro poll e após início/reinício: ready=false.
- Readiness exige último poll válido, snapshot válido, freshness menor que timeout e
  ausência de parada. Falha de ciclo/snapshot/parada invalida; poll novo recupera.
  Coleta recalcula freshness, então worker parado no tempo não mantém gauge ready=1.
- Runtime notifica falha uma vez em run_cycle, preserva exceção original/backoff;
  notifications isoladas e lifecycle start/stop em finally. Logger indisponível e
  snapshot indisponível não desfazem commit nem provocam reentrega por telemetria.

## Contrato de métricas internas

| Métrica | Semântica |
|---|---|
| nfcore_worker_jobs_total{outcome} | Contadores process-local de ciclos concluídos: claimed/succeeded/retry_wait/dead_letter |
| nfcore_worker_job_failures_total | Retry + dead-letter observados em ciclos concluídos; não é erro de DB |
| nfcore_worker_cycle_failures_total{outcome=failed} | Erros de poll/ciclo; observabilidade não conta sucesso como falha |
| nfcore_worker_cycle_count / _seconds_total | Duração/quantidade de ciclos, falha separada pelo outcome |
| nfcore_worker_queue_jobs{outcome} | Gauges duráveis pending/in_flight/retry_wait/succeeded/dead_letter |
| nfcore_worker_backlog_jobs | Pending + retry_wait + in_flight; inclui futuras e leased; não significa somente jobs due |
| nfcore_worker_queue_snapshot_valid | Leitura de fila bem-sucedida;0 após falha; últimos gauges podem estar antigos |
| nfcore_worker_heartbeat_observed / _age_seconds | Existência e idade monotônica do último poll concluído;0/0 antes de observação não afirma heartbeat |
| nfcore_worker_last_success_timestamp_seconds | UTC do último poll,0 antes de início/reinício |
| nfcore_worker_ready / _stopped | Saúde interna do poll recalculada na coleta e lifecycle; não é aprovação externa |
| nfcore_worker_telemetry_failures_total{outcome} | Falha de leitura queue ou emissão log, separada de processamento |

Contadores do processo reiniciam; não são histórico econômico/fiscal. Após falha
parcial de lote, commits anteriores permanecem nos gauges duráveis/auditoria, embora
contadores de ciclo completo não representem aquele lote incompleto. Queries de
telemetria são somente leitura, globais e internas à plataforma; não expor ao tenant
nem compartilhar este registry com a rota HTTP de métricas da API. Exporters,
monitoramento operacional, dashboards/alertas/tracing e tuning de coleta pertencem P9.
Cada ciclo realiza uma consulta agregada; volume/frequência/custo precisam de medição
operacional antes de promoção. Durante falha/staleness, usar ready/validity/age; nunca
interpretar ausência de amostra ou último backlog conhecido como fila atual vazia.

## Matriz reproduzível

32 novos casos: nove cenários SQLite/PostgreSQL (18) e14 casos process-local.
Arquivo: tests/runtime/test_p04_t03_worker_observability.py.

- cinco estados duráveis sem mutação/audit/identidade; backlog125 não truncado;
- resultados success/retry/fatal e gauges compatíveis com banco;
- erro do snapshot após sucesso preserva entrega, invalida saúde e recupera;
- falha do poll invalida/recupera readiness, falha contada uma vez;
- shutdown do loop drena lote e muda saúde, sem claim seguinte;
- logger quebrado não converte sucesso em retry; observer arbitrário quebrado não
  quebra sucesso nem backoff de falha;
- nova composição reconstrói gauges duráveis sem replay e reinicia contadores locais;
- coleta não reconsulta DB; freshness exata no limite do timeout, idle, start/stop;
- timeout/gauge inválidos, labels privados e snapshots malformados rejeitados;
- store de referência em memória conserva semântica dos estados.

Persistência SQLite/PostgreSQL é real; dispatch sintético não prova entrega externa.
Sem teste existente removido/enfraquecido. SIGTERM/processo/container permanece T04.

## Verificação / evidências

Dirigidos45 PASS/21 PostgreSQL SKIP/zero FAIL local (DSN ausente).
Ruff PASS; Mypy strict193 PASS; plan59 PASS; migrations1..16 policy PASS;
secret scan PASS; diff check PASS. Suíte local completa:1386 PASS/251 PostgreSQL
SKIP/zero FAIL em109.83s; um warning TestClient preexistente.
CI PostgreSQL real obrigatória antes de certificar os nove novos casos PostgreSQL.
Dependências locais restauradas em venv temporário; sem mudança de dependências do repo.

## Staging / limites / continuidade

Read-only reconfirmado: API/Portal/PostgreSQL1/1, Worker0/1;
deployments históricos inalterados; drift conhecido P5/P9/P11.
Readiness aqui é saúde do poll configurado, não certifica assinatura/egress/provider,
Secret Manager P6, execução contínua implantada, canal externo ou produção fiscal.
T04 e fases posteriores não iniciadas. PRODUCTION_APPROVED=NO;COMMERCIAL_LIVE=NO.
Próxima ação: gates/CI completos, prova, merge específico, CI main e fechamento.
T03 não concluída antes desse ciclo; não iniciar T04 antecipadamente.
