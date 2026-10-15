# AGENTS.md — FM Fiscal Core V2

## Autoridade

Este repositório implementa a evolução independente e multiproduto do motor fiscal brasileiro da FM Tecnologia.

O Fiscal Core não é autoridade do domínio de negócio de Kordena, Iron Fit, Vendedor IA, CampaIA ou qualquer consumidor. Ele recebe contratos fiscais neutros, executa regras e lifecycle fiscais e devolve resultados/eventos auditáveis.

## Estratégia de transição

1. O repositório `faabio3131/kordena-fiscal-engine` permanece baseline congelado durante a transição.
2. O baseline certificado de origem é `b336def47ad4f5188307102203f4e04b98406014`.
3. O V2 deve provar equivalência antes de refatoração multiproduto.
4. O fork é temporário. Depois do cutover certificado, o V2 vira a única arquitetura fiscal ativa e o original é preservado como histórico/auditoria.

## Regras obrigatórias

1. Nunca adicionar segredo, certificado real, senha, CSC, token, credencial, endpoint privado ou dado real de cliente.
2. Todo dado de exemplo deve ser sintético.
3. Alterações fiscais relevantes exigem teste correspondente.
4. Emissão deve ser idempotente por construção.
5. Numeração fiscal não pode usar estratégia concorrencialmente insegura como `MAX + 1`.
6. Regras tributárias devem possuir versão/vigência e ficar atrás do Tax Rule Engine.
7. Documento autorizado deve preservar snapshot histórico; cadastro atual não reescreve passado.
8. Adapters externos não podem inventar regra de negócio.
9. IA pode sugerir classificação, nunca alterar silenciosamente configuração fiscal de alto impacto.
10. Falhas de escopo, assinatura, schema, autorização, capability ou segredo são fail-closed.
11. Core não importa domínios privados dos SaaS consumidores.
12. Integração multiproduto exige `host_system_id`/namespace e binding governado de tenant/unidade.
13. Nenhum merge, deploy, promoção para produção ou cutover é automático.

## Disciplina de entrega

Para cada bloco V2:

- confirmar escopo em `docs/EXECUTION_TRACKER_V2.md`;
- implementar somente o bloco ativo e dependências mínimas;
- executar testes dirigidos;
- executar Ruff, Mypy strict e Pytest;
- revisar diff;
- registrar SHA, PR e CI;
- registrar riscos residuais;
- somente então alterar o estado para `CONCLUÍDO`.

Nenhuma etapa é concluída por declaração sem evidência.


## NFCore Commercial Launch — execução governada por plano mestre

Esta seção rege o trabalho do **FM NFCORE V1 — Commercial Launch** e complementa as regras históricas acima.

### Arquivos obrigatórios

Antes de executar qualquer bloco, leia integralmente:

1. `docs/NFCORE_V1_COMPLETION_MASTER_EXECUTION_SCHEDULE_2026-10-05.md`;
2. `docs/NFCORE_V1_EXECUTION_LEDGER.md`;
3. `docs/standards/FM_AI_MASTER_PLAN_EXECUTION_STANDARD.md`;
4. este `AGENTS.md`.

Git/GitHub, CI e runtime continuam sendo as fontes superiores para determinar o CURRENT técnico. O cronograma governa escopo/ordem/gates; o ledger governa estado/prova; o chat não substitui a persistência do plano.

### Disciplina obrigatória

1. Antes de qualquer coisa, reconfirmar `main`, HEAD, PRs abertas, CI e o ambiente afetado.
2. O plano precisa estar `APROVADO` ou `EM EXECUCAO`.
3. Executar somente a primeira tarefa não concluída do ledger, uma por vez.
4. Releia a tarefa no cronograma imediatamente antes de executá-la; não use memória do chat como substituto.
5. Uma PR de execução corresponde a uma única tarefa `NFV1-Pxx-Tyy`, exceto a PR inicial de bootstrap documental.
6. Concluído significa critério de aceite provado. Rode os testes, confira o resultado, obtenha CI/evidência e só então marque `[x]`.
7. O campo **Prova** de tarefa concluída deve registrar PR, CI e commit/SHA; integrações externas também exigem evidência de runtime.
8. Falha deve ser corrigida pela causa; nunca pular, apagar ou enfraquecer teste válido.
9. O que não foi provado é **não confirmado**. Fake/synthetic/mock não prova integração real.
10. Qualquer pendência descoberta deve ser resolvida, receber ID no cronograma/ledger, virar blocker ou ser rejeitada explicitamente com justificativa.
11. Alteração de escopo exige atualizar cronograma e ledger antes da execução.
12. Rode `python3 scripts/check_nfcore_plan.py` antes de abrir/atualizar a PR e antes de declarar o item certificável.

### Parada obrigatória para decisão humana

Parar e solicitar autorização específica antes de:

- decisão de produto/preço;
- mudança de segurança sensível;
- tratamento novo de dado pessoal;
- gasto ou conta real;
- segredo/certificado/credencial real;
- alteração de outro repositório;
- mudança de visibilidade;
- merge quando não autorizado;
- deploy;
- migration produtiva;
- DNS;
- produção fiscal;
- transação real não previamente aprovada;
- operação irreversível.

### Regra de continuidade

Ao retomar o projeto, nunca continue apenas do chat. Reabra o cronograma, o ledger e o último checkpoint persistente; depois reconfirme GitHub/CI/runtime e execute exatamente a próxima tarefa permitida.


