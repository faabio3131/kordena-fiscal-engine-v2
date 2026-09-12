# V2-10 — Product Contract Packs

Status: **EM EXECUÇÃO — FOUNDATION + KORDENA CERTIFICADOS**  
Branch: `v2/product-contract-packs`  
Base certificada: `v2/vertical-modularization` @ `5d3e06be52a75b60b36640ee8a5d1869b11de928`  
Dependência: V2-09 concluída e certificada.

## Objetivo

Provar, por contratos versionados e testes sintéticos, que um único FM Fiscal Core atende Kordena, Iron Fit, Vendedor IA e CampaIA sem importar os domínios privados desses SaaS e sem permitir que um produto herde regras, capabilities ou namespaces de outro.

## Entregas vinculantes

- `KordenaFiscalContractPack`;
- `IronFiscalContractPack`;
- `SalesFiscalContractPack`;
- `CampaiaFiscalContractPack`;
- contrato base/registry explícito para packs de produto;
- fixtures sintéticas e contract tests por produto;
- matriz versionada de casos de uso, `FiscalOperationKind`, documentos, eventos e capabilities esperadas;
- integração explícita com módulos verticais V2-09 quando aplicável;
- nenhum pack concede readiness fiscal: a autoridade permanece na Capability & Readiness API;
- nenhum pack importa código privado de Kordena, Iron Fit, Vendedor IA ou CampaIA;
- nenhum adapter/pack importa domínio de outro SaaS;
- resolução por `host_namespace` explícito e fail-closed.

## Blocos de execução

1. **Foundation — CONCLUÍDO/CERTIFICADO:** contrato imutável de Product Contract Pack, use-case descriptor e registry fail-closed.
2. **Kordena — CONCLUÍDO/CERTIFICADO:** vendas/PDV com vertical restaurante explícita, sem alterar regras tributárias do restaurante.
3. **Iron Fit — PRÓXIMO:** mensalidades/serviços/recorrência com vertical fitness e NFS-e como família contratual aplicável, sem promover readiness.
4. **Vendedor IA:** vendas genéricas sem dependência de restaurante/fitness/SaaS e sem inferência de pagamento/autoridade ausente.
5. **CampaIA:** faturamento próprio de serviço/SaaS modelado com vertical SaaS/serviço, sem inferir fatos fiscais não fornecidos.
6. **Cross-product certification:** isolamento de namespaces, matriz consolidada, fixtures sintéticas, regression completa e auditoria de diff.

## Foundation entregue

Foi criada a superfície `kordena_fiscal.contract_packs` com:

- `ProductUseCaseDescriptor`: declara operation kinds, document kinds, ações fiscais, vertical opcional, capabilities verticais e eventos inbound/outbound;
- `ProductContractPackDescriptor`: identidade/versionamento por `pack_id` + `host_namespace`, resolução explícita de use case e validação de operação;
- `ProductContractPackRegistry`: registro único por pack e por host namespace;
- `DeclarativeProductFiscalContractPack` e protocolo `ProductFiscalContractPack` para extensão futura;
- validação de `host_namespace` exato e operation kind declarado;
- resolução de pack/use case inexistente fail-closed;
- validação explícita do contrato de vertical contra `VerticalModuleRegistry` V2-09;
- nenhuma função da foundation consulta, promove ou substitui Capability & Readiness.

### Contract tests da Foundation

Os testes cobrem matriz declarativa, use case desconhecido, isolamento por host namespace, operation kind incompatível, colisão de `pack_id`/host, pack/host não registrado, módulo vertical ausente, capability vertical sem módulo e duplicidade de use case.

### Gate Foundation V2-10

- SHA funcional/certificação: `3af9a6ded0303ca7d591bbfa69b771c4571a9cc0`;
- Actions run: `34672479434` — **SUCCESS**;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **73 source files**;
- Pytest: **354 PASS em 1.45s**;
- baseline V2-09: 346 testes; incremento da Foundation: **+8 testes**;
- workflow restaurado para apenas `workflow_dispatch` no commit `24b54f47fad9dac11b900194d63f0803b8dfda30`.

## KordenaFiscalContractPack

O primeiro pack concreto usa o namespace canônico certificado `fm.kordena` e não importa nenhum modelo privado do SaaS Kordena.

Casos de uso declarados:

- `restaurant-pos-sale`: `FiscalOperationKind.SALE` + NFC-e, com ações de issue/query/cancel/contingency/reconcile/archive reference;
- `restaurant-invoice-sale`: `FiscalOperationKind.SALE` + NF-e, com issue/query/cancel/inutilize/contingency/reconcile/archive reference.

Ambos exigem explicitamente o módulo vertical `restaurant` e as capabilities `tax.restaurant.supply-classification` e `tax.restaurant.base-adjustments`. A declaração não executa nem replica regras tributárias; ela apenas exige a vertical V2-09 já certificada.

Os eventos de retorno declarados são exatamente eventos públicos existentes no AsyncAPI v1.1.0: autorização, rejeição, cancelamento, atualização de emissão, reconciliação e archive reference. O pack não inventa evento outbound de pedido; chamadas de emissão permanecem nos contratos públicos do Bridge.

### Contract tests Kordena

A fixture sintética representa uma venda Kordena canônica em homologação, com `host_namespace=fm.kordena`, sem dado real de cliente.

Os testes provam:

- identidade estável do pack e dos dois use cases;
- NFC-e no PDV e NF-e na venda faturada como famílias contratuais, sem promoção de readiness;
- vertical restaurante e suas duas capabilities obrigatórias;
- ausência da vertical falha fechado;
- operação com `fm.iron` no pack Kordena falha por namespace mismatch;
- registry resolve Kordena somente pelo pack/host exatos;
- todos os eventos declarados existem no AsyncAPI público;
- o descriptor Kordena não expõe namespaces de Iron, Vendedor IA ou CampaIA.

### Gate Kordena V2-10

- SHA funcional/certificação: `6fd934c024736f3d5e23aa4d1172d60caa49fb7c`;
- Actions run: `34672769666` — **SUCCESS**;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **74 source files**;
- Pytest: **362 PASS em 1.16s**;
- checkpoint Foundation: 354; incremento Kordena: **+8 testes**;
- compare contra checkpoint Foundation `532275595a5055a008eb69c46fa19400a3f790c2`: **4 commits à frente, 0 atrás**, restrito ao pack Kordena, exports, testes e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `6a919ebdcab17b5f7b3215aa8d032abc2411afb0`.

## Princípios de segurança arquitetural

- o pack é uma declaração de integração, não uma nova autoridade fiscal;
- document kind permitido no pack não equivale a homologação nem `PRODUCTION_APPROVED`;
- ativação de vertical é explícita;
- caso de uso não declarado falha fechado;
- `host_namespace` não pode ser sobrescrito por dado vindo de outro produto;
- contratos públicos V2-04 permanecem language-neutral; esta fase não acopla consumidores ao pacote Python interno como requisito de integração.

## Gate da fase

A V2-10 somente será `CONCLUÍDA` após os quatro packs, fixtures sintéticas, matriz consolidada, isolamento cross-product, PR Draft, SHA de evidência, CI verde, Ruff, Mypy strict, Pytest, auditoria do diff e riscos residuais documentados.

## Governança

PR #11 permanece Draft. Nenhum merge, deploy, promoção, homologação externa, segredo real ou cutover foi executado.
