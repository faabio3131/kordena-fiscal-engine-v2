# V2-16 — Integração dos Produtos FM — Registro de Execução

Data: 2026-09-13

## Estado de entrada e governança

A V2-15 permanece preservada no checkpoint certificado `33e34866bc6e8c736c585c45101ce214816e0594`, com a PR #16 OPEN/DRAFT e não mergeada. Esta execução não altera aquele checkpoint, não realiza merge/deploy/cutover e não usa segredos reais.

A primeira janela da V2-16 executou B1-B3. A segunda autorização executou sequencialmente B4-B6, com correção de falhas internas até verde e registro explícito de bloqueios reais sem falsificação de estado.

## V2-16.1 — Contrato de integração

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**.

A fronteira `kordena_fiscal.integrations` deriva produto/use case exclusivamente dos Product Contract Packs certificados e liga-os ao contrato público FM Fiscal Bridge v1 vigente. Readiness permanece obrigatório antes de mutações e nenhuma resolução de pack concede homologação ou produção.

Gate certificado: SHA `c23d49997a4344363720436374a8d9476e665262`, run `34779681157`: instalação, Ruff, mypy e pytest verdes.

## V2-16.2 — Integração Kordena

Status: **BLOQUEADA POR PRÉ-REQUISITO REAL DO PLANO MESTRE**.

A V1 Web Premium ainda não está liberada para FISC-20. A PR Kordena #118 permanece OPEN/DRAFT; nenhum acoplamento runtime prematuro foi introduzido e nenhum verde artificial foi declarado.

## V2-16.3 — Integração Iron Fit

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**.

A integração nasce do fato autoritativo `FinancialService.payCharge` após quitação idempotente da `Charge`. O handoff usa `fm.iron`, permanece `PENDING_CAPABILITY`, exige binding/readiness e não duplica provider, município ou regra tributária no produto.

Branch Iron: `feat/fisc-v2-16-iron-integration`. PR #48 OPEN/DRAFT e não mergeada. Gate final SHA `2be8321eeb066f0296ba812faab0a098c32f0632`, run `34780329013`: npm ci, dependency audit, Prisma generate, lint/typecheck, build e smoke regression tests verdes.

## V2-16.4 — Integração Vendedor IA

Status: **BLOQUEADO PARCIAL — HANDOFF INTERNO CONCLUÍDO/CERTIFICADO; CLASSIFICAÇÃO FISCAL/DESTINATÁRIO PENDENTES NO PRODUTO**.

### Autoridade comercial encontrada

No Vendedor IA, a autoridade real de liquidação é `Payment.status = CONFIRMED`, alcançada server-side pelo refresh do provider ou por webhook validado/normalizado. A venda usa `Quote` em estado `ACCEPTED` e snapshot de itens como contrato comercial fonte.

### Implementação

Branch: `feat/fisc-v2-16-vendedor-integration`. PR Vendedor IA #1: OPEN/DRAFT e não mergeada.

Foi criado handoff durável/idempotente:

- host `fm.vendedor-ia`;
- pack `sales`;
- operação `sale`;
- candidatos permitidos `nfce-sale` / `nfe-sale`, sem seleção heurística pelo SaaS;
- chave `vendedor-ia:payment:<paymentId>:sale:v1`;
- venda de produto liquidada → `PENDING_FISCAL_CLASSIFICATION`;
- quote com item SERVICE → `BLOCKED_UNSUPPORTED_SALE_CONTENT`;
- recipient fiscal data, binding e readiness obrigatórios antes de emissão.

### Bloqueio real

O modelo atual de Customer não possui CPF/CNPJ nem endereço fiscal e o domínio não contém fatos suficientes para escolher com segurança NF-e versus NFC-e. Isso impede emissão efetiva, mas não invalida o handoff liquidado já certificado.

### Gate

HEAD `b4b7fb05236c481d5626de5386864ae6f5227418`, run `34783831679`, job `103795573887`: install PASS, build PASS, typecheck PASS, **34 arquivos de teste / 157 testes PASS**, runtime security boundaries PASS e production Docker smoke PASS.

A branch temporária `fisc-v2-16-vendedor-ci-gate` foi neutralizada de volta ao baseline `09a3f3a9cad353e4537418d9aacf1b6b43f3200d` após o gate.

## V2-16.5 — Integração CampaIA

Status: **BLOQUEADO PARCIAL — ADAPTER FISCAL INTERNO CONCLUÍDO/CERTIFICADO; AUTORIDADE REAL DE FATURAMENTO/PAGAMENTO PRÓPRIO AINDA INEXISTENTE**.

