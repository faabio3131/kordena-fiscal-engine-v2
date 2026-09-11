# FM Fiscal Core V2

Repositório privado de evolução do `kordena-fiscal-engine` para um produto fiscal independente e multiproduto da FM Tecnologia.

## Estratégia de transição

- O repositório original permanece como baseline estável para o Kordena durante a transição.
- Este V2 evolui em paralelo até atingir equivalência funcional + universalização multiproduto.
- Não haverá dois motores ativos permanentes: após certificação e migração, o V2 passa a ser a única arquitetura fiscal ativa e o original é preservado apenas como histórico/auditoria.
- Nenhum segredo, PFX, CSC, token, dado real de cliente ou endpoint produtivo deve ser versionado.

## Baseline de origem

Fonte certificada: `faabio3131/kordena-fiscal-engine`

Baseline técnico congelado: `b336def47ad4f5188307102203f4e04b98406014` — FISC-00 a FISC-19 concluídos.

## Governança

A execução do V2 é controlada pelo Plano Mestre e pelo tracker em `docs/`.
