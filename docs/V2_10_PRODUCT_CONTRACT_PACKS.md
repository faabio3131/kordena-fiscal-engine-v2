# V2-10 — Product Contract Packs

Status: **EM EXECUÇÃO — QUATRO PRODUCT PACKS CERTIFICADOS; CROSS-PRODUCT PENDENTE**  
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

1. **Foundation — CONCLUÍDO/CERTIFICADO**.
2. **Kordena — CONCLUÍDO/CERTIFICADO**.
3. **Iron Fit — CONCLUÍDO/CERTIFICADO**.
4. **Vendedor IA — CONCLUÍDO/CERTIFICADO**.
5. **CampaIA — CONCLUÍDO/CERTIFICADO**.
6. **Cross-product certification — PRÓXIMO:** matriz consolidada, isolamento entre os quatro namespaces, regressão completa e auditoria final do diff.

## Foundation

`kordena_fiscal.contract_packs` fornece descriptors versionados de pack/use case, registry único por `pack_id` e `host_namespace`, validação exata de namespace, operation kind e vertical/capabilities, sempre fail-closed e sem substituir a Capability & Readiness API.

Gate Foundation: SHA `3af9a6ded0303ca7d591bbfa69b771c4571a9cc0`, run `34672479434`, 73 source files, **354 PASS**. CI restaurado em `24b54f47fad9dac11b900194d63f0803b8dfda30`.

## KordenaFiscalContractPack

Namespace `fm.kordena`. `restaurant-pos-sale` declara SALE + NFC-e e `restaurant-invoice-sale` declara SALE + NF-e. Ambos exigem explicitamente a vertical `restaurant` e capabilities já certificadas na V2-09, sem copiar regra tributária nem conceder readiness.

Gate Kordena: SHA `6fd934c024736f3d5e23aa4d1172d60caa49fb7c`, run `34672769666`, 74 source files, **362 PASS**. CI restaurado em `6a919ebdcab17b5f7b3215aa8d032abc2411afb0`.

## IronFiscalContractPack

Namespace `fm.iron`. Casos `membership-billing`, `recurring-membership-billing` e `fitness-service-billing` usam NFS-e e a vertical `fitness` com capability específica por operação. `INUTILIZE` e `CONTINGENCY` não são concedidos genericamente para NFS-e.

Gate Iron Fit: SHA `3c3f18dd77663e021424b9f32c9f1a849b001c84`, run `34672919212`, 75 source files, **371 PASS**. CI restaurado em `270a602316423f928ed10124fc8e9688fb38904c`.

## SalesFiscalContractPack — Vendedor IA

Namespace `fm.vendedor-ia`. `nfce-sale` e `nfe-sale` aceitam somente `SALE`, sem vertical setorial e sem inferir `payments`, `settled_at` ou autoridade de pagamento. Cross-host e operation kind incompatível falham fechado.

Gate Vendedor IA: SHA `7be9453e6757784e38e77e83928bc0f828007f90`, run `34674065346`, 76 source files, **380 PASS**. CI restaurado em `40fb0a83574bffeab1981656dfa3f90c44762b9a`.

## CampaiaFiscalContractPack

O pack CampaIA usa o namespace canônico `fm.campaia` e modela somente fatos de faturamento próprios do produto. Nenhum modelo privado da CampaIA é importado.

Casos de uso declarados:

- `service-billing`: `FiscalOperationKind.SERVICE` + NFS-e, exigindo vertical `service` e capability `operation.service`;
- `saas-billing`: `FiscalOperationKind.SAAS_BILLING` + NFS-e, exigindo vertical `saas` e capabilities `operation.service` + `operation.subscription`.

Os dois casos declaram somente issue/query/cancel/reconcile/archive reference. `INUTILIZE` e `CONTINGENCY` não são concedidos genericamente para NFS-e. O pack não infere pagamento, settlement, fatos tributários municipais, jurisdição, readiness ou `PRODUCTION_APPROVED`.

### Contract tests CampaIA

Os testes provam:

- identidade estável `campaia` / `fm.campaia` e dois use cases explícitos;
- SERVICE e SAAS_BILLING permanecem contratos distintos;
- NFS-e é apenas família contratual, sem promoção de readiness;
- as verticais `service` e `saas` são exigidas explicitamente e ausência de qualquer uma falha fechado;
- `SUBSCRIPTION` não é silenciosamente aceito no use case `saas-billing`;
- namespace `fm.vendedor-ia` contra CampaIA falha fechado;
- fixture sem `payments` e sem `settled_at` não sofre inferência ou mutação;
- eventos inbound existem no AsyncAPI público e nenhum outbound privado é inventado;
- descriptor não contém restaurante, fitness nem namespaces dos outros produtos.

### Gate CampaIA V2-10

- SHA funcional/certificação: `1e0558773f7a39b6e5b4156f874fd201d4efdf3c`;
- Actions run: `34707632430` — **SUCCESS**;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **77 source files**;
- Pytest: **389 PASS em 2.14s**;
- checkpoint Vendedor IA: 380; incremento CampaIA: **+9 testes**;
- compare `def50ae4d8914ec88821309a5a31990cfdc0b879` -> `1e0558773f7a39b6e5b4156f874fd201d4efdf3c`: **4 commits à frente, 0 atrás**, restrito ao pack CampaIA, exports, testes e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `e4918e8471a3e710daab897d32ffe000bcba5212`.

## Princípios de segurança arquitetural

- pack é declaração de integração, não autoridade fiscal;
- document kind permitido não equivale a homologação nem `PRODUCTION_APPROVED`;
- ativação de vertical é explícita quando necessária;
- pagamento, settlement, tributos e jurisdição nunca são inferidos pelo nome do produto;
- caso de uso não declarado, operation kind incompatível e cross-host falham fechado;
- contratos públicos V2-04 permanecem language-neutral.

## Gate da fase

A V2-10 somente será `CONCLUÍDA` após a certificação cross-product consolidada, matriz final de documentos/eventos/capabilities, isolamento entre os quatro hosts, regressão completa, auditoria do diff contra V2-09 e riscos residuais documentados.

## Governança

PR #11 permanece Draft. Nenhum merge, deploy, promoção, homologação externa, segredo real ou cutover foi executado.
