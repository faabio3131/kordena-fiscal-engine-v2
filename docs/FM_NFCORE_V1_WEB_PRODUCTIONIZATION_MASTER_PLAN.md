# FM NFCORE V1 — Plano Mestre de Web Productionization

Status: **PLANO OFICIAL — EXECUÇÃO PENDENTE POR BLOCOS**  
Data: 2026-09-14  
Baseline auditado: `main` @ `851a8c3e1163e7362b83998b8d53255e2d564df3`

## 1. Objetivo

Transformar o FM NFCORE de Core fiscal + portal premium interno em um SaaS web real, deployável, autenticado, persistente, observável e comercialmente operável, sem quebrar os contratos fiscais, safety gates e boundaries já certificados.

O objetivo desta fase não é reescrever o Core. É materializar a camada web/infraestrutura que falta para operar o produto real na internet.

## 2. Resultado da auditoria do repositório

### 2.1 Já existe e deve ser preservado

- Core fiscal modular e desacoplado;
- contratos OpenAPI/AsyncAPI versionados em `contracts/v1`;
- lifecycle, idempotência, reconciliação, archive, inbox/outbox e webhook architecture;
- Control Plane e configuração por tenant/unidade/ambiente;
- billing foundation, pricing configurável e onboarding;
- S2S/workload identity e signing boundaries;
- Vault abstraction com `SecretReference`;
- observabilidade de domínio: eventos, métricas, tracing e alerting abstractions;
- provider/gateway, resilience e homologation boundaries;
- portal premium responsivo FM NFCORE V1;
- Python SDK e referência TypeScript;
- 773 testes certificados no último gate de identidade.

### 2.2 Lacunas web/produtivas confirmadas

#### Runtime HTTP standalone

O repositório possui contratos OpenAPI, SDKs e serviços de aplicação, porém não possui framework/runtime HTTP de produção materializado. O `pyproject.toml` não contém FastAPI, Starlette, Uvicorn, Flask, Django ou equivalente.

**Estado: FALTA IMPLEMENTAR.**

#### Persistência de produção

A implementação persistente concreta atual é SQLite (`src/kordena_fiscal/persistence/sqlite*.py`). Não existe adapter PostgreSQL materializado no baseline auditado.

**Estado: FALTA IMPLEMENTAR.**

#### Autenticação web de usuário final

Existe segurança S2S/workload para integrações, mas não foi identificada camada completa de identidade de usuário web com login, sessões/tokens, recuperação de senha e RBAC de portal.

**Estado: FALTA IMPLEMENTAR.**

#### Portal conectado ao backend

O portal atual foi deliberadamente construído como superfície segura com dados sintéticos. Os testes preservam inclusive ausência de `fetch()` e de armazenamento de credenciais no navegador.

**Estado: FALTA CONECTAR, mantendo safety boundaries.**

#### Packaging/deploy de produção

Não há `Dockerfile`, compose, manifests de deploy ou IaC materializados no baseline auditado.

**Estado: FALTA IMPLEMENTAR.**

#### Secret backend produtivo

O boundary de Vault está pronto, porém o adapter concreto identificado no baseline é `in_memory.py`; provider cloud/KMS/secret manager real não está materializado.

**Estado: FALTA IMPLEMENTAR ADAPTER REAL.**

#### Provider transports reais

Os boundaries estão certificados e existe `SyntheticProviderTransport`. Endpoints e credenciais reais permanecem dependentes de homologação/provisionamento externo.

**Estado: INTERNO PREPARADO / EXTERNO PENDENTE.**

#### Produção, DNS e TLS

Configuração de hostname/domain existe como modelo, mas deploy, DNS, HTTPS e endpoint produtivo real não foram executados.

**Estado: EXTERNO/OPERACIONAL PENDENTE.**

## 3. Arquitetura alvo V1 web

Topologia inicial recomendada para custo e simplicidade:

```text
Internet
  -> HTTPS / Reverse Proxy / CDN
     -> Web App FM NFCORE
     -> API FM NFCORE
        -> Application/Core
        -> PostgreSQL
        -> Object Storage (XML/PDF/evidências)
        -> Queue/Worker
        -> Secret Manager/KMS
        -> Providers fiscais
        -> Observability
```

### Componentes

- **Web UI:** portal FM NFCORE responsivo;
- **API:** FastAPI como adapter HTTP fino sobre serviços existentes;
- **Database:** PostgreSQL;
- **Migrations:** Alembic ou mecanismo equivalente versionado;
- **Async:** worker dedicado com fila persistente;
- **Storage:** object storage compatível S3 para XML/PDF/archive quando aplicável;
- **Secrets:** adapter para Secret Manager/KMS escolhido no ambiente;
- **Ingress:** HTTPS obrigatório;
- **Observability:** logs estruturados, health/readiness, métricas e alertas;
- **CI/CD:** build, test, image, deploy staging e promoção governada para produção.

Kubernetes não é requisito para a primeira V1 comercial. A arquitetura deve permanecer preparada para migração futura sem reescrever o Core.

## 4. Work Packages sequenciais

### WP-WEB-01 — HTTP Runtime Foundation

Objetivo:
- adicionar FastAPI/ASGI;
- app factory;
- versionamento `/api/v1`;
- request/correlation context;
- health/liveness/readiness;
- exception mapping;
- OpenAPI alinhada ao contrato existente;
- testes de contrato HTTP.

Gate:
- Ruff PASS;
- Mypy PASS;
- Pytest PASS;
- rotas críticas com contract tests;
- nenhum bypass de tenant/readiness.

