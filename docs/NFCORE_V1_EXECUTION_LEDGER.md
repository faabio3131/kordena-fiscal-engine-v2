# FM NFCORE V1 — LEDGER CANÔNICO DE EXECUÇÃO

> Este arquivo registra **estado e prova** das tarefas definidas em `docs/NFCORE_V1_COMPLETION_MASTER_EXECUTION_SCHEDULE_2026-10-05.md`. Ele não redefine escopo. O cronograma continua sendo a autoridade de escopo, dependências, critérios e gates. O validador exige correspondência exata de IDs e ordem.

## Cabeçalho

- **Objetivo:** executar integralmente o cronograma mestre de conclusão do FM NFCORE V1 sem pular tarefas e sem marcar conclusão sem prova.
- **Dono / aprovador:** dono do projeto — padrão aprovado por instrução explícita em 2026-10-05.
- **Estado:** EM EXECUCAO
- **Fora de escopo:** alterar o conteúdo técnico das tarefas sem atualização prévia do cronograma; merge/deploy/produção não autorizados; criação de segunda autoridade.
- **Pode fazer sem perguntar:** auditoria read-only, implementação e testes estritamente dentro da tarefa ativa, criação de branch/PR Draft e atualização de evidência documental.
- **Deve parar e perguntar:** preço/produto, segurança nova, dado pessoal, gasto, conta real, secret/certificado real, outro repositório, mudança de visibilidade, merge quando não autorizado, deploy, migration produtiva, DNS, fiscal real/produção, operação irreversível.

## Itens — ordem obrigatória, um por vez

### 1. NFV1-P00-T01 — Reconciliar documentação CURRENT

- [x] **Estado:** concluído
- **Objetivo:** executar exatamente a tarefa NFV1-P00-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** nada
- **Entregar:** tudo que o cronograma exige para NFV1-P00-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P00-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PR #101; CI #581; merge SHA 824842f2ed5586351a75cd57fc765c716899bb9e; Plan Governance #10.

### 2. NFV1-P00-T02 — Congelar matriz de capacidades

- [x] **Estado:** concluído
- **Objetivo:** executar exatamente a tarefa NFV1-P00-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P00-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P00-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P00-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PR #103; CI #586; merge SHA 09dd77798122202ba1b7e548818b879556bec0ae; Plan Governance #15.

### 3. NFV1-P00-T03 — Registrar staging drift

- [x] **Estado:** concluído
- **Objetivo:** executar exatamente a tarefa NFV1-P00-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P00-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P00-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P00-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** staging permanece em drift; isso foi registrado como blocker com ownership formal e não foi mascarado como resolvido.
- **Decisões do dono pendentes:** nenhuma para o fechamento do P0.
- **Prova:** PR #105; CI #597; merge SHA 3837d1e6b5a3c38e3aa2ceb032fb952fab700a4c; Plan Governance #26; staging drift register STG-B01..STG-B08.

### 4. NFV1-P01-T01 — Identificar composição canônica

- [x] **Estado:** concluído
- **Objetivo:** executar exatamente a tarefa NFV1-P01-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P00-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P01-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P01-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** T01 identificou e congelou a composição canônica, mas não implementou o composition root; `BridgeSecurityBoundary`, `BridgeRequestExecutor` e `PortalOperationExecutor` produtivos continuam pendentes para P01-T02. Provider transport real e ExternalSecretClient concreto permanecem fora de P1 e fail-closed.
- **Decisões do dono pendentes:** nenhuma para o fechamento da T01.
- **Prova:** PR #107; CI #603; merge SHA 4f896762674508498e3261aaf2d36480f284dfa2; Plan Governance #32; checkpoint `docs/checkpoints/NFV1_P01_T01_CLOSEOUT_2026-10-06.md`.

### 5. NFV1-P01-T02 — Implementar composition root

- [x] **Estado:** concluído
- **Objetivo:** executar exatamente a tarefa NFV1-P01-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P01-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P01-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P01-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** provider transport real, ExternalSecretClient concreto, credenciais S2S reais e produção fiscal permanecem ausentes e fail-closed; staging continua em drift conhecido e pertence às fases próprias.
- **Decisões do dono pendentes:** nenhuma para o fechamento da T02. T03 continua bloqueada até este closeout entrar em main.
- **Prova:** PR #109; CI #607; merge SHA a051af1b0b958e36669b3aea90c0430217b9b21f; Plan Governance #36; checkpoint `docs/checkpoints/NFV1_P01_T02_CLOSEOUT_2026-10-06.md`.

