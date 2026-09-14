# FM Fiscal Core V2 — Auditoria Geral após V2-17.2

Data: 2026-09-13  
Escopo: Plano Mestre × código × testes × PRs × CI × integrações × convergência  
Base V2-17: `v2/fm-products-integration@6998d5a4b7370621160e2520bbadabafca86bda0`

## 1. Sumário executivo

O FM Fiscal Core V2 evoluiu do clone certificado do baseline legado FISC-00..FISC-19 para um Core fiscal host-neutral, multiproduto, persistente, event-driven, governado por capabilities/readiness, com Control Plane, adapters provider-neutral, Vault/Signer boundaries, observabilidade/compliance, hardening, integração multiproduto e contratos preparatórios de convergência.

O estado técnico atual após V2-17.2 é:

- **V2-00..V2-14: internamente CONCLUÍDAS/CERTIFICADAS**;
- **V2-15: BLOQUEADA PARCIAL — interno certificado, homologação/evidência externa oficial pendente**;
- **V2-16: BLOQUEADA PARCIAL — todo trabalho interno executável B1-B7 certificado, com bloqueios reais de produto documentados**;
- **V2-17.1: CONCLUÍDA/CERTIFICADA INTERNAMENTE como preparação de convergência**;
- **V2-17.2: CONCLUÍDA/CERTIFICADA INTERNAMENTE em rehearsal sintético**;
- **cutover real: NÃO AUTORIZADO e NÃO PRONTO**;
- **V2-17.3: NÃO INICIADA**;
- **V2-18: NÃO INICIADA**.

O gate mais recente certificado antes da documentação desta auditoria é V2-17.2, SHA `ba979defe16102fc2163f14a6612eac1516bcaf6`, run `34785613970`, job `103800433451`: Install/Ruff PASS, Mypy PASS em **117 source files** e Pytest **660 PASS em 13.20s**.

## 2. Plano Mestre × realidade — fase a fase

| Fase | Objetivo do Plano Mestre | Resultado real | Evidência final conhecida | Status / pendência |
|---|---|---|---|---|
| V2-00 | Clone técnico + equivalência | baseline `b336def...` importado com src/tests equivalentes | 45 source / 215 PASS | CONCLUÍDO |
| V2-01 | Identidade FM Fiscal + neutralização Kordena | produto independente; namespace legado preservado por compatibilidade | 45 / 215 | CONCLUÍDO |
| V2-02 | Host Namespace + Fiscal Account Binding | partição host+account+unit+environment; spoofing cross-host fail-closed | 46 / 239 | CONCLUÍDO |
| V2-03 | Fiscal Operation Contract genérico | operações sale/membership/subscription/service/recurring/SaaS neutras | 47 / 262 | CONCLUÍDO |
| V2-04 | FM Fiscal Bridge público | OpenAPI/JSON Schema/AsyncAPI language-neutral, erro/headers/idempotência | 47 / 269 | CONCLUÍDO |
| V2-05 | S2S + workload identity | caller identity, grants, binding, webhook HMAC, rate-limit/audit | 48 / 290 | CONCLUÍDO |
| V2-06 | Capability & Readiness API | ações/readiness/jurisdição/ambiente fail-closed | 49 / 305 | CONCLUÍDO |
| V2-07 | Application + persistência durável | UoW/repositories/SQLite reference, lifecycle/restart/recovery | 59 / 309 | CONCLUÍDO; datastore distribuído é decisão/runtime posterior |
| V2-08 | Events/Webhooks/Inbox/Outbox | inbox/outbox duráveis, signed webhook, retry/DLQ/ordering/audit | 67 / 337 | CONCLUÍDO |
| V2-09 | Modularização vertical | restaurant explícito; service/fitness/SaaS neutros; registry extensível | 71 / 346 | CONCLUÍDO |
| V2-10 | Product Contract Packs | Kordena/Iron/Vendedor/CampaIA, 4 hosts/9 use cases, cross-host | 78 / 397 | CONCLUÍDO |
| V2-11 | Control Plane | onboarding/perfis/capability/operational state/RBAC/audit | 85 / 437 | CONCLUÍDO |
| V2-12 | Gateway/Signer/Vault adapters | Vault/KMS boundary, signer, providers, resilience, homologation gates | 97 / 508 | CONCLUÍDO internamente; credenciais reais continuam externas |
| V2-13 | Observabilidade + Compliance | sanitização, metrics, tracing, alerts, watcher governado | 103 / 563 | CONCLUÍDO |
| V2-14 | Hardening sistêmico | chaos, concurrency, security, load/backpressure, recovery | 103 / 582 | CONCLUÍDO |
| V2-15 | Homologação + pilotos | readiness/matrizes/pilotos/go-no-go internos | 111 / 620 | BLOQUEADO PARCIAL: evidência oficial externa pendente |
| V2-16 | Integração FM multiproduto | Integration Contract, Iron, Vendedor, CampaIA seam, onboarding, cross-certification | 114 / 646 | BLOQUEADO PARCIAL por Kordena/Vendedor/CampaIA, interno executável fechado |
| V2-17.1 | Convergence readiness / autoridade única | matriz fail-closed + single authority para 11 domínios | 116 / 651 | CONCLUÍDO INTERNAMENTE; cutover bloqueado |
| V2-17.2 | Migração + rollback rehearsal | inventário 20 categorias, dry-run, idempotência, restart, conflito, rollback, sequence floor | 117 / 660 | CONCLUÍDO INTERNAMENTE em dados sintéticos; migração real não executada |
| V2-18 | Produto comercial independente | fora da autorização | — | PENDENTE |

