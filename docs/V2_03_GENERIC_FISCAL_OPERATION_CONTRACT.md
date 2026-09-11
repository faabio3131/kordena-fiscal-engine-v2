# V2-03 — Fiscal Operation Contract genérico

Status: **CONCLUÍDO E CERTIFICADO**  
Data: 2026-09-11

## Objetivo

Remover a suposição de que toda origem fiscal é uma venda e criar um contrato canônico que represente fatos econômicos/fiscais de qualquer produto consumidor sem importar modelos privados do host.

## Princípio

O FM Fiscal recebe uma **operação fiscal neutra**, não uma `Sale`, `Comanda`, `Charge`, `Subscription`, `Campaign`, `Student` ou qualquer entidade privada do SaaS consumidor.

```text
host privado
   ↓ adapter
FiscalOperationSnapshot
   ↓
FM Fiscal Core
```

## Operações suportadas pelo contrato

- venda;
- mensalidade;
- assinatura;
- serviço;
- cobrança recorrente;
- faturamento SaaS;
- operação genérica extensível.

## Contrato canônico

`FiscalOperationSnapshot` carrega:

- `scope` universal V2;
- `operation_reference` estável;
- `operation_kind`;
- `occurred_at`;
- `settled_at` quando houver liquidação;
- totais econômicos neutros;
- pagamentos neutros;
- troco quando aplicável.

`FiscalOperationTotals` valida a identidade econômica:

```text
net = gross - discount + surcharge
```

`FiscalOperationPayment` representa fatos de pagamento sem códigos específicos de adquirente, provedor ou documento fiscal.

## Compatibilidade

O contrato legado `HostSettlementSnapshot` permanece disponível durante a migração. A reconciliação antiga é mantida como wrapper compatível e converte o snapshot legado para `FiscalOperationSnapshot`.

Novos consumidores e novos contratos públicos devem utilizar o modelo neutro.

## Reconciliação neutra

A rota canônica passa a ser `FiscalReconciliationEngine.reconcile_operation(...)`.

Ela:

- exige uma operação liquidada;
- compara a partição universal host/account/unit/environment;
- valida a mesma `operation_reference`;
- compara total líquido e pagamentos da operação com o documento fiscal;
- trata cancelamento, duplicidade, processamento pendente e ausência de documento sem semântica exclusiva de venda.

O método legado `reconcile(HostSettlementSnapshot, ...)` é preservado e traduz códigos neutros para os códigos históricos esperados pelo baseline V1.

## Invariantes

1. O Core não conhece entidades privadas do host.
2. `operation_reference` deve ser estável e idempotente no namespace do host.
3. timestamps devem ser timezone-aware.
4. `settled_at`, quando presente, não pode anteceder `occurred_at`.
5. valores monetários devem ser BRL, finitos e não negativos neste contrato.
6. `change_amount` não pode exceder o total de pagamentos.
7. uma reconciliação fiscal de operação exige `settled_at`.
8. cross-host/cross-account/cross-unit/cross-environment falha fechado.
9. compatibilidade legado não pode governar novos contratos universais.

## Fora de escopo

- OpenAPI/JSON Schema/AsyncAPI: V2-04;
- autenticação S2S: V2-05;
- persistência durável: V2-07;
- adapters concretos Kordena/Iron/Vendedor/CampaIA: V2-10/V2-16;
- regras tributárias específicas por tipo de operação continuam no motor fiscal e não no contrato de host.

## Certificação

- PR #4 criada em Draft sobre V2-02;
- base: `637b326cab5c179875186201756bd3561bdf008d`;
- gate final SHA: `598a2ec83aecd27a5427f3e1e401532e8be2696a`;
- GitHub Actions run `34645939363`: **SUCCESS**;
- Install: PASS — `fm-fiscal-core==0.1.0.dev0`;
- Ruff: PASS;
- Mypy strict: PASS — **47 source files sem issues**;
- Pytest: PASS — **262 passed em 0.77s**;
- venda, mensalidade, assinatura, serviço, cobrança recorrente e faturamento SaaS cobertos por testes;
- compatibilidade `HostSettlementSnapshot` preservada pelos testes legados e por teste explícito de tradução de códigos;
- reconciliação cross-host permanece fail-closed;
- diff auditado contra V2-02 e limitado ao contrato genérico, reconciliação, testes e documentação;
- nenhuma regra tributária, cálculo, emissão, numeração, gateway, assinatura ou provider contract foi alterado;
- CI retornado a `workflow_dispatch` após o gate verde.

O primeiro gate desta fase (`34645774207`) parou apenas em uma violação `E501` de formatação antes de Mypy/Pytest; a linha foi corrigida e o gate definitivo acima ficou integralmente verde.

## Decisão

V2-03 está **CONCLUÍDO E CERTIFICADO**. O `FiscalOperationSnapshot` passa a ser o contrato canônico para novas fronteiras universais. V2-04 — FM Fiscal Bridge está liberado.
