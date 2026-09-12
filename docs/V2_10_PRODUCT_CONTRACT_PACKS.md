# V2-10 — Product Contract Packs

Status: **CONCLUÍDO / CERTIFICADO**  
Branch: `v2/product-contract-packs`  
Base certificada: `v2/vertical-modularization` @ `5d3e06be52a75b60b36640ee8a5d1869b11de928`  
Dependência: V2-09 concluída e certificada.

## Objetivo

Provar, por contratos versionados e testes sintéticos, que um único FM Fiscal Core atende Kordena, Iron Fit, Vendedor IA e CampaIA sem importar os domínios privados desses SaaS e sem permitir que um produto herde regras, capabilities ou namespaces de outro.

## Resultado

A V2-10 entrega quatro Product Contract Packs concretos, um registry multiproduto explícito e uma matriz derivada diretamente dos descriptors certificados. O Core continua sendo a única autoridade fiscal: packs declaram integrações e casos de uso, mas não concedem readiness, homologação ou `PRODUCTION_APPROVED`.

## Product Contract Packs certificados

### Kordena

- pack `kordena`, host `fm.kordena`;
- `restaurant-pos-sale`: SALE + NFC-e + vertical `restaurant`;
- `restaurant-invoice-sale`: SALE + NF-e + vertical `restaurant`;
- capabilities setoriais já certificadas na V2-09, sem cópia de regra tributária.

Gate: `6fd934c024736f3d5e23aa4d1172d60caa49fb7c`, run `34672769666`, 74 source files, **362 PASS**.

### Iron Fit

- pack `iron`, host `fm.iron`;
- `membership-billing`: MEMBERSHIP + NFS-e + `fitness/operation.membership`;
- `recurring-membership-billing`: RECURRING_CHARGE + NFS-e + `fitness/operation.recurring`;
- `fitness-service-billing`: SERVICE + NFS-e + `fitness/operation.service`;
- sem overclaim genérico de inutilização/contingência NFS-e.

Gate: `3c3f18dd77663e021424b9f32c9f1a849b001c84`, run `34672919212`, 75 source files, **371 PASS**.

### Vendedor IA

- pack `sales`, host `fm.vendedor-ia`;
- `nfce-sale`: SALE + NFC-e;
- `nfe-sale`: SALE + NF-e;
- nenhuma vertical setorial obrigatória;
- nenhuma inferência de `payments`, `settled_at` ou autoridade de pagamento.

Gate: `7be9453e6757784e38e77e83928bc0f828007f90`, run `34674065346`, 76 source files, **380 PASS**.

### CampaIA

- pack `campaia`, host `fm.campaia`;
- `service-billing`: SERVICE + NFS-e + `service/operation.service`;
- `saas-billing`: SAAS_BILLING + NFS-e + `saas/operation.service` + `saas/operation.subscription`;
- sem inferência de pagamento, settlement, tributo municipal, jurisdição ou readiness.

Gate: `1e0558773f7a39b6e5b4156f874fd201d4efdf3c`, run `34707632430`, 77 source files, **389 PASS**.

## Foundation e composição multiproduto

A foundation `kordena_fiscal.contract_packs` fornece `ProductUseCaseDescriptor`, `ProductContractPackDescriptor`, `ProductContractPackRegistry` e validações fail-closed por `pack_id`, `host_namespace`, operation kind e vertical/capability. Gate Foundation: `3af9a6ded0303ca7d591bbfa69b771c4571a9cc0`, run `34672479434`, 73 source files, **354 PASS**.

O fechamento cross-product adiciona `FM_PRODUCT_CONTRACT_PACKS`, `FM_PRODUCT_CONTRACT_REGISTRY`, `ProductContractMatrixRow` e `V2_10_PRODUCT_CONTRACT_MATRIX`. A matriz é derivada dos descriptors imutáveis; não existe uma segunda fonte de verdade fiscal.

## Matriz consolidada V2-10

