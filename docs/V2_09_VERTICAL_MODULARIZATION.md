# V2-09 — Modularização de Verticais

Status: **EM EXECUÇÃO**  
Branch: `v2/vertical-modularization`  
Base certificada: `v2/events-webhooks-inbox-outbox` @ `cc30ec3bddd2f61595c0d869f710e22d83e24743`  
Dependência: V2-08 concluída e certificada.

## Objetivo

Preservar inteligência fiscal setorial sem acoplar o FM Fiscal Core a restaurante ou a qualquer produto/vertical específica.

## Entregas vinculantes

- restaurante passa a existir como módulo/capability vertical explícita;
- serviço, fitness e SaaS operam sobre contratos genéricos sem importar ou depender do classificador de restaurante;
- novas verticais podem ser adicionadas por extensão/registro, sem fork do Core;
- compatibilidade pública e regressão do classificador de restaurante/Kordena devem permanecer verdes;
- o Core não fará inferência silenciosa de vertical: ativação e resolução de módulos são explícitas e fail-closed;
- nenhuma regra normativa de restaurante será copiada para módulos neutros.

## Estratégia de implementação

1. criar um contrato host-neutral de módulo vertical e registry explícito;
2. extrair a implementação normativa de restaurante para `kordena_fiscal.verticals.restaurant`;
3. manter `kordena_fiscal.tax.restaurant` como camada de compatibilidade para não quebrar consumidores existentes;
4. criar módulos declarativos neutros de `service`, `fitness` e `saas`, sem import do módulo restaurante;
5. provar extensibilidade com módulo sintético registrado em runtime sem alteração do Core;
6. executar regression completa, Ruff, Mypy strict e Pytest;
7. auditar o diff contra V2-08 e documentar riscos residuais.

## Governança

A PR da fase permanecerá Draft. Nenhum merge, deploy, promoção, segredo real, homologação externa ou cutover será executado automaticamente.
