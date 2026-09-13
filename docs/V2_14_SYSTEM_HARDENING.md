# V2-14 — SYSTEM HARDENING

Status: **EM EXECUÇÃO — B1-B2 CERTIFICADOS / B3 EM EXECUÇÃO**  
Branch: `v2/system-hardening`  
PR: `#15` — Draft  
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

1. **Failure Injection + Chaos Hardening — CONCLUÍDO/CERTIFICADO.**
2. **Concurrency / Idempotency / Race Conditions — CONCLUÍDO/CERTIFICADO.**
3. **Security Hardening — EM EXECUÇÃO.**
4. Performance / Load / Backpressure — PENDENTE.
5. Recovery / Durability / Restart — PENDENTE.
6. End-to-End Certification + fechamento — PENDENTE.

## B1 — Failure Injection + Chaos Hardening

A suíte `tests/hardening/test_failure_injection.py` cobre timeout/retry, provider intermitente, circuit breaker, unknown outcome, Vault/signer indisponíveis, telemetria best-effort, webhook timeout/dead-letter, storage outage, restart/replay e exceção inesperada de adapter.

Gate B1: `6ae140bbc9c6d8d9ddca978591d2e110b9b82c4d` / run `34766801662` / job `103749098152` — **103 source / 574 PASS em 4.83s**. CI restaurado em `b477b53a041726700cc6746718d3b4e7b34fb2c5`.

## B2 — Concurrency / Idempotency / Race Conditions

A auditoria constatou que as invariantes exigidas já estavam implementadas em testes certificados do Core, evitando duplicação artificial de suíte:

- `test_concurrent_begin_creates_exactly_one_new_reservation`: 64 begins concorrentes -> 1 reserva + 63 replays;
- `test_128_concurrent_reservations_are_unique_and_contiguous`: sequência fiscal concorrente única/contígua;
- `test_two_durable_workers_do_not_dispatch_same_live_lease`: leasing do outbox impede despacho duplicado;
- `test_stale_worker_cannot_finalize_after_lease_reclaim`: attempt version funciona como fencing token;
- inbox/outbox compartilham transaction boundary e eventos iguais são isolados por host;
- idempotency/sequence são particionados por tenant/unit/environment/document kind.

Nenhum gap funcional exigiu alteração de produção neste bloco. A regressão completa certificou conjuntamente essas invariantes.

Gate B2: `a01f668fb9ae4027cb040dc9f621c85c69b4df38` / run `34766907909` / job `103749380939` — **Install PASS, Ruff PASS, Mypy strict PASS em 103 source files e 574 PASS em 5.62s**. CI restaurado em `b0f61e83934e6796c0baa82ae0069c5f9fb09d1f`.

## B3 — Security Hardening

Em execução: isolamento multi-scope/provider, S2S/workload identity, webhook signature/replay, secret boundaries, sanitização, malformed/oversized input, XML safety, serialization/persistence e structural secret scan.

## Critério de fechamento

A V2-14 só poderá ser marcada CONCLUÍDA/CERTIFICADA após full regression, gates de todos os blocos, auditoria V2-13 -> V2-14, secret/migration/architecture audit, fechamento documental e restauração do CI para o blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.
