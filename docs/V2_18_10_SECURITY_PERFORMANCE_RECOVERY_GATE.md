# V2-18.10 — Security + Performance + Disaster Recovery Commercial Gate

## Estado

**IMPLEMENTADA — AGUARDANDO GATE FINAL DO BLOCO.**

## Escopo

Este gate não reimplementa hardening já certificado no Core. Ele recompõe a superfície comercial com os controles V2 existentes e adiciona checks comerciais específicos.

## Cobertura herdada da regressão integral

A suíte completa já executa e mantém verdes os hardenings de V2-14, incluindo:

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

A suíte S2S também mantém negativos de:

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

O CI temporário de certificação da V2-18.10 foi elevado para executar, além de Ruff/Mypy/Pytest:

- **Bandit** sobre `src/` como SAST Python;
- **pip-audit** sobre o conjunto explícito de dependências de runtime (`cryptography`, `lxml`, `cffi`, `pycparser`).

Essas ferramentas são instaladas somente no runner do gate temporário. Elas não entram como dependência de runtime do produto e o workflow auxiliar será neutralizado após o fechamento da V2-18.

## Classificação

Um achado real de Bandit, pip-audit, Ruff, Mypy ou Pytest é vermelho e deve ser corrigido antes do avanço. Nenhum finding pode ser suprimido apenas para obter verde.

## Limites

Este gate é interno/sintético. Ele não substitui pentest externo, homologação oficial, teste de capacidade sobre infraestrutura produtiva ou disaster recovery em produção. Esses itens continuam dependentes de ambiente/autorização quando aplicáveis.
