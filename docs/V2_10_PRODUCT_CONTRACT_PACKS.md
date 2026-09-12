# V2-10 — Product Contract Packs

Status: **EM EXECUÇÃO**  
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

1. **Foundation:** contrato imutável de Product Contract Pack, use-case descriptor e registry fail-closed.
2. **Kordena:** vendas/PDV com vertical restaurante explícita, sem alterar regras tributárias do restaurante.
3. **Iron Fit:** mensalidades/serviços/recorrência com vertical fitness e NFS-e como família contratual aplicável, sem promover readiness.
4. **Vendedor IA:** vendas genéricas sem dependência de restaurante/fitness/SaaS e sem inferência de pagamento/autoridade ausente.
5. **CampaIA:** faturamento próprio de serviço/SaaS modelado com vertical SaaS/serviço, sem inferir fatos fiscais não fornecidos.
6. **Cross-product certification:** isolamento de namespaces, matriz consolidada, fixtures sintéticas, regression completa e auditoria de diff.

## Princípios de segurança arquitetural

- o pack é uma declaração de integração, não uma nova autoridade fiscal;
- document kind permitido no pack não equivale a homologação nem `PRODUCTION_APPROVED`;
- ativação de vertical é explícita;
- caso de uso não declarado falha fechado;
- `host_namespace` não pode ser sobrescrito por dado vindo de outro produto;
- contratos públicos V2-04 permanecem language-neutral; esta fase não acopla consumidores ao pacote Python interno como requisito de integração.

## Gate da fase

A V2-10 somente será `CONCLUÍDA` após PR Draft, SHA de evidência, CI verde, Ruff, Mypy strict, Pytest, contract tests dos quatro produtos, auditoria do diff e riscos residuais documentados.

## Governança

Nenhum merge, deploy, promoção, homologação externa, segredo real ou cutover será executado automaticamente.
