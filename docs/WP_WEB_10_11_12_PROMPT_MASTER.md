# Prompt Mestre — WP-WEB-10, WP-WEB-11 e WP-WEB-12

> Uso: execução sequencial dos três próximos blocos oficiais do plano de produção web do FM NFCORE V1.0.
> Regra superior: evidência real vence intenção. Nenhum estado externo pode ser promovido sem prova verificável.

## Missão

Trabalhe no repositório `faabio3131/kordena-fiscal-engine-v2` e execute, em ordem estrita, os três próximos blocos oficiais:

1. `WP-WEB-10 — Domain, TLS & Production Provisioning`
2. `WP-WEB-11 — Cakto Commercial Activation`
3. `WP-WEB-12 — Real Fiscal Homologation & Pilot`

Antes de alterar qualquer código, leia a `main`, o plano mestre oficial e os artefatos de fechamento dos WPs anteriores. Preserve todas as invariantes fiscais, de segurança, multi-tenant, idempotência, auditoria, recuperação e governança já certificadas.

## Regras inegociáveis para os três blocos

- Execute os WPs em ordem. Não comece o próximo enquanto o anterior não estiver tecnicamente encerrado ou explicitamente classificado como `BLOCKED_EXTERNAL` com toda a preparação interna concluída e certificada.
- Use branch e PR dedicadas por bloco. Não faça alterações diretamente na `main`.
- Não faça merge com CI vermelho, teste pulado para esconder falha, lint/typecheck quebrado, vulnerabilidade crítica aberta ou evidência incompleta.
- Não reduza cobertura, não enfraqueça gates, não remova fail-closed, não desative secret scan e não contorne políticas de migrations.
- Não comite certificados, CSC, tokens, senhas, chaves privadas, credenciais de Cakto, credenciais fiscais ou qualquer segredo real.
- Não invente domínio, DNS, certificado TLS, conta cloud, WAF, webhook Cakto, assinatura Cakto, produto/plano Cakto, certificado fiscal, CSC, credencial de prefeitura/SEFAZ/provider ou resultado de homologação.
- Separe rigorosamente autoridade comercial de autoridade fiscal. Pagamento confirmado pode habilitar ciclo comercial, mas nunca autoriza sozinho emissão fiscal real ou promoção para produção fiscal.
- Preserve tenant isolation, unidade/filial, RBAC, session authority, idempotência, reconciliação, trilha de auditoria, correlação/causação e proteção contra replay.
- Toda decisão de Go/No-Go para produção real continua humana.
- Se qualquer dependência externa estiver ausente, finalize o máximo interno possível, documente o bloqueio com precisão e pare no limite correto. `BLOCKED_EXTERNAL` é resultado válido; fabricar evidência não é.

---

## WP-WEB-10 — Domain, TLS & Production Provisioning

### Objetivo

Fechar a fronteira de produção web/edge com domínio oficial, DNS, TLS, HTTPS, CORS/CSP/headers, proxy/ingress, WAF/rate limiting e isolamento de ambiente, aproveitando a fundação provider-neutral já existente.

### Pré-flight obrigatório

1. Confirme que a `main` contém o fechamento dos WPs anteriores e que a matriz de CI está verde.
2. Audite a implementação de edge existente: trusted hosts, CORS explícito, CSP/security headers, HSTS policy, proxy-header spoofing guard, trusted proxy CIDRs, `--no-proxy-headers` no Uvicorn e hardening do portal estático.
3. Confirme que production continua fail-closed sem hostname público e que ranges globais de proxy trust não são aceitos em production-like profiles.
4. Liste separadamente o que é controlável pelo repositório e o que exige infraestrutura/credenciais reais.

### Execução interna

- Feche qualquer lacuna de validação de hostname, origem, proxy trust e headers.
- Garanta redirect HTTP→HTTPS no ponto correto da arquitetura sem criar loop atrás de proxy.
- Garanta que HSTS só seja tratado como efetivo quando TLS real estiver terminando corretamente.
- Configure cookies/sessões de produção com atributos seguros onde aplicável (`Secure`, `HttpOnly`, `SameSite`) e confirme proteção CSRF onde houver mutação baseada em cookie.
- Preserve health/readiness internos sem tornar endpoints administrativos/metrics públicos por acidente.
- Defina configuração provider-neutral para ingress/CDN/WAF/rate limit, mas não simule recurso cloud inexistente.
- Certifique que portal e API continuam sem segredos em imagem, frontend bundle ou logs.

