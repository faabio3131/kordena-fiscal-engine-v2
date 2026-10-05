# FM NFCORE V1 — CRONOGRAMA MESTRE DE CONCLUSÃO E CERTIFICAÇÃO

**Status:** CANONICAL EXECUTION CONTROL CANDIDATE  
**Data-base da auditoria:** 2026-10-05  
**Projeto:** NFCore Commercial Launch  
**Produto:** FM NFCORE V1  
**Repositório canônico:** faabio3131/kordena-fiscal-engine-v2  
**Branch canônica:** main  
**CURRENT auditado:** 0644901ac0816b9bf8f12c648d010418486a6483  
**CI do CURRENT:** FM NFCORE V1 CI #566 — SUCCESS  
**PRs abertas no momento da auditoria:** 0

**Objetivo:** concluir o FM NFCORE V1 de forma comprovável, sem reconstruções paralelas, fases esquecidas ou promoção indevida de código preparado para estado operacional.  
**Padrão automatizado de execução:** `docs/standards/FM_AI_MASTER_PLAN_EXECUTION_STANDARD.md` + `docs/NFCORE_V1_EXECUTION_LEDGER.md` + `scripts/check_nfcore_plan.py`.

> Este documento governa as pendências identificadas na auditoria completa de 2026-10-05. Para a execução pós-auditoria, ele prevalece sobre cronogramas históricos quando houver divergência de estado. Documentos históricos permanecem como evidência, mas não substituem o CURRENT técnico.

---

# 1. REGRA CONSTITUCIONAL DE EXECUÇÃO

A linha obrigatória é:

~~~text
AUDITORIA CURRENT
 -> DESIGN / DECISÃO
 -> IMPLEMENTAÇÃO
 -> TESTES
 -> GATES
 -> PR
 -> CI DA PR
 -> EVIDÊNCIA
 -> MERGE QUANDO AUTORIZADO
 -> CI DA MAIN
 -> DEPLOY CONTROLADO
 -> EVIDÊNCIA DE RUNTIME
 -> CERTIFICAÇÃO
 -> PRÓXIMO BLOCO
~~~

Nenhuma fase pode ser considerada concluída porque um arquivo, classe, rota, teste, harness, UI ou documento existe. Conclusão exige evidência reproduzível da camada correspondente.

---

# 2. FONTES DE VERDADE

Ordem obrigatória em cada retomada:

1. código CURRENT no Git/GitHub;
2. branch, HEAD, PRs, merges e main;
3. CI, testes, builds e evidências reproduzíveis;
4. este cronograma e NFCORE_V1_COMMERCIAL_LAUNCH_CURRENT.md;
5. ADRs, System Design e certificações anteriores;
6. documentação histórica;
7. conversa/memória somente como contexto.

Antes de qualquer alteração:

- [ ] reconfirmar main;
- [ ] reconfirmar HEAD;
- [ ] listar PRs abertas;
- [ ] validar CI do HEAD;
- [ ] verificar staging real;
- [ ] verificar drift main x ambientes;
- [ ] identificar a autoridade canônica;
- [ ] declarar CURRENT -> TARGET;
- [ ] congelar escopo;
- [ ] definir mapa de impacto;
- [ ] definir critérios de aceite;
- [ ] definir testes;
- [ ] registrar ações proibidas no bloco.

---

# 3. VOCABULÁRIO DE STATUS — USO OBRIGATÓRIO

| Status | Significado |
|---|---|
| NOT_STARTED | trabalho ainda não iniciado |
| READY_TO_START | predecessores certificados |
| IN_PROGRESS | implementação/teste em andamento |
| BLOCKED_INTERNAL | depende de correção ou decisão técnica interna |
| BLOCKED_EXTERNAL | depende de terceiro, credencial, homologação, conta, DNS, certificado ou provider |
| IMPLEMENTED_NOT_INTEGRATED | código existe, mas não está ligado à linha operacional canônica |
| INTEGRATED_NOT_DEPLOYED | integração está na main, mas não no ambiente-alvo |
| DEPLOYED_NOT_CERTIFIED | implantado sem matriz de evidência concluída |
| DONE_CERTIFIED | critérios de aceite, testes, CI, evidência e integração concluídos |

É proibido usar “pronto”, “100%”, “finalizado”, “homologado”, “produção” ou “live” sem classificação e evidência.

---

