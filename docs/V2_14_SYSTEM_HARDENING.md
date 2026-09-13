# V2-14 — SYSTEM HARDENING

Status: **EM EXECUÇÃO — B1-B3 CERTIFICADOS / B4 EM EXECUÇÃO**  
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
4. **Performance / Load / Backpressure — EM EXECUÇÃO.**
5. Recovery / Durability / Restart — PENDENTE.
6. End-to-End Certification + fechamento — PENDENTE.

## B1 — Failure Injection + Chaos Hardening

A suíte `tests/hardening/test_failure_injection.py` cobre timeout/retry, provider intermitente, circuit breaker, unknown outcome, Vault/signer indisponíveis, telemetria best-effort, webhook timeout/dead-letter, storage outage, restart/replay e exceção inesperada de adapter.

Gate B1: `6ae140bbc9c6d8d9ddca978591d2e110b9b82c4d` / run `34766801662` / job `103749098152` — **103 source / 574 PASS em 4.83s**. CI restaurado em `b477b53a041726700cc6746718d3b4e7b34fb2c5`.

## B2 — Concurrency / Idempotency / Race Conditions

A auditoria constatou invariantes concorrentes já implementadas/certificadas: 64 begins idempotentes concorrentes geram uma reserva, 128 números fiscais são únicos/contíguos, leasing do outbox impede double-dispatch, stale workers são barrados por attempt-version fencing e partições são isoladas por host/tenant/unit/environment/document kind.

Gate B2: `a01f668fb9ae4027cb040dc9f621c85c69b4df38` / run `34766907909` / job `103749380939` — **103 source / 574 PASS em 5.62s**. CI restaurado em `b0f61e83934e6796c0baa82ae0069c5f9fb09d1f`.

## B3 — Security Hardening

A auditoria certificou, sob regressão integral, as proteções existentes sem necessidade de alterar produção:

- workload credentials são hash-only, com rotação/revogação/validade e fail-closed;
- S2S rejeita cross-host, cross-tenant, cross-unit, capability ausente e binding inexistente;
- webhook usa HMAC-SHA256, rejeita body adulterado, assinatura stale/future e headers malformados;
- URLs de webhook exigem HTTPS e rejeitam credenciais/fragmentos;
- XML usa parser `resolve_entities=False`, `load_dtd=False`, `no_network=True`, `huge_tree=False` e bloqueia `DOCTYPE`;
- XSD resources usam path relativo seguro e SHA-256 pinning;
- Vault/signing/telemetria mantêm secret material fora de repr/persistência e sanitizam campos sensíveis;
- partições provider/tenant/unit/environment permanecem fail-closed.

Gate B3: `eae4863ace3ac738375a272ba892f7508eba78ba` / run `34766999896` / job `103749636115` — **Install PASS, Ruff PASS, Mypy strict PASS em 103 source files e 574 PASS em 4.48s**. CI restaurado em `98a76c70e1b6a816eac7b2df91c4c44e99c56e3d`.

## B4 — Performance / Load / Backpressure

Em execução. `tests/hardening/test_load_baseline.py` define workloads reproduzíveis sem converter medições de CI em promessa comercial: 2.048 reservas de sequência, 5.000 pontos em uma única série governada, 128 partições concorrendo por cap de 32 séries e drenagem durável de 200 entradas de outbox em lotes de 50 sem duplicação.

## Critério de fechamento

A V2-14 só poderá ser marcada CONCLUÍDA/CERTIFICADA após full regression, gates de todos os blocos, auditoria V2-13 -> V2-14, secret/migration/architecture audit, fechamento documental e restauração do CI para o blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.
