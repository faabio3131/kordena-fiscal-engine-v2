# FM NFCORE V1 — PROMPT MESTRE DE EXECUÇÃO DA CADEIA COMERCIAL

**Status:** EXECUTION MASTER CANDIDATE — HUMAN APPROVAL REQUIRED BEFORE PRODUCTION IMPLEMENTATION  
**Data:** 2026-09-27  
**Projeto:** NFCore Commercial Launch  
**Produto:** FM NFCORE V1  
**Repositório canônico:** `faabio3131/kordena-fiscal-engine-v2`  
**CURRENT base no momento deste documento:** `19f1102d64a956de3eefa6cb2d6f2f0ddefb0f09`

---

## 1. MISSÃO

Concluir a cadeia comercial do NFCore de ponta a ponta para que uma venda ou trial legitimamente autorizado possa resultar em um cliente NFCore utilizável, sem acoplar o produto a Cakto, Hotmart, Kax, Site FM, marketplace, afiliado, representante ou qualquer outro canal externo.

Princípio operacional:

> **O canal vende. O NFCore valida o direito comercial e entrega o SaaS.**

A cadeia final deve permitir, conforme o canal:

```text
Canal de venda
    ↓
evento comercial autenticado e validado
    ↓
fato comercial canônico NFCore
    ↓
purchase/subscription/entitlement canônico
    ↓
identidade comercial/claim
    ↓
organização canônica
    ↓
primeiro OWNER
    ↓
ativação segura
    ↓
login
    ↓
onboarding
    ↓
uso do NFCore
```

Nenhum canal externo se torna autoridade de tenant, usuário, RBAC, fiscal, organização ou regra de negócio do NFCore.

---

## 2. ORDEM DE AUTORIDADE

Sempre obedecer:

1. Código CURRENT no Git/GitHub.
2. Branches, commits, PRs, merges e `main`.
3. CI, testes, builds e evidências reproduzíveis.
4. Documento Mestre FM.
5. System Design / ADRs / checkpoints canônicos.
6. Este Prompt Mestre.
7. Conversa/memória apenas como contexto.

Antes de qualquer bloco:

- reconfirmar `main`, HEAD, PRs e CI;
- ler o último checkpoint persistente;
- identificar a autoridade canônica;
- declarar CURRENT → TARGET;
- congelar escopo;
- definir mapa de impacto;
- definir critérios de aceite;
- definir testes;
- só então implementar.

---

## 3. PRINCÍPIOS CONSTITUCIONAIS

### 3.1 Uma autoridade por domínio

Não criar segunda autoridade para:

- pricing;
- checkout;
- billing/subscription/entitlement;
- tenant;
- organização;
- usuário;
- autenticação;
- RBAC;
- unidade;
- fiscal;
- secrets;
- activation/recovery;
- audit.

Adapters traduzem fatos externos. Não substituem autoridades internas.

### 3.2 Provider-neutral por padrão

O Core não conhece regras específicas de Cakto, Hotmart, Kax ou outro canal.

Novo protocolo externo pode exigir um adapter reutilizável uma vez.

Depois de suportado:

- conta;
- produto;
- oferta;
- preço externo;
- endpoint;
- webhook;
- secret;
- credencial;

são configuração governada, não forks de código por cliente.

### 3.3 Core coordena; serviços determinísticos executam

IA nunca substitui:

- autenticação;
- autorização;
- tenant/unidade;
- payment proof;
- entitlement;
- fiscal rule;
- idempotência;
- migration;
- segurança;
- aprovação humana.

### 3.4 Fail-closed

Falhar fechado em:

- identidade;
- autenticação;
- autorização;
- tenant;
- unidade;
- PII;
- secrets;
- pagamento;
- refund/chargeback;
- subscription state;
- activation;
- integrações críticas;
- fiscal;
- produção;
- ações irreversíveis.

---

## 4. MAPA DE AUTORIDADE COMERCIAL

### External Sales Channel

Autoridade apenas sobre o fato externo que realmente processou, por exemplo:

- pagamento aprovado;
- renovação;
- atraso;
- cancelamento;
- refund;
- chargeback.

O canal não é autoridade de:

- tenant NFCore;
- organização NFCore;
- OWNER;
- RBAC;
- entitlement canônico;
- fiscal production;
- dados fiscais.

### NFCore Commercial Authority

Autoridade canônica de:

- internal purchase/acquisition;
- plan/price mapping;
- subscription state;
- entitlement;
- quota;
- claim/activation state;
- commercial access.

### NFCore Control Plane

Autoridade canônica de:

- tenant/organization;
- unit;
- user;
- OWNER;
- permissions;
- onboarding state.

