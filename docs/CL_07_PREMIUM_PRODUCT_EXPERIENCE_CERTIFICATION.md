# CL-07 — Premium Product Experience Certification

Status: `CERTIFICATION_CANDIDATE`

Baseline funcional: `feat/nfcore-cl06-commercial-onboarding-e2e` @ `1da6f0651a6baf84b976b2983f21abc2bd68536a`.

PR: `#53`

Branch: `feat/nfcore-cl07-premium-product-experience`

## Escopo certificado internamente

CL-07 preserva a arquitetura funcional do portal e fecha apenas gaps materiais de acabamento de produto, acessibilidade e governança visual.

Implementação incluída:

- identidade visual FM NFCORE preservada e formalizada;
- design system documentado e governado;
- estados disabled explícitos;
- foco por teclado com `:focus-visible`;
- suporte a `prefers-contrast: more`;
- suporte a `prefers-reduced-motion`;
- refinamento do login/recovery em telas estreitas;
- contratos responsivos em desktop/tablet/mobile preservados;
- navegação continua derivada das superfícies autorizadas pelo backend;
- auth, password recovery, CSRF, idempotência, tenant isolation e RBAC permanecem canônicos;
- nenhuma autoridade fiscal/comercial foi movida para o frontend;
- nenhuma funcionalidade falsa, preço hardcoded ou readiness sintética foi adicionada.

## Testes e invariantes

Os testes de frontend validam:

- contratos autenticados;
- ausência de autoridade tenant/role no browser;
- CSRF + idempotência;
- password recovery sem exposição de token;
- navegação limitada por `available_surfaces` do backend;
- tokens centrais do design system;
- breakpoints responsivos;
- `focus-visible`;
- disabled state;
- high contrast;
- reduced motion.

A certificação final exige a matriz completa `FM NFCORE V1 CI` em `completed/success` no HEAD final da PR. O SHA exato e o workflow run final devem ser registrados na PR após a execução imutável.

## Governança

Nenhum merge, deploy, DNS, cutover, emissão fiscal real ou `PRODUCTION_APPROVED` é autorizado por este documento.
