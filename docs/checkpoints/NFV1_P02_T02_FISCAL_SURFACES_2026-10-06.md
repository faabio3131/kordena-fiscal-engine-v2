# NFV1-P02-T02 — Superfícies fiscais

Data: 2026-10-06. Repository: `faabio3131/kordena-fiscal-engine-v2`.
Status: EM EXECUÇÃO, não certificado.
main de entrada: `5454a05619feafb4c179d9b047817d8593a46437`.
CI main #623 SUCCESS; Plan Governance #52 SUCCESS; zero PRs abertas.
Predecessor: P02-T01, PR #115 + closeout #116 mergeados e certificados.
Branch: `feat/nfv1-p02-t02-fiscal-surfaces`; HEAD/PR/CI de entrega pendentes.

## CURRENT → TARGET / escopo congelado

CURRENT: cinco surfaces fiscais retornam 503; seleção de unidade não chega ao
executor; lifecycle/idempotency não persistem partição de escopo recuperável; não
existe matriz de readiness composta no root; handlers fiscais externos não configurados.

TARGET: conectar documents, issuances, errors, reconciliation e capabilities ao
mesmo Portal/router/executor, usando autoridades e UoW existentes. Leituras fiscais
limitadas por tenant da sessão, unidade autorizada, namespace e ambiente. Metadados
sanitizados, sem XML/payloads/reasons/secrets raw. Estado não configurado permanece
bloqueado; não fabricar homologação ou operação bem-sucedida.

Dependência mínima de persistência: evoluir o lifecycle existente para conservar
escopo da reserva de emissão, sem segundo repository/estado fiscal. Registros legados
sem escopo não serão atribuídos por heurística nem expostos em listagem. Reserva
com escopo deve rejeitar colisão com documento de outro escopo ou legado não comprovado.
Projeções de archive/outbox/reconciliation consultam as partições canônicas existentes.
Readiness reutiliza CapabilityReadinessService/GovernedCapabilityReadinessService;
nenhuma nova matriz ou aprovação implícita. Ausência é estado explícito.

Fora de escopo: T03..T07, nova política de papéis/usuários, preço/comercial, provider
real, secrets/certificados reais, homologação oficial, deploy e migração produtiva.

## Impacto / aceite / testes

- Mesmo runtime/composition, Portal API e frontend; nenhuma segunda autoridade.
- Ports/adapters de lifecycle/archive/outbox/reconciliation: consultas com limites,
  isolamento em SQL e memória; migração aditiva governada, sem backfill inventado.
- Unit filter validado no backend e propagado ao executor; ambientes habilitados.
- Cinco surfaces disponíveis; vazio, bloqueio e erro distintos; ação fiscal permanece
  no CanonicalPortalOperationExecutor/path existente, CSRF/RBAC/idempotência preservados.
- UI deve mostrar dependência fiscal ausente; retry do mesmo request preserva a key.
- Testes dirigidos: isolamento tenant/unit/host/environment, registros legados,
  colisão/replay, sanitização, sessão/RBAC/CSRF, readiness indisponível/com authority
  explícita; jornadas Playwright internas com HTTP durável, sem page.route fiscal.
- Gates: plan validator, secret/migration policy, Ruff, Mypy, pytest + PostgreSQL,
  frontend lint/typecheck/tests/build, Playwright, auditorias, containers/non-root,
  smokes/readiness, vulnerability policy, SBOM, backup/restore, CI remota.
- Somente CI PR e main verdes + closeout autorizam DONE_CERTIFIED.

## Staging / segurança / dependências / blockers

Consulta READ-ONLY: API/Portal deployments permanecem 2026-10-04; Worker deployment
2026-10-01, 0/1 running, apesar do rótulo Online. SHAs auditados no closeout T01:
API/Portal `f9b5b2c5b436045947159f1e76be9303f5a95d90`; Worker
`1c34ba001935952f83ec0b065144e0b8311a5650`. Postgres 1/1. Patch staged sem changes.
STG-B01..B08 continuam P4/P5/P9/P11. Nenhum deploy executado.

Dados de testes sintéticos não certificam integração externa. Handlers/provider,
matriz readiness real e perfis fiscais operacionais dependem de configuração/evidência
governada posterior; a UI não pode substituir essas autoridades. P2-G02 fica P6/P7/P10.
P2-G05/G06 e administração de usuários continuam P02-T04; não antecipar sua política.
PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO. Nenhuma autorização humana nova consumida.

## Provas e closeout

PENDENTES. Atualizar após implementação e gates; não converter TARGET em CURRENT.
Próxima Task ID, somente após certificação: NFV1-P02-T03.
