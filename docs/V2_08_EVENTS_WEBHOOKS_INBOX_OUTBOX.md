# V2-08 — Events / Webhooks / Inbox / Outbox

Status: **EM EXECUÇÃO — DURABLE INBOX + DURABLE OUTBOX WORKER CERTIFICADOS**  
Branch: `v2/events-webhooks-inbox-outbox`  
PR: **#9 Draft**  
Dependência certificada: V2-07.

## Objetivo

Construir a camada assíncrona durável do FM Fiscal para publicação e consumo de eventos, entrega segura de webhooks e processamento idempotente de mensagens, preservando as garantias já certificadas de segurança S2S, assinatura HMAC, persistência durável, idempotência e isolamento host/tenant/unidade.

## Princípios obrigatórios

- nenhum side effect assíncrono depende apenas de memória de processo;
- outbox é persistida no mesmo domínio transacional que produz o fato fiscal quando aplicável;
- inbox impede reprocessamento destrutivo de mensagens recebidas;
- entrega é at-least-once, com consumidores obrigatoriamente idempotentes;
- retries são explícitos, limitados e auditáveis;
- falhas permanentes terminam em DLQ/dead-letter governada;
- leases/claims impedem processamento concorrente da mesma mensagem;
- restart de processo não perde estado de entrega ou consumo;
- correlation/causation/idempotency keys atravessam toda a cadeia;
- I/O externo nunca deve manter a transação local do banco aberta;
- webhook signing continua usando a segurança certificada no V2-05;
- nenhum consumidor específico entra no núcleo.

## Bloco funcional 1 — Durable Inbox — CONCLUÍDO E CERTIFICADO

A superfície `kordena_fiscal.events` implementa `FiscalInboxEntry`, `FiscalInboxStatus`, `FiscalInboxStore`, `FiscalInboxService`, deduplicação determinística por partição fiscal + producer + upstream `event_id`, SHA-256 do payload, correlation/causation/idempotency e lifecycle `RECEIVED -> PROCESSING -> PROCESSED/REJECTED` com optimistic versioning.

A migration SQLite v2 `v2_08_durable_inbox` integra a inbox ao mesmo `FiscalUnitOfWork` do V2-07. Replay idêntico após restart, conflito semântico fail-closed, isolamento por host, rollback inbox+outbox e upgrade controlado V2-07 -> migration 2 foram comprovados.

Gate definitivo:

- SHA: `f467d0dafa70e3c0debd3aacccbb183c954c5b35`;
- Actions run: `34662707064` — **SUCCESS**;
- Install PASS; Ruff PASS; Mypy strict PASS — 62 source files;
- Pytest: **316 PASS em 0.85s**;
- baseline V2-07: 309 testes; +7 testes.

## Bloco funcional 2 — Durable Outbox Delivery + Dispatcher/Worker — CONCLUÍDO E CERTIFICADO

O estado persistido de outbox criado no V2-07 já possuía `PENDING`, `IN_FLIGHT`, `RETRY_WAIT`, `SUCCEEDED` e `DEAD_LETTER`, além de `attempt_count`, `lease_until`, `available_at`, `last_error` e `completion_reference`. O V2-08 adicionou a fronteira de execução durável necessária para usar esse estado corretamente em produção assíncrona.

### Worker transacional curto

Foi criado `DurableFiscalOutboxWorker` na camada de aplicação. O worker usa três etapas separadas:

1. abre uma Unit of Work curta, faz `claim_due(...)`, grava `IN_FLIGHT` + lease + novo `attempt_count` e **commita antes de qualquer I/O externo**;
2. executa o handler de transporte/provedor fora da transação local;
3. abre nova Unit of Work para `mark_succeeded`, `reschedule` ou `dead_letter`, sempre validando o `attempt_count` esperado.

Isso evita manter `BEGIN IMMEDIATE` aberto durante rede/broker/provider e usa o número da tentativa como fencing token contra worker stale.

### Claim, lease e concorrência

