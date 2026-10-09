# CHECKPOINT — NFV1-P04-T02 — Outbox/inbox/background

Data: 2026-10-09 (America/Sao_Paulo).
Produto: FM NFCORE V1.
Repository: faabio3131/kordena-fiscal-engine-v2.
Main/Main HEAD: `8385be0ee80e434a922e9ad10b11a4f15c2188db`.
Branch: feat/nfv1-p04-t02-worker-recovery.
Branch HEAD/PR/CI PR: a registrar na PR publicada; certificação pendente.
CI main de entrada: #716/run37882569950 e Governance #137/run37882569961 SUCCESS.
PR #144 MERGED por autorização do dono;20 tarefas concluídas antes de T02.
Estado: IN_PROGRESS. Autorização T02: dono instruiu “Executar”.

## CURRENT -> TARGET e impacto

CURRENT: registry T01 e loop/UOW/outbox/inbox/auditoria existem; retry/leases/restart
possuem testes anteriores. O UPDATE da outbox usa apenas entry_id após uma leitura
prévia de status/attempt; há janela de concorrência entre leitura e escrita.
TARGET: provar poll/dispatch, retry/backoff limitado, idempotência, dead-letter,
shutdown, restart e replay seguro; fechar a janela com comparação atômica na escrita.
Escopo: persistência canônica e matriz interna T02; mesma outbox/UOW/worker/router.
Sem fila/handler comercial novo, mudança de política, migração, deploy ou segredo real.

## Mudanças e causa raiz

SqliteFiscalOutboxStore é reutilizado pelo adapter PostgreSQL. A seleção de uma lease
expirada pode anteceder uma conclusão concorrente: o UPDATE incondicional poderia
ressuscitar uma entrada concluída como uma nova tentativa, com nova auditoria válida.
A checagem anterior à transição também não garante estado estável até o UPDATE.
Agora cada UPDATE compara entry_id + status esperado + attempt_count esperado.
Claim que perdeu a disputa não retorna entrada e não despacha; transição obsoleta
lança OutboxStateError, preservando a transação/auditoria do vencedor.
Nenhuma regra de domínio nova, tabela ou configuração por cliente.

## Matriz reproduzível

Arquivo: tests/application/test_p04_t02_worker_recovery.py.
18 casos: oito cenários em SQLite e PostgreSQL (16), mais duas disputas PostgreSQL.

| Cenário | Evidência / limite |
|---|---|
| Retry/backoff/restart | Delays2/5/5 com teto5; runtime novo em cada tentativa; nada antes do vencimento; quarta tentativa dead-letter; audit consistente |
| Terminal/reopen | Novo objeto DB; sucesso e replay persistem sem novo dispatch/auditoria |
| Crash após efeito | Inbox sintético commitado antes de ProcessLost; outbox/audit CLAIMED; nada antes da lease; reclaim no vencimento; inbox replay/version2; uma conclusão durável |
| Shutdown durante lote | Termina as duas entradas já claimed; terceira permanece PENDING/sem audit; runtime novo a conclui |
| Shutdown prévio | Nenhum claim, tentativa ou side effect |
| Atomicidade inbox/outbox | Ambas criações sem commit desaparecem; poll vazio |
| Falha de persistência | Falha sintética antes de abrir UOW; espera0.75; recupera em lotes2/2/1; idle0.25; sem perda de estado |
| Fatal/dead-letter | Uma tentativa fatal, sem retry ou reexecução por replay |
| Disputa claim x sucesso | Dois UOWs PostgreSQL reais; hook força conclusão entre SELECT e UPDATE de reclaim; sucesso não ressuscita |
| Disputa finalização x reclaim | Dois UOWs PostgreSQL reais; hook força tentativa2 entre leitura e UPDATE; tentativa1 rejeitada sem sobrescrever vencedor |

As disputas usam instrumentação de interleaving, sem threads/sleeps não determinísticos;
as leituras/escritas/commits concorrentes são PostgreSQL reais na CI. Nenhum teste
existente apagado, enfraquecido ou pulado para esconder falha.

## Testes/evidências

Dirigidos:33 PASS/12 PostgreSQL SKIP/zero FAIL local, DSN ausente.
Ruff PASS; Mypy strict193 PASS; plan59 PASS; migrations1..16 policy PASS;
secret scan PASS; diff check PASS. Suíte local completa:1363 PASS/242 PostgreSQL SKIP/zero FAIL,125.54s; um warning TestClient existente.
CI PostgreSQL real obrigatória antes de certificar; resultados finais na PR.
Sem PostgreSQL local configurado, dez novos casos PostgreSQL aguardam CI.

## Autoridades, segurança e isolamento

Outbox identity/dedup, tenant/unit/environment/host, handler registry, delivery audit,
FiscalInboxService e UOW existentes. Errors inesperados continuam redigidos pelo worker.
Shutdown drena o lote já claimed; interrupção abrupta depende de lease/retry.
Entrega é at-least-once: crash após I/O pode repetir transporte. Inbox de destinatário
com efeito/recebimento atômicos é requisito para efeitos únicos. O receiver sintético
certifica a composição interna desse padrão, nunca deduplicação de um cliente externo.
Handler/signing/egress reais não são ativados ou certificados por este harness.

## Staging e limites

Read-only reconfirmado: API/Portal/PostgreSQL1/1; Worker0/1;
deployments históricos inalterados. Drift conhecido P5/P9/P11.
Dependência de assinatura real/Secret Manager P6 não certificada; fail-closed mantido.
Observabilidade T03, container contínuo/sinal de processo T04 e staging P5 não iniciados.
PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.

## Próxima ação

Concluir gates/CI do HEAD, registrar prova, solicitar merge específico da PR T02.
Não marcar T02 concluída nem iniciar T03 antes de merge/main/evidência/fechamento.
