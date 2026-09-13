# V2-12 — Gateway / Signer / Vault Production Adapters

Status: **EM EXECUÇÃO — BLOCOS 1 E 2 CERTIFICADOS**  
Branch: `v2/production-adapters`  
Base certificada: `v2/control-plane` @ `0439246151c7edc959615361c0275961e11c3af0`  
Dependência: V2-11 concluída e certificada.

## Objetivo

Preparar a operação real do FM Fiscal sem acoplar o Core a fornecedor único, introduzindo ports/adapters para resolução segura de segredo, assinatura fiscal e, nos blocos posteriores, providers/gateways, resiliência e homologation gates por documento/jurisdição.

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

## Blocos desta execução autorizada

1. **Vault/KMS abstraction + Secret Resolution Boundary — CONCLUÍDO/CERTIFICADO.**
2. **Signer Boundary + assinatura por SecretReference — CONCLUÍDO/CERTIFICADO.**

## Bloco 1 — Vault/KMS abstraction + Secret Resolution Boundary

Foi criado o package `kordena_fiscal.vault` fora do domínio fiscal, preservando dependency inversion. `SecretResolutionService` lê somente a `SecretReference` governada no Control Plane e delega material runtime ao port `FiscalSecretVault`.

### Contratos e isolamento

- `SecretResolutionContext` exige `ExecutionScope` com `host_namespace`, purpose, kind e workload explícitos;
- purpose determina o kind permitido: document signing -> certificate, CSC authentication -> CSC, provider authentication -> credentials;
- tenant, unit e environment são validados contra onboarding e binding persistido;
- o adapter sintético indexa material por host + reference, impedindo reutilização cross-host;
- scopes desconhecidos não revelam existência administrativa: falham como referência indisponível;
- environment não habilitado falha por autorização;
- não existe fallback silencioso.

### Material efêmero

Foram introduzidos tipos explícitos e não persistentes:

- `EphemeralCertificateMaterial`;
- `EphemeralCscMaterial`;
- `EphemeralProviderCredentialsMaterial`.

Todos usam `slots`, `repr=False`, `eq=False` e representação redigida. Não possuem repository, serializer ou integração com UoW. O material fica exclusivamente no adapter runtime.

### Adapter sintético

`InMemorySyntheticFiscalSecretVault` existe apenas para contract tests e não lê filesystem, environment variables ou store externo. Os fixtures usam bytes declaradamente sintéticos e não utilizáveis como segredo real.

### Segurança e persistência

Os testes comprovam que:

- resolução válida funciona por reference;
- cross-host, cross-tenant, cross-unit e cross-environment falham fechado;
- kind/purpose incompatível é rejeitado;
- Vault indisponível/material ausente falham fechado;
- repr não contém material;
- resolução não acrescenta material ao audit trail;
- schema `fm_control_plane_secret_references` continua somente com reference metadata;
- restart preserva a reference, mas não o material efêmero.

### Certificação Bloco 1

Primeira tentativa: run `34758852638`, job `103727925782`. Install/Ruff/Mypy passaram e Mypy validou 88 source files; Pytest terminou com 446 PASS e 1 FAIL porque o teste esperava `SecretUnavailableError` em scope não onboarded enquanto o serviço retornava `SecretAuthorizationError`. A correção tornou scopes inexistentes indistinguíveis de reference ausente, reduzindo enumeração administrativa e preservando fail-closed.

Gate definitivo:

- SHA: `961ee84aa28f58ce933d2dd899bfd013c801da1c`;
- run: `34758902465` — **SUCCESS**;
- job: `103728060621`;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **88 source files**;
- Pytest: **447 PASS em 2.15s**;
- baseline V2-11: 437; incremento líquido: **+10 testes**;
- diff bootstrap -> gate: 7 commits à frente, 0 atrás, restrito ao Vault boundary, testes e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `cb399d0c74ae5925c4d89412a4760472fe7ab430`.

## Bloco 2 — Signer Boundary + assinatura por SecretReference

Foi criado `kordena_fiscal.signing` como boundary independente de provider e de regra tributária. O signer recebe conteúdo canônico pronto para assinatura, escopo fiscal explícito e `SecretReference` de certificado. O material criptográfico nunca vem diretamente do caller: ele é obtido exclusivamente por `SecretResolutionService` -> `FiscalSecretVault`.