O claim durável permanece atômico dentro do adapter SQLite. Enquanto a lease está viva, outro worker não recebe a mesma entrada. Quando a lease expira, a mensagem volta a ser claimable e o `attempt_count` é incrementado.

A suíte executa dois workers duráveis concorrentes sobre o mesmo banco e comprova apenas uma entrega para a lease ativa.

### Retry/backoff e restart

`FiscalRetryPolicy` continua governando `max_attempts`, atraso inicial, multiplicador e teto. Falha retryable persiste `RETRY_WAIT` + `available_at`; um novo processo, usando outro `SqliteFiscalDatabase` sobre o mesmo arquivo, respeita o backoff e continua a entrega após restart.

Exceções comuns levantadas pelo handler são convertidas em falha retryable com erro limitado a 1024 caracteres. Ao atingir o limite, a entrada vai para `DEAD_LETTER` e deixa de ser claimable.

### Crash recovery e stale-worker fencing

A suíte simula crash depois do claim e antes do dispatch. Antes de `lease_until` nada é reprocessado; exatamente após a expiração, outro worker recupera a entrada e prossegue com nova tentativa.

Também foi comprovado que um worker antigo não consegue gravar sucesso depois que sua lease expirou e uma nova tentativa tomou autoridade: o `expected_attempt` antigo falha fechado com `OutboxStateError`.

### Prova de ausência de transação sobre I/O

Um handler de teste abre e commita uma nova Unit of Work no mesmo SQLite durante `dispatch`. Isso só é possível porque o worker já commitou e fechou a transação do claim antes de chamar o handler. O teste certifica explicitamente essa propriedade arquitetural.

### Migration

Nenhuma nova migration foi necessária neste bloco. O schema durável de outbox do V2-07 já contém todo o estado necessário para claim/lease/retry/success/dead-letter; o trabalho do V2-08 foi adicionar a orquestração correta e comprová-la contra o adapter durável.

### Gate de certificação do bloco

Gate definitivo do Durable Outbox Worker:

- SHA: `56678f730f2e7c3c235530887612a7ee71b5efc8`;
- Actions run: `34663828770` — **SUCCESS**;
- Install: **PASS**;
- Ruff: **PASS**;
- Mypy strict: **PASS — 63 source files sem issues**;
- Pytest completo: **322 PASS em 1.16s**;
- baseline após Durable Inbox: 316 testes; **+6 testes** neste bloco.

Os 6 testes cobrem transação curta sobre I/O, retry/backoff após restart, recovery de lease após crash, concorrência entre dois workers, fencing de worker stale e exceção do handler com retry limitado + DLQ.

Após o gate, o CI foi restaurado novamente para `workflow_dispatch` apenas no commit `c533bf65791025dd597f1871ee8f1572e39954ee`.

## Escopo restante do V2-08

Ainda permanecem pendentes antes do fechamento da fase:

- webhook delivery assinado usando HMAC-SHA256, `key_id`, timestamp e anti-replay certificados no V2-05;
- adapter/handler de webhook sobre `DurableFiscalOutboxWorker`;
- auditoria end-to-end de tentativas de entrega e resultado final, além do estado resumido já persistido na outbox;
- ordering governado quando houver chave explícita, sem fila global obrigatória;
- validação final de aderência aos contratos AsyncAPI/Bridge e ausência de breaking change;
- testes específicos de duplicate webhook delivery, assinatura, rotação, replay e falhas permanentes;
- gate final da fase e auditoria completa do diff contra V2-07.

## Limites

A certificação dos dois primeiros blocos não conclui V2-08. Não houve merge, deploy, cutover, segredo real, homologação externa ou promoção para produção.

## Próximo bloco

**V2-08 permanece EM EXECUÇÃO. Durable Inbox e Durable Outbox Delivery + Dispatcher/Worker estão CONCLUÍDOS E CERTIFICADOS. O próximo bloco funcional é Webhook Delivery assinado, reutilizando obrigatoriamente a segurança HMAC/anti-replay/rotação certificada no V2-05.**
