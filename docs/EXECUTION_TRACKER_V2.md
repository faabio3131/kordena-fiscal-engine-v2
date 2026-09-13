# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-14 — Hardening sistêmico**  
Fase atual: **V2-15 — B0 CERTIFICADO / B1 HOMOLOGATION ENVIRONMENT READINESS EM EXECUÇÃO**

> Snapshot pré-V2-15: `docs/history/EXECUTION_TRACKER_V2_PRE_V2_15.md`. Plano: `docs/V2_15_HOMOLOGATION_CONTROLLED_PILOTS.md`. Auditoria vinculante: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. Merge está autorizado somente para escopo integralmente concluído e 100% verde; deploy, produção real e cutover continuam proibidos nesta execução.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-12 | Gateway/Signer/Vault adapters | **CONCLUÍDO** | PR #13 Draft; 508 PASS |
| V2-13 | Observabilidade + Compliance Operations | **CONCLUÍDO** | PR #14 Draft; 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 Draft; B6 582 PASS; doc gate 582 PASS; CI final dispatch-only |
| V2-15 | Homologação + pilotos controlados | **EM EXECUÇÃO** | PR #16 Draft; B0 Zero-Code CERTIFICADO; B1 EM EXECUÇÃO |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | depende de Core configurável/homologação e readiness real dos produtos |
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

### B0 — Commercial Configurability Audit + Zero-Code Onboarding — CONCLUÍDO/CERTIFICADO

Documento: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

Remediações concluídas:

- SecretReference provider-scoped para CREDENTIALS/CSC;
- ProviderBinding durável por cliente/capacidade/jurisdição/operação;
- `FiscalProductProfile` persistente;
- enablement durável de módulos/operações;
- webhook destination config;
- workload identity/grants duráveis;
- homologation evidence durável;
- numbering config durável;
- timeout/retry/circuit policy profiles duráveis;
- runtime concreto separado do núcleo do Control Plane.

Gate B0: SHA `0cc8eeb8ed82fd40cf9c307cf4c24873bdf11bb2`, run `34775807228`, job `103773578619`: Install PASS, Ruff PASS, Mypy PASS em **109 source files**, Pytest **592 PASS em 5.54s**. A separação arquitetural verde foi persistida em `4fbe0f962a8df0c0b44c43b6d70b8636ec965f7d`.

O gate Zero-Code certifica clientes sintéticos fiscalmente distintos usando o mesmo source/binário, persistência/restart e isolamento fail-closed entre tenant/unit/provider/environment.

### B1 — Homologation Environment Readiness — EM EXECUÇÃO

Auditar ambiente HOMOLOGATION, provider descriptors/bindings, Vault refs, signer, CSC, credentials, transport/TLS/schema/jurisdiction/readiness/telemetria e distinguir evidência técnica interna de evidência oficial externa.

### B2 — NF-e Homologation Matrix — PENDENTE

Aguardando B1 verde.

### B3 — NFC-e Homologation Matrix — PENDENTE

Aguardando B2 verde.

## Governança preservada

Nenhum endpoint produtivo, emissão de produção, deploy ou cutover é autorizado. Homologação oficial externa só pode ser registrada com evidência externa real. Se evidência/credencial/certificado/CSC/provider externo não estiver disponível, concluir todo o trabalho interno e registrar bloqueio externo preciso. B4-B6 não iniciar nesta autorização específica; V2-17 não iniciar.
