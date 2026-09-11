# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-05 — Auth S2S + Workload Identity + Webhook Security**  
Próxima fase liberada: **V2-06 — Capability & Readiness API**

> O tracker detalhado anterior ao fechamento do V2-05 foi preservado byte-for-byte em `docs/history/EXECUTION_TRACKER_V2_PRE_V2_05.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`.

Nenhum bloco é `CONCLUÍDO` sem branch, SHA, PR Draft, CI, testes/gates, auditoria de diff e riscos residuais documentados. Nenhum merge, deploy, promoção ou cutover é automático.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-00 | Clone técnico + equivalência | **CONCLUÍDO** | PR #1 Draft; baseline `b336def47ad4f5188307102203f4e04b98406014`; `src/` e `tests/` equivalentes; gate `9da776e353b31d03a8453a83c6e61a736e6ed00b`; run `34633874565` SUCCESS; Pytest 215 PASS |
| V2-01 | Identidade FM + neutralização de branding | **CONCLUÍDO** | PR #2 Draft; gate `ac6ad42eeacca2a84675e7e57e04b18414cadf36`; run `34635131000` SUCCESS; distribuição `fm-fiscal-core`; Pytest 215 PASS |
| V2-02 | Host namespace + fiscal account binding | **CONCLUÍDO** | PR #3 Draft; gate `4fa8a2a8c74db65622099cd7dca43d2e8d19aea3`; run `34637445978` SUCCESS; partição host/account/unit/environment; Pytest 239 PASS |
| V2-03 | Fiscal Operation Contract genérico | **CONCLUÍDO** | PR #4 Draft; gate `598a2ec83aecd27a5427f3e1e401532e8be2696a`; run `34645939363` SUCCESS; 47 source files; Pytest 262 PASS |
| V2-04 | FM Fiscal Bridge — OpenAPI/JSON Schema/AsyncAPI | **CONCLUÍDO** | PR #5 Draft; gate `86689b3d3d7d47740b56bcc22594aa8c8e0b08c7`; run `34655024269` SUCCESS; contratos v1 language-neutral; 47 source files; Pytest 269 PASS |
| V2-05 | Auth S2S + workload identity + webhook security | **CONCLUÍDO** | PR #6 Draft; gate `196928d1b0cfe896df0c4741839ce72258f8f4d4`; run `34656535435` SUCCESS; OpenAPI/AsyncAPI v1.1; 48 source files; Pytest 290 PASS |
| V2-06 | Capability & Readiness API | PENDENTE | **LIBERADO** após V2-05 |
| V2-07 | Application service + persistência durável | PENDENTE | depende V2-05; integração com V2-06 conforme contrato |
| V2-08 | Events/Webhooks/Inbox/Outbox | PENDENTE | depende V2-07 |
| V2-09 | Modularização de verticais | PENDENTE | após contratos core estabilizados |
| V2-10 | Contract Packs Kordena/Iron/Vendedor/CampaIA | PENDENTE | depende V2-03..V2-09 |
| V2-11 | Control Plane independente | PENDENTE | depende core operacional |
| V2-12 | Gateway/Signer/Vault production adapters | PENDENTE | depende V2-11 |
| V2-13 | Observabilidade + Compliance Operations | PENDENTE | depende V2-07/V2-12 |
| V2-14 | Hardening sistêmico | PENDENTE | regressão/carga/falhas/segurança |
| V2-15 | Homologação + pilotos controlados | PENDENTE | depende V2-14 |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | Kordena aguarda V1 Web Premium; demais aguardam V2 universal certificado |
| V2-17 | Convergência/cutover + arquivamento original | PENDENTE | somente após equivalência e integrações certificadas |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## Checkpoints executivos

### V2-00 — Equivalência

- baseline original congelado em `b336def47ad4f5188307102203f4e04b98406014`;
- código e suíte de regressão transportados para o V2;
- gate final: Ruff PASS, Mypy PASS, **215 testes PASS**;
- nenhuma refatoração multiproduto ocorreu antes da equivalência.

