# FM Fiscal — V2-18 Release Candidate Manifest

## Identidade do candidato

- Produto: **FM Fiscal**
- Release Candidate técnico: **`2.18.0-rc.1`**
- Repositório: `faabio3131/kordena-fiscal-engine-v2`
- Branch: `v2/commercial-independent-product`
- PR permanente: **#22 — OPEN/DRAFT/não mergeada**
- Base V2-17 certificada: `cfd58c3249a5601dc62088eee7327dfe02759646`
- SHA de código do RC após o fechamento funcional/security de V2-18.10: `744925d9940cbf17f527423fe54d442f1d845204`
- Publicação produtiva: **NÃO AUTORIZADA**

O SHA acima identifica o conteúdo executável certificado antes da documentação de fechamento V2-18.11. O HEAD documental final é certificado por CI após a inclusão deste manifesto, closure certification, tracker e auditoria final.

## Superfícies públicas

Bridge/API pública preservada:

- `POST /v1/capabilities/query`
- `POST /v1/issuances`
- `POST /v1/queries`
- `POST /v1/reconciliations`

Escopo público obrigatório preserva:

- host namespace;
- tenant;
- unidade;
- ambiente;
- correlation;
- causation quando aplicável;
- idempotency para mutações.

## Persistência e migrações

- autoridade de persistência permanece no FM Fiscal;
- migrations SQLite de referência permanecem versionadas e restart-safe;
- baseline de schema certificado inclui migrations `1..5`;
- migration contract V2-17.2 e cutover rehearsal V2-17.3 são sintéticos/governados;
- **nenhuma migração produtiva foi executada**.

## SDKs

### Python

Pacote de referência: `fm_fiscal_sdk`

Cobre:

- Bridge público;
- scope headers;
- correlation/causation;
- idempotency;
- retry bounded;
- webhook signature verification.

### TypeScript

Referência TypeScript incluída na documentação/superfície V2-18.5. Não contém regra fiscal privada nem acesso direto ao banco do Core.

SDKs acompanham o RC técnico e não são publicação autônoma de registry nesta fase.

## Produto comercial técnico

O RC contém:

- identidade FM Fiscal independente;
- catálogo de módulos;
- editions/entitlements configuráveis;
- self-service onboarding resumível;
- plans/quotas/trial/grace/suspension/reactivation;
- separação Commercial Billing Authority × Fiscal Document Authority;
- documentation/developer experience;
- support/runbooks/health contracts;
- pacote técnico LGPD/retention;
- premium portal de referência;
- commercial E2E sintético.

Não existem preços finais hardcoded nem SLA contratual definitivo.

## Portal premium

Referência em `portal/`:

- `index.html`;
- `styles.css`;
- `app.js`.

É uma superfície interna/sintética de referência, sem chamadas de rede, cookies, localStorage, segredo real ou mutação produtiva.

## Dependências de runtime certificadas

Faixas declaradas:

- `cryptography>=50,<51`;
- `lxml>=5.3,<7`.

O gate V2-18.10 instalou `cryptography 50.0.1` e executou `pip-audit` sobre o conjunto explícito de runtime, com resultado **No known vulnerabilities found**.

A faixa antiga `cryptography>=44,<48` foi elevada após o dependency audit encontrar advisories reais em `cryptography 47.0.0`.

## Segurança

Gate V2-18.10:

- run `34791936752`;
- job `103817664298`;
- Ruff PASS;
- Mypy PASS em 126 source files;
- Bandit Medium/High PASS;
- B608 documentado como false positive estruturalmente protegido;
- pip-audit PASS sem vulnerabilidades conhecidas no conjunto auditado;
- Pytest 741 PASS.

Triage: `docs/V2_18_10_SAST_TRIAGE.md`.

## Performance e recovery

A regressão do RC mantém os hardenings já certificados:

- 2.048 números fiscais concorrentes únicos/contíguos;
- 5.000 pontos de métricas;
- cardinality cap/noisy-neighbor;
- 200 outbox entries sem duplicação;
- circuit breaker/recovery;
- provider timeout/retry bounded;
- unknown outcome sem blind retry;
- restart/lease reclaim;
- inbox/outbox/webhook retry/DLQ;
- archive tamper detection;
- migration/restart idempotence;
- billing/onboarding checkpoint restore.

## Known limitations / blockers

O RC não é autorização de produção. Permanecem fora do fechamento puramente interno:

- Kordena/Web Premium FISC-20 e integração produtiva do consumidor;
- fatos fiscais ainda ausentes no Vendedor IA para classificação segura quando aplicável;
- authority de own billing/payment da CampaIA quando aplicável;
- homologações oficiais externas;
- certificados, CSC e provider credentials reais;
- inventário/freeze de writers reais;
- snapshot/migração produtiva;
- deploy/DNS/endpoint produtivo;
- cutover real;
- aprovação jurídica/comercial final de itens marcados;
- autorização humana final.

## Classificação

**`2.18.0-rc.1` = Release Candidate técnico interno.**

Não significa:

- release produtiva;
- homologação oficial;
- `PRODUCTION_APPROVED`;
- cutover;
- SLA contratual publicado;
- parecer jurídico final.
