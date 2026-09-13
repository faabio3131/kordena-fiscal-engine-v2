# V2-14 — SYSTEM HARDENING

Status: **EM EXECUÇÃO — B1-B5 CERTIFICADOS / B6 EM EXECUÇÃO**  
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
3. **Security Hardening — CONCLUÍDO/CERTIFICADO.**
4. **Performance / Load / Backpressure — CONCLUÍDO/CERTIFICADO.**
5. **Recovery / Durability / Restart — CONCLUÍDO/CERTIFICADO.**
6. **End-to-End Certification + fechamento — EM EXECUÇÃO.**

## B1 — Failure Injection + Chaos Hardening

`tests/hardening/test_failure_injection.py` cobre timeout/retry, provider intermitente, circuit breaker, unknown outcome, Vault/signer indisponíveis, telemetria best-effort, webhook timeout/dead-letter, storage outage, restart/replay e exceção inesperada de adapter.

Gate B1: `6ae140bbc9c6d8d9ddca978591d2e110b9b82c4d` / run `34766801662` / job `103749098152` — **103 source / 574 PASS em 4.83s**. CI restaurado em `b477b53a041726700cc6746718d3b4e7b34fb2c5`.

## B2 — Concurrency / Idempotency / Race Conditions

A auditoria certificou as invariantes concorrentes já existentes: 64 begins idempotentes concorrentes -> uma reserva; 128 números fiscais únicos/contíguos; leasing do outbox sem double-dispatch; stale-worker fencing por attempt version; transaction boundary inbox/outbox; isolamento por host/tenant/unit/environment/document kind.

Gate B2: `a01f668fb9ae4027cb040dc9f621c85c69b4df38` / run `34766907909` / job `103749380939` — **103 source / 574 PASS em 5.62s**. CI restaurado em `b0f61e83934e6796c0baa82ae0069c5f9fb09d1f`.

## B3 — Security Hardening

A regressão integral certificou workload auth hash-only/rotação/revogação, S2S fail-closed cross-scope, webhook HMAC/replay bounds, HTTPS-only destinations, XML no-network/DTD/entities disabled, XSD path-safe/hash-pinned, secret boundaries e sanitização de telemetria.

Gate B3: `eae4863ace3ac738375a272ba892f7508eba78ba` / run `34766999896` / job `103749636115` — **103 source / 574 PASS em 4.48s**. CI restaurado em `98a76c70e1b6a816eac7b2df91c4c44e99c56e3d`.

## B4 — Performance / Load / Backpressure

`tests/hardening/test_load_baseline.py` define workloads reproduzíveis sem converter CI em promessa comercial: 2.048 reservas fiscais únicas/contíguas; 5.000 pontos na mesma série de métrica; 128 tenants disputando limite de 32 séries; 200 entradas duráveis de outbox drenadas em lotes de 50 sem duplicação.

Gate B4: `64279702a2b48639e7a293ae187dc5819ca48329` / run `34767103876` / job `103749915646` — **103 source / 578 PASS em 4.47s**. CI restaurado em `76e0db78609ada734511752c7af11d2a4debfe82`.

## B5 — Recovery / Durability / Restart

A regressão certificou migrations idempotentes, restart do authority state, rollback do UoW, crash recovery de issuance sem duplicação, lease recovery de outbox, inbox replay, reconciliation durável, archive append-only e verificação SHA-256/manifest chain.

Gate B5: `0bcb8997d7a917cc59c910448a24b1a6d7d67abc` / run `34767187658` / job `103750146391` — **Install PASS, Ruff PASS, Mypy strict PASS em 103 source files e 578 PASS em 6.81s**. CI restaurado em `a6e76ea98852a546ffe5c5f31ed81f47c453ebd0`.

## B6 — End-to-End Certification + fechamento

`tests/hardening/test_v2_14_closure.py` adiciona o fechamento estrutural da fase: migrations/restart idempotentes, detecção fail-closed de tampering no archive, identidade distinta de partições multi-tenant/unit, structural secret scan e garantia de que o domínio universal não importa boundaries/adapters de infraestrutura.

O gate B6 deve executar regressão integral, auditoria V2-13 -> V2-14, dependency/migration/secret/architecture audit e fechamento documental antes da fase ser declarada concluída.

## Critério de fechamento

A V2-14 só poderá ser marcada CONCLUÍDA/CERTIFICADA após full regression, gate B6, auditoria V2-13 -> V2-14, secret/migration/architecture audit, fechamento documental e restauração do CI para o blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.
