# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-03 — Fiscal Operation Contract genérico**  
Próxima fase liberada: **V2-04 — FM Fiscal Bridge — OpenAPI/JSON Schema/AsyncAPI**

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`.

Nenhum bloco pode ser marcado `CONCLUÍDO` sem branch, SHA, PR, CI, testes/gates, revisão do diff e riscos residuais documentados.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-00 | Clone técnico + equivalência | **CONCLUÍDO** | PR #1 Draft; baseline `b336def47ad4f5188307102203f4e04b98406014`; `src/` tree `bd756be69685cecad0907816e93fca8616482553`; `tests/` tree `af98a932eca692a1eb2307879de7afbd01d1f003`; gate SHA `9da776e353b31d03a8453a83c6e61a736e6ed00b`; Actions run `34633874565` SUCCESS; Ruff PASS; Mypy PASS; Pytest 215 PASS |
| V2-01 | Identidade FM + neutralização de branding | **CONCLUÍDO** | PR #2 Draft; gate SHA `ac6ad42eeacca2a84675e7e57e04b18414cadf36`; Actions run `34635131000` SUCCESS; distribuição `fm-fiscal-core`; Ruff PASS; Mypy PASS; Pytest 215 PASS |
| V2-02 | Host namespace + fiscal account binding | **CONCLUÍDO** | PR #3 Draft; gate definitivo SHA `4fa8a2a8c74db65622099cd7dca43d2e8d19aea3`; Actions run `34637445978` SUCCESS; propagação sequence/idempotency/archive/outbox/reconciliation/audit/document composition; Ruff PASS; Mypy PASS; Pytest 239 PASS |
| V2-03 | Fiscal Operation Contract genérico | **CONCLUÍDO** | PR #4 Draft; gate SHA `598a2ec83aecd27a5427f3e1e401532e8be2696a`; Actions run `34645939363` SUCCESS; Ruff PASS; Mypy strict PASS — 47 source files; Pytest 262 PASS |
| V2-04 | FM Fiscal Bridge — OpenAPI/JSON Schema/AsyncAPI | PENDENTE | liberado após V2-03 |
| V2-05 | Auth S2S + workload identity + webhook security | PENDENTE | depende V2-04 |
| V2-06 | Capability & Readiness API | PENDENTE | depende V2-04/V2-05 |
| V2-07 | Application service + persistência durável | PENDENTE | depende V2-05 |
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

## Checkpoint V2-00.1 — Bootstrap — 2026-09-11

- Repositório privado V2 confirmado e acessível pelo GitHub App.
- `main` inicializada e README atualizado com a estratégia de fork transitório.
- Branch de execução: `v2/foundation-equivalence-and-master-plan`.
- Plano Mestre criado em `docs/PLANO_MESTRE_EXECUCAO_V2.md`.
- Baseline de origem fixado em `b336def47ad4f5188307102203f4e04b98406014`.
- Manifest de equivalência criado em `docs/BASELINE_EQUIVALENCE_MANIFEST.md`.

## Checkpoint V2-00.2 — Execução iniciada — 2026-09-11

- PR #1 criada em Draft: `V2-00 — Foundation, Master Plan and Baseline Equivalence`.
- `.gitignore` e `pyproject.toml` do baseline importados sem alteração semântica.
- CI criada com os mesmos gates Ruff + Mypy + Pytest; durante a cópia massiva ficou temporariamente em `workflow_dispatch` para evitar consumo desnecessário de minutos.
- Primeiro slice técnico importado do SHA certificado: `src/kordena_fiscal/__init__.py` e todo o pacote `src/kordena_fiscal/domain/`.
- Nenhuma refatoração multiproduto foi iniciada; os arquivos importados preservaram o comportamento original.

## Checkpoint V2-00.3 — Equivalência certificada — 2026-09-11

- Árvore completa `src/` transportada sem mudança semântica.
- Suíte completa de 24 arquivos de teste transportada byte-for-byte.
- Tree SHA `src/` no original e no V2: `bd756be69685cecad0907816e93fca8616482553`.
- Tree SHA `tests/` no original e no V2: `af98a932eca692a1eb2307879de7afbd01d1f003`.
- Commit submetido ao gate: `9da776e353b31d03a8453a83c6e61a736e6ed00b`.
- GitHub Actions run `34633874565`: **SUCCESS**.
- Install: PASS.
- Ruff: PASS.
- Mypy: PASS — 45 source files sem issues.
- Pytest: PASS — **215 passed**.
- Diff auditado: diferenças fora da árvore fiscal são apenas governança/documentação/CI do V2 (`INFRA-ONLY`).
- Risco residual de equivalência: nenhum desvio conhecido em relação ao baseline certificado.
- CI retornado a `workflow_dispatch` após o gate verde para controlar consumo de minutos.

## Checkpoint V2-01.1 — Identidade FM Fiscal iniciada — 2026-09-11

- Branch: `v2/fm-fiscal-identity-and-brand`.
- Produto oficializado como **FM Fiscal**, da **FM Tecnologia**.
- Kordena reclassificado formalmente como produto consumidor/adapter, não marca-mãe.
- Distribuição Python renomeada de `kordena-fiscal-engine` para `fm-fiscal-core`.
- Namespace `kordena_fiscal` preservado temporariamente por compatibilidade; renomeação em massa proibida nesta fase.
- Brand System registrado em `docs/brand/FM_FISCAL_BRAND_SYSTEM.md`.
- Design tokens registrados em `docs/brand/fm-fiscal.tokens.json`.
- Política de identidade/namespace registrada em `docs/V2_01_IDENTITY_NAMESPACE_POLICY.md`.
- Nenhuma regra fiscal, cálculo, state machine, idempotência, emissão, gateway ou contrato fiscal existente foi alterado neste checkpoint.

## Checkpoint V2-01.2 — Identidade certificada — 2026-09-11

- PR #2 criada em Draft e empilhada sobre V2-00.
- Gate executado no SHA `ac6ad42eeacca2a84675e7e57e04b18414cadf36`.
- GitHub Actions run `34635131000`: **SUCCESS**.
- Instalação da distribuição `fm-fiscal-core==0.1.0.dev0`: PASS.
- Ruff: PASS.
- Mypy strict: PASS — 45 source files sem issues.
- Pytest: PASS — **215 passed em 0.80s**.
- Auditoria do diff contra `820e58001d17d07537f2a1c740a69e092f3cef3c`: mudanças restritas a README, `pyproject.toml`, documentação de identidade/brand/tokens/tracker e CI temporário; nenhuma árvore fiscal de `src/` foi modificada.
- CI retornado a `workflow_dispatch` após o gate verde para controlar consumo de minutos.
- Risco residual: namespace Python legado `kordena_fiscal` permanece intencionalmente por compatibilidade e será migrado somente com estratégia explícita e gate próprio.

## Checkpoint V2-02.1 — Binding multiproduto implementado — 2026-09-11

- Branch: `v2/host-namespace-fiscal-account-binding`.
- Documento de invariantes: `docs/V2_02_HOST_NAMESPACE_AND_BINDING.md`.
- `HostNamespace` introduz namespace estável por aplicação consumidora.
- `HostScope` qualifica `tenant_id` e `unit_id` externos pelo namespace do host.
- `FiscalAccountId` e `FiscalUnitId` introduzem identidades fiscais internas opacas.
- `FiscalAccountBinding` mapeia escopo externo para escopo fiscal interno.
- `FiscalBindingRegistry` define resolução exata, sem fallback cross-host/cross-unit.
- Resolução para `ExecutionScope` usa IDs fiscais internos, impedindo que IDs externos sejam tratados como autoridade fiscal.
- Testes novos cobrem normalização, validação, colisão entre produtos, resolução exata, unidade incorreta e duplicidade de bindings.
- Autenticação, persistência e provisioning permanecem fora do V2-02 conforme Plano Mestre.

## Checkpoint V2-02.2 — Gate inicial de binding — 2026-09-11

- PR #3 criada em Draft e empilhada sobre V2-01.
- Gate inicial executado no SHA `dbb77082be4daba149ba4bb72585bfa77b76a4da`.
- GitHub Actions run `34635737969`: **SUCCESS**.
- Ruff e Mypy verdes; Pytest **228 passed**.
- Após reconciliação com o Plano Mestre, o escopo foi ampliado dentro da mesma V2-02 para completar a propagação obrigatória de host namespace em todos os subsistemas de identidade.

## Checkpoint V2-02.3 — Partição host-aware propagada — 2026-09-11

- `ExecutionScope` passou a carregar `host_namespace` e expor `identity_partition_key = host + fiscal account + fiscal unit + environment`, mantendo o `partition_key` legado para compatibilidade.
- `FiscalAccountBinding` propaga o namespace resolvido ao escopo interno.
- Sequence Manager passou a separar streams de numeração por host.
- Idempotency passou a incluir host na identidade de emissão quando presente.
- Archive e manifest de auditoria passaram a particionar por host; consulta por documento não cruza namespaces.
- Outbox passou a gerar identidade determinística por host.
- Reconciliation passou a comparar a partição universal e falhar fechado em tentativa cross-host; fingerprint também inclui host.
- Canonical serialization registra `host_namespace` para scopes V2-bound.
- `FiscalDomainEvent` carrega o `ExecutionScope`, portanto a metadata de evento/auditoria preserva o host.
- Gate intermediário SHA `5e9cd9fec2f98f85503f951c3accaf9816ea8f1b`; run `34636812046` SUCCESS; Pytest **237 passed**.

## Checkpoint V2-02.4 — Hardening cross-host e certificação definitiva — 2026-09-11

- `CanonicalFiscalDocument` agora valida issuer e product profile pela `identity_partition_key`, não apenas tenant/unit/environment legados.
- Composição cross-host falha fechado mesmo quando conta/unidade internas têm os mesmos IDs.
- Testes adicionais cobrem spoofing cross-host de issuer/product e presença do host no snapshot canônico.
- Gate definitivo executado no SHA `4fa8a2a8c74db65622099cd7dca43d2e8d19aea3`.
- GitHub Actions run `34637445978`: **SUCCESS**.
- Install: PASS — `fm-fiscal-core==0.1.0.dev0`.
- Ruff: PASS.
- Mypy strict: PASS — **46 source files sem issues**.
- Pytest: PASS — **239 passed em 0.48s**.
- Diff auditado contra a base V2-01 `00f8136fa2a2b2ad38e4752a8b55bdc542f239ae`: alterações limitadas ao contrato de identidade/binding, propagação da partição, hardening cross-host, testes e documentação/CI.
- Compatibilidade preservada: scopes legados sem host mantêm o material determinístico V1; novas fronteiras host-facing devem obrigatoriamente resolver binding antes de ingressar no Core.
- CI retornado a `workflow_dispatch` após o gate verde.
- Riscos residuais: autenticação S2S será V2-05; persistência durável de bindings será V2-07/V2-11; neutralização semântica de `sale/HostSettlement` pertence ao V2-03.

## Checkpoint V2-03.1 — Contrato universal e reconciliação neutra — 2026-09-11

- Branch: `v2/generic-fiscal-operation-contract`.
- PR #4 criada em Draft e empilhada sobre V2-02.
- `FiscalOperationKind` introduz famílias canônicas: sale, membership, subscription, service, recurring_charge, saas_billing e other.
- `FiscalOperationPayment`, `FiscalOperationTotals` e `FiscalOperationSnapshot` introduzem o contrato econômico/fiscal host-neutral.
- `FiscalOperationSnapshot` separa `occurred_at` de `settled_at` e valida a identidade econômica `net = gross - discount + surcharge`.
- `FiscalReconciliationEngine.reconcile_operation(...)` tornou-se a rota canônica neutra de reconciliação.
- `HostSettlementSnapshot` permanece como camada de compatibilidade V1 e adapta a venda histórica para `FiscalOperationSnapshot`.
- Novos códigos de divergência são operation-neutral; o wrapper legado traduz de volta os códigos históricos para preservar compatibilidade.
- `operation_kind`, totals, pagamentos, timestamps, reference e host namespace participam do fingerprint neutro.
- Cross-host/cross-account/cross-unit/cross-environment continua fail-closed.

## Checkpoint V2-03.2 — Certificação — 2026-09-11

- Base V2-02: `637b326cab5c179875186201756bd3561bdf008d`.
- Primeiro gate run `34645774207` falhou somente no Ruff por uma linha `E501`; Mypy/Pytest nem foram executados nesse run.
- Correção de formatação aplicada sem mudança semântica.
- Gate definitivo executado no SHA `598a2ec83aecd27a5427f3e1e401532e8be2696a`.
- GitHub Actions run `34645939363`: **SUCCESS**.
- Install: PASS — `fm-fiscal-core==0.1.0.dev0`.
- Ruff: PASS.
- Mypy strict: PASS — **47 source files sem issues**.
- Pytest: PASS — **262 passed em 0.77s**.
- Testes cobrem venda, mensalidade, assinatura, serviço, cobrança recorrente, faturamento SaaS, invariantes econômicos, timestamps, liquidação, cross-host e compatibilidade V1.
- Diff auditado contra V2-02: mudanças limitadas ao contrato genérico, reconciliação, testes e documentação; nenhuma regra tributária, cálculo, emissão, numeração, assinatura ou provider contract foi modificada.
- CI retornado a `workflow_dispatch` após o gate verde para controlar consumo de minutos.
- Riscos residuais governados: contratos language-neutral pertencem ao V2-04; autenticação caller/workload ao V2-05; persistência durável ao V2-07; adapters concretos por produto ao V2-10/V2-16.

Decisão: **V2-03 CONCLUÍDO E CERTIFICADO. V2-04 está LIBERADO, mas permanece PENDENTE até abertura formal de sua branch/PR.**
