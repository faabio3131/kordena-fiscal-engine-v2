# V2-13 — Observabilidade + Compliance Operations

Status: **EM EXECUÇÃO — BLOCOS 1-3 CERTIFICADOS / BLOCO 4 EM EXECUÇÃO**  
Branch: `v2/observability-compliance-operations`  
Base certificada: `v2/production-adapters` @ `1242ce74d874ffb87783401ce1abaabb350c948c`  
Dependência: V2-12 concluída e certificada.

## Objetivo

Tornar o FM Fiscal operável e auditável em produção futura, com observabilidade estruturada, sanitização, métricas, tracing/correlation, alertas operacionais/compliance e Regulatory Watcher governado, sem transformar observabilidade em nova autoridade fiscal e sem permitir promoção normativa automática.

## Princípios vinculantes

- observabilidade não pode alterar decisão fiscal, readiness ou estado de documento;
- logs, métricas, traces e alertas devem ser sanitizados por construção;
- segredo, certificado, CSC, credential bytes, payload fiscal integral e dado real de cliente não entram em telemetria;
- cardinalidade deve ser controlada; correlation/document references podem aparecer somente em superfícies apropriadas e sanitizadas;
- host/tenant/unit/environment/document kind são dimensões explícitas de operação, nunca inferidas silenciosamente;
- falha da telemetria não pode causar duplicação de emissão, bypass de segurança ou promoção de readiness;
- alertas operacionais apontam risco/condição; não promovem `PRODUCTION_APPROVED`;
- Regulatory Watcher separa fato normativo, evidência, proposta e decisão;
- nenhuma regra normativa entra em vigor automaticamente: revisão, testes e aprovação humana são obrigatórios;
- nenhuma integração SaaS privada, deploy, produção real, homologação oficial ou cutover é autorizada nesta fase.

## Blocos

1. **Structured Observability Boundary + Sanitization — CONCLUÍDO/CERTIFICADO.**
2. **Metrics + Cardinality Governance — CONCLUÍDO/CERTIFICADO.**
3. **Tracing / Correlation / Causation — CONCLUÍDO/CERTIFICADO.**
4. **Operational & Compliance Alerts — EM EXECUÇÃO.**
5. **Regulatory Watcher Governado — PENDENTE.**
6. **End-to-End Certification + fechamento V2-13 — PENDENTE.**

## Bloco 1 — Structured Observability Boundary + Sanitization — CONCLUÍDO/CERTIFICADO

Foi criado `kordena_fiscal.observability` fora do domínio fiscal, com eventos estruturados, contexto fiscal explícito, sanitização recursiva fail-closed, bounded text/collections e sink sintético sem rede/filesystem. Falha do sink é best-effort e não altera execução fiscal.

Primeira tentativa do gate: run `34763491466`, job `103740272028`; Install PASS, Ruff falhou somente por duas ocorrências UP035 de import `Mapping`; Mypy/Pytest ficaram bloqueados.

Gate definitivo B1: SHA `11aa2fa9a63d624235ba90619d853aa3d38e2bb3`, run `34763558714`, job `103740454991`, **99 source files / 518 PASS em 4.52s**. CI restaurado em `e18af325808c53637492680b17219db0deea49cc`.

## Bloco 2 — Metrics + Cardinality Governance — CONCLUÍDO/CERTIFICADO

`MetricDefinition`, `MetricPoint`, `MetricRecorder`, `MetricSink` e `InMemoryMetricSink` modelam counters, gauges e histograms sem SDK específico. Scope fiscal é derivado exclusivamente de `ObservabilityContext`, labels opcionais são whitelist fechada, labels de alta cardinalidade/sensíveis falham fechado e `max_series` limita novas séries sem impedir atualização das existentes.

Catálogo certificado: queue depth, retries, rejeições, unknown provider outcomes, contingência e duração de operação.

Gate definitivo B2: SHA `832cdddcc0653ead483ca42a6c93c7966ad9e67f`, run `34763739929`, job `103740927942`, **100 source files / 528 PASS em 5.02s**. CI restaurado em `bd300c3e92cf344f91d74976ae235c909ba65ced`.

## Bloco 3 — Tracing / Correlation / Causation — CONCLUÍDO/CERTIFICADO

Foi criado `observability.tracing` com `TraceContext`, `TracePropagation`, `TraceSpan`, `TraceRecorder`, `TraceSpanSink` e sink sintético. Trace IDs usam 32 hex, span IDs 16 hex, correlation/causation são referências bounded e carrier possui allowlist fixa de headers.

A cadeia application -> outbox -> provider -> reconciliation preserva `trace_id` e `correlation_id`, com parent spans e causation explícitos. Replay pode reidratar carrier e criar novo child span sem persistir trace como estado fiscal. Attributes reutilizam a sanitização fail-closed do Bloco 1. Correlação do trace deve corresponder ao `ExecutionScope`; mismatch falha fechado. Falha do trace sink é best-effort.

Gate definitivo B3:

- SHA: `f23df8625c78aafa3284c00515376d5174b7892e`;
- run: `34763939319` — **SUCCESS**;
- job: `103741455008`;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **101 source files**;
- Pytest: **537 PASS em 5.46s**;
- baseline B2: 528; incremento líquido: **+9 testes**;
- CI restaurado em `838a20f6b5e597bd8fd6263ff5406ad833c257df`.

## Bloco 4 — Operational & Compliance Alerts — EM EXECUÇÃO

Entregas:

- alertas modelados para certificado próximo de expirar/indisponível;
- fila/backlog/dead-letter;
- taxa de rejeição;
- gap de numeração/sequence;
- contingência prolongada;
- unknown provider outcome pendente de reconciliação;
- severity, deduplication key e scope explícito;
- política para não alertar em loop nem vazar payload.

Gate: cenários sintéticos reproduzíveis e isolamento por scope/provider/jurisdição.

## Bloco 5 — Regulatory Watcher Governado

Entregas: observações normativas com proveniência/evidência, triagem, propostas não executáveis, revisão humana/testes/aprovação e conflitos explícitos. O watcher nunca altera readiness/rules sozinho.

## Bloco 6 — End-to-End Certification + fechamento V2-13

Certificar structured logs, metrics/cardinalidade, tracing/correlation, alertas, Regulatory Watcher, ausência de raw secrets/payloads, fail-open controlado da telemetria, cross-host/cross-tenant/cross-provider isolation, restart/replay, regressão mestre e diff completo V2-12 -> V2-13.

## Política de CI

O workflow permanece `workflow_dispatch` por padrão. Em cada gate de bloco: habilitar temporariamente `pull_request`, registrar SHA/run/job e gates, restaurar o blob dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c` e somente então reconciliar documentação.

## Governança

A PR #14 permanece Draft. Nenhum merge, deploy, promoção, homologação oficial, segredo real, integração privada de SaaS ou cutover é permitido automaticamente.