### Fiscal Authority

Separada de comercialização.

Pagamento nunca cria:

- `PRODUCTION_APPROVED`;
- homologação;
- certificado;
- CSC;
- provider fiscal readiness.

---

## 5. EVENTOS COMERCIAIS CANÔNICOS

Adapters devem normalizar eventos externos em fatos internos estreitos.

Conjunto inicial candidato:

- `SaleConfirmed`;
- `SubscriptionActivated`;
- `SubscriptionRenewed`;
- `SubscriptionPaymentLate`;
- `SubscriptionRecovered`;
- `SubscriptionCanceled`;
- `RefundConfirmed`;
- `ChargebackConfirmed`.

Cada fato deve carregar somente o mínimo necessário, incluindo quando aplicável:

- provider/channel ID;
- provider event ID;
- provider order/subscription reference;
- canonical plan/price reference resolvida;
- buyer/contact reference mínima;
- occurred_at;
- idempotency/dedup key;
- correlation/causation IDs.

Nunca aceitar do browser como verdade:

- payment approved;
- entitlement IDs;
- tenant ID;
- subscription status;
- refund;
- commercial approval;
- fiscal production state.

---

## 6. SEGURANÇA E ISOLAMENTO DE DADOS — OBRIGATÓRIO

Segurança não é fase final. Cada mudança deve provar isolamento e minimização.

### 6.1 Classes operacionais de dados para CL-11

Esta classificação é operacional deste bloco e deve ser reconciliada com qualquer classificação corporativa futura mais ampla.

**PUBLIC**
- planos/preços publicados;
- conteúdo comercial público;
- URLs públicas de checkout já aprovadas para exposição.

**INTERNAL**
- IDs internos não sensíveis;
- estados de workflow;
- métricas agregadas sem PII.

**CUSTOMER/PII**
- nome;
- e-mail;
- telefone;
- endereço;
- dados de contato;
- dados pessoais vindos de canal externo.

**CONFIDENTIAL BUSINESS/FISCAL**
- identidade empresarial;
- dados de organização;
- billing state;
- entitlements;
- dados fiscais;
- configurações tenant/unidade;
- evidências de homologação.

**SECRET**
- webhook secret;
- API token;
- OAuth client secret;
- certificados privados;
- CSC;
- database credentials;
- cloud credentials;
- session secrets;
- reset/activation raw token.

### 6.2 Regras obrigatórias

- segredo real nunca entra no Git;
- segredo real nunca entra em logs;
- segredo real nunca entra em browser/client bundle;
- segredo real nunca entra em auditoria em claro;
- secret material somente por Vault/Secret Manager boundary;
- PII não deve aparecer em log estruturado salvo política explícita e minimizada;
- raw webhook body não deve ser persistido indefinidamente por conveniência;
- quando prova de integridade bastar, usar hash/digest;
- external customer ID deve permanecer provider-scoped;
- external order/subscription IDs devem ser namespaced por provider;
- lookup cross-provider deve exigir provider explícito;
- queries tenant-scoped devem exigir autoridade da sessão/contexto canônico;
- browser headers não podem sobrescrever tenant/unidade autenticados;
- nenhum evento de provider pode transportar autoridade de tenant canônico;
- nenhum adapter pode ler dados de outro tenant sem contrato explícito de plataforma;
- retries devem preservar idempotência;
- dead-letter não pode expor payload sensível;
- backups devem preservar criptografia, retenção e isolamento;
- export/delete/retention de PII devem ser tecnicamente mapeados;
- qualquer requisito jurídico/LGPD não comprovado deve ser marcado `HUMAN/LEGAL REVIEW REQUIRED`.

### 6.3 Testes obrigatórios de isolamento

Adicionar cobertura para:

- cross-tenant read;
- cross-tenant write;
- cross-unit access;
- cross-provider external ID collision;
- same external customer ID em providers diferentes;
- replay de webhook;
- forged provider event;
- forged browser payment claim;
- session tenant spoofing;
- wrong-plan mapping;
- owner email pertencente a outro tenant;
- activation token replay;
- reset token leakage;
- secret leakage em logs/errors/audit;
- dead-letter payload redaction;
- backup/restore mantendo segregação.

---

## 7. DATA MINIMIZATION E RETENÇÃO

Antes de criar qualquer coluna/tabela, responder:

1. Por que este dado é necessário?
2. Qual domínio é autoridade?
3. Quem pode ler?
4. Quem pode escrever?
5. Por quanto tempo precisa existir?
6. Pode ser hash/reference em vez de valor bruto?
7. Precisa ser exportável?
8. Precisa ser apagável?
9. Está em backup?
10. Aparece em log/auditoria?
11. É PII, fiscal, comercial ou secret?
12. Existe base jurídica validada? Se não, marcar revisão humana/jurídica.