### 6. NFV1-P01-T03 — Certificar autoridade

- [x] **Estado:** concluído
- **Objetivo:** executar exatamente a tarefa NFV1-P01-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P01-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** certificar tenant spoofing, unit spoofing, cross-tenant, cross-unit, RBAC, sessão, S2S e idempotência no caminho fiscal composto.
- **Não fazer:** não antecipar T04; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar deploy, produção ou ação externa não autorizada.
- **Critério de aceite:** todas as autoridades permanecem server-side/fail-closed; escopo S2S exige binding durável exato; browser não define tenant/role/permission; mutações exigem e propagam idempotency key; nenhum gate transversal violado.
- **Verificação:** testes dirigidos de autoridade + suíte existente + `python3 scripts/check_nfcore_plan.py` certificados em PR e pós-merge.
- **Riscos / não confirmado:** provider transport real, secret backend real e produção fiscal permanecem fora do escopo; staging continua em drift conhecido. A T03 certifica autoridade interna, não homologação externa nem API fiscal completa.
- **Decisões do dono pendentes:** nenhuma para o fechamento da T03. T04 permanece bloqueada até este closeout entrar em main.
- **Prova:** PR #111; head certificado `41f8b92afbaae589b36f0a4f96322f8372776640`; merge SHA `400aef6c7ac8914c76bfa914ac4586dc77181daf`; Plan Governance #40 e pós-merge #41; CI #611 e pós-merge #612; checkpoint `docs/checkpoints/NFV1_P01_T03_CLOSEOUT_2026-10-06.md`.

### 7. NFV1-P01-T04 — Certificar API fiscal

- [x] **Estado:** concluído
- **Objetivo:** certificar emissão, consulta, cancelamento, inutilização, reconciliação, capabilities e archive reference sobre o runtime fiscal canônico, sem ampliar escopo.
- **Depende de:** NFV1-P01-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** matriz integrada das sete rotas Bridge do launch-scope, status/operation IDs, idempotência, scope interno, fail-closed sem dependência e readiness sem overclaim.
- **Não fazer:** não antecipar P2/P6/P7; não criar provider/secret/signer paralelo; não usar synthetic/fake como prova de integração externa real; não executar deploy, homologação ou produção.
- **Critério de aceite:** sete operações canônicas atravessam um único path quando dependências são explicitamente injetadas em teste; ausência de dependência real retorna FISCAL_RUNTIME_NOT_READY; mutações exigem idempotência; perfil declara provider/secret/signer externo como não configurados; nenhum gate transversal violado.
- **Verificação:** testes T04 + contratos Bridge + suíte completa + `python3 scripts/check_nfcore_plan.py` certificados na PR e novamente pós-merge.
- **Riscos / não confirmado:** esta tarefa certifica a API e integração interna; não prova FiscalProviderTransport real, ExternalSecretClient real, signing operacional externo, homologação oficial, staging CURRENT ou produção.
- **Decisões do dono pendentes:** nenhuma para o fechamento da T04. P02-T01 permanece bloqueada até este closeout entrar em main.
- **Prova:** PR #113; head certificado `d4062ac5be070519e80ca35286b9f1892f800405`; merge SHA `b589f1170d002ca8d248ceb889385a8c32b989d3`; Plan Governance #44 e pós-merge #45; CI #615 e pós-merge #616; checkpoint `docs/checkpoints/NFV1_P01_T04_CLOSEOUT_2026-10-06.md`.

### 8. NFV1-P02-T01 — Matriz frontend x backend

