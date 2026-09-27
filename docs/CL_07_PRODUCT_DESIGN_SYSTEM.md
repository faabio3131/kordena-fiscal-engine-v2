# FM NFCORE V1 — Product Design System

Status: `CL-07 GOVERNED PRODUCT CONTRACT`

## 1. Princípio

A interface do FM NFCORE deve comunicar infraestrutura fiscal enterprise: precisão, segurança, rastreabilidade e governança. O design não concede autoridade operacional. Todo estado de readiness, ambiente, permissão e operação continua derivado da API autenticada.

## 2. Identidade visual

Base visual:

- superfícies escuras profundas;
- azul como cor primária de ação;
- ciano como sinal de infraestrutura/estado técnico;
- verde para sucesso certificado;
- âmbar para atenção/homologação/pendência;
- rosa/vermelho para falha ou bloqueio;
- tipografia sans-serif de alta legibilidade;
- densidade informacional compatível com produto B2B técnico.

Os tokens canônicos permanecem em `portal/styles.css`. Não duplicar cores/spacing/radius em componentes quando existir token apropriado.

## 3. Hierarquia

A hierarquia principal é:

1. produto/contexto autenticado;
2. estado crítico/readiness;
3. navegação por superfícies disponibilizadas pelo backend;
4. conteúdo operacional;
5. ações governadas.

A UI nunca deve apresentar funcionalidade indisponível como se estivesse ativa.

## 4. Estados

Estados visuais devem distinguir, quando aplicável:

- `READY`;
- `PENDING`;
- `BLOCKED`;
- `ERROR`;
- `WARNING`;
- `HOMOLOGATION`;
- `PRODUCTION`;
- `EXTERNAL_CONFIGURATION_REQUIRED`.

O rótulo visual não substitui evidência backend. Produção fiscal continua sujeita à autoridade canônica de produção.

## 5. Interação

Regras obrigatórias:

- foco de teclado claramente visível;
- controles desabilitados visualmente distintos e não clicáveis;
- nenhum hover como única fonte de informação;
- erros em regiões anunciáveis (`role=alert`/`aria-live`) quando aplicável;
- formulários com labels explícitos e autocomplete apropriado;
- operações críticas com feedback de loading/error/success;
- `prefers-reduced-motion` respeitado;
- `prefers-contrast: more` recebe bordas/foco reforçados.

## 6. Responsividade

Breakpoints existentes devem preservar operação em desktop, tablet e mobile. Em telas estreitas:

- sidebar deixa de ser coluna fixa;
- navegação não pode exigir scroll horizontal;
- grids colapsam progressivamente;
- ações permanecem acionáveis com toque;
- tabelas/listas operacionais devem degradar para blocos legíveis.

## 7. Segurança e autoridade

É proibido introduzir no frontend:

- tenant ou role como autoridade local;
- segredo/token persistido em `localStorage`/`sessionStorage`;
- promoção visual de produção sem autoridade backend;
- mocks em produção para aparentar readiness;
- preço comercial hardcoded.

## 8. Regressão

O contrato de frontend deve verificar no mínimo:

- tokens principais do design system;
- breakpoints responsivos;
- reduced-motion;
- focus-visible;
- disabled state;
- high-contrast support;
- continuidade dos contratos de autenticação, CSRF, idempotência e navegação backend-driven.

Mudanças futuras de UX devem manter estes invariantes e passar pela matriz completa de CI.