# 4. CURRENT CONFIRMADO NA AUDITORIA DE 2026-10-05

## 4.1 Repositório e qualidade

- main: 0644901ac0816b9bf8f12c648d010418486a6483;
- PRs abertas: 0;
- CI #566: SUCCESS;
- Ruff: PASS;
- Mypy: 0 issues em 178 source files;
- Pytest: 1099 PASS / 0 FAIL;
- frontend tests: 11;
- Playwright: 7 PASS;
- secret scan: PASS;
- Python dependency audit: sem vulnerabilidades conhecidas;
- Node dependency audit: 0 vulnerabilidades;
- containers API/Worker/Portal: build PASS;
- imagens non-root: PASS;
- PostgreSQL backup/restore CI: PASS;
- readiness sobre DB restaurado: PASS;
- SBOM: gerado.

## 4.2 Staging real

Projeto Railway: FM NFCORE Staging.

| Componente | Revisão auditada |
|---|---|
| main CURRENT | 0644901ac0816b9bf8f12c648d010418486a6483 |
| API staging | f9b5b2c5b436045947159f1e76be9303f5a95d90 |
| Portal staging | f9b5b2c5b436045947159f1e76be9303f5a95d90 |
| Worker staging | 1c34ba001935952f83ec0b065144e0b8311a5650 |

PostgreSQL, API e Portal existem no staging. O Worker existe como serviço, mas não está comprovado como processo contínuo operacional.

Classificação:

STAGING_REAL / VERSION_DRIFT_PRESENT / NOT_CERTIFIED_AGAINST_CURRENT

## 4.3 Gaps estruturais confirmados

1. motor fiscal existe, mas o runtime oficial não injeta BridgeSecurityBoundary e BridgeRequestExecutor;
2. PortalOperationExecutor não está composto no app oficial;
3. superfícies Web estão descritas, mas várias não estão disponíveis no executor durável;
4. aquisição, trial e webhook Cakto existem, mas não estão compostos no runtime padrão;
5. worker contínuo exige handler_factory, mas o entrypoint oficial não o fornece;
6. provider fiscal real não existe; há fake/synthetic;
7. secret manager concreto não existe; há boundary provider-neutral;
8. tracing/exporters operacionais não estão ativos;
9. homologação fiscal oficial não existe;
10. produção NFCore não está comprovada;
11. canal comercial real não foi certificado;
12. documentação CURRENT histórica está parcialmente defasada.

---

# 5. REGRAS ANTI-ERRO E ANTI-ESQUECIMENTO

## 5.1 Dependência obrigatória

~~~text
P0
 ↓
P1 -> P2 -> P3 -> P4
              ↓
              P5
              ↓
      P6 + P7 + P8 + P9
              ↓
             P10
              ↓
             P11
              ↓
             P12
~~~

Fases paralelas somente podem ocorrer quando não mascaram blocker anterior.

## 5.2 Toda mudança precisa de ID

Formato obrigatório: NFV1-Pxx-Tyy.

Nenhuma pendência descoberta durante execução pode ficar somente no chat. Deve ser resolvida, registrada como tarefa, registrada como blocker ou rejeitada explicitamente com justificativa técnica.

## 5.3 Zero pendência invisível

Ao terminar cada fase, varrer:

- [ ] TODO/FIXME/HACK relevante;
- [ ] rota sem composição;
- [ ] frontend referenciando superfície indisponível;
- [ ] configuração sem runtime;
- [ ] serviço em SHA divergente;
- [ ] teste pulado relevante;
- [ ] feature flag provisória;
- [ ] mock/synthetic em caminho real;
- [ ] configuração manual não documentada;
- [ ] runbook ausente;
- [ ] evidência externa faltante;
- [ ] observabilidade ausente;
- [ ] rollback não provado.

Uma caixa [x] só pode ser marcada com evidência correspondente.

---

# 6. CRONOGRAMA MESTRE

# P0 — RECONCILIAÇÃO DE GOVERNANÇA E CURRENT

**Status inicial:** READY_TO_START

**Status certificado em 2026-10-05:** DONE_CERTIFIED

## Objetivo

Eliminar divergência documental e fixar um ponto de partida único.

## Tarefas

### NFV1-P00-T01 — Reconciliar documentação CURRENT

- atualizar NFCORE_V1_COMMERCIAL_LAUNCH_CURRENT.md;
- registrar a auditoria de 2026-10-05;
- apontar este cronograma como controle de execução;
- preservar histórico sem convertê-lo em CURRENT.

