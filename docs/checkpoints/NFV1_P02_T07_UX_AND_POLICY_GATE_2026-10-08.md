# CHECKPOINT — NFV1-P02-T07 — Premium UX / gate de recuperação

Data: 2026-10-08 UTC. Repository: faabio3131/kordena-fiscal-engine-v2.
Main: main; HEAD de entrada `fdf9855c7b8048870ff89d91d4d03797d2f11c49`.
T06 DONE_CERTIFIED: implementação #127 e closeout #128 MERGED; CI main #662
(37729723863) e Plan Governance #83 (37729723843) SUCCESS no HEAD de entrada;
1359 Python/PostgreSQL, 14 frontend e 21 Playwright PASS/zero SKIP. Zero PRs abertas.
Branch: feat/nfv1-p02-t07-premium-ux; HEAD/PR finais são os da PR contendo este
checkpoint, sem SHA circular. CI PR/main desta parcela pendente. T07 não certificada.

## Autoridade / CURRENT → TARGET / escopo congelado / impacto

AGENTS, cronograma inteiro/ledger, padrão mestre, CURRENT, matriz P2 e closeout T06
reabertos; T07 é o primeiro item incompleto. Nenhum ADR separado T07 localizado;
composição P1 e design premium existentes preservados. CURRENT: suporte sem projeção,
detalhes fiscais sem CSS dedicado, labels técnicas, bloqueios por substring e retry
somente em memória. TARGET desta parcela: UX/mobile/acessibilidade/bloqueios e
suporte de configuração sanitizada; política de recuperação proposta, não implementada.

Escopo: Portal app/runtime CSS, projeção support no executor existente, testes
SQLite/PostgreSQL/Playwright, evidência visual CI e registros/runbook. Preservar
logos/paleta/layout, papéis/permissões e proibição de storage; nenhuma nova segurança,
dado pessoal, preço, provider, fila, API ou regra fiscal implementados nesta parcela.
Sem migrations. Mapa: UI/detail/error/busy/retry-read/duplo envio, surface support,
CI adiciona upload obrigatório das screenshots de teste, documentação do blocker.

Aceite da parcela: scope real support sem SLA/health inventado; filtros/unit/env,
mobile 320/390/1280, details por teclado, labels pt-BR, readiness negativa bloqueada,
erro com retry de leitura; tests/gates completos verdes antes de merge. Não é aceite
integral T07 nem PORTAL_COMMERCIAL_PARITY_CERTIFIED. P3 não iniciada.

## Mudanças / autoridades / arquivos / validação

Reutilizados DurableHumanPortalExecutor, sessão/RBAC/router/scope/UoW/control-plane,
Portal atual e identidade visual aprovada. support lê somente unidades/configuração
autorizadas e declara suporte/produção/health externos não confirmados; sem tickets/SLA.
CSS acessível de detalhes/checkbox/form/mobile, foco visível, redução de movimento
preservada; loading aria-busy/status, erro alert/retry-read; submit fiscal in-flight
bloqueado. Readiness NOT_APPROVED/NOT_READY não ganha tratamento positivo por substring.

Arquivos: portal/app.js, portal/runtime.css, web/portal_runtime.py, testes T07,
.github/workflows/ci.yml, runbook WP_WEB_08, proposta de política, matriz/CURRENT/ledger.
Migrations: nenhuma. Rollback preserva dados e contratos anteriores.
Testes locais/CI finais devem ser registrados abaixo/na PR; não promover skips locais.
Chromium local não pôde ser instalado: download retornou ZIP inválido; CI deve
executar Chromium/Playwright e publicar screenshots obrigatórias. Não desabilitar gate.

## Segurança / staging / blockers / riscos / decisões humanas

Tenant/unit/env continuam server-side; support exige portal.read existente;
nenhum segredo/payload/link privado/ticket/PII novo projetado. Browser storage proibido;
recovery URL fragment e compatibilidade query mantidos, removidos da URL imediatamente.
Dados de testes somente sintéticos; mocks UI-only não são prova de integração real.

