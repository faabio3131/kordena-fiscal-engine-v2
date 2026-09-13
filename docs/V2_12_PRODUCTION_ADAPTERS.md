# V2-12 — Gateway / Signer / Vault Production Adapters

Status: **CONCLUÍDA / CERTIFICADA**  
Branch: `v2/production-adapters`  
PR: `#13` — Draft  
Base certificada: `v2/control-plane` @ `0439246151c7edc959615361c0275961e11c3af0`  
Dependência: V2-11 concluída e certificada.

## Objetivo

Preparar a operação real do FM Fiscal sem acoplar o Core a fornecedor único, introduzindo ports/adapters para resolução segura de segredo, assinatura fiscal, providers/gateways, resiliência e homologation gates por documento/jurisdição, sem realizar chamada produtiva, homologação oficial externa ou persistir material sensível nesta fase.

## Princípios vinculantes certificados

- domínio permanece host-neutral, provider-neutral e secret-neutral;
- dependency inversion e fail-closed são obrigatórios;
- nenhum segredo real entra em Git, fixtures, docs, logs, SQLite, payload persistido ou snapshots;
- Control Plane armazena somente `SecretReference` opaca;
- material sensível existe somente de forma efêmera em runtime;
- signer não decide regra fiscal nem readiness;
- Vault não decide readiness;
- provider adapter não decide autorização administrativa;
- resilience não decide rejeição fiscal;
- homologation gates técnicos não substituem a autoridade central de `CapabilityReadinessService`;
- nenhum merge, deploy, produção real, homologação externa, promoção ou cutover foi executado.

## Blocos

1. **Vault/KMS abstraction + Secret Resolution Boundary — CONCLUÍDO/CERTIFICADO.**
2. **Signer Boundary + assinatura por SecretReference — CONCLUÍDO/CERTIFICADO.**
3. **Provider/Gateway adapters + CSC/Credentials — CONCLUÍDO/CERTIFICADO.**
4. **Resilience Runtime — CONCLUÍDO/CERTIFICADO.**
5. **Homologation Gates + cross-provider — CONCLUÍDO/CERTIFICADO.**
6. **Certificação end-to-end + fechamento V2-12 — CONCLUÍDO/CERTIFICADO.**

## Bloco 1 — Vault/KMS abstraction + Secret Resolution Boundary

Foi criado `kordena_fiscal.vault` fora do domínio fiscal. `SecretResolutionService` lê somente `SecretReference` governada no Control Plane e delega material runtime ao port `FiscalSecretVault`.

Tipos efêmeros explícitos: `EphemeralCertificateMaterial`, `EphemeralCscMaterial` e `EphemeralProviderCredentialsMaterial`. Todos são redigidos em `repr`, não possuem repository/serializer e não entram no UoW.

Gate definitivo: SHA `961ee84aa28f58ce933d2dd899bfd013c801da1c`, run `34758902465`, job `103728060621`, **88 source files, 447 PASS em 2.15s**. CI restaurado em `cb399d0c74ae5925c4d89412a4760472fe7ab430`.

## Bloco 2 — Signer Boundary + assinatura por SecretReference

Foi criado `kordena_fiscal.signing`. O signer recebe bytes canônicos, contexto fiscal explícito e `SecretReference`; o material PKCS#12 é obtido exclusivamente por `SecretResolutionService` -> `FiscalSecretVault`.

`CryptographyFiscalDocumentSigner` usa `cryptography>=44,<48` para PKCS#12, RSA/ECDSA e verificação. NF-e/NFC-e são explícitos; NFS-e permanece provider/jurisdição-specific e não recebe uma implementação universal artificial. Nenhum PFX/P12/PEM/KEY é persistido.

Gate definitivo: SHA `f27ae85ac1dbf0b5cf47eea96d1437585b37cb92`, run `34759157421`, job `103728746009`, **91 source files, 459 PASS em 3.05s**. CI restaurado em `750dbb7e2e7f34fd55fe8a79fbda7dd422af9fb7`.

## Bloco 3 — Provider/Gateway adapters + CSC/Credentials

`ProviderDescriptor` declara `provider_id`, document kinds, jurisdictions, environments, operations e requisitos de CSC. `ProviderRegistry` resolve exatamente um provider e falha fechado em ausência/ambiguidade. `ProviderRequest`/`ProviderResponse` não transportam segredo persistível.