### NFV1-P00-T02 — Congelar matriz de capacidades

Criar matriz:

capacidade -> domínio -> application -> infra -> persistence -> API -> auth/RBAC -> tenant/unit -> Web -> tests -> CI -> staging -> production.

### NFV1-P00-T03 — Registrar staging drift

Persistir main SHA, API SHA, Portal SHA, Worker SHA, banco/migrations, domínios e runtime status.

## Gate

- [x] documentação coincide com Git/Railway;
- [x] matriz de capacidades existe;
- [x] blockers conhecidos possuem IDs.

**Gate de saída:** CURRENT_RECONCILED_2026_10_05

---

# P1 — PRODUCTION FISCAL COMPOSITION ROOT

**Status inicial:** READY_TO_START após P0  
**Prioridade:** CRÍTICA

## Objetivo

Conectar o motor fiscal existente à aplicação Web/runtime canônica sem criar segunda API ou segundo domínio.

## CURRENT

Existem contratos de emissão, consulta, cancelamento, inutilização, reconciliação, Provider Gateway, authorization boundary, production activation authority, signing, persistence e rotas HTTP. O app padrão não injeta os executores/segurança necessários.

## TARGET

~~~text
HTTP/API/Portal
 -> authority autenticada
 -> tenant/unit scope
 -> BridgeSecurityBoundary
 -> PortalOperationExecutor / BridgeRequestExecutor
 -> application/domain fiscal existente
 -> provider registry
 -> persistence/audit
~~~

## Tarefas

### NFV1-P01-T01 — Identificar composição canônica

- localizar executores válidos;
- impedir executor paralelo;
- mapear signing/provider/vault/production authority.

### NFV1-P01-T02 — Implementar composition root

- injetar BridgeSecurityBoundary;
- injetar BridgeRequestExecutor;
- injetar PortalOperationExecutor;
- preservar fail-closed;
- não habilitar produção fiscal automaticamente.

### NFV1-P01-T03 — Certificar autoridade

Testar tenant spoofing, unit spoofing, cross-tenant, cross-unit, RBAC, sessão, S2S e idempotência.

### NFV1-P01-T04 — Certificar API fiscal

Validar emissão, consulta, cancelamento, inutilização, reconciliação e demais operações do launch scope.

## Gate

- [ ] dependências internas compostas;
- [ ] ausência de provider/secret/produção continua fail-closed;
- [ ] UI não é autoridade;
- [ ] testes unit/integration/security verdes;
- [ ] CI completo verde.

**Gate de saída:** FISCAL_RUNTIME_COMPOSED_AND_CERTIFIED_INTERNAL

---

# P2 — PORTAL FUNCTIONAL PARITY

**Status inicial:** NOT_STARTED  
**Dependência:** P1

## Objetivo

Expor no mesmo Portal as capacidades necessárias ao V1, reutilizando autoridades existentes.

## Superfícies a fechar

- Documentos;
- Emissões;
- Erros;
- Reconciliação;
- Capabilities;
- Certificados;
- Providers;
- Usuários;
- Webhooks;
- Integrações;
- Uso;
- Billing;
- Planos;
- Suporte;
- Inutilização.

## Tarefas

### NFV1-P02-T01 — Matriz frontend x backend

Para cada superfície registrar authority, endpoint, projection, mutações, RBAC, tenant/unit, estados e audit trail.

### NFV1-P02-T02 — Superfícies fiscais

Conectar documents, issuances, errors, reconciliation e capabilities.

### NFV1-P02-T03 — Configuração do cliente

Conectar certificates, providers, webhooks, integrations e settings sem expor secrets.

### NFV1-P02-T04 — Usuários e RBAC

Implementar administração baseada na autoridade humana existente e testar OWNER, ADMIN, OPERATOR, AUDITOR, BILLING e platform admin.

### NFV1-P02-T05 — Billing/Planos/Uso

Expor estado canônico, mantendo provider externo como adapter.

### NFV1-P02-T06 — Inutilização

Adicionar operação ao fluxo Web governado.

### NFV1-P02-T07 — Premium UX

Preservar identidade, mobile, acessibilidade e estados reais de bloqueio.

## Gate

