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
