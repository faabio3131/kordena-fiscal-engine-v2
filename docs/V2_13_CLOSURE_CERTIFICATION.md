# V2-13 — CLOSURE CERTIFICATION

Status: **CONCLUÍDA / CERTIFICADA**  
Branch: `v2/observability-compliance-operations`  
PR: `#14` — permanece Draft  
Base V2-12: `1242ce74d874ffb87783401ce1abaabb350c948c`

## Escopo certificado

A V2-13 estabelece e certifica a camada provider-neutral de Observabilidade + Compliance Operations do FM Fiscal Core sem transformar telemetria ou watcher normativo em autoridade fiscal.

Blocos certificados:

1. Structured Observability Boundary + Sanitization;
2. Metrics + Cardinality Governance;
3. Tracing / Correlation / Causation;
4. Operational & Compliance Alerts;
5. Regulatory Watcher Governado;
6. End-to-End Certification + auditoria e fechamento.

## Gates

| Bloco | SHA | Run / Job | Resultado |
|---|---|---|---|
| B1 | `11aa2fa9a63d624235ba90619d853aa3d38e2bb3` | `34763558714` / `103740454991` | 99 source / 518 PASS em 4.52s |
| B2 | `832cdddcc0653ead483ca42a6c93c7966ad9e67f` | `34763739929` / `103740927942` | 100 source / 528 PASS em 5.02s |
| B3 | `f23df8625c78aafa3284c00515376d5174b7892e` | `34763939319` / `103741455008` | 101 source / 537 PASS em 5.46s |
| B4 | `79e83cf34b6b7d6bf71b98036d20cdd0b3364cfd` | `34764162846` / `103742057522` | 102 source / 547 PASS em 4.45s |
| B5 | `9174b461b13d6a8b26c76cfa1a9cc877fbc18895` | `34764440273` / `103742791023` | 103 source / 557 PASS em 4.44s |
| B6 funcional | `0b919fa8fc2bd0203774a0b487e46a94fe6dfda1` | `34765368461` / `103745272017` | Install/Ruff/Mypy PASS; 103 source / 563 PASS em 4.10s |
| Fechamento documental | `94d822aef5c0f6889e67f85bbee6b68c9aac145e` | `34765573097` / `103745807658` | Install/Ruff/Mypy PASS; 103 source / 563 PASS em 7.20s |

## End-to-end certificado

A suíte de fechamento `tests/observability/test_v2_13_closure.py` certifica de forma integrada:

- B1-B4 compartilham o mesmo scope fiscal explícito e sanitizam material sensível;
- payload, credential bytes e material bruto são redigidos nas superfícies de evento/trace;
- hashes e referências explicitamente seguras podem sobreviver à sanitização;
- falhas sintéticas de sinks de eventos, métricas, tracing e alertas são best-effort/fail-open para telemetria e não escapam para alterar semântica fiscal;
- partições de host/tenant/provider permanecem distintas em métricas e deduplicação de alertas;
- trace carrier pode ser reidratado em restart/replay preservando correlation/causation permitidos;
- Regulatory Watcher pode observar, triar, propor e receber aprovação humana, mas a proposta continua `executable == False` e readiness/capability permanece idêntica antes/depois;
- domínio fiscal não depende do package de observabilidade;
- watcher não possui porta de aplicação/promoção para `CapabilityReadinessService` ou `JurisdictionCapabilityMatrix`.

## Auditoria de segredo/payload

A certificação confirma que os contratos tipados centrais de telemetria não possuem campos estruturais para raw payload, secret value, credential bytes, certificate bytes, private key, PFX, XML ou body.

`StructuredObservabilityEvent` e `TraceSpan` aceitam somente attributes sanitizados recursivamente; chaves sensíveis são redigidas e bytes/objetos desconhecidos falham fechado. Métricas usam whitelist de labels, rejeitam labels de alta cardinalidade/sensíveis e impõem `max_series` por definição.