### Divergências relevantes do plano

1. O Plano Mestre original previa Multi-Product Cross-Certification como V2-16.6. A execução utilizou B6 para industrializar Adapter Contract Pack/onboarding. A divergência foi preservada e reconciliada corretamente em V2-16.7, que completou a cross-certification no estado atual.
2. V2-15 não pôde virar homologação oficial total porque não há certificados/CSC/credentials/ambientes/respostas oficiais suficientes. O resultado foi corretamente mantido parcial.
3. V2-16 não pode ser total porque produtos consumidores ainda têm pré-requisitos reais; isso não invalida o Core multiproduto interno.
4. V2-17.2 certifica o **contrato/invariantes de migração por rehearsal sintético**, não uma migração de produção nem uma prova com snapshot real autorizado.

## 3. A — INTERNO CONCLUÍDO

Está construído e certificado internamente:

- equivalência com o baseline fiscal legado `b336def...`;
- identidade independente FM Fiscal;
- domínio host-neutral e multi-host;
- binding host/tenant/unit/environment;
- contrato econômico/fiscal genérico;
- Bridge público versionado;
- segurança S2S/workload/webhook;
- capability/readiness como autoridade central;
- application service/UoW e persistência durável de referência;
- idempotency/sequence/lifecycle/reconciliation/archive/outbox/inbox;
- eventos assíncronos, webhook delivery, retry/DLQ/ordering/audit;
- verticais modulares;
- quatro Product Contract Packs e onboarding fail-closed de novos produtos;
- Control Plane;
- Vault/Signer/Provider boundaries e resilience;
- observabilidade e Compliance Operations;
- hardening de segurança/concorrência/failure/recovery/load;
- matrizes internas de homologation readiness e pilotos controlados;
- Iron Fit fiscal handoff;
- Vendedor IA confirmed-payment handoff até classificação fiscal;
- CampaIA own-billing boundary até existência de fato real de billing;
- current-state multi-product cross-certification;
- convergência fail-closed e desenho de autoridade única;
- inventário de migração, migration contract sintético, restart/idempotência/conflict/rollback rehearsal e proteção de sequence floor.

## 4. B — INTERNO AINDA PENDENTE

Depois da V2-17.2, os principais trabalhos que ainda podem existir como engenharia interna são preparatórios e **não devem ser executados nesta autorização**:

1. **V2-17.3 — Cutover Rehearsal / Authority Transfer Closure**: transformar o plano de single authority em uma orquestração/rehearsal de freeze → validate → migrate/reconcile → activate authority → rollback, ainda sem produção.
2. Criar validação/adapters de importação para o formato real de snapshot autorizado quando esse formato/dataset estiver disponível; o rehearsal atual usa contrato sintético por design.
3. Executar uma auditoria final de writers reais e dependências runtime do ambiente alvo quando houver inventário operacional autorizado; Git não identifica por si só processos implantados.
4. Revalidar full regression e migration rehearsal após a resolução do Kordena/FISC-20 e antes de pedir autorização de cutover.

Esses itens não são bugs atuais do Core; são passos de convergência que dependem parcialmente das condições operacionais seguintes.