- [ ] nenhum item visível aponta para superfície inexistente;
- [ ] mutações usam controles exigidos;
- [ ] RBAC e tenant/unit validados;
- [ ] Playwright cobre jornadas críticas;
- [ ] visual premium preservado;
- [ ] CI verde.

**Gate de saída:** PORTAL_COMMERCIAL_PARITY_CERTIFIED

---

# P3 — COMMERCIAL RUNTIME WIRING

**Status inicial:** NOT_STARTED  
**Dependência:** P1

## Objetivo

Conectar os componentes comerciais já construídos ao runtime real.

## Tarefas

### NFV1-P03-T01 — First-party acquisition

Compor CommercialAcquisitionService, security, rate limit, pricing, release, checkout, persistence e activation readiness.

### NFV1-P03-T02 — Trial

Compor GovernedTrialService, security, anti-abuse, rate limit, activation delivery e canonical subscription.

### NFV1-P03-T03 — Provider webhook runtime

Quando Cakto for selecionada, resolver secret por boundary governada, compor receiver, autenticar assinatura, registrar inbox, traduzir evento canônico e acionar fulfillment/provisioning/activation.

### NFV1-P03-T04 — Purchase readiness

purchase_enabled deve permanecer falso se faltar pricing, release, checkout, receiver, canonical persistence, fulfillment, provisioning ou activation delivery.

### NFV1-P03-T05 — Lifecycle comercial

Cobrir sale, activation, renewal, late payment, pause, recovery, cancel, refund e chargeback.

## Gate

- [ ] acquisition endpoint real registrado;
- [ ] trial endpoint real registrado;
- [ ] webhook somente quando configurado;
- [ ] browser nunca define pagamento/tenant/entitlement;
- [ ] replay não duplica org/OWNER/subscription;
- [ ] CI verde.

**Gate de saída:** COMMERCIAL_RUNTIME_COMPOSED_INTERNAL

---

# P4 — CONTINUOUS WORKER RUNTIME

**Status inicial:** NOT_STARTED  
**Dependência:** P3

## Objetivo

Transformar Worker de probe em processo operacional contínuo governado.

## Tarefas

### NFV1-P04-T01 — Handler registry canônico

Identificar handlers existentes, compor registry explícito e não criar fila paralela.

### NFV1-P04-T02 — Outbox/inbox/background

Provar poll/dispatch, retry, backoff, idempotência, dead-letter, shutdown, restart e replay seguro.

### NFV1-P04-T03 — Observabilidade do Worker

Medir backlog, jobs processados, falhas, retry, dead-letter e heartbeat/readiness.

### NFV1-P04-T04 — Container

Provar processo contínuo, SIGTERM, non-root e health/runtime contract.

## Gate

- [ ] Worker permanece executando sem modo oneshot;
- [ ] handler registry explícito;
- [ ] retry/dead-letter certificado;
- [ ] crash/restart testado;
- [ ] side effects idempotentes;
- [ ] CI verde.

**Gate de saída:** CONTINUOUS_WORKER_CERTIFIED_INTERNAL

---

# P5 — RECONCILIAÇÃO E CERTIFICAÇÃO DO STAGING

**Status inicial:** NOT_STARTED  
**Dependências:** P1 + P2 + P3 + P4  
**Ação externa controlada:** deploy

## Objetivo

Colocar API, Portal e Worker na mesma revisão imutável e certificar o ambiente real.

## Tarefas

### NFV1-P05-T01 — Pré-deploy

Main CI verde, SHA imutável, backup, migrations governadas, rollback baseline, secrets fora de Git e Postgres saudável.

### NFV1-P05-T02 — Deploy reconciliado

Implantar o mesmo SHA em API, Portal e Worker.

### NFV1-P05-T03 — Smoke

Liveness, readiness, login, recovery, portal bootstrap, onboarding, worker e DB.

### NFV1-P05-T04 — E2E real

Login, unidade, configuração, jornada fiscal controlada, jornadas comerciais, RBAC, isolamento e recuperação.

### NFV1-P05-T05 — Rollback rehearsal

Provar rollback sem destruir estado canônico.

## Gate

- [ ] API SHA == Portal SHA == Worker SHA == SHA certificado;
- [ ] Worker running > 0;
- [ ] E2E verde;
- [ ] rollback provado;
- [ ] evidência persistida.

**Gate de saída:** STAGING_CURRENT_SHA_E2E_CERTIFIED

---

# P6 — EXTERNAL SECRET MANAGER ADAPTER

