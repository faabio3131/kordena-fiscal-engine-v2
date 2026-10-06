# NFV1-P02-T03 — Parcela de consulta e checkpoint bloqueado

Data: 2026-10-06. Repository: `faabio3131/kordena-fiscal-engine-v2`.
Branch canônica: main. **T03 BLOQUEADA EXTERNAMENTE; NÃO DONE_CERTIFIED.**
Status da parcela de consulta: INTEGRADA / GATES INTERNOS PR E MAIN VERIFICADOS.
Este registro documental permanece condicionado aos seus próprios gates/merge.

## Evidência imutável / GitHub

- main de entrada: `4b0d008d39ef3c579fa0d521864a92a58907b0de`;
- predecessor T02: #117 + closeout #118 MERGED; CI #629/Governance #58 SUCCESS;
- branch da consulta: `feat/nfcore-web-nfv1-p02-t03-client-config`;
- código da consulta: `616549ded6c73ca0df44b1f686c688d8adbcf3b5`;
- HEAD final certificado: `c908848dff0d2ff7f45e33dfa5b2ff51943f54f9`;
- PR #119 MERGED, somente a parcela interna de consulta e o blocker;
- merge/main: `db2a8fb71097eb4e1f6e5919e1eb544c8a3167ac`;
- CI PR #640 SUCCESS: https://github.com/faabio3131/kordena-fiscal-engine-v2/actions/runs/37507161174;
- CI push #639 SUCCESS: https://github.com/faabio3131/kordena-fiscal-engine-v2/actions/runs/37507154500;
- Plan Governance PR #61 SUCCESS: https://github.com/faabio3131/kordena-fiscal-engine-v2/actions/runs/37507161234;
- CI main #641 SUCCESS: https://github.com/faabio3131/kordena-fiscal-engine-v2/actions/runs/37508377264;
- Plan Governance main #62 SUCCESS: https://github.com/faabio3131/kordena-fiscal-engine-v2/actions/runs/37508377293;
- merge técnico interno autorizado pelo dono, clean/mergeable, protected expected_head_sha.

Branch deste checkpoint: `docs/nfv1-p02-t03-blocked-checkpoint`. Seu HEAD/PR são os
da PR que contém este registro; não usar SHA circular. O registro também deve
passar gates e integrar main; isso não certifica a task completa ou sua fase.

## CURRENT → TARGET / escopo / impacto

Antes: certificates/providers/webhooks/integrations indisponíveis, settings básico.
Agora: cinco consultas duráveis no mesmo Portal/router/executor/stores/UoW. Total
16 surfaces genéricas duráveis; cinco restantes: users (T04), usage/billing/plans
(T05), support (T07). Matriz T01 conserva seu baseline histórico, com evolução neste
registro. T03 permanece dona das configurações/formulários/mutações não concluídas.

Referências opacas são metadata, não material verificado. Providers mostram bindings,
não catálogo/readiness. Webhooks mostram destination_id/enabled; SQL da projeção não
seleciona URL/query/path/headers/body. Integrations mostra módulos/bindings, sem
enumerar credenciais/grants/hash de workload. Settings mostra políticas persistidas,
sem inferir aplicação operacional. Cada coleção tem até 100 registros; integrations
combina duas coleções. Binding não tem partição de ambiente no modelo existente:
resposta declara essa limitação, sem inventar isolamento novo para esse objeto.

UI reutiliza filtros/paginação/metadata e declara consulta/alterações pendentes;
nenhum botão de salvar fictício. Nenhuma escrita nova registrada. TARGET integral
(configuração governada com mutações) NÃO alcançado. Leitura não fecha CRUD.

Autoridades: HumanIdentity/AuthenticatedHuman/RBAC/CSRF; DurableControlPlaneService,
CommercialConfigurationService, SecretReference/ProviderBinding/WebhookDestinationConfig,
UnitModuleBinding/RuntimePolicy, FiscalAccountBinding; mesmos stores SQLite/PostgreSQL.
Sem segunda API/auth/sessão/tenant/unidade/RBAC/persistence/frontend/Registry/Vault/fila.
Nenhuma migration nova; schema 1..13 preservado. Inventário exato: diff da PR #119.

Dependência mínima CI: mesmo `scripts/check_nfcore_plan.py` também no workflow de
CI existente; gatilho push já existente foi reutilizado. Gate fortalecido, sem novo
workflow/runner/infra. Indisponibilidade temporária do shell não virou dispensa.

## Gates / segurança / isolamento

