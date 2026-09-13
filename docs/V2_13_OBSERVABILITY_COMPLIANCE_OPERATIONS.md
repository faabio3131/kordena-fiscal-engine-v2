# V2-13 — Observabilidade + Compliance Operations

Status: **EM EXECUÇÃO — BLOCOS 1-5 CERTIFICADOS / BLOCO 6 EM EXECUÇÃO**  
Branch: `v2/observability-compliance-operations`  
Base certificada: `v2/production-adapters` @ `1242ce74d874ffb87783401ce1abaabb350c948c`  
Dependência: V2-12 concluída e certificada.

## Objetivo

Tornar o FM Fiscal operável e auditável em produção futura, com observabilidade estruturada, sanitização, métricas, tracing/correlation, alertas operacionais/compliance e Regulatory Watcher governado, sem transformar observabilidade em nova autoridade fiscal e sem permitir promoção normativa automática.

## Princípios vinculantes

- observabilidade não pode alterar decisão fiscal, readiness ou estado de documento;
- logs, métricas, traces e alertas devem ser sanitizados por construção;
- segredo, certificado, CSC, credential bytes, payload fiscal integral e dado real de cliente não entram em telemetria;
- cardinalidade deve ser controlada;
- host/tenant/unit/environment/document kind são dimensões explícitas de operação;
- falha da telemetria não pode causar duplicação de emissão, bypass de segurança ou promoção de readiness;
- alertas operacionais não promovem `PRODUCTION_APPROVED`;
- Regulatory Watcher separa fato normativo, evidência, proposta e decisão;
- nenhuma regra normativa entra em vigor automaticamente: revisão, testes e aprovação humana são obrigatórios;
- nenhuma integração SaaS privada, deploy, produção real, homologação oficial ou cutover é autorizada nesta fase.

## Blocos

1. **Structured Observability Boundary + Sanitization — CONCLUÍDO/CERTIFICADO.**
2. **Metrics + Cardinality Governance — CONCLUÍDO/CERTIFICADO.**
3. **Tracing / Correlation / Causation — CONCLUÍDO/CERTIFICADO.**
4. **Operational & Compliance Alerts — CONCLUÍDO/CERTIFICADO.**
5. **Regulatory Watcher Governado — CONCLUÍDO/CERTIFICADO.**
6. **End-to-End Certification + fechamento V2-13 — EM EXECUÇÃO.**

## Bloco 1 — Structured Observability Boundary + Sanitization — CONCLUÍDO/CERTIFICADO

Boundary provider-neutral fora do domínio fiscal com eventos estruturados, sanitização recursiva fail-closed, bounded text/collections e sink sintético best-effort.

Gate B1: `11aa2fa9a63d624235ba90619d853aa3d38e2bb3` / run `34763558714` / job `103740454991` / **99 source / 518 PASS em 4.52s**. CI restaurado em `e18af325808c53637492680b17219db0deea49cc`.

## Bloco 2 — Metrics + Cardinality Governance — CONCLUÍDO/CERTIFICADO

Counters/gauges/histograms sem SDK específico; scope fiscal derivado de `ObservabilityContext`; labels opcionais por whitelist; `max_series` limita cardinalidade; labels sensíveis/alta cardinalidade falham fechado.

Gate B2: `832cdddcc0653ead483ca42a6c93c7966ad9e67f` / run `34763739929` / job `103740927942` / **100 source / 528 PASS em 5.02s**. CI restaurado em `bd300c3e92cf344f91d74976ae235c909ba65ced`.

## Bloco 3 — Tracing / Correlation / Causation — CONCLUÍDO/CERTIFICADO

`TraceContext`, carrier com allowlist fixa, cadeia parent/child, correlation/causation explícitos, replay por reidratação e attributes sanitizados. Trace correlation deve corresponder ao scope fiscal. Falha do sink é best-effort.

Gate B3: `f23df8625c78aafa3284c00515376d5174b7892e` / run `34763939319` / job `103741455008` / **101 source / 537 PASS em 5.46s**. CI restaurado em `838a20f6b5e597bd8fd6263ff5406ad833c257df`.

## Bloco 4 — Operational & Compliance Alerts — CONCLUÍDO/CERTIFICADO

Foi criado `observability.alerts` com alertas tipados e sanitizados para certificado próximo de expirar/indisponível, fila/backlog/dead-letter, taxa de rejeição, gap de numeração, contingência prolongada e unknown provider outcome.

`AlertRegistry` calcula chave SHA-256 de deduplicação a partir de kind + host + tenant + unit + environment + document kind + operation + provider + jurisdiction + dimensão segura. Alertas ativos não entram em loop; após `resolve()` podem ser emitidos novamente. Falha do sink não marca alerta como ativo.

`OperationalAlertEvaluator` só produz sinais operacionais/compliance; não altera documento, readiness ou regra fiscal. Attributes passam pela sanitização fail-closed do B1 e referências explicitamente seguras podem ser preservadas.

Primeira tentativa B4: run `34764107470`, job `103741903144`; Install PASS, Ruff falhou apenas por import não usado `MappingProxyType`; Mypy/Pytest bloqueados. Import removido sem alteração semântica.

Gate definitivo B4:

- SHA: `79e83cf34b6b7d6bf71b98036d20cdd0b3364cfd`;
- run: `34764162846` — **SUCCESS**;
- job: `103742057522`;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **102 source files**;
- Pytest: **547 PASS em 4.45s**;
- baseline B3: 537; incremento líquido: **+10 testes**;
- CI restaurado em `dba2173c4ba0c23d5791b96ae6e381333d63a2b2`.

## Bloco 5 — Regulatory Watcher Governado — CONCLUÍDO/CERTIFICADO

Foi criado `compliance.regulatory_watcher` com observações normativas imutáveis, fonte/proveniência, jurisdição, assunto, vigência, hash de evidência, conflitos explícitos e estados separados de observação, triagem, proposta e decisão.

A comparação com capability/rule vigente é somente leitura. `RegulatoryChangeProposal` é explicitamente não executável e aprovação exige revisão humana identificada e evidência de testes. Mesmo aprovada, a proposta não altera `CapabilityReadinessService`, `JurisdictionCapabilityMatrix`, readiness, rule matrix ou qualquer adapter de produção.

O fluxo representa contradições entre fontes em vez de ocultá-las e rejeita transições inválidas, impedindo promoção normativa autônoma.

Gate definitivo B5:

- SHA: `9174b461b13d6a8b26c76cfa1a9cc877fbc18895`;
- run: `34764440273` — **SUCCESS**;
- job: `103742791023`;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **103 source files**;
- Pytest: **557 PASS em 4.44s**;
- baseline B4: 547; incremento líquido: **+10 testes**;
- CI restaurado para dispatch-only em `2c113de637277732a695e18a3ab5ffd4d0e92773`.

## Bloco 6 — End-to-End Certification + fechamento V2-13 — EM EXECUÇÃO

Certificar structured logs, metrics/cardinalidade, tracing/correlation, alertas, Regulatory Watcher, ausência de raw secrets/payloads, fail-open controlado da telemetria, isolamento cross-host/cross-tenant/cross-provider, restart/replay, regressão mestre e diff completo V2-12 -> V2-13.

## Política de CI

O workflow permanece `workflow_dispatch` por padrão. Em cada gate de bloco: habilitar temporariamente `pull_request`, registrar SHA/run/job e gates, restaurar o blob dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c` e somente então reconciliar documentação.

## Governança

A PR #14 permanece Draft. Nenhum merge, deploy, promoção, homologação oficial, segredo real, integração privada de SaaS ou cutover é permitido automaticamente.
