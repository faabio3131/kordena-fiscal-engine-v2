# V2-17.3 — CUTOVER REHEARSAL / AUTHORITY TRANSFER CLOSURE

Data: 2026-09-13

Status inicial: **EM EXECUÇÃO — SOMENTE REHEARSAL SINTÉTICO/CONTROLADO**.

## Objetivo

Transformar V2-17.1 (readiness + single authority) e V2-17.2 (migration/rollback rehearsal)
em uma orquestração explícita de transferência de autoridade, sem qualquer efeito produtivo.

## Máquina de estados

A implementação `kordena_fiscal.convergence.cutover_rehearsal` utiliza:

1. `PRECHECK`
2. `FREEZE_REQUESTED`
3. `WRITERS_FROZEN`
4. `SNAPSHOT_CAPTURED`
5. `MIGRATION_VALIDATED`
6. `MIGRATION_APPLIED`
7. `RECONCILIATION_VALIDATED`
8. `AUTHORITY_TRANSFER_READY`
9. `V2_AUTHORITY_ACTIVE`
10. `POST_TRANSFER_VALIDATION`
11. `CLOSED`

Caminhos controlados adicionais:

- `ABORT`
- `ROLLBACK_REQUIRED`
- `ROLLBACK_IN_PROGRESS`
- `ROLLED_BACK`

## Invariantes obrigatórios

O rehearsal falha fechado quando houver:

- blocker obrigatório na readiness matrix;
- writer legado não congelado;
- snapshot inconsistente;
- migração conflitante ou não determinística;
- regressão de sequence;
- perda de idempotência;
- inbox/outbox não reconciliadas;
- unknown outcome pendente;
- falha de integridade do archive;
- falha de lifecycle;
- falha de binding;
- promoção de readiness causada por migração;
- perda de provider state;
- trilha de auditoria incompleta.

## Barreira de produção

A classe `CutoverRehearsal` rejeita explicitamente:

- migração marcada como efeito produtivo;
- ativação de autoridade V2 não simulada.

Essa proteção é adicional à governança documental. O código desta fase não contém adapter de
produção, não recebe segredo real e não desliga writers reais.

## Restart e rollback

`CutoverRehearsalCheckpoint` permite checkpoint/restore do estágio sintético sem regressão de
estado. Rollback pode ser ensaiado antes ou depois da ativação **simulada** da autoridade V2,
mas somente conclui quando os invariantes pós-rollback estão verdes.

## Cenários mínimos de certificação

A suíte dedicada cobre:

- happy path;
- blocker obrigatório;
- writer legado inesperado;
- snapshot inconsistente;
- conflito de migração;
- migração não determinística;
- tentativa de migração produtiva;
- falha individual de invariantes materiais;
- tentativa de authority activation real;
- checkpoint/restart;
- rollback pré-transferência;
- rollback pós-transferência simulada;
- abort;
- transição fora de ordem;
- unknown outcomes inválidos.

## Limites preservados

Esta fase NÃO prova:

- writers reais de um ambiente produtivo;
- snapshot real de cliente;
- conectividade oficial SEFAZ/prefeitura/provider;
- homologação oficial;
- autorização para cutover.

Esses elementos permanecem gates externos/humanos e não podem ser sintetizados.