### Checkpoint ativo — NFV1-P09-T02 (2026-10-15)

- CURRENT auditado: `main=4f7d520ef66831edb56d8d68c60ca24cc17b51f4`; P09-T01 PR #187 MERGED, CI pós-merge #38744017770 SUCCESS e governança #38744017835 SUCCESS.
- Tarefa em execução: `NFV1-P09-T02 — Métricas`; PR [#188](https://github.com/faabio3131/kordena-fiscal-engine-v2/pull/188), branch `feat/nfv1-p09-t02-runtime-metrics`, **DRAFT / NÃO MERGEADA**.
- Implementações sob revisão: métricas HTTP por método e classe de status, latência; métricas de despacho do Worker e snapshots outbox/PostgreSQL, usando somente `MetricsRegistry` canônico. Falhas de telemetria não podem alterar resposta ou execução fiscal.
- Gates CURRENT devem ser consultados pelo HEAD da PR no GitHub; CI verde em commit anterior não certifica HEAD novo.
- **PENDENTE / NÃO CERTIFICADO:** eventos comerciais, fulfillment, ativação, reconciliação, rejeições fiscais e falhas de provedores somente onde houver fronteiras canônicas reais. Não usar contagem de HTTP nem mocks como prova de operação comercial ou homologação fiscal.
- Ao retomar: reconfirmar branch/HEAD/PR/CI; conferir Ruff/Mypy/Pytest/testes E2E e `python3 scripts/check_nfcore_plan.py`; conciliar ledger e provas. Somente marcar `[x]` após gates completos no HEAD correto. P09-T03 depende do fechamento de T02.
- Restrições preservadas: sem merge não autorizado, sem deploy, migrations produtivas, DNS, segredos ou ativação fiscal real. O ledger e cronograma permanecem fontes de estado e escopo; este checkpoint não os substitui.

### Auditoria de reuso obrigatório — P09-T02 (2026-10-15)

A inspeção do código CURRENT na PR #188 confirmou que as autoridades abaixo **já existem**. Esta é uma matriz de desenho/impacto, **não** certificado de integração real:
- **Fulfillment comercial:** `application/commercial_fulfillment.py::CommercialFulfillmentService.process` grava receipt idempotente, estado de compra/contrato/assinatura e commit; distingue replay. Instrumentação deve observar o resultado **depois** do commit, sem alterar decisões nem usar a entrada bruta como venda confirmada.
- **Ativação efetiva:** `application/commercial_activation.py::CommercialCustomerActivationService.provision/mark_active` governa `ACTIVATION_PENDING` e `ACTIVE`; apenas `mark_active` com commit de estado ativo permite registrar ativação concluída. A simples abertura de oferta ou envio de email **não** é ativação.
- **Reconciliação comercial:** `application/cakto_reconciliation.py::CaktoCanonicalCommercialBridgeService.reconcile` produz `CaktoReconciliationResult.drift` a partir de estado canônico e snapshot externo; não equivale a reconciliação fiscal.
- **Reconciliação fiscal:** `reconciliation/engine.py::FiscalReconciliationEngine.reconcile_operation` já calcula status/issues, pure domain; a emissão operacional deve ocorrer no orquestrador autorizado, não como efeito colateral no motor puro.
- **Taxonomia canônica existente:** `runtime/commercial_observability.py::CommercialTelemetry` define `CommercialTelemetryEvent`/`CommercialTelemetryOutcome` e `nfcore_commercial_events_total`. Reutilizar antes de propor novo contador para os mesmos fatos. `observability/metrics.py` é um subsistema V2 existente; inventariar usos/contratos antes de consolidar exportadores. Não criar terceiro registry.
- **Rejeições fiscais:** pendente rastrear e provar o ponto de decisão canônico de rejeição por provedor, distinguindo erro de transporte, rejeição de negócio e indisponibilidade. Não contar qualquer erro HTTP/webhook como rejeição fiscal.

**Estado:** mapa de reuso confirmado no código; conexões runtime, cobertura de testes da telemetria comercial e CI no HEAD final ainda PENDENTES. P09-T02 permanece EM EXECUÇÃO, PR #188 Draft. Não implementar nova regra de fulfillment/ativação/reconciliação; apenas adapters seguros e testes após inspeção de composição e persistência.

### Reconciliação Web vs. código — ponto de continuidade (2026-10-15)

- Auditoria persistida em `docs/checkpoints/NFV1_WEB_PARITY_RECONCILIATION_CURRENT_2026-10-15.md` na PR #188. `main` auditada: `4f7d520ef66831edb56d8d68c60ca24cc17b51f4`.
- Constatado: menu `portal/app.js`, executor `web/portal_runtime.py`, rotas condicionais `web/app.py` e domínios comerciais/fiscais já existem. **Não reconstruir por padrão**; verificar composição real da API/Worker/Portal, RBAC/tenant e publicação Web na mesma revisão.
- Paridade Web em staging permanece NÃO COMPROVADA; a auditoria do código não autoriza declarar produto pronto ou fazer deploy. PR #188 permanece DRAFT, P09-T02 em execução.
- Próxima ação: mapear wiring runtime e comparar superfícies código→API→Web→E2E→staging; corrigir somente gaps comprovados. Preservar gates e autorização humana para merge/deploy.
