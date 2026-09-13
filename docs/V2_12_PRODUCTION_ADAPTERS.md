# V2-12 — Gateway / Signer / Vault Production Adapters

Status: **EM EXECUÇÃO — BLOCOS 1, 2 E 3 CERTIFICADOS**  
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
- nenhum deploy, produção real, homologação externa, promoção ou cutover nesta fase sem autorização humana explícita.

## Blocos

1. **Vault/KMS abstraction + Secret Resolution Boundary — CONCLUÍDO/CERTIFICADO.**
2. **Signer Boundary + assinatura por SecretReference — CONCLUÍDO/CERTIFICADO.**
3. **Provider/Gateway adapters + CSC/Credentials — CONCLUÍDO/CERTIFICADO.**
4. **Resilience Runtime — PRÓXIMO.**
5. **Homologation Gates + cross-provider — PENDENTE.**
6. **Certificação end-to-end + fechamento V2-12 — PENDENTE.**

## Bloco 1 — Vault/KMS abstraction + Secret Resolution Boundary

Foi criado `kordena_fiscal.vault` fora do domínio fiscal. `SecretResolutionService` lê somente `SecretReference` governada no Control Plane e delega material runtime ao port `FiscalSecretVault`.

Tipos efêmeros explícitos: `EphemeralCertificateMaterial`, `EphemeralCscMaterial` e `EphemeralProviderCredentialsMaterial`. Todos são redigidos em `repr`, não possuem repository/serializer e não entram no UoW.

Gate definitivo: SHA `961ee84aa28f58ce933d2dd899bfd013c801da1c`, run `34758902465`, job `103728060621`, **88 source files, 447 PASS em 2.15s**. CI restaurado em `cb399d0c74ae5925c4d89412a4760472fe7ab430`.

## Bloco 2 — Signer Boundary + assinatura por SecretReference

Foi criado `kordena_fiscal.signing`. O signer recebe bytes canônicos, contexto fiscal explícito e `SecretReference`; o material PKCS#12 é obtido exclusivamente por `SecretResolutionService` -> `FiscalSecretVault`.

`CryptographyFiscalDocumentSigner` usa `cryptography>=44,<48` para PKCS#12, RSA/ECDSA e verificação. NF-e/NFC-e são explícitos; NFS-e permanece fail-closed até adapter/provider específico. Nenhum PFX/P12/PEM/KEY é persistido.

Gate definitivo: SHA `f27ae85ac1dbf0b5cf47eea96d1437585b37cb92`, run `34759157421`, job `103728746009`, **91 source files, 459 PASS em 3.05s**. CI restaurado em `750dbb7e2e7f34fd55fe8a79fbda7dd422af9fb7`.

## Bloco 3 — Provider/Gateway adapters + CSC/Credentials

Foi introduzida uma camada provider-neutral sobre o gateway existente, sem substituir o contrato certificado de autorização V1.

### Provider identity e routing

`ProviderDescriptor` declara explicitamente `provider_id`, document kinds, jurisdictions, environments, operations e combinações que exigem CSC. `ProviderRegistry` resolve exatamente um provider; ausência ou ambiguidade falham fechado. Não existe seleção implícita por nome de tenant, produto FM ou host privado.

### Provider request/response

`ProviderRequest` transporta apenas escopo, document kind, jurisdiction, operação, payload/signed artifact, correlation e workload. Credencial e CSC não fazem parte do contrato persistível. `ProviderResponse` normaliza a resposta sem expor headers/token/material privado.

### Secret runtime

`ConfiguredProviderAdapter` resolve sempre credenciais via `SecretReferenceKind.CREDENTIALS` e, somente quando a capability declarada exigir, CSC via `SecretReferenceKind.CSC`. Ambos passam pelo `SecretResolutionService` certificado. Cross-tenant, cross-unit e cross-environment não reutilizam material.

### Transport

`FiscalProviderTransport` é injetável. `SyntheticProviderTransport` não usa socket/endpoints externos e armazena apenas observações não secretas (reference ids e hashes). O adapter não possui SDK de provider e nenhuma chamada produtiva foi realizada.

### Readiness

`ProviderGatewayService` chama a autoridade existente `CapabilityReadinessService.require_action` antes do routing. O provider não cria, promove ou altera readiness.

### Falhas encontradas e correções

- run `34759978765` falhou no Ruff por oito ocorrências de formatação/teste genérico; foram corrigidas sem alterar semântica;
- run `34760070032` passou Ruff/Mypy, mas a coleta do Pytest detectou ciclo de importação `gateway -> signing -> vault -> persistence -> operations -> gateway`;
- a correção tornou os novos exports de provider em `kordena_fiscal.gateway` lazy, preservando o contrato público antigo e eliminando o ciclo.

### Certificação Bloco 3

Gate definitivo:

- SHA: `42f27c67145d2d4469374596d869ffc3ba05f013`;
- run: `34760113452` — **SUCCESS**;
- job: `103731343836`;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **93 source files**;
- Pytest: **471 PASS em 3.27s**;
- baseline Bloco 2: 459; incremento líquido: **+12 testes**;
- diff B2 documental -> gate B3: 8 commits à frente, 0 atrás; gateway/provider, synthetic transport, tests e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `9e5019d64b5174ad9fe138e52c566ec3df73af84`.

## Próximos blocos

Bloco 4: timeout/retry/backoff/circuit breaker/unknown outcome. Depois, homologation gates + cross-provider e certificação end-to-end com fechamento integral da V2-12.

## Governança

A PR #13 permanece Draft. V2-12 permanece **EM EXECUÇÃO**. Sem merge, deploy, produção real, homologação externa ou cutover automático.
