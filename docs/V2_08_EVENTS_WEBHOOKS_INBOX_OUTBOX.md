# V2-08 — Events / Webhooks / Inbox / Outbox

Status: **EM EXECUÇÃO — BOOTSTRAP DOCUMENTAL**  
Branch: `v2/events-webhooks-inbox-outbox`  
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

## Escopo inicial

O bloco V2-08 deve cobrir, no mínimo:

- durable inbox store com deduplicação e estado de processamento;
- durable outbox delivery state sobre a persistência criada no V2-07;
- worker/dispatcher desacoplado para claims, retries, success e dead-letter;
- política de backoff e limite de tentativas;
- recuperação de lease expirado após crash;
- webhook delivery usando assinatura HMAC-SHA256, `key_id`, timestamp e anti-replay já certificados;
- auditoria de tentativas de entrega e resultado final;
- preservação de ordering quando houver chave de ordenação explícita, sem criar fila global obrigatória;
- integração com os contratos AsyncAPI/Bridge existentes sem breaking change indevido;
- testes de restart, duplicate delivery, duplicate intake, retry, lease expiry e DLQ.

## Fora do escopo deste bootstrap

A abertura da branch/PR Draft não autoriza implementação cega. Antes do gate final, o diff deve permanecer limitado ao V2-08. Não haverá merge, deploy, cutover, segredo real, homologação externa ou promoção para produção nesta etapa de abertura.

## Gate de fechamento futuro

V2-08 somente poderá ser marcado `CONCLUÍDO` após:

- implementação completa da inbox durável;
- dispatcher/outbox com retry/backoff/lease/DLQ;
- delivery de webhook assinado e verificado;
- testes de concorrência/restart/replay e falhas permanentes;
- aderência ao AsyncAPI/Bridge existente;
- Install PASS;
- Ruff PASS;
- Mypy strict PASS;
- Pytest completo PASS;
- CI definitivo verde com SHA/run registrados;
- auditoria do diff contra V2-07;
- riscos residuais documentados;
- PR Draft preservada, sem merge e sem deploy.

## Estado deste commit

Somente o bootstrap documental e de governança da fase foi iniciado. A implementação funcional do V2-08 ainda não foi declarada concluída e deverá avançar de forma sequencial e auditável.
