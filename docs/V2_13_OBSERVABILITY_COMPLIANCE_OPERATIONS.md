# V2-13 — Observabilidade + Compliance Operations

Status: **EM EXECUÇÃO — AUTORIZADA EM 2026-09-13**  
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

1. **Structured Observability Boundary + Sanitization — EM EXECUÇÃO.**
2. **Metrics + Cardinality Governance — PENDENTE.**
3. **Tracing / Correlation / Causation — PENDENTE.**
4. **Operational & Compliance Alerts — PENDENTE.**
5. **Regulatory Watcher Governado — PENDENTE.**
6. **End-to-End Certification + fechamento V2-13 — PENDENTE.**

## Bloco 1 — Structured Observability Boundary + Sanitization

Entregas:

- package/provider-neutral de observabilidade fora do domínio;
- eventos estruturados com severidade, categoria, timestamp e scope fiscal explícito;
- sanitização recursiva e fail-closed de campos proibidos;
- política explícita para referências, hashes e mensagens de erro;
- sink in-memory sintético para testes, sem filesystem/network;
- adapters existentes podem emitir observabilidade sem importar produto consumidor;
- testes negativos de segredo/payload/credential leakage.

Gate: Ruff + Mypy strict + regressão completa e testes novos de sanitização.

## Bloco 2 — Metrics + Cardinality Governance

Entregas:

- métricas por host/tenant/unit/environment/document kind/operation/provider quando aplicável;
- counters/gauges/histograms modelados sem SDK específico;
- whitelist de labels e limites de cardinalidade;
- rejeição de labels proibidas/valores de alta entropia onde inadequado;
- métricas para filas, retries, rejeições, unknown outcomes e contingência;
- nenhum segredo/payload em labels.

Gate: invariantes de cardinalidade e isolamento multi-tenant/multi-host.

## Bloco 3 — Tracing / Correlation / Causation

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

Certificar:

- structured logs sanitizados;
- metrics e cardinalidade;
- tracing/correlation;
- alertas operacionais;
- Regulatory Watcher governado;
- ausência de raw secrets/payloads em toda telemetria;
- fail-open controlado da telemetria sem afetar autoridade fiscal;
- cross-host/cross-tenant/cross-provider isolation;
- restart/replay onde aplicável;
- regressão mestre;
- diff completo V2-12 -> V2-13;
- riscos residuais e documentação final.

## Política de CI

O workflow permanece `workflow_dispatch` por padrão. Em cada gate de bloco:

1. habilitar temporariamente `pull_request`;
2. registrar SHA/run/job e resultado de Install/Ruff/Mypy/Pytest;
3. restaurar imediatamente o arquivo para o blob governado dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`;
4. somente então reconciliar documentação do bloco.

## Governança

A PR da fase deve permanecer Draft. Nenhum merge, deploy, promoção, homologação oficial, segredo real, integração privada de SaaS ou cutover é permitido automaticamente.
