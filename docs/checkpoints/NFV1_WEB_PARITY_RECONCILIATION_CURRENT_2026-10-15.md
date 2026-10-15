# NFCore V1 — Reconciliação de funcionalidades construídas vs. Web

Data: 2026-10-15. Auditoria de leitura da `main` em `4f7d520ef66831edb56d8d68c60ca24cc17b51f4`, registrada na branch da PR #188 somente como evidência de diagnóstico. **Não certifica staging nem substitui o cronograma.**

## Fatos confirmados por código CURRENT

| Área | Implementado no repositório | Conexão Web | Lacuna de prova |
| --- | --- | --- | --- |
| Portal visual | `portal/app.js` possui menu para documentos, emissões, inutilizações, erros, reconciliação, onboarding, empresas, unidades, ambientes, capacidades, certificados, provedores, usuários, webhooks, integração, uso, billing, planos e administração comercial | Navegação para `/v1/portal/surfaces/{surface_id}` | A presença do menu **não** prova rota ativa nem dados reais em staging |
| API Web | `src/kordena_fiscal/web/app.py::create_app` injeta `human_identity`, `portal_executor`, `pricing_administration`, `commercial_release_administration` e `cakto_checkout_administration` | `include_router` condicionado a componentes configurados | Verificar bootstrap/runtime efetivo de cada serviço na revisão publicada |
| Executor durável | `web/portal_runtime.py::DurablePortalExecutor` fornece `snapshot`, `surface` e fluxo de operações autorizadas | Superfícies dinâmicas em `available_surfaces`; usuário, billing e operação fiscal dependem de colaboradores configurados | Comparar disponibilidade/autoridade por tenant e unidade no staging |
| Fulfillment | `application/commercial_fulfillment.py::CommercialFulfillmentService.process` tem recibo idempotente, replay, mudanças em compra/contrato e commit | Necessita composição do ingresso comercial real | Não inferir compra executada de checkout visível ou de teste mock |
| Ativação | `application/commercial_activation.py::CommercialCustomerActivationService.provision/mark_active` persiste transições até `ACTIVE` | Necessita caminho real de identidade, recuperação e provisionamento | Ativação real requer transição canônica comprovada |
| Reconciliação comercial | `application/cakto_reconciliation.py::CaktoCanonicalCommercialBridgeService.reconcile` produz `drift` | Depende de ingresso/snapshot externo configurado | Não confundir com reconciliação fiscal nem declarar provider homologado |
| Reconciliação fiscal | `reconciliation/engine.py::FiscalReconciliationEngine.reconcile_operation` computa status/issues | Portal possui superfície `reconciliation` | Confirmar executor, persistência e jornada real |
| Observabilidade | `runtime/observability.py` e `runtime/commercial_observability.py` já oferecem instrumentos canônicos | PR #188 DRAFT amplia métricas internas | Não criar segundo mecanismo nem usar métrica como prova de integração Web |

## Classificação

- **REUTILIZAR:** domínio, fulfillment, ativação, reconciliações, navegação e executores já identificados.
- **INTEGRAR / RECONCILIAR:** composição real do bootstrap, dependências opcionais, autorização/tenant/unidade, APIs e superfícies visíveis.
- **TESTAR:** jornadas browser→API→aplicação→persistência→resultado; logs e saúde operacionais no staging CURRENT.
- **NÃO CONFIRMADO:** paridade Web no deployment ativo; configuração de serviços externos e homologações fiscais reais.
- **NÃO AUTORIZADO:** merge, deploy, migrations e segredos. Nenhum `100% pronto`.

## Próxima sequência executável

1. Auditar entrypoint e composição da API/Worker/portal no perfil de deploy e associar cada dependência a uma fonte de configuração.
2. Construir matriz por superfície com estados `código`, `API`, `RBAC/tenant`, `Web`, `E2E`, `staging`.
3. Distinguir conexão ausente, bug de contrato, bloqueio externo e funcionalidade realmente inexistente.
4. Corrigir apenas gaps comprovados por código; preservar PR #188/T02 e documentação canônica; obter autorização específica para deploy.
5. Fazer smoke/E2E com a mesma revisão da API, Portal e Worker, sem afirmar homologação externa não executada.
