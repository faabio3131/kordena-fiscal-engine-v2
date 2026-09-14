# V2-18.8 — Premium Product Experience

## Estado

**IMPLEMENTADA — AGUARDANDO GATE FINAL DO BLOCO.**

## Objetivo

Transformar as superfícies administrativas/comerciais do FM Fiscal em uma referência visual enterprise sem alterar as fronteiras de autoridade fiscal e sem executar produção.

## Superfície criada

A referência está em `portal/`:

- `index.html` — shell semântico, skip-link, indicadores, aviso de Release Candidate interno e confirmação de ações críticas;
- `styles.css` — sistema visual responsivo, foco visível, reduced-motion, empty/loading/error states e componentes operacionais;
- `app.js` — navegação e views inteiramente locais/sintéticas, sem rede, sem persistência de segredo e sem mutação fiscal.

Views cobertas:

- onboarding;
- empresas;
- unidades;
- ambientes;
- capabilities;
- documentos;
- emissões;
- erros;
- reconciliação;
- webhooks;
- integrações;
- certificados/references;
- providers;
- usage;
- billing;
- planos;
- auditoria;
- suporte;
- configurações.

## Guardrails

A experiência premium preserva:

1. `READY_INTERNAL` não significa autorização produtiva;
2. produção aparece explicitamente bloqueada na referência;
3. cutover real continua `HUMAN_APPROVAL_REQUIRED`;
4. certificados, CSC, tokens e credenciais são somente referências fictícias;
5. a referência não executa `fetch`, não grava cookies/localStorage e não contém material secreto;
6. billing comercial não é tratado como autoridade de documento fiscal;
7. bloqueios Kordena/Vendedor IA/CampaIA continuam visíveis e não são convertidos em verde artificial.

## Testes

`tests/product/test_premium_portal.py` certifica:

- shell acessível;
- confirmação de ação crítica;
- cobertura das superfícies exigidas;
- bloqueios de produção/segredo;
- ausência de material privado e chamadas de rede;
- responsividade;
- reduced-motion e foco visível.

## Produção

Este bloco não realiza deploy, cutover, emissão real, provisioning de segredo real ou promoção para `PRODUCTION_APPROVED`.
