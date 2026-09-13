# V2-17 — Convergência e Cutover — Execução Governada

Data de início: 2026-09-13  
Branch: `v2/convergence-cutover`  
Base: V2-16 `v2/fm-products-integration@6998d5a4b7370621160e2520bbadabafca86bda0`

## Escopo desta autorização

A V2-17 foi iniciada apenas como preparação e certificação interna de convergência. **Cutover real, produção, migração produtiva e arquivamento/desativação do motor legado permanecem proibidos.**

## Referência correta do motor legado

O repositório `faabio3131/kordena-fiscal-engine` tem `main` em um commit inicial/placeholder (`b050d4540227ea1ab6dd7b367284daca2ed9a7ac`). Esse ref NÃO é o baseline fiscal a ser usado em convergência.

O baseline fiscal público FISC-00..FISC-19 certificado está preservado em:

- branch `feat/fisc-19-rtc-multiuf-hardening`;
- SHA `b336def47ad4f5188307102203f4e04b98406014`.

Esse SHA foi a origem certificada usada pela V2-00 e é a referência histórica correta para equivalência/migração. Git, por si só, não prova qual runtime está implantado em produção; nenhuma autoridade operacional produtiva é inferida daqui.

## V2-17.1 — Convergence Readiness + Single Fiscal Authority

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE — CUTOVER REAL CONTINUA BLOQUEADO.**

### Matriz de pré-condições no checkpoint V2-17.1

| Requisito | Estado | Evidência / motivo |
|---|---|---|
| Equivalência funcional | `READY_INTERNAL` | V2-00 + regressões cumulativas |
| Multiproduto certificado | `READY_INTERNAL` | V2-16.7 cross-product closure |
| Kordena operando no V2 | `BLOCKED_PRODUCT` | PR #118 funcionalmente PARCIAL; FISC-20 não liberado |
| Regressão fiscal completa | `READY_INTERNAL` | V2-16.7 verde |
| Migração estado/documentos definida | `BLOCKED_PRODUCT` no checkpoint B17.1 | escopo da V2-17.2 |
| Migração testada | `BLOCKED_PRODUCT` no checkpoint B17.1 | escopo da V2-17.2 |
| Rollback documentado | `BLOCKED_PRODUCT` no checkpoint B17.1 | escopo da V2-17.2 |
| Evidência operacional externa oficial | `BLOCKED_EXTERNAL` | V2-15 mantém homologações oficiais pendentes |
| Aprovação humana de cutover | `HUMAN_APPROVAL_REQUIRED` | autorização atual proíbe cutover real |

`kordena_fiscal.convergence.readiness` materializa essa matriz de forma descritiva/fail-closed. `require_cutover_ready()` rejeita o cutover enquanto qualquer requisito obrigatório não estiver `READY_INTERNAL`.

### Single Fiscal Authority

`SingleFiscalAuthorityPlan` exige uma única autoridade futura, `fm-fiscal-core-v2`, para:

- sequence;
- idempotency;
- document lifecycle;
- archive;
- reconciliation;
- provider state;
- fiscal binding;
- capability;
- readiness;
- audit;
- events.

O plano exige cobertura de todos os domínios exatamente uma vez e proíbe que uma autoridade legado distinta permaneça `READ_WRITE` após cutover. Isso é invariante pré-cutover; nenhum writer real foi desligado nesta execução.

### Gate V2-17.1

HEAD certificado: `3f5b1892a28d898b336296dcf82ea2d8ca924d4e`.

Run `34785466576`, job `103800032384`:

- Install PASS;
- Ruff PASS;
- Mypy PASS em **116 source files**;
- Pytest **651 PASS em 7.29s**.

Nenhum bloqueio foi mascarado.

## V2-17.2 — State/Document Migration + Rollback Rehearsal

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE EM REHEARSAL SINTÉTICO — MIGRAÇÃO PRODUTIVA NÃO EXECUTADA.**

### Inventário governado

A V2-17.2 classificou 20 categorias de estado:

| Categoria | Tratamento planejado |
|---|---|
| fiscal-documents | `REFERENCE` |
| document-lifecycle | `MIGRATE` |
| numbering-sequence | `MIGRATE` |
| idempotency | `MIGRATE` |
| provider-operation-references | `MIGRATE` |
| archive-metadata | `MIGRATE` |
| xml-document-references | `ARCHIVE_ONLY` |
| fiscal-account-bindings | `MIGRATE` |
| fiscal-profiles | `MIGRATE` |
| environment-state | `MIGRATE` |
| capability-readiness-evidence | `RECONCILE` |
| outbox | `RECONCILE` |
| inbox | `RECONCILE` |
| webhook-delivery-state | `RECONCILE` |
| reconciliation-state | `MIGRATE` |
| contingencies | `RECONCILE` |
| cancel-inutilization-references | `MIGRATE` |
| correlation-causation | `MIGRATE` |
| audit-trail | `ARCHIVE_ONLY` |
| regulatory-provenance | `MIGRATE` |

