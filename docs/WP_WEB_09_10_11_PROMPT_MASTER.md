# PROMPT MESTRE — WP-WEB-09 + preparação técnica WP-WEB-10 e WP-WEB-11

Status: **EXECUTION CONTRACT — INTERNAL WORK MAY PROCEED; EXTERNAL PROVISIONING MUST REMAIN EXPLICITLY BLOCKED**

## 0. Baseline e autoridade

Repositório canônico: `faabio3131/kordena-fiscal-engine-v2`.

Baseline obrigatória: `main` após o merge certificado do WP-WEB-08 (PR #38).

Branch de trabalho: `feat/nfcore-web-09-cicd-staging`.

A ordem oficial permanece:

`WP-WEB-08 -> WP-WEB-09 -> WP-WEB-10 -> WP-WEB-11 -> WP-WEB-12`.

Nenhum bloco posterior pode ser declarado concluído apenas porque sua preparação técnica foi criada.

## 1. Regras constitucionais de execução

1. Preservar todos os contratos fiscais, tenant boundaries, idempotência, sequence authority, reconciliation, secret references e fail-closed gates já certificados.
2. Não criar um segundo Core, segundo lifecycle fiscal, segundo catálogo comercial ou autoridade paralela.
3. Não inserir credencial, certificado, CSC, token, senha ou segredo real no repositório, workflow, imagem, fixture, log ou artifact.
4. Não usar credenciais fictícias para declarar staging/produção reais.
5. Nenhuma migration destrutiva de produção pode ser automática.
6. Nenhum deploy de produção pode ocorrer sem aprovação humana explícita.
7. Nenhum restore/cutover de produção pode ser automatizado pelo repositório.
8. Não enfraquecer, remover, pular ou marcar como permitido qualquer teste/gate apenas para obter verde.
9. Não usar force-push/rebase destrutivo sobre histórico publicado.
10. Estados permitidos devem ser precisos: `INTERNAL_READY`, `STAGING_READY`, `BLOCKED_EXTERNAL`, `PILOT_READY`. Não declarar `100% commercial web` antes dos gates oficiais restantes.

## 2. WP-WEB-09 — CI/CD & Staging

### 2.1 Objetivo

Materializar um pipeline reprodutível de build, testes, segurança, imagens, migrations governadas, deploy em staging quando a infraestrutura real existir, smoke pós-deploy, rollback e promoção manual/aprovada para produção.

### 2.2 Parte interna obrigatória e executável agora

Implementar e testar no repositório:

- CI em Pull Request e em `main`, preservando `workflow_dispatch`;
- Ruff, Mypy e Pytest;
- frontend lint, typecheck, tests e build;
- Playwright E2E crítico;
- validação de Docker Compose e scripts operacionais;
- build das imagens API, worker e portal;
- validação non-root e rejeição de profile produtivo inseguro;
- smoke dos containers;
- rehearsal PostgreSQL backup/restore;
- secret scanning do conteúdo versionado/configuração de pipeline sem imprimir material sensível;
- dependency/security scan para Python e Node com política explícita;
- container image scanning;
- geração de SBOM para imagens ou build artifacts quando tecnicamente adequado;
- artifacts de evidência mínimos e sem segredos;
- workflow de staging parametrizado e fail-closed quando a infraestrutura/credenciais não estiverem provisionadas;
- migrations governadas antes do rollout, com bloqueio de operação destrutiva não aprovada;
- smoke tests pós-deploy contra URL de staging configurada externamente;
- estratégia de rollback documentada e automatizável sem inventar provedor;
- produção apenas por promoção manual/aprovada, nunca por push comum;
- documentação de runbook e closure matrix do WP-WEB-09.

### 2.3 Deploy de staging: contrato, não ficção

O pipeline deve separar duas situações:

**Sem infraestrutura/credenciais reais:**
- validar toda a lógica interna;
- encerrar o estágio externo como `BLOCKED_EXTERNAL` ou `SKIPPED_NOT_PROVISIONED`, sem falha falsa e sem sucesso falso;
- explicar exatamente quais inputs externos faltam.

**Com infraestrutura/credenciais reais:**
- autenticar por mecanismo seguro/efêmero quando o provedor permitir;
- executar migration governada;
- implantar componentes;
- aguardar health/readiness;
- executar smoke pós-deploy;
- registrar versão/commit implantado;
- falhar e acionar rollback quando o gate pós-deploy falhar.

Não escolher unilateralmente AWS, GCP, Azure, Fly.io, Render, Railway, Vercel ou outro provedor como decisão arquitetural definitiva. A implementação deve preservar portabilidade e usar um adapter/contrato claro para o deploy real.

### 2.4 Gate de encerramento interno do WP-WEB-09

Antes de abrir PR de encerramento:

- branch atualizada a partir de `main` sem regressão;
- Ruff PASS;
- Mypy PASS;
- Pytest PASS;
- frontend lint PASS;
- frontend typecheck PASS;
- frontend tests PASS;
- frontend build PASS;
- Playwright E2E PASS;
- recovery rehearsal PASS;
- security/dependency scans PASS conforme política documentada;
- image scan PASS conforme política documentada;
- nenhuma credencial real presente;
- pipeline de staging testado em modo fail-closed sem provisioning;
- smoke pós-deploy testável por contrato;
- produção protegida por aprovação/manual gate;
- documentação reconciliada;
- PR somente após HEAD final 100% verde.

A conclusão externa de staging somente poderá ser `STAGING_READY` depois de existir infraestrutura real e um deploy real bem-sucedido. Antes disso, use `INTERNAL_READY / BLOCKED_EXTERNAL`.

## 3. Preparação técnica WP-WEB-10 — Domain, TLS & Production Provisioning

### 3.1 Pode ser preparado agora

Criar apenas fundações independentes do provedor:

- contrato de hostname público por ambiente;
- HTTPS obrigatório em staging/produção;
- redirect seguro HTTP->HTTPS quando a borda escolhida exigir;
- configuração de trusted proxy/forwarded headers sem aceitar spoofing irrestrito;
- CORS por allowlist explícita;
- CSP e headers de segurança adequados ao portal;
- rate-limit/WAF integration points;
- health/readiness separados da exposição pública;
- checklist de DNS, TLS, certificate rotation, ingress/CDN/reverse proxy;
- runbook de cutover e rollback de DNS;
- validações automatizadas que rejeitem wildcard permissivo ou profile inseguro em produção.

### 3.2 Bloqueios externos obrigatórios

Não executar nem declarar concluído sem:

- domínio/hostname oficial escolhido;
- acesso ao DNS;
- conta/infraestrutura cloud ou hosting real;
- estratégia TLS/certificado real;
- endpoint de produção real.

Estado enquanto faltar qualquer item acima: `BLOCKED_EXTERNAL`.

## 4. Preparação técnica WP-WEB-11 — Cakto Commercial Activation

### 4.1 Pode ser preparado agora

Criar arquitetura e testes sem segredo real:

- port/interface para gateway comercial Cakto;
- modelo canônico de evento comercial separado da autoridade fiscal;
- tabela/configuração de mapping `produto/plano Cakto -> pricing catalog`;
- webhook endpoint isolado, autenticado, replay-safe e idempotente;
- deduplicação por identificador de evento;
- persistência/audit de eventos permitidos sem armazenar segredo bruto;
- estados de assinatura e transições governadas;
- provisioning de tenant somente após evento comercial confirmado e validado;
- suspensão/reativação governadas;
- reconciliador para inconsistência entre estado comercial externo e estado interno;
- testes negativos de assinatura inválida, replay, evento fora de ordem, produto desconhecido e tentativa cross-tenant;
- fixtures completamente sintéticas;
- documentação de configuração e rotação de secret reference.

### 4.2 Não pode ser ativado agora sem intervenção externa

- conta Cakto real;
- credenciais/API key reais, se aplicável;
- segredo real de webhook;
- IDs reais de produtos/planos/ofertas;
- decisão comercial final de preços/provisioning;
- endpoint público HTTPS acessível para callbacks reais.

Enquanto esses itens não existirem, o WP-WEB-11 permanece **preparado internamente, mas não comercialmente ativado**.

## 5. Sequência de execução obrigatória deste prompt

### Fase A — pré-flight

1. Confirmar branch e SHA de `main` após PR #38.
2. Confirmar que a branch `feat/nfcore-web-09-cicd-staging` nasceu dessa `main`.
3. Inventariar `.github/workflows`, Dockerfiles, Compose, migrations, runtime profiles, scripts de recovery e documentação.
4. Não alterar código até fechar o inventário e identificar gaps reais.

### Fase B — implementação interna WP-WEB-09

Implementar em pequenos commits coerentes, sempre preservando o gate existente. Após cada mudança estrutural, reexecutar os checks afetados.

### Fase C — preparação técnica WP-WEB-10

Somente depois do pipeline interno do WP-WEB-09 estar estável. Implementar contratos/configuração/testes independentes do domínio/provedor real. Não provisionar nada externo.

### Fase D — preparação técnica WP-WEB-11

Somente depois da preparação do WP-WEB-10 não ter criado regressão. Implementar boundaries, modelos, webhook sintético e testes, sem credenciais reais e sem ativação comercial fictícia.

### Fase E — certificação

Executar a matriz final completa. Se qualquer gate falhar, corrigir a causa raiz e repetir a matriz completa. Não abrir PR de fechamento com gate vermelho.

A documentação final deve separar claramente:

- `DONE_INTERNAL`;
- `BLOCKED_EXTERNAL`;
- evidências de testes;
- inputs que Fabio precisará fornecer no futuro;
- o que ainda é proibido declarar como produção.

## 6. Critério de parada e escalonamento humano

Parar e solicitar intervenção humana apenas quando uma etapa realmente exigir uma decisão ou recurso externo, como:

- escolha/conta do provedor cloud/hosting;
- domínio/DNS;
- credenciais de staging/produção;
- segredo/conta Cakto;
- decisão comercial irreversível;
- promoção/deploy real de produção;
- operação destrutiva ou cutover real.

Não solicitar ao usuário ações manuais que possam ser concluídas com segurança apenas no repositório.

## 7. Resultado esperado desta rodada

1. WP-WEB-09 com toda a fundação interna de CI/CD implementada, testada e certificada.
2. Staging real explicitamente `BLOCKED_EXTERNAL` até existir infraestrutura/credenciais, sem maquiar o estado.
3. WP-WEB-10 preparado tecnicamente até o limite anterior a domínio/DNS/TLS/infra real.
4. WP-WEB-11 preparado tecnicamente até o limite anterior à conta/credenciais/IDs reais da Cakto.
5. Nenhuma regressão nos contratos fiscais certificados.
6. Próximo ponto de intervenção humana documentado de forma objetiva.
