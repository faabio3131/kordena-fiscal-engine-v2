# NFV1-P03-T05 — implementação interna de lifecycle comercial

Data: 2026-10-08 (America/Sao_Paulo). Estado atual: certificação interna
integrada; fechamento documental aguarda integração/gates próprios.
O registro final abaixo prevalece sobre pendências históricas da implementação.
Política: T05-B01 integralmente aprovada pelo dono (“Aprovo”).
Base: main c0e42fbb7ecfb1558c4aace664f971fb93eeeaba; PR #140 MERGED;
CI #701 e Governance #122 SUCCESS. Entrega na PR #141.

## CURRENT → TARGET e implementação

- Contrato canônico por purchase preserva pricing_id/version, plan/entitlements,
  quotas periódicas, cadence e carência da configuração original publicada.
  PlanDefinition.grace_days default0 e periodic_quotas default vazio usam a
  autoridade existente de publicação (plataforma, versão, audit e permissão).
- Cada invoice autenticada concede um período no mesmo contrato. Renewal usa
  start=max(término anterior,occurred_at), calendário/clamp mensal e cadence
  original. ONE_TIME não renova; pagamento tardio não cobre o intervalo anterior.
- Crédito por invoice persiste além do event_id, produto/ambiente/assinatura
  herdados do namespace/correlação Command. Mesmo crédito com novo ID é replay
  sem mudança de status, prazo ou uso; conteúdo/associação divergente falha fechado.
  Locks existentes do receiver serializam ingress; escrita do contrato tem CAS.
- Uma renovação antecipada preserva o uso no período ainda vigente. O período
  futuro inicia com0; operações são medidas no período efetivo do horário de
  ingresso. Datas/cadence, créditos e contadores anteriores não podem ser apagados.
  Snapshot histórico de uso permanece durável. Replay/late/pause/recovery não resetam.
- Status e validade temporal são reavaliados em entitlement/usage e claim/activation.
  GRACE só estende cobertura pelo valor contratado, default0. Pausa bloqueia,
  recovery não inventa tempo; cancel/refund/chargeback são terminais, com identidade
  e estado fiscal preexistente preservados. Leitura fiscal não recebe nova autoridade.
- Renewal funciona antes de claim/provisioning, sem criar org/OWNER/subscription;
  activation posterior usa os períodos contratados. Delivery no receiver fica restrito
  a opening events; retry da mesma ativação recupera falha de entrega sem duplicar OWNER.
- Migração16 aditiva: tabela fm_commercial_contracts + payment_reference em receipts.
  Registros legados permanecem; termos são reconstruídos do primeiro evento pago,
  pricing histórico e período durável existente. Sem prova desses dados, fail-closed.
  Readiness exige todas as migrations até16. Nenhuma migration produtiva executada.

## Verificação e limites

35 casos novos:20 canônicos duráveis SQLite +15 HTTP/PostgreSQL (CI).
Matriz: nove eventos, antes/depois de claim/activation; fim de mês/bissexto;
carência0/configurada e quotas; expired/recovery; early/late; ONE_TIME;
pricing posterior; invoice com IDs novos/conflito; concorrência/restart;
falha antes/depois do commit; upgrade15→16; uso/histórico/identidade/delivery.
Testes existentes de quota agora informam o horário determinístico da fixture;
não dependem da data da máquina para decidir validade. Nenhum teste apagado ou relaxado.
Expectativas de migration foram ampliadas para16, preservando checks legados.

Ruff/Mypy strict (195 arquivos)/migration policy16/secret scan/plan59/diff check PASS.
Dirigidos existentes e novos:79 PASS/14 PostgreSQL SKIP inicialmente; novos casos
finais19 PASS/13 PostgreSQL SKIP. DSN local ausente; resultados locais não certificam
PostgreSQL. Uma execução local completa anterior revelou seis falhas (cinco por
horário implícito de fixtures, uma por precedência de stale); causas corrigidas e
respectivos dirigidos verdes. A CI remota integral no HEAD publicado é obrigatória.
CI final, HEAD e tree exatos serão registrados na PR após conclusão dos gates.

