# V2-16 — Integração dos Produtos FM — Registro de Execução

Data: 2026-09-13

## Estado de entrada

A V2-15 permanece preservada no checkpoint certificado `33e34866bc6e8c736c585c45101ce214816e0594`, com a PR #16 OPEN/DRAFT e não mergeada. Esta execução não altera aquele checkpoint, não realiza deploy/cutover e não usa segredos reais.

## V2-16.1 — Contrato de integração

Status: IMPLEMENTADO — AGUARDANDO GATE DE CERTIFICAÇÃO.

A fronteira operacional comum foi adicionada em `kordena_fiscal.integrations`. Ela deriva o produto/use case exclusivamente dos Product Contract Packs certificados e fixa a ligação com o contrato público FM Fiscal Bridge v1:

- capability/readiness: `GET /v1/fiscal/capabilities`;
- emissão: `POST /v1/fiscal/issuances`;
- acompanhamento: `GET /v1/fiscal/operations/{operation_id}`;
- reconciliação: `GET /v1/fiscal/reconciliation`;
- webhooks: `POST /v1/fiscal/webhooks`;
- escopo obrigatório por tenant/unidade/correlação/host;
- idempotência explícita via `Idempotency-Key`;
- readiness obrigatório antes de mutações.

O contrato é descritivo e fail-closed. Resolver um Product Contract Pack NÃO declara município/UF/provider homologado, NÃO concede prontidão de produção e NÃO substitui a Capability & Readiness API.

## V2-16.2 — Integração Kordena

Status: BLOQUEADA POR PRÉ-REQUISITO DO PLANO MESTRE.

O Plano Mestre determina que a integração Kordena só avance quando a V1 Web Premium estiver liberada para FISC-20. Em 2026-09-13, a PR Kordena #118 (`feat/web-parity-v1-total-original-migration`) permanece OPEN/DRAFT e registra estado funcional parcial. Portanto:

- nenhum acoplamento prematuro foi introduzido no Kordena;
- o Product Contract Pack `kordena` permanece disponível como contrato certificado;
- a implementação runtime fica congelada até o pré-requisito real ficar verde;
- este bloqueio não é defeito do FM Fiscal Core e não deve ser mascarado como integração concluída.

## V2-16.3 — Integração Iron Fit

Status: EM EXECUÇÃO.

Levantamento inicial confirmou que a autoridade de liquidação no Iron Fit é `FinancialService.payCharge`: a cobrança é marcada `PAID` e a `FinancialTransaction` correspondente é criada dentro da mesma transação serializável, com tratamento idempotente de repetição/concorrência. A integração NFS-e deverá nascer desse fato liquidado, nunca da mera criação de assinatura/cobrança.

## Guardrails desta execução

- SEM MERGE.
- SEM DEPLOY.
- SEM PRODUÇÃO REAL.
- SEM CUTOVER.
- SEM SEGREDO REAL NO REPOSITÓRIO.
- SEM HOMOLOGAÇÃO EXTERNA INVENTADA.
- SEM PROMOÇÃO INDEVIDA DE `PRODUCTION_APPROVED`.
- bloqueios reais de pré-requisito devem ser registrados como bloqueio, não convertidos artificialmente em verde.