**Status inicial:** NOT_STARTED  
**Dependência operacional:** P5

## Objetivo

Ligar ExternalSecretClient a um Secret Manager/Vault concreto sem alterar domínio.

## Tarefas

### NFV1-P06-T01 — Selecionar provider

Critérios: IAM, rotação, disponibilidade, auditoria, custo e recovery.

### NFV1-P06-T02 — Implementar adapter de infraestrutura

Nenhuma regra de domínio no adapter.

### NFV1-P06-T03 — Certificar escopo

Tenant, unidade, ambiente, provider, purpose, version e expiration.

### NFV1-P06-T04 — Rotação e falha

Testar missing, revoked, expired, permission denied, backend unavailable e rotation.

## Gate

- [ ] zero secret raw em Git/log;
- [ ] staging/production rejeitam backend inseguro;
- [ ] audit trail sem material sensível;
- [ ] provider real testado.

**Gate de saída:** EXTERNAL_SECRET_BACKEND_CERTIFIED

---

# P7 — FISCAL PROVIDER TRANSPORT REAL

**Status inicial:** NOT_STARTED  
**Dependências:** P1 + P6  
**Dependência externa:** provider/SEFAZ/prefeitura/credenciais.

## Objetivo

Implementar o primeiro transporte fiscal real reutilizável da launch matrix.

## Tarefas

### NFV1-P07-T01 — Definir launch matrix

Fixar documento, UF/município, provider, operações, homologação e produção.

### NFV1-P07-T02 — Adapter de transporte

Autenticação, timeout, request, normalization, rejection, delivery unknown, query/reconciliation e observabilidade.

### NFV1-P07-T03 — Signer/CSC/certificado

Somente referências e material efêmero.

### NFV1-P07-T04 — Contract tests

Provider real deve satisfazer contratos sem alterar Core.

## Gate

- [ ] fake/synthetic fora do caminho real;
- [ ] timeouts explícitos;
- [ ] delivery unknown reconciliável;
- [ ] credencial fora do domínio;
- [ ] launch matrix registrada.

**Gate de saída:** REAL_FISCAL_PROVIDER_ADAPTER_READY_FOR_HOMOLOGATION

---

# P8 — REAL COMMERCIAL CHANNEL VALIDATION

**Status inicial:** NOT_STARTED  
**Dependências:** P3 + P5 + P6  
**Dependência externa:** conta/KYC/provider.

## Objetivo

Executar ao menos um canal comercial real sem transferir autoridade ao provider.

## Tarefas

### NFV1-P08-T01 — Configurar provider aprovado

Se Cakto for selecionada: conta/KYC, produto, oferta, preço, webhook, secret e callback HTTPS.

### NFV1-P08-T02 — Compra controlada

~~~text
checkout
 -> pagamento controlado
 -> webhook autenticado
 -> canonical purchase
 -> subscription
 -> claim/provisioning
 -> OWNER
 -> activation
 -> login
~~~

### NFV1-P08-T03 — Lifecycle

Renewal, late, recovery, cancel, refund e chargeback quando suportados.

### NFV1-P08-T04 — Reconciliação

Detectar e corrigir drift provider x canonical state.

## Gate

- [ ] transação real evidenciada;
- [ ] no provider lock-in;
- [ ] replay seguro;
- [ ] callback HTTPS;
- [ ] secret governado;
- [ ] customer usable account entregue.

**Gate de saída:** COMMERCIAL_CHANNEL_READY

---

# P9 — OBSERVABILIDADE, BACKUP E OPERAÇÃO

**Status inicial:** NOT_STARTED  
**Dependência:** P5  
**Pode avançar em paralelo com P6-P8.**

## Objetivo

Transformar contratos internos de observabilidade e recovery em operação real.

## Tarefas

### NFV1-P09-T01 — Tracing

Ativar e provar traces de API, DB, chamadas externas e Worker.

### NFV1-P09-T02 — Métricas

HTTP/error/latency, commercial events, fulfillment, worker backlog, retries, dead-letter, provider errors, fiscal rejection, reconciliation e activation.

### NFV1-P09-T03 — Alerts

5xx, provider unavailable, queue backlog, dead-letter, certificate expiry, secret failure, DB, deployment e rejection rate.

### NFV1-P09-T04 — Backup/restore operacional

Definir e provar retenção, frequência, RPO, RTO e restore rehearsal.

