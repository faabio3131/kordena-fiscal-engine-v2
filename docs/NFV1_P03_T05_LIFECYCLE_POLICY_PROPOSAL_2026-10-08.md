# NFV1-P03-T05 — Lifecycle comercial: auditoria e política proposta

Data: 2026-10-08 (America/Sao_Paulo).
Status: POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION — T05-B01 RESOLVIDO.
Aprovação explícita do dono: “Aprovo”, em 2026-10-08 (America/Sao_Paulo).
Implementação/testes internos autorizados; merge/deploy/operação real não autorizados.
Produto: FM NFCORE V1. Repositório: faabio3131/kordena-fiscal-engine-v2.
Main: `c0e42fbb7ecfb1558c4aace664f971fb93eeeaba`.
Predecessor: T04 certificada internamente; PR #139/#140 MERGED;
CI main #701/run37867655781 e Governance #122/run37867655790 SUCCESS.

## Escopo e CURRENT → TARGET

T05 cobre sale, activation, renewal, late payment, pause, recovery, cancel,
refund e chargeback. Não inicia P4, não altera outro repositório e não executa
credencial, cobrança ou deploy real. Command permanece emissor autenticado de
fatos; NFCORE preserva purchase, subscription, tenant, OWNER e entitlement canônicos.

CURRENT: nove eventos existem, com proteção de identidade, ordem temporal,
terminalidade e replay. Fulfillment sincroniza status de assinatura durável,
mas não atualiza período na renovação. Command correlaciona assinatura à invoice
inicial; não há crédito de período deduplicado por invoice de renovação.
TARGET: lifecycle completo, períodos e uso governados, idempotência durável,
sem recriar identidade e sem transformar status ACTIVE em validade ilimitada.

## Evidências e limites

- `CommercialFulfillmentService._sync_subscription_status` altera status e
  last_event_id/at; period_start/end e usage permanecem inalterados.
- Probe sintético executou o serviço canônico com assinatura em memória:
  término inicial 2026-10-28T02:30:00Z; renewal, late, pause e recovery mantiveram
  esse término e usage documents=7. Estados observados: ACTIVE, GRACE,
  SUSPENDED, ACTIVE; cancel/refund/chargeback resultaram CANCELED na assinatura.
- `CommercialSubscription.accepts_new_commercial_operations` considera somente
  status, sem argumento de horário. Isso prova a lacuna do contrato interno;
  não prova que uma API fiscal implantada conceda acesso indevido.
- Activation.provision/retry não verifica validade comercial temporal antes
  de emitir reset; claimability verifica state, sem condição de billing.
  Impacto de ponta a ponta ainda requer testes, não declarado certificado.
- Dirigidos existentes:39 PASS/22 PostgreSQL SKIP/zero FAIL; DSN local ausente.
  Warning de depreciação TestClient existente. Nenhum teste enfraquecido.
- Staging somente leitura: Portal/API/PostgreSQL1/1,Worker0/1; drift histórico
  permanece P4/P5/P9/P11. Sem deploy. Probe não prova integração externa real.

## T05-B01 — política recomendada para aprovação como conjunto

1. **Renovação:** cada invoice paga concede no máximo um novo período à mesma
   assinatura. Início = maior entre término anterior e occurred_at autenticado;
   fim = início + cadence do snapshot canônico contratado. Preservar cálculo
   calendário existente (fim de mês/ano bissexto), sem substituir meses por30dias.
   Cadence atual publicada não reescreve contrato anterior. ONE_TIME não renova.
   Renovação atrasada não concede retroativamente operações no intervalo sem cobertura.
2. **Idempotência:** invoice namespaceada por produto/ambiente/assinatura é
   deduplicada duravelmente além do event_id. Mesma invoice com eventos novos,
   replay, concorrência ou restart não acrescenta tempo/usage/identidade novamente.
   Conflito de associação/conteúdo falha fechado. Reutilizar inbox/UOW e locks;
   migration aditiva governada se necessária, preservando dados legados.
3. **Atraso/carência:** atraso produz GRACE; carência configurável pela autoridade
   comercial de plataforma no snapshot contratado, default0dias, sem concessão
   gratuita inferida. Novas operações comerciais exigem horário dentro da cobertura
   paga ou da carência explicitamente configurada. Não criar cron/worker em T05;
   decisão temporal é reavaliada no ingresso comercial, independente de scheduler.
4. **Pausa/recuperação:** pausa bloqueia novas operações e não estende período;
   recuperação pode retornar ACTIVE dentro da cobertura válida, mas não cria
   pagamento nem novo período. Depois de expirar, somente renovação paga válida
   concede cobertura adicional. Não reprovisionar tenant/OWNER/subscription nem
   emitir repetidamente reset por todo evento de renovação/atraso/pausa/recuperação.
5. **Cancelamento/reembolso/chargeback:** mantêm terminalidade existente;
   bloqueiam novas operações comerciais e reativação automática por eventos.
   Preservar conta, organização, documentos fiscais, histórico e auditoria.
   Uma nova contratação, se futura, usa aquisição governada; não ressuscita contrato.
6. **Uso/quotas:** cada novo período pago inicia seus contadores periódicos em0,
   preservando snapshot/histórico do uso anterior. Pause/recovery, late e replay
   não zeram contadores nem concedem quota extra. Não criar preços/quotas/entitlements
   novos; reutilizar os contratados. Browser nunca define pagamento, período ou grants.

Configuração comercial pertence à plataforma existente, com versão/audit/permissão;
não ao browser/tenant arbitrário. A política acima foi integralmente aprovada; implementação e certificação pendentes.
Regras de quotas periódicas/carência deverão ser explícitas na configuração canônica,
sem constantes por cliente e sem alterar código/deploy para configurar um cliente.
Não alterar segurança fiscal, permissões de leitura histórica ou autoridade de emissão.

## Mapa de impacto e certificação após aprovação

- Billing/checkpoint: validade temporal, carência e período/uso governados.
- Fulfillment/activation/claim: transições e provisionamento/delivery compatíveis.
- Command ingress/store: identidade de invoice e crédito durável sem dupla concessão.
- Composição/API: mesmos serviços e rota, sem cobrança ou tenant authority paralelas.
- Persistence: fresh/upgrade/restart/replay; nenhuma migration produtiva autorizada.
- Testes: matriz dos nove eventos antes/depois da ativação; período expirado,
  carência0/configurada, pagamento antecipado/tardio, fim de mês/bissexto,
  snapshot de cadence, ONE_TIME, mesma invoice/novo event_id, concorrência,
  conflito/stale/same-time, falha antes/depois do commit, isolamento e segredo revogado.
- PostgreSQL real na CI, entitlements/usage e leitura fiscal preservada,
  Ruff/Mypy/secret/migration/plan, frontend/Playwright/containers/audits/SBOM/restore.

## Gate e continuidade

T05 IN_PROGRESS. T05-B01 resolvido pela aprovação específica do conjunto pelo dono.
AGENTS.md exige autorização específica antes de decisão de produto/preço e mudança
de segurança sensível; o executor interpreta período/carência/quota como decisão
comercial que concede ou bloqueia direitos. Não tratar autorização genérica para
executar T05 como seleção dessas regras ainda não apresentadas.

Próxima ação: implementar somente T05 conforme política aprovada e certificar todos
os gates antes de propor merge. T05 não concluída; P4 não iniciada.
PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.
