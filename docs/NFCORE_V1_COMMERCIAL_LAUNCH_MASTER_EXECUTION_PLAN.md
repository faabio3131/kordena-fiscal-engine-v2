# FM NFCORE V1 — Commercial Launch Closure

## Auditoria de prontidão + Plano Mestre de Execução

**Status:** PLANO MESTRE — AGUARDANDO APROVAÇÃO PARA EXECUÇÃO  
**Data:** 2026-09-16  
**Repositório:** `faabio3131/kordena-fiscal-engine-v2`  
**Baseline:** `main @ da3c927c2cd2fac6559f4c178f715fad9db0a14d`

## Objetivo

Transformar o NFCORE V1, já internamente certificado, em produto comercial real para Cakto + site FM Tecnologia, sem atrasar o lançamento com a futura camada cognitiva V2.

A branch `feat/nfcore-accounting-workspace-core-management` fica estacionada até o lançamento da V1.

Este plano não inventa `WP-WEB-13`. A sequência oficial Web terminou em `WP-WEB-12`; o fechamento comercial usa `CL-00..CL-12`.

## Resultado da auditoria

### Pronto e reutilizável

- Core fiscal multi-tenant e fail-closed;
- portal web e componentes de login/session/RBAC;
- PostgreSQL/migrations e persistência de identidade;
- pricing, billing e onboarding configuráveis;
- Cakto interna com webhook autenticado, inbox durável, idempotência, retry/DLQ, entitlements e reconciliação;
- outbox, webhook delivery e reconciliation no domínio/aplicação;
- SecretReference e secret boundary vendor-neutral;
- containers API/worker/portal;
- CI completa, E2E, security audits, SBOM, backup/restore;
- contratos de staging e promoção governada;
- autoridade fiscal de produção separada de billing.

### Lacunas reais de lançamento

1. **Composition root produtivo — BLOCKED_INTERNAL.** O runtime monta `create_app()` sem injetar identidade humana, portal/executors; Cakto só aparece se receiver for explicitamente injetado. É necessário compor os serviços já existentes, sem criar arquitetura paralela.
2. **Worker produtivo — BLOCKED_INTERNAL.** O entrypoint atual valida dependências e fica intencionalmente idle. É necessário ligar os background workers canônicos já existentes.
3. **Secret backend real — BLOCKED_EXTERNAL.** O boundary está pronto, mas nenhum AWS/Azure/GCP/Vault/KMS real foi escolhido/configurado.
4. **Staging/produção — BLOCKED_EXTERNAL.** CI/CD é provider-neutral; faltam hosting, PostgreSQL real, ingress, HTTPS, secret backend e deploy driver do provedor escolhido.
5. **Cakto real — INTERNAL_CAKTO_READY / BLOCKED_EXTERNAL.** Faltam credenciais, produto/oferta, callback HTTPS, webhook real e reconciliação real.
6. **Pricing — motor pronto; decisão comercial pendente.** Fazer nova pesquisa competitiva antes de congelar planos/preços.
7. **Site FM — pendente de preflight no repositório correto.** O site deve reutilizar o mesmo catálogo/checkout, nunca billing paralelo.
8. **Fiscal real — INTERNAL_FISCAL_ACTIVATION_READY / BLOCKED_EXTERNAL.** Definir escopo inicial e homologar somente as células realmente vendidas.
9. **Legal/LGPD — technical-ready; legal validation required.** Documentação técnica não substitui validação jurídica externa.

## Governança obrigatória

- sem alteração direta em `main`;
- sem merge, deploy, DNS produtivo ou cutover sem autorização humana específica;
- sem segredos reais no Git, banco comum, browser ou logs;
- sem enfraquecer testes;
- sem segunda arquitetura de auth, billing, tenant, worker ou autoridade fiscal;
- `MERGED != DEPLOYED`;
- `INTERNAL_READY != STAGING_READY`;
- `CAKTO_COMMERCIAL_READY != FISCAL_HOMOLOGATED`;
- `HOMOLOGATED != PILOT_READY`;
- `PILOT_READY != PRODUCTION_APPROVED`;
- `PRODUCTION_APPROVED != CUTOVER_COMPLETE`.

## Cronograma Mestre

