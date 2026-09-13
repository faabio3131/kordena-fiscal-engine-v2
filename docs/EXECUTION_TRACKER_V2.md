# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-14 — Hardening sistêmico**  
Fase atual: **V2-15 — B0-B3 CERTIFICADOS INTERNAMENTE; B4 AGUARDANDO NOVA AUTORIZAÇÃO**

> Snapshot pré-V2-15: `docs/history/EXECUTION_TRACKER_V2_PRE_V2_15.md`. Plano: `docs/V2_15_HOMOLOGATION_CONTROLLED_PILOTS.md`. Auditoria vinculante: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`. Merge está autorizado somente para escopo integralmente concluído e 100% verde; deploy, produção real e cutover continuam proibidos nesta execução. Homologação oficial externa exige evidência externa real.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-12 | Gateway/Signer/Vault adapters | **CONCLUÍDO** | PR #13 Draft; 508 PASS |
| V2-13 | Observabilidade + Compliance Operations | **CONCLUÍDO** | PR #14 Draft; 563 PASS |
| V2-14 | Hardening sistêmico | **CONCLUÍDO** | PR #15 Draft; B6 582 PASS; doc gate 582 PASS; CI final dispatch-only |
| V2-15 | Homologação + pilotos controlados | **EM EXECUÇÃO** | PR #16 Draft; B0-B3 certificados internamente; B4-B6 pendentes |
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

Gate de transformação B0: SHA `0cc8eeb8ed82fd40cf9c307cf4c24873bdf11bb2`, run `34775807228`, job `103773578619`: 109 source files, **592 PASS em 5.54s**. Separação arquitetural persistida em `4fbe0f962a8df0c0b44c43b6d70b8636ec965f7d`.

Gate limpo de recertificação B0: SHA `87af3e9c96b135142d4ea41118c3463c4223f3d9`, run `34776022773`, job `103774161682`: Install/Ruff/Mypy PASS, 109 source files, **592 PASS em 8.42s**.

### B1 — Homologation Environment Readiness — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Documento: `docs/V2_15_B1_HOMOLOGATION_ENVIRONMENT_READINESS.md`.

Readiness HOMOLOGATION exato por provider/document/jurisdiction/environment, provider-scoped credentials/CSC, certificate reference, runtime policy, evidence durável, restart e fail-closed. `PRODUCTION` rejeitado. Evidência técnica interna permanece separada de evidência oficial externa.

Gate B1: SHA `4bd07f94db7c0d5e05c7896adbfc8ff80d377ac3`, run `34776243989`, job `103774775120`: Install/Ruff/Mypy PASS, **110 source files**, **597 PASS em 6.19s**.

### B2 — NF-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Matriz: `docs/V2_15_NFE_HOMOLOGATION_MATRIX.md`.

Cobertura interna: AUTHORIZE/QUERY/CANCEL, resolução exata de provider/jurisdição, restart durability, rejection normalization, retry semantics e unknown authorization outcome sem blind retry.

Gate B2: SHA `ec5a00dff67710a2d20e7931665e15e94d6de77b`, run `34776372599`, job `103775124030`: Install/Ruff/Mypy PASS, **110 source files**, **601 PASS em 22.18s**.

### B3 — NFC-e Homologation Matrix — CONCLUÍDO/CERTIFICADO INTERNAMENTE

Matriz: `docs/V2_15_NFCE_HOMOLOGATION_MATRIX.md`.

Cobertura interna: AUTHORIZE/QUERY/CANCEL, provider-scoped CSC/credentials, certificado por referência, fail-closed cross-provider, proibição HOMOLOGATION→PRODUCTION e persistência sem material secreto.

Gate B3: SHA `5507d4ea4c721af4ea77b576e162c684b551eb38`, run `34776525383`, job `103775530828`: Install/Ruff/Mypy PASS, **110 source files**, **605 PASS em 6.94s**. CI restaurado dispatch-only em `210c4f5ec2a47ce619c8eb4ca56c165454ce9d6f`.

### B4 — NFS-e Homologation Matrix — PENDENTE

Não iniciado nesta autorização específica. Aguardar nova autorização.

### B5 — Pilotos Controlados + Go/No-Go — PENDENTE

Não iniciado nesta autorização específica. Aguardar nova autorização.

### B6 — Certificação/Fechamento V2-15 — PENDENTE

Não iniciado nesta autorização específica. Aguardar nova autorização.

## Evidência externa / merge

B1-B3 possuem certificação técnica interna somente. Nenhuma homologação oficial externa foi executada ou alegada; `external_official` permanece falso sem evidência real. A PR #16 representa a V2-15 inteira, portanto permanece OPEN/DRAFT/não mergeada enquanto B4-B6 estiverem pendentes, mesmo havendo autorização genérica para merge de escopo integralmente concluído e verde.

## Governança preservada

Nenhum endpoint produtivo, emissão de produção, deploy ou cutover foi autorizado/executado. Nenhum segredo real foi incluído no repositório. B4-B6 não iniciar sem nova autorização específica; V2-17 não iniciar.