### WP-WEB-02 — Identity, Session & RBAC

Objetivo:
- usuários humanos;
- login seguro;
- hashing de senha moderno;
- sessão/token web;
- expiração/rotação/revogação;
- password reset;
- RBAC;
- tenant/unit scope derivado da autoridade autenticada;
- proteção CSRF quando aplicável;
- rate limiting de auth.

Gate:
- cross-tenant negatives;
- privilege escalation negatives;
- sessão revogada não reutilizável;
- segredo/senha nunca retornado em API/log.

### WP-WEB-03 — PostgreSQL Production Persistence

Objetivo:
- adapters PostgreSQL compatíveis com ports atuais;
- migrations;
- transactions;
- optimistic/concurrency control onde necessário;
- índices;
- pooling;
- tenant isolation tests;
- migration from synthetic/local state only when applicable.

Gate:
- suite equivalente ao SQLite + PostgreSQL;
- restart/recovery;
- idempotência e sequence authority preservadas;
- migration upgrade/downgrade testada.

### WP-WEB-04 — Portal Real API Integration

Objetivo:
- remover datasets sintéticos da jornada operacional real;
- camada de API client;
- login/logout;
- loading/error/empty real;
- paginação/filtros;
- formulários de onboarding/configuração;
- documentos, emissões, reconciliation, webhooks, certificates, usage, plans e audit ligados ao backend.

Regra:
- nenhuma credencial fiscal sensível no browser;
- browser manipula somente referências e metadados permitidos.

### WP-WEB-05 — Worker & Async Runtime

Objetivo:
- outbox worker em processo separado;
- webhook delivery worker;
- reconciliation jobs;
- retry/DLQ governado;
- lease/locking para impedir processamento duplicado;
- shutdown seguro.

### WP-WEB-06 — Production Secret Backend

Objetivo:
- implementar `FiscalSecretVault` produtivo para o provedor escolhido;
- envelope encryption/KMS quando aplicável;
- rotação;
- least privilege;
- audit de resolução;
- zero material secreto persistido no banco/app logs.

### WP-WEB-07 — Containers & Environment Profiles

Objetivo:
- Dockerfile API;
- Dockerfile/hosting frontend;
- worker image;
- `.env.example` sem segredos;
- profiles dev/staging/prod;
- health checks;
- startup dependency checks;
- non-root runtime.

### WP-WEB-08 — Observability & Recovery Productionization

Objetivo:
- structured logs;
- metrics endpoint/exporter;
- distributed tracing adapter;
- alerts;
- backup schedule;
- restore rehearsal;
- RPO/RTO técnico inicial;
- incident runbooks alinhados ao runtime real.

### WP-WEB-09 — CI/CD & Staging

Objetivo:
- pipeline de build/test/security;
- container scanning;
- deploy automático em staging;
- migrations governadas;
- smoke tests pós-deploy;
- promoção de produção manual/aprovada.

### WP-WEB-10 — Domain, TLS & Production Provisioning

Objetivo:
- hostname oficial;
- DNS;
- HTTPS/TLS;
- redirects seguros;
- CORS/CSP/headers;
- WAF/rate limiting conforme provedor;
- ambiente produtivo isolado.

Dependência: domínio e conta cloud reais.

### WP-WEB-11 — Cakto Commercial Activation

Objetivo:
- checkout/subscription integration;
- webhook Cakto autenticado e idempotente;
- mapping produto/plano -> pricing catalog;
- provisioning de tenant após evento comercial confirmado;
- suspensão/reativação governadas;
- billing authority separada da fiscal authority.

Dependência: conta e credenciais reais Cakto.

### WP-WEB-12 — Real Fiscal Homologation & Pilot

Objetivo:
- certificados/CSC/credentials reais;
- transports reais;
- homologação por UF/município/provider/operação;
- piloto controlado;
- emissão/cancelamento/reconciliation/webhook reais;
- Go/No-Go humano.

Regra: nenhum readiness produtivo será promovido sem evidência real.

## 5. Ordem de execução

Ordem obrigatória recomendada:

`WP-WEB-01 -> 02 -> 03 -> 04 -> 05 -> 06 -> 07 -> 08 -> 09 -> 10 -> 11 -> 12`

Alguns blocos podem ter preparação paralela, mas promoção para a próxima etapa exige gate verde do predecessor crítico.

## 6. Critério de “FM NFCORE 100% comercial web”

Somente declarar **100% comercial web** quando:

- portal real estiver ligado ao backend;
- autenticação/RBAC estiverem ativos;
- PostgreSQL e migrations estiverem produtivos;
- worker/async estiver operacional;
- secret backend real estiver configurado;
- container/deploy/staging/prod estiverem certificados;
- domínio + HTTPS estiverem ativos;
- backup/restore e observability estiverem validados;
- Cakto estiver integrada para o modelo comercial aprovado;
- homologações reais mínimas da oferta estiverem provadas;
- piloto real estiver aprovado;
- Go-Live tiver autorização humana.

Até lá, usar estados precisos como `INTERNAL_READY`, `STAGING_READY`, `BLOCKED_EXTERNAL` ou `PILOT_READY`, sem declarar produção completa artificialmente.

## 7. Primeiro próximo passo

Iniciar **WP-WEB-01 — HTTP Runtime Foundation** em branch própria, sem alterar regras fiscais, com FastAPI como adapter de transporte e contract tests contra `contracts/v1/openapi.json`.
