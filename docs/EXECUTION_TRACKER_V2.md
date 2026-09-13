# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-14 — Hardening sistêmico**  
Fase atual: **V2-15 — REMEDIAÇÃO DE CONFIGURABILIDADE COMERCIAL / ZERO-CODE ONBOARDING**

> Snapshot pré-V2-15: `docs/history/EXECUTION_TRACKER_V2_PRE_V2_15.md`. Plano: `docs/V2_15_HOMOLOGATION_CONTROLLED_PILOTS.md`. Auditoria vinculante: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. Nenhum merge, deploy, promoção ou cutover é automático.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-12 | Gateway/Signer/Vault adapters | **CONCLUÍDO** | PR #13 Draft; 508 PASS |
| V2-13 | Observabilidade + Compliance Operations | **CONCLUÍDO** | PR #14 Draft; 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 Draft; B6 582 PASS; doc gate 582 PASS; CI final dispatch-only |
| V2-15 | Homologação + pilotos controlados | **EM EXECUÇÃO** | PR #16 Draft; B0 Commercial Configurability audit concluída; remediação Zero-Code obrigatória antes de B1 |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | AUTORIZADA; depende de Core configurável/homologação e readiness real dos produtos |
| V2-17 | Convergência/cutover | PENDENTE | NÃO AUTORIZADO nesta execução |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## V2-14 — Hardening sistêmico — CONCLUÍDA/CERTIFICADA

Fechamento: `docs/V2_14_CLOSURE_CERTIFICATION.md`. Branch `v2/system-hardening`, PR #15 Draft. Gate funcional B6 582 PASS; gate documental 582 PASS; CI final dispatch-only.

## V2-15 — Homologação + Pilotos Controlados — EM EXECUÇÃO

### Bootstrap — CONCLUÍDO

- branch `v2/homologation-controlled-pilots` criada exatamente do HEAD final V2-14 `15426a4460ed18c8861c807b92b98c6cfecb3126`;
- snapshot pré-fase criado;
- plano formal criado;
- PR #16 Draft stacked sobre `v2/system-hardening`, aberta e não mergeada.

### Decisão arquitetural vinculante — ZERO-CODE CUSTOMER ONBOARDING

Um cliente novo não pode exigir alteração de código para diferenças fiscais já suportadas pela plataforma. Host/tenant/unidade/ambiente/perfil fiscal/documentos/jurisdição/provider/SecretReferences/módulos/policies devem ser resolvidos por configuração durável e governada. Regras legais continuam em catálogos governados, não em campos normativos livres do cliente.

### B0 — Commercial Configurability Audit + Zero-Code Onboarding — EM EXECUÇÃO

**Auditoria: CONCLUÍDA. Remediação: EM EXECUÇÃO.**

Documento: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

Achados bloqueantes principais:

- Control Plane permite somente uma SecretReference por kind/tenant/unit/environment e precisa distinguir provider para CREDENTIALS/CSC;
- falta ProviderBinding/FiscalCapabilityBinding durável por cliente;
- `FiscalProductProfile` existe no domínio, mas falta persistence/CRUD comercial;
- falta enablement durável de documento/operação/módulo por unidade;
- falta configuração durável de webhook destination;
- workload identities/grants ainda dependem de composição em memória;
- homologation evidence/gates não possuem registro operacional durável por tenant/unit;
- numeração e resilience/runtime policies são parametrizadas mas ainda precisam de configuration/policy profiles apropriados;
- legal/tax/readiness rules devem ser catálogos governados e versionados, não tenant-editable.

Gate de saída B0: três clientes sintéticos fiscalmente diferentes devem ser onboardados e persistidos com o mesmo source/binário, sobreviver a restart, resolver providers/SecretReferences/módulos corretos e falhar fechado em qualquer tentativa cross-tenant/unit/provider/environment.

### B1 — Homologation Environment Readiness — AGUARDANDO B0

O B1 original permanece no plano, mas não deve avançar antes do gate Zero-Code ficar verde. Depois, auditar ambiente HOMOLOGATION, provider descriptors/bindings, Vault refs, signer, CSC, credentials, transport/TLS/schema/jurisdiction/readiness/telemetria e distinguir evidência técnica interna de evidência oficial externa.

## Governança preservada

Nenhum endpoint produtivo, emissão de produção, merge, deploy ou cutover é autorizado. Se evidência/credencial/certificado/CSC/provider externo não estiver disponível, concluir todo o trabalho interno e registrar bloqueio parcial preciso. V2-17 não iniciar.
