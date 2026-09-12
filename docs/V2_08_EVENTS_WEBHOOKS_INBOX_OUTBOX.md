# V2-08 — Events / Webhooks / Inbox / Outbox

Status: **EM EXECUÇÃO — INBOX + OUTBOX WORKER + WEBHOOK DELIVERY CERTIFICADOS**  
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
- webhook signing reutiliza a segurança certificada no V2-05, sem duplicar criptografia;
- nenhum consumidor específico entra no núcleo.

## Bloco funcional 1 — Durable Inbox — CONCLUÍDO E CERTIFICADO

A superfície `kordena_fiscal.events` implementa contrato, estados, deduplicação, SHA-256, correlation/causation/idempotency e lifecycle versionado da inbox. A migration SQLite v2 integra a inbox ao mesmo `FiscalUnitOfWork` do V2-07.

Gate definitivo:

- SHA: `f467d0dafa70e3c0debd3aacccbb183c954c5b35`;
- Actions run: `34662707064` — **SUCCESS**;
- Install PASS; Ruff PASS; Mypy strict PASS — 62 source files;
- Pytest: **316 PASS em 0.85s**;
- baseline V2-07: 309 testes; +7 testes.

## Bloco funcional 2 — Durable Outbox Delivery + Dispatcher/Worker — CONCLUÍDO E CERTIFICADO

Foi criado `DurableFiscalOutboxWorker` com claim/lease commitado antes do I/O externo, handler fora da transação SQLite, finalização em nova Unit of Work, retry/backoff durável, recovery de lease após crash, DLQ e fencing por `attempt_count`.

Gate definitivo:

- SHA: `56678f730f2e7c3c235530887612a7ee71b5efc8`;
- Actions run: `34663828770` — **SUCCESS**;
- Install PASS; Ruff PASS; Mypy strict PASS — 63 source files;
- Pytest: **322 PASS em 1.16s**;
- baseline pós-Inbox: 316 testes; +6 testes.

## Bloco funcional 3 — Signed Webhook Delivery — CONCLUÍDO E CERTIFICADO

Foi criada a camada `application/webhook_delivery.py`, integrada ao `DurableFiscalOutboxWorker` através do contrato já existente `FiscalOutboxHandler`.

### Reuso obrigatório da segurança V2-05

`SignedWebhookOutboxHandler` usa diretamente `WebhookSecurity.sign(...)`. Portanto, o bloco não cria algoritmo criptográfico paralelo: HMAC-SHA256, canonical material `unix_timestamp + '.' + raw_body`, `key_id`, formato `t=<unix>,kid=<key-id>,v1=<hex>`, tolerância temporal e overlap de rotação permanecem sob a primitive certificada no V2-05.

O corpo assinado é exatamente `FiscalOutboxEntry.payload`, o mesmo payload durável que será enviado pelo transporte. Isso evita divergência entre bytes assinados e bytes entregues.

### Contrato de destino e transporte

Foram adicionados contratos host-neutral:

- `WebhookDestination`;
- `WebhookDestinationResolver`;
- `WebhookDeliveryRequest`;
- `WebhookDeliveryResponse`;
- `WebhookTransport`;
- `WebhookDeliveryClock`;
- `SignedWebhookOutboxHandler`.

Destino exige URL HTTPS absoluta, sem credenciais embutidas e sem fragmento. Segredos não pertencem ao objeto de destino.

O transporte permanece injetável: o Core não ficou acoplado a `requests`, `httpx`, API Gateway ou fornecedor específico. O adapter HTTP real poderá ser conectado posteriormente sem alterar a semântica central.

### Headers e rastreabilidade

A entrega inclui:

- `Content-Type: application/json`;
- `X-FM-Webhook-Signature` com a assinatura certificada;
- `X-FM-Correlation-ID`;
- `X-FM-Outbox-Entry-ID`;
- `X-FM-Delivery-Attempt`.

