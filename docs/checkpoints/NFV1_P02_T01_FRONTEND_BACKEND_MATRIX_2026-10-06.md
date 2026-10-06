# CHECKPOINT — NFV1-P02-T01 — Matriz frontend × backend

Data: 2026-10-06.
Produto: FM NFCORE V1.
Repository: faabio3131/kordena-fiscal-engine-v2.
Main: main.
Main HEAD de entrada: 0e5be77267a800384d111c03e30705d95bdb0d28.
Branch: docs/nfv1-p02-t01-frontend-backend-matrix.
Branch HEAD: registrar SHA certificado na PR/closeout; este arquivo integra o próprio commit.
PR/status: #115 OPEN/DRAFT; sem declaração de conclusão antecipada.
CI PR: pendente; obrigatório no exact HEAD.
CI main de entrada: #618 SUCCESS; Plan Governance #47 SUCCESS.
Predecessor: P01-T04 DONE_CERTIFIED; PR #113 e closeout #114 mergeados.

## CURRENT → TARGET / escopo / impacto

CURRENT: P1 certificado internamente; Portal com 7 projeções genéricas duráveis,
14 não compostas, 3 superfícies de plataforma (checkout condicionado ao adapter).
TARGET T01: matriz das 24 superfícies da navegação + inutilização, com authority,
endpoint, projection, mutations, RBAC, tenant/unit, estados e audit trail.
Escopo congelado: auditoria/matriz/documentação. Sem implementação das tarefas posteriores.
Mapa de impacto: quatro arquivos documentais; nenhum contrato, runtime ou segurança alterados.

## Mudanças / autoridades reutilizadas

- matriz completa em `docs/NFCORE_V1_P02_FRONTEND_BACKEND_MATRIX_2026-10-06.md`;
- gaps P2-G01..G18 ligados a tarefas canônicas;
- CURRENT reconciliado com P1 certificado e próxima tarefa T01;
- ledger: somente P02-T01 em execução;
- HumanIdentity/session/RBAC, DurableHumanPortalExecutor, Control Plane, FiscalApplicationService,
  CanonicalFiscalOperationPath, ProviderRegistry/readiness, vault e subscription canônicos
  preservados como autoridades; nenhuma segunda autoridade construída.

Arquivos: matriz, este checkpoint, CURRENT e ledger.
Migrations: nenhuma.

## Critérios / testes / gates

Aceite: cobertura 24+1; 15 superfícies exigidas pelo cronograma; identificação exata
das 14 projeções genéricas indisponíveis; RBAC/estados/auditoria por superfície;
gaps com ownership; sem overclaim; Plan Governance e CI verdes.

Testes locais/evidência:
- cobertura estrutural: PASS (24 navegação + inutilização; 21 genéricas, 7 duráveis, 14 indisponíveis);
- `python3 scripts/check_nfcore_plan.py`: PASS, 59/59;
- repository secret scan: PASS;
- migration policy: PASS, versões 1..12, cakto_schema=2;
- Ruff: PASS; Mypy: PASS, 179 source files;
- Pytest Python 3.12 local: 1085 PASS, 39 SKIP (PostgreSQL DSN local ausente), 1 warning upstream;
- os skips locais não certificam PostgreSQL; CI Python 3.11 com PostgreSQL obrigatório precisa executar a suíte completa;
- frontend lint/typecheck/build: PASS; frontend tests: 11 PASS; npm audit: 0 vulnerabilidades;
- download Chromium local falhou (arquivo recebido truncado/inválido); Playwright local não executado;
- CI remota: aguardando nova execução no HEAD final; nenhum gate substituído/enfraquecido.
CI completa remota obrigatória, incluindo PostgreSQL, frontend/E2E, containers/non-root,
security/dependency/vulnerability scans, SBOM e backup/restore.
Documento/contrato/mocks não comprovam provider ou staging real.

## Segurança / tenant / unidade

- nenhuma credencial/secret/certificado/CSC ou dado real adicionado;
- nenhuma permissão/autoridade nova;
- isolamento por tenant da sessão preservado;
- lacunas CURRENT de unit_id em listagem e audit unit-scoping registradas como P2-G04/G05;
- UI não é autoridade; handler fiscal externo ausente permanece 503 fail-closed;
- política nova de administração de usuários deve passar pelo gate humano se necessária.

## Staging — somente leitura

Railway: FM NFCORE Staging; environment c9878b9b-62b2-4a97-b8ba-743c8a3e99ec.
API e Portal: f9b5b2c5b436045947159f1e76be9303f5a95d90; 1/1 cada.
Worker: 1c34ba001935952f83ec0b065144e0b8311a5650; 0/1 running.
Postgres 18: 1/1; volume persistente 5000 MB.
Sem alterações staged substantivas; patch vazio changes=[] em pendingWork.
Classificação: STAGING_REAL / VERSION_DRIFT_PRESENT / NOT_CERTIFIED_AGAINST_CURRENT.

## Blockers / riscos / decisões humanas

T01 não requer credencial/decisão externa. CI/merge/main/closeout pendentes impedem certificação.
Gaps P2-G01..G18 e STG-B01..B08 permanecem com ownership na matriz/cronograma.
Dependências externas: P6 vault real; P7 provider real; P8 canal comercial real;
P10 homologação; P11 produção; P12 Go/No-Go humano.
Autorização de 2026-10-06 permite merge técnico interno condicionado a CI/Plan Governance
SUCCESS e expected head certificado; não autoriza deploy ou operação externa.

## Ações NÃO realizadas

Sem deploy, restart, migration externa, DNS, mudança de visibilidade, secret real,
homologação oficial, compra/emissão fiscal real, cutover ou produção.
PRODUCTION_APPROVED=NO. COMMERCIAL_LIVE=NO.

Gate de saída da tarefa: PENDING até gates/merge/main/closeout.
Gate de fase PORTAL_COMMERCIAL_PARITY_CERTIFIED: NOT MET.
Próxima ação: certificar T01; somente depois iniciar NFV1-P02-T02.