CI #640: 1173 Python/PostgreSQL PASS, zero SKIP; 11 frontend PASS; 11 Playwright PASS.
Main #641 repetiu 1173 Python/PostgreSQL PASS/zero SKIP e 11 Playwright PASS,
com todos os gates abaixo SUCCESS no exact merge SHA.
24 novos casos SQLite/PostgreSQL + uma jornada HTTP durável das cinco vistas. Auth,
roles existentes, tenant/unit/environment, sanitização, paginação, recomposição HTTP,
ausência de escrita e leitura incapaz de habilitar produção em unidade HML-only.

Todos os gates PR: plan (59 tarefas, próxima ainda T03), secret/migration policy,
Ruff/Mypy, dependency audits, frontend lint/typecheck/tests/build, Playwright,
Compose/scripts/images/non-root, insecure-production rejection, smokes API/Worker/
Portal, artifact inspection, vulnerability policy sem waiver, SBOM, PostgreSQL
backup/restore e readiness sobre banco restaurado.

Falha #630 no baseline: asserção síncrona de variável de callback de ativação;
`expect.poll` aguarda o mesmo valor. Mesmo token, URL e sucesso exigidos; nenhum
teste desabilitado/retry de suite ou mudança do fluxo de reset. Runs substituídos
cancelados não foram tratados como certificação. CI final exact HEAD obrigatório.

Checkpoint histórico contém limites locais e reprodução posterior: 1110 PASS/63
SKIP (DSN PostgreSQL local ausente). Skips não provaram PostgreSQL; a CI zero SKIP
é a evidência positiva. Testes sintéticos/loopback não provam integração externa.

## Zero pendência invisível / rollback / riscos

Nenhum TODO/FIXME/HACK novo, teste removido/desabilitado, mock/provider fake em root,
secret/certificado/CSC/endpoint privado real, autoridade paralela ou flag provisória.
P2-G08/T03: writes/CRUD restantes pendentes; T03-B01 abaixo. P2-G01 demais surfaces
mantêm owners acima; P2-G09 usuários/política T04; P2-G13 browser recovery T07;
P2-G02 handlers/provider/Vault/signer real P6/P7/P10; audit/observabilidade P9.

Rollback da parcela: reverter código remove novas vistas e preserva configuração
existente; sem down migration/backfill/dados novos de cliente. Backup/restore em CI
não prova rollback de staging; rollout/rollback real continua P5 sob autorização.

## Staging / dependências / blocker / decisão humana

Railway pós-merge READ-ONLY: deployments inalterados. API/Portal SHA
`f9b5b2c5b436045947159f1e76be9303f5a95d90`, 1/1 cada; Worker
`1c34ba001935952f83ec0b065144e0b8311a5650`, 0/1 apesar de Online/SUCCESS;
Postgres 18/1/1/volume 5000 MB; staged patch changes vazio. STAGING_REAL /
VERSION_DRIFT_PRESENT / NOT_CERTIFIED_AGAINST_CURRENT. STG-B01..B08: P4/P5/P9/P11.

**T03-B01 — HUMAN_SECURITY_DECISION_REQUIRED**. C04 requer allowlist/política, mas
CURRENT não define autoridade de aprovação/egress nem proteção DNS/redirect/rede.
AGENTS.md manda parar antes de "mudança de segurança sensível"; padrão mestre §6
antes de "mudança de segurança". O merge de consulta não aprovou política nova.

Recurso exato: dono aprovar/ajustar a tabela DRAFT em
`docs/NFV1_P02_T03_WEBHOOK_SECURITY_POLICY_PROPOSAL_2026-10-06.md`, registrando
aprovador/data/escopo. Proposta: tenant solicita, platform_admin existente aprova
destino exact scoped/versionado; HTTPS/443; sem IP literal/query/redirect; somente
rede pública, DNS revalidado e conexão ao IP validado; default deny/revogação/audit;
mesma policy em cadastro e delivery existentes. DRAFT NÃO IMPLEMENTADO.

Após decisão: continuar ESTA T03, concluir formulários/mutações/audit/idempotência/
versão subordinados às autoridades/catálogos; aplicar policy no delivery; gates,
PR/main/closeout; só então concluir e liberar T04. Nenhuma tarefa independente
posterior está liberada no ledger sequencial. PORTAL_COMMERCIAL_PARITY_CERTIFIED NOT MET.

## Ações não realizadas

Sem deploy/restart/staging migration/produção migration/infra paga/DNS/TLS produtivo,
real secret/credential/certificado/CSC, novo dado pessoal, consulta DNS privada,
entrega de webhook, homologação, fiscal/financeiro real, controlled pilot/cutover/
Go-No-Go. PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO. Próxima ação: decisão T03-B01
e retomada da T03; próxima Task T04 ainda bloqueada.
