# FM Fiscal

Produto fiscal independente e multiproduto da **FM Tecnologia**, construído a partir de um baseline fiscal já certificado e evoluído para operar como infraestrutura horizontal para os produtos do ecossistema FM e integrações futuras.

## Posicionamento

O FM Fiscal é a fonte fiscal ativa de longo prazo da FM Tecnologia. Ele não pertence ao Kordena: o Kordena será um dos produtos consumidores, ao lado de Iron, Vendedor IA, CampaIA e novos SaaS.

Arquitetura de marca:

```text
FM Tecnologia
├── FM Fiscal
├── Kordena
├── Iron
├── Vendedor IA
└── CampaIA
```

## Estratégia de transição

- O repositório original `faabio3131/kordena-fiscal-engine` permanece como baseline estável durante a transição.
- Este V2 evolui em paralelo até atingir universalização multiproduto e certificação completa.
- Após o cutover, o FM Fiscal passa a ser a única arquitetura fiscal ativa e o original fica apenas como histórico/auditoria.
- Nenhum novo produto deve criar dependência estrutural da identidade Kordena dentro do FM Fiscal.
- Nenhum segredo, PFX, CSC, token, dado real de cliente ou endpoint produtivo deve ser versionado.

## Identidade técnica

- Produto: **FM Fiscal**
- Núcleo: **FM Fiscal Core**
- Fronteira de integração: **FM Fiscal Bridge**
- Marca institucional: **FM Tecnologia**
- Namespace Python legado durante a transição: `kordena_fiscal`

O namespace legado é preservado temporariamente por compatibilidade e rastreabilidade do baseline. Novos contratos públicos e nomenclaturas arquiteturais não devem adotar Kordena como identidade do produto. A migração de namespace será tratada de forma compatível e governada, sem renomeação em massa que quebre consumidores.

## Identidade visual

A identidade oficial segue o conceito **Fluxo Fiscal Contínuo**: precisão, movimento de dados, reconciliação e continuidade operacional. A especificação está em `docs/brand/FM_FISCAL_BRAND_SYSTEM.md`.

## Baseline de origem

Fonte certificada: `faabio3131/kordena-fiscal-engine`

Baseline técnico congelado: `b336def47ad4f5188307102203f4e04b98406014` — FISC-00 a FISC-19 concluídos.

## Governança

A execução do V2 é controlada pelo Plano Mestre e pelo tracker em `docs/`.
