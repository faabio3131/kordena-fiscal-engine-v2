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


## Certificação pós-merge — evidência superior (2026-10-10)

O status `IN_PROGRESS` e os placeholders de PR/CI deste checkpoint são históricos. A PR #159 foi integrada e os gates posteriores encerraram com sucesso:
- **Branch testada:** `test/nfv1-p06-t04-secret-rotation-failures`, head `0763dc97f6fe3053bf80f22d1eae27095a9d24a0`; **PR #159 MERGED**, merge/main `d2600c6a6604d9f3f8be3ea3642b78ebbf688832`.
- **Pré-merge:** CI #747/run38063730623 e Governance #168/run38063730630 SUCCESS no head.
- **Pós-merge:** CI #748/run38064965857 (quality job 114250640404) e Governance #169/run38064965821 SUCCESS no SHA do merge; **41/41 etapas**.
- **Logs CI main:** 2.022 Python/PostgreSQL PASS, zero FAIL, zero SKIP, 1 warning preexistente TestClient, 439,52s; 14 frontend PASS; 28 Playwright PASS em 23,6s. Ruff, Mypy, secret scan, migrations 1–17, dependências, frontend lint/typecheck/build, E2E, containers, non-root, vulnerability policy, SBOM, PostgreSQL backup/restore/readiness PASS.
- **T04** cobre missing, revoked, expired, permission denied, backend unavailable, timeout/version missing, rotação 9→10, conflito CAS e revogação concorrente em signature/certificate/csc/credentials; 85 novos casos adicionados ao baseline. Não foi necessário modificar regras ou código de produção.
- **Classificação:** `NFV1-P06-T04 DONE_CERTIFIED_INTERNAL`, condicionado ao merge e gates específicos do presente fechamento documental. Após esse fechamento: 27/59 concluídas; próxima tarefa no ledger `NFV1-P05-T01` continua `BLOCKED_EXTERNAL`.
- **Bloqueio externo não mitigado:** P6-T01-B02 (identidade/IAM/GSM real/conta/bootstrap/canal) sem prova, `EXTERNAL_SECRET_BACKEND_CERTIFIED=NOT MET`. Testes sintéticos não certificam cloud nem staging. Último staging read-only segue em drift/Worker 0/1, não reinspecionado; `PRODUCTION_APPROVED=NO`; `COMMERCIAL_LIVE=NO`.
- Nenhum segredo/credencial real, criação de conta, gasto, IAM, cloud I/O, migration produtiva, DNS, deploy ou emissão fiscal ocorreu. **Merge deste fechamento documental exige autorização própria.**

Evidências remotas: [CI pós-merge #748](https://github.com/faabio3131/kordena-fiscal-engine-v2/actions/runs/38064965857) e [Governance #169](https://github.com/faabio3131/kordena-fiscal-engine-v2/actions/runs/38064965821).
