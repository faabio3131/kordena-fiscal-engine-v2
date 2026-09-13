# V2-16 — Integração dos Produtos FM — Registro de Execução

Data: 2026-09-13

## Estado de entrada e governança

A V2-15 permanece preservada no checkpoint certificado `33e34866bc6e8c736c585c45101ce214816e0594`, PR #16 OPEN/DRAFT e não mergeada. A V2-16 não altera aquele checkpoint, não realiza merge/deploy/cutover e não usa segredos reais.

A execução ocorreu em janelas governadas: B1-B3, depois B4-B6, e por fim B7 para reconciliar a Multi-Product Cross-Certification prevista no Plano Mestre e fechar todo o trabalho interno legitimamente executável da fase.

## V2-16.1 — Contrato de integração

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**.

A fronteira `kordena_fiscal.integrations` deriva produto/use case exclusivamente dos Product Contract Packs certificados e liga-os ao contrato público FM Fiscal Bridge v1 vigente. Readiness permanece obrigatório antes de mutações e nenhuma resolução de pack concede homologação ou produção.

Gate certificado: SHA `c23d49997a4344363720436374a8d9476e665262`, run `34779681157`: Install/Ruff/Mypy/Pytest PASS.

## V2-16.2 — Integração Kordena

Status: **BLOQUEADA POR PRÉ-REQUISITO REAL DO PLANO MESTRE**.

A V1 Web Premium/FISC-20 ainda não está liberada. A PR Kordena #118 permanece OPEN/DRAFT e funcionalmente PARCIAL. Nenhum acoplamento runtime prematuro foi introduzido e nenhum verde artificial foi declarado.

## V2-16.3 — Integração Iron Fit

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**.

A integração nasce do fato autoritativo `FinancialService.payCharge` após quitação idempotente da `Charge`. O handoff `fm.iron` permanece `PENDING_CAPABILITY`, exige binding/readiness e não duplica provider, município ou regra tributária no produto.

Branch `feat/fisc-v2-16-iron-integration`, PR #48 OPEN/DRAFT. Gate final SHA `2be8321eeb066f0296ba812faab0a098c32f0632`, run `34780329013`: npm ci, dependency audit, Prisma generate, lint/typecheck, build e smoke regression PASS.

## V2-16.4 — Integração Vendedor IA

Status: **BLOQUEADO PARCIAL — HANDOFF INTERNO CONCLUÍDO/CERTIFICADO; CLASSIFICAÇÃO FISCAL/DESTINATÁRIO PENDENTES NO PRODUTO**.

Autoridade comercial: `Payment.status = CONFIRMED`, com `Quote` ACCEPTED + snapshot de itens. O handoff usa `fm.vendedor-ia`, pack `sales`, operação `sale`, chave `vendedor-ia:payment:<paymentId>:sale:v1` e não escolhe heurísticamente NF-e/NFC-e. Venda de produto liquidada fica `PENDING_FISCAL_CLASSIFICATION`; conteúdo SERVICE fica `BLOCKED_UNSUPPORTED_SALE_CONTENT`.

Bloqueio real: Customer atual não possui CPF/CNPJ/endereço fiscal e o domínio não contém fatos suficientes para selecionar NF-e versus NFC-e com segurança.

Branch `feat/fisc-v2-16-vendedor-integration`, PR #1 OPEN/DRAFT. HEAD `b4b7fb05236c481d5626de5386864ae6f5227418`, run `34783831679`, job `103795573887`: build/typecheck PASS; **157 testes PASS**; runtime security PASS; Docker smoke PASS.

## V2-16.5 — Integração CampaIA

Status: **BLOQUEADO PARCIAL — ADAPTER FISCAL INTERNO CONCLUÍDO/CERTIFICADO; AUTORIDADE REAL DE FATURAMENTO/PAGAMENTO PRÓPRIO AINDA INEXISTENTE**.

Campanha, orçamento e media spend não foram tratados como receita própria. Foi criada seam fail-closed `SettledOwnBillingFact` para futuro fato autoritativo de faturamento próprio liquidado: `service-billing` → service/NFS-e; `saas-billing` → saas_billing/NFS-e; idempotência `campaia:billing:<billingId>:nfse:v1`; `PENDING_CAPABILITY`; binding/readiness obrigatórios.

