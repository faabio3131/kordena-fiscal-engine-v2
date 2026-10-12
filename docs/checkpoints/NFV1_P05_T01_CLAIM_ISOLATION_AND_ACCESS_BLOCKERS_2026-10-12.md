# NFV1-P05-T01 — isolamento pré-claim e continuidade operacional

Data: 2026-10-12 (America/Sao_Paulo). Produto: FM NFCORE V1.
Repositório: `faabio3131/kordena-fiscal-engine-v2`.
Main confirmada: `cb3c640e2ddc16e02aa491874140beedc113540e`.
PR #175 MERGED. CI #831/run38313245111 e Governance #252/run38313245124 SUCCESS.
Branch candidata: `fix/nfv1-p05-t01-scoped-worker-claims`.
PR/HEAD/CI da candidata: registrar após publicação; não certificados neste registro.

## CURRENT e autorização

O dono determinou retomar P05, configurar/validar GSM real, resolver isolamento
Worker e executar planejamento somente leitura. Aprovação específica continua
obrigatória antes de schema, migrations ou publicação de serviços. Esta retomada
do pré-deploy P05 não conclui nem inicia outras tarefas do ledger (inclusive P09).

Railway project `b84b290d-f3b4-46a1-9023-0b761cb96b0d`, environment
`c9878b9b-62b2-4a97-b8ba-743c8a3e99ec` tem label `production`, mas pertence
ao **FM NFCORE Staging**, não à infraestrutura produtiva de P11.

| Serviço | Deployment confirmado | Data | Réplicas running/total |
|---|---|---|---|
| API | c0f8fb2b-30e3-45f8-a814-73c0ba97506b | 04/10 | 1/1 |
| Portal | 35b7aafc-b509-4851-a572-c0bd46781977 | 04/10 | 1/1 |
| Worker | 3215f498-0aa1-4ce3-8e61-cc74b72b68b6 | 01/10 | 0/1 |
| Postgres | ce9b66e7-6de7-4c70-9852-8ca1936a719b | 01/10 | 1/1 |

API sem preDeployCommand (lista vazia); Worker restart policy NEVER.
Worker deployment SUCCESS/serviço Online não é processo contínuo operacional.
Postgres usa imagem18 e somente rede privada, sem TCP proxy público.
Nenhuma configuração Railway foi alterada. O connector OAuth devolve nomes de
variáveis, com `valuesRedacted=true`; não fornece DSN/SSH para preflight SQL.

## CURRENT → TARGET e mapa de impacto

A composição GSM #175 possui assinatura restrita a tenant/unidade, mas o poll
reivindica globalmente antes de verificar escopo. Negar dispatch posteriormente
não impede lease, tentativa, auditoria/retry/dead-letter indevidos nos outros jobs.

TARGET interno: seleção explícita e imutável `OutboxClaimSelection` na outbox
existente, por host + tenant + unidade + ambiente fiscal + operação. Filtro SQL
antes do LIMIT e antes de UPDATE/lease/attempt; validação defensiva com rollback
se um store retornar partição estranha. Métricas agregam a mesma seleção.
Correlação do job não integra a identidade da partição.

Autoridades reutilizadas: ExecutionScope, stores outbox SQLite/Postgres,
FiscalUnitOfWork, CAS/attempt fence, DurableFiscalOutboxWorker, handler registry,
SecretBinding/SecretResolver, assinatura/egress existentes e WorkerObservability.
Mapa: contrato outbox → store → worker → composição → entrypoint → GSM bootstrap.
Nenhuma migration/schema novo, fila, autenticação, persistência ou regra fiscal
paralela. Nenhuma credencial real lida/gerada/distribuída pelo patch.

O bootstrap requer `NFCORE_WORKER_GSM_HOST_NAMESPACE` e cria composição
explicitamente isolada em homologation. Não usa wildcard/fallback global.
Preserva todos os requisitos anteriores de identidade/segredo e probe ONESHOT.
O piloto continua uma partição configurada: não é registry dinâmico de todos os
tenants e não significa cobertura comercial multi-tenant completa.

## Planejamento estrutural das migrations — sem execução remota

Fonte CURRENT: constantes canônicas, `migration_guard.py`, `PostgresFiscalDatabase`
e CaktoCommercialDatabase. Última evidência SQL do operador em 12/10: fiscal1..12;
tabela de rastreio Cakto ausente. **Não foi possível reconfirmar o banco nesta sessão.**

| Ordem | Migration | Efeito aditivo previsto |
|---|---|---|
| 13 | scoped_fiscal_projections | colunas de escopo no lifecycle e índices canônicos |
| 14 | customer_configuration_commands_and_egress | revisão/idempotência de configuração e metadata de aprovação de destinos |
| 15 | command_commercial_ingress | bindings/auditoria/inbox/correlações do Command |
| 16 | commercial_contracted_periods | referência de pagamento e contratos comerciais |
| 17 | external_secret_bindings | referências e metadata GSM; nenhum material secreto |
| Cakto1 | web11_cakto_commercial_activation | bindings, inbox, tenants e entitlements canônicos |
| Cakto2 | cl11_cakto_canonical_reconciliation | callback/subscription metadata e índice |

