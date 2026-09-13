# V2-14 — SYSTEM HARDENING

Status: **EM EXECUÇÃO**  
Branch: `v2/system-hardening`  
Base certificada: `v2/observability-compliance-operations` @ `12d9503f53b59dc7ba24ec205e21ce1ab03c91fb`  
Dependência: V2-13 concluída e certificada.

## Objetivo

Provar segurança, resiliência, consistência e comportamento adversarial do FM Fiscal Core antes de consumidores reais, preservando fail-closed nas superfícies fiscais/segurança e fail-open somente nas superfícies explicitamente best-effort.

## Princípios vinculantes

- nenhuma duplicidade fiscal por retry, concorrência, crash ou replay;
- tenant/host/unit/environment/provider isolation permanecem obrigatórios;
- nenhum segredo real entra em Git, testes, fixtures, logs, métricas, traces ou snapshots;
- telemetria pode falhar aberta apenas por ser best-effort, sem alterar semântica fiscal;
- auth/webhook/secret boundaries permanecem fail-closed;
- não enfraquecer Ruff, Mypy, Pytest ou invariantes existentes;
- performance deve ser medida sem inventar capacidade comercial;
- CI normal permanece `workflow_dispatch`, com `pull_request` temporário somente durante gates;
- nenhuma produção, homologação oficial, merge, deploy ou cutover nesta fase.

## Blocos

1. Failure Injection + Chaos Hardening — EM EXECUÇÃO.
2. Concurrency / Idempotency / Race Conditions — PENDENTE.
3. Security Hardening — PENDENTE.
4. Performance / Load / Backpressure — PENDENTE.
5. Recovery / Durability / Restart — PENDENTE.
6. End-to-End Certification + fechamento — PENDENTE.

## Critério de fechamento

A V2-14 só poderá ser marcada CONCLUÍDA/CERTIFICADA após full regression, gates de todos os blocos, auditoria V2-13 -> V2-14, secret/migration/architecture audit, fechamento documental e restauração do CI para o blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.