Branch `feat/fisc-v2-16-campaia-integration`, PR #1 OPEN/DRAFT. HEAD `bdebbc3558ff8b07c1a38e0cb728be0dc3635c4b`, run `34784021431`, job `103796103296`: **267 core + 80 API = 347 PASS**; AsyncAPI PASS com 24 eventos.

## V2-16.6 — Adapter Contract Pack / novos produtos FM

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**.

Foram adicionadas somente as lacunas reais sobre a fundação V2-10:

- `ProductOnboardingDeclaration` + `certify_product_onboarding(...)`;
- `ProductMutationPreflight` + `validate_product_mutation_preflight(...)`;
- fail-closed para pack/host/use case/operação/documento/ação/escopo/idempotência/binding/capability/readiness;
- prova sintética fora do catálogo real;
- `docs/V2_16_ADAPTER_PACK_ONBOARDING.md`.

A certificação estrutural produz explicitamente `readiness_granted = False`; binding, capability e readiness continuam em suas autoridades próprias.

O primeiro gate B6 encontrou cinco violações Ruff. Foram corrigidas sem reduzir cobertura nem relaxar assertions. Gate integral: SHA `878738c172ab31e3f81618a95986370b17d0e602`, run `34784375685`, job `103797066379`: Install/Ruff PASS; Mypy PASS em 114 source files; Pytest **639 PASS**.

## V2-16.7 — End-to-End + Multi-Product Cross-Certification + Fechamento

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**.

O Plano Mestre original descrevia B6 como Multi-Product Cross-Certification, enquanto a execução anterior utilizou B6 para industrializar o Adapter Contract Pack. O histórico não foi renomeado. B7 reconciliou a diferença e completou a prova no estado atual.

Foi adicionada `tests/test_v2_16_cross_product_closure.py`, certificando no código corrente:

- quatro packs/host namespaces;
- NF-e, NFC-e e NFS-e;
- múltiplos operation kinds;
- host/tenant/unit/correlation/idempotency isolados em pre-flight;
- spoofing cross-product fail-closed;
- environment como parte da partição de execução;
- correlation/causation explícitas e isoladas no carrier governado;
- runtime readiness obrigatório para todos os contratos de integração;
- nenhuma autoridade de `production_approved` nos Contract Packs/Integration Contracts.

Gate B7: SHA `5afb3d9af8879f17b451e757f53ca41796e843e7`, run `34785216450`, job `103799337982`: Install PASS; Ruff PASS; Mypy PASS em **114 source files**; Pytest **646 PASS em 6.44s**.

Diff do gate contra V2-15 `33e34866...`: **20 commits ahead, 0 behind**, merge-base preservado; 10 arquivos no escopo V2-16.

Closure formal: `docs/V2_16_CLOSURE_CERTIFICATION.md`.

## Decisão formal após B1-B7

**V2-16 — BLOQUEADA PARCIAL — TODO O TRABALHO INTERNO EXECUTÁVEL CONCLUÍDO/CERTIFICADO; DEPENDÊNCIAS DE PRODUTO/EXTERNAS DOCUMENTADAS.**

A fase não é declarada integralmente concluída porque Kordena ainda depende de Web Premium/FISC-20, Vendedor IA ainda carece de dados/classificação fiscal suficientes e CampaIA ainda carece de autoridade real de faturamento próprio. Esses bloqueios não invalidam a certificação interna do Core multiproduto e não impedem trabalho preparatório de convergência, mas impedem cutover real enquanto pré-condições obrigatórias não forem satisfeitas.

## Guardrails preservados

- PRs permanentes continuam Draft/não mergeadas.
- SEM merge/auto-merge/Ready for Review.
- SEM deploy/produção real/cutover.
- SEM segredo real.
- SEM homologação externa inventada.
- SEM promoção indevida de `PRODUCTION_APPROVED`.
- O início da V2-17 é permitido somente pela autorização executiva específica e permanece preparatório, sem cutover real.