O contrato não presume que payloads assinados ou trilhas históricas imutáveis precisam ser duplicados fisicamente. References/archive permanecem evidência onde aplicável.

### Migration Contract / rehearsal

`kordena_fiscal.convergence.migration` é deliberadamente sintético e in-memory. Ele transporta apenas identificadores, categorias, checksums e provenance; não é migrador de banco produtivo.

Foram certificados:

- batch versionado por `batch_id` + fingerprint SHA-256 determinístico;
- dry-run determinístico e sem mutação;
- validation-before-apply;
- record IDs únicos;
- idempotência de reaplicação;
- conflito de conteúdo fail-closed antes de mutação;
- reused batch ID com conteúdo diferente fail-closed;
- interrupção sintética no meio do batch + restart;
- reconciliation após restart;
- rollback somente do estado introduzido pelo batch, preservando estado pré-existente;
- re-run após rollback;
- proteção de sequência: target nunca pode cair abaixo de `max(legacy_last_issued, v2_last_issued)`.

### Primeira tentativa e correção

Run `34785562237`, job `103800288626`:

- Install PASS;
- Ruff FAIL por **20 E501** exclusivamente no inventário declarativo do novo módulo;
- Mypy/Pytest corretamente não executados.

As linhas foram reformatadas sem mudança semântica ou relaxamento de regra/teste.

### Gate final V2-17.2

HEAD certificado: `ba979defe16102fc2163f14a6612eac1516bcaf6`.

Run `34785613970`, job `103800433451`:

- Install PASS;
- Ruff PASS;
- Mypy PASS em **117 source files**;
- Pytest **660 PASS em 13.20s**.

### Rollback runbook — pré-cutover

Este runbook é preparatório; nenhuma ação operacional real foi executada.

#### Pré-condições antes de qualquer futuro cutover

1. identificar todos os writers efetivamente ativos no ambiente alvo;
2. resolver Kordena/FISC-20 e demais requisitos obrigatórios;
3. obter evidência operacional externa necessária;
4. executar dry-run sobre snapshot autorizado/representativo;
5. conferir contagens, checksums, sequence floors, pending outbox/inbox, unknown outcomes e contingencies;
6. congelar writers legados apenas em janela futura explicitamente aprovada;
7. impedir dual-write/split-brain;
8. obter aprovação humana explícita.

#### Sinais obrigatórios de abort

- conflito de record/checksum/provenance;
- contagem pré/pós incompatível;
- regressão de sequence;
- documento ou idempotency state não reconciliado;
- unknown outcome ainda aberto;
- contingência não resolvida;
- pending inbox/outbox/webhook sem plano de reconciliation;
- Kordena ainda não operando no V2;
- ausência de evidência externa obrigatória;
- ausência de aprovação humana.

#### Ponto de não retorno

Nenhum ponto de não retorno foi alcançado nesta autorização. Em futuro cutover real, a ativação do V2 como writer fiscal exclusivo deve ocorrer somente depois do freeze dos writers, validação da migração e reconciliation. O instante exato deve ser parte de uma autorização futura específica.

#### Sequência de rollback futuro

1. bloquear novos side effects fiscais no V2;
2. preservar integralmente ledger, archive, audit e eventos gerados durante a janela;
3. identificar qualquer documento/efeito criado após início da janela;
4. reconciliar provider state, outbox/inbox, webhook e unknown outcomes antes de reativar autoridade anterior;
5. somente reativar o writer anterior se a reativação não puder duplicar documentos, sequência ou idempotency;
6. restaurar a autoridade anterior de forma explícita e auditada;
7. reexecutar reconciliation e full regression;
8. registrar causa, estado final e aprovação humana.

O rehearsal sintético prova as invariantes de idempotência/restart/rollback do contrato, não substitui um ensaio com snapshot autorizado nem um rollback operacional real.

## Diff V2-16 → checkpoint V2-17.2

Base: `6998d5a4b7370621160e2520bbadabafca86bda0`.

HEAD certificado B17.2: `ba979defe16102fc2163f14a6612eac1516bcaf6`.

- status: `ahead`;
- ahead: **9 commits**;
- behind: **0**;
- merge-base: exatamente a base V2-16;
- arquivos líquidos: 7;
- novas superfícies restritas a `convergence`, testes e documentação/snapshot;
- nenhuma migration de banco produtiva;
- nenhuma dependência produtiva nova;
- nenhum provider/segredo/endpoint produtivo alterado.

## Estado da V2-17 após os blocos autorizados

**V2-17 — PREPARAÇÃO DE CONVERGÊNCIA PARCIALMENTE CONCLUÍDA — V2-17.1 E V2-17.2 INTERNAMENTE CERTIFICADAS; CUTOVER REAL BLOQUEADO POR PRÉ-CONDIÇÕES OBRIGATÓRIAS.**

A próxima etapa não é autorizada nesta janela. A auditoria geral deve ser concluída antes de qualquer V2-17.3.
