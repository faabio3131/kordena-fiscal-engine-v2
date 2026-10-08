# NFV1-P02-T07 — recuperação fiscal durável — reconstrução

Data: 2026-10-08. Main de entrada 82e05f7af6ffca031f457ff93f43ae875ad05122.
Branch feat/nfv1-p02-t07-fiscal-recovery. Política T07-B01 aprovada como conjunto.
Implementação/testes/publicação da branch e PR Draft autorizados pelo dono.

## CURRENT → TARGET / escopo e aceite

CURRENT: parcela UX integrada; associação conta-pedido após reload ausente na main.
TARGET: metadados duráveis no receipt canônico, mesma conta/epoch/scope/permissão,
24h, fingerprint/key no backend, claim atômico antes do efeito, sem browser storage.
Pedido com resultado desconhecido exige evidência/reconciliação; nunca envio cego.
Reutilizar Portal/router/executor/UoW/fm_configuration_commands/audit/outbox/lifecycle.
Nenhuma segunda autoridade fiscal, fila, autenticação, payload copy ou migration.
Impacto: persistence port/adapter, executor/router, UI, testes SQLite/PostgreSQL/E2E.
Aceite: crash/reload/perda de resposta/concorrência/expiry/revogação/RBAC/isolamento,
audit rollback e único efeito interno comprovados; lint/build/CI/screenshots verdes.

## Continuidade / evidência

Os commits locais anteriormente relatados 83cf6b8/864161e/530faac não estão
no ambiente atual nem no GitHub. Buscas de arquivos/worktrees/objetos/reflogs
não os localizaram. Causa da indisponibilidade não comprovada. Não alegar que
os testes anteriores certificam esta reconstrução. Candidata será publicada
em Draft para persistência e CI, mantendo T07 em execução e P2 NOT MET.
Main permaneceu no SHA acima, PRs abertas na entrada zero. Railway READ-ONLY:
mesmo ambiente histórico, patch pendente 8d720a42 sem changes; sem write/deploy.
CI main anteriormente confirmada #668 é baseline; nova CI obrigatória.

## Limites / próxima ação

Implementar e testar somente T07. PostgreSQL/Playwright/visual ainda pendentes.
Sem merge/deploy/fiscal externo/secret/DNS/custo. P3 não iniciada.
PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.

## Candidata na PR #131 / verificação inicial

PR Draft https://github.com/faabio3131/kordena-fiscal-engine-v2/pull/131.
Publicação via conector GitHub autenticado: git HTTPS local sem credencial de push;
não houve novo bloqueio de aprovação. Árvore local/remota conferida a cada atualização.
Nova implementação evolui fm_configuration_commands com leitura e CAS; aliases de
key e receipt por conteúdo impedem novas chaves entre abas. Preparação+auditoria
atômicas; claim+auditoria commit antes do handler. Executing nunca redispatcha;
consulta outbox por operação/correlation/scope ou tentativa de emissão SHA256(key)
com lifecycle scope exato. Outros contratos sem evidência exigem reconciliação.
Resposta recuperada contém metadados, não cópia do payload/resultado bruto.
Janela 24h, sessão/epoch/permissão revalidados. Expiração não libera numeração.
UI permite seleção explícita e reenvio original, mantendo storage proibido.

Primeira rodada dirigida: 20 SQLite PASS / 20 Pg SKIP; Pg local sem DSN, CI obrigatória.
Frontend 14 PASS, lint/typecheck/build PASS, Ruff/Mypy187 e gates plano/secret/
migration PASS. Matriz completa final em execução; nenhuma certificação antecipada.
Teste Cakto assina com clock atual no início do caso: evita envelhecimento do
NOW capturado na coleta durante suíte longa; tolerância/runtime de auth inalterados.
Jornadas E2E novas usam outro loopback/DB sintético para isolar receipts das
jornadas existentes; não há operação fiscal externa ou provider real.

## Evidência local final / candidata congelada

Runtime/testes Python no HEAD `faa6970bd13afb3110cd6c1430b8cbe9d17d984b`:
**1255 PASS / 158 SKIP / zero FAIL**, 58.71s, pytest-xdist 4/loadscope, Python3.12.
Skips por ausência de DSN PostgreSQL local; não substituem a CI real, que exige
zero skip no seu ambiente. Quatro warnings Starlette/TestClient preexistentes,
um por worker. Recuperação dirigida21 PASS/21 Pg SKIP/zero FAIL (8.49s).
Ruff, Mypy187, frontend lint/typecheck/build e14 testes PASS. Plano59/migration
versions1..14/cakto2/secret/diff PASS. Npm0 vulnerabilidades; pip-audit2.10.1 sem
vulnerabilidades conhecidas. Nenhum novo skip, teste removido ou gate reduzido.

ID opaco agora distinto do fingerprint backend, com teste de não exposição.
Permissão perdida gera auditoria de bloqueio durável. Rotas novas retornam
metadados sanitizados; primeira resposta da rota legada preserva campos fiscais
contratuais, sem chave/fingerprint. Chamadas originais continuam verificadas no
handler (a chave não precisa ser exposta ao browser para provar sua propagação).

HEAD posterior `34acb06c875031e41cdd5c9e4340c8758e5c7cc7` altera somente jornadas
E2E UI-only: stubs de list/prepare/resume explícitos e prova CSRF/key preservada,
com espera pela chamada efetiva após o novo protocolo assíncrono. Runtime Python/
Portal inalterados. Jornadas novas continuam real HTTP/SQLite sintético e isolado.
Chromium local: download ZIP inválido; testes E2E e revisão visual pendentes CI.

CI #670..673 canceladas automaticamente por atualização da candidata; não são
falhas, nem provas de sucesso. #674/run37789674054 em execução no HEAD34acb06,
Governance95 SUCCESS. O commit documental que contém este checkpoint tem gates
próprios obrigatórios; HEAD/CI final/evidência serão os da própria PR #131,
registrados na descrição da PR após conclusão. Não marcar ledger/T07 concluídos
antes da integração autorizada e CI main verde. Não anunciar CI verde antecipadamente.

Railway READ-ONLY final: Portal35b7aafc/APIc0f8fb2b/Pgce9b66e7 1/1;
Worker3215f498 0/1 apesar de Online; patch8d720a42 sem changes. Mesmo drift;
sem deploy/write/secret externo. P5/P9/P11 preservam autoridades destas pendências.
P2 NOT MET; P3 não iniciada. Próxima ação: concluir CI/E2E, baixar/conferir/inspecionar
screenshots, persistir resultado na PR e propor merge ao dono somente com gates verdes.