### Dependências externas obrigatórias para conclusão real

- domínio/hostname oficial;
- acesso ao provedor DNS;
- infraestrutura cloud/ingress/CDN/reverse proxy escolhida;
- emissão/renovação de certificado TLS;
- ranges reais de proxy/ingress;
- WAF/rate limiting reais;
- rede/ambiente de produção isolado;
- banco PostgreSQL de produção e secret manager reais;
- endpoint público real para smoke/evidência.

### Gates

- secret scan;
- migration policy;
- Ruff;
- Mypy;
- Pytest;
- dependency audits;
- frontend lint/typecheck/tests/build;
- Playwright crítico;
- Docker/Compose validation;
- non-root;
- runtime smokes;
- vulnerability policy;
- SBOM;
- backup/restore rehearsal quando aplicável;
- testes de Host/CORS/CSP/HSTS/proxy spoofing/redirect/HTTPS;
- smoke público real somente se infraestrutura real existir.

### Critério de fechamento

Use uma das classificações exatas:

- `PRODUCTION_EDGE_READY`: somente com domínio, DNS, TLS e infraestrutura reais comprovados por evidência.
- `INTERNAL_EDGE_READY / BLOCKED_EXTERNAL`: toda preparação controlável pelo repositório está verde, mas falta infraestrutura real.

Nunca use `PRODUCTION_EDGE_READY` só porque os testes locais passaram.

---

## WP-WEB-11 — Cakto Commercial Activation

### Objetivo

Ativar o ciclo comercial real via Cakto sem permitir que billing se torne autoridade fiscal.

### Pré-flight obrigatório

1. Leia a documentação oficial atual da Cakto e confirme o contrato efetivamente disponível para a conta real.
2. Não implemente assinatura, nomes de eventos, campos de payload ou códigos de status por memória/guess. Derive da documentação/credenciais reais e preserve versão/proveniência.
3. Mapeie o domínio já existente de tenants, planos, entitlement, suspensão e reativação antes de criar qualquer tabela/serviço novo. Evite um segundo sistema comercial paralelo.

### Execução

- checkout/assinatura com identificadores reais de produto/plano;
- endpoint de webhook autenticado conforme o mecanismo oficial da Cakto;
- persistência durável de inbox/event receipt antes dos efeitos de negócio;
- deduplicação/idempotência por identificador estável do evento;
- proteção contra replay e tratamento seguro de retries;
- tolerância a eventos fora de ordem;
- validação de assinatura/autenticidade antes de qualquer mutação;
- mapeamento explícito `produto/plano Cakto → plano interno/entitlements`;
- provisioning de tenant somente após evento comercial confirmado e verificável;
- suspensão, reativação, cancelamento e falha de pagamento de forma auditável;
- reconciliação periódica entre estado Cakto e estado interno;
- logs sem payload sensível/segredos;
- métricas, alertas e DLQ/reprocessamento governado para eventos falhos;
- testes de duplicidade, replay, assinatura inválida, ordem invertida, timeout, retry e evento desconhecido.

### Regras de autoridade

- Billing pode controlar entitlement comercial.
- Billing não pode marcar `fiscal_production_activated=true`.
- Billing não pode instalar certificado fiscal, CSC ou credencial fiscal.
- Billing não pode promover homologação fiscal.
- Uma conta paga sem homologação fiscal permanece sem autoridade para emissão fiscal real.

### Dependências externas obrigatórias

- conta Cakto real habilitada;
- credenciais/API/webhook secret reais via secret manager;
- IDs reais de produtos/planos;
- URL pública real de webhook;
- eventos reais ou ambiente oficial de teste fornecido pela Cakto.

### Critério de fechamento

- `CAKTO_COMMERCIAL_READY`: somente com webhook/eventos reais certificados e reconciliação comprovada.
- `INTERNAL_CAKTO_READY / BLOCKED_EXTERNAL`: integração interna completa e testada, mas sem credenciais/eventos externos reais.

---

## WP-WEB-12 — Real Fiscal Homologation & Pilot

### Objetivo

Executar homologação fiscal real, por jurisdição/provider/operação, e um piloto controlado baseado exclusivamente em evidências oficiais.

### Pré-flight obrigatório

