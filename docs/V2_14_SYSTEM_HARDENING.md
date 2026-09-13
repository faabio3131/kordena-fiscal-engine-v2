# V2-14 — SYSTEM HARDENING

Status: **EM EXECUÇÃO — B1 CERTIFICADO / B2 EM EXECUÇÃO**  
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
2. **Concurrency / Idempotency / Race Conditions — EM EXECUÇÃO.**
3. Security Hardening — PENDENTE.
4. Performance / Load / Backpressure — PENDENTE.
5. Recovery / Durability / Restart — PENDENTE.
6. End-to-End Certification + fechamento — PENDENTE.

## B1 — Failure Injection + Chaos Hardening

A suíte `tests/hardening/test_failure_injection.py` adicionou cenários adversariais sobre contracts já certificados:

- timeout/provider indisponível com retry limitado;
- provider intermitente com recuperação sem chamada extra;
- circuit breaker OPEN -> HALF_OPEN -> CLOSED;
- autorização com outcome desconhecido sem retry automático e com reconciliação obrigatória;
- Vault indisponível e signer indisponível em fail-closed;
- telemetria indisponível em fail-open best-effort;
- webhook transport timeout com retry durável e dead-letter;
- storage indisponível antes do claim/dispatch;
- replay após lease expirada/restart sem despacho paralelo;
- exceção inesperada de adapter classificada como permanente, sem retry cego.

Gate B1: `6ae140bbc9c6d8d9ddca978591d2e110b9b82c4d` / run `34766801662` / job `103749098152` — **Install PASS, Ruff PASS, Mypy strict PASS em 103 source files e 574 PASS em 4.83s**. Baseline V2-13: 563; incremento líquido: +11 testes. CI restaurado em `b477b53a041726700cc6746718d3b4e7b34fb2c5` para o blob dispatch-only governado.

## B2 — Concurrency / Idempotency / Race Conditions

Em certificação. O baseline já contém provas concorrentes explícitas para idempotência semântica, sequência fiscal contígua, leasing/stale-worker fencing no outbox e isolamento de partições. O gate B2 deve certificar conjuntamente essas invariantes sob a regressão completa e documentar qualquer gap real antes de avançar.

## Critério de fechamento

A V2-14 só poderá ser marcada CONCLUÍDA/CERTIFICADA após full regression, gates de todos os blocos, auditoria V2-13 -> V2-14, secret/migration/architecture audit, fechamento documental e restauração do CI para o blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.
