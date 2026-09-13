# V2-16 — Integração dos Produtos FM — Registro de Execução

Data: 2026-09-13

## Estado de entrada

A V2-15 permanece preservada no checkpoint certificado `33e34866bc6e8c736c585c45101ce214816e0594`, com a PR #16 OPEN/DRAFT e não mergeada. Esta execução não altera aquele checkpoint, não realiza deploy/cutover e não usa segredos reais.

A autorização desta janela cobre somente os três primeiros blocos da V2-16, com avanço sequencial: corrigir gates internos que falharem e avançar quando verdes; bloqueios reais de produto/pré-requisito devem ser registrados sem falsificação de estado.

## V2-16.1 — Contrato de integração

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**.

A fronteira operacional comum foi adicionada em `kordena_fiscal.integrations`. Ela deriva produto/use case exclusivamente dos Product Contract Packs certificados e fixa a ligação com o contrato público FM Fiscal Bridge v1 vigente:

- capability/readiness: `POST /v1/capabilities/query`;
- emissão: `POST /v1/issuances`;
- consultas: `POST /v1/queries`;
- reconciliação: `POST /v1/reconciliations`;
- escopo obrigatório por `X-FM-Host-Namespace`, `X-FM-Tenant-Id`, `X-FM-Unit-Id`, `X-FM-Environment` e `X-Correlation-Id`;
- idempotência explícita via `Idempotency-Key`;
- readiness obrigatório antes de mutações.

O contrato é descritivo e fail-closed. Resolver um Product Contract Pack NÃO declara município/UF/provider homologado, NÃO concede prontidão de produção e NÃO substitui a Capability & Readiness API.

O primeiro gate detectou drift entre uma versão anterior do desenho do Bridge e o OpenAPI certificado atual. A implementação foi corrigida contra `contracts/v1/openapi.json`, sem enfraquecer o teste. Gate certificado no SHA `c23d49997a4344363720436374a8d9476e665262`, run `34779681157`: instalação, Ruff, mypy e pytest verdes.

## V2-16.2 — Integração Kordena

Status: **BLOQUEADA POR PRÉ-REQUISITO REAL DO PLANO MESTRE**.

O Plano Mestre determina que a integração Kordena só avance quando a V1 Web Premium estiver liberada para FISC-20. Em 2026-09-13, a PR Kordena #118 (`feat/web-parity-v1-total-original-migration`) permanece OPEN/DRAFT e registra estado funcional parcial. Portanto:

- nenhum acoplamento prematuro foi introduzido no Kordena;
- o Product Contract Pack `kordena` permanece disponível como contrato certificado;
- a implementação runtime fica congelada até o pré-requisito real ficar verde;
- este bloqueio não é defeito do FM Fiscal Core e não deve ser mascarado como integração concluída.

## V2-16.3 — Integração Iron Fit

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**.

A autoridade de liquidação no Iron Fit foi confirmada em `FinancialService.payCharge`: a `Charge` é marcada `PAID` e a `FinancialTransaction` correspondente é criada dentro da mesma transação serializável, com proteção idempotente contra repetição/concorrência.

A integração implementada cria um handoff fiscal determinístico a partir do fato comercial liquidado:

- host namespace `fm.iron`;
- Product Contract Pack `iron`;
- cobrança recorrente → `recurring-membership-billing` / `recurring_charge` / `nfse`;
- cobrança de mensalidade sem assinatura recorrente → `membership-billing` / `membership` / `nfse`;
- estado inicial `PENDING_CAPABILITY`;
- `readinessRequiredBeforeIssuance = true`;
- binding fiscal obrigatório antes de emissão;
- chave idempotente `iron:charge:<chargeId>:nfse:v1`;
- registro do handoff dentro da mesma transação serializável da quitação, usando o audit ledger governado;
- nenhuma chamada de rede real, nenhum provider/município escolhido pelo Iron e nenhuma regra tributária duplicada no produto.

Durante o primeiro gate do Iron, `npm audit --audit-level=high` bloqueou a execução antes de compilar o nosso código por vulnerabilidade alta transitiva no `multer 2.2.0`. O gate NÃO foi desabilitado. A dependência foi corrigida para `multer 2.3.0`, o lockfile foi regenerado de forma reproduzível e o workflow canônico foi restaurado antes da certificação final.

Branch Iron: `feat/fisc-v2-16-iron-integration`. PR Iron #48: OPEN/DRAFT, não mergeada. Gate canônico final no SHA `2be8321eeb066f0296ba812faab0a098c32f0632`, run `34780329013`: `npm ci`, dependency audit, Prisma generate, lint/typecheck, build e smoke regression tests verdes.

## Resultado formal da execução autorizada B1-B3

**V2-16 — BLOQUEADA PARCIAL — V2-16.1 E V2-16.3 INTERNAMENTE CONCLUÍDAS/CERTIFICADAS; V2-16.2 KORDENA BLOQUEADA POR PRÉ-REQUISITO WEB PREMIUM/FISC-20.**

A execução autorizada dos três blocos foi concluída. O bloqueio restante desta janela é explícito e externo ao FM Fiscal Core: depende da liberação real do Kordena Web Premium/FISC-20.

## Guardrails preservados

- SEM MERGE da PR #16, PR #17 ou PR Iron #48.
- SEM DEPLOY.
- SEM PRODUÇÃO REAL.
- SEM CUTOVER.
- SEM SEGREDO REAL NO REPOSITÓRIO.
- SEM HOMOLOGAÇÃO EXTERNA INVENTADA.
- SEM PROMOÇÃO INDEVIDA DE `PRODUCTION_APPROVED`.
- nenhum bloco posterior à V2-16.3 foi iniciado nesta execução.
