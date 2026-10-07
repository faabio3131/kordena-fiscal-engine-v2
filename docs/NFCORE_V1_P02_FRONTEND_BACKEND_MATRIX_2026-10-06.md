# NFV1-P02-T01 — Matriz frontend × backend

Data: 2026-10-06. Produto: FM NFCORE V1.
Repository: `faabio3131/kordena-fiscal-engine-v2`.
Baseline auditado: `main@0e5be77267a800384d111c03e30705d95bdb0d28`.
CI de origem: FM NFCORE V1 CI #618 SUCCESS; NFCore Plan Governance #47 SUCCESS.
PRs abertas na entrada: zero. P0/P1 certificados; closeout P1: PR #114 mergeada.

## Evolução CURRENT T04 — 2026-10-07

Política T04 aprovada explicitamente pelo dono como conjunto: OWNER administra todos
os papéis do próprio tenant; ADMIN somente OPERATOR/AUDITOR/BILLING; demais papéis
não administram usuários. Tenant e unit scope permanecem derivados da sessão;
`platform_admin` é autoridade separada e não concedível/mutável pelo tenant.

PR #123 MERGED, HEAD `14e27b269344b9bec549d13dd96434e8a41ad8aa`, merge/main
`459f7d1d4fd54997345d9458e1b365d49a50e31d`. CI PR #651 SUCCESS; Governance
#72 (PR) e #73 (main) SUCCESS. A implementação integra surface `users` durável,
createUser/updateUser com CSRF, Idempotency-Key, versão e audit; update revoga
sessões/resets e protege o último OWNER ativo; navegação é filtrada pela permissão
backend; audit de conta restrita respeita unit_ids. P2-G05, P2-G06 na parcela
RBAC/navegação e P2-G09 ficam resolvidos internamente, condicionado ao closeout/main
verdes. CI main #652 da implementação ficou presa em infraestrutura no Install
Chromium e não é usada como evidência final.

Com T04 certificada serão 17 surfaces genéricas duráveis; usage/billing/plans
permanecem T05 e support permanece T07. P2 continua aberto.

## Evolução CURRENT T03 — 2026-10-06

PR #121: cinco formulários/comandos canônicos (configureCertificates/Providers/
Webhooks/Integrations/Settings), egress exclusivo de platform_admin e metadados
sanitizados de webhook_event na outbox existente. Tenant/unit/env, sessão, CSRF,
Idempotency-Key, versão/fingerprint/audit/rollback duráveis; transport com policy
por delivery/retry, DNS e IP pinning/TLS. Política aprovada pelo dono como conjunto.
PR #121 MERGED, HEAD 2e7333f02d3673196d18c25702b1ab39fbfb5eb8, main
1e9c102ab250b822c89cfbb5c3d185ba3c62d9ea. CI #647/#648 e Governance #68/#69
SUCCESS; 1277 Python/PostgreSQL, 12 frontend e 18 Playwright PASS/zero SKIP.
P2-G08 resolvido internamente. T03 DONE_CERTIFIED condicionado ao closeout/gates;
T04 não iniciada. Registro: checkpoints/NFV1_P02_T03_CLOSEOUT_2026-10-06.md.
As linhas abaixo conservam o baseline T01 e o checkpoint da parcela de leitura;
prova de destino/secret/provider/entrega real e operação em produção segue não confirmada.

## Evolução histórica da parcela de consulta — 2026-10-06

