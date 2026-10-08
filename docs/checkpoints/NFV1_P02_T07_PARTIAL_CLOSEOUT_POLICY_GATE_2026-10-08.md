# CHECKPOINT — NFV1-P02-T07 — closeout parcial / T07-B01

Data: 2026-10-08 UTC. Repository: faabio3131/kordena-fiscal-engine-v2.
Main: main; HEAD da parcela `3181dcdf614d8b22d8fab9e2238050d0c2207772`.
Branch implementação: feat/nfv1-p02-t07-premium-ux; HEAD
`95c8e4b85bf61cf1d761d3a0785e1e6da79c9340`; PR #129 MERGED.
Árvore branch/main idêntica: `1012f3958ab4966345772b9c5d78d7db75433acf`.
Branch documental: docs/nfv1-p02-t07-partial-closeout; seu HEAD/PR/gates exatos
são os da PR contendo este documento, evitando SHA circular.
Status: PARCELA INTEGRADA COM CI PR/MAIN SUCCESS; T07 BLOQUEADO INTERNO em T07-B01.

## Autoridade / CURRENT → TARGET / escopo / impacto / aceite

T06 DONE_CERTIFIED: #127/#128, main fdf9855c7b8048870ff89d91d4d03797d2f11c49,
CI #662/Governance #83 SUCCESS. T07 é a primeira incompleta. AGENTS, cronograma,
ledger/CURRENT, padrão, matriz P2 e closeout T06 governam. Checkpoint detalhado:
NFV1_P02_T07_UX_AND_POLICY_GATE_2026-10-08.md. CURRENT: UX parcial integrada,
recuperação após reload/crash não certificada. TARGET restante: política aprovada,
recuperação durável provada e aceite integral T07/P2. Não promover TARGET a CURRENT.
Escopo documental congelado: CURRENT, ledger, matriz e este checkpoint; nenhum
runtime, requisito, migration, teste ou gate alterado nesta PR. Aceite: evidência
exata PR/main, blocker persistido e gates próprios do closeout verdes.

## Mudanças / autoridades reutilizadas / arquivos / migrations

PR #129: support sobre unidades/configuração autorizadas no executor existente,
filtros server-side, projeção sanitizada sem SLA/saúde/ticket inventados. Portal
atual: detalhes mobile/teclado, labels pt-BR, foco/aria-busy/alert/read retry,
readiness negativa bloqueada, submit in-flight e consulta preserva key pendente.
Logos/paleta/HTML/CSS base preservados. Reutilizados DurableHumanPortalExecutor,
sessão/RBAC/router/UoW/control-plane/autoridades fiscais. Arquivos runtime:
portal/app.js, portal/runtime.css, web/portal_runtime.py; testes support/premium_ux;
workflow adiciona upload obrigatório de screenshots; runbook WP_WEB_08 atualizado.
Migrations: nenhuma. Rollback de código preserva dados/contratos; nenhum deploy/
rollback operacional externo realizado ou certificado por estes testes.

## CI / testes / evidência / limitação da publicação documental

CI PR #665 (37733283484, job 113167055672)/Governance #86 (37733283404) SUCCESS.
CI main #666 (37733952353, job 113169161061)/Governance #87 (37733952332) SUCCESS.
HEADs exatos acima: 1371 Python/PostgreSQL, 14 frontend e 26 Playwright PASS,
zero SKIP; 41 steps SUCCESS em PR e main. Gates: plan/migrations/secrets, Ruff,
Mypy/Pytest/Pg, dependency audits, frontend lint/typecheck/tests/build, Playwright,
compose/scripts/Docker/non-root, fail-closed production profile, API health/readiness,
Worker/Portal smoke, secret-artifact scan/vulnerability policy/SBOM, backup/restore
PostgreSQL e readiness no banco restaurado. Closeout exige CI PR/main própria
SUCCESS; SHA/resultados finais persistidos na PR documental após CI main.

Local implementação: 1234 PASS/137 SKIP/zero FAIL (Pg ausente, não certificação);
Ruff/Mypy186/frontend14/build/plan/secret/migration/syntax/diff PASS. Chromium local
retornou ZIP inválido, sem enfraquecer CI. Plan/secret/diff PASS na preparação
local destes quatro registros. Execução local deixou de responder ao atualizar
os campos finais de evidência, inclusive comandos read-only triviais; resultado
da última tentativa de commit local não confirmado. Publicação documental feita
pelos objetos Git canônicos, a partir dos arquivos no HEAD main certificado,
com alteração somente de evidência textual; nova CI remota integral obrigatória.
Não alegar rerun local final nem sincronização de árvore local não confirmados.

