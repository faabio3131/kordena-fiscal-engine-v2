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
