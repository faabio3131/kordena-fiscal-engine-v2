# V2-18.10 — Security + Performance + Disaster Recovery Commercial Gate

## Estado

**CONCLUÍDA / CERTIFICADA INTERNAMENTE.**

Gate final:

- run `34791936752`;
- job `103817664298`;
- Install PASS;
- Ruff PASS;
- Mypy PASS em **126 source files**;
- Bandit Medium/High PASS com a triagem B608 documentada;
- pip-audit PASS — **No known vulnerabilities found** no conjunto de runtime auditado;
- Pytest **741 PASS em 5.43s**.

## Escopo

Este gate não reimplementa hardening já certificado no Core. Ele recompõe a superfície comercial com os controles V2 existentes e adiciona checks comerciais específicos.

## Cobertura herdada da regressão integral

A suíte completa mantém verdes os hardenings de V2-14, incluindo:

- provider timeout e retry bounded;
- circuit breaker open/half-open/recovery;
- unknown authorization outcome sem blind retry;
- vault e signer fail-closed;
- webhook timeout, retry e DLQ;
- storage outage antes de dispatch;
- restart com reclaim de lease sem dispatch paralelo;
- adapter crash sem retry indevido;
- migrations/restart idempotentes;
- archive tamper detection;
- cross-tenant/cross-unit partitioning;
- structural secret scan;
- sequence baseline com 2.048 números únicos/contíguos;
- 5.000 pontos de métrica;
- noisy-neighbor cardinality cap;
- outbox com 200 entradas sem duplicação.

A suíte S2S mantém negativos de:

- cross-host spoofing;
- capability ausente;
- cross-tenant/cross-unit;
- binding ausente;
- rate limiting por caller autenticado;
- webhook tamper/stale/future/rotation/malformed header.

## Hardening comercial adicional

`tests/product/test_commercial_hardening.py` cobre:

- retry bounded do SDK preservando idempotency/correlation;
- esgotamento de retry fail-closed;
- webhook com assinatura incorreta;
- checkpoint/restore de billing sem regressão de usage/status;
- restart determinístico de onboarding;
- runbooks críticos com escalation;
- scan da superfície comercial contra private keys e material produtivo;
- dependências de runtime pequenas e com upper bounds.

## SAST e dependency audit

O CI temporário de certificação executou, além de Ruff/Mypy/Pytest:

- **Bandit** sobre `src/` como SAST Python;
- **pip-audit** sobre o conjunto explícito de dependências de runtime (`cryptography`, `lxml`, `cffi`, `pycparser`).

O primeiro full scan do Bandit, sem `# nosec`, encontrou 0 High, 3 Medium e 14 Low. A análise e classificação completa estão em `docs/V2_18_10_SAST_TRIAGE.md`. Os três Medium B608 foram demonstrados como false positives de SELECTs cujas únicas interpolações são listas de colunas constantes do próprio módulo; todos os valores de runtime continuam ligados por `?` e isso possui regressão estrutural dedicada em `tests/product/test_sast_triage.py`.

O gate final permaneceu bloqueante para qualquer **Medium/High diferente do B608 documentado**. Findings baixos ficaram documentados. Um `assert` de runtime relevante em `application/outbox_worker.py` foi convertido para validação explícita fail-closed.

## Correção de dependência vulnerável

O primeiro `pip-audit` encontrou advisories reais em `cryptography 47.0.0`, incluindo correções disponíveis somente nas linhas 48/49/50. A faixa de runtime foi elevada de:

`cryptography>=44,<48`

para:

`cryptography>=50,<51`

O gate final instalou `cryptography 50.0.1`, reexecutou SAST, dependency audit e toda a regressão, concluindo sem vulnerabilidades conhecidas no conjunto auditado e com 741 testes verdes.

A expectativa histórica de V2-12 foi reconciliada para continuar exigindo um conjunto fechado/explícito de dependências, agora com a faixa segura.

## Limites

Este gate é interno/sintético. Ele não substitui pentest externo, homologação oficial, teste de capacidade sobre infraestrutura produtiva ou disaster recovery em produção. Esses itens continuam dependentes de ambiente/autorização quando aplicáveis.

Este bloco não autoriza deploy, cutover, segredo real ou `PRODUCTION_APPROVED` produtivo.