Nenhum segredo real, certificado real, CSC real, credential real ou payload fiscal de cliente foi introduzido nesta fase.

## Auditoria de isolamento

Foram certificados scopes explícitos de host, tenant, unit, environment, document kind, operation e provider. Alertas derivam chave SHA-256 de deduplicação a partir da partição operacional completa e jurisdição/dimensão segura; métricas mantêm séries distintas por partição e não aceitam override de labels-base.

A suíte B6 cobre explicitamente cross-host, cross-tenant e cross-provider sem fallback implícito.

## Regulatory Watcher e soberania humana

`RegulatoryWatcherService` representa evidência normativa, proveniência, jurisdição, assunto, vigência, conflitos, triagem, propostas e decisões humanas.

Regras vinculantes certificadas:

- observação não altera rule matrix;
- proposta exige observações triadas;
- aprovação/rejeição registra reviewer e hash de evidência de testes;
- proposta aprovada continua não executável;
- não existe método `apply` ou `promote` no watcher;
- não há dependência do watcher para a autoridade central de readiness;
- nenhuma promoção normativa automática foi criada.

## Auditoria de diff funcional

Base V2-12 `1242ce74d874ffb87783401ce1abaabb350c948c` -> estado pós-gate funcional/restauração `615a9db4e205cc0ad115552cf7045d6b6ed247a7`:

- 45 commits à frente;
- 0 atrás;
- 17 arquivos líquidos;
- 3.526 adições;
- 51 remoções;
- alterações restritas a documentação/tracker, `compliance.regulatory_watcher`, package `observability` e respectivas suítes de teste;
- nenhum arquivo de `src/kordena_fiscal/domain` foi alterado;
- nenhuma migration nova foi criada;
- `.github/workflows/ci.yml` não aparece no diff líquido porque foi restaurado ao conteúdo original dispatch-only.

## CI e governança

Gate funcional B6: `0b919fa8fc2bd0203774a0b487e46a94fe6dfda1`, run `34765368461`, job `103745272017`: **Install PASS, Ruff PASS, Mypy strict PASS em 103 source files e 563 PASS em 4.10s**.

Após o gate funcional, o CI foi restaurado em `615a9db4e205cc0ad115552cf7045d6b6ed247a7` para o blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.

O fechamento documental recebeu gate final no SHA `94d822aef5c0f6889e67f85bbee6b68c9aac145e`, run `34765573097`, job `103745807658`: **Install PASS, Ruff PASS, Mypy strict PASS em 103 source files e 563 PASS em 7.20s**. Em seguida o CI foi restaurado novamente no commit `1b7861b6f3365bf1eedff4870c7acd3af4bd70b4`, retornando ao mesmo blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.

A PR #14 permanece OPEN / DRAFT / não mergeada.

## Riscos residuais / limites explícitos

- exporters/backends reais de observabilidade e instrumentação produtiva completa não foram ativados; a fase certifica contracts/boundaries provider-neutral e sinks sintéticos;
- o Regulatory Watcher desta fase é workflow governado in-memory; persistência operacional e integrações externas não foram promovidas para produção;
- thresholds/roteamento reais de alertas e tuning de cardinalidade dependem de hardening e dados operacionais posteriores;
- nenhuma homologação oficial externa, deploy, piloto real, produção ou cutover foi executado;
- o warning de transição Node 20 -> Node 24 das GitHub Actions permanece informativo e não afetou Ruff, Mypy ou Pytest.

## Regra de saída

A V2-13 está **CONCLUÍDA / CERTIFICADA**. A V2-14 — Hardening sistêmico permanece **PENDENTE, aguardando autorização humana explícita**.

**SEM MERGE. SEM DEPLOY. SEM PRODUÇÃO REAL. SEM HOMOLOGAÇÃO OFICIAL EXTERNA. SEM CUTOVER. SEM PROMOÇÃO NORMATIVA AUTOMÁTICA.**