- [x] **Estado:** concluído
- **Objetivo:** registrar authority, endpoint, projection, mutações, RBAC, tenant/unit, estados e audit trail de todas as superfícies P2 e da navegação CURRENT.
- **Depende de:** NFV1-P01-T04 concluído e certificado; closeout PR #114 mergeado; main de entrada `0e5be77267a800384d111c03e30705d95bdb0d28`, CI #618 e Plan Governance #47 SUCCESS.
- **Entregar:** matriz `docs/NFCORE_V1_P02_FRONTEND_BACKEND_MATRIX_2026-10-06.md`, cobertura 24 itens de navegação + inutilização, gaps P2-G01..G18 com ownership e checkpoint T01.
- **Não fazer:** não implementar T02 ou posteriores; não criar autoridade paralela; não transformar mocks em integração real; não fazer deploy ou operação externa.
- **Critério de aceite:** 15 superfícies launch-scope e todas as surfaces CURRENT cobertas nos oito eixos; disponibilidade e integração separadas; mutações/gates identificados; gaps atribuídos; CI/Plan Governance verdes; merge/main/closeout antes de concluir.
- **Verificação:** cobertura frontend × permissões × executor × matriz; secret scan; migration policy; `python3 scripts/check_nfcore_plan.py`; CI completa remota no exact HEAD e pós-merge.
- **Riscos / não confirmado:** 14 projeções genéricas não compostas; audit sem filtro de unidade; seleção unit_id não propagada; UI não filtra todos os papéis; E2E mock não prova runtime; gaps e tarefas donas constam na matriz. Staging em drift; produção não aprovada.
- **Decisões do dono pendentes:** nenhuma para T01; política nova de segurança/usuários e qualquer deploy/secret/fiscal real seguem gates humanos específicos.
- **Prova:** PR #115; HEAD `46b92811d52ab03864dd35377f3f918c31e5f83b`; merge SHA `d38226b66b4a56bbd507b4b74ed20f9d6b94e0fb`; CI #620 (PR) e CI #621 (main) SUCCESS; Plan Governance #49 (PR) e #50 (main) SUCCESS; checkpoint `docs/checkpoints/NFV1_P02_T01_CLOSEOUT_2026-10-06.md`.

### 9. NFV1-P02-T02 — Superfícies fiscais