## 5. C — EXTERNO / PRODUTO / HOMOLOGAÇÃO

### Kordena

- PR #118 permanece funcionalmente PARCIAL.
- Web Premium/FISC-20 continua pré-requisito.
- Kordena ainda não está operando sobre o V2.
- Consequência: **cutover real é proibido**.

### Vendedor IA

- autoridade de liquidação já existe: `Payment.status = CONFIRMED`;
- handoff interno está certificado;
- faltam CPF/CNPJ/endereço fiscal e autoridade/fatos suficientes para seleção segura NF-e versus NFC-e.

### CampaIA

- adapter de own-billing está certificado;
- falta no produto o fato autoritativo real de faturamento/pagamento próprio;
- media spend/orçamento de campanha não pode ser convertido em receita.

### V2-15 / homologação oficial

Continuam externos quando não provisionados:

- certificados privados;
- CSC;
- provider credentials;
- conectividade/autorização oficial;
- ambientes SEFAZ/prefeitura/provider;
- evidências oficiais por UF/município/documento/operação;
- tenants/unidades piloto reais autorizados.

Não há base documental atual para declarar qualquer provider, UF ou município **oficialmente homologado em produção**. CONTRACT_ONLY/HOMOLOGATION_READY sintético ou interno não equivale a homologação oficial.

## 6. D — APROVAÇÃO HUMANA

Exigem decisão explícita do Diretor em autorização futura:

- merge das PRs quando a estratégia de integração for definida;
- provisionamento/uso operacional de segredos reais sob mecanismo aprovado;
- promoção para `PRODUCTION_APPROVED` com evidência correspondente;
- migração de dados/estado produtivo;
- freeze de writers reais;
- ativação do V2 como autoridade fiscal exclusiva;
- cutover real;
- deploy/endpoint/DNS produtivo quando aplicável;
- rollback operacional real;
- arquivamento/read-only/desativação do motor legado depois de cutover bem-sucedido;
- início da V2-18.

## 7. Auditoria arquitetural total

### Core host-neutral

**VERDE INTERNO.** Desde V2-02/V2-03, host namespace é parte da partição fiscal e operação deixou de pressupor venda. V2-10/V2-16 reforçam que packs/adapters não importam domínio privado de outro SaaS.

### Bridge / contracts

**VERDE INTERNO.** OpenAPI/JSON Schema/AsyncAPI públicos e versionados; headers de host/scope/correlation/causation/idempotency; Integration Contract atual exige readiness antes de mutação.

### Product Contract Packs / adapters

**VERDE NO CORE.** Quatro packs certificados e caminho de onboarding de futuros produtos fail-closed. Runtime de todos os produtos consumidores ainda não está completo pelos bloqueios explicitados.

### Control Plane / capability / readiness

**VERDE INTERNO.** Capability/Readiness permanece autoridade; Contract Pack e migration não promovem readiness. `PRODUCTION_APPROVED` não é derivado silenciosamente.

### Gateway / Signer / Vault / providers

**VERDE COMO ARQUITETURA/ADAPTER INTERNO.** Secret resolution provider-scoped e reference-only. Operação real depende de material externo e ambientes oficiais.

### Persistence / migrations / archive / reconciliation

**VERDE INTERNO até os limites certificados.** Persistência durável de referência, migrations controladas históricas, restart/recovery e reconciliation estão testados. V2-17.2 adicionou contrato sintético de convergência, não migration de produção.

### Outbox / inbox / webhooks / async

**VERDE INTERNO.** Dedup/retry/DLQ/audit/ordering governados, webhook signed e consumer idempotente certificados.

### Observability / compliance

**VERDE INTERNO.** Logs sanitizados, métricas, tracing, alerts e watcher sem promoção automática. Nenhum raw secret/payload deve virar telemetria.

### Security / S2S / RBAC / secrets

**VERDE INTERNO nas superfícies certificadas.** Autorização e isolamento fail-closed; nenhum segredo real no Git. Material operacional real ainda depende do processo externo de provisioning.

### Concurrency / performance / recovery

**VERDE NO BASELINE TÉCNICO MEDIDO.** V2-14 certificou concorrência/idempotência, failure injection, load/backpressure e recovery. Nenhuma capacidade comercial foi inventada a partir desses testes.

### Authority duplication

