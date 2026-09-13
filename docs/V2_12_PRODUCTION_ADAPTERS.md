# V2-12 — Gateway / Signer / Vault Production Adapters

Status: **EM EXECUÇÃO — BLOCOS 1 A 5 CERTIFICADOS**  
Branch: `v2/production-adapters`  
Base certificada: `v2/control-plane` @ `0439246151c7edc959615361c0275961e11c3af0`  
Dependência: V2-11 concluída e certificada.

## Objetivo

Preparar a operação real do FM Fiscal sem acoplar o Core a fornecedor único, introduzindo ports/adapters para resolução segura de segredo, assinatura fiscal, providers/gateways, resiliência e homologation gates por documento/jurisdição.

## Princípios vinculantes

- domínio continua host-neutral, provider-neutral e secret-neutral;
- dependency inversion e fail-closed são obrigatórios;
- nenhum segredo real entra em Git, fixtures, docs, logs, SQLite, payload persistido ou snapshots;
- Control Plane armazena somente `SecretReference` opaca;
- material sensível só existe de forma efêmera em runtime;
- signer não decide regra fiscal nem readiness;
- Vault não decide readiness;
- provider adapter não decide autorização administrativa;
- resilience não decide rejeição fiscal;
- homologation gates técnicos não substituem a autoridade central de `CapabilityReadinessService`;
- nenhum deploy, produção real, homologação externa, promoção ou cutover nesta fase sem autorização humana explícita.

## Blocos

1. **Vault/KMS abstraction + Secret Resolution Boundary — CONCLUÍDO/CERTIFICADO.**
2. **Signer Boundary + assinatura por SecretReference — CONCLUÍDO/CERTIFICADO.**
3. **Provider/Gateway adapters + CSC/Credentials — CONCLUÍDO/CERTIFICADO.**
4. **Resilience Runtime — CONCLUÍDO/CERTIFICADO.**
5. **Homologation Gates + cross-provider — CONCLUÍDO/CERTIFICADO.**
6. **Certificação end-to-end + fechamento V2-12 — PRÓXIMO.**

## Bloco 1 — Vault/KMS abstraction + Secret Resolution Boundary

Foi criado `kordena_fiscal.vault` fora do domínio fiscal. `SecretResolutionService` lê somente `SecretReference` governada no Control Plane e delega material runtime ao port `FiscalSecretVault`.

Tipos efêmeros explícitos: `EphemeralCertificateMaterial`, `EphemeralCscMaterial` e `EphemeralProviderCredentialsMaterial`. Todos são redigidos em `repr`, não possuem repository/serializer e não entram no UoW.

Gate definitivo: SHA `961ee84aa28f58ce933d2dd899bfd013c801da1c`, run `34758902465`, job `103728060621`, **88 source files, 447 PASS em 2.15s**. CI restaurado em `cb399d0c74ae5925c4d89412a4760472fe7ab430`.

## Bloco 2 — Signer Boundary + assinatura por SecretReference

Foi criado `kordena_fiscal.signing`. O signer recebe bytes canônicos, contexto fiscal explícito e `SecretReference`; o material PKCS#12 é obtido exclusivamente por `SecretResolutionService` -> `FiscalSecretVault`.

`CryptographyFiscalDocumentSigner` usa `cryptography>=44,<48` para PKCS#12, RSA/ECDSA e verificação. NF-e/NFC-e são explícitos; NFS-e permanece fail-closed até adapter/provider específico. Nenhum PFX/P12/PEM/KEY é persistido.

Gate definitivo: SHA `f27ae85ac1dbf0b5cf47eea96d1437585b37cb92`, run `34759157421`, job `103728746009`, **91 source files, 459 PASS em 3.05s**. CI restaurado em `750dbb7e2e7f34fd55fe8a79fbda7dd422af9fb7`.

## Bloco 3 — Provider/Gateway adapters + CSC/Credentials

`ProviderDescriptor` declara `provider_id`, document kinds, jurisdictions, environments, operations e requisitos de CSC. `ProviderRegistry` resolve exatamente um provider e falha fechado em ausência/ambiguidade. `ProviderRequest`/`ProviderResponse` não transportam segredo persistível.