Não copiar payload completo de marketplace para banco canônico.

Persistir somente campos necessários para:

- segurança;
- dedup/idempotência;
- reconciliação;
- entitlement;
- claim;
- auditoria.

---

## 8. CANONICAL CUSTOMER CLAIM

Venda externa não deve exigir criação prévia de tenant.

Fluxo suportado:

```text
venda aprovada
    ↓
purchase canônica UNCLAIMED
    ↓
activation/claim seguro
    ↓
comprador prova posse do canal de contato
    ↓
fornece/completa identidade empresarial necessária
    ↓
NFCore resolve/cria organização canônica
    ↓
OWNER
```

Nunca transformar automaticamente:

- display name do comprador em razão social;
- provider customer ID em tenant ID;
- e-mail do provider em prova suficiente de autoridade empresarial quando houver conflito.

Casos ambíguos vão para `MANUAL_REVIEW`.

---

## 9. FIRST-PARTY E MARKETPLACE

### Venda iniciada no Site FM

Permitido coletar previamente dados mínimos para melhorar UX.

O Site pode criar/solicitar uma referência de aquisição NFCore.

O Site não é autoridade de pagamento.

### Venda iniciada fora do Site

Hotmart/Cakto/Kax/afiliado/marketplace podem gerar venda sem visita prévia ao Site FM.

O NFCore deve receber o evento, criar purchase não reclamada/identity-required e seguir pelo claim/activation.

O Site FM nunca é dependência obrigatória da comercialização.

---

## 10. BILLING/SUBSCRIPTION CANÔNICO

Reutilizar e evoluir:

- `CommercialPlan`;
- `CommercialSubscription`;
- `SubscriptionStatus`;
- quotas;
- entitlements.

Criar persistência durável provider-neutral.

Provider-specific state permanece somente para:

- inbox;
- reconciliation;
- event ordering;
- external status evidence.

Acesso ao NFCore deve ser decidido pela autoridade canônica.

### Transições mínimas

- paid/activated -> ACTIVE;
- renewal -> mantém/atualiza ACTIVE;
- late -> GRACE conforme política;
- recovered -> ACTIVE;
- canceled -> CANCELED/SUSPENDED conforme política;
- refund/chargeback -> política comercial canônica;
- fiscal history nunca é apagado por billing.

---

## 11. PURCHASE READINESS

`purchase_enabled` só pode ser verdadeiro quando a jornada paga estiver operacional.

Gates mínimos:

- Commercial Release aprovado;
- pricing publicado;
- provider/checkout configurado;
- mapping completo;
- webhook/event processing ready;
- canonical purchase/subscription persistence ready;
- fulfillment orchestrator ready;
- provisioning ready;
- activation delivery ready;
- security dependencies ready.

Qualquer ausência -> `purchase_enabled=false`.

Nunca exibir CTA de compra que possa cobrar sem entregar uma conta utilizável.

---

## 12. ACTIVATION/RECOVERY

Reutilizar `PasswordRecoveryService`.

Não criar segunda autoridade de senha.

Regras:

- raw token nunca em log;
- raw token nunca em audit;
- token one-time;
- TTL;
- replay falha;
- reset revoga sessões antigas;
- delivery externo por porta injetada;
- delivery failure é retryable sem duplicar usuário;
- request público não enumera contas;
- activation delivery readiness participa do purchase gate.

---

## 13. TRIAL

Trial é fluxo separado e permanece desativado até implementação/certificação.

Target:

```text
trial request
 -> canonical trial subscription
 -> organization + OWNER
 -> activation
 -> entitlement temporário
 -> expiry
 -> conversion or suspension
```

Trial não é inferido apenas de `trial_days`.

---

## 14. ADAPTERS DE CANAL

### Cakto

Preservar adapter atual e reposicioná-lo como canal/financial-event adapter.

Reutilizar:

- HMAC/auth;
- inbox;
- dedup;
- retry/dead-letter;
- reconciliation;
- external product/offer mapping.

Modificar somente o necessário para emitir fatos canônicos.

### Hotmart

Implementar somente quando escolhido como canal real.

Antes:

- estudar documentação oficial atual;
- definir autenticação/webhook;
- mapear product/offer/subscription events;
- criar adapter isolado;
- contract tests;
- sandbox/controlled validation quando disponível.

### Kax/outros

Mesmo padrão.

Não implementar providers especulativos sem decisão comercial.

---

