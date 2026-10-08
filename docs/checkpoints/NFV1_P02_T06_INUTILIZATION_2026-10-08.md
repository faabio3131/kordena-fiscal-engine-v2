# CHECKPOINT — NFV1-P02-T06 — Inutilização

Data: 2026-10-08 UTC. Produto: FM NFCORE V1.
Repository: faabio3131/kordena-fiscal-engine-v2. Main: main.
Main HEAD de entrada: `6506e3c50dec9e1f948311a13301c6524e26d1b0`.
Branch: `feat/nfv1-p02-t06-inutilization`; branch HEAD/PR/CI finais são os da PR
que contém este registro, evitando SHA circular. Status: IN_PROGRESS / não certificado.
CI main de entrada #658 (37704254327) SUCCESS; Plan Governance #79
(37704254339) SUCCESS; zero PRs abertas. PR #126 closeout T05 MERGED.
Predecessor T05 DONE_CERTIFIED. T06 é o primeiro item pendente; T07 não iniciada.

## Autoridade / CURRENT → TARGET / escopo congelado

AGENTS.md, cronograma inteiro, ledger, CURRENT, padrão mestre e checkpoints P1/P2
regem esta tarefa. Não há ADR separado específico de T06 localizado.
CURRENT: operação inutilizeFiscalRange e document.inutilize já existem; caminho
canônico e contratos de InutilizationRequest/FiscalOperationsClient existem; falta
jornada própria da UI. Root não configura provider/handler real, mantém 503.
TARGET interno: navegação/tela/formulário de Inutilização no mesmo Portal, comandos
no router existente, contrato validado por InutilizationRequest, estado sanitizado
da outbox por scope exato. Cadastro, request ou outbox não são autorização fiscal.

Permissões O/A/OPERATOR existentes preservadas; AUDITOR/BILLING negados; plataforma
não recebe bypass. Sessão/RBAC/CSRF/tenant/unit/environment/Idempotency-Key existentes.
Sem nova política de segurança, papéis, dados pessoais, API, frontend, registry,
fila, Vault, persistência ou regra fiscal. Regras de modelo/série/faixa/justificativa
delegadas ao contrato existente; provider/produção continuam autoridades próprias.

## Mapa de impacto / aceite / testes

- Portal nav/form/request/resultado; nenhuma edição JSON necessária para inutilização.
- Mesmos router/executor/path e domínio de operações; payload whitelisted normalizado.
- Outbox store existente: filtro opcional de operação antes de LIMIT/OFFSET, sem schema novo.
- Leituras tenant/unit/host/env exatos, metadados somente, sem justificativa/payload/key/protocolo raw.
- Form depende de permissão, unidade/ambiente e executor configurado; ausência explícita.
- Retry do mesmo intento conserva chave/conteúdo; 2xx não vira homologação/autorização inventada.
- Testes SQLite/PostgreSQL, role/CSRF/spoof/scope/intervalos/contrato, paginação/sanitização,
  missing handler fail-closed e Playwright HTTPS/router durável sintético sem page.route.
- Gates: plan/secret/migration, Ruff/Mypy, Pytest/PostgreSQL, frontend lint/typecheck/tests/
  build/Playwright, dependency audits, Docker/non-root/smokes/Worker/readiness,
  vulnerability/SBOM/backup-restore e CI remota PR/main; closeout antes de [x].

## Staging / riscos / blockers / ações não realizadas

Railway READ-ONLY: projeto FM NFCORE Staging, environment chamado production dentro
do projeto staging. Portal deployment 35b7aafc-b509-4851-a572-c0bd46781977 e API
c0f8fb2b-30e3-45f8-a814-73c0ba97506b inalterados desde 2026-10-04, 1/1 cada.
Worker 3215f498-0aa1-4ce3-8e61-cc74b72b68b6 desde 2026-10-01, 0/1; Postgres
ce9b66e7-6de7-4c70-9852-8ca1936a719b, 1/1. SHA histórico API/Portal f9b5b2c,
Worker 1c34ba0; deployments idênticos. get_staged_changes null/resources vazios;
environment_status lista patch histórico vazio. Nenhuma variável/secret consultado.
Drift STG-B01..B08 permanece P4/P5/P9/P11; não certifica staging contra main.

Migrations previstas: nenhuma. Provider/secret/signer real: P6/P7; homologação P10.
Replay externo só pode ser certificado com handler/provider real nas tarefas donas;
harness sintético prova somente ingresso/outbox internos. UI reload/crash P02-T07.
Sem blocker humano novo da T06 identificado; integração real continua não confirmada.
Sem deploy/staging write/DNS/infra/custo/secret/cert/CSC real/fiscal oficial/pagamento/
homologação/piloto/cutover/Go-No-Go. PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.
Próxima ação: implementação/testes/gates da própria T06; próxima Task somente após
certificação integral: NFV1-P02-T07. P2 gate permanece NOT MET.

## Implementação e validação local antes da PR

Jornada candidata implementada: superfície/formulário/validação canônica/projeção
sanitizada com filtro antes de paginação. Port outbox evoluído no adapter compartilhado
SQLite/PostgreSQL e memória; sem migration. Request model aceita somente int 55/65,
demais invariantes delegadas a InutilizationRequest. Campos extras/authority rejeitados.
UI exige confirmação dos campos, reusa key/conteúdo em retry e impede alteração de
intento pendente; resposta do executor não é promovida a protocolo oficial.

52 novos casos coletados: 26 SQLite PASS/26 PostgreSQL SKIP local por DSN ausente.
Rerun completo local: 1228 PASS, 131 SKIP, zero FAIL (94.34s). Ruff, Mypy strict
(186 source files), plan checker, migration policy 1..14, secret scan, frontend
lint/typecheck/14 testes/build PASS. CI deve repetir tudo com PostgreSQL/zero SKIP.
Playwright local não iniciou: Chromium ausente; nenhuma asserção removida. Duas
novas jornadas HTTPS/router/SQLite foram adicionadas e devem executar na CI.

Primeiro teste dirigido falhou por duas causas exclusivamente no fixture sintético:
identity_material é tuple (serializado por JSON no hash), e header CSRF anônimo não
aceita None (agora vazio, produz 401 real). Causas corrigidas, mesmos asserts passaram.
Nenhum teste removido/skipped para obter verde. Depreciação TestClient informativa,
visível no log; não suprimida, rejeitada como blocker por não indicar falha funcional.

Zero TODO/FIXME/HACK encontrado em src/portal/diff T06. Harness de recibo na outbox
existe somente em tests/support; não é handler/provider/registry de produção, não
faz dispatch nem declara inutilização aceita. Recompõe/replay em DB real internos;
tráfego/replay fiscal oficial continuam não confirmados, fases P4/P7/P10.
Rollback de código conserva dados da outbox e contratos anteriores; nenhum DROP.
PR/CI main/closeout ainda pendentes: não marcar DONE_CERTIFIED.
