# FM FISCAL CORE V2 — PLANO MESTRE DE EXECUÇÃO

Status: **ATIVO**  
Data de abertura: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Origem certificada: `faabio3131/kordena-fiscal-engine` @ `b336def47ad4f5188307102203f4e04b98406014`

## 1. Missão

Evoluir a base fiscal já certificada em um único produto fiscal independente da FM Tecnologia, multiproduto e reutilizável por Kordena, Iron Fit, Vendedor IA, CampaIA e produtos futuros, preservando integralmente os comportamentos fiscais válidos do baseline original.

A estratégia é um **fork transitório controlado**. O repositório original permanece congelado como baseline seguro durante a construção. O V2 só substitui o original depois de equivalência, universalização, integração e certificação. Após o cutover, o original permanece arquivado para auditoria e histórico, mas deixa de ser arquitetura ativa.

## 2. Princípios vinculantes

1. **Equivalência antes de evolução.** O V2 deve primeiro reproduzir o baseline FISC-00..FISC-19 sem regressão.
2. **Uma única verdade fiscal futura.** O fork é temporário; não haverá dois motores mantidos indefinidamente.
3. **Core host-neutral.** O domínio fiscal não importa entidades de Kordena, Iron Fit, Vendedor IA, CampaIA ou qualquer SaaS.
4. **Produtos entram por contratos.** Adapters/Bridge convertem domínios externos em contratos fiscais canônicos.
5. **Sem compartilhamento de banco entre produtos.** Integrações remotas usam API/eventos versionados.
6. **Fail-closed.** Identidade, tenant/unidade, capabilities, credenciais, perfil fiscal e autorização não podem ser inferidos silenciosamente.
7. **Idempotência ponta a ponta.** Retries, webhooks, outbox, emissão e reconciliação devem tolerar repetição sem duplicidade.
8. **Regra fiscal determinística e versionada.** IA pode auxiliar classificação, nunca promover regra fiscal de alto impacto silenciosamente.
9. **Nenhum segredo no Git.** PFX, senha, CSC, token, credencial, dado real de cliente e endpoint privado/produtivo são proibidos.
10. **PRs Draft e gates obrigatórios.** Nenhuma fase é concluída sem evidência de código, testes, CI, revisão, SHA e riscos residuais.

## 3. Arquitetura-alvo

```text
KORDENA ------- KordenaFiscalAdapter --------\
IRON FIT ------ IronFiscalAdapter ------------\
VENDEDOR IA --- SalesFiscalAdapter ------------> FM FISCAL BRIDGE / API
CAMPAIA ------- CampaiaFiscalAdapter ---------/            |
NOVO PRODUTO -- ProductFiscalAdapter --------/              v
                                                   FM FISCAL CORE
                                                         |
                              +--------------------------+--------------------------+
                              |                          |                          |
                            NFC-e                      NF-e                       NFS-e
                              |                          |                          |
                              +-------- Gateways / Signer / Vault / Archive --------+
                                                         |
                                              Compliance / IBS-CBS-IS
```

O FM Fiscal Core é a autoridade fiscal. O Bridge é a fronteira de integração. Cada SaaS continua autoridade do próprio negócio, pagamentos, clientes e operações.

## 4. Ordem mestre de construção

### V2-00 — Clone técnico + prova de equivalência

**Objetivo:** reproduzir no V2 a árvore certificada do original e provar que nada foi perdido.

Entregas:
- importar código, testes, docs técnicos e CI do baseline `b336def...`;
- registrar manifest de origem por SHA;
- executar Ruff, Mypy strict e Pytest no clone;
- comparar inventário estrutural e superfícies públicas;
- confirmar que nenhuma alteração semântica foi introduzida na importação.

Gate: **100% equivalência ou bloqueio.**

### V2-01 — Identidade do produto e neutralização de branding

**Objetivo:** separar identidade técnica do antigo produto Kordena sem quebrar compatibilidade.

Entregas:
- nome de produto `FM Fiscal Core`;
- estratégia de namespace/package compatível;
- ADR de depreciação de nomes antigos;
- nenhuma renomeação em massa que quebre o baseline sem camada de compatibilidade.

Dependência: V2-00.

### V2-02 — Host Namespace + Fiscal Account Binding

**Objetivo:** impedir colisões entre SaaS independentes.

Entregas:
- `host_system_id` / `product_namespace` no contexto universal;
- partição real por host + tenant + unidade + ambiente;
- binding governado entre identidade externa e conta/perfil fiscal interno;
- propagação para sequence manager, idempotency, archive, outbox, reconciliation e audit;
- testes de colisão Kordena/Iron/Vendedor/CampaIA com ids locais iguais.

