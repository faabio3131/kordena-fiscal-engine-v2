# V2-18.1 — PRODUCT IDENTITY + COMMERCIAL PACKAGING

Data: 2026-09-13

Status: **EM CERTIFICAÇÃO INTERNA**.

## Identidade

Produto: **FM Fiscal**

Empresa: **FM Tecnologia**

Posicionamento: infraestrutura fiscal brasileira independente, multiproduto, versionada e
governada para SaaS e plataformas digitais que precisam integrar NF-e, NFC-e e NFS-e sem
replicar regra fiscal dentro de cada produto consumidor.

Kordena é consumidor/adaptador do FM Fiscal, não identidade comercial principal.

## Público-alvo inicial

- SaaS brasileiros e plataformas digitais;
- ecossistemas multiproduto;
- times técnicos que precisam de API fiscal versionada e auditável;
- operações que exigem isolamento por tenant, unidade, ambiente e host.

## Diferenciais técnicos comercializáveis

- Core host-neutral;
- Bridge/API pública e versionada;
- Capability & Readiness fail-closed;
- idempotência, sequence, lifecycle, archive e reconciliation governados;
- S2S/workload identity;
- inbox/outbox e webhooks assinados;
- Control Plane;
- adapters provider-neutral;
- observabilidade/compliance;
- contrato multiproduto e onboarding de novos produtos.

## Packaging

O catálogo interno define três **blueprints configuráveis**, não preços comerciais finais:

- `foundation`;
- `growth`;
- `enterprise`.

A configuração pode ser construída externamente via `CommercialCatalog.from_mapping(...)`,
portanto novos planos/edições não exigem alteração do domínio fiscal.

## Entitlements conceituais iniciais

- `documents.issue`;
- `documents.query`;
- `webhooks.delivery`;
- `reconciliation`;
- `archive.reference`;
- `usage.documents`;
- `support.premium`.

Esses identifiers são catálogo comercial. Não promovem capability fiscal nem
`PRODUCTION_APPROVED`.

## Preço

**NÃO DEFINIDO NESTA FASE.** Nenhum preço foi inventado ou hardcoded. Preço final permanece
decisão comercial do Diretor.
