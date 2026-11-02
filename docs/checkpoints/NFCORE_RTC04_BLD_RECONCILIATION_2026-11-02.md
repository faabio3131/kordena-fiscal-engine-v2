# RTC-04 e BUILD — reconciliação incremental de 02/11/2026

## Fonte de verdade auditada
- Repositório `faabio3131/nf-core-v001`; `main` base desta entrega: `2e388071af68c63d63cdbf258b58c7fe4113f7d5`.
- RTC-04 B1 PR #310, B2 PR #311 e B3 PR #312 **MERGED**. CI/Governança pós-B3: workflows 41384501601 e 41384501576 SUCCESS.
- Portal SVRS https://dfe-portal.svrs.rs.gov.br/NFe/Documentos lista NT 2025.002 v1.53, publicada em 30/10/2026. A listagem federal consultada https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=04BIflQt1aY%3D ainda apresentava v1.52. Tratar essa diferença de publicação/listagem como metadados divergentes, não como permissão de usar fórmula.
- `config/rtc/official-baseline-2026-10-30.json` já registra v1.53 **somente como referência**, com `REFERENCE_ONLY_NOT_PRODUCTION_APPROVED`, sem hash original, vigência pinada, XSD e regras de rounding homologadas. Nenhuma nova alíquota ou regra calculável foi inferida.

## Delta controlado nesta PR
Teste direcionado exige que a referência publicada à NT não contenha `sha256`/vigência implícita, não seja um `rate_table` e mantenha explicitamente pendentes os checksums de XSD e fórmulas. **Não altera engine, catálogo, cálculo, emissão, API, schema, Contabo ou production.**

## BUILD — anti-retrabalho
- `docs/NFCORE_V1_BUILD_INTEGRATION_LEDGER.md`: BLD-00/01/02 DONE **internamente**; preservar os módulos integrados, não reconstruir.
- BLD-03: `IN_PROGRESS`, PRs #260/#279 já integradas; restante é a comprovação integral de jornada e liberação comercial, não a criação de segundo formulário trial. Verificar PR #299 (decisão de preço/trial), PR #298 (trial público/Command) antes de implementação.
- BLD-04: `PENDING` no ledger histórico embora #281 já tenha sido integrada; verificar diff da PR #297 de endurecimento de entrada comercial antes de duplicar proteção. Não concluir sem E2E HTTP assinado→inbox→entitlement→claim com isolamento PostgreSQL.
- BLD-05/06: pendentes de contrato fiscal neutro e teste Web/API/DB/Worker; usar executores existentes e não inventar provider/SEFAZ.
- BLD-07/08: site externo e aceite Web operacionais pendentes; nenhuma prova de CI local equivale a revisão publicada.
- PR #296 é `NO-GO` para promoção em `production`; PR #302 é preflight Contabo somente leitura. Ambas estão fora do escopo desta PR.

## Gates e limites
- A execução de CI/Governança desta PR e sua revisão do diff devem ocorrer antes de qualquer merge.
- O B3 continua `authoritative=False`. RTC-04 global permanece `IMPLEMENTED_PARTIAL`.
- Não há autorização para deploy, secrets reais, migrations, pagamento, emissão, mudança de `production` ou homologação oficial.
- Próximo delta elegível: obter/verificar conteúdo integral da NT 1.53 e XSD por SHA e vigência e definir golden cases por célula, **ou**, independentemente, reconciliar BLD-03/04 nas PRs existentes sem recriar suas capacidades.