Gate: spoofing/cross-product deve falhar fechado.

### V2-03 — Fiscal Operation Contract genérico

**Objetivo:** remover a suposição de que toda origem fiscal é uma venda.

Entregas:
- `FiscalOperationSnapshot`/equivalente;
- operation reference, occurrence/settlement timestamps, totals e payments neutros;
- suporte a venda, mensalidade, assinatura, serviço, cobrança recorrente e faturamento SaaS;
- camada de compatibilidade para contratos `Sale/HostSettlement` existentes;
- reconciliação semanticamente neutra.

Dependência: V2-02.

### V2-04 — Contratos públicos do FM Fiscal Bridge

**Objetivo:** criar fronteira language-neutral para Python, TypeScript e stacks futuros.

Entregas:
- OpenAPI versionada;
- JSON Schemas canônicos;
- AsyncAPI/event schemas quando aplicável;
- contratos de emissão, consulta, cancelamento, inutilização, capabilities, reconciliação e archive reference;
- erro canônico independente de provedor;
- idempotency/correlation/causation headers/fields.

Gate: contratos consumíveis sem importar pacote Python ou banco interno.

### V2-05 — Segurança S2S + identidade de workload

**Objetivo:** autenticar o produto chamador e impedir falsificação de escopo.

Entregas:
- caller application identity;
- autorização por produto/capability;
- binding caller → host_system_id;
- proteção tenant/unit/profile;
- estratégia de rotação de credencial/workload identity;
- assinatura/verificação de webhooks;
- rate limiting e audit trail de caller identity.

Gate: testes negativos cross-host/cross-tenant/cross-unit 100% verdes.

### V2-06 — Capability & Readiness API

**Objetivo:** o consumidor pergunta ao Fiscal o que pode executar; nunca infere localmente.

Entregas:
- NFC-e/NF-e/NFS-e;
- UF/município/ambiente;
- emissão, consulta, cancelamento, inutilização, contingência;
- readiness `CONTRACT_ONLY`, `HOMOLOGATION_READY`, `PRODUCTION_APPROVED`;
- versionamento de capability e provenance normativa.

Dependências: V2-02, V2-04, V2-05.

### V2-07 — Serviço de aplicação e persistência durável

**Objetivo:** transformar o core de biblioteca em motor operável de forma independente sem contaminar o domínio.

Entregas:
- application service/orchestrator universal;
- interfaces de repositories/UoW;
- persistência durável de idempotency, sequence, lifecycle, outbox, bindings, archive metadata e reconciliation state;
- migrations controladas;
- nenhuma regra de negócio escondida em controller/repository.

Gate: reinício/process crash não pode causar emissão duplicada ou perda de autoridade.

### V2-08 — Eventos, Webhooks, Inbox/Outbox e processamento assíncrono

**Objetivo:** suportar emissões pending/contingência/retries e integração confiável.

Entregas:
- envelope universal versionado;
- deduplicação de inbound/outbound;
- retries/backoff/dead-letter;
- webhook delivery state;
- correlation/causation;
- reconciliação assíncrona.

Dependência: V2-07.

### V2-09 — Modularização de verticais

**Objetivo:** preservar inteligência setorial sem acoplar todos os consumidores a restaurante.

Entregas:
- restaurante como capability/vertical module;
- serviço/fitness/SaaS sem dependência de restaurant classifier;
- extensão futura por vertical sem fork do Core;
- regression suite do Kordena preservada.

### V2-10 — Product Contract Packs

**Objetivo:** provar que um único Core atende os produtos da FM.

Entregas de contrato, sem acoplar repositórios privados ao Core:
- `KordenaFiscalContractPack`;
- `IronFiscalContractPack`;
- `SalesFiscalContractPack`;
- `CampaiaFiscalContractPack`;
- fixtures sintéticas e contract tests por produto;
- matriz de documentos/eventos/capabilities por caso de uso.

Gate: nenhum adapter importa domínio de outro SaaS.

### V2-11 — Control Plane do produto independente

**Objetivo:** permitir operação autônoma do FM Fiscal.

Entregas:
- onboarding empresa/unidade;
- perfis fiscais e vigências;
- gestão de capabilities e ambientes;
- referências de certificado/CSC/credentials via Vault;
- operações, erros, contingência, archive e reconciliação;
- RBAC administrativo;
- trilha de auditoria.

A UI comercial/premium vem depois do domínio operacional certificado.