- [x] **Estado:** concluído
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** cinco projeções fiscais duráveis no Portal existente, filtros de unidade/ambiente, metadados sanitizados, readiness governado/bloqueado, reserva com escopo canônico, migração aditiva 13, UI/paginação/retry e testes dirigidos + E2E HTTP durável.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** testes tenant/unit/host/environment, auth/RBAC/CSRF, colisão/replay/legado, paginação/erro, readiness; Python/PostgreSQL, frontend/Playwright, migration/secret policy, containers/smokes/audits/SBOM/backup-restore; CI PR/main e `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** lifecycle legado sem escopo recuperável não pode ser exposto; readiness/handlers externos ausentes; staging em drift. Consultar checkpoint T02 para tratamento e ownership.
- **Decisões do dono pendentes:** nenhuma para T02; política de configuração/usuários será revisada nas tarefas donas; deploy/secret/fiscal real seguem gates humanos.
- **Prova:** PR #117 MERGED; HEAD `06def0c237dcbc0856441e88c811443e902b7c34`; merge/main `f5bfbbb91ac7766a31a144c3626376f50b15646a`; CI #626 (PR) e #627 (main) SUCCESS; Plan Governance #55 (PR) e #56 (main) SUCCESS; 1149 Python/PostgreSQL PASS/zero SKIP, 10 Playwright PASS; closeout `docs/checkpoints/NFV1_P02_T02_CLOSEOUT_2026-10-06.md`, certificação documental condicionada ao merge/gates deste registro.

### 10. NFV1-P02-T03 — Configuração do cliente

- [x] **Estado:** concluído
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** cinco vistas de configuração no Portal existente; leituras duráveis sanitizadas e mutações governadas. Configuração governada interna e política aprovada implementadas; certificação condicionada ao closeout/main verdes.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** configuração interna certificada pela PR/main; gates deste closeout pendentes; resolução operacional de Vault/providers e tráfego real não confirmados (P6/P7/P10); staging drift (P4/P5/P9/P11).
- **Decisões do dono pendentes:** T03-B01 RESOLVIDO: POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION pelo dono em 2026-10-06; implementar exatamente a política aprovada, sem operação externa. Registro de aprovação substitui a pendência histórica de aprovar/ajustar a política sensível de destinos/egress em `docs/NFV1_P02_T03_WEBHOOK_SECURITY_POLICY_PROPOSAL_2026-10-06.md` (APROVADA PARA IMPLEMENTAÇÃO INTERNA), antes de cadastrar/ativar webhooks pelo Portal. AGENTS.md e padrão mestre §6 exigem decisão; nenhuma aprovação implícita. T04 somente após este closeout integrar main com gates completos verdes; não iniciada nesta entrega.
- **Prova:** PR #121 MERGED; HEAD `2e7333f02d3673196d18c25702b1ab39fbfb5eb8`; merge/main `1e9c102ab250b822c89cfbb5c3d185ba3c62d9ea`, árvore idêntica à certificada; CI #647 (PR, run 37514869023) e #648 (main, run 37516153619) SUCCESS; Plan Governance #68 (PR, run 37514868987) e #69 (main, run 37516153800) SUCCESS; 1277 Python/PostgreSQL PASS/zero SKIP, 12 frontend PASS e 18 Playwright PASS nas duas CIs; closeout `docs/checkpoints/NFV1_P02_T03_CLOSEOUT_2026-10-06.md`, certificação documental condicionada ao merge/gates deste registro. Política POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION e T03-B01 resolvido; sem operação externa. Parcela histórica de consulta #119/#120 preservada nos checkpoints.

### 11. NFV1-P02-T04 — Usuários e RBAC

- [x] **Estado:** concluído
- **Objetivo:** administrar usuários pelo HumanAccount/RBAC canônico, sem segunda autenticação ou autoridade paralela.
- **Depende de:** NFV1-P02-T03 DONE_CERTIFIED; main de entrada `d8d958a33a7a2364e005cb5742baecae9ed1e341`, CI #650 e Plan Governance #71 SUCCESS.
- **Entregar:** superfície `users`, criação/alteração governadas, OWNER/ADMIN via `user.manage`, testes de OPERATOR/AUDITOR/BILLING/platform_admin, escopo tenant/unit, revogação de sessões, audit e UI.
- **Não fazer:** não permitir tenant/browser definir autoridade; não conceder/mutar `platform_admin`; não criar papéis/RBAC/auth paralelos; não iniciar T05; não fazer deploy/operação externa.
- **Critério de aceite:** papéis existentes e platform_admin certificados; grants seguem exatamente a matriz de delegação aprovada e nunca excedem tenant/unit scope do ator; cross-tenant/unit falha fechado; mutações têm CSRF/idempotência/versão/audit; sessões são revogadas; frontend e CI verdes.
- **Verificação:** Ruff, Mypy, Pytest/PostgreSQL, frontend lint/typecheck/test/build, Playwright, security/migration/secret gates, containers/SBOM/backup-restore e `python scripts/check_nfcore_plan.py` na PR e no closeout/main.
- **Riscos / não confirmado:** staging permanece em drift e fora desta tarefa; integração operacional externa/produção não foi executada. CI main #652 da implementação ficou presa em infraestrutura no Install Chromium após gates anteriores verdes e não é usada como evidência final; este closeout exige sua própria PR/main integral verde.
- **Decisões do dono pendentes:** nenhuma. Política T04 aprovada explicitamente como conjunto em 2026-10-07: OWNER administra todos os papéis do próprio tenant; ADMIN somente OPERATOR/AUDITOR/BILLING; demais papéis não administram usuários; tenant/unit permanecem server-side; platform_admin não é concedível pelo tenant; mudanças de autoridade revogam sessões; último OWNER ativo é protegido; criação usa o fluxo canônico de ativação/reset sem senha/token expostos. A reconciliação pós-merge confirmou que a PR #123 corresponde exatamente a esta política.
- **Prova:** PR #123 MERGED; HEAD `14e27b269344b9bec549d13dd96434e8a41ad8aa`; merge/main `459f7d1d4fd54997345d9458e1b365d49a50e31d`; CI #651 (PR) SUCCESS; Plan Governance #72 (PR) e #73 (main) SUCCESS; checkpoint `docs/checkpoints/NFV1_P02_T04_USERS_RBAC_2026-10-07.md`; closeout `docs/checkpoints/NFV1_P02_T04_CLOSEOUT_2026-10-07.md`, certificação final condicionada ao merge/gates completos deste registro.

### 12. NFV1-P02-T05 — Billing/Planos/Uso

- [x] **Estado:** concluído
- **Objetivo:** expor Billing, Planos e Uso a partir das autoridades comerciais canônicas, mantendo provider/gateway externo como adapter.
- **Depende de:** NFV1-P02-T04 DONE_CERTIFIED; main de entrada `acc8510f3df11fb284386f951e427dffdeeef242`, CI #654 e Plan Governance #75 SUCCESS.
- **Entregar:** projeções read-only `billing`, `plans` e `usage` no Portal existente, compostas com subscription durável e catálogo de pricing publicado; RBAC `billing.read`; testes tenant/RBAC/PostgreSQL/frontend.
- **Não fazer:** não inventar preço/plano/promoção; não alterar billing status/entitlement/usage pelo Portal; não transformar provider externo em autoridade; não iniciar T06; não fazer deploy/operação externa.
- **Critério de aceite:** assinatura/uso/plano vêm do estado canônico persistido; ausência retorna vazio sem fabricar estado; OWNER/ADMIN/AUDITOR/BILLING têm leitura e OPERATOR falha fechado; tenant vem da sessão; referências externas/provider não vazam; CI integral verde.
- **Verificação:** Ruff, Mypy, Pytest/PostgreSQL, frontend lint/typecheck/test/build, Playwright, secret/migration/container/SBOM/backup-restore e `python scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preço/plano/provider reais continuam decisões/configurações externas; P3/P8 ainda precisam certificar aquisição/cobrança operacional; staging permanece em drift.
- **Decisões do dono pendentes:** nenhuma para esta implementação read-only. Qualquer preço/plano/promoção/provider real exige decisão humana própria e não será inferido.
- **Prova:** PR #125 MERGED; HEAD `d0a81ca9cf641295498b3ef92db256d4b3f417c0`; merge/main `7332943467dd876c6c72c163d73a9c3454e05828`; CI #655 (PR) e #656 (main) SUCCESS; Plan Governance #76 (PR) e #77 (main) SUCCESS; checkpoint `docs/checkpoints/NFV1_P02_T05_BILLING_PLANS_USAGE_2026-10-07.md`; closeout `docs/checkpoints/NFV1_P02_T05_CLOSEOUT_2026-10-07.md`.