| Pack | Host | Caso de uso | Operação | Documento | Vertical |
|---|---|---|---|---|---|
| Kordena | `fm.kordena` | `restaurant-pos-sale` | SALE | NFC-e | restaurant |
| Kordena | `fm.kordena` | `restaurant-invoice-sale` | SALE | NF-e | restaurant |
| Iron | `fm.iron` | `membership-billing` | MEMBERSHIP | NFS-e | fitness |
| Iron | `fm.iron` | `recurring-membership-billing` | RECURRING_CHARGE | NFS-e | fitness |
| Iron | `fm.iron` | `fitness-service-billing` | SERVICE | NFS-e | fitness |
| Sales | `fm.vendedor-ia` | `nfce-sale` | SALE | NFC-e | — |
| Sales | `fm.vendedor-ia` | `nfe-sale` | SALE | NF-e | — |
| CampaIA | `fm.campaia` | `service-billing` | SERVICE | NFS-e | service |
| CampaIA | `fm.campaia` | `saas-billing` | SAAS_BILLING | NFS-e | saas |

Todos os eventos inbound declarados existem no AsyncAPI público da V2-04; nenhum pack inventa evento outbound privado. Os contract tests também provam que cada pack aceita somente seu próprio host e rejeita os outros três namespaces.

## Gate cross-product

O primeiro run de certificação cross-product (`34707799695`) falhou somente no Ruff por três violações E501 de formatação em `catalog.py`; Mypy e Pytest nem chegaram a executar. Não houve defeito semântico. A formatação foi corrigida cirurgicamente no commit `44941004207d2991fccfd0f28b402bc3cda9357f`.

Gate funcional definitivo:

- SHA: `44941004207d2991fccfd0f28b402bc3cda9357f`;
- Actions run: `34707834828` — **SUCCESS**;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **78 source files**;
- Pytest: **397 PASS em 1.16s**;
- incremento sobre CampaIA: **+8 testes**;
- baseline V2-09: 346; incremento líquido V2-10: **+51 testes**;
- compare checkpoint CampaIA `e39cfe905a5f9ce19b00f827fd8c56714f14c62a` -> gate: **5 commits à frente, 0 atrás**, restrito a catalog/matrix, exports, testes cross-product e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `fcd3fc69086c46ede94079a48da90a5ec0764572`.

## Auditoria do diff contra V2-09

Compare V2-09 `5d3e06be52a75b60b36640ee8a5d1869b11de928` -> checkpoint pós-gate/restauração `fcd3fc69086c46ede94079a48da90a5ec0764572`:

- **48 commits à frente, 0 atrás**;
- 16 arquivos líquidos alterados;
- alterações concentradas em documentação/snapshot da fase, `src/kordena_fiscal/contract_packs/**` e `tests/contract_packs/**`;
- `.github/workflows/ci.yml` está líquido igual à base após restauração;
- nenhum OpenAPI, AsyncAPI ou JSON Schema foi alterado pela V2-10;
- nenhuma migration, persistência, webhook, segurança S2S, provider fiscal, infraestrutura, segredo real, deploy ou cutover foi introduzido.

## Riscos residuais / limites

- Product Contract Packs são contratos de integração, não prova de homologação fiscal real;
- disponibilidade de documento/jurisdição continua subordinada à Capability & Readiness API;
- adapters reais, signer/vault, providers e homologação pertencem às fases posteriores;
- wiring operacional do Control Plane ainda será tratado na V2-11;
- NFS-e permanece dependente de capability/jurisdição específica e não recebe permissões genéricas por produto;
- o namespace Python legado `kordena_fiscal` permanece por compatibilidade transitória, sem transformar Kordena em proprietário conceitual do Core.

## Governança

PR #11 permanece Draft. Nenhum merge, deploy, promoção, homologação externa, segredo real ou cutover foi executado. O fechamento documental será submetido a uma última regressão integral antes de liberar formalmente a V2-11.
