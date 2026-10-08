# CHECKPOINT / FECHAMENTO — NFV1-P03-T03 Provider webhook runtime

Data: 2026-10-08. Produto: FM NFCORE V1.
Repository: faabio3131/kordena-fiscal-engine-v2.
Main HEAD: 0bbd02984aa6ac357d9ffc48d43dcfc1c1cc9c89 (PR #136).
Branch: feat/nfv1-p03-t03-webhook. PR #137 MERGED por autorização específica.
HEAD certificado: `1404cdc5f12525e15c5e887c0b8a4579e3e75793`.
Merge/main: `bfb31e5f8d6924f4fff8f92c37c8e420b04c871f`.
Árvore PR/main idêntica: `c683b03891a5d0421260e18d85234f0d33d2c711`.
CI PR #692/run37850360972 e Governance #113/run37850360981 SUCCESS.
PR: 41/41 etapas PASS;1504 Python/PostgreSQL,14 frontend,28 Playwright PASS, zero FAIL/zero SKIP.
CI main #693/run37857702520 e Governance #114/run37857702555 SUCCESS.
Job main113585762495:41/41 etapas PASS;1504 Python/PostgreSQL PASS/zero FAIL/zero SKIP,295.08s;14 frontend e28 Playwright PASS.
Estado: DONE_CERTIFIED interno, condicionado à integração/gates deste fechamento documental.
Warnings observados na main: depreciação Starlette/httpx no TestClient e metadata alias Pydantic no teste concorrente de configuração existente. Não foram suprimidos; suíte passou integralmente.
CI main de entrada: #688 / 37842407176 SUCCESS; Governance #109 SUCCESS.

CURRENT: P03-T03 integrado e certificado internamente na main; fechamento documental candidato.
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

Testes certificados na PR #137: 1504 Python/PostgreSQL,14 frontend e28 Playwright
PASS, zero FAIL/zero SKIP;41/41 etapas. Ruff/Mypy/plan/migration policy,
secret scan, audits, containers/non-root/smokes, SBOM e backup/restore PASS.
Testes locais sem DSN possuem SKIPs; não são usados como prova PostgreSQL.
A evidência final remota supersede as contagens locais e CI #691 histórica.

Security/Tenant/Unit: contrato nega tenant/unit/role/permissões/PII livres; binding
não concede autoridade fiscal nem platform_admin. Rate limit por binding/processo,
sem alegar limitação global distribuída. Configuração de clientes é estado durável,
sem condicionais de código por cliente.

Staging: não reconfirmado; último registro indica drift. Nenhum deploy realizado.
External dependencies: emissor real Command, checkout/delivery/backend reais não
certificados. Nenhum gateway/Asaas configurado no NFCore; pertencem ao Command.

Riscos/pendências:
- T03 integrado e gate pós-merge PASS; integração do fechamento documental pendente.
- Retry do emissor com o mesmo envelope recupera inbox pendente. Worker contínuo P4.
- Purchase-readiness completa é T04; esta entrega não declara canal real habilitado.
- Lifecycle abrangente T05; homologação Command/gateway real P8.
- Merge/deploy, secrets reais e operação externa seguem gates próprios.

Gate técnico de saída: PASS (PR e main com todos os gates completos).
Próxima tarefa: NFV1-P03-T04 Purchase readiness, somente após integração/gates deste fechamento documental. T04 não iniciada.
P3 permanece incompleta até T04/T05. PRODUCTION_APPROVED=NO;COMMERCIAL_LIVE=NO.

## Continuidade documental

Atualiza o checkpoint existente para evitar cópias paralelas. A autorização específica
recebida cobre merge da PR #137 e validação da main; o merge desta nova PR
documental requer autorização específica conforme AGENTS.md.
SHA/PR/CI documentais finais serão registrados no corpo da PR, evitando referência
circular dentro do próprio commit. Nenhum deploy ou operação externa autorizado.

## Correções da CI #691

HEAD eaac43a866d863ca4169e006bf8dab5d57749b40: 1498 PASS/5 FAIL, sem SKIP.
Duas expectativas de upgrade ainda omitiam a migração 15; corrigidas. Fixtures
de claim e expiração agora preservam nome/identidade imutáveis da aquisição.
Binding de outra assinatura com aquisição já vinculada agora rejeita explicitamente
409; colisão SQL de correlação também vira conflito canônico e rollback, sem
tratá-la como indisponibilidade transitória. Nenhum teste foi removido ou relaxado.
Revisão corrigida HEAD1404cdc5f12525e15c5e887c0b8a4579e3e75793;CI #692 PR e #693 main completas SUCCESS. A evidência final acima supersede a tentativa #691.
