# V2-17.4 — CONSUMER INTEGRATION CLOSURE

Data: 2026-09-13

Estado: **CONCLUÍDA COMO REAUDITORIA GOVERNADA — BLOQUEIOS REAIS PRESERVADOS**.

## Objetivo

Revalidar o estado dos quatro consumidores FM antes da certificação final de convergência e
executar todo o trabalho legítimo que não dependa de fatos de negócio inexistentes ou de
pré-requisitos externos.

## Kordena

Repositório: `faabio3131/fm-ai-platform`

PR revalidada: `#118`

HEAD observado: `9ee10a08cf445cc7233cde5b70564f8feade315c`

Estado observado na própria PR: **PARCIAL**.

O pré-requisito Web Premium/FISC-20 continua não liberado. Portanto:

- integração runtime final com FM Fiscal V2 NÃO foi inventada;
- Kordena continua `BLOCKED_PRODUCT` para cutover;
- o bloqueio não invalida o Core universal nem impede o avanço comercial interno.

## Iron Fit

Repositório: `faabio3131/iron-fit-backend`

PR revalidada: `#48`

HEAD: `2be8321eeb066f0296ba812faab0a098c32f0632`

Estado: **CONCLUÍDO/CERTIFICADO INTERNAMENTE**.

Autoridade preservada:

- fato fiscal deriva de `Charge` pago/liquidado;
- handoff permanece idempotente;
- NFS-e/capability/readiness continuam sob autoridade do FM Fiscal;
- nenhuma regra fiscal comum foi duplicada no Iron.

## Vendedor IA

Repositório: `faabio3131/ai-sales-saas-vendedor-ia`

PR revalidada: `#1`

HEAD: `b4b7fb05236c481d5626de5386864ae6f5227418`

Estado: **BLOQUEADO PARCIAL / HANDOFF INTERNO CERTIFICADO**.

Continua válido:

- `Payment.status = CONFIRMED` como fato autoritativo de liquidação;
- produto não possui ainda CPF/CNPJ e endereço fiscal suficientes no domínio atual;
- não existem fatos suficientes para selecionar com segurança NF-e versus NFC-e;
- nenhum documento fiscal foi adivinhado.

## CampaIA

Repositório: `faabio3131/CampaIA`

PR revalidada: `#1`

HEAD: `bdebbc3558ff8b07c1a38e0cb728be0dc3635c4b`

Estado: **BLOQUEADO PARCIAL / ADAPTER INTERNO CERTIFICADO**.

Continua válido:

- `SettledOwnBillingFact` é a boundary fail-closed;
- o produto ainda não possui authority real de billing/payment próprio;
- media spend e orçamento de campanha NÃO são receita própria;
- nenhuma assinatura/pagamento fictício foi criado para fechar o fiscal.

## Cross-product certification

A suíte vigente `tests/test_v2_16_cross_product_closure.py` continua cobrindo o estado atual:

- quatro hosts;
- tenant isolation;
- unit isolation;
- environment isolation;
- idempotency isolation;
- correlation;
- causation;
- capabilities;
- readiness obrigatório;
- spoofing cross-product fail-closed;
- ausência de `production_approved` na superfície de integração.

A regressão completa da V2-17.3 executou essa suíte novamente dentro do total de 675 testes.

## Classificação final deste bloco

| Produto | Estado de integração | Impede Core interno? | Impede cutover real? |
|---|---|---:|---:|
| Kordena | `BLOCKED_PRODUCT` | Não | Sim |
| Iron Fit | `READY_INTERNAL` | Não | Não, isoladamente |
| Vendedor IA | `BLOCKED_PRODUCT` parcial | Não | Sim para uso completo do produto |
| CampaIA | `BLOCKED_PRODUCT` parcial | Não | Sim para billing próprio completo |

Nenhum bloqueio foi convertido artificialmente em verde.