Não foi encontrada duplicação de authority dentro do V2: Capability/Readiness, lifecycle, sequence, idempotency etc. possuem limites definidos. **O risco de dual authority entre legado e V2 é operacional/futuro**, pois writers reais ainda não foram congelados. V2-17.1 torna esse estado inválido após cutover por construção.

## 8. Auditoria de testes e CI

Evolução dos gates principais:

- V2-00: 45 source / 215 PASS;
- V2-02: 46 / 239;
- V2-04: 47 / 269;
- V2-06: 49 / 305;
- V2-08: 67 / 337;
- V2-10: 78 / 397;
- V2-12: 97 / 508;
- V2-13: 103 / 563;
- V2-14: 103 / 582;
- V2-15: 111 / 620;
- V2-16.7: 114 / 646;
- V2-17.1: 116 / 651;
- V2-17.2: **117 / 660**.

Cobertura qualitativa existente inclui:

- contract tests;
- negative/fail-closed tests;
- cross-host/cross-tenant/cross-unit;
- security/webhook/auth;
- idempotency/sequence;
- concurrency/race;
- fault injection;
- persistence/restart/recovery;
- outbox/inbox/retry/DLQ;
- cross-provider;
- load/backpressure baseline;
- archive/reconciliation;
- cross-product;
- convergence readiness;
- migration dry-run/idempotency/interruption/conflict/rollback/sequence floor.

### Falhas intermediárias relevantes

Os vermelhos observados foram preservados e corrigidos, não mascarados. Exemplos: import ordering/E501 em várias fases; dependency audit do Iron corrigido via versão segura do `multer`; V2-16 B6 Ruff corrigido sem relaxar asserts; V2-17.2 primeiro gate `34785562237` falhou em 20 E501 e foi recertificado no run `34785613970`.

### Gap de teste relevante atual

Ainda não existe teste de **migração sobre snapshot real/autorizado de produção** nem rehearsal operacional com writers reais, por proibição e ausência de pré-condições. Isso é deliberadamente diferente do rehearsal sintético já verde.

## 9. Auditoria das integrações FM

| Produto | Contrato/Core | Authority comercial | Integração interna | Readiness / bloqueio | Próximo passo |
|---|---|---|---|---|---|
| Kordena | pack `fm.kordena` | domínio existente, mas FISC-20 depende Web Premium | runtime V2 ainda não integrado | BLOQUEADO_PRODUCT | concluir/liberar Web Premium/FISC-20 e integrar Kordena ao V2 |
| Iron Fit | pack `fm.iron` | `FinancialService.payCharge` / Charge paga | certificado | readiness fiscal continua Core | manter Draft até estratégia de merge/cutover |
| Vendedor IA | pack `fm.vendedor-ia` | `Payment.status=CONFIRMED` | handoff certificado | faltam recipient fiscal data/classificação NF-e/NFC-e | completar dados/fatos fiscais no produto |
| CampaIA | pack `fm.campaia` | ainda inexistente para own billing | boundary certificado | falta authoritative billing/payment fact | implementar domínio real de billing próprio |
| futuros | onboarding/Contract Pack | deve ser declarado explicitamente | caminho certificado | fail-closed até binding/capability/readiness | usar template de onboarding sem alterar Core privado |

## 10. Auditoria de homologação

Manter quatro conceitos separados:

1. **certificação interna** — código/testes/CI verdes;
2. **homologação sintética/interna** — cenários e matrizes sem autoridade oficial;
3. **homologação oficial externa** — exige resposta/evidência oficial por provider/jurisdição/documento/operação;
4. **produção** — exige `PRODUCTION_APPROVED`, credenciais/ambiente e autorização humana.

No estado atual, não há evidência suficiente para promover provider/UF/município a homologado oficial ou produção. As matrizes internas NF-e/NFC-e/NFS-e são importantes e verdes, mas não substituem a autoridade externa.

## 11. Auditoria de convergência — respostas objetivas

1. **O V2 já reproduz e supera funcionalmente o antigo Core?**  
   **Sim, internamente, em relação ao baseline certificado `b336def...`**, com equivalência inicial e evolução acumulada. Isso não equivale a provar o comportamento de um runtime produtivo não inspecionado.

2. **O Core universal está arquiteturalmente independente?**  
   **Sim, internamente certificado.** O domínio é host-neutral e integra produtos por contratos/packs.

