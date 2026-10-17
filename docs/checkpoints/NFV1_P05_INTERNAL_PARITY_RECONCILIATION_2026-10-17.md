# NFV1-P05 — Reconciliação de API, Worker e Portal / construção interna

**Data:** 2026-10-17  
**Escopo:** auditoria CURRENT, impacto de revisão, proteção do esquema comercial já migrado e gates internos. **Não realiza deploy, merge, migração, mudança de credenciais, homologação externa nem promoção de checkbox.** Este checkpoint complementa a PR #204 e os registros da issue #181.

## Fontes efetivamente consultadas

1. GitHub branch `main`: `976ae4e223accd603af710d083b18ca47b95b614` (merge #209); `FM NFCORE V1 CI #1007 SUCCESS`; `NFCore Plan Governance #428 SUCCESS` no mesmo SHA.
2. Railway projeto `b84b290d-f3b4-46a1-9023-0b761cb96b0d`, ambiente `c9878b9b-62b2-4a97-b8ba-743c8a3e99ec` (nome interno `production`, projeto **staging**, NÃO produto em produção comercial).
3. Código em `C:\nfcore-p05-deploy-no-migration` no HEAD exato da `main`. A alteração local preexistente de `.github/PULL_REQUEST_TEMPLATE.md` **não foi tocada**.
4. Cronograma e ledger canônicos; fontes e testes internos da `main`. Nenhuma leitura de valor de segredo.

## Revisões implantadas e discrepância

| Serviço | SHA implantado (fonte) | State | Comparação com main |
| --- | --- | --- | --- |
| nfcore-api | `e4ffd584c4bc66632e80d1ab1448cdb67cd914ea` | ONLINE 1/1, SUCCESS | Atrasado |
| nfcore-worker | `e4ffd584c4bc66632e80d1ab1448cdb67cd914ea` | ONLINE 1/1, SUCCESS | Atrasado |
| nfcore-portal | `2f3689838cfbec1c6d2ffac614cb0eb364d91633` | ONLINE 1/1, SUCCESS | Atrasado; SHA distinto |
| PostgreSQL | Serviço ONLINE 1/1 | ONLINE | Fiscal 1..17, Cakto 1..2 (provas SQL na issue #181) |

Há zero staged changes na Railway. O `preDeployCommand` da API está vazio, conforme configuração efetiva. A API/Worker no SHA implantado divergem da main em **21 arquivos, 952 adições, 11 exclusões**, incluindo `runtime/api.py`, `worker_composition.py`, `worker_staging_gsm_bootstrap.py`, `issuance/nfce.py` e alertas internos P09-T03. O Portal diverge da main em 53 arquivos do repositório, mas **nenhum arquivo sob `portal/` difere** entre `2f36898...` e main. Não confundir ausência de alteração visual com paridade de contratos do backend ou SHA de release.

**Current → Target:** três serviços em mesma revisão imutável *quando houver deploy especificamente aprovado*, com smoke interno e contratos reconciliados. Nenhum deploy foi autorizado neste checkpoint.

## Matriz de construção de funcionalidades (sem duplicação)

| Eixo | O que o código CURRENT já possui | Lacuna / ação correta |
| --- | --- | --- |
| Autenticação e tenant/unidade | `build_postgres_runtime_composition` compõe `HumanIdentityService`, administração, session/recovery e `DurableHumanPortalExecutor`. Testes frontend de autoridade do backend e CSRF presentes. | Evidenciar jornadas autenticadas no release alinhado mais adiante, não criar segunda auth. |
| Fiscal Web | `CanonicalFiscalOperationPath`, `CanonicalBridgeSecurityBoundary` e `CanonicalPortalOperationExecutor` existentes. `queryArchiveReference` tem handler canônico. | Handlers oficiais de emissão/consulta/cancelamento dependem de adapters reais. Para desenvolvimento interno, simulação apenas isolada e identificada, nunca habilitada silenciosamente no staging. Não inventar homologação. |
| Comercial | Persistência canônica, provisioning, fulfillment, activation, trial, pricing/release e `CaktoCheckoutAdministrationService` existentes. Cakto schema 1..2 aplicado. | Ingressos e checkout são condicionais a dependencies de segurança/entrega/provedor. `command_secret_resolver` deve ser injetado pela autoridade segura. O canal de launch indicado no código atual é Command; não inferir que habilitar Cakto ou cadastrar preço sem decisão resolveria o checkout. |
| Worker/outbox | Worker 1/1 conectado; composição e GSM vinculados no staging; nova lógica de alertas já na main. | Avaliar delta da composição Worker/alertas antes do release alinhado; não repetir bootstrap GSM certificado. |
| Observabilidade | Métricas HTTP, fulfillment, authorization/rejection, provider error e alertas possuem código/alguns testes na main. | Não duplicar métricas; PR #201 de overflow de counter segue OPEN/DRAFT. P09-T01/T02 exigem evidências próprias antes de concluir. |
| Portal premium | `portal/` não mudou entre revisão do Portal e `main`. | Não redesenhar. PR #182 com mostrar senha está aberta: avaliar integração e gates específicos, sem duplicar. |

## Gates internos realmente executados nesta retomada

- `py -3 scripts/check_nfcore_plan.py`: **PASS**, 59 IDs, estado `EM EXECUCAO`, próxima pendência formal **NFV1-P05-T01**.
- `npm run test:frontend`: **PASS 14/14**, 0 fail. Abrange isolamento da autoridade de tenant/papel, CSRF/idempotência, sessão, recovery, catálogo e release comerciais, interface acessível.
- `test_p05_t01_railway_config_gate.py`: **PASS 11/11** quando executado isoladamente com `PYTHONPATH` do checkout correto.
- `test_p05_t01_schema_preflight.py`: **PASS** (10 casos; exit code 0) com `PYTHONPATH` do checkout correto.
- Execução ampla de pytest diretamente no Windows foi **NÃO CERTIFICADA**: inicialmente Python importava de outro checkout (`nfcore-t04-work`); com a importação corrigida, parte dos testes de API não coletou por ausência local de `google.cloud.secretmanager_v1` e testes Worker usam `os.O_NOFOLLOW`, primitiva POSIX ausente no Windows. Não alterar a proteção Linux nem apagar testes para obter verde local. CI GitHub da main continua SUCCESS; testes adicionais devem rodar em ambiente Linux/dependências instaladas.

## Regra de sequenciamento aprovada pelo dono

**Construção/integração interna primeiro; testes e homologações reais com terceiros ficam para fase final.** Isso não remove gates internos, segurança, RBAC, tenant isolation ou critérios finais de lançamento. Estados externos não são promovidos para DONE_CERTIFIED.

## Próximas ações, em ordem

1. Concluir o fechamento documental objetivo da P05-T01 com provas atuais (incluindo o schema Cakto já migrado); preservar histórico de backup e restore, sem repetição automática. Não mudar checkbox sem satisfazer o validador.
2. Congelar uma revisão candidata `main` após reconciliar mudanças de Worker/API e PRs pendentes, com teste interno em Linux e dependências completas. Não executar nem configurar deploy até autorização humana específica.
3. Identificar e implementar apenas deltas funcionais internos não cobertos pelas entregas existentes: configuração governada do runtime de desenvolvimento, adapters fiscais de desenvolvimento exclusivamente isolados quando previstos, ingressos comerciais internos assinados e caminhos do Portal sem bypass de autoridade.
4. Manter T03/T04 (smoke/E2E contra runtime publicado), T05 (rollback rehearsal), providers externos e Go/No-Go como pendências distintas, sem inventar homologação; executar os externos apenas na fase final aprovada.

**Classificação:** `API_WORKER_PORTAL_ONLINE`; `DEPLOYED_VERSION_DRIFT`; `CAKTO_SCHEMA_APPLIED_CONFIRMED`; `INTERNAL_GATES_PARTIAL_PASS`; `P05_T01_NOT_YET_CERTIFIED`; `EXTERNAL_HOMOLOGATION_DEFERRED`. Não publicar como comercialmente pronto.
