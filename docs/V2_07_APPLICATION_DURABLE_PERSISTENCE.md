# V2-07 — Application Service + Persistência Durável

Status: **EM EXECUÇÃO**  
Branch: `v2/application-durable-persistence`  
Dependência certificada: V2-06.

## Objetivo

Transformar o FM Fiscal Core de biblioteca de domínio em motor operável por uma camada de aplicação independente, preservando as regras fiscais no domínio e movendo estado operacional crítico para contratos de persistência durável.

## Princípio arquitetural

A aplicação coordena; o domínio decide; o repositório persiste.

Nenhuma regra fiscal é escondida em controller, SQL ou repository. Transições continuam sob `FiscalStateMachine`, reconciliação continua sob `FiscalReconciliationEngine`, idempotência e sequência preservam seus contratos certificados, e a camada SQLite apenas materializa esses estados com atomicidade e controle de concorrência.

## Portas de persistência

V2-07 acrescenta portas explícitas para:

- binding host -> conta/unidade fiscal;
- lifecycle com optimistic concurrency;
- estado de reconciliação;
- Unit of Work transacional.

As portas existentes são reutilizadas para:

- idempotência de emissão;
- sequência fiscal;
- outbox;
- archive.

`FiscalUnitOfWork` reúne essas superfícies em uma transação local única.

## Application Service universal

`FiscalApplicationService` é host-neutral e não conhece Kordena, Iron Fit, Vendedor IA, CampaIA ou qualquer vertical futura. Ele fornece coordenação transacional para:

- registrar e resolver bindings;
- reservar a autoridade de uma emissão antes de qualquer side effect externo;
- persistir lifecycle por transições válidas;
- finalizar autorização/rejeição acoplando lifecycle + idempotência na mesma transação;
- reservar numeração;
- registrar outbox e archive;
- executar e persistir reconciliação.

I/O externo de provider permanece fora das transações locais.

## Regra de crash/restart

A reserva de emissão persiste atomicamente `IssuanceAttempt` e o lifecycle inicial antes de comunicação externa.

Ao reiniciar o processo, a mesma chave/fingerprint não gera nova emissão:

- tentativa já autorizada -> `AUTHORIZED_REPLAY`;
- tentativa já rejeitada -> `REJECTED_REPLAY`;
- tentativa ainda `RESERVED` -> `RECOVERY_REQUIRED`;
- apenas uma intenção realmente nova -> `FRESH`.

`RECOVERY_REQUIRED` é fail-closed: significa que o processo deve consultar/reconciliar o provider antes de tentar novo side effect. Isso cobre a janela crítica de crash depois da solicitação externa e antes do registro do resultado, evitando duplicação silenciosa.

## SQLite durable reference adapter

V2-07 inclui um adapter SQLite filesystem-backed, sem nova dependência de runtime. `:memory:` é recusado explicitamente para a superfície durável.

A migration controlada v1 cria estado durável para:

- idempotency attempts;
- fiscal sequences;
- lifecycle;
- fiscal bindings;
- outbox;
- archive metadata + conteúdo;
- reconciliation state;
- schema migration ledger.

Os writers entram com `BEGIN IMMEDIATE`, serializando mutações concorrentes antes da leitura do estado fiscal mutável. Lifecycle usa versão otimista; chaves críticas possuem constraints/PKs explícitas.

## Limites

SQLite é o adapter durável de referência e habilita operação single-node/process-restart. Ele não é apresentado como banco distribuído multi-region. Adapters de infraestrutura distribuída podem implementar as mesmas portas sem contaminar domínio/application service.

V2-07 não cria servidor HTTP público, não altera o Bridge V1, não introduz segredo/certificado real, não executa homologação externa, merge, deploy ou cutover.

Delivery assíncrono completo, inbox, retries/DLQ operacionais e workers pertencem ao V2-08.

## Gate de fechamento

V2-07 somente poderá ser marcado `CONCLUÍDO` após:

- migration idempotente;
- restart real sobre arquivo SQLite mantendo autoridade;
- replay de idempotência sem duplicação;
- sequência contínua após restart;
- lifecycle durável e protegido por versão;
- binding, outbox, archive e reconciliação recuperáveis após restart;
- rollback de Unit of Work comprovado;
- cenário de crash em `TRANSMITTING` retornando `RECOVERY_REQUIRED`;
- recuperação seguida de finalização atômica e replay autorizado;
- Ruff PASS;
- Mypy strict PASS;
- Pytest completo PASS;
- CI definitivo verde com SHA/run registrados;
- diff auditado contra V2-06;
- riscos residuais documentados;
- PR Draft preservada, sem merge e sem deploy.