3. **O multiproduto está tecnicamente certificado?**  
   **Sim no Core/contratos/cross-certification.** A conclusão runtime dos consumidores é parcial: Iron verde; Kordena/Vendedor/CampaIA possuem bloqueios reais distintos.

4. **Há alguma regra fiscal válida somente no sistema antigo?**  
   **Não há evidência disso no baseline autoritativo do repositório.** A V2-00 clonou `b336def...` e a branch FISC-19 legado permanece nesse mesmo SHA. O `main` legado é placeholder e não é baseline. Isso não autoriza inferir o estado de um runtime implantado externamente.

5. **Há algum writer fiscal que continuaria concorrendo com o V2?**  
   **Potencialmente sim até o cutover**, porque nenhum writer real foi desativado nesta autorização. A identidade dos writers operacionais deve ser inventariada antes da janela real. O plano V2-17.1 proíbe dual-write após cutover.

6. **A migração está definida?**  
   **Sim como contrato/inventário governado de V2-17.2.**

7. **A migração foi testada?**  
   **Sim sinteticamente em CI; não em dados produtivos reais.**

8. **O rollback está definido?**  
   **Sim como runbook preparatório e invariantes.**

9. **O rollback foi ensaiado?**  
   **Sim no rehearsal sintético do ledger; não operacionalmente em produção.**

10. **O Kordena já pode operar no V2?**  
    **Não.** PR #118/Web Premium/FISC-20 permanece bloqueio obrigatório.

11. **Quais pré-condições impedem cutover real?**  
    Kordena operando no V2; evidência operacional/homologação oficial necessária; snapshot/formato real autorizado e rehearsal correspondente; inventário/freeze de writers reais; reconciliação de pending state/unknown outcomes; full regression no estado final; aprovação humana explícita.

12. **O que falta antes da autorização final de cutover?**  
    Resolver os bloqueios acima, executar o próximo rehearsal de authority transfer com dados/ambiente autorizados, confirmar rollback operacional e apresentar um Go/No-Go final ao Diretor. Só então uma autorização específica poderá permitir migração/cutover reais.

## 12. Próximos blocos recomendados — NÃO EXECUTAR NESTA JANELA

### Prioridade 1 — pré-requisitos paralelos

- finalizar Web Premium/FISC-20 e integrar Kordena ao V2;
- resolver recipient/classificação do Vendedor IA;
- criar billing authority real da CampaIA;
- obter/provisionar de forma segura evidências, certificados/CSC/credentials e ambientes oficiais necessários para os providers/jurisdições alvo.

### Prioridade 2 — próximo bloco do Core

**V2-17.3 — Cutover Rehearsal / Authority Transfer Closure**, somente em nova autorização.

Escopo recomendado:

- inventário de writers reais;
- snapshot autorizado/representativo no formato real;
- dry-run do adapter de migração;
- freeze simulation;
- migration/reconciliation simulation;
- authority activation simulation;
- rollback operacional simulado;
- final Go/No-Go matrix;
- full regression final;
- nenhum cutover real sem autorização posterior específica.

### Prioridade 3 — depois da convergência real

V2-18 — produto comercial independente: identidade comercial, portal/documentação, onboarding self-service, plans/entitlements/billing, SLA/support, SDKs, termos/LGPD/retenção e experiência premium.

## 13. Decisão da auditoria

**A — INTERNO CONCLUÍDO:** arquitetura universal, Core/Bridge, segurança, persistence/events, Control Plane, adapters, observabilidade/hardening, certificação interna V2-15, integração multiproduto executável, V2-16 closure, V2-17.1 e V2-17.2 sintéticas.

**B — INTERNO AINDA PENDENTE:** próximo rehearsal/orquestração V2-17.3 e validações finais condicionadas ao ambiente/dataset autorizado.

**C — EXTERNO/PRODUTO/HOMOLOGAÇÃO:** Kordena FISC-20, gaps de Vendedor/CampaIA, credenciais/certificados/CSC/ambientes/evidências oficiais.

**D — APROVAÇÃO HUMANA:** merge/deploy/produção/migração/freeze/cutover/rollback operacional/archive legado/PRODUCTION_APPROVED/V2-18.

**Próxima autorização recomendada:** não é cutover real. Deve ser uma autorização para **V2-17.3 — Cutover Rehearsal / Authority Transfer Closure**, idealmente depois de o Kordena/FISC-20 e os requisitos operacionais mínimos estarem liberados.
