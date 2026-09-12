# V2-10 — Product Contract Packs

Status: **EM EXECUÇÃO — FOUNDATION + KORDENA + IRON FIT CERTIFICADOS**  
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
3. **Iron Fit — CONCLUÍDO/CERTIFICADO:** mensalidades/serviços/recorrência com vertical fitness e NFS-e como família contratual, sem promover readiness.
4. **Vendedor IA — PRÓXIMO:** vendas genéricas sem dependência de restaurante/fitness/SaaS e sem inferência de pagamento/autoridade ausente.
5. **CampaIA:** faturamento próprio de serviço/SaaS modelado com vertical SaaS/serviço, sem inferir fatos fiscais não fornecidos.
6. **Cross-product certification:** isolamento de namespaces, matriz consolidada, fixtures sintéticas, regression completa e auditoria de diff.

## Foundation entregue

Foi criada a superfície `kordena_fiscal.contract_packs` com descriptors versionados de casos de uso/packs, registry único por pack e host namespace, validação exata de `host_namespace`, operation kind e vertical/capabilities, sempre fail-closed e sem substituir a Capability & Readiness API.

### Gate Foundation V2-10

- SHA `3af9a6ded0303ca7d591bbfa69b771c4571a9cc0`;
- run `34672479434` — **SUCCESS**;
- Install/Ruff PASS;
- Mypy strict PASS — **73 source files**;
- Pytest **354 PASS em 1.45s**;
- baseline V2-09: 346; incremento **+8**;
- CI restaurado no commit `24b54f47fad9dac11b900194d63f0803b8dfda30`.

## KordenaFiscalContractPack

Namespace canônico `fm.kordena`, sem modelos privados do Kordena. `restaurant-pos-sale` declara SALE + NFC-e e `restaurant-invoice-sale` declara SALE + NF-e. Ambos exigem explicitamente a vertical `restaurant` e as capabilities `tax.restaurant.supply-classification` e `tax.restaurant.base-adjustments`, sem copiar regra tributária nem conceder readiness.

Os eventos inbound declarados existem no AsyncAPI público v1.1.0; o pack não inventa evento outbound de pedido. Fixtures são integralmente sintéticas e operações com namespace de outro produto falham fechado.

### Gate Kordena V2-10

- SHA `6fd934c024736f3d5e23aa4d1172d60caa49fb7c`;
- run `34672769666` — **SUCCESS**;
- Install/Ruff PASS;
- Mypy strict PASS — **74 source files**;
- Pytest **362 PASS em 1.16s**;
- checkpoint Foundation 354; incremento **+8**;
- compare específico: **4 commits à frente, 0 atrás**;
- CI restaurado no commit `6a919ebdcab17b5f7b3215aa8d032abc2411afb0`.

## IronFiscalContractPack

O pack Iron Fit usa o namespace canônico `fm.iron`, sem importar qualquer modelo privado do Iron Fit e sem depender de restaurante, Kordena, SaaS ou outra vertical.

Casos de uso declarados:

- `membership-billing`: `FiscalOperationKind.MEMBERSHIP` + NFS-e, exigindo `fitness` / `operation.membership`;
- `recurring-membership-billing`: `FiscalOperationKind.RECURRING_CHARGE` + NFS-e, exigindo `fitness` / `operation.recurring`;
- `fitness-service-billing`: `FiscalOperationKind.SERVICE` + NFS-e, exigindo `fitness` / `operation.service`.

Todos declaram somente issue/query/cancel/reconcile/archive reference. `INUTILIZE` e `CONTINGENCY` não são concedidos genericamente para NFS-e porque dependem da autoridade de capability/jurisdição. Assim, o pack descreve a família contratual aplicável sem promover homologação ou `PRODUCTION_APPROVED`.

### Contract tests Iron Fit

Os testes provam:

- identidade estável `iron` / `fm.iron` e três use cases explícitos;
- separação correta entre membership, recurring charge e service;
- todos os casos apontam para NFS-e e a capability específica da vertical fitness;
- ausência da vertical fitness falha fechado;
- namespace `fm.kordena` contra pack Iron falha fechado;
- operation kind incompatível falha fechado;
- registry resolve somente o host exato;
- eventos declarados existem no AsyncAPI público e não há outbound inventado;
- descriptor Iron não contém restaurante nem namespaces dos demais produtos;
- nenhuma superfície de readiness é criada pelo pack.

### Gate Iron Fit V2-10

- SHA funcional/certificação: `3c3f18dd77663e021424b9f32c9f1a849b001c84`;
- Actions run: `34672919212` — **SUCCESS**;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **75 source files**;
- Pytest: **371 PASS em 1.41s**;
- checkpoint Kordena: 362; incremento Iron Fit: **+9 testes**;
- compare contra checkpoint Kordena `ce1d2e54020a2b9a6e868cf457d4211452b39a51`: **4 commits à frente, 0 atrás**, restrito ao pack Iron, exports, testes e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `270a602316423f928ed10124fc8e9688fb38904c`.

## Princípios de segurança arquitetural

- o pack é declaração de integração, não nova autoridade fiscal;
- document kind permitido não equivale a homologação nem `PRODUCTION_APPROVED`;
- ativação de vertical é explícita;
- caso de uso não declarado falha fechado;
- `host_namespace` não pode ser sobrescrito por dado de outro produto;
- contratos públicos V2-04 permanecem language-neutral.

## Gate da fase

A V2-10 somente será `CONCLUÍDA` após os quatro packs, fixtures sintéticas, matriz consolidada, isolamento cross-product, PR Draft, SHA de evidência, CI verde, Ruff, Mypy strict, Pytest, auditoria do diff e riscos residuais documentados.

## Governança

PR #11 permanece Draft. Nenhum merge, deploy, promoção, homologação externa, segredo real ou cutover foi executado.
