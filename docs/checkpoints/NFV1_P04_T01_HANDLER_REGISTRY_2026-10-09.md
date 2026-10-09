# NFV1-P04-T01 — Handler registry canônico

Data: 2026-10-09 (America/Sao_Paulo). Estado: IN_PROGRESS.
Autorização: dono instruiu “Prossiga” após fechamento P3 integrado/certificado.
Base main: `4c3838f0c35e728f36f9c15ac1c3f62c42cd35d2`, PR #142 MERGED;
CI #711/run37877105753 e Governance #132/run37877105824 SUCCESS.
Escopo: somente T01; sem deploy/migration produtiva/credencial/transação real.

## Inventário CURRENT e composição

| Componente existente | Papel / decisão T01 |
|---|---|
| SignedWebhookOutboxHandler | Único handler concreto que implementa dispatch(FiscalOutboxEntry); registrado como deliver_webhook |
| DurableWebhookDestinationResolver | URL obtida da configuração durável pelo escopo tenant/unit/environment da entrada e destination_id explícito |
| DurableWebhookEgressPolicy / PinnedWebhookTransport | Aprovação/versionamento/expiração/revogação e egress aprovados P02-T03, preservados |
| RoutedOutboxHandler | Router existente; operação desconhecida continua poison/permanent failure, nunca execução fiscal implícita |
| DurableFiscalOutboxWorker | Mesma outbox, UOW, leases, retry/backoff, dead-letter e delivery audit; nenhuma fila nova |
| BackgroundWorkerRuntime | Loop existente; certificação expandida de recuperação/observabilidade/container pertence T02/T03/T04 |
| Provider/fiscal operation handlers | Contrato HTTP/fiscal diferente; não são FiscalOutboxHandler e não recebem adapter inventado |
| Commercial receiver/inbox/activation | Caminho comercial canônico existente; não criar replay/provisionamento paralelo no Worker |

TARGET: build_canonical_worker_handlers retorna mapa imutável com a única operação
concreta existente. WorkerWebhookDependencies exige WebhookSecurity existente e
referência destination_id válida; repr exclui security. Sem URL ou chave raw, aliases
arbitrários, import dinâmico ou configuração de tenant dentro do registry.

worker_main.run usa registry canônico quando dependências explícitas são injetadas.
Factory legada explícita permanece compatível; fornecer as duas fontes é rejeitado
antes de invocar factory/poll. ONESHOT permanece probe de banco/migrations e nunca
compõe handlers/dispatch. Ausência de dependências bloqueia antes de consumir jobs.

Destino e aprovação são resolvidos/revalidados no dispatch, sem cache de autorização;
revogação bloqueia a tentativa seguinte. A assinatura usa a mesma boundary existente.
Nenhuma regra nova de segurança/produto, nenhum endpoint de configuração novo.

## Verificação / evidência

16 casos novos: mapa restrito/imutável; dependência ausente/inválida; referência
inválida; repr; unknown operation/missing destination sobre outbox real SQLite;
isolamento tenant; aprovação durável pendente/aprovada, assinatura exata e revogação;
entrypoint PostgreSQL canônico; rejeição de composição ambígua; ONESHOT sem registry.
Transporte/DNS no teste são sintéticos, sem socket externo; não provam egress real.
Três novos casos de entrypoint exigem PostgreSQL real na CI.

Dirigidos:29 PASS/5 PostgreSQL SKIP/zero FAIL local (DSN ausente). Incluem matriz
existente de runtime e delivery. Nenhum teste existente alterado, apagado ou enfraquecido.
Ruff/Mypy strict193/plan59/migration16/secret scan PASS. Suíte local completa e CI
integral do HEAD em validação; resultados finais/PR/SHA serão registrados na PR.
Suíte local completa:1355 PASS/232 SKIP/zero FAIL,134.97s; warning TestClient
existente. DSN local ausente; nenhuma integração PostgreSQL é certificada localmente.

## Limites e continuidade

Worker padrão continua fail-closed enquanto a boundary de assinatura real não
for fornecida; não fabricar segredo nem promover worker idling como operacional.
Secret backend concreto permanece P6; configuração/governança externa existente
não é certificada pelo objeto de dependências. Referência de destino e assinatura
são configuráveis na composição, sem constantes por cliente ou alteração de adapter.

Staging read-only confirmado em início: deployments históricos inalterados;
API/Portal/PostgreSQL1/1, Worker0/1. Drift P5/P9/P11. T02/T03/T04 não iniciadas.
Não certifica worker contínuo implantado, integração externa, homologação ou produção.
T01 não concluída antes de PR/CI/merge/main/evidência. Merge requer autorização;
deploy/produção não autorizados. PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.
