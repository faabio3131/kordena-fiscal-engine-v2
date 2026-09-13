# V2-14 — CLOSURE CERTIFICATION

Status: **CONCLUÍDA / CERTIFICADA**  
Branch: `v2/system-hardening`  
PR: `#15` — permanece Draft  
Base V2-13: `12d9503f53b59dc7ba24ec205e21ce1ab03c91fb`

## Escopo certificado

A V2-14 endurece o FM Fiscal Core contra falhas, concorrência, abuso de superfícies de segurança, pressão de carga e cenários de crash/restart sem alterar as regras fiscais universais.

Blocos certificados:

1. Failure Injection + Chaos Hardening;
2. Concurrency / Idempotency / Race Conditions;
3. Security Hardening;
4. Performance / Load / Backpressure;
5. Recovery / Durability / Restart;
6. End-to-End Certification + auditoria e fechamento.

## Gates

| Bloco | SHA | Run / Job | Resultado |
|---|---|---|---|
| B1 | `6ae140bbc9c6d8d9ddca978591d2e110b9b82c4d` | `34766801662` / `103749098152` | 103 source / 574 PASS em 4.83s |
| B2 | `a01f668fb9ae4027cb040dc9f621c85c69b4df38` | `34766907909` / `103749380939` | 103 source / 574 PASS em 5.62s |
| B3 | `eae4863ace3ac738375a272ba892f7508eba78ba` | `34766999896` / `103749636115` | 103 source / 574 PASS em 4.48s |
| B4 | `64279702a2b48639e7a293ae187dc5819ca48329` | `34767103876` / `103749915646` | 103 source / 578 PASS em 4.47s |
| B5 | `0bcb8997d7a917cc59c910448a24b1a6d7d67abc` | `34767187658` / `103750146391` | 103 source / 578 PASS em 6.81s |
| B6 funcional | `004190e102f88f613f83607b477f2abf99be7818` | `34767340977` / `103750554549` | Install/Ruff/Mypy PASS; 103 source / 582 PASS em 5.79s |
| Fechamento documental | `dac957f45a1a37054b89bc3bc8829fd311ebd8db` | `34767492053` / `103750960133` | Install/Ruff/Mypy PASS; 103 source / 582 PASS em 6.41s |

## Certificações

Failure injection cobre provider timeout/intermitência, retry budget, circuit breaker, unknown authorization outcome sem retry, indisponibilidade de Vault/signer, falha de telemetria best-effort, timeout de webhook com dead-letter, storage outage, replay de lease após restart e exceção inesperada de adapter sem retry cego.

Concorrência prova idempotência semântica sob disputa, numeração fiscal única/contígua, outbox leasing sem double-dispatch, stale-worker fencing e isolamento de partições.

Security hardening revalida workload auth hash-only/rotação/revogação, S2S cross-scope fail-closed, HMAC webhooks, destinos HTTPS-only, XML no-network/sem DTD/entity resolution/huge-tree, XSD path-safe/hash-pinned e secret material fora de persistência/telemetria.

Load/backpressure usa workloads reproduzíveis de CI: 2.048 reservas fiscais, 5.000 pontos em uma série, 128 tenants contra cap de 32 séries e 200 itens de outbox em lotes de 50. Esses números não são SLA nem promessa comercial.

Recovery/durability cobre migrations idempotentes, rollback, restart, crash recovery de issuance, lease recovery, inbox replay, reconciliation durável, archive append-only e SHA-256/manifest chain.

`tests/hardening/test_v2_14_closure.py` fecha migrations/restart, archive tamper fail-closed, identidade distinta de partições e structural secret/domain-boundary scan.

## Auditoria de diff

V2-13 `12d9503f53b59dc7ba24ec205e21ce1ab03c91fb` -> pós-gate funcional/restauração `321f1a64354969e65705f4ac7863583e66855598`:

- **24 commits à frente, 0 atrás**;
- **6 arquivos líquidos**;
- nenhuma alteração em código de produção;
- nenhuma migration nova;
- nenhuma dependência produtiva nova;
- CI sem diff líquido após restauração.

## CI e governança

Após o gate B6 funcional o CI foi restaurado em `321f1a64354969e65705f4ac7863583e66855598`. Após o gate documental final, foi restaurado novamente em `139c761ae9116653a66bf95eec2afdfe3b0504f0` para o blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.

A PR #15 permanece OPEN / DRAFT / não mergeada. V2-15 está autorizada a iniciar sobre o HEAD documental final desta fase. Nenhum merge, deploy, produção real, homologação oficial externa ou cutover foi executado.

**V2-14 — CONCLUÍDA / CERTIFICADA.**