### 13. NFV1-P02-T06 — Inutilização

- [ ] **Estado:** em execução
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T06 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T05 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** jornada própria de Inutilização no Portal existente, validação do contrato canônico, estado sanitizado da outbox e controles de ingresso/retry; sem operação externa.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T06 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** provider/handler/secret real e homologação permanecem P6/P7/P10; staging drift P4/P5/P9/P11; checkpoint docs/checkpoints/NFV1_P02_T06_INUTILIZATION_2026-10-08.md.
- **Decisões do dono pendentes:** nenhuma nova decisão: reutilizar papéis/permissões/contratos existentes; operação fiscal real/deploy seguem gates humanos.
- **Prova:** PENDENTE

### 14. NFV1-P02-T07 — Premium UX

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T07 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T06 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P02-T07, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T07 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 15. NFV1-P03-T01 — First-party acquisition

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P03-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T07 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P03-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P03-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 16. NFV1-P03-T02 — Trial

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P03-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P03-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P03-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P03-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 17. NFV1-P03-T03 — Provider webhook runtime

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P03-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P03-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P03-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P03-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 18. NFV1-P03-T04 — Purchase readiness

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P03-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P03-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P03-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P03-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 19. NFV1-P03-T05 — Lifecycle comercial

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P03-T05 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P03-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P03-T05, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P03-T05 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 20. NFV1-P04-T01 — Handler registry canônico

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P04-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P03-T05 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P04-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P04-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 21. NFV1-P04-T02 — Outbox/inbox/background

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P04-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P04-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P04-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P04-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 22. NFV1-P04-T03 — Observabilidade do Worker

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P04-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P04-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P04-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P04-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 23. NFV1-P04-T04 — Container

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P04-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P04-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P04-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P04-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 24. NFV1-P05-T01 — Pré-deploy

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P05-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P04-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P05-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P05-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 25. NFV1-P05-T02 — Deploy reconciliado

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P05-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P05-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P05-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P05-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 26. NFV1-P05-T03 — Smoke

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P05-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P05-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P05-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P05-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 27. NFV1-P05-T04 — E2E real

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P05-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P05-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P05-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P05-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 28. NFV1-P05-T05 — Rollback rehearsal

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P05-T05 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P05-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P05-T05, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P05-T05 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 29. NFV1-P06-T01 — Selecionar provider

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P06-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P05-T05 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P06-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P06-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 30. NFV1-P06-T02 — Implementar adapter de infraestrutura

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P06-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P06-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P06-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P06-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 31. NFV1-P06-T03 — Certificar escopo

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P06-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P06-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P06-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P06-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 32. NFV1-P06-T04 — Rotação e falha

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P06-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P06-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P06-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P06-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 33. NFV1-P07-T01 — Definir launch matrix

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P07-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P06-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P07-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P07-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 34. NFV1-P07-T02 — Adapter de transporte

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P07-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P07-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P07-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P07-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 35. NFV1-P07-T03 — Signer/CSC/certificado

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P07-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P07-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P07-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P07-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 36. NFV1-P07-T04 — Contract tests

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P07-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P07-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P07-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P07-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 37. NFV1-P08-T01 — Configurar provider aprovado

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P08-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P07-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P08-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P08-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 38. NFV1-P08-T02 — Compra controlada

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P08-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P08-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P08-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P08-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 39. NFV1-P08-T03 — Lifecycle

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P08-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P08-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P08-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P08-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 40. NFV1-P08-T04 — Reconciliação

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P08-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P08-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P08-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P08-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 41. NFV1-P09-T01 — Tracing

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P09-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P08-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P09-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P09-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 42. NFV1-P09-T02 — Métricas

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P09-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P09-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P09-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P09-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 43. NFV1-P09-T03 — Alerts

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P09-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P09-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P09-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P09-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 44. NFV1-P09-T04 — Backup/restore operacional

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P09-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P09-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P09-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P09-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 45. NFV1-P09-T05 — Runbooks

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P09-T05 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P09-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P09-T05, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P09-T05 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 46. NFV1-P10-T01 — Credenciais oficiais

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P10-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P09-T05 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P10-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P10-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 47. NFV1-P10-T02 — Homologação oficial

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P10-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P10-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P10-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P10-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 48. NFV1-P10-T03 — Evidence ledger

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P10-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P10-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P10-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P10-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 49. NFV1-P10-T04 — Controlled pilot

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P10-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P10-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P10-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P10-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 50. NFV1-P11-T01 — Environment

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P11-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P10-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P11-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P11-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 51. NFV1-P11-T02 — DNS/TLS

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P11-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P11-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P11-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P11-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 52. NFV1-P11-T03 — Observabilidade/backup

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P11-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P11-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P11-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P11-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 53. NFV1-P11-T04 — Promotion readiness

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P11-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P11-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P11-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P11-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 54. NFV1-P12-T01 — Certificar prontidão funcional

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P12-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P11-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P12-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P12-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 55. NFV1-P12-T02 — Certificar paridade comercial

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P12-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P12-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P12-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P12-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 56. NFV1-P12-T03 — Certificar prontidão técnica de produção

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P12-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P12-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P12-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P12-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 57. NFV1-P12-T04 — Certificar prontidão operacional

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P12-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P12-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P12-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P12-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 58. NFV1-P12-T05 — Certificar prontidão comercial

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P12-T05 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P12-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P12-T05, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P12-T05 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 59. NFV1-P12-T06 — Go/No-Go humano e promoção controlada

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P12-T06 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P12-T05 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P12-T06, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P12-T06 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

## Relatório final

Ao concluir o plano, registrar: entregas por tarefa; PRs e commits de merge; CI da main; evidências de staging/produção; o que foi verificado e como; o que não foi confirmado; decisões humanas; blockers residuais; estado final do Go/No-Go.

## Regra de atualização

1. A tarefa ativa pode mudar de `pendente` para `em execução` quando o trabalho iniciar.
2. Somente depois de prova completa ela pode virar `[x] **Estado:** concluído`.
3. O campo **Prova** de tarefa concluída deve conter PR + CI + commit/SHA.
4. Nenhuma tarefa posterior pode ser concluída enquanto existir anterior não concluída.
5. Se o cronograma ganhar, remover ou reordenar um ID, este ledger deve ser atualizado na mesma mudança; caso contrário o CI falha.