Criar schema Cakto não seleciona/ativa Cakto como gateway. Pagamentos da plataforma
continuam governados pelo Command conforme política aprovada.
ALTER/CREATE INDEX exigem janela governada; não presumir ausência de lock/drift.
O apply canônico tem transações separadas para fiscal e Cakto: uma falha Cakto
após fiscal não implica rollback automático do primeiro commit. Retomar somente
após diagnóstico e novo preflight, sem down-migration improvisada.

Execução read-only pendente, fora do startup Railway e com DSN entregue pelo canal
privado, sem imprimir valores:

```sh
PGOPTIONS='-c default_transaction_read_only=on' \
NFCORE_ENVIRONMENT=staging \
python scripts/ci/migration_guard.py --plan-staging
```

O operador não deve definir `NFCORE_SCHEMA_MIGRATION_APPROVED=true` nesse passo.
Sem relação esperada/ordem contígua, o guard deve bloquear. Aplicação somente
pelo orquestrador canônico após aprovação específica, backup e gates.

## Backup já restaurado: preservar, não repetir

Evidência canônica existente: ciphertext age 78.572 bytes, SHA256
`58ae2d97cc40f26c89900e7f349211f89770255f57427231d38ac5f8bafeded6`;
PG18 restore exit0,34 tabelas, ambiente descartado, atestado pelo operador.
Usar o verificador existente `local-logical-attested`, com arquivo privado real,
SHA/age/integridade/idade <=72h e custódia da chave confirmados antes de aplicar.
Não recriar restore por rotina nem copiar ciphertext/chave para Git.
O arquivo físico e a custódia não foram verificados nesta sessão.
Não há prova de PITR, retenção independente nem RPO/RTO produtivos.

O baseline API/Portal histórico `f9b5b2c5b436045947159f1e76be9303f5a95d90`
foi inspecionado estaticamente: startup ainda chama initialize e readiness aceita
migrations não vazias. Isso não prova rollback operacional em PG18 atualizado;
o plano não autoriza DDL automático do código legado nem restore destrutivo.
Worker antigo permanece baseline degradado 0/1; Worker candidato deve comprovar
RUNNING/heartbeat/health com assinatura real e revisão exata.

## Gates e limites da prova

- Ruff PASS; Mypy strict PASS (203 source files).
- Testes dirigidos após patch:35 PASS,8 SKIP locais por ausência de PostgreSQL.
- Regressão local intermediária:1768 PASS,435 SKIP,2 warnings; não é certificação
  PostgreSQL nem CI da candidata final. Testes adicionais posteriores passam no
  gate dirigido; CI integral final permanece obrigatória.
- Plan validator PASS,59 IDs/checks preservados; secret scan PASS;
  migration policy PASS fiscal1..17/Cakto2; diff check PASS.
- Critérios novos: jobs estrangeiros anteriores ao LIMIT intactos; operação
  desconhecida e lease expirada estrangeira intactas; defesa de store corrompido
  com rollback; backlog isolado; factory→entrypoint preserva seleção; concorrência
  de Workers em duas partições PostgreSQL (prova remota ainda requerida).

## Blockers reais e próxima ação

1. Desktop Commander retornou limite mensal atingido: comandos pausados, device
   continua paired/online. Não reconectar nem repetir chamadas para contornar.
   Sem ele, não há backup físico/SSH privado PostgreSQL acessível nesta sessão.
2. Console GCP `fm-nfcore-staging` retornou Site Unavailable neste Cloud Browser.
   Nenhum connector GCP correspondente disponível. Não afirmar IAM real validado.
3. Reconciliar identidade worker/API segregadas, keyID/idade IAM ou WIF governada,
   IAM exact-secret, versões pinadas, auditoria Data Access e read/deny reais.
   Acesso a credential file e metadata de operador não prova key age independentemente.
4. Não existe prova de preflight SQL remoto atual, integridade atual do backup,
   GSM real, Worker operacional ou Web na revisão candidata.

Publicar candidata Draft e executar CI remota; merge continua sujeito à aprovação
humana. Recuperar acessos antes de pedir aprovação de schema/deploy. Depois dos
gates reais e aprovação: migrations governadas; API/Portal/Worker no mesmo SHA;
health/readiness/réplicas/login/recovery/RBAC/isolation e jornadas Web reais.
P05-T01 permanece BLOCKED_EXTERNAL; nenhuma checkbox foi promovida.
`EXTERNAL_SECRET_BACKEND_CERTIFIED=NOT MET`, `STAGING_CURRENT_SHA_E2E_CERTIFIED=NOT MET`,
`PRODUCTION_APPROVED=NO`, `COMMERCIAL_LIVE=NO`.
