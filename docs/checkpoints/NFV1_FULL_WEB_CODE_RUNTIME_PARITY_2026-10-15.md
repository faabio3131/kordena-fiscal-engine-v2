# FM NFCORE V1 — Auditoria de paridade integral: planejamento × código × Web publicada
Data: 2026-10-15. Auditoria interna de construção, NÃO avaliação de homologação fiscal externa.

## Fontes e identidade de revisão
- Planejamento: `docs/NFCORE_V1_COMPLETION_MASTER_EXECUTION_SCHEDULE_2026-10-05.md` (P02 superfícies; P03 comercial; P04 worker; P12 matrizes funcionais), ledger e `AGENTS.md`.
- Código: `main` SHA `4f7d520ef66831edb56d8d68c60ca24cc17b51f4` (Portal `portal/app.js`; API `runtime/api.py`, `web/app.py`; composição `runtime/composition.py`; `web/portal_runtime.py`, `web/portal_api.py`).
- Railway `FM NFCORE Staging`, ambiente interno tecnicamente chamado `production`: API, Portal, Worker tiveram deployments SUCCESS no SHA acima; status online.
- Leituras GET externas da instância sincronizada: `https://nfcore-api-production.up.railway.app/runtime/profile`; `/health/ready`; `https://nfcore-portal-production.up.railway.app/v1/commercial/offer` e homepage.
- Limite: não foi usado login de conta autorizada. Portanto, superfície autenticada, mutações e E2E de negócio **ainda precisam ser executados** em ambiente de teste. Os resultados abaixo são lastreados em código + perfil real, sem inferir sucesso funcional de um menu.

## Fatos do runtime REAL (perfil publicado)
- `environment=staging`, `persistence_backend=postgres`, `secret_backend_profile=external`, `https_required=true`.
- Configurados (`true`): `human_identity`, `portal_executor`, `bridge_security`, `bridge_executor`, `portal_fiscal_operation_executor`, `password_recovery`, `password_reset_delivery`, `commercial_activation`, `pricing_admin`, `commercial_release_admin`, `canonical_commercial_persistence`, `commercial_fulfillment`, `commercial_provisioning`, `commercial_activation_delivery` e `commercial_delivery_path_ready`.
- `fiscal_operation_handlers_configured=[]`, `bridge_workload_identity_configured=false`, `fiscal_provider_transport_real_configured=false`, `fiscal_external_secret_client_configured=false`, `fiscal_signer_configured=false`. **Executor fiscal existe mas nenhuma operação está executável neste bootstrap**; não construir novo motor.
- `pricing_catalog_published=false`; `commercial_release_status=unavailable`; `commercial_checkout_provider_configured=null`, `commercial_checkout_processing_configured=false`, `commercial_first_party_acquisition_configured=false`, `commercial_trial_configured=false`, `cakto_checkout_admin_configured=false`, `command_webhook_configured=false`, `cakto_webhook_configured=false`. Oferta pública confirmou `unpriced`, `unavailable`, `unconfigured`, `purchase_enabled=false`, `trial_enabled=false`.
- `/health/ready` retornou `ready`. Esse gate é de infraestrutura/composição básica e **não prova paridade de jornadas de negócio**.