### V2-12 — Gateway/Signer/Vault production adapters

**Objetivo:** preparar operação real sem acoplar o Core a fornecedor único.

Entregas:
- provider adapters aprovados;
- signer real por referência de segredo;
- vault/KMS abstraction;
- CSC e credenciais por unidade/ambiente;
- timeout/retry/circuit breaker;
- homologation gates por documento/jurisdição.

Nenhum segredo entra em fixture ou repositório.

### V2-13 — Observabilidade + Compliance Operations

**Objetivo:** tornar o produto operável e auditável.

Entregas:
- logs estruturados sanitizados;
- métricas por host/tenant/unidade/document kind;
- tracing/correlation;
- alertas de certificado, fila, rejeição, gap de numeração e contingência;
- Regulatory Watcher governado;
- promoção de regra normativa somente com revisão/testes/aprovação.

### V2-14 — Hardening sistêmico

**Objetivo:** provar segurança e resiliência antes de consumidores reais.

Gates:
- contract tests;
- property/invariant tests onde aplicável;
- concorrência e corrida de sequence/idempotency;
- fault injection de gateway/outbox;
- replay/recovery;
- isolamento multi-tenant/multi-host;
- segurança de webhook/auth;
- load/performance baseline;
- archive integrity;
- regressão completa do baseline V1.

### V2-15 — Homologação e pilotos controlados

**Objetivo:** transformar readiness técnico em readiness operacional real.

Entregas:
- homologação por documento/jurisdição selecionada;
- evidências oficiais quando necessárias;
- runbooks;
- rollback/kill-switch;
- tenants/unidades piloto sintéticos e depois autorizados.

`PRODUCTION_APPROVED` só pode ser promovido com evidência.

### V2-16 — Integração com produtos FM

Ordem recomendada:
1. **Kordena**, somente quando V1 Web Premium estiver liberada para FISC-20;
2. **Iron Fit**, com foco inicial em NFS-e de serviços/mensalidades e operações aplicáveis;
3. **Vendedor IA**, após autoridade de pagamento/venda e dados fiscais suficientes;
4. **CampaIA**, inicialmente para faturamento próprio/serviços tributáveis modelados;
5. novos produtos via adapter contract pack.

Cada integração tem PR/gate próprio e não muda regra fiscal comum dentro do SaaS consumidor.

### V2-17 — Convergência e cutover

**Objetivo:** eliminar a duplicidade transitória.

Pré-condições obrigatórias:
- equivalência funcional comprovada;
- multiproduto certificado;
- Kordena operando no V2;
- regressão fiscal completa verde;
- migração de estado/documentos definida e testada;
- rollback documentado;
- aprovação humana explícita.

Ações:
- V2 passa a ser a única arquitetura fiscal ativa;
- original é arquivado/read-only como evidência histórica;
- nenhuma correção normativa nova deve ser aplicada apenas no original.

### V2-18 — Produto comercial independente

**Objetivo:** lapidar o FM Fiscal como produto FM Tecnologia.

Entregas futuras:
- identidade comercial;
- portal/documentação pública;
- onboarding self-service governado;
- planos/entitlements/billing;
- SLA/support;
- SDKs;
- termos, LGPD, retenção e contratos;
- experiência visual premium.

Esta fase não é pré-requisito para uso interno nos SaaS FM.

## 5. Caminho crítico

```text
V2-00 → V2-01 → V2-02 → V2-03 → V2-04 → V2-05
                                      |        |
                                      v        v
                                    V2-06    V2-07 → V2-08
                                                |
                      V2-09 → V2-10 ------------+
                                                v
                              V2-11 → V2-12 → V2-13 → V2-14 → V2-15
                                                                  |
                                                                  v
                                                               V2-16
                                                                  |
                                                                  v
                                                               V2-17
                                                                  |
                                                                  v
                                                               V2-18
```

## 6. Política de execução

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`.

Para concluir qualquer bloco é obrigatório registrar:
- branch;
- SHA de evidência;
- PR;
- CI;
- testes/gates executados;
- diff auditado;
- riscos residuais;
- decisão de avanço.

Não executar merge/deploy automaticamente. Produção, segredos, homologação oficial e cutover exigem autorização humana explícita.

## 7. Decisão de início

**V2-00 está autorizado e iniciado em 2026-09-11.**

Primeiro objetivo operacional: importar o baseline certificado `b336def47ad4f5188307102203f4e04b98406014`, registrar proveniência e atingir equivalência de testes antes de qualquer refatoração multiproduto.
