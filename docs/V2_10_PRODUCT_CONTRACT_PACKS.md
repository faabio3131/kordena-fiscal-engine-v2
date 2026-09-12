# V2-10 — Product Contract Packs

Status: **EM EXECUÇÃO — FOUNDATION + KORDENA + IRON FIT + VENDEDOR IA CERTIFICADOS**  
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
4. **Vendedor IA — CONCLUÍDO/CERTIFICADO:** venda genérica NFC-e/NF-e, sem vertical específica e sem inferir pagamento, settlement ou autoridade fiscal ausente.
5. **CampaIA — PRÓXIMO:** faturamento próprio de serviço/SaaS modelado com vertical SaaS/serviço, sem inferir fatos fiscais não fornecidos.
6. **Cross-product certification:** isolamento de namespaces, matriz consolidada, fixtures sintéticas, regression completa e auditoria de diff.

## Foundation

Foi criada a superfície `kordena_fiscal.contract_packs` com descriptors versionados de casos de uso/packs, registry único por pack e host namespace, validação exata de `host_namespace`, operation kind e vertical/capabilities, sempre fail-closed e sem substituir a Capability & Readiness API.

### Gate Foundation

- SHA `3af9a6ded0303ca7d591bbfa69b771c4571a9cc0`;
- run `34672479434` — **SUCCESS**;
- Install/Ruff PASS;
- Mypy strict PASS — **73 source files**;
- Pytest **354 PASS em 1.45s**;
- baseline V2-09: 346; incremento **+8**;
- CI restaurado no commit `24b54f47fad9dac11b900194d63f0803b8dfda30`.

## KordenaFiscalContractPack

Namespace canônico `fm.kordena`, sem modelos privados do Kordena. `restaurant-pos-sale` declara SALE + NFC-e e `restaurant-invoice-sale` declara SALE + NF-e. Ambos exigem explicitamente a vertical `restaurant` e as capabilities `tax.restaurant.supply-classification` e `tax.restaurant.base-adjustments`, sem copiar regra tributária nem conceder readiness.

### Gate Kordena

- SHA `6fd934c024736f3d5e23aa4d1172d60caa49fb7c`;
- run `34672769666` — **SUCCESS**;
- Install/Ruff PASS;
- Mypy strict PASS — **74 source files**;
- Pytest **362 PASS em 1.16s**;
- incremento **+8**;
- CI restaurado no commit `6a919ebdcab17b5f7b3215aa8d032abc2411afb0`.

## IronFiscalContractPack

O pack Iron Fit usa `fm.iron`, sem modelos privados do Iron Fit e sem dependência de restaurante/Kordena/SaaS.

Casos de uso:

- `membership-billing`: `MEMBERSHIP` + NFS-e + `fitness/operation.membership`;
- `recurring-membership-billing`: `RECURRING_CHARGE` + NFS-e + `fitness/operation.recurring`;
- `fitness-service-billing`: `SERVICE` + NFS-e + `fitness/operation.service`.

As ações genéricas de NFS-e ficam limitadas a issue/query/cancel/reconcile/archive reference. `INUTILIZE` e `CONTINGENCY` não são concedidos genericamente pelo pack.

### Gate Iron Fit

- SHA `3c3f18dd77663e021424b9f32c9f1a849b001c84`;
- run `34672919212` — **SUCCESS**;
- Install/Ruff PASS;
- Mypy strict PASS — **75 source files**;
- Pytest **371 PASS em 1.41s**;
- incremento **+9**;
- CI restaurado no commit `270a602316423f928ed10124fc8e9688fb38904c`.

## SalesFiscalContractPack — Vendedor IA

O pack de vendas usa o namespace canônico `fm.vendedor-ia` e permanece totalmente horizontal: não exige `restaurant`, `fitness`, `saas` ou qualquer outra vertical específica.

Casos de uso declarados:

- `nfce-sale`: `FiscalOperationKind.SALE` + NFC-e, com issue/query/cancel/contingency/reconcile/archive reference;
- `nfe-sale`: `FiscalOperationKind.SALE` + NF-e, com issue/query/cancel/inutilize/contingency/reconcile/archive reference.

O pack não cria nem infere fatos de pagamento. Uma operação sem `payments` e sem `settled_at` continua válida como contrato de venda, desde que os demais fatos canônicos existam; autoridade de pagamento, settlement e suficiência de dados fiscais permanecem responsabilidades externas. O pack também não contém readiness, homologação ou `PRODUCTION_APPROVED`.

### Contract tests Vendedor IA

Os testes provam:

- identidade estável `sales` / `fm.vendedor-ia` e dois casos de uso explícitos;
- ambos aceitam apenas `FiscalOperationKind.SALE`;
- NFC-e e NF-e permanecem famílias contratuais distintas, com ações específicas sem overclaim;
- nenhum módulo vertical é necessário;
- operação `SERVICE` no use case de venda falha fechado;
- namespace `fm.kordena` contra o pack Sales falha fechado;
- fixture sem pagamento/settlement não sofre inferência nem mutação pelo pack;
- registry resolve apenas o namespace exato `fm.vendedor-ia`;
- eventos inbound existem no AsyncAPI público e nenhum evento outbound privado é inventado;
- descriptor não contém restaurante, fitness, SaaS ou namespaces dos demais produtos.

### Gate Vendedor IA V2-10

- SHA funcional/certificação: `7be9453e6757784e38e77e83928bc0f828007f90`;
- Actions run: `34674065346` — **SUCCESS**;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **76 source files**;
- Pytest: **380 PASS em 1.29s**;
- checkpoint Iron Fit: 371; incremento Vendedor IA: **+9 testes**;
- compare contra checkpoint Iron `364d743c8aef40299b7a4855da02edf75a5a3b02`: **4 commits à frente, 0 atrás**, restrito ao pack Sales, exports, testes e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `40fb0a83574bffeab1981656dfa3f90c44762b9a`.

## Princípios de segurança arquitetural

- pack é declaração de integração, não nova autoridade fiscal;
- document kind permitido não equivale a homologação nem `PRODUCTION_APPROVED`;
- ativação de vertical é explícita quando necessária;
- ausência de vertical no Sales é intencional e testada;
- pagamento/settlement nunca são inferidos a partir do nome do produto ou do use case;
- caso de uso não declarado e cross-host falham fechado;
- contratos públicos V2-04 permanecem language-neutral.

## Gate da fase

A V2-10 somente será `CONCLUÍDA` após os quatro packs, fixtures sintéticas, matriz consolidada, isolamento cross-product, PR Draft, SHA de evidência, CI verde, Ruff, Mypy strict, Pytest, auditoria do diff e riscos residuais documentados.

## Governança

PR #11 permanece Draft. Nenhum merge, deploy, promoção, homologação externa, segredo real ou cutover foi executado.
