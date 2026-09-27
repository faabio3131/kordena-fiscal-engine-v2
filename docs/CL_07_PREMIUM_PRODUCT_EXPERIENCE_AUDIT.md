# CL-07 — Premium Product Experience Audit

Status: `AUDIT_COMPLETE / IMPLEMENTATION_REQUIRED`

Baseline funcional auditado: `1da6f0651a6baf84b976b2983f21abc2bd68536a` (CL-06 certificado).

## Resultado executivo

O portal já possui uma fundação visual premium consistente: identidade FM NFCORE própria, design tokens, estados de loading/empty/error, layout responsivo, foco visível, redução de movimento, navegação orientada pelo backend e separação explícita entre interface e autoridade fiscal. Portanto CL-07 não deve reconstruir o frontend nem substituir a arquitetura existente.

A remediação de CL-07 deve ser cirúrgica e concentrada em acabamento de produto, acessibilidade, comportamento de controles e formalização do design system.

## Gaps materiais identificados

1. Estados `disabled` de botões/controles não possuem tratamento visual/semântico específico no design system.
2. Inputs usam `:focus` genérico; a experiência deve privilegiar `:focus-visible` sem remover indicação de foco para teclado.
3. Falta uma documentação vinculante do design system e dos estados operacionais para evitar regressões visuais futuras.
4. O contrato de responsividade/reduced-motion deve ser testado como requisito de produto, não apenas existir incidentalmente no CSS.
5. O portal deve preservar a regra de que UI nunca promove readiness/produção; estados visuais precisam continuar derivados da API autenticada.

## Decisão de implementação

- preservar `portal/index.html`, `portal/app.js`, auth, recovery, onboarding, CSRF, idempotência, tenant scope e RBAC;
- evoluir apenas o design system compartilhado e seus contratos;
- não criar mocks de funcionalidades ausentes;
- não adicionar novas autoridades ou estado comercial/fiscal no navegador;
- manter a estética enterprise já adotada (azul/ciano, superfícies profundas, informação operacional densa, contraste alto) sem copiar terceiros.

## Gate de certificação

CL-07 só poderá ser declarado `INTERNALLY_CERTIFIED` quando o HEAD final passar integralmente pela matriz `FM NFCORE V1 CI` e a documentação de certificação registrar o SHA/run exatos.
