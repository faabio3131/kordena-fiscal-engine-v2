# CHECKPOINT — NFV1-P06-T04 — Rotação e falha

- **Data:** 2026-10-10
- **Produto/repo:** FM NFCORE V1 / faabio3131/kordena-fiscal-engine-v2
- **Entrada main:** `0e61a8311253aecf06a3faa48afd3b5b1be073b4`
- **Predecessora:** T03 certificada internamente, PR #158 MERGED, CI #746 e Governance #167 SUCCESS. 26/59 concluídas; T04 primeira pendente.
- **Branch:** `test/nfv1-p06-t04-secret-rotation-failures`
- **Estado:** IN_PROGRESS. Não declarar T04 concluída sem CI, certificação, merge autorizado, pós-merge e registro final.
- **Autorização:** usuário em 2026-10-10 — "Pode executar". Escopo interno reversível; merge, deploy, credencial, projeto/cloud/IAM/gasto dependem de autorização própria.

## CURRENT → TARGET e autoridades

O adapter GSM `DurableGsmReader` verifica binding durável, escopo, estado active, expiração, workload, resource allowlist, pinned version, CRC e envelope antes de retornar bytes. Revalida o binding depois do acesso. `SecretBindingAdministration` preserva identidade canônica e grava revisão/auditoria na mesma UoW com CAS. `GoogleSignatureSecretBackend`, `GoogleFiscalSecretClient`, `SecretResolver` e `ExternalFiscalSecretVault` permanecem únicos; não adicionar nova API, tabela, autorizações ou provider de produção.

TARGET: testar as seis classes de falhas exigidas pelo cronograma em assinatura, certificado, CSC e credenciais, com os dois bancos de testes SQL. Exercitar rotação pinada 9→10, bloqueio de versão antiga, revogação durante leitura, conflito de CAS e mapeamento sanitizado de erros do SDK. Dados exclusivamente sintéticos. Testes de integração cloud reais NÃO realizados.

## Mapa de impacto e gates

- Arquivo de teste novo: `tests/vault/test_p06_t04_rotation_failures.py`.
- Este checkpoint, ledger e CURRENT registram apenas estado de execução, escopo e riscos.
- Nenhum código de produção, API, RBAC, tenant, persistência, migration, frontend, workflow ou secrets reais alterados por este bloco de testes.
- Obrigatório: `python3 scripts/check_nfcore_plan.py`, Ruff, Mypy strict, pytest SQLite/PostgreSQL, CI 41 gates, frontend/Playwright, Docker/containers, SBOM/security, backup/restore e readiness. CI da candidata ainda pendente.
- Critério: 0 FAIL/0 SKIP na CI remota; falhas investigadas sem remover testes válidos. A eventual certificação **interna** não atende o gate `EXTERNAL_SECRET_BACKEND_CERTIFIED` sem acesso GSM real validado.
- Revisar diff completo antes de PR; registrar HEAD, PR, runs e execução pós-merge separadamente.

## Pendências e limites

P6-T01-B02 **BLOCKED_EXTERNAL**: conta/projeto/região/billing/budget, identidade/IAM, bootstrap/rota de acesso e prova real GSM. Staging permanece em drift no último levantamento (API/Portal/PostgreSQL 1/1, Worker 0/1), sem inspeção nova ou deploy. Sem segredo/credencial real, produção, SQL externo, DNS, compra ou operação fiscal. `PRODUCTION_APPROVED=NO`, `COMMERCIAL_LIVE=NO`.

**Próxima ação:** validar testes dirigidos quando possível, executar Ruff/MyPy/validador de plano, abrir PR Draft com escopo único T04, certificar CI no HEAD exato, preservar o gate humano de merge. Não iniciar P5.