`ConfiguredProviderAdapter` resolve credenciais via `SecretReferenceKind.CREDENTIALS` e CSC via `SecretReferenceKind.CSC`, sempre através do Vault boundary. `SyntheticProviderTransport` é no-network e registra somente reference ids, hashes e timeouts. `ProviderGatewayService` consulta `CapabilityReadinessService` sem promover readiness.

Falhas intermediárias: run `34759978765` (Ruff) e run `34760070032` (ciclo de importação). A correção adotou exports lazy no novo provider runtime.

Gate definitivo: SHA `42f27c67145d2d4469374596d869ffc3ba05f013`, run `34760113452`, job `103731343836`, **93 source files, 471 PASS em 3.27s**. CI restaurado em `9e5019d64b5174ad9fe138e52c566ec3df73af84`.

## Bloco 4 — Resilience Runtime

Foi criado `kordena_fiscal.resilience` e o contrato de transport passou a exigir `ProviderTimeoutPolicy` explícita com connect/read timeout. `RetryPolicy` oferece máximo de tentativas, exponential backoff, jitter e delay máximo, todos limitados e testáveis por dependências injetáveis.

QUERY/STATUS são `SAFE_RETRY`; AUTHORIZE/CANCEL/INUTILIZE são `CONDITIONAL_RETRY`. Autorização com `delivery_unknown=True` nunca é repetida automaticamente: produz `UnknownProviderOutcomeError` e exige query/reconciliation. Rejeição fiscal e erro de autenticação/validação não são tratados como indisponibilidade transitória.

`CircuitBreakerRegistry` implementa `CLOSED`, `OPEN` e `HALF_OPEN`, particionado por provider + environment + UF + município opcional.

Falhas intermediárias: run `34760512225` (Ruff E501) e run `34760572581` (Mypy retorno Any no delay), ambas corrigidas sem relaxar gates.

Gate definitivo: SHA `a3db491049d6058753ebad18d6fb62026310b1b8`, run `34760627774`, job `103732719543`, **95 source files, 483 PASS em 3.03s**. CI restaurado em `dd7d3eb5a6c718bf9576b377112b0c4a812e6159`.

## Bloco 5 — Homologation Gates + Cross-provider

Foi criado `kordena_fiscal.homologation` como camada técnica de evidência. `HomologationGateEvaluator` consulta `CapabilityReadinessService.require_action`; a matriz técnica não cria nem promove readiness.

`HomologationGateKey` é particionado por provider, document kind, jurisdiction, environment e operation. A matriz exige correspondência exata. Para NFS-e, município IBGE explícito é obrigatório; não existe cobertura municipal universal inferida.

`HomologationEvidence` cobre adapter disponível, credential reference, signer capability, CSC quando aplicável, transport, resilience, contract tests, jurisdiction mapping e operação suportada. Configuração parcial permanece `CONTRACT_READY`; somente evidência completa produz `TECHNICALLY_CERTIFIED`, e ainda assim a execução depende da autoridade central.

Gate definitivo: SHA `ae9347b2f97f6984e22f6a719eec5e4b1ea8a3db`, run `34760988165`, job `103733669977`, **97 source files, 497 PASS em 3.41s**. CI restaurado em `e2c89a602c85c104e668f8bb3cc469161ed4b408`.

## Bloco 6 — Certificação End-to-End + fechamento V2-12

### Auditoria e correção cross-provider

A auditoria end-to-end encontrou um ponto que precisava ser endurecido antes do fechamento: credenciais e CSC já eram isolados por host/tenant/unit/environment/kind, porém o slot runtime ainda não incluía `provider_id`. Isso poderia permitir que dois providers do mesmo escopo administrativo consumissem o mesmo material runtime.

A correção foi aplicada sem alterar o schema V2-11 e sem persistir provider secret material:

- `SecretResolutionContext` passou a exigir `provider_id` para `PROVIDER_AUTHENTICATION` e `CSC_AUTHENTICATION`;
- o Vault sintético indexa material provider-scoped por `(host, reference_id, provider_id)`;
- CREDENTIALS/CSC não possuem fallback entre providers;
- certificado de assinatura continua provider-independent;
- `ConfiguredProviderAdapter` injeta sempre seu `descriptor.provider_id` na resolução;
- o Control Plane continua guardando somente a referência opaca por tenant/unit/environment/kind.

Novos testes provam que provider A e B podem compartilhar a mesma referência opaca como namespace externo, mas recebem slots de material distintos no Vault, e provider sem slot exato falha fechado antes do transport.

