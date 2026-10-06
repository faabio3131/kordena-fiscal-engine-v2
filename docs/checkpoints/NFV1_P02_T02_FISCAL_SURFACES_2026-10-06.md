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

Implementação local concluída, ainda SEM certificação remota/merge:
- 12 surfaces duráveis (7 anteriores + 5 fiscais); archive e lifecycle separados,
  emissão/fila com tipos explícitos; sem inferir autorização do archive ou da outbox.
- Unidade/ambiente selecionados propagados e revalidados no backend. Tenant e
  namespace derivados da sessão/runtime; listagens usam partição exata em SQL.
- Cada coleção canônica tem limit 1..100 e offset 0..10000; documents/issuances/errors
  combinam no máximo duas coleções (até 200 linhas/página), sem total inventado.
  Estado de erro filtrado ANTES de LIMIT. UI possui seleção e paginação explícitas.
- Reserva nova exige ExecutionScope; replay e colisão cross-scope/legado rejeitados
  atomicamente. Migração 13 adiciona colunas de escopo no lifecycle e índices; NÃO
  inventa backfill nem altera regra fiscal, numbering ou conteúdo histórico.
- Capabilities delegadas à autoridade existente, com profile/context/vigência. Root
  continua sem matriz: estado blocked. CONTRACT_ONLY não é promovido a readiness.
- UI permite apenas operações configuradas e permissões declaradas pelo backend;
  CSRF/idempotência permanecem server-side. Retry com conteúdo igual preserva a key;
  tentativa pendente impede mudança silenciosa do pedido.
- Filtro do contrato também restringe audit a unidades permitidas/selecionadas,
  sem novo papel/autoridade. Certificação transversal permanece P02-T04.

Validação local inicial: Ruff/Mypy (180 arquivos), secret scan, migration policy,
frontend lint/typecheck/11 testes/build PASS. Pytest então 1095 PASS/48 SKIP (DSN
PostgreSQL ausente); novos casos readiness/paginação adicionados depois, a suíte
final será registrada em closeout. Esses skips NÃO certificam PostgreSQL.
Teste HTTP via HTTPS loopback + router real + SQLite: cinco GETs 200; falha sintética
após commit 503 → retry mesma key 200 reserved_internal_replay; sem emissão/provider.
Playwright local não certificado (Chromium ausente após download truncado); CI remota
obrigatória tem 7 jornadas anteriores + 3 jornadas fiscais duráveis novas.

Auditoria zero pendência invisível do diff: nenhum TODO/FIXME/HACK novo, sem teste
removido/desabilitado. Expectativas de migration-version nos testes foram atualizadas;
reconstruções históricas removem 13 também para provar upgrade exato. O teste de
surface não composta usa certificates, pois documents agora é implementada; novas
jornadas cobrem documents real. Mocks antigos permanecem apenas provas de UI;
novos E2E fiscais não usam page.route. SQLite/test TLS/handler de reserva vivem
exclusivamente em tests, loopback e diretório temporário; nenhum provider fake no root.

Pendência explícita P2-G13 / P02-T07: a key de tentativa pendente vive na página;
recuperação após reload/crash do browser exige jornada governada adicional. Nenhum
handler externo está ativo nesta tarefa; não certificar replay fiscal externo por esse
harness. P2-G02/P6/P7/P10 continuam bloqueando integração real. Perfis/matriz
operacionais ausentes não são supridos por regras sintéticas dos testes.

Rollback: migração aditiva mantém colunas/tabelas antigas; reversão de código conserva
os dados novos e bloqueia surfaces antes indisponíveis. Não executar down migration,
DROP ou atribuição de scope a legado. Rehearsal de backup/restore/containers será
provado novamente pela CI; rollout/rollback em staging pertence a P5 e requer deploy
autorizado. Nenhuma migration aplicada a staging/produção.

PR/HEAD/CI final/main/closeout: PENDENTES. Não converter TARGET em CURRENT.
Próxima Task ID, somente após certificação: NFV1-P02-T03.

Refinamento da revisão T02: Emissões inclui status/generation da autoridade de
idempotência, após descobrir document_id exclusivamente por lifecycle scoped; não
expõe key/fingerprint/rejection_reason. Nova key não pode reutilizar document_id
existente e transformar colisão em reserva FRESH; a transação é revertida. Índice
aditivo por document_id/generation incluído na migração 13. Teste correspondente.
Suíte local final antes desse refinamento: 1097 PASS/50 SKIP (DSN ausente).

CI #624 FAIL (HEAD 46fbc245): três causas no gate PostgreSQL; nenhuma certificação.
Fixture v8 agora reconstrói schema 1..8 completo e preserva lifecycle legado NULL
no upgrade; expectativa da migration12 inclui13; query de overlap de profile usa
CAST do parâmetro NULL para TEXT (SQLite/PostgreSQL), sem relaxar conflito/vigência.
Nenhum teste/gate removido ou skip novo para contornar essa falha. Reexecutar CI.
