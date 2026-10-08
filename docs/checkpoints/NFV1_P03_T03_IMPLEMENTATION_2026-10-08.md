# CHECKPOINT — NFV1-P03-T03 Provider webhook runtime

Data: 2026-10-08. Produto: FM NFCORE V1.
Repository: faabio3131/kordena-fiscal-engine-v2.
Main HEAD: 0bbd02984aa6ac357d9ffc48d43dcfc1c1cc9c89 (PR #136).
Branch: feat/nfv1-p03-t03-webhook. PR: #137 Draft. HEAD/CI final: registrar na PR após gates.
CI main de entrada: #688 / 37842407176 SUCCESS; Governance #109 SUCCESS.

CURRENT: P03-T02 certificado; P03-T03 em execução.
TARGET: ingresso comercial interno Command configurável, autenticado e durável.
Política integral aprovada explicitamente pelo dono em 2026-10-08:
POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION, T03-B01 resolvido.

Mudanças e autoridades reutilizadas:
- Rota POST /v1/commercial/command/events apenas com SecretResolver e composição
  canônica PostgreSQL. Signature HMAC existente, schema estrito e corpo <=64KiB.
- Binding governado com CAS, trilha de auditoria e somente AdminPrincipal global
  com commercial_config.write + secret_reference.write. Nenhum tenant se autoriza.
- Resolver efêmero de referência/version; scope inclui binding/produto/ambiente/versão.
  Missing/expiry/revocation/scope/backend error bloqueiam autenticação.
- Migração aditiva 15 no boundary/guard existentes: bindings/audit, inbox e
  correlações. Inbox não armazena corpo bruto. Identidades/fingerprint persistidos.
- Locks PostgreSQL por aquisição/subscription/evento serializam réplicas.
  Inbox pendente é confirmada antes do fulfillment; processed_at só após resultado.
- CommercialFulfillmentService mantém compra local; aquisição/plan/price/release
  canônicos exigidos; correlaciona produto/ambiente/cliente/assinatura/fatura.
- Claim existente continua obrigatório; sem criação de tenant/OWNER pelo pagamento.
  Após claim, evento elegível reutiliza provisioning/activation/delivery existentes.
  Falha de delivery mantém evento pendente, reprocessamento não duplica org/OWNER.

Testes: Ruff/Mypy/plan/migration policy e testes dirigidos locais; suite local inicial: 1289 PASS/204 SKIP (sem DSN), sem falhas;
testes dirigidos finais: 31 PASS/18 SKIP locais; PostgreSQL remoto em execução. Sem DSN PostgreSQL local; SKIP local não é prova.
Remote CI obrigatório antes de propor certificação. Não remover/enfraquecer gates.

Security/Tenant/Unit: contrato nega tenant/unit/role/permissões/PII livres; binding
não concede autoridade fiscal nem platform_admin. Rate limit por binding/processo,
sem alegar limitação global distribuída. Configuração de clientes é estado durável,
sem condicionais de código por cliente.

Staging: não reconfirmado; último registro indica drift. Nenhum deploy realizado.
External dependencies: emissor real Command, checkout/delivery/backend reais não
certificados. Nenhum gateway/Asaas configurado no NFCore; pertencem ao Command.

Riscos/pendências:
- T03 implementado não integrado enquanto PR/CI/merge pendentes.
- Retry do emissor com o mesmo envelope recupera inbox pendente. Worker contínuo P4.
- Purchase-readiness completa é T04; esta entrega não declara canal real habilitado.
- Lifecycle abrangente T05; homologação Command/gateway real P8.
- Merge/deploy, secrets reais e operação externa seguem gates próprios.

Gate de saída: PENDENTE (CI remota/integração).
Próxima ação: publicar PR Draft P03-T03 e validar todos os gates. T04 não iniciada.
