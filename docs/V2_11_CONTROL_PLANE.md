# V2-11 — Control Plane independente

Status: **EM EXECUÇÃO — FOUNDATION ADMINISTRATIVA CERTIFICADA**  
Branch: `v2/control-plane`  
Base certificada: `v2/product-contract-packs` @ `156a945cc8e2708eba21551b128ac3d673bb0cdc`  
Dependência: V2-10 concluída e certificada.

## Objetivo

Permitir operação autônoma e governada do FM Fiscal por um Control Plane independente dos produtos consumidores, sem introduzir UI comercial/premium antes do domínio operacional estar certificado e sem absorver responsabilidades de provider/vault de produção reservadas à V2-12.

## Entregas vinculantes do Plano Mestre

- onboarding de empresa e unidade;
- perfis fiscais e vigências;
- gestão de capabilities e ambientes;
- referências de certificado, CSC e credentials por abstração/referência de Vault, nunca segredo bruto;
- visão/operação governada de operações, erros, contingência, archive e reconciliação;
- RBAC administrativo;
- trilha de auditoria.

## Limites arquiteturais

- nenhum segredo, certificado PFX, CSC, token ou credential material entra no domínio, fixture ou repositório;
- V2-11 armazena e governa somente referências opacas a segredos; adapters reais de Vault/KMS são V2-12;
- Control Plane não promove sozinho `PRODUCTION_APPROVED`; Capability & Readiness permanece autoridade fiscal;
- nenhuma UI comercial/premium é construída nesta fase;
- nenhuma dependência de domínio privado de Kordena, Iron Fit, Vendedor IA ou CampaIA;
- todo escopo administrativo é explícito por tenant/unidade/ambiente e falha fechado;
- mudanças administrativas relevantes geram auditoria imutável com ator, ação, alvo, timestamp e correlation id.

## Blocos de execução

1. **Foundation administrativa — CONCLUÍDO/CERTIFICADO:** identidade de organização/unidade fiscal, ator administrativo, RBAC, referências opacas de segredo e audit event; serviço em memória para provar invariantes antes da persistência.
2. **Persistência durável e perfis fiscais — PRÓXIMO:** onboarding durável, perfis/vigências, ambientes e referências; migration explícita e restart safety.
3. **Capability/Readiness governance:** associação governada entre configuração administrativa e a Capability & Readiness API sem criar autoridade paralela.
4. **Operational Control Plane:** consultas/visões governadas de operações, erros, contingência, archive e reconciliação reutilizando os serviços certificados existentes.
5. **Certificação end-to-end:** RBAC, isolamento multi-tenant/unidade, audit trail, ausência de segredo bruto, restart/replay, diff completo e regressão integral.

## Bloco 1 — Foundation administrativa

Foi criada a superfície `kordena_fiscal.control_plane` com contratos host-neutral e serviço administrativo em memória deliberadamente transitório.

### Domínio administrativo

- `ControlPlanePermission` define permissões explícitas e fail-closed para organization, unit, profile, capability, secret reference, audit e operations;
- `AdminPrincipal` separa escopo global de allowlist de tenants e proíbe combinação ambígua dos dois;
- `FiscalOrganization` e `FiscalUnitRegistration` modelam onboarding sem carregar domínio privado de qualquer SaaS;
- `FiscalUnitRegistration.enabled_environments` exige conjunto explícito e inicia em HOMOLOGATION por padrão, sem habilitar produção silenciosamente;
- `SecretReference` aceita somente referência opaca `ref:...` e contém apenas id, kind, tenant, unit e environment;
- `SecretReferenceKind` limita as categorias a certificate, CSC e credentials;
- `ControlPlaneAuditEvent` é um fato administrativo imutável sem payload livre que possa carregar segredo acidentalmente.

### Serviço e RBAC

`ControlPlaneFoundationService` certifica as invariantes antes de introduzir persistência:

- onboarding de organização exige `organization.write` e ator global;
- onboarding de unidade exige `unit.write`, tenant autorizado e organização previamente criada;
- binding de referência exige `secret_reference.write`, tenant autorizado, unidade existente e environment habilitado;
- duplicidades e bindings ambíguos falham fechado;
- leitura de auditoria exige `audit.read` e respeita isolamento de tenant;
- toda mutação administrativa certificada gera audit event com ator, ação, alvo, correlation id, tenant/unidade e timestamp timezone-aware.

### Segurança de referências

Os contract tests inspecionam estruturalmente `SecretReference` e comprovam ausência dos campos `secret`, `value`, `material`, `password`, `token` e `pfx`. Valores que não seguem o formato opaco `ref:...` são rejeitados antes de qualquer armazenamento.

### Certificação Foundation

A primeira tentativa de CI (`34708348014`) falhou na coleta por colisão de basename entre `tests/control_plane/test_foundation.py` e o teste legado `tests/test_foundation.py`; foi corrigido isolando `tests/control_plane` como package. A segunda tentativa (`34708391513`) executou a suíte e encontrou um único mismatch de expectativa no teste de RBAC: o ator usado para provar ausência de global scope também não possuía `organization.write`, portanto o serviço corretamente falhou primeiro por falta da permission. O fixture foi corrigido para separar as duas invariantes, sem mudança semântica no serviço.

Gate definitivo:

- SHA funcional/certificação: `eaeca06739f756d31085617c1eecabebcc846dd7`;
- Actions run: `34708472525` — **SUCCESS**;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **81 source files**;
- Pytest: **406 PASS em 1.46s**;
- baseline V2-10: 397; incremento Foundation V2-11: **+9 testes**;
- compare bootstrap `f2167b5ac7ca3806287c3fd4abf509a5b698925a` -> gate: **7 commits à frente, 0 atrás**; alterações restritas ao novo `control_plane`, testes e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `71823391c456b120ae5a4cf35d599caea0df353d`.

## Gate da fase

A V2-11 somente será marcada `CONCLUÍDA` após todos os blocos, documentação, PR Draft, CI verde, Ruff, Mypy strict, Pytest, auditoria de diff contra V2-10, riscos residuais e restauração do CI para `workflow_dispatch`.

## Governança

PR #12 permanece Draft. Nenhum merge, deploy, promoção, homologação externa ou cutover é autorizado automaticamente.