Staging reconfirmado somente leitura: quatro serviços, sem novas falhas reportadas;
drift histórico/Worker0/1 permanece sob P4/P5/P9/P11. Nenhum deploy/mutação Railway.
Não prova Secret Manager/Command emissor/checkout/delivery reais (P6/P8), staging
CURRENT, homologação ou produção. Warning TestClient existente não suprimido.
T05 não concluída; P4 não iniciada. Merge/deploy/operação real não autorizados.
PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.

Revisão: Portal Uso projeta o período efetivo, preservando contadores após pagamento
antecipado. Upgrade também recupera receipt NULL legado somente após validar o
fingerprint autenticado do inbox; replay antigo não repete delivery de ativação mais
nova. Snapshot legado preserva plano/quotas já duráveis.23 testes canônicos/Portal PASS.

CI #704/run37871230173 no HEAD04dfde1 falhou:1557 PASS/13 FAIL/zero SKIP.
Causas:11 novos casos usavam nome legal diferente do snapshot da aquisição;
a autoridade existente rejeitou a troca. Fixture agora usa o nome canônico.
Dois asserts legados multiline ainda listavam migrations até15; ampliados até16.
Guards/testes preservados. Nova CI completa obrigatória no HEAD corrigido.

CI #706/run37871912756:1569 PASS/1 FAIL/zero SKIP. Todos34 novos casos passaram.
Regressão de trial same_key concorrente: réplica capturou horário antes da
reserva criada pela outra e aguardou lock. Sob o guard existente, replay usa
max(ingresso,created_at da reserva), sem mudar início/fim, plano, quota ou
identidade; não usa início de período pago futuro. Matriz existente preservada
e um novo teste garante o piso temporal e ausência de extensão do trial.
Nova CI integral exigida. Dependência mínima de T05; não reabre/antecipa fase.

## Certificação final interna e fechamento — 2026-10-08

O dono autorizou especificamente o merge #141 (“Aprovado”). PR MERGED;
HEAD certificado `32755fd1e3b7563561017c82cdb2f1871ccb7bca`;
merge/main `b8b25fda37a6682bc57eb2349f132770e46b0362`;
árvore idêntica PR/main `9f6eeed928faa5ab020570ce16491eecc0fc0d35`.

- CI #708/run37872723397, job113634399443 (PR) SUCCESS.
- CI #709/run37875267814, job113642298519 (main) SUCCESS.
- Governance #129/run37872723403 e #130/run37875267800 SUCCESS.
- PR/main:41/41 etapas;1571 Python/PostgreSQL,14 frontend,28 Playwright PASS;
  zero FAIL, zero SKIP.35 novos casos; warning TestClient existente.
- Ruff/Mypy strict195, plano59, migration16, secret scan, audits,
  frontend lint/type/build/E2E, containers/non-root/smokes/security/SBOM,
  PostgreSQL backup/restore/readiness PASS.

Nove eventos comerciais cobertos. Renovação avança período uma vez por invoice;
calendário e termos originais preservados. Early renewal mantém quota no período
efetivo; novo período começa em0. Cobertura temporal/carência/terminalidade,
identidade, replay/restart/concorrência, upgrade aditivo e recuperação de falhas
provados internamente. Histórico de falhas acima preserva suas causas/correções;
a CI final integral substitui qualquer pendência histórica de teste/merge #141.

Varredura: nenhum TODO/FIXME/HACK nos arquivos centrais novos/revisados;
sem autoridade paralela ou nova rota de cobrança. Dependências externas ausentes
continuam fail-closed e com ownership P6/P8. Worker contínuo P4, drift/ambiente
P5/P9/P11, providers/homologação P7/P10 e lançamento P12 permanecem pendentes.
Staging somente leitura, deployments inalterados: Portal/API/PostgreSQL1/1,
Worker0/1. Nenhum deploy, credencial, cobrança ou migration produtiva executado.

T05 DONE_CERTIFIED interno condicionado à integração/gates deste fechamento;
P3 COMMERCIAL_RUNTIME_COMPOSED_INTERNAL sob a mesma condição. Próxima tarefa:
NFV1-P04-T01 — Handler registry canônico, não iniciada nesta entrega.
Nova PR documental não recebe aprovação de merge por inferência.
PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.