### Certificação end-to-end

`tests/control_plane/test_v2_12_closure.py` certifica:

- NF-e: Control Plane -> SecretReference -> Vault -> Signer -> Provider -> Resilience -> resposta normalizada;
- NFC-e: o mesmo fluxo com CSC provider-scoped obrigatório;
- NFS-e: query municipal/provider-specific, sem inventar signer universal;
- outcome desconhecido de autorização: uma única tentativa e reconciliação obrigatória;
- restart: referências sobrevivem, material efêmero não;
- SQLite: somente metadados de referência, sem PFX/password/credentials/CSC runtime;
- structural secret scan: ausência de `.pfx`, `.p12`, `.pem`, `.key` e PEM private material no repositório;
- architecture audit: domínio não importa Vault/Gateway/Signer/Resilience/Homologation/cryptography;
- cross-product neutrality: adapters não dependem de Iron Fit, Vendedor IA ou CampaIA;
- dependency audit: dependências produtivas limitadas a `cryptography>=44,<48` e `lxml>=5.3,<7`.

Primeira tentativa B6: run `34762578767`, job `103737871189`, Install PASS e Ruff falhou por duas linhas E501 na nova suíte; Mypy/Pytest foram corretamente bloqueados. A formatação foi corrigida sem alterar regras de lint.

Gate funcional definitivo B6:

- SHA: `b7bccf2babed336941d920eed73cd0699e6939d4`;
- run: `34762735800` — **SUCCESS**;
- job: `103738293942`;
- Install: PASS;
- Ruff: PASS;
- Mypy strict: PASS — **97 source files**;
- Pytest: **508 PASS em 5.06s**;
- baseline B5: 497; incremento líquido: **+11 testes**;
- CI restaurado para `workflow_dispatch` no commit `0e232f63d052db6ca2a7c8cd6ef5d97e3fdf0032`.

### Gate de fechamento documental

Após reconciliar plano, tracker, closure record e corpo da PR, a regressão completa foi executada novamente no SHA `8cbd4f974a6e72e3f99557d6481c9267a3e8ef81`, run `34762972272`, job `103738907041`: **Install PASS, Ruff PASS, Mypy strict PASS em 97 source files e 508 PASS em 4.12s**. O CI foi restaurado definitivamente no commit `75dece2ed83d323834617857f943e3373bc6ecb8` para o blob dispatch-only `b161340d7164afcbf3da0eb0327135528a39450c`.

## Auditoria integral V2-11 -> V2-12

Compare funcional `0439246151c7edc959615361c0275961e11c3af0` -> `b7bccf2babed336941d920eed73cd0699e6939d4`:

- **68 commits à frente, 0 atrás**;
- **29 arquivos líquidos** no gate funcional, incluindo o CI temporariamente habilitado;
- **5.046 adições / 15 remoções**;
- alterações limitadas a documentação/tracker/snapshot, `pyproject.toml`, boundaries `vault/signing/gateway/resilience/homologation` e testes correspondentes;
- nenhuma migration nova;
- nenhuma alteração em `src/kordena_fiscal/domain`;
- nenhum provider SDK produtivo ou endpoint externo real;
- nenhuma chave/certificado/CSC/token/credential real;
- nenhuma dependência privada de SaaS no runtime universal.

O diff documental final agrega somente registros de fechamento e restauração do CI; não altera o comportamento funcional certificado pelo gate B6.

## Dependências e limites

Dependências produtivas adicionadas/confirmadas nesta fase:

- `cryptography>=44,<48`: PKCS#12, RSA/ECDSA, assinatura e verificação;
- `lxml>=5.3,<7`: infraestrutura XML já utilizada pelo Core.

A V2-12 certifica os boundaries e o comportamento fail-closed necessários para adapters produtivos. Credenciais/certificados reais, endpoints reais, homologação oficial externa e aprovação de produção não foram usados nem simulados como concluídos; pertencem às etapas operacionais/homologação posteriores do Plano Mestre.

O warning do GitHub Actions sobre transição Node 20 -> Node 24 é de infraestrutura das actions e não representou falha de qualidade do código.

## Governança final

A PR #13 deve permanecer **OPEN / DRAFT / não mergeada**. Não houve merge, deploy, produção real, homologação oficial externa, promoção automática ou cutover. A próxima fase do cronograma é V2-13 e permanece **PENDENTE**, aguardando autorização explícita.