## 15. OBSERVABILIDADE

Obrigatório instrumentar sem vazar dados.

Métricas mínimas:

- events received;
- signature failures;
- duplicates;
- processing latency;
- canonical sale transitions;
- claim pending;
- provisioning success/failure;
- activation delivery success/failure;
- dead-letter count;
- subscription state transitions;
- refund/chargeback transitions.

Logs:

- structured;
- correlation ID;
- provider ID;
- canonical internal reference;
- sem secrets;
- sem raw tokens;
- PII minimizada/redigida.

Alertas:

- webhook authentication spike;
- processing backlog;
- dead-letter growth;
- provisioning failures;
- activation delivery failure rate;
- reconciliation drift;
- canonical/provider state mismatch.

---

## 16. MIGRATIONS E PERSISTÊNCIA

Toda mudança de schema:

- migration forward explícita;
- fresh database test;
- upgrade test;
- idempotency;
- backward compatibility de rollout;
- PostgreSQL;
- backup/restore;
- restored DB readiness.

Não alterar silenciosamente schema version já certificado.

---

## 17. TEST MATRIX

### Backend

- Ruff;
- Mypy;
- unit;
- integration;
- domain;
- application;
- persistence;
- migrations;
- PostgreSQL;
- auth;
- RBAC;
- tenant;
- unit;
- commercial;
- webhook;
- idempotency;
- ordering;
- concurrency;
- recovery.

### Frontend/Site/Portal

- lint;
- typecheck;
- unit;
- contract tests;
- build;
- Playwright/E2E;
- accessibility;
- responsive.

### Security

- secret scan;
- dependency audit;
- container vulnerability;
- SBOM;
- non-root;
- CSRF;
- cookie/session;
- rate limits;
- webhook forgery;
- tenant spoofing;
- PII redaction;
- secret/log leakage;
- activation replay.

### Runtime

- Docker;
- Compose;
- API smoke;
- worker smoke;
- portal smoke;
- health/readiness;
- backup/restore;
- restored DB readiness.

Nunca remover teste válido para obter CI verde.

---

## 18. EXECUTION FLOW

Para cada sub-bloco:

```text
AUDIT CURRENT
 -> DESIGN/ADR
 -> IMPACT MAP
 -> IMPLEMENT
 -> LOCAL/FOCUSED TESTS
 -> FULL MATRIX
 -> PR
 -> REMOTE CI
 -> EVIDENCE
 -> CERTIFICATION
 -> MERGE ONLY WHEN AUTHORIZED
 -> POST-MERGE CURRENT CHECK
 -> NEXT BLOCK
```

Preferir mudanças pequenas, reversíveis, auditáveis e testáveis.

---

## 19. STOP CONDITIONS

Parar para decisão humana quando houver:

- mudança de autoridade;
- nova coleta significativa de PII;
- alteração de retenção;
- requisito jurídico/LGPD;
- novo provider real;
- credencial real;
- ação de deploy;
- DNS;
- produção;
- migration produtiva;
- homologação externa;
- irreversibilidade;
- risco de vazamento;
- conflito arquitetural.

---

## 20. DEFINITION OF DONE DA CADEIA COMERCIAL

Só considerar a cadeia comercial internamente pronta quando houver evidência de:

1. venda válida de um canal autenticado;
2. normalização para fato canônico;
3. purchase/subscription durável;
4. entitlement canônico;
5. claim/identity segura;
6. organização canônica;
7. OWNER;
8. activation delivery;
9. login;
10. onboarding;
11. renewal;
12. late/grace;
13. cancel;
14. refund;
15. chargeback;
16. retries/replay;
17. cross-tenant isolation;
18. provider isolation;
19. PII/secrets protection;
20. observability;
21. backup/restore;
22. full CI verde.

Mesmo assim, não declarar Comercial Live sem:

- canal real configurado;
- staging real;
- delivery real;
- legal/LGPD review quando aplicável;
- fiscal homologation necessária;
- human Go/No-Go;
- production promotion autorizada.

---

## 21. RESULTADO ESPERADO

Ao final, o mesmo NFCore deve poder ser vendido por múltiplos canais sem reconstrução:

```text
Cakto   Hotmart   Site FM   Kax   B2B   Future
  \       |        |        |     |      /
           Channel Adapters
                  ↓
          Canonical Sale Facts
                  ↓
       NFCore Commercial Fulfillment
                  ↓
     Subscription / Entitlement
                  ↓
         Claim / Organization
                  ↓
               OWNER
                  ↓
             Activation
                  ↓
               NFCore
```

Com segurança, isolamento, auditabilidade e autoridade canônica preservados.