## Matriz de paridade: todas as áreas P02/P12
| Área prevista | Código/domínio | Web/rota interna | Runtime atual | Diagnóstico / próxima prova |
| --- | --- | --- | --- | --- |
| Login, sessão, RBAC/tenant | Implementado em `web/human_auth.py`, `web/portal_api.py` e runtime | API, Portal presentes | `human_identity=true`; negativas 401 previamente verificadas | E2E autenticado com perfis e unidades; não inserir credenciais em evidência |
| Visão geral e saúde | Implementados | Menu, `/v1/portal/bootstrap`, `/runtime/profile` | Bootstrap de Portal configurado | E2E e comparação de projeções reais |
| Documentos/consulta/archive | Implementações fiscais duráveis e Portal | Menu, `/surfaces/documents` | API/Portal disponíveis; handler externo ausente | Leitura autenticada/empty states, dados persistidos e contrato |
| Emissão fiscal | `CanonicalFiscalOperationPath`, `CanonicalPortalOperationExecutor`, operações no Portal | `issueFiscalDocument` exige `DOCUMENT_ISSUE` | **`fiscal_operation_handlers_configured=[]`** | BLOQUEIO_INTERNO_DE_WIRING: auditar registro de handlers; conectar adapters de desenvolvimento seguros, sem simular operação real como oficial |
| Consulta/cancelamento fiscal | Operações e permissões `DOCUMENT_QUERY`, `DOCUMENT_CANCEL` | Operações Portal/Bridge | Nenhum handler fiscal | Testar idempotência e fluxo com adapter de teste interno |
| Inutilização | `inutilizeFiscalRange` + `DOCUMENT_INUTILIZE` | Menu e rota governada | Nenhum handler fiscal | Conectar somente handler canônico, sem nova regra |
| Erros e rejeições fiscais | Projeções e estados de documentos/outbox | `/surfaces/errors` | Dados internos podem ser consultáveis, provedor real desligado | E2E com eventos sintéticos e políticas reais |
| Reconciliação fiscal | `FiscalReconciliationEngine`, superfície e operação `RECONCILIATION_EXECUTE` | Menu e API | Handler fiscal externo ausente | Provar leitura e reconciliação sintética por contrato |
| Capacidades/prontidão | `capability_readiness`, `/surfaces/capabilities` | Menu, Portal | Executor configurado, provider real false | Diferenciar capacidade construída de integração externa |
| Onboarding/empresas/unidades/ambientes | `DurableHumanPortalExecutor`, Control Plane | Menu/Portal | DB + executor true | Jornada autenticada de configuração sem alterar escopo externo |
| Certificados/configuração | `CONFIGURATION_WRITE`, `CERTIFICATE_MANAGE` | Menu, rotas governadas | Referências persistentes; nenhum signer fiscal real | Testar cadastro sintético e bloqueio sem segredo |
| Providers/Webhooks/Integrações/Settings | Control Plane, políticas e adapters existentes | Menu/Portal, `INTEGRATION_MANAGE` | Receivers comerciais não configurados | Configuração persistente e RBAC; não duplicar provedor |
| Usuários e papéis | `HumanAdministrationService`, `USER_MANAGE` | Menu/Portal | Identity configurada; composição injeta administração | E2E OWNER/ADMIN/OPERATOR/AUDITOR/BILLING, isolamento |
| Uso, billing, planos | Persistência e `CommercialPortalReadService` | Menu/Portal, `BILLING_READ` | Persistência/leitor comercial configurados | Validar leitura real com dados sintéticos |
| Suporte/auditoria | Projeções + `AUDIT_READ` | Menu/Portal | Código integrado | E2E read-only por papel |
| Catálogo de preços | Pricing admin e tela | Rota de admin presente | **Catálogo não publicado** | Configuração interna sintética governada, sem decidir preço real |
| Liberação comercial | Estado/release admin existente | Rota de admin presente | **Release indisponível** | Fluxo de configuração interna e prova de bloqueio/versão |
| Checkout e canais de venda | Projetor, binding e adapter Cakto existentes | UI e router condicional | **Provider null, processamento false, Cakto admin false** | Auditar configuração do provider e wiring, não reconstruir checkout |
| Compra/fulfillment/assinatura | `CommercialFulfillmentService` e persistência | Entradas comerciais condicionais | Fulfillment/provisioning true; **ingresso aquisição false** | Conectar ingresso de teste interno; evento validado→commit→portal |
| Trial | `GovernedTrialService`, `create_commercial_trial_router` | Rota condicional | **trial false** | Verificar security/delivery inject; não inventar trial existente em runtime |
| Ativação/recovery | `CommercialCustomerActivationService` e envio recovery | Login e recuperação | Serviços configurados true | Testar jornada sintética de ponta a ponta; `ACTIVE` só após commit |
| Worker/outbox/transportes | Worker + outbox/handlers, container separado | Sem menu próprio obrigatório | Railway Worker online; sem prova de processamento real | Testar ciclo interno, filas/retries/DLQ com dados sintéticos |

## Ordem de correção orientada por entrega Web (não criar nova arquitetura)
1. **Testar paridade autenticada automatizada** da instância publicada: bootstrap/available_surfaces, permissões, superfície→API→persistência e estados de bloqueio. Exige sessão de testes autorizada, sem segredos nos artefatos.
2. **Wiring fiscal de desenvolvimento:** rastrear como `fiscal_operation_handlers` chega de `runtime/api.py` à composição; confirmar ausência em entrypoint publicado. Construir apenas adaptador de simulação interna quando já previsto e seguro, explicitamente rotulado, sem produzir efeitos fiscais oficiais.
3. **Wiring comercial:** reutilizar `CommercialFulfillmentService`, checkout projector, lifecycle e trial. Auditar por que `create_runtime_app` recebe `None` para security/receiver/checkout e gerar composição do mesmo sistema com configuração de desenvolvimento apropriada.
4. **Configuração funcional sintética:** completar catálogo/release/checkout internos quando produto/valores já aprovados; não inventar decisões comerciais reais.
5. **Regressão interna:** Pytest, PostgreSQL, RBAC/tenant, Node tests, Playwright/E2E; revisão única CI, publicação coordenada e reteste real da Web após aprovação.

## CONTROLES
- Esta auditoria é diagnóstico do software em construção, não homologação externa. Nenhuma homologação externa é bloqueio para construir funcionalidades locais ou passar testes internos.
- Não inventar que `fiscal_provider_transport_real_configured=false` exige imediatamente serviços oficiais para permitir simulação/desenvolvimento. Também não publicar handlers de simulação como se fossem oficiais.
- Sem merge, deploy, mudanças de secrets, migrations, compra real ou ativação fiscal por esta PR. PR #188 é outra tarefa e continua Draft.
- **Critério de aceite da auditoria:** matriz rastreável e gaps classificados. **Critério da entrega Web completa:** cada linha provada por testes internos e navegação autenticada na revisão publicada.
