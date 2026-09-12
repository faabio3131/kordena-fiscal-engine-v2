# V2-09 — Modularização de Verticais

Status: **CONCLUÍDO E CERTIFICADO**  
Branch: `v2/vertical-modularization`  
PR: **#10 Draft**  
Base certificada: `v2/events-webhooks-inbox-outbox` @ `cc30ec3bddd2f61595c0d869f710e22d83e24743`  
Dependência: V2-08 concluída e certificada.

## Objetivo

Preservar inteligência fiscal setorial sem acoplar o FM Fiscal Core a restaurante ou a qualquer produto/vertical específica.

## Arquitetura implementada

Foi criada a superfície host-neutral `kordena_fiscal.verticals` com contrato explícito de módulo vertical, descriptor imutável e registry fail-closed. O Core não infere vertical por host, produto, payload ou nome: módulos precisam ser registrados e capabilities precisam ser declaradas.

`VerticalModuleRegistry` fornece registro, resolução explícita, exigência de capability e consulta dos módulos que declaram determinada capability. Identidades duplicadas falham fechado e uma vertical/capability ausente gera erro explícito.

## Restaurante como módulo vertical

A implementação normativa antes localizada em `kordena_fiscal.tax.restaurant` foi movida para `kordena_fiscal.verticals.restaurant`, que agora contém o classificador, fatos, decisões e `RestaurantVerticalModule`.

O módulo declara explicitamente as capabilities:

- `tax.restaurant.supply-classification`;
- `tax.restaurant.base-adjustments`.

Nenhuma regra tributária do restaurante foi alterada. `kordena_fiscal.tax.restaurant` passou a ser uma camada fina de compatibilidade, reexportando os mesmos símbolos da nova implementação. A suíte legada `tests/tax/test_restaurant_classifier.py` continuou integralmente verde, preservando a regressão do Kordena e consumidores existentes.

## Verticais neutras

Foram adicionados módulos declarativos sem dependência do classificador de restaurante:

- `service`: `operation.service`;
- `fitness`: `operation.service`, `operation.membership`, `operation.recurring`;
- `saas`: `operation.service`, `operation.subscription`, `operation.recurring`.

Esses módulos descrevem apenas semântica de operação. Eles não concedem readiness fiscal, documento suportado, alíquota, regime ou autorização. Essas autoridades continuam pertencendo às camadas comuns já certificadas do Fiscal Core.

Um teste em processo Python novo prova que importar `kordena_fiscal.verticals` e usar service/fitness/SaaS não carrega `kordena_fiscal.verticals.restaurant` nem `kordena_fiscal.tax.restaurant`.

## Extensão futura sem fork do Core

A suíte registra uma vertical sintética `future-commerce` apenas através do contrato `VerticalModuleDescriptor` + `VerticalModuleRegistry`, sem alteração no Core. Isso prova o ponto de extensão exigido pelo Plano Mestre para futuras verticais.

## Testes e gate

Foram adicionados 9 testes dirigidos para:

- fail-closed de vertical desconhecida;
- rejeição de registro duplicado;
- resolução explícita por capability;
- neutralidade de service/fitness/SaaS;
- ausência de import eager do restaurante;
- extensão futura sem fork;
- registro e uso explícito do módulo restaurante;
- identidade entre a superfície legada e a implementação vertical;
- validação fail-closed dos descriptors.

Gate funcional definitivo:

- SHA: `88071fd557199ffd6848312ea5559b0cba415ee1`;
- Actions run: `34668430831` — **SUCCESS**;
- Install: **PASS**;
- Ruff: **PASS**;
- Mypy strict: **PASS — 71 source files sem issues**;
- Pytest completo: **346 PASS em 1.35s**;
- baseline V2-08: 337 testes; incremento líquido V2-09: **+9 testes**.

## Auditoria do diff

Compare V2-08 `cc30ec3bddd2f61595c0d869f710e22d83e24743` -> gate V2-09 `88071fd557199ffd6848312ea5559b0cba415ee1`:

- **9 commits à frente, 0 atrás**;
- mudanças limitadas ao CI temporário, documentação da fase, snapshot do tracker, nova superfície `verticals`, shim de compatibilidade do restaurante e testes V2-09;
- nenhum arquivo OpenAPI, AsyncAPI ou JSON Schema foi alterado;
- nenhuma persistência, migration, segurança, webhook, provider, infraestrutura, segredo real ou deploy foi introduzido.

## Riscos residuais e limites

- o registry é uma primitive de Core e sua composição/configuração operacional ainda é responsabilidade de camadas superiores;
- módulos service/fitness/SaaS são declarações de semântica de operação, não Product Contract Packs completos;
- a camada `kordena_fiscal.tax.restaurant` permanece por compatibilidade; qualquer depreciação futura deve ser governada e versionada;
- mappings específicos de Kordena, Iron Fit, Vendedor IA e CampaIA pertencem à V2-10 e não foram acoplados ao Core nesta fase;
- nenhum adapter de produção, homologação externa, merge, deploy, promoção ou cutover foi realizado.

## Governança e decisão

PR #10 permanece Draft. A fase está tecnicamente concluída após o gate completo e a auditoria do diff. O CI temporário de PR deve ser restaurado para `workflow_dispatch` após a certificação documental final.

**V2-09 CONCLUÍDO E CERTIFICADO. V2-10 — Product Contract Packs — está LIBERADA / PENDENTE.**