| Bloco | Escopo | Estimativa interna | Dependência principal |
|---|---|---:|---|
| CL-00 | Freeze V1 + governança + inventário | 1–2 h | — |
| CL-01 | Production Composition Root | 8–14 h | CL-00 |
| CL-02 | Worker Runtime Activation | 8–14 h | CL-01 |
| CL-03 | Secret Manager real | 8–16 h | CL-00 |
| CL-04 | Infraestrutura + staging real | 10–18 h | CL-01/02/03 |
| CL-05 | Cakto real + E2E/reconciliação | 8–14 h | CL-03/04 |
| CL-06 | Pesquisa de mercado + pricing/packaging | 8–14 h | CL-00 |
| CL-07 | Jornada comercial E2E | 8–14 h | CL-01/02/05/06 |
| CL-08 | Página NFCORE no site FM | 6–12 h provisórias | CL-06 + preflight site |
| CL-09 | Escopo fiscal inicial + homologação oficial | 6–12 h + espera externa | CL-03/04 |
| CL-10 | Piloto real controlado | 6–10 h + janela externa | CL-09 |
| CL-11 | Go/No-Go + Production Cutover | 6–10 h | CL-05/07/08/09/10 |
| CL-12 | Hypercare primeiro lote comercial | 4–8 h | CL-11 |

**Ordem de grandeza interna:** aproximadamente **95–150 horas**.  
**Valor de planejamento:** aproximadamente **120 horas internas**, sem contar espera de Cakto, cloud, DNS, certificados, provider/SEFAZ/prefeitura, piloto e validação jurídica.

## Caminho crítico

`CL-00 -> CL-01 -> CL-02/CL-03 -> CL-04 -> CL-05/CL-07 -> CL-09 -> CL-10 -> CL-11 -> CL-12`

Paralelizáveis: CL-03, CL-06, CL-08 e validações externas/jurídicas.

## Gates resumidos

### CL-01 — Composition Root
Compor Postgres/repositories, HumanIdentityService, password recovery, portal/executors e Cakto receiver quando configurado. Produção fiscal permanece falsa sem authority exata. Gate: toda matriz CI 100% verde.

### CL-02 — Worker
Ligar background runtime, outbox, webhook delivery, reconciliation e processamento Cakto. Preservar lease, idempotência, retries, shutdown e fail-closed. Gate: concorrência/restart/crash recovery verdes.

### CL-03 — Secrets
Escolher e integrar Secret Manager real ao boundary existente, com least privilege, rotação/revogação e auditoria sem material sensível. Gate: staging sem backend in-memory.

### CL-04 — Staging
Provisionar ambiente real, Postgres, API, worker, portal, ingress/HTTPS, logs, métricas e backup; materializar deploy driver e executar workflow real. Gate: `STAGING_READY`.

### CL-05 — Cakto
Revalidar contrato atual; configurar credenciais, produto/oferta e callback; provar evento real, processamento assíncrono e reconciliação. Gate: `CAKTO_COMMERCIAL_READY` sem conceder autoridade fiscal.

### CL-06 — Pricing
Refazer pesquisa competitiva, decidir planos/trial/promoção e publicar configuração versionada. Gate: aprovação do diretor.

### CL-07 — Jornada comercial
Provar `site/checkout -> Cakto -> webhook -> entitlement -> tenant -> owner/login -> onboarding -> empresa/unidade -> configuração fiscal -> readiness`, incluindo cancelamento, suspensão e reativação.

### CL-08 — Site
Fixar repo/branch/SHA do site, publicar página do NFCORE, planos e CTA Cakto/trial. Não prometer capacidade ainda não homologada.

### CL-09 — Homologação
Escolher o escopo fiscal real de lançamento e obter evidência oficial por documento × operação × UF/município × provider. Células sem evidência permanecem `BLOCKED_EXTERNAL`.

### CL-10 — Piloto
Executar fluxo real controlado no escopo homologado, reconciliar e produzir pacote Go/No-Go. `PILOT_READY` não implica `PRODUCTION_APPROVED`.

### CL-11 — Go-Live
Validar domínio/TLS, banco, secrets, backups, monitoramento, Cakto, site, homologação, piloto e checklist jurídico/operacional. Deploy/cutover e `PRODUCTION_APPROVED` exigem autorização humana específica.

### CL-12 — Hypercare
Monitorar auth, checkout, webhooks, workers, fiscal, reconciliação e suporte no primeiro lote. Somente correções V1.x; nenhuma feature V2.

## Critério de conclusão

Somente declarar **NFCORE V1.0 COMMERCIAL LIVE** quando runtime composto, worker, Postgres, Secret Manager, staging, Cakto E2E, pricing, onboarding, site, escopo fiscal homologado, piloto, backup/restore, monitoramento e Go/No-Go estiverem comprovados, seguidos de deploy/cutover explicitamente autorizado e smoke produtivo verde.

## Primeiro bloco após aprovação

Executar `CL-00` e imediatamente `CL-01 — Production Composition Root`.

A prioridade é fechar a diferença entre **componentes certificados** e **aplicação comercial realmente composta**, sem reconstruir a Web V1 e sem misturar a arquitetura cognitiva V2.