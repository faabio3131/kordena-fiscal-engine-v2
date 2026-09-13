# V2-13 — Observabilidade + Compliance Operations

Status: **EM EXECUÇÃO — BLOCOS 1-2 CERTIFICADOS / BLOCO 3 EM EXECUÇÃO**  
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
3. **Tracing / Correlation / Causation — EM EXECUÇÃO.**
4. **Operational & Compliance Alerts — PENDENTE.**
5. **Regulatory Watcher Governado — PENDENTE.**
6. **End-to-End Certification + fechamento V2-13 — PENDENTE.**

## Bloco 1 — Structured Observability Boundary + Sanitization — CONCLUÍDO/CERTIFICADO

Foi criado `kordena_fiscal.observability` fora do domínio fiscal, com `ObservabilityContext`, `StructuredObservabilityEvent`, `StructuredObservabilityService`, `StructuredEventSink` e sink sintético in-memory sem rede/filesystem.

A sanitização é recursiva e fail-closed: bytes e objetos desconhecidos são redigidos sem `repr`; chaves sensíveis como password/token/credential/CSC/PFX/payload/XML/body/signature/certificate são redigidas por padrão; apenas referências, hashes e fingerprints explicitamente seguros sobrevivem. Mensagens contendo Bearer/Basic auth, material PEM/XML ou padrões de segredo são redigidas. Texto e coleções são bounded.

`StructuredObservabilityService.emit()` é best-effort: falha do sink retorna `False` e não escapa para a execução fiscal. O domínio permanece sem dependência de observabilidade.

Primeira tentativa do gate: run `34763491466`, job `103740272028`; Install PASS, Ruff falhou somente por duas ocorrências UP035 de import `Mapping` em `typing`; Mypy/Pytest ficaram bloqueados. Correção aplicada sem alterar semântica.

Gate definitivo B1: SHA `11aa2fa9a63d624235ba90619d853aa3d38e2bb3`, run `34763558714`, job `103740454991`, **Install PASS / Ruff PASS / Mypy strict PASS — 99 source files / 518 PASS em 4.52s**. Baseline V2-12: 508; incremento líquido +10. CI restaurado em `e18af325808c53637492680b17219db0deea49cc`.

## Bloco 2 — Metrics + Cardinality Governance — CONCLUÍDO/CERTIFICADO

Foi criado `observability.metrics`, provider-neutral e sem SDK específico. `MetricDefinition`, `MetricPoint`, `MetricRecorder`, `MetricSink` e `InMemoryMetricSink` modelam counters, gauges e histograms com labels governadas.

As dimensões base são derivadas exclusivamente de `ObservabilityContext`: host, tenant, unidade, ambiente e, quando presentes, document kind, operação e provider. Labels opcionais são whitelist fechada (`queue`, `reason_code`, `status`, `contingency_mode`) e não podem sobrescrever o scope. Labels de alta cardinalidade ou sensíveis — correlation/document ids, references arbitrárias, payload, secret, token, credential, password, message/XML/body — falham fechado.

Cada métrica tem `max_series` explícito; novas séries além do limite são recusadas sem impedir atualização de série já conhecida. Falha do sink é best-effort e não registra série fantasma. O catálogo cobre queue depth, retries, rejeições, unknown provider outcomes, contingência e duração de operação.

Gate definitivo B2:

- SHA: `832cdddcc0653ead483ca42a6c93c7966ad9e67f`;
- run: `34763739929` — **SUCCESS**;
- job: `103740927942`;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **100 source files**;
- Pytest: **528 PASS em 5.02s**;
- baseline B1: 518; incremento líquido: **+10 testes**;
- CI restaurado para `workflow_dispatch` no commit `bd300c3e92cf344f91d74976ae235c909ba65ced`.

## Bloco 3 — Tracing / Correlation / Causation — EM EXECUÇÃO

Entregas:

- propagation contract para correlation/causation/trace ids;
- spans sintéticos provider-neutral;
- continuidade de trace entre application/outbox/provider/reconciliation;
- scope fiscal explícito no trace context;
- sanitização e limites de tamanho;
- telemetria opcional não altera semantics de execução.

Gate: replay/restart preserva referências operacionais permitidas sem transformar trace em estado fiscal.

## Bloco 4 — Operational & Compliance Alerts

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

Entregas:

- `RegulatoryObservation` com fonte/proveniência, jurisdição, assunto, effective dates e hash de evidência;
- estados separados para observado, triado, proposta de mudança, aprovado/rejeitado;
- comparação com capability/rule version vigente sem mutação automática;
- `RegulatoryChangeProposal` explicitamente não executável;
- promoção normativa exige revisão humana + testes + aprovação registrada;
- conflito/contradição de fontes é representado, não ocultado.

Gate: watcher nunca altera `CapabilityReadinessService` nem rule matrix sozinho.

## Bloco 6 — End-to-End Certification + fechamento V2-13

Certificar structured logs, metrics/cardinalidade, tracing/correlation, alertas, Regulatory Watcher, ausência de raw secrets/payloads, fail-open controlado da telemetria, cross-host/cross-tenant/cross-provider isolation, restart/replay, regressão mestre e diff completo V2-12 -> V2-13.

## Política de CI

O workflow permanece `workflow_dispatch` por padrão. Em cada gate de bloco: habilitar temporariamente `pull_request`, registrar SHA/run/job e gates, restaurar o blob dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c` e somente então reconciliar documentação.

## Governança

A PR #14 permanece Draft. Nenhum merge, deploy, promoção, homologação oficial, segredo real, integração privada de SaaS ou cutover é permitido automaticamente.