`ConfiguredProviderAdapter` resolve credenciais via `SecretReferenceKind.CREDENTIALS` e CSC via `SecretReferenceKind.CSC`, sempre através do Vault boundary. `SyntheticProviderTransport` é no-network e registra somente reference ids e hashes. `ProviderGatewayService` consulta `CapabilityReadinessService` sem promover readiness.

Falhas intermediárias: run `34759978765` (Ruff) e run `34760070032` (ciclo de importação). A correção adotou exports lazy no novo provider runtime.

Gate definitivo: SHA `42f27c67145d2d4469374596d869ffc3ba05f013`, run `34760113452`, job `103731343836`, **93 source files, 471 PASS em 3.27s**. CI restaurado em `9e5019d64b5174ad9fe138e52c566ec3df73af84`.

## Bloco 4 — Resilience Runtime

Foi criado `kordena_fiscal.resilience` e o contrato de transport do provider passou a exigir `ProviderTimeoutPolicy` explícita com connect/read timeout, eliminando dependência de defaults ocultos de SDK.

`RetryPolicy` oferece máximo de tentativas, exponential backoff, jitter e delay máximo, todos limitados e testáveis por `Sleeper`/`JitterSource` injetáveis. QUERY/STATUS são `SAFE_RETRY`; AUTHORIZE/CANCEL/INUTILIZE são `CONDITIONAL_RETRY`.

Uma autorização com `delivery_unknown=True` nunca é repetida automaticamente: produz `UnknownProviderOutcomeError` e exige query/reconciliation. Rejeição fiscal e erro de autenticação/validação não são tratados como indisponibilidade transitória.

`CircuitBreakerRegistry` implementa `CLOSED`, `OPEN` e `HALF_OPEN`, com thresholds configuráveis. A chave é particionada por provider + environment + UF + município opcional, impedindo falha de um provider/jurisdição de derrubar toda a malha.

Falhas intermediárias: run `34760512225` (Ruff E501) e run `34760572581` (Mypy retorno Any no delay), ambas corrigidas sem relaxar gates.

Gate definitivo: SHA `a3db491049d6058753ebad18d6fb62026310b1b8`, run `34760627774`, job `103732719543`, **95 source files, 483 PASS em 3.03s**. CI restaurado em `dd7d3eb5a6c718bf9576b377112b0c4a812e6159`.

## Bloco 5 — Homologation Gates + Cross-provider

Foi criado `kordena_fiscal.homologation` como camada técnica de evidência. Ela não cria uma segunda autoridade de readiness: `HomologationGateEvaluator` consulta `CapabilityReadinessService.require_action` e combina o snapshot central com evidência técnica explícita.

`HomologationGateKey` é particionado por provider, document kind, jurisdiction, environment e operation. A matriz é fail-closed e exige correspondência exata, sem provider default silencioso. Para NFS-e, município IBGE explícito é obrigatório; não existe cobertura municipal universal inferida.

`HomologationEvidence` cobre adapter disponível, credential reference, signer capability, CSC quando aplicável, transport, resilience, contract tests, jurisdiction mapping e operação suportada. Configuração parcial permanece `CONTRACT_READY`; somente evidência completa produz `TECHNICALLY_CERTIFIED`, e mesmo assim a execução depende do readiness central.

A certificação cross-provider prova coexistência de providers com isolamento de evidência, credenciais e circuit breaker. Falha/circuito de provider A não altera gate ou circuito de provider B.

### Certificação Bloco 5

Gate definitivo:

- SHA: `ae9347b2f97f6984e22f6a719eec5e4b1ea8a3db`;
- run: `34760988165` — **SUCCESS**;
- job: `103733669977`;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **97 source files**;
- Pytest: **497 PASS em 3.41s**;
- baseline Bloco 4: 483; incremento líquido: **+14 testes**;
- diff checkpoint B4 documental -> gate B5: **7 commits à frente, 0 atrás**, adicionando somente homologation gates/tests e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `e2c89a602c85c104e668f8bb3cc469161ed4b408`.

## Próximo bloco

Bloco 6: certificação end-to-end, failure matrix, structural secret scan, dependency/architecture audit, cross-product neutrality, regressão mestre, auditoria completa V2-11 -> V2-12 e fechamento documental integral da V2-12.

## Governança

A PR #13 permanece Draft. V2-12 permanece **EM EXECUÇÃO**. Sem merge, deploy, produção real, homologação externa ou cutover automático.