### Achado arquitetural

O runtime atual da CampaIA modela campanhas, orçamento/gasto de mídia, conexões com plataformas, aprovações, autonomia, reconciliação e outbox. Não existe ainda domínio autoritativo de assinatura, cobrança ou pagamento próprio da CampaIA. Verba de campanha e media spend não são receita CampaIA e não foram reutilizados como autoridade fiscal.

### Implementação

Branch: `feat/fisc-v2-16-campaia-integration`. PR CampaIA #1: OPEN/DRAFT e não mergeada.

Foi criada uma seam fail-closed `SettledOwnBillingFact` que somente poderá ser alimentada por um futuro fato real de faturamento próprio liquidado:

- `service-billing` → `service` + `nfse`;
- `saas-billing` → `saas_billing` + `nfse`;
- idempotência `campaia:billing:<billingId>:nfse:v1`;
- estado `PENDING_CAPABILITY`;
- binding/readiness obrigatórios;
- nenhum provider, município, ISS, retenção, alíquota ou production approval no SaaS.

### Gate

HEAD `bdebbc3558ff8b07c1a38e0cb728be0dc3635c4b`, run `34784021431`, job `103796103296`: backend dependencies PASS; **267 core tests PASS**; **80 API tests PASS**; total **347 PASS**; contract dependencies PASS; AsyncAPI PASS com 24 eventos verificados end-to-end.

## V2-16.6 — Adapter Contract Pack / novos produtos FM

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**.

A avaliação concluiu que a fundação existente já cobria descriptors, registry, host namespace, use cases, operation/document kinds e vertical capabilities. Para evitar overengineering, foram adicionadas somente as lacunas reais:

1. `ProductOnboardingDeclaration` + `certify_product_onboarding(...)` para exigir identidade, autoridade comercial explícita e estratégia de idempotência sem conceder readiness;
2. `ProductMutationPreflight` + `validate_product_mutation_preflight(...)` para fail-closed antes de mutação quando pack/host/use case/operação/documento/ação/escopo/idempotência/binding/capability/readiness estiverem ausentes ou incompatíveis;
3. suíte sintética `tests/test_v2_16_product_pack_onboarding.py`, sem registrar produto fictício no catálogo real;
4. documentação `docs/V2_16_ADAPTER_PACK_ONBOARDING.md`.

A certificação estrutural produz explicitamente `readiness_granted = False`. Binding, capability e readiness continuam vindo de suas autoridades próprias; o helper apenas verifica que já foram resolvidos antes da mutação.

O primeiro gate B6 encontrou cinco violações Ruff e foi mantido vermelho. As violações foram corrigidas no código/testes sem remover cobertura nem relaxar assertions. Um run intermediário ainda avaliou um commit anterior; o gate integral corrigido no SHA `878738c172ab31e3f81618a95986370b17d0e602`, run `34784375685`, job `103797066379`, concluiu: Install PASS, Ruff PASS, Mypy PASS em **114 source files** e Pytest **639 PASS em 16.83s**.

## Decisão formal após B1-B6

**V2-16 — BLOQUEADA PARCIAL — B1, B3 E B6 INTERNAMENTE CONCLUÍDOS/CERTIFICADOS; B2 KORDENA BLOQUEADO POR PRÉ-REQUISITO WEB PREMIUM/FISC-20; B4 VENDEDOR IA E B5 CAMPAIA INTERNAMENTE CERTIFICADOS, MAS BLOQUEADOS PARCIALMENTE POR LACUNAS REAIS DE DOMÍNIO DOS PRODUTOS.**

A segunda autorização B4-B6 está concluída. Nenhum bloqueio foi convertido artificialmente em verde. A arquitetura para futuros produtos está certificada, mas V2-16 não pode ser declarada integralmente concluída enquanto os bloqueios obrigatórios acima persistirem.

## Guardrails preservados

- SEM MERGE da PR #16, PR #17, Iron #48, Vendedor IA #1 ou CampaIA #1.
- SEM Ready/auto-merge.
- SEM DEPLOY.
- SEM PRODUÇÃO REAL.
- SEM CUTOVER.
- SEM SEGREDO REAL NO REPOSITÓRIO.
- SEM HOMOLOGAÇÃO EXTERNA INVENTADA.
- SEM PROMOÇÃO INDEVIDA DE `PRODUCTION_APPROVED`.
- V2-17 NÃO INICIADA.
