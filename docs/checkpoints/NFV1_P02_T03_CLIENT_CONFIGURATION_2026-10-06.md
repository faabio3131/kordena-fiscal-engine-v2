# NFV1-P02-T03 — Configuração do cliente

Data: 2026-10-06. Repository: `faabio3131/kordena-fiscal-engine-v2`.
Status: EM EXECUÇÃO; task NÃO certificada.
main de entrada: `4b0d008d39ef3c579fa0d521864a92a58907b0de`; PRs abertas: zero.
Predecessor P02-T02: entrega #117 + closeout #118 MERGED.
CI main #629 (37503486524) e Plan Governance #58 (37503486424): SUCCESS.
Branch: `feat/nfcore-web-nfv1-p02-t03-client-config`; HEAD/PR/CI de entrega pendentes.

## Autoridade / CURRENT → TARGET / escopo congelado

Cronograma P02-T03: conectar certificates, providers, webhooks, integrations e
settings sem expor secrets. Ledger: primeira incompleta, predecessor certificado.
T04 e posteriores não liberadas. Não criar outro cronograma.

CURRENT: quatro projeções ausentes; settings snapshot básico. Autoridades existentes:
SecretReference/DurableControlPlaneService; CommercialConfigurationService;
ProviderBinding, WebhookDestinationConfig, UnitModuleBinding, RuntimePolicy;
FiscalAccountBinding; HumanIdentity/session/RBAC/CSRF; UoW SQLite/PostgreSQL.
ProviderRegistry/Vault/readiness permanecem únicos; cadastro não é operação provada.

TARGET completo: cinco vistas e configuração governada por cliente sem código,
mutações com controles exigidos, isolamento/sanitização e jornadas críticas.
Parcela interna independente anterior à decisão: leituras duráveis paginadas, UI
de consulta e bloqueios verdadeiros. Não certificar CRUD pela entrega de leitura.

## Gate humano / execução independente

C04 de docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md exige HTTPS, sem credentials,
auditável e allowlist/política de segurança. Inspeção CURRENT: WebhookDestinationConfig
e WebhookDestination validam scheme/hostname/userinfo/fragment. Não há política de
aprovação/egress, bloqueio de IP privado/loopback/link-local, DNS/redirect seguro ou
catálogo aprovado de destinos no código/documentos pesquisados V2-05/08/15 e CL-13.
CommercialConfigurationService.set_webhook_destination não registra audit fact.

Expor cadastro/ativação arbitrária pelo browser exige nova decisão de segurança
sensível: quem aprova destinos de egress e qual limite de rede/redirect é permitido.
OWNER/ADMIN integration.manage não define aprovação de rede pela plataforma.
Proposta DRAFT será persistida; não adotá-la automaticamente.
AGENTS.md: "mudança de segurança sensível"; padrão mestre §6: "mudança de segurança".
Ambos exigem parar antes dessa decisão e registrar blocker no ledger/checkpoint.
Leituras independentes continuam autorizadas; escritas dependentes não serão expostas.

## Impacto / aceite / testes / gates

- Mesmo Portal/router/executor/frontend e stores; sem segunda autoridade.
- Exact tenant/unit/environment e binding pela conta/unidade fiscal interna da sessão.
- Certificados: referência opaca/kind/provider/scope; sem resolução do Vault.
- Providers: binding persistido; não inventar catálogo/readiness/homologação.
- Webhooks: metadata sem URL/path/query/headers/body bruto.
- Integrations: módulos/bindings; não enumerar credenciais/grants globais de workload.
- Settings: runtime policies persistidas; cadastro não prova ativação.
- UI com seleção/página e estados read-only/bloqueado/vazio/erro; sem botão fictício.
- Testes HTTP durável das cinco vistas, RBAC/tenant/unit/env/sanitização/paginação,
  restart da configuração, Playwright crítico.
- Todos os gates obrigatórios: plan/secret/migration/Ruff/Mypy/Python/PostgreSQL,
  frontend/Playwright/audits/containers/non-root/smokes/SBOM/backup-restore/CI.
- Dependência mínima de verificação: mesmo scripts/check_nfcore_plan.py também no
  workflow CI existente. Branch corresponde ao gatilho push feat/nfcore-web-*.
  Prova remota ANTES da PR durante indisponibilidade do shell, sem novo workflow,
  runner, infraestrutura ou plano e sem enfraquecimento.

## Staging / riscos / recursos / ações não realizadas

READ-ONLY revalidado: API/Portal deployments c0f8fb2b/35b7aafc inalterados, SHA
f9b5b2c5b436045947159f1e76be9303f5a95d90, 1/1 cada; Worker 3215f498,
SHA 1c34ba001935952f83ec0b065144e0b8311a5650, 0/1; Postgres 18/1/1/5000 MB.
Patch staged changes vazio. Projeto staging, environment chamado production.
STG-B01..B08 continuam P4/P5/P9/P11; sem deploy.

Shell scratch deixou de responder mesmo pwd após T02. Nenhuma validação/reprodução
local T03 tem resultado confirmado. Inspeção de código e prova CI são separadas.
Não alegar execução das URLs unsafe sem saída confirmada. T02 main remota verde.

Sem real secret/certificado/CSC, endpoint privado real, chamada externa, provider,
homologação/pagamento/novo dado pessoal/infra paga/deploy/migration externa/DNS/TLS
produtivo/cutover/Go-No-Go. PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.

## Prova / pendências / próxima Task

PENDENTE implementação/testes/CI da parcela de leitura. Mutação webhook exige
aprovação de proposta DRAFT; demais configurações/mutações ainda dentro de T03,
não transferidas artificialmente para outra Task. PORTAL_COMMERCIAL_PARITY_CERTIFIED
permanece NOT MET. Próxima Task P02-T04 somente após T03 completa e certificada.


## Parcela implementada — candidata, ainda sem CI

Cinco consultas no mesmo executor, 16 surfaces genéricas duráveis quando integradas
(12 anteriores + quatro novas; settings aprimorada). Projeções nos stores existentes
sem schema/migration nova: refs opacas, provider bindings, destino IDs/enabled sem
URL bruta, módulos/bindings de integração e políticas runtime. Cada coleção <=100,
integrações combina até duas coleções; scope antes do LIMIT. Binding não possui
partição por environment no modelo existente: resposta declara isso, não inventa.
UI consulta com seleção/página e aviso read-only; nenhuma escrita nova cadastrada.

22 testes parametrizados SQLite/PostgreSQL candidatos + uma jornada Playwright
HTTP durável candidata. PostgreSQL local NÃO executado; resultados CI pendentes.
Todos os testes anteriores preservados; teste de surface indisponível usa users
porque certificates agora é conectada e possui testes positivos/negativos próprios.

DRAFT concreto: docs/NFV1_P02_T03_WEBHOOK_SECURITY_POLICY_PROPOSAL_2026-10-06.md.
Sem aprovação implícita. Demais mutações T03 continuam pendentes dentro desta Task.

CI #630 no baseline da branch (4b0d008, antes da implementação T03) falhou no
E2E antigo de ativação: variável de callback assíncrono era verificada de forma
síncrona após click. 1149 Python/PostgreSQL PASS; não certificar esse run.
Asserção passou a aguardar o mesmo valor por expect.poll; nenhum teste removido,
retry de suite introduzido ou comportamento de reset alterado. Reexecutar CI completa.