Staging reconsultado READ-ONLY: Portal/API 1/1 nos deployments históricos 35b7aafc/
c0f8fb2b; Worker 0/1 3215f498; Pg 1/1 ce9b66e7. Staged changes null/resources vazios;
pending patch histórico vazio. Nenhuma variável/secret/log consultado. Drift
STG-B01..B08 permanece P4/P5/P9/P11; staging não certificado contra main.

T07-B01: política para associação conta → intento e retomada fiscal após reload/crash
não aprovada. Implementação dependente PARADA; não enfraquecer teste que proíbe
storage. Proposta concreta: docs/NFV1_P02_T07_FISCAL_INTENT_RECOVERY_POLICY_PROPOSAL_2026-10-08.md.
AGENTS exige decisão antes de mudança de segurança sensível/dado pessoal; padrão §6
antes de mudança de segurança. Aprovação da política como conjunto é o recurso exato.
P2-G11 parcela de configuração tratada; SLA/atendimento operacional P9/P12 externos.
P2-G13 crash/reload continua aberto em T07; P2-G14 restante visual/labels e P2-G17
compatibilidade documentados sem excluir links válidos. P2-G18 replay/concurrency
comercial preserva authorities/expected_version; validação operacional P3.

Sem deploy/staging write/produção/migration produtiva/secret/cert/CSC real/DNS/infra/
custo/fiscal oficial/pagamento/homologação/piloto/cutover/Go-No-Go.
PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO. T07/P2 NOT MET.
Próxima ação: concluir gates da parcela, persistir evidência e solicitar política
T07-B01. Próxima Task liberável somente após T07 certificada: NFV1-P03-T01.

## Validação local pré-PR e revisão da parcela

Suite completa local: 1234 PASS, 137 SKIP, zero FAIL (100.24s). PostgreSQL ausente
localmente; CI deve executar 1371 Python/PostgreSQL sem SKIP. Directed support:
6 SQLite PASS / 6 PostgreSQL SKIP local. Ruff/Mypy strict 186 arquivos, frontend
lint/typecheck/14 testes/build, syntax E2E, secret scan, migration policy e plan PASS.
Cinco jornadas T07 adicionadas: 3 HTTP durável em 320/390/1280px e 2 UI-only
explicitamente sintéticas para negative readiness/error-read retry e submit lock/
preservação da key após consulta. Total esperado Playwright 26, ainda não certificado.
Screenshots CI obrigatórias nas 3 larguras; identidade aprovada/CSS base/HTML preservados.

Falhas locais corrigidas pela causa: anotação de retorno no helper recursivo text
exigida pelo typecheck e formatação de linhas do teste exigida por Ruff. Nenhum
assert/gate enfraquecido. Download Chromium inválido continua limitação local,
sem skip/supressão em CI. Warning TestClient preexistente visível.

Auditoria encontrou consulta fiscal apagando pending key de mutação na memória;
correção mantém o mesmo intento até uma mutação bem-sucedida, e teste UI comprova
consulta intermediária + mesma key. Não resolve T07-B01 após reload/crash.
Varredura TODO/FIXME/HACK relevante sem ocorrência nova; forms/routes realmente
chamam o Portal existente, dados de suporte são configuração e não saúde/SLA.
API/Portal/Worker staging continuam SHA divergente e sem certificação atual.

## Falha CI investigada e corrigida

CI candidata #663 (37731471523), HEAD 30f7a271cb0eb59501ec7eaedcddc7b4cc2e6c30:
1371 Python/PostgreSQL PASS/zero SKIP, frontend 14 PASS; Playwright 23 PASS/3 FAIL.
Causa: testes novos verificavam todo #workspace para ausência de unit-b, incluindo
o seletor em que OWNER legitimamente possui unit-a e unit-b. Corrigido o alvo para
os registros .grid-list, preservadas as asserções negativas de isolamento e
adicionados count=2 do seletor e confirmação HTTP exata [unit-a]. Nenhum teste
removido/skipped, nenhuma autorização ou gate reduzido; repetir CI integral.
