# V2-08 — Events / Webhooks / Inbox / Outbox

Status: **CONCLUÍDO E CERTIFICADO**  
Branch: `v2/events-webhooks-inbox-outbox`  
PR: **#9 Draft**  
Base certificada: V2-07 (`v2/application-durable-persistence`).

## Objetivo cumprido

A V2-08 estabelece a camada assíncrona durável e host-neutral do FM Fiscal: inbox idempotente, outbox durável, worker com claim/lease/retry/DLQ, webhook assinado e verificado, auditoria persistente por tentativa, ordering somente quando explicitamente solicitado e prova integrada de duplicate delivery sem duplicação de efeito fiscal/local.

A semântica permanece at-least-once. O Core não promete exactly-once de rede; ele combina outbox durável, identidade estável e consumidor/inbox idempotente para impedir que reentregas legítimas corrompam estado.

## Princípios certificados

- nenhum side effect assíncrono depende apenas de memória de processo;
- claim/lease é commitado antes de I/O externo;
- I/O externo nunca mantém a transação SQLite local aberta;
- retries são limitados, persistidos e auditáveis;
- falha permanente termina em `DEAD_LETTER`;
- leases expiradas são recuperáveis e worker stale perde autoridade por fencing de `attempt_count`;
- assinatura reutiliza `WebhookSecurity` da V2-05, sem algoritmo criptográfico paralelo;
- assinatura é calculada sobre exatamente os bytes persistidos na outbox;
- verificação de assinatura ocorre antes da aceitação na inbox;
- duplicate delivery terminal vira replay/no-op e não reaplica o consumidor;
- efeito do consumidor pode ser persistido no mesmo `FiscalUnitOfWork` que marca a inbox como `PROCESSED`;
- ordering existe somente para uma chave explícita e para a mesma partição fiscal; mensagens sem chave continuam independentes;
- nenhuma fila global obrigatória, nenhum consumidor específico de produto e nenhum adapter de produção foram introduzidos.

## Bloco 1 — Durable Inbox — certificado

`kordena_fiscal.events` implementa `FiscalInboxEntry`, lifecycle `RECEIVED -> PROCESSING -> PROCESSED/REJECTED`, optimistic versioning, identidade determinística por partição fiscal + producer + upstream `event_id`, SHA-256 do payload e preservation de correlation/causation/idempotency.

A migration SQLite v2 `v2_08_durable_inbox` integrou a inbox ao mesmo UoW da persistência V2-07. Replay após restart, conflito semântico fail-closed, isolamento por host e rollback conjunto inbox+outbox foram comprovados.

Gate: `f467d0dafa70e3c0debd3aacccbb183c954c5b35`, run `34662707064` — **SUCCESS**; 62 source files; 316 PASS.

## Bloco 2 — Durable Outbox Delivery + Dispatcher/Worker — certificado

`DurableFiscalOutboxWorker` usa transações curtas: claim/lease + commit, I/O fora da transação, e nova UoW para success/retry/dead-letter. Retry/backoff sobrevive restart; lease expirada é recuperada; dois workers não despacham a mesma lease ativa; stale worker não consegue finalizar depois de reclaim.

Gate: `56678f730f2e7c3c235530887612a7ee71b5efc8`, run `34663828770` — **SUCCESS**; 63 source files; 322 PASS.

## Bloco 3 — Signed Webhook Delivery — certificado

`SignedWebhookOutboxHandler` reutiliza diretamente `WebhookSecurity.sign(...)` da V2-05: HMAC-SHA256, `key_id`, timestamp, tolerância temporal, anti-replay temporal e overlap de rotação permanecem na primitive certificada.

O header obrigatório continua `X-FM-Webhook-Signature` no formato `t=<unix>,kid=<key-id>,v1=<hex>`. Destino exige HTTPS absoluto, sem credenciais embutidas e sem fragmento. 2xx é sucesso; 408/425/429/5xx/<200 é retryable; demais não-2xx são fatais/DLQ. Retry gera nova assinatura e novo número de tentativa.

Teste dedicado manteve `contracts/v1/asyncapi.json` em v1.1.0 e confirmou compatibilidade sem breaking change.

Gate: `8321106338aca262a76fe2bdfa76665bdcc57950`, run `34664214273` — **SUCCESS**; 64 source files; 331 PASS.

## Bloco 4 — fechamento funcional — auditoria + ordering + duplicate delivery

### Auditoria durável por tentativa

Foi criada a migration SQLite v3 `v2_08_delivery_audit_and_ordering` e a superfície `FiscalDeliveryAttempt` / `FiscalDeliveryAuditStore`.

Cada tentativa registra durablemente:

- `entry_id` e `attempt_count`;
- partição fiscal e `correlation_id`;
- operação e `ordering_key`, quando houver;
- `CLAIMED`, `SUCCEEDED`, `RETRY_SCHEDULED`, `DEAD_LETTER` ou `LEASE_EXPIRED`;
- início/fim, próximo instante de retry, referência final e erro.

