# V2-08 — Events / Webhooks / Inbox / Outbox

Status: **EM EXECUÇÃO — DURABLE INBOX CERTIFICADA**  
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
- webhook signing continua usando a segurança certificada no V2-05;
- nenhum consumidor específico (Kordena, Iron Fit, Vendedor IA, CampaIA ou futuro produto) entra no núcleo.

## Bloco funcional 1 — Durable Inbox — CONCLUÍDO E CERTIFICADO

O primeiro bloco funcional do V2-08 foi implementado sobre a persistência certificada no V2-07.

### Contrato e identidade

Foi criada a superfície `kordena_fiscal.events` com `FiscalInboxEntry`, `FiscalInboxStatus`, `FiscalInboxStore`, `FiscalInboxService`, `FiscalInboxReceiveResult`, `InboxConflictError`, `InboxStateError` e `build_inbox_entry_id(...)`.

A identidade da mensagem é determinística e particionada por `ExecutionScope` + producer + upstream `event_id`. Assim, o mesmo `event_id` pode existir legitimamente em hosts/contas/unidades diferentes sem colisão, enquanto reutilização da mesma identidade semântica com conteúdo diferente falha fechado.

O payload é persistido junto do SHA-256 e o objeto valida a correspondência entre conteúdo e digest. `correlation_id`, `causation_id` e `idempotency_key` são preservados para rastreabilidade end-to-end.

### Estados governados

O lifecycle da inbox possui quatro estados: `RECEIVED`, `PROCESSING`, `PROCESSED` e `REJECTED`.

Transições são protegidas por versão otimista. `begin_processing` exige `RECEIVED`; conclusão/rejeição exigem `PROCESSING`; versão stale ou transição inválida gera `InboxStateError`. Estados terminais registram `processed_at` e resultado ou erro conforme o caso.

### Deduplicação

Receber novamente a mesma identidade semântica e o mesmo conteúdo retorna replay da entrada já persistida, inclusive depois de restart do processo. O novo instante de recebimento não substitui a primeira recepção.

Se a mesma identidade for reutilizada com payload ou metadados semânticos diferentes, o processamento falha fechado com `InboxConflictError`.

### Integração transacional V2-07

Foi criada a migration SQLite **v2** (`v2_08_durable_inbox`) com tabela `fm_fiscal_inbox`, chave primária determinística, constraint única da identidade semântica e índice de status.

`FiscalUnitOfWork` agora expõe `inbox` ao lado de idempotência, sequência, outbox, archive, binding, lifecycle e reconciliação. O adapter `SqliteFiscalInboxStore` participa do mesmo `BEGIN IMMEDIATE` do V2-07.

O teste transacional comprova que inbox + outbox inseridas na mesma Unit of Work são revertidas juntas quando não ocorre commit. Isso estabelece a base para consumidores que, nos próximos blocos, precisarão registrar o consumo e o side effect assíncrono no mesmo limite transacional.

`FiscalApplicationService` também ganhou operações transacionais para receber, iniciar processamento, concluir, rejeitar e consultar eventos da inbox.

### Upgrade controlado

A suíte comprova a atualização de um banco no estado V2-07, preservando migration 1 e aplicando somente migration 2 da Durable Inbox. A migration é idempotente e não reaplica o schema anterior.

### Testes do bloco

O bloco acrescentou 7 testes sobre o baseline V2-07 de 309 testes: replay após restart, conflito por conteúdo divergente, lifecycle versionado, terminal rejeitado, rollback inbox+outbox, isolamento por host e upgrade de schema V2-07 -> inbox.

### Gate de certificação do bloco

Gate definitivo da Durable Inbox:

- SHA: `f467d0dafa70e3c0debd3aacccbb183c954c5b35`;
- Actions run: `34662707064` — **SUCCESS**;
- Install: **PASS**;
- Ruff: **PASS**;
- Mypy strict: **PASS — 62 source files sem issues**;
- Pytest completo: **316 PASS em 0.85s**.

O primeiro gate funcional (`ac1854b25c14d7721daac1e7fc678905e6fe1c39`) falhou somente em uma linha E501 do Ruff. A correção foi estritamente de formatação. Após adicionar o teste explícito de upgrade V2-07 -> inbox, o gate definitivo acima permaneceu 100% verde.

Após a certificação deste bloco, o workflow foi novamente restaurado para `workflow_dispatch` apenas no commit `c9e26364e2f0925439ac86e146a8ab5668f57c3b`.

## Escopo restante do V2-08

Ainda permanecem pendentes antes do fechamento da fase:

- durable outbox delivery state sobre a persistência criada no V2-07;
- worker/dispatcher desacoplado para claims, retries, success e dead-letter;
- política de backoff e limite de tentativas;
- recuperação de lease expirado após crash;
- webhook delivery usando assinatura HMAC-SHA256, `key_id`, timestamp e anti-replay já certificados;
- auditoria de tentativas de entrega e resultado final;
- preservação de ordering quando houver chave de ordenação explícita, sem criar fila global obrigatória;
- integração com os contratos AsyncAPI/Bridge existentes sem breaking change indevido;
- testes adicionais de duplicate delivery, retry, lease expiry, concorrência e DLQ.

## Limites

A certificação da Durable Inbox não conclui o V2-08. Não houve merge, deploy, cutover, segredo real, homologação externa ou promoção para produção.

## Gate de fechamento futuro

V2-08 somente poderá ser marcado `CONCLUÍDO` após Durable Inbox certificada, dispatcher/outbox com retry/backoff/lease/DLQ, delivery de webhook assinado e verificado, testes de concorrência/restart/replay e falhas permanentes, aderência ao AsyncAPI/Bridge existente, gate completo verde, auditoria final do diff e riscos residuais documentados.

## Próximo bloco

**V2-08 permanece EM EXECUÇÃO. O primeiro bloco funcional — Durable Inbox — está CONCLUÍDO E CERTIFICADO. O próximo bloco é Durable Outbox Delivery + Dispatcher/Worker, com claim/lease, retry/backoff e dead-letter.**