CI #663: 23 Playwright PASS/3 FAIL por asserção sobre workspace inteiro incluindo
unit-b no seletor legítimo OWNER. Corrigido alvo .grid-list, preservadas negativas
e adicionada confirmação HTTP exata [unit-a]. CI #664 completa SUCCESS, 1371/14/26.
Captura fullPage após scroll de foco mostrava skip-link fora do viewport sobre
navegação; testados foco/Enter → main/details/skip fora do viewport e normalizado
scroll=0 antes da captura. CI #665 PASS, sem autorização/teste/gate reduzido.

Artifact #665: 11530118810, três screenshots 320/390/1280px baixadas/inspecionadas;
digest ZIP sha256:ffcf4bc0783bf2bbfbf6531da73935159614c830f17e39ccb99f080f6edd6737
conferido. Logo/paleta/layout, detalhes legíveis, foco e bloqueio preservados;
sem overlay indevido na captura normalizada. Retenção GitHub até 2026-10-22;
IDs/digest/testes/revisão persistem no Git/PR. HTTP durável loopback sintético;
dois casos UI-only declarados não provam runtime externo. Warnings preexistentes
TestClient/eventual alias Pydantic/deprecações actions visíveis, sem supressão;
rejeitados como blocker funcional da parcela: contratos/gates/audits verdes,
sem redução de política de vulnerabilidade ou assertions de segurança.

## Segurança / tenant/unit / staging / zero pendência invisível

RBAC/sessão/CSRF/tenant/unit/env server-side/Idempotency-Key preservados; support
exige portal.read existente. Sem segredo/payload/PII novo, segunda API/auth/session/
autoridade/fila/registry/Vault/persistência/frontend. Storage proibido e nova
política de receipts DRAFT, não implementada. Dados de testes somente sintéticos.
Staging reconsultado READ-ONLY após merge: projeto b84b290d-f3b4-46a1-9023-0b761cb96b0d,
environment c9878b9b-62b2-4a97-b8ba-743c8a3e99ec (nome production no projeto
FM NFCORE Staging). Portal 35b7aafc/API c0f8fb2b 1/1; Worker 3215f498 0/1 apesar
de Online/SUCCESS; Pg ce9b66e7 1/1; mesmos deployments históricos. Staged null,
resources/sharedVariables vazios; pending patch 8d720a42 histórico com changes=[].
Nenhuma variável/secret/log consultado. Drift STG-B01..B08 pertence P4/P5/P9/P11;
staging não certificado contra main.
Auditoria: sem TODO/FIXME/HACK novo relevante nos caminhos alterados; support
composto via router/executor real e UI usa filtros/HTTP existentes; sem botão
fake/flag provisória/config FM universal/serviço paralelo. P2-G11 configuração
support resolvida; SLA/atendimento/health externo P9/P12. P2-G14 parcela visual/
labels/teclado provada; P2-G17 compatibilidade documentada; P2-G18 replay/concurrency
preservado e prova operacional P3. P2-G13 crash/reload continua T07-B01. Limitação
local de publicação registrada acima; CI remota final permanece obrigatória.

## Blocker / decisão humana / ações não realizadas / próxima task

T07-B01: aprovar/ajustar como conjunto
NFV1_P02_T07_FISCAL_INTENT_RECOVERY_POLICY_PROPOSAL_2026-10-08.md.
Recurso: POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION para T07, mesma conta/
session_epoch/scope/permissão, 24h, nenhum bypass/storage, receipt/fingerprint/key
original protegidos no mecanismo canônico e fail-closed. AGENTS exige decisão
antes de "mudança de segurança sensível"/"tratamento novo de dado pessoal";
padrão §6 antes de "mudança de segurança". Associação conta → intento/retomada
introduz política nova; aprovação T03 não a aprova. Implementação dependente parada.
Sem deploy/staging write/produção/infra/DNS/TLS produtivo/migration produtiva/secret/
credencial/cert/CSC real/custo/fiscal oficial/pagamento/KYC/homologação/piloto/cutover/
Go-No-Go. PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO. T07/P2 NOT MET, ledger T07
`[ ] bloqueado interno`; P3 não iniciada. Próxima ação: gates do closeout e decisão
T07-B01. Próxima Task ID continua NFV1-P02-T07; P03-T01 só depois de T07 certificada.