1. Releia toda a matriz de homologação já existente no repositório.
2. Não converta `NOT_RUN`, `BLOCKED_EXTERNAL`, `SIMULATED`, `INTERNAL_READY` ou equivalente em homologado.
3. Liste certificados, CSCs, credenciais, UFs, municípios, providers e ambientes realmente disponíveis.
4. Segredos reais entram apenas via secret manager/ambiente autorizado e nunca no Git, logs, screenshots ou artefatos públicos.

### Execução

- conectar transports reais oficiais já previstos pela arquitetura;
- validar cadeia do certificado, validade, escopo e tenant/unidade corretos;
- validar CSC/credenciais/provider por ambiente e jurisdição;
- executar homologação por combinação relevante de documento/operação/jurisdição/provider;
- registrar request/response sanitizados, timestamps, correlation/causation IDs, identificadores oficiais e resultado;
- testar emissão, consulta, cancelamento, inutilização quando aplicável, webhook/callback e reconciliação;
- testar retry/idempotência sob timeout e falha transitória real controlada;
- testar recuperação/reprocessamento sem emissão duplicada;
- manter matriz de homologação granular, nunca um único boolean global;
- executar piloto com tenant/unidade explicitamente autorizados;
- observar métricas, falhas, latência, divergências e reconciliação;
- produzir pacote de evidências para decisão humana de Go/No-Go.

### Regras de homologação

- Homologado significa evidência real do ambiente oficial correspondente.
- Homologação em uma UF não homologa outra UF.
- Homologação em um município NFS-e não homologa outro município.
- Homologação com um provider não homologa outro provider.
- Uma operação bem-sucedida não homologa automaticamente cancelamento, inutilização, contingência ou reconciliação.
- Mock, fixture, sandbox local e transporte simulado nunca contam como homologação oficial.

### Dependências externas obrigatórias

- certificados digitais reais autorizados;
- CSC/token quando aplicável;
- credenciais de SEFAZ/prefeitura/provider;
- ambientes oficiais de homologação;
- tenants/unidades piloto autorizados;
- janela operacional e aprovação humana.

### Critério de fechamento

- `HOMOLOGATED` somente para cada célula da matriz que tenha evidência real.
- `PILOT_READY` somente quando todas as células exigidas para o piloto estiverem homologadas e a matriz técnica estiver verde.
- `PRODUCTION_APPROVED` somente após decisão humana explícita e registrada.
- Caso faltem insumos externos, manter `BLOCKED_EXTERNAL` sem criar evidência substituta.

---

## Matriz de execução e merge

Para cada WP:

1. crie branch dedicada a partir da `main` verde mais recente;
2. implemente apenas o escopo daquele WP;
3. execute a matriz completa de qualidade/segurança/recovery;
4. corrija todas as falhas reais; não masque testes;
5. documente resultados e dependências externas;
6. abra PR com estado preciso;
7. exija CI do HEAD final 100% verde;
8. faça merge somente do escopo interno efetivamente certificado;
9. confirme SHA da `main` pós-merge;
10. só então avance ao WP seguinte.

Se um WP estiver `BLOCKED_EXTERNAL`, é permitido mergear a preparação interna quando ela estiver completa, testada, segura e claramente documentada como preparação — nunca como ativação real.

## Relatório obrigatório ao final de cada WP

Informe:

- WP e escopo concluído;
- classificação de readiness exata;
- branch;
- PR;
- HEAD certificado;
- SHA de merge/main;
- CI run final e conclusão;
- quantidade/estado dos testes relevantes;
- evidências reais obtidas;
- dependências externas ainda ausentes;
- riscos residuais;
- decisão: `MERGED`, `BLOCKED_EXTERNAL`, `NO_GO` ou `READY_FOR_NEXT_WP`.

## Travas finais

É proibido:

- afirmar produção real sem domínio/DNS/TLS reais;
- afirmar integração Cakto real sem autenticação/evento real;
- afirmar homologação fiscal sem ambiente oficial/evidência real;
- colocar segredo no repositório;
- usar credencial fictícia como prova;
- desabilitar segurança para fazer smoke passar;
- promover automaticamente `PRODUCTION_APPROVED`;
- fazer force-push/rebase destrutivo em evidência já certificada;
- iniciar WP-WEB-12 antes de encerrar corretamente WP-WEB-11;
- criar um WP adicional fora do plano para substituir escopo bloqueado.

O objetivo não é deixar o relatório verde a qualquer custo. O objetivo é deixar o sistema tecnicamente correto e o estado documental exatamente igual à realidade.