### NFV1-P09-T05 — Runbooks

Deploy, rollback, DB restore, provider incident, webhook incident, secret rotation, certificate expiry, compromised credential, commercial reconciliation e fiscal unknown outcome.

## Gate

- [ ] dashboards reais;
- [ ] alerts reais;
- [ ] tracing ativo;
- [ ] backup periódico;
- [ ] restore ensaiado;
- [ ] runbooks versionados.

**Gate de saída:** OPERATIONAL_READINESS_CERTIFIED

---

# P10 — HOMOLOGAÇÃO FISCAL OFICIAL E PILOTO

**Status inicial:** BLOCKED_EXTERNAL até P7 e insumos externos  
**Dependências:** P5 + P6 + P7 + P9

## Objetivo

Converter readiness interna em evidência fiscal externa real.

## Tarefas

### NFV1-P10-T01 — Credenciais oficiais

Certificado, CSC quando aplicável, provider credential e homologation environment por célula.

### NFV1-P10-T02 — Homologação oficial

Executar exatamente as operações da launch matrix.

### NFV1-P10-T03 — Evidence ledger

Registrar célula, provider, documento, operação, jurisdição, timestamp, evidence/protocolo e resultado.

### NFV1-P10-T04 — Controlled pilot

Allowlist, kill switch, tenant/unidade, escopo, monitoramento, reconciliação e incident procedure.

## Gate

- [ ] nenhuma célula generalizada;
- [ ] evidence externa real;
- [ ] pilot autorizado;
- [ ] kill switch testado;
- [ ] reconciliação concluída;
- [ ] zero blocker crítico.

**Gate de saída:** FISCAL_LAUNCH_MATRIX_HOMOLOGATED

---

# P11 — INFRAESTRUTURA DE PRODUÇÃO

**Status inicial:** NOT_STARTED  
**Dependências:** P5 + P6 + P8 + P9 + P10  
**Requer autorização humana específica.**

## Objetivo

Provisionar produção como evolução da mesma aplicação certificada.

## Tarefas

### NFV1-P11-T01 — Environment

Projeto/environment, PostgreSQL, API, Worker, Portal, Secret Manager, IAM e network.

### NFV1-P11-T02 — DNS/TLS

Domínio oficial, TLS, redirects, allowed hosts, CORS e trusted proxy.

### NFV1-P11-T03 — Observabilidade/backup

Aplicar os mesmos padrões certificados em staging.

### NFV1-P11-T04 — Promotion readiness

Somente revisão imutável já certificada.

## Gate

- [ ] infra separada;
- [ ] credenciais separadas de staging;
- [ ] DNS/TLS correto;
- [ ] DB/backup/monitoring;
- [ ] rollback baseline;
- [ ] nenhum deploy sem aprovação final.

**Gate de saída:** PRODUCTION_INFRA_READY_FOR_PROMOTION

---

# P12 — CERTIFICAÇÃO FINAL E GO/NO-GO

**Status inicial:** NOT_STARTED  
**Dependências:** P1-P11

### NFV1-P12-T01 — Certificar prontidão funcional

Executar e provar integralmente a matriz A antes de avançar.

## A. Prontidão funcional

- [ ] emissão;
- [ ] consulta;
- [ ] cancelamento;
- [ ] inutilização;
- [ ] reconciliação;
- [ ] documentos/archive;
- [ ] onboarding;
- [ ] recovery;
- [ ] worker;
- [ ] billing/subscription.

### NFV1-P12-T02 — Certificar paridade comercial

Executar e provar integralmente a matriz B antes de avançar.

## B. Paridade comercial

- [ ] pricing;
- [ ] release;
- [ ] checkout;
- [ ] purchase;
- [ ] trial, se fizer parte do lançamento;
- [ ] activation;
- [ ] cancel/refund;
- [ ] customer portal.

### NFV1-P12-T03 — Certificar prontidão técnica de produção

Executar e provar integralmente a matriz C antes de avançar.

## C. Prontidão técnica de produção

- [ ] auth;
- [ ] RBAC;
- [ ] tenant/unit;
- [ ] migrations;
- [ ] PostgreSQL;
- [ ] secrets;
- [ ] containers;
- [ ] CI;
- [ ] security scans;
- [ ] staging certified;
- [ ] exact revision.

### NFV1-P12-T04 — Certificar prontidão operacional

Executar e provar integralmente a matriz D antes de avançar.