O header obrigatório de assinatura permanece exatamente o definido no AsyncAPI v1.1.0. Nenhuma alteração do contrato foi necessária neste bloco.

### Classificação de resposta

O handler converte resposta do transporte em resultado do worker:

- HTTP 2xx -> `SUCCEEDED`;
- HTTP 408, 425, 429, 5xx e respostas provisórias < 200 -> `RETRYABLE_FAILURE`;
- demais respostas não-2xx, inclusive 3xx e erros 4xx não-retryable -> `FATAL_FAILURE` e DLQ pelo worker.

Falha de configuração sem destino também é fail-closed e vai diretamente para dead-letter sem realizar I/O.

### Retry e nova assinatura

Cada nova tentativa é assinada novamente usando o relógio da entrega. O teste de 429 comprova que o estado entra em `RETRY_WAIT`, respeita o backoff durável e a segunda tentativa possui novo timestamp e novo `X-FM-Delivery-Attempt`.

### Rotação

A suíte usa um emissor assinando com a chave anterior enquanto o receptor possui a chave anterior e a chave atual, com a atual ativa. A verificação é aceita, comprovando integração real com o overlap de rotação já certificado no V2-05.

### Compatibilidade AsyncAPI

Teste dedicado lê `contracts/v1/asyncapi.json` e comprova:

- versão permanece `1.1.0`;
- header requerido continua `X-FM-Webhook-Signature`;
- algoritmo continua `HMAC-SHA256`;
- `security_stage` continua `V2-05_CERTIFIED`.

Logo, não houve breaking change nem bump artificial do contrato.

### Gate de certificação do bloco

A primeira tentativa de CI do bloco, run `34664156025`, passou Install/Ruff/Mypy e falhou somente porque o helper de teste chamou um método inexistente de conveniência no `FiscalApplicationService`. O teste foi corrigido para usar a superfície já certificada `FiscalOutboxService(uow.outbox)`, sem mudança semântica na implementação.

Gate definitivo:

- SHA: `8321106338aca262a76fe2bdfa76665bdcc57950`;
- Actions run: `34664214273` — **SUCCESS**;
- Install: **PASS**;
- Ruff: **PASS**;
- Mypy strict: **PASS — 64 source files sem issues**;
- Pytest completo: **331 PASS em 1.05s**;
- baseline pós-Outbox Worker: 322 testes; **+9 testes** neste bloco.

Compare específico do bloco contra o checkpoint anterior `6b90df9021c0f9f6fd725524027333f13f1cd596`: 5 commits à frente, 0 atrás, alterando apenas CI temporário, export da aplicação, novo handler de webhook e testes.

Após o gate verde, o CI foi restaurado para `workflow_dispatch` no commit `cd1dc973e6502074e173fbc9178d1aedec0a3fe7`.

## Escopo restante do V2-08

Ainda permanecem pendentes antes do fechamento da fase:

- auditoria durável end-to-end de cada tentativa de entrega e resultado final, além do estado resumido da outbox;
- ordering governado quando houver chave explícita, sem introduzir fila global obrigatória;
- teste explícito de duplicate webhook delivery/consumer idempotency atravessando outbox + assinatura + inbox;
- revisão final de aderência AsyncAPI/Bridge e de rastreabilidade;
- gate final consolidado da V2-08;
- auditoria final do diff completo contra V2-07;
- riscos residuais e limites de produção documentados.

## Limites

A certificação dos três blocos não conclui V2-08. Não houve merge, deploy, cutover, segredo real, homologação externa ou promoção para produção.

## Próximo bloco

**V2-08 permanece EM EXECUÇÃO. Inbox, Durable Outbox Worker e Signed Webhook Delivery estão CONCLUÍDOS E CERTIFICADOS. O próximo bloco é auditoria end-to-end + ordering governado + prova de duplicate delivery idempotente, seguido do gate final consolidado da V2-08.**
