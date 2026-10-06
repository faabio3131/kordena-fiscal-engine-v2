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

- [ ] **Estado:** em execução
- **Objetivo:** certificar emissão, consulta, cancelamento, inutilização, reconciliação, capabilities e archive reference sobre o runtime fiscal canônico, sem ampliar escopo.
- **Depende de:** NFV1-P01-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** matriz integrada das sete rotas Bridge do launch-scope, status/operation IDs, idempotência, scope interno, fail-closed sem dependência e readiness sem overclaim.
- **Não fazer:** não antecipar P2/P6/P7; não criar provider/secret/signer paralelo; não usar synthetic/fake como prova de integração externa real; não executar deploy, homologação ou produção.
- **Critério de aceite:** sete operações canônicas atravessam um único path quando dependências são explicitamente injetadas em teste; ausência de dependência real retorna FISCAL_RUNTIME_NOT_READY; mutações exigem idempotência; perfil declara provider/secret/signer externo como não configurados; nenhum gate transversal violado.
- **Verificação:** testes T04 + contratos Bridge + suíte existente e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** esta tarefa certifica a API e integração interna; não prova FiscalProviderTransport real, ExternalSecretClient real, signing operacional externo, homologação oficial, staging CURRENT ou produção.
- **Decisões do dono pendentes:** nenhuma para certificação interna; merge/deploy/produção permanecem sujeitos a autorização específica.
- **Prova:** branch `test/nfv1-p01-t04-fiscal-api-certification`; checkpoint `docs/checkpoints/NFV1_P01_T04_FISCAL_API_CERTIFICATION_2026-10-06.md`; PR/CI pendentes.

### 8. NFV1-P02-T01 — Matriz frontend x backend

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T01 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P01-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P02-T01, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T01 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 9. NFV1-P02-T02 — Superfícies fiscais

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T02 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T01 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P02-T02, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T02 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 10. NFV1-P02-T03 — Configuração do cliente

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T03 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T02 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P02-T03, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T03 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 11. NFV1-P02-T04 — Usuários e RBAC

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T04 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T03 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P02-T04, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T04 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 12. NFV1-P02-T05 — Billing/Planos/Uso

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T05 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T04 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P02-T05, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T05 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
- **Prova:** PENDENTE

### 13. NFV1-P02-T06 — Inutilização

- [ ] **Estado:** pendente
- **Objetivo:** executar exatamente a tarefa NFV1-P02-T06 do cronograma mestre, sem ampliar escopo.
- **Depende de:** NFV1-P02-T05 concluído e certificado; mais as dependências formais do cronograma
- **Entregar:** tudo que o cronograma exige para NFV1-P02-T06, mais os testes/evidências diretamente necessários.
- **Não fazer:** não antecipar tarefa posterior; não criar autoridade paralela; não mascarar falha; não usar mock/synthetic como prova de integração real; não executar ação humana/externa não autorizada.
- **Critério de aceite:** critérios específicos de NFV1-P02-T06 no cronograma satisfeitos e nenhum gate transversal violado.
- **Verificação:** executar os testes aplicáveis definidos no cronograma/PR e, obrigatoriamente, `python3 scripts/check_nfcore_plan.py`.
- **Riscos / não confirmado:** preencher na PR/checkpoint; ausência de prova permanece não confirmada.
- **Decisões do dono pendentes:** nenhuma no bootstrap; registrar aqui se surgir decisão que o executor não pode tomar.
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