## D. Prontidão operacional

- [ ] observability;
- [ ] alerts;
- [ ] tracing;
- [ ] backup;
- [ ] restore;
- [ ] runbooks;
- [ ] incident response;
- [ ] rollback.

### NFV1-P12-T05 — Certificar prontidão comercial

Executar e provar integralmente a matriz E antes de avançar.

## E. Prontidão comercial

- [ ] canal real;
- [ ] domínio/TLS;
- [ ] homologação fiscal da launch matrix;
- [ ] controlled pilot;
- [ ] suporte;
- [ ] pendências legais/LGPD resolvidas ou aprovadas;
- [ ] zero blocker crítico.

### NFV1-P12-T06 — Go/No-Go humano e promoção controlada

Somente após todas as matrizes um humano pode emitir:

PRODUCTION_APPROVED

Promoção:

~~~text
exact certified revision
 -> production preflight
 -> backup
 -> migration
 -> deploy
 -> health/readiness
 -> smoke
 -> monitored acceptance
 -> rollback ready
~~~

**Estado final permitido:** COMMERCIAL_LIVE, somente após evidência pós-promoção.

---

# 7. GATES TRANSVERSAIS — BLOQUEIO AUTOMÁTICO

Qualquer ocorrência bloqueia avanço:

- CI vermelho;
- teste removido/desabilitado para obter verde;
- segredo em Git/log/artifact;
- PII indevida;
- tenant spoofing;
- unit spoofing;
- cross-tenant leak;
- UI como autoridade;
- provider como tenant authority;
- browser declarando pagamento ou entitlement;
- migration sem governança;
- falta de idempotência em mutação crítica;
- retry sem controle;
- worker sem execução real;
- synthetic/fake em caminho declarado real;
- checkout ativo sem fulfillment/activation;
- homologação sem evidência oficial;
- produção fiscal sem aprovação;
- ambiente em SHA divergente na certificação;
- backup sem restore;
- deploy sem rollback;
- blocker crítico aberto;
- decisão humana obrigatória ausente.

---

# 8. TEST MATRIX PADRÃO POR BLOCO

Quando aplicável executar:

- Ruff;
- Mypy;
- unit tests;
- integration tests;
- auth;
- RBAC;
- tenant isolation;
- unit isolation;
- idempotency;
- migrations fresh;
- migrations upgrade;
- PostgreSQL;
- frontend lint;
- frontend typecheck;
- frontend tests;
- build;
- Playwright E2E;
- Docker/container;
- non-root;
- dependency audit;
- secret scan;
- security policy;
- health;
- readiness;
- Worker;
- backup/restore;
- smoke;
- observability;
- remote CI.

É proibido remover gate válido para obter verde.

---

# 9. TEMPLATE OBRIGATÓRIO DE CHECKPOINT

~~~markdown
# CHECKPOINT — <FASE / TAREFA>

Data:
Produto: FM NFCORE V1
Repository:
Main:
Main HEAD:
Branch:
Branch HEAD:
PR:
PR status:
CI PR:
CI main:

CURRENT:
TARGET:

Mudanças:
- ...

Autoridades reutilizadas:
- ...

Arquivos alterados:
- ...

Migrations:
- ...

Testes executados:
- ...

Evidências:
- ...

Security:
- ...

Tenant/Unit:
- ...

Staging:
- ...

External dependencies:
- ...

Blockers:
- ...

Riscos:
- ...

Pendências:
- ...

Gate de saída:
- PASS / FAIL

Próxima ação:
- ...
~~~

Sem checkpoint persistente, a fase não é considerada certificada.

---

# 10. LEDGER MESTRE

