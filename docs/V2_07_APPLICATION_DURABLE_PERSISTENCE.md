# V2-07 — Application Service + Persistência Durável

Status: **CONCLUÍDO E CERTIFICADO**  
Branch: `v2/application-durable-persistence`  
PR: **#8 Draft**  
Gate definitivo: `999ba84b9c25988441867820bfe8af0571269548`  
Actions run: `34659892798` — **SUCCESS**  
Dependência certificada: V2-06.

## Objetivo

Transformar o FM Fiscal Core de biblioteca de domínio em motor operável por uma camada de aplicação independente, preservando as regras fiscais no domínio e movendo estado operacional crítico para contratos de persistência durável.

## Princípio arquitetural

A aplicação coordena; o domínio decide; o repositório persiste.

Nenhuma regra fiscal foi escondida em controller, SQL ou repository. Transições continuam sob `FiscalStateMachine`, reconciliação continua sob `FiscalReconciliationEngine`, idempotência e sequência preservam seus contratos certificados, e a camada SQLite materializa esses estados com atomicidade e controle de concorrência.

## Portas de persistência

V2-07 acrescentou portas explícitas para:

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

`RECOVERY_REQUIRED` é fail-closed: o processo deve consultar/reconciliar o provider antes de tentar novo side effect. O teste de restart levou o lifecycle até `TRANSMITTING`, reabriu o banco em novo objeto de aplicação, recebeu `RECOVERY_REQUIRED`, registrou depois a autorização confirmada e comprovou replay posterior como `AUTHORIZED_REPLAY` sem duplicação silenciosa.

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

## Certificação

Gate definitivo executado sobre o SHA `999ba84b9c25988441867820bfe8af0571269548` no run `34659892798`:

- Install: **PASS**;
- Ruff: **PASS** — `All checks passed!`;
- Mypy strict: **PASS** — `Success: no issues found in 59 source files`;
- Pytest completo: **309 PASS em 0.94s**.

O baseline V2-06 possuía 305 testes; V2-07 adicionou 4 testes de integração durável cobrindo migration, restart, rollback transacional, persistência das autoridades fiscais e crash-recovery.

O primeiro run da fase falhou exclusivamente no gate Ruff por ordenação de imports. A correção foi cirúrgica, sem alteração semântica, e o run seguinte ficou integralmente verde.

## Auditoria do diff

Comparação final contra `v2/capability-readiness-api` no gate:

- branch 19 commits à frente e 0 atrás;
- 15 arquivos alterados;
- mudanças restritas a application service, persistence ports/adapters, testes, documentação/tracker e ativação temporária do CI de PR;
- nenhum contrato público do Bridge V1 foi alterado;
- nenhuma regra de provider, assinatura, segurança S2S, capability/readiness ou domínio regulatório foi movida para SQL/controller;
- nenhuma dependência externa nova foi adicionada;
- nenhum segredo, certificado, homologação externa, merge, deploy ou cutover foi realizado.

A PR #8 permanece **OPEN / DRAFT / mergeable**, sem merge.

## Riscos residuais governados

- SQLite é o adapter durável de referência para single-node/process-restart; não é apresentado como datastore distribuído multi-region;
- provider I/O não participa da transação SQLite: a janela entre side effect externo e persistência local é protegida por `RECOVERY_REQUIRED`, mas consulta/reconciliação automática e workers de recovery pertencem às próximas fases;
- inbox, delivery assíncrono completo, retries, DLQ e workers pertencem ao V2-08;
- adapters de persistência distribuída podem ser adicionados posteriormente pelas mesmas portas, sem contaminar domínio/application service;
- servidor HTTP produtivo, infraestrutura de produção e homologação real continuam fora do escopo desta fase.

## Limites

V2-07 não cria servidor HTTP público, não altera o Bridge V1, não introduz segredo/certificado real, não executa homologação externa, merge, deploy ou cutover.

Delivery assíncrono completo, inbox, retries/DLQ operacionais e workers pertencem ao V2-08.

## Decisão

**V2-07 está CONCLUÍDO E CERTIFICADO. V2-08 — Events/Webhooks/Inbox/Outbox fica LIBERADO. PR #8 permanece Draft, sem merge e sem deploy.**
