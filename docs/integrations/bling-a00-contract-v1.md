# NFCore / Bling — contrato de integração A-00 v1

**Emissão:** 2026-11-09. **Owner:** Agente A (plataforma, persistência, ingress, OAuth e worker).
**Baseline compartilhado:** `main@46784694a09a18f4402817f84c1a534e31b2123a`.
**Consumidor:** Agente B (reconciliação, painel, ampliação fiscal e E2E).
**Estado:** CONTRACT_CANDIDATE. Não representa código multi-tenant ou OAuth já concluído; requer PR/CI e revisão cruzada.

## Invariantes (não negociáveis)

1. Um `installation_id` opaco e persistente representa o vínculo OAuth/webhook de UMA empresa Bling com escopo `host_namespace=bling`, tenant, unidade e ambiente fiscal; nunca é identidade fiscal autorizadora por si só.
2. O escopo fiscal é exclusivamente o resultado de `FiscalApplicationService.resolve_scope(HostScope(HostNamespace("bling"), external_tenant_id, external_unit_id), environment=...)`; IDs oriundos de headers/JSON/callback não conferem autorização. Revisão Web exige sessão canônica + `integration.manage` e `document.issue`/CSRF para mutações.
3. As credenciais são referenciadas por identificador imutável de segredo e guardadas criptografadas com rotação/ciclo de vida. Access token, refresh token, secret de webhook, códigos OAuth, corpos brutos sigilosos e A1 nunca aparecem em API, logs, telemetria ou frontend.
4. O webhook público identifica instalação por rota `/webhooks/bling/installations/{installation_id}` e valida HMAC do corpo exato com a chave desta instalação ANTES de ler a identidade da empresa. CompanyId do payload deve coincidir com o binding validado; entradas sem correspondência retornam 401/404 genérico, sem enfileirar. A rota legada `/webhooks/bling` só existe no modo legado single-tenant até a migração controlada; é desativada ou rejeitada quando ambígua.
5. Estados duráveis: `not_configured`, `connected`, `needs_reauth`, `paused`, `error`. Apenas `connected` permite coleta/alteração de status. Falta de A1 bloqueia emissão, sem marcar instalação como homologada.
6. OAuth usa Authorization Code e state anti-CSRF de uso único com expiração, redirect URI HTTPS exato, scopes explícitos, validação de empresa OAuth e CAS/mutex transacional no refresh. 401 irreversível ou refresh inválido => `needs_reauth` fail-closed; 429/5xx => retry com backoff, sem token de outra instalação.
7. Worker utiliza a outbox fiscal canônica e seleciona explicitamente partição (`installation_id`, tenant, unidade, ambiente), com lease, idempotência, DLQ, recuperação e sem segundo executor fiscal. Resultado incerto exige `reconcileFiscalOperation`; jamais emitir duplicado. Emissão só em homologação até autorização humana específica.
8. API de listagem sanitizada e paginada sempre deriva escopo da sessão; cursor opaco é vinculado à mesma instalação/escopo. O Agent B não cria segunda leitura persistente ou segunda fila.
9. Deploy Worker é opt-in na Contabo, sem ativação automática, sem credenciais reais, sem migração produtiva e sem alterações aos demais produtos.

## Contratos para o Agente B (interfaces A-owned)

**`BlingInstallationView`:** installation_id, company_id, tenant_id, unit_id, environment, state, health_code, credential_status, updated_at (ISO UTC), revision. Nunca inclui segredo, token, base URL mutável ou dados de outro tenant.

**`BlingOrderPage`:** rows sanitizadas (order_id, state, document_id, review_required, retryable, updated_at), next_cursor, limit <= 100. Leitura autenticada e restrita ao escopo da instalação/portal.

**`BlingProviderOrderPage`:** busca com query/cursor/limite e orçamento de timeouts/backpressure; autorização OAuth resolvida apenas pelo A. Somente como ferramenta de reconciliação, nunca fonte de decisões fiscais.

**`BlingRecoveryResult`:** operation_id, installation_id, order_id, outcome (`already_recorded`, `queued`, `requires_review`, `blocked`), correlation_id. Não dispara emissão incerta nem sobrescreve documentos.

**Erros UI/HTTP:** `BLING_INSTALLATION_NOT_FOUND` (404 sem vazamento), `BLING_SCOPE_FORBIDDEN` (403), `BLING_NEEDS_REAUTH` (409), `BLING_PAUSED` (409), `BLING_RATE_LIMITED` (429), `BLING_NOT_CONFIGURED` (503), `BLING_REVIEW_CONFLICT` (409), `BLING_RECOVERY_REQUIRED` (409), `BLING_TEMPORARILY_UNAVAILABLE` (503). O HTTP e sua semântica são versionados; o B não converte erro em sucesso.

**Router do B:** `build_bling_operations_router(identity, installation_reader, order_reader, recovery_port) -> APIRouter`. O A inclui o router em `runtime/api.py` somente após testes de `_authenticated`/`_authorized`/`_csrf`. O B possui o código interno do router. Contratos Python de portas estão em `src/kordena_fiscal/integrations/bling_contracts.py`.

## Ownership de arquivos / concorrência

A: `runtime/bling_ingress.py`, `runtime/bling_worker.py`, `runtime/worker_main.py`, `runtime/api.py` (composição), `connectors/bling_api.py`, `connectors/bling_webhook.py`, módulos novos de instalação, OAuth, credenciais e persistência, testes correspondentes. `application/bling_orders.py` PROTEGIDO (somente A com aviso explícito ao B).
B: `portal/app.js` e assets Web, sua rota `runtime/bling_operations.py`, reconciliação de pedidos, matriz fiscal, XSD, testes do painel. Não alterar arquivos A, nem `AGENTS.md`, nem produção. Qualquer alteração em contratos implica versão nova, revisão A+B e gate.

## Marcas de sincronização

- G0: PR A-00 publicada; B pode iniciar trabalho apenas com contrato versionado, não considerar endpoints existentes.
- G1: A-01 DB + ingress funcionais; B pode executar testes de leitura via mock do contrato.
- G2: A-02 OAuth governado e Worker multi-instalação; B conecta recuperação e UI.
- G3: CI A verde e CI B verde no mesmo merge base; um responsável revisa conflito, integra em main via PR e reconcilia release com production, preservando checkout Cakto.
- G4: credenciais/instalações externas e A1 reais somente após autorização separada; não confundir com DONE interno.

## Matriz mínima de aceitação A

2 tenants × 2 unidades × >= 2 instalações, replay/webhook malicioso, OAuth state e refresh concorrente/401/429/revoked, worker off-scope, crash/restart, emissão incerta, erro de secret store e exaustão de rate-limit. SQLite local + PostgreSQL real CI, lint/mypy, CI, migrações e container opt-in. Qualquer falha é NO_GO. Nenhuma etapa de criação de código autoriza merge/deploy por si só.