| Fase | Gate | Status inicial em 2026-10-05 | Evidência |
|---|---|---|---|
| P0 | CURRENT_RECONCILED_2026_10_05 | READY_TO_START | docs + Git/Railway CURRENT |
| P1 | FISCAL_RUNTIME_COMPOSED_AND_CERTIFIED_INTERNAL | READY_TO_START após P0 | code + tests + CI |
| P2 | PORTAL_COMMERCIAL_PARITY_CERTIFIED | NOT_STARTED | Web/API/RBAC/E2E |
| P3 | COMMERCIAL_RUNTIME_COMPOSED_INTERNAL | NOT_STARTED | acquisition/trial/webhook |
| P4 | CONTINUOUS_WORKER_CERTIFIED_INTERNAL | NOT_STARTED | running worker + retry/DLQ |
| P5 | STAGING_CURRENT_SHA_E2E_CERTIFIED | NOT_STARTED | same SHA + real E2E |
| P6 | EXTERNAL_SECRET_BACKEND_CERTIFIED | NOT_STARTED | provider real |
| P7 | REAL_FISCAL_PROVIDER_ADAPTER_READY_FOR_HOMOLOGATION | NOT_STARTED | adapter real |
| P8 | COMMERCIAL_CHANNEL_READY | NOT_STARTED | transaction real |
| P9 | OPERATIONAL_READINESS_CERTIFIED | NOT_STARTED | tracing/alerts/backup/runbooks |
| P10 | FISCAL_LAUNCH_MATRIX_HOMOLOGATED | BLOCKED_EXTERNAL | official evidence + pilot |
| P11 | PRODUCTION_INFRA_READY_FOR_PROMOTION | NOT_STARTED | production infrastructure |
| P12 | COMMERCIAL_LIVE | NOT_STARTED | final DoD + human Go/No-Go |

---

# 11. DEFINITION OF DONE DO NFCORE V1

NFCore V1 somente pode ser classificado como comercialmente concluído com prova de:

- jornadas reais do cliente;
- operações fiscais do launch scope;
- auth/RBAC/tenant/unit corretos;
- Worker operacional;
- dados/migrations governados;
- Web com paridade necessária;
- visual premium;
- billing/comercial;
- canal de venda real;
- CI verde;
- staging certificado no exact SHA;
- Secret Manager/Vault real;
- provider fiscal real;
- homologação oficial necessária;
- piloto controlado;
- produção correta;
- domínio/TLS;
- backup/recovery;
- observabilidade;
- runbooks;
- zero blocker crítico;
- Go/No-Go humano final.

---

# 12. AÇÕES NÃO AUTORIZADAS POR ESTE DOCUMENTO

Este cronograma não autoriza automaticamente:

- merge em main;
- deploy em produção;
- migration produtiva;
- DNS produtivo;
- alteração irreversível;
- segredo real em Git;
- ativação fiscal de produção;
- transação paga real fora de teste controlado aprovado;
- emissão fiscal real de produção;
- PRODUCTION_APPROVED.

Autorização deve ser específica quando necessária.

---

# 13. PRÓXIMA AÇÃO CANÔNICA

Após aprovação/merge deste cronograma:

~~~text
P0 — reconciliar CURRENT documental
 -> certificar
P1 — Production Fiscal Composition Root
 -> certificar
P2/P3 — Portal Parity + Commercial Runtime
 -> certificar
P4 — Continuous Worker
 -> certificar
P5 — reconciliar staging no mesmo SHA
~~~

Nenhuma fase posterior deve ser usada para escapar de pendências de P0-P5.

---

# 14. PADRÃO AUTOMATIZADO DE EXECUÇÃO

Este cronograma é executado sob o padrão persistente:

- `docs/standards/FM_AI_MASTER_PLAN_EXECUTION_STANDARD.md`;
- `docs/NFCORE_V1_EXECUTION_LEDGER.md`;
- `scripts/check_nfcore_plan.py`;
- `.github/workflows/nfcore-plan-governance.yml`;
- `.github/PULL_REQUEST_TEMPLATE.md`;
- `AGENTS.md`.

Regras adicionais:

1. o cronograma define escopo, dependências, critérios e gates;
2. o ledger registra estado e prova de cada tarefa `NFV1-Pxx-Tyy`;
3. o validador exige que cronograma e ledger tenham exatamente os mesmos IDs e ordem;
4. tarefa concluída exige PR, CI e commit/SHA como prova;
5. uma tarefa posterior não pode ser concluída enquanto houver tarefa anterior não concluída;
6. alteração de escopo exige atualizar cronograma e ledger antes da execução;
7. Git/GitHub, CI e runtime continuam superiores à documentação para determinar CURRENT técnico;
8. conversa pode autorizar decisões, mas não substitui atualização persistente do plano.

---

# 15. PRINCÍPIO FINAL

> O NFCore não será considerado concluído por possuir muito código, documentação, testes ou infraestrutura preparada. Será concluído somente quando a mesma aplicação, na mesma linha arquitetural, estiver integrada, testada, implantada, observável, homologada, operável e comercialmente comprovada.