As tabelas abaixo conservam o baseline T01. T02 (#117/#118) conectou cinco vistas
fiscais; T03 parcela (#119, main `db2a8fb71097eb4e1f6e5919e1eb544c8a3167ac`,
CI #641/Governance #62 SUCCESS) conectou quatro novas vistas e aprimorou settings.
CURRENT: 16 surfaces genéricas duráveis; users T04, usage/billing/plans T05 e
support T07 restantes. Configuração integral/write continua T03, bloqueada por
T03-B01 (política de destinos DRAFT); não há Task T03 certificada nem P2 concluída.
Registro superior: `checkpoints/NFV1_P02_T03_READ_ONLY_CHECKPOINT_2026-10-06.md`.

## Escopo congelado e aceite

Esta tarefa registra, para TODAS as superfícies do cronograma e da navegação existente,
autoridade, endpoint, projeção, mutações, RBAC, tenant/unidade, estados e auditoria.
Não implementa superfícies, não muda contratos/permissões e não cria outro plano.
As tarefas donas dos gaps continuam sendo as Task IDs do cronograma canônico.

CURRENT → TARGET da T01: inventário disperso → matriz completa, com gaps identificados,
evidências de código e ownership. TARGET de implementação nas tabelas não é CURRENT.

Mapa de impacto: somente esta matriz, checkpoint T01, ledger e reconciliação do CURRENT.
Sem migrations, runtime, frontend ou infraestrutura alterados.

Aceite: 24 itens da navegação + inutilização cobertos; 15 superfícies exigidas pelo P2
cobertas; endpoints existentes separados de projeções indisponíveis; mutações e gates
enumerados; lacunas atribuídas; Plan Governance e CI completas verdes antes de merge;
CI main e closeout antes de marcar T01 concluída.

## Autoridades e contratos comuns

- Runtime único: `runtime/api.py:create_runtime_app`; composição durável:
  `runtime/composition.py:build_postgres_runtime_composition`.
- Tenant, papel e unidades: `HumanIdentityService` → sessão opaca → `AuthenticatedHuman`.
  `platform_admin` é flag explícita da conta, não sexto papel nem atributo do browser.
- `web/portal_api.py`: autorização backend por `_SURFACE_PERMISSIONS` e
  `_OPERATION_PERMISSIONS`; `_reject_browser_authority`, `_csrf`, `_safe_payload`.
- GET genérico: `/v1/portal/surfaces/{surface_id}` retorna `{surface, rows}`;
  bootstrap: `/v1/portal/bootstrap`. Rotas registradas não provam projeção integrada.
- `DurableHumanPortalExecutor`: sete superfícies duráveis; as demais retornam
  `503 PORTAL_RUNTIME_NOT_READY`, após autenticação/RBAC.
- Fiscal: `CanonicalPortalOperationExecutor` → `CanonicalFiscalOperationPath` →
  `FiscalApplicationService` e autoridades de domínio existentes. O root padrão não
  configura handlers fiscais externos; operação autorizada e corretamente configurada
  quanto a unidade/ambiente termina em `503 FISCAL_RUNTIME_NOT_READY` sem handler.
- Provider: `ProviderRegistry` / `ProviderGatewayService`; vault:
  `SecretResolutionService` / `ExternalFiscalSecretVault`; readiness:
  `CapabilityReadinessService`; produção: `ProductionExecutionAuthority`.
  Nenhuma projeção/UI pode substituir essas autoridades.

Prefixo dos arquivos fonte citados abaixo: `src/kordena_fiscal/`.

## 1. Matriz de superfícies — CURRENT versus TARGET

`G(id)` significa GET `/v1/portal/surfaces/{id}`. `F(op)` significa POST
`/v1/portal/operations/{op}`. Identificadores escritos nesta seção são existentes,
exceto onde explicitamente indicado AUSENTE/TARGET.

| ID / superfície | Endpoint CURRENT | Autoridade / projeção CURRENT | Mutação CURRENT e TARGET delimitado | Estado e tarefa dona |
|---|---|---|---|---|
| overview / Visão geral | bootstrap; G(overview) | `DurableHumanPortalExecutor.snapshot`: organização, unidades, ambientes, onboarding e configuração de executor | leitura; TARGET agregar somente indicadores comprovados | integrado internamente; refinamento P02-T07 |
| documents / Documentos | G(documents) | projeção AUSENTE; reutilizar UoW `lifecycle`/`archive`, `FiscalApplicationService`, `OperationalControlPlaneService` quando aplicável | F(queryFiscalDocument), F(cancelFiscalDocument) existem; leitura/archive Web por conectar | projeção indisponível; P02-T02; provider real P7 |
| issuances / Emissões | G(issuances) | projeção AUSENTE; lifecycle/idempotency/issuance existentes são autoridades, não o grid | F(issueFiscalDocument) existe; TARGET conectar listagem e ação ao mesmo path | projeção indisponível; P02-T02; P6/P7/P10 externos |
| errors / Erros | G(errors) | projeção AUSENTE; delivery audit/outbox e vistas sanitizadas de `OperationalControlPlaneService` existem | nenhuma mutação específica; TARGET leitura de falhas sanitizada | P02-T02; observabilidade operacional P9 |
| reconciliation / Reconciliação | G(reconciliation) | projeção AUSENTE; UoW `reconciliations`, `FiscalReconciliationEngine`, `OperationalControlPlaneService` | F(reconcileFiscalOperation) existe; TARGET conectar estado durável e ação canônica | P02-T02; provider real P7 |
| onboarding / Onboarding | G(onboarding) | snapshot de organização/unidades; `DurableControlPlaneService` | F(onboardUnit) integrado; somente homologação; organização comercial provisionada é predecessor | básico integrado; configuração restante P02-T03/P3 |
| companies / Empresas | G(companies) | uma organização da sessão: tenant_id, legal_name, status | nenhuma criação de organização pelo browser; provisioning comercial continua autoridade | leitura integrada; refinamento P02-T03 |
| units / Unidades | G(units) | unidades descobertas por audit UNIT_ONBOARDED, filtradas por unit_ids da conta | F(onboardUnit); replay same configuration retorna already_onboarded | integrado básico; gaps de escopo P02-T03/P02-T04 |
| environments / Ambientes | G(environments) | ambientes habilitados nas unidades permitidas; não certifica readiness fiscal | não há mutação Web para habilitar produção | integrado básico; P02-T03; promoção P10/P11/P12 |
| capabilities / Capabilities | G(capabilities) | projeção AUSENTE; `CapabilityReadinessService` / `GovernedCapabilityReadinessService` existentes | queryCapabilities existe no Bridge; não registrado como operação Portal | P02-T02; não inferir homologação |
| certificates / Certificados | G(certificates) | projeção AUSENTE; `SecretReference`, `DurableControlPlaneService.bind_secret_reference`, `SecretResolutionService` | nenhuma mutação Portal; TARGET referências opacas/metadados e configuração governada, sem material raw | P02-T03; secret backend P6; material oficial P10 |
| providers / Providers | G(providers) | projeção AUSENTE; `ProviderBinding`, `CommercialConfigurationService`, registry/gateway existentes | nenhuma mutação Portal; TARGET bindings por tenant/unidade/ambiente/documento/operação/jurisdição | P02-T03; transporte real P7 |
| users / Usuários | G(users) | projeção AUSENTE; `HumanAccountRepository`, sessão e RBAC existentes | nenhuma administração Portal; TARGET estender a mesma autoridade humana, sem segunda auth | P02-T04; política administrativa a revisar antes de implementação |
| webhooks / Webhooks | G(webhooks) | projeção AUSENTE; `WebhookDestinationConfig`, commercial store, delivery audit/inbox/outbox existentes | nenhuma mutação Portal; TARGET configurar destino e acompanhar entrega, sem secret raw | P02-T03; Worker P4; ingress comercial P3 |
| integrations / Integrações | G(integrations) | projeção AUSENTE; bindings host/fiscal, módulos e workload credential metadata existentes | nenhuma mutação Portal; TARGET exposição governada das autoridades existentes | P02-T03; S2S real depende de configuração autorizada |
| usage / Uso | G(usage) | projeção AUSENTE; `SubscriptionCheckpoint.usage`, estado comercial canônico | nenhuma alteração pelo browser; TARGET leitura de uso persistido, sem inventar consumo | P02-T05; medição/jornada operacional P3/P4/P9 |
| billing / Billing | G(billing) | projeção AUSENTE; canonical commercial UoW/subscription/fulfillment | nenhuma declaração de pagamento/entitlement permitida; TARGET leitura canônica | P02-T05; canal real P8 |
| plans / Planos | G(plans) | projeção AUSENTE; `CommercialPlan`, catálogo de pricing e subscription canônica | nenhuma mutação cliente; catálogo da plataforma separado abaixo | P02-T05; preços reais exigem decisão humana |
| pricing-admin / Catálogo comercial | GET/POST `/v1/admin/pricing` | `CommercialPricingAdministrationService`, catálogo durável; formulário dedicado | publicar configuração versionada; sessão platform_admin + CSRF; controle de versão no catálogo | integrado interno; provider/IDs/preços reais fora desta tarefa |
| commercial-release / Liberação comercial | GET/POST `/v1/admin/commercial-release` | `CommercialReleaseAdministrationService` e projeção de oferta | registrar decisão comercial; platform_admin + CSRF; controle de versão no catálogo | integrado interno; não equivale a aprovação fiscal; readiness de compra P3 |
| checkout-admin / Canais de Venda / Checkout | GET/POST `/v1/admin/checkout/cakto` | adapter Cakto opcional; `CaktoCheckoutAdministrationService` | binding de oferta do adapter; platform_admin + CSRF; upsert por referência externa | condicionado a adapter composto; nenhuma dependência arquitetural obrigatória em Cakto; P3/P8 |
| audit / Auditoria | G(audit) | `control_plane.list_audit(tenant)` → metadados action/target/correlation/unit | somente leitura; não contém audit fiscal/comercial completo | integrado parcial; filtro de unidade e cobertura P02-T04/P02-T07/P9 |
| support / Suporte | G(support) | projeção AUSENTE; health/metrics/tracing/runbooks existentes não compõem esta superfície | nenhuma mutação/ticket service encontrado; TARGET não fabricar tickets ou SLA | P02-T07 para estado sanitizado; P9/P12 para operação/suporte real |
| settings / Configurações | G(settings) | CURRENT retorna snapshot básico; não retorna políticas/configuração completa | nenhuma mutação settings; TARGET `CommercialConfigurationService`/Control Plane, configuração por cliente sem código | P02-T03 |
| inutilização / Inutilização | sem item próprio de navegação; opção existe no dialog; F(inutilizeFiscalRange) | `CanonicalPortalOperationExecutor` e path fiscal compartilhado; projeção dedicada AUSENTE | mutação existe; dialog só abre por documents/issuances/reconciliation após carregar projeção disponível | jornada não alcançável no root padrão; P02-T06; P6/P7/P10 externos |

## 2. RBAC CURRENT por superfície e operação

O/A = OWNER e ADMIN; Op = OPERATOR; Au = AUDITOR; B = BILLING.
Flags e permissões são avaliadas no backend. A UI CURRENT filtra disponibilidade,
mas não filtra todos os itens/ações pelo papel; visibilidade não concede acesso.

| Superfície(s) | Permissão CURRENT | Papéis CURRENT que possuem a permissão | Escopo / auditoria / estados |
|---|---|---|---|
| overview, errors, capabilities, support | portal.read | O/A, Op, Au, B | tenant da sessão; projeções ausentes ainda 503; novos dados devem restringir unidades |
| documents, issuances, reconciliation | document.query | O/A, Op, Au | tenant + unidades autorizadas; metadados fiscais sem segredo; listagens ainda 503 |
| onboarding, companies, units, environments, settings | configuration.write | O/A | organization/unit do tenant; onboarding registra UNIT_ONBOARDED e correlation ID |
| certificates | certificate.manage | O/A | tenant/unidade/ambiente/purpose/provider/version; raw secrets bloqueados; projeção 503 |
| providers, webhooks, integrations | integration.manage | O/A | bindings/config do tenant; mutações TARGET auditáveis; projeção 503 |
| users | user.manage | O/A | tenant da sessão; não permite conceder platform_admin automaticamente; projeção 503 |
| usage, billing, plans | billing.read | O/A, Au, B | assinatura/uso do tenant; provider externo não é autoridade; projeção 503 |
| audit | audit.read | O/A, Au | CURRENT filtra tenant mas não eventos por unit_ids; gap explícito abaixo |
| pricing-admin, commercial-release, checkout-admin | platform_admin flag | somente conta com flag explícita | autoridade global separada; O/A do tenant não implica flag; adapter optional |
| issueFiscalDocument | document.issue | O/A, Op | CSRF + unidade/ambiente validados + Idempotency-Key; handler ausente 503 |
| queryFiscalDocument | document.query | O/A, Op, Au | POST protegido por CSRF; unidade/ambiente validados; key opcional; handler ausente 503 |
| cancelFiscalDocument | document.cancel | O/A, Op | CSRF + Idempotency-Key + scope canônico; handler ausente 503 |
| inutilizeFiscalRange | document.inutilize | O/A, Op | CSRF + Idempotency-Key + scope canônico; handler ausente 503 |
| reconcileFiscalOperation | reconciliation.execute | O/A, Op | CSRF + Idempotency-Key + scope canônico; handler ausente 503 |
| onboardUnit | configuration.write | O/A | CSRF + Idempotency-Key; organization must exist; unit scope revalidado; homologação apenas |

Ausência/invalidade da sessão: 401. Falta de permissão/unidade/CSRF: 403.
Autoridade fornecida pelo browser ou key obrigatória ausente: 400.
Unidade fiscal não configurada: 409. Surface/operation desconhecida: 404.
Secret em projeção: 500 PORTAL_SECRET_BOUNDARY_VIOLATION.
Dependência de projeção/fiscal ausente: 503. Vazio confirmado: `rows=[]`, nunca fallback fake.

## 3. Tenant, unidade e audit trail — limites confirmados

FATO: HTTP ignora tenant headers como autoridade e rejeita mass assignment em mutações.
FATO: operações fiscais revalidam conta/unit/environment e consultam a unidade durável.
FATO: unidades projetadas são limitadas por `authority.account.unit_ids`.

GAP: G(id) aceita `?unit_id` para autorização, porém não passa esse filtro ao executor.
Isso não permite inventar tenant; tampouco prova filtro de listagem por unidade selecionada.
Listagens futuras precisam preservar seleção/escopo sem introduzir segunda autoridade.

GAP: `_tenant_state` filtra unidades mas devolve todos os eventos do tenant.
G(audit) não restringe eventos às unidades da conta. Não declarar isolamento por unidade
de audit como certificado. Não há PII/secret novo nesta tarefa documental.

FATO: unit discovery depende de eventos UNIT_ONBOARDED; unidades inseridas por caminho
sem esse evento não aparecem. A mutação onboarding usa serviço durável com auditoria.

GAP: a composição usa `InMemorySecurityAuditSink` se nenhum sink explícito for fornecido.
Segurança interna testada não prova trilha S2S operacional persistida/exportada.

TARGET: cada escrita deve reutilizar audit/UoW canônico, correlation/causation e
idempotência; não usar UI como registro de auditoria. Listagens devem ser sanitizadas,
limitar volume e consultar estado autorizado; não enumerar tenants globalmente.

## 4. Registro de pendências — zero pendência invisível

| Gap | Fato CURRENT / ação necessária | Task ID dona |
|---|---|---|
| P2-G01 | 14 superfícies genéricas não têm projeção durável; router e labels não equivalem a disponibilidade | P02-T02/T03/T04/T05/T07, conforme matriz |
| P2-G02 | fiscal handlers padrão vazios; path composto é dispatcher interno, não integração externa executável | P7; P6/P10 dependências; P02-T02 mantém bloqueio explícito |
| P2-G03 | queryArchiveReference/queryCapabilities Bridge sem operação Portal correspondente/projeção | P02-T02 |
| P2-G04 | filtro unit_id não chega à projeção; definir contrato de filtro preservando autoridade | P02-T02; certificar transversalmente P02-T04 |
| P2-G05 | auditoria tenant-wide para conta restrita por unidade | P02-T04; não expor eventos de unidade não autorizada |
| P2-G06 | disponibilidade de navegação não considera todas as permissões; dialog não restringe opções por RBAC; 403 backend preservado | P02-T04/P02-T07 |
| P2-G07 | inutilização tem contrato e opção, mas fluxo Web depende de superfícies indisponíveis e não tem jornada dedicada | P02-T06 |
| P2-G08 | settings/onboarding básicos não compõem configuração de certificado/provider/webhook/integration completa por cliente | P02-T03 |
| P2-G09 | users não possui list/admin; política de criação/revogação/escopo de papéis precisa revisão antes de mudança sensível | P02-T04; decisão humana se política nova necessária |
| P2-G10 | billing/plans/usage sem projeção; subscription/usage canônicos existem, não inferir cobrança/uso real | P02-T05; P3/P8 validação operacional |
| P2-G11 | support sem projection/ticket service; não inventar integração, atendimento ou SLA | P02-T07/P09-T05/P12-T05; definição humana se ampliar produto |
| P2-G12 | Playwright usa page.route mocks e servidor estático; cobre UI/contratos, não HTTP durável real | jornadas internas P02-T02..T07; real staging P05-T04 |
| P2-G13 | operation dialog gera nova key a cada submit; retry de outcome unknown ainda sem jornada de reutilização explícita | P02-T02/P02-T06/P02-T07 |
| P2-G14 | erros/projected backend keys exibidos genericamente; várias descrições/labels em inglês | P02-T07; português, acessibilidade, estados reais |
| P2-G15 | sink S2S default in-memory não prova auditoria operacional durável | P09-T01/T02/T05 |
| P2-G16 | CURRENT documental ainda priorizava P01-T01, apesar de P1 mergeado/certificado | corrigido nesta T01 por checkpoint superior reconciliado |
| P2-G17 | recovery aceita query reset_token por compatibilidade; delivery novo usa fragment | P02-T07: reconciliar runbook/compatibilidade sem remover links válidos às cegas |
| P2-G18 | admin pricing/release usam expected_version e correlation ID; checkout faz upsert; essas rotas não exigem Idempotency-Key como operações fiscais | P02-T05/P02-T07 e P3: provar replay/controle de concorrência sem afirmar key inexistente |
| STG-B01..B08 | staging diverge de main; Worker sem processo running; tracing/domínios/rollback não certificados | registro canônico de drift; P4/P5/P9/P11 |

A varredura `TODO|FIXME|HACK` em Portal/portal API/runtime fiscal não encontrou marcadores
de implementação pendente. A ausência dessas palavras não fecha nenhum gap funcional.
Mocks/synthetic encontrados nos testes são evidência interna apenas. Testes PostgreSQL
têm skip quando DSN ausente; CI fornece PostgreSQL e deve confirmar execução, não aceitar
skip local como certificação. Flags de adapter Cakto/worker oneshot são governadas, não
prova de canal real/Worker contínuo.

## 5. Evidências e verificação

Fontes auditadas: `portal/app.js`, `portal/index.html`, `web/portal_api.py`,
`web/portal_runtime.py`, `web/app.py`, `runtime/api.py`, `runtime/composition.py`,
`runtime/fiscal_runtime.py`, `security/human_identity.py`, `persistence/ports.py`,
`control_plane/durable.py`, `control_plane/commercial.py`, `control_plane/operations.py`,
`control_plane/capability.py`, `product/billing.py`, `persistence/commercial_fulfillment.py`,
`web/pricing_admin.py`, `web/commercial_release.py`, `web/cakto_checkout.py`.

Decisão de composição reutilizada: `NFCORE_V1_P01_CANONICAL_FISCAL_COMPOSITION_2026-10-05.md`.
Closeout predecessor: `checkpoints/NFV1_P01_T04_CLOSEOUT_2026-10-06.md`.
Certificação Web histórica: `web/WP_WEB_04_REAL_PORTAL_INTEGRATION.md`, sem promover sua
evidência antiga para CI atual ou integração externa real.

Validação T01: conferir cobertura exata entre navegação, mapa de permissões, surfaces
duráveis e tabela; rodar `python3 scripts/check_nfcore_plan.py`, secret scan e migration
policy; CI completa obrigatória inclui Ruff/Mypy/Pytest/PostgreSQL, frontend e Playwright,
dependency/container scans, smokes, SBOM e backup/restore. Não desabilitar gates.

## 6. Staging e limites externos

Railway reconsultado READ-ONLY: projeto `FM NFCORE Staging`,
environment `c9878b9b-62b2-4a97-b8ba-743c8a3e99ec` (label production dentro do projeto staging).
API/Portal: `f9b5b2c5b436045947159f1e76be9303f5a95d90`, cada um 1/1 running.
Worker: `1c34ba001935952f83ec0b065144e0b8311a5650`, 0/1 running.
Postgres 18: 1/1, volume 5000 MB. Serviços sem alterações staged;
pendingWork contém patch vazio com `changes=[]`. Sem deploy/restart/configuração alterados.

Classificação: STAGING_REAL / VERSION_DRIFT_PRESENT / NOT_CERTIFIED_AGAINST_CURRENT.
Não foi feita leitura de secret nem transação fiscal/comercial real.
`PRODUCTION_APPROVED=NO`; `COMMERCIAL_LIVE=NO`.

Próxima tarefa após CI, merge e closeout T01 certificados: **NFV1-P02-T02 — Superfícies fiscais**.
O gate de fase PORTAL_COMMERCIAL_PARITY_CERTIFIED continua NOT MET.