O worker grava o início da auditoria na mesma transação do claim e grava o resultado na mesma transação da mudança de estado da outbox. A suíte prova persistência da auditoria após restart, `RETRY_SCHEDULED -> SUCCEEDED` e `LEASE_EXPIRED -> SUCCEEDED` após crash/reclaim.

### Ordering governado

`fm_fiscal_outbox_ordering` associa opcionalmente uma entrada a uma `ordering_key`. O claim bloqueia uma entrada apenas quando existe uma mensagem anterior, na mesma partição fiscal e na mesma chave, que ainda não chegou a `SUCCEEDED` ou `DEAD_LETTER`.

Consequências deliberadas:

- nenhuma chave -> nenhuma dependência de ordenação;
- chaves diferentes continuam paralelizáveis;
- retry de uma mensagem mantém bloqueadas apenas as posteriores da mesma stream;
- `DEAD_LETTER` é terminal e libera a stream para não criar bloqueio infinito;
- não foi criada fila global nem serialização sistêmica.

### Recepção assinada e duplicate delivery idempotente

`SignedWebhookInboxReceiver` verifica `WebhookSignature` antes de abrir a aceitação durável. Em seguida, dentro de uma única UoW local:

1. recebe/deduplica a mensagem na inbox;
2. inicia `PROCESSING` quando a mensagem ainda precisa de efeito;
3. chama o consumidor com a mesma UoW;
4. grava o side effect local e marca a inbox `PROCESSED` no mesmo commit.

A prova integrada executa `outbox -> webhook assinado -> receiver -> inbox/consumer` e o transporte entrega intencionalmente o mesmo request assinado duas vezes. A primeira entrega aplica o consumidor; a segunda encontra a inbox terminal e retorna replay sem nova invocação. O side effect é persistido uma única vez. Assinatura inválida é rejeitada antes de qualquer linha de inbox ser criada.

### Upgrade de schema

A suíte certifica os dois caminhos:

- banco no estado V2-07, migration 1 presente: aplica migrations 2 e 3 sem reaplicar v1;
- banco no checkpoint V2-08 Inbox, migrations 1 e 2 presentes: aplica somente migration 3.

## Gate final consolidado

Primeira tentativa do fechamento, run `34666540502`, passou Install, Ruff e Mypy (67 source files) e falhou somente porque 22 asserts legados ainda esperavam a lista de migrations `(1, 2)` após a introdução intencional da migration v3. Os asserts/migration tests foram atualizados; não houve rollback nem mudança de semântica para mascarar falha funcional.

Gate funcional final reforçado:

- SHA: `bc77ee4cf2b7151d06c09cf32ca9168363ece1c7`;
- Actions run: `34666753555` — **SUCCESS**;
- Install: **PASS**;
- Ruff: **PASS**;
- Mypy strict: **PASS — 67 source files sem issues**;
- Pytest completo: **337 PASS em 1.35s**;
- baseline V2-07: 309 testes; V2-08 final: **+28 testes líquidos**.

## Auditoria final do diff contra V2-07

Compare do gate `bc77ee4...` contra `v2/application-durable-persistence` (`e767ec36290f3304e495ce8fbeee6522f041d599`): **65 commits à frente, 0 atrás**.

O diff está limitado a:

- documentação/tracker V2-08 e snapshot pré-fase;
- `application` para worker, webhook delivery/receiving e integração inbox;
- `events` para inbox e delivery audit;
- `persistence` para migration v2/v3, stores e UoW;
- testes V2-08 e atualização das expectativas de migration;
- alteração temporária de CI para certificação.

Não houve alteração em contratos OpenAPI/AsyncAPI/JSON Schema no fechamento, nem código de deploy, segredo real, provider fiscal, adapter HTTP de produção, infraestrutura, promoção ou cutover.

## Riscos residuais / limites deliberados

- transporte HTTP real, secret manager/vault e rotação operacional de chaves pertencem aos adapters de produção posteriores (V2-12);
- entrega de rede é at-least-once; consumidores externos continuam obrigados a respeitar idempotência pela identidade do evento;
- ordering é opt-in e local à chave/partição, não garantia global;
- `DEAD_LETTER` exige governança operacional futura para inspeção/replay controlado;
- telemetria operacional ampla, métricas/SLOs e compliance runtime permanecem para V2-13/V2-14;
- nenhuma homologação fiscal externa ou produção foi executada nesta fase.

## Fechamento

**V2-08 está CONCLUÍDO E CERTIFICADO.** A PR #9 permanece Draft e sem merge. Nenhum deploy, promoção ou cutover foi realizado. O próximo bloco liberado pelo Plano Mestre é **V2-09 — Modularização de verticais**.
