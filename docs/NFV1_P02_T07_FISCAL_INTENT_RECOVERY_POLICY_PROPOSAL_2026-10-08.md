# NFV1-P02-T07 — Política proposta de recuperação de intento fiscal

Status: DRAFT / HUMAN_POLICY_APPROVAL_REQUIRED. Data: 2026-10-08 UTC.
Repository: faabio3131/kordena-fiscal-engine-v2. Blocker: T07-B01.
Nenhuma parte desta política está implementada ou aprovada por este documento.

## Problema CURRENT / autoridade

T02/T06 conservam Idempotency-Key e fingerprint somente na memória da página.
Após reload/crash, a UI perde a associação ao pedido e pode criar outra chave.
O contrato `tests/frontend/portal_contract.test.js` proíbe localStorage e
sessionStorage. Não alterar ou enfraquecer esse teste para implementar recovery.
Reservas/outbox têm idempotência e escopo próprios; não constituem uma lista
autorizada de tentativas de uma conta humana nem guardam toda chave recuperável.
Receipts de configuração existem na persistência canônica, mas seu escopo/política
não autoriza automaticamente exposição ou retomada de operações fiscais humanas.

AGENTS.md exige parada antes de "mudança de segurança sensível" e "tratamento novo
de dado pessoal"; padrão mestre §6 exige decisão antes de "mudança de segurança".
A nova associação conta → intento e a sua autorização de leitura/retomada precisam
de aprovação explícita. Este blocker não impede os ajustes independentes de UX.

## Política proposta como conjunto para implementação interna

1. Manter a proibição de browser storage. Nenhum payload fiscal, token, senha,
   cookie, certificado, CSC ou chave de idempotência será persistido no navegador.
2. Recuperação ocorrerá no mesmo Portal/router/executor fiscal e UoW/persistência
   canônicos. Evoluir o mecanismo durável de receipts existente; nenhuma segunda
   fila, regra fiscal, sessão, autenticação, registry, Vault ou authority.
3. Registrar somente metadados necessários: identificador opaco do intento,
   operação, host/tenant/unidade/ambiente, conta iniciadora, session_epoch,
   fingerprint calculado no backend, referência ao estado canônico e chave
   idempotente protegida no backend. Não criar cópia adicional do payload fiscal.
4. Receipts não determinam sucesso fiscal, pagamento, entitlement ou produção.
   Outbox/reserva/lifecycle/provider permanecem as autoridades correspondentes.
5. Somente a mesma conta autenticada poderá consultar/retomar seu intento, no mesmo
   tenant/host/unidade/ambiente, com a permissão original da operação revalidada
   server-side. OWNER/ADMIN não ganham acesso implícito aos intentos de outra conta;
   platform_admin não recebe bypass. Mudança de session_epoch bloqueia retomada.
6. A UI receberá somente identificador opaco e metadados sanitizados autorizados;
   nunca o payload, key original, resultado bruto, segredo ou protocolo inventado.
   Retomada exige sessão válida, CSRF, Idempotency-Key e fingerprint correspondente
   ao conteúdo original reenviado. Backend reutiliza a chave canônica original.
7. Preparação/associação durável deve ocorrer antes de qualquer efeito e ser
   atômica com o estado interno pertinente, sem segunda reserva/numeração/outbox.
   Conflito de conteúdo, duas abas e concorrência falham fechado. Um retry nunca
   gera chave original nova, nova emissão ou efeito externo duplicado.
8. Janela proposta de retomada automática: até 24 horas após criação, nunca além
   da revogação/perda de escopo/permissão. Expiração NÃO comprova falha, NÃO libera
   numeração e NÃO autoriza automaticamente novo intento. Resultado desconhecido
   após expiração exige reconciliação canônica. Não apagar evidência existente.
9. Ausência de receipt/policy, receipt expirado, conta/epoch/scope divergente,
   perda de permissão, fingerprint inválido ou persistência indisponível =
   fail-closed. Não depender de informação declarada pelo browser como autoridade.
10. Auditoria durável sanitizada de preparação, recuperação, bloqueio e retomada,
    sem payload, key, token, cookie ou conteúdo fiscal bruto. Retenção operacional
    continua governada pelas tarefas P9/P12; sem purge novo nesta implementação.
11. Validar SQLite/PostgreSQL, crash/reload, resposta perdida após commit, duas abas,
    conflito de conteúdo, sessão revogada, epoch alterado, expiração, RBAC,
    cross-account/tenant/unit/host/env, audit rollback e único efeito no harness.
    Playwright deve manter a proibição de storage e usar HTTP durável sintético.
12. Eventual migration somente aditiva, no schema canônico e sob migration guard.
    Reversão de código mantém receipts e dados; não habilita produção fiscal.

## Decisão solicitada / limites

Aprovar ou ajustar este conjunto como POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION
para a própria T07, incluindo janela de 24 horas, mesma conta/session_epoch e
ausência de bypass administrativo. A aprovação permitirá implementação/testes/
migration aditiva governada se necessária/PR/CI; não certifica o TARGET por si só.

Não autoriza deploy, staging write, segredo/credencial/certificado/CSC real,
DNS/custo, destino/tráfego real, operação fiscal oficial, pagamento, homologação,
piloto, produção, Go/No-Go, PRODUCTION_APPROVED ou COMMERCIAL_LIVE.
Somente dados sintéticos nos testes. P3 não inicia enquanto T07 não for certificada.