### V2-01 — Identidade FM Fiscal

- **FM Fiscal** oficializado como produto independente da **FM Tecnologia**;
- Kordena reclassificado como consumidor/adapter;
- distribuição Python renomeada para `fm-fiscal-core`;
- namespace legado `kordena_fiscal` preservado temporariamente por compatibilidade;
- identidade visual e política de naming registradas e certificadas.

### V2-02 — Identidade multiproduto

- `HostNamespace`, `HostScope`, `FiscalAccountId`, `FiscalUnitId` e `FiscalAccountBinding` introduzidos;
- `ExecutionScope.identity_partition_key` passou a incluir host + conta fiscal + unidade fiscal + ambiente;
- sequência, idempotência, archive, outbox, reconciliação, audit e composição documental passaram a respeitar partição host-aware;
- spoofing/cross-host falha fechado;
- gate final: **239 testes PASS**.

### V2-03 — Operação fiscal neutra

- `FiscalOperationSnapshot`, totals, payments e kinds universais introduzidos;
- venda, mensalidade, assinatura, serviço, cobrança recorrente e SaaS billing suportados;
- `reconcile_operation(...)` tornou-se rota canônica;
- `HostSettlementSnapshot` mantido somente como compatibilidade V1;
- gate final: **262 testes PASS**.

### V2-04 — Bridge language-neutral

- `contracts/v1/` criou OpenAPI 3.1, JSON Schema 2020-12 e AsyncAPI 3.0;
- emissão, consulta, cancelamento, inutilização, capabilities, reconciliação e archive reference possuem contratos independentes de linguagem/banco;
- `CanonicalError` provider-neutral e correlation/causation/idempotency formalizados;
- nenhuma alteração de runtime `src/` nesta fase;
- gate final: **269 testes PASS**.

### V2-05 — S2S, Workload Identity e Webhook Security

- branch `v2/s2s-workload-webhook-security`;
- PR #6 Draft sobre V2-04;
- `CallerIdentity` fixa `host_namespace`, capabilities e grants de tenant/unidade;
- `WorkloadCredentialRecord` usa segredo opaco com hash, validade, revogação e rotação;
- `S2SAuthorizer` valida caller → host → capability → grant → binding exato antes de criar `ExecutionScope`;
- cross-host, cross-tenant e cross-unit falham fechado;
- rate limiting de referência por caller e audit trail allowed/denied implementados;
- `WebhookSecurity` usa HMAC-SHA256, `key_id`, janela antirreplay, tolerância de clock e comparação constant-time;
- rotação de chave de webhook suportada por overlap controlado;
- Bridge elevado para contrato **v1.1.0**: OpenAPI exige workload credential id + bearer secret; AsyncAPI exige `X-FM-Webhook-Signature`;
- gate definitivo: `196928d1b0cfe896df0c4741839ce72258f8f4d4`;
- Actions run `34656535435`: **SUCCESS**;
- Install PASS; Ruff PASS; Mypy strict PASS — **48 source files sem issues**; Pytest **290 PASS em 0.82s**;
- diff auditado contra V2-04: somente segurança S2S/webhook, contratos, testes, docs e CI temporário;
- gates anteriores desta fase falharam somente em lint e foram corrigidos sem mudança semântica;
- CI retornado a `workflow_dispatch` após certificação;
- nenhum merge ou deploy executado.

## Riscos residuais governados após V2-05

- V2-06 deve transformar capability/readiness em autoridade consultável, versionada e com provenance normativa;
- persistência/coordenação distribuída de credenciais, rate limit, bindings e auditoria pertence ao runtime/control plane posterior;
- delivery durável, retries, DLQ e estado de webhooks pertencem ao V2-08;
- secret manager/vault e identidade de produção serão adapters governados, não regras incorporadas ao Core.

## Próxima decisão

**V2-05 CONCLUÍDO E CERTIFICADO. V2-06 — Capability & Readiness API está LIBERADO e é o próximo bloco de construção.**
