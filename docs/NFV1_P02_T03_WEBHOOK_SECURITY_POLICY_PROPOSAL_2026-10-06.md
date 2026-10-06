# NFV1-P02-T03 — Proposta de política de destinos de webhook

Data: 2026-10-06. Repository: `faabio3131/kordena-fiscal-engine-v2`.
**Status: DRAFT / DECISÃO HUMANA PENDENTE. NÃO APROVADO. NÃO IMPLEMENTADO.**
Task ID: NFV1-P02-T03. Não cria cronograma ou autoridade concorrente.

## Problema CURRENT e por que requer decisão

C04 em `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md` exige allowlist/política.
Hoje o contrato aceita HTTPS com hostname, sem userinfo/fragment. Não há fonte
aprovada de destinos ou política contra redes privadas/DNS rebinding/redirect.
INTEGRATION_MANAGE permite administrar integração, mas não define autoridade
para aprovar egress da plataforma. Uma nova interface que permita ao cliente
escolher destino afeta o encaminhamento de payloads fiscais assinados.

AGENTS.md exige parar antes de "mudança de segurança sensível"; padrão mestre
§6 antes de "mudança de segurança". A autorização interna de execução/merge não
foi interpretada como aprovação desta política nova. Aprovação deste DRAFT NÃO
autoriza deploy, destino real, secret real, entrega externa ou produção.

## Proposta concreta para aprovação em conjunto

| Decisão | Política recomendada (DRAFT) |
|---|---|
| Quem solicita | OWNER/ADMIN com integration.manage, tenant/unidades derivados da sessão. Nenhuma permissão nova para OPERATOR/AUDITOR/BILLING. |
| Quem aprova destino | Administrador de plataforma com flag platform_admin canônica; tenant não aprova egress nem concede a própria flag. Sem segunda autenticação/RBAC. |
| Scope | Registro versionado no Control Plane existente, exact tenant/unit/environment/destination; aprovação por destino, sem wildcard cross-tenant ou cross-unit. |
| URL | HTTPS porta 443, hostname DNS normalizado e path explícito; rejeitar userinfo, fragment, query, IP literal, localhost e nomes locais. Sem URL/headers livres contendo credenciais. |
| Rede | Somente endereços globalmente roteáveis; negar private, loopback, link-local/metadata, multicast, reserved e unspecified IPv4/IPv6. Se qualquer resposta DNS for proibida, deny. |
| DNS / conexão | Revalidar resolução em cada tentativa e conectar apenas ao endereço validado, preservando hostname TLS; não validar um IP e conectar a outro. |
| Redirect | Não seguir redirects; 3xx não representa entrega confirmada. Mudança de destino requer novo registro/aprovação. |
| Estado padrão | Não aprovado, revogado, expirado ou policy ausente => deny. Cadastro nunca equivale a habilitar entrega. |
| Mutação | CSRF + permissão/unidade backend; Idempotency-Key com fingerprint persistido e rollback atômico; controle de versão; conflitos/replay devem falhar fechado ou retornar resultado original. |
| Audit | Fact durável no UoW existente para solicitação/aprovação/revogação/alteração; actor pseudônimo, scope, correlation, IDs/version/outcome; sem URL/query/payload/secret bruto. |
| Entrega | Reutilizar WebhookSecurity + SignedWebhookOutboxHandler + outbox/worker + transport existente. A mesma política aprovada deve ser revalidada no delivery, não só no cadastro/UI. |
| Configuração por cliente | Destino/aprovação por dados persistidos e referências, sem commit por cliente. Nenhum domínio FM hardcoded como regra universal. |

Não escolhe cloud/proxy/provedor, não provisiona recurso, não publica destinos e
não cria outra fila/registry/Vault. A aprovação da política habilita implementação
interna governada no mesmo stack, com dados exclusivamente sintéticos nos testes.
Decisões de operação real/deploy permanecem gates específicos posteriores.

## Mapa de impacto após aprovação

CommercialConfigurationService + Control Plane/audit/UoW: cadastro e estado aprovado
versionados, sem segundo store. Portal API/executor/UI: formulário real, permissão,
CSRF, scope, idempotência/concorrência e metadata sanitizada. Delivery resolver/
transport/Worker existentes: aplicar a política antes de I/O e de cada retry.
Mudança de schema, se necessária, aditiva e sob migration guard; nenhuma migration
produtiva nesta autorização. Catálogo de providers/Vault seguem suas autoridades.

Demais mutações T03 (referências, bindings/módulos/policies) permanecem pendentes
de implementação/testes desta tarefa. Não são declaradas completas nem remetidas
para uma tarefa posterior. Catálogos regulatórios/readiness/produção não editáveis
livremente pelo tenant; workload credentials/grants globais não expostos.

## Aceite e testes exigidos depois da decisão

- Aprovação/revogação persistida, sem self-approval de tenant ou spoofing de flag.
- Isolamento tenant/unit/environment; roles; sessão/CSRF; versão e idempotência.
- DNS com um endereço privado entre respostas públicas => deny; rebinding => deny.
- IPv4/IPv6/metadata/loopback/localnames/IP literal/userinfo/query/fragment/portas/
  redirects não autorizados => deny; nenhuma chamada externa nesses testes.
- Configuração ausente, versão antiga, revogação e falha de resolução => deny.
- Outbox/lease/retry continuam canônicos e sem side effect duplo.
- URL/query/headers/hash/token/raw payload não saem em UI/log/audit/CI artifacts.
- Mesma configuração persiste entre recomposições; cliente novo sem código.
- Playwright HTTP durável, PostgreSQL e todos os gates existentes verdes antes
  de certificar T03; CI main e closeout; staging real em P5 sob autorização.

## Aprovação/recurso solicitado ao dono

Aprovar ou ajustar a política da tabela como conjunto. Registro esperado:
POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION, aprovador, data, escopo e versões.
Não usar PRODUCTION_APPROVED/COMMERCIAL_LIVE. Enquanto pendente, T03 permanece
bloqueada para cadastro/ativação e seu successor P02-T04 não é executado.