### Contratos

- `FiscalSignatureRequest` exige host/tenant/unit/environment explícitos, document kind, canonical bytes, certificate reference e workload;
- certificate reference precisa ser `CERTIFICATE` e coincidir exatamente com tenant/unit/environment do scope;
- `FiscalSignatureResult` expõe somente conteúdo assinado, assinatura, algoritmo, referência opaca, fingerprint SHA-256, timestamp e document kind;
- request/result possuem `repr` sanitizado e não expõem conteúdo canônico, password ou material de chave.

### Adapter criptográfico

`CryptographyFiscalDocumentSigner` usa `cryptography` para PKCS#12, RSA/ECDSA e verificação. O adapter não implementa criptografia própria, parser de PFX próprio ou canonicalização XML improvisada.

O signer trabalha sobre bytes canônicos fornecidos pelo adapter de documento/provider. Embedding XML, transformações XMLDSig e variantes municipais/provider-specific ficam para adapters posteriores, evitando declarar uma assinatura universal falsa.

Capacidades atuais do boundary:

- NF-e e NFC-e: RSA-SHA256 ou ECDSA-SHA256 conforme a chave presente no certificado;
- NFS-e: fail-closed por padrão, pois assinatura e formato podem variar por provider/município; um adapter posterior deve habilitar explicitamente o modelo suportado;
- verification re-resolve o certificado, compara referência/fingerprint e valida a assinatura;
- alteração de conteúdo ou assinatura é detectada;
- Vault indisponível, certificado ausente, PKCS#12 inválido, signer indisponível ou capability não suportada produzem erros canônicos sanitizados.

### Dependência `cryptography`

Foi adicionada a faixa `cryptography>=44,<48`. O CI resolveu `cryptography 47.0.0`. A dependência foi adotada para evitar implementação manual de RSA/ECDSA e parsing PKCS#12. A metadata pública do PyPI classifica o projeto como Production/Stable e informa licença `Apache-2.0 OR BSD-3-Clause`; a faixa está deliberadamente limitada e futuras atualizações devem passar pelos mesmos gates antes de ampliação.

### Testes e zero secret persistence

Os testes geram chave RSA, certificado X.509 autoassinado e PKCS#12 sintéticos exclusivamente em memória durante a execução. Nenhum `.pfx`, `.p12`, `.pem` ou `.key` é comitado.

A suíte certifica:

- assinatura e verificação válidas;
- tampering de conteúdo e assinatura detectado;
- cross-tenant, cross-unit e cross-environment bloqueados;
- CSC não entra no signer como identidade de certificado;
- Vault e signer indisponíveis falham fechado;
- PKCS#12 inválido não vaza material ou password na exceção;
- NFS-e não é tratada falsamente como NF-e/NFC-e;
- schema de `SecretReference` permanece sem segredo;
- restart conserva somente reference, não material criptográfico;
- signer não possui UoW próprio nem autoridade de readiness.

### Certificação Bloco 2

Gate definitivo:

- SHA: `f27ae85ac1dbf0b5cf47eea96d1437585b37cb92`;
- run: `34759157421` — **SUCCESS**;
- job: `103728746009`;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **91 source files**;
- Pytest: **459 PASS em 3.05s**;
- baseline Bloco 1: 447; incremento líquido: **+12 testes**;
- diff do checkpoint documental do Bloco 1 -> gate: 8 commits à frente, 0 atrás; alterações restritas ao signer boundary, dependency, testes e CI temporário;
- CI restaurado para `workflow_dispatch` no commit `750dbb7e2e7f34fd55fe8a79fbda7dd422af9fb7`.

## Blocos posteriores da V2-12

Permanecem deliberadamente pendentes após esta execução:

- adapters concretos de providers/gateways;
- CSC/provider credentials por unidade/ambiente conforme provider;
- timeout/retry/circuit breaker;
- homologation gates por documento/jurisdição;
- certificação cross-provider;
- fechamento end-to-end da V2-12.

## Gate por bloco

Cada bloco exige: implementação, Ruff, Mypy strict, Pytest completo, diff auditado, SHA/run/job registrados, documentação reconciliada e CI restaurado para `workflow_dispatch`.

## Governança

A PR #13 permanece Draft. V2-12 permanece **EM EXECUÇÃO**. Sem merge, deploy, produção real, homologação externa ou cutover automático.
