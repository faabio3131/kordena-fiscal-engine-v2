# NFCore V1 — Matriz de composição API × Portal × Worker (auditoria CURRENT)

**Data:** 2026-10-15. **Main lida:** `4f7d520ef66831edb56d8d68c60ca24cc17b51f4`. Registro documental na PR #188, que permanece DRAFT; **nenhum deploy, merge ou migration**. Inspeção de código não comprova staging.

## 1. Entradas executadas

| Processo | Imagem / entrypoint real | Autoridades e condições | Consequência se ausente |
|---|---|---|---|
| API | `Dockerfile.api` → `uvicorn kordena_fiscal.runtime.api:app` | `RuntimeApi` exige PostgreSQL/configuração; `build_postgres_runtime_composition` conecta identidade, executor portal, comercial e fiscal. `runtime.api` monta a `web.app.create_app` com colaboradores opcionais | DB ou composição falha: readiness negativa; rotas condicionais não são registradas |
| Portal | `Dockerfile.portal` → `serve_portal.py` na pasta `portal/` | `portal/app.js` desenha menu e consulta `/v1/portal/bootstrap`, `/v1/portal/surfaces/{id}` e operações | HTML/menu pode existir com funcionalidade indisponível por RBAC ou pela API |
| Worker | `Dockerfile.worker` → `python -m kordena_fiscal.runtime.worker_main` | Worker exige PostgreSQL, `staging_gsm_handler_factory` e registry de handlers explicitamente configurado; `build_production_worker_runtime` usa outbox/UOW/observador existentes | Sem identidade/segredos/handlers válidos: falha fechada, sem consumir jobs |

## 2. Superfícies e contratos (código, não prova operacional)

Todos os módulos abaixo reutilizam a única identidade de sessão autorizada; `web/portal_api.py` aplica `_SURFACE_PERMISSIONS` e/ou `_OPERATION_PERMISSIONS`, enquanto `web/portal_runtime.py` resolve os dados pela UOW. Disponibilidade é filtrada conforme permissões e colaboradores reais.

| Superfícies do menu Portal | Permissão principal | Autoridade/condição de wiring | Status auditado |
|---|---|---|---|
| Visão geral; erros; capabilities; suporte | `PORTAL_READ` | `DurableHumanPortalExecutor` e suas projeções | Código integrado; staging não provado |
| Documentos; emissões; reconciliação | `DOCUMENT_QUERY` | `DurableHumanPortalExecutor`, estados fiscais duráveis; reconciliação executável requer `RECONCILIATION_EXECUTE` | Código integrado; execução real não provada |
| Inutilização | `DOCUMENT_INUTILIZE` | Execução governada com handler fiscal efetivamente configurado | Condicional; provider real não provado |
| Onboarding; empresas; unidades; ambientes; configurações | `CONFIGURATION_WRITE` | Control Plane durável e escopo de unidade | Código integrado; staging não provado |
| Certificados | `CERTIFICATE_MANAGE` | Somente referências governadas; segredo fora da UI | Código integrado; binding real não provado |
| Provedores; webhooks; integrações | `INTEGRATION_MANAGE` | Adapters/políticas/autorização de egress e configuração de transport | Código integrado; provider e egress real não provados |
| Usuários | `USER_MANAGE` | `user_administration` injetado, ou fica indisponível | Condicional; composição em código, staging não provado |
| Uso; billing; planos | `BILLING_READ` | `commercial_reader` opcional na composição | Condicional; dados comerciais reais não provados |
| Auditoria | `AUDIT_READ` | UOW e projeção no escopo autorizado | Código integrado; staging não provado |
| Aprovação de egress | Autoridade `platform_admin` e rota específica | Disponível somente à administração da plataforma; não permitir autoaprovação de tenant | Condicional |
| Catálogo comercial; liberação comercial; canais checkout | Autoridade de administração da plataforma, rotas especializadas | `pricing_administration`, `commercial_release_administration`, `cakto_checkout_administration` opcionais; checkout também depende de ingresso/processing e prontidão | Condicional; venda real não provada |

## 3. Operações protegidas

`portal_api._OPERATION_PERMISSIONS`: `onboardUnit/configureSettings` → CONFIGURATION_WRITE; `configureCertificates` → CERTIFICATE_MANAGE; `configureProviders/configureWebhooks/configureIntegrations` → INTEGRATION_MANAGE; `createUser/updateUser` → USER_MANAGE; `issueFiscalDocument` → DOCUMENT_ISSUE; `queryFiscalDocument` → DOCUMENT_QUERY; `cancelFiscalDocument` → DOCUMENT_CANCEL; `inutilizeFiscalRange` → DOCUMENT_INUTILIZE; `reconcileFiscalOperation` → RECONCILIATION_EXECUTE. O backend reconstrói contexto de sessão/tenant/unidade; o frontend **não** autoriza operações.

`DurableHumanPortalExecutor.snapshot` sinaliza `fiscal_operation_executor_configured`, `fiscal_operations_configured`, `configured_fiscal_operations` e `available_surfaces`. Essas chaves são verificações prioritárias contra o runtime real, não provas de implementação fiscal por si.

## 4. Lacunas objetivas e ações

1. **Verificar deployment CURRENT:** confirmar imagem/revisão única e estado de API/Worker/Portal na Railway; comparar HEAD real, PostgreSQL, migrations, GSM/credenciais do Worker e dependências de checkout. Não inferir disponibilidade apenas de GitHub.
2. **Verificar boot real:** consultar health/readiness e configuração sanitizada; `RuntimeApi` pode deixar a composição indisponível se a base ou schemas falharem. Não usar cookies, segredos nem dados pessoais em evidências.
3. **Executar roteiro de paridade:** conta autorizada de homologação, permissão e unidade → bootstrap → cada superfície → ação → persistência → refresh → replay/negações → E2E. Sem navegador e ambiente reais acessados nesta auditoria.
4. **Classificar cada gap:** `CONFIGURAÇÃO_WIRING`, `CONTRATO_API`, `RBAC_SCOPE`, `ERRO_IMPLEMENTAÇÃO`, `BLOQUEIO_EXTERNO`, `EVIDÊNCIA_AUSENTE`; construir novo domínio só se comprovadamente ausente.
5. **Não confundir marcadores:** `main` e CI verde comprovam integração de código, não experiência Web de cliente. P09-T02 continua com gates próprios na PR #188; P05/staging continua separado.

## 5. Decisão

**Reutilizar** as superfícies, handlers e a persistência existentes; **não criar segundo frontend, autenticação, tenant authority, backend nem regra fiscal**. Próximo trabalho operacional é confrontar esta matriz com a configuração e o runtime real, com autorização específica antes de qualquer deploy/migration/segredo. Este relatório é evidência de auditoria estática, não homologação.
