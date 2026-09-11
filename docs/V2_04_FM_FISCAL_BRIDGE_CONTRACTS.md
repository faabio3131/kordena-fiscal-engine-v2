# V2-04 — FM Fiscal Bridge: contratos públicos language-neutral

Status: **CONCLUÍDO E CERTIFICADO**  
Data: 2026-09-11

## Objetivo

Criar uma fronteira pública versionada que possa ser consumida por Python, TypeScript ou qualquer stack futura sem importar o pacote Python do Core, acessar banco interno ou depender de tipos de provedor.

## Artefatos públicos

O contrato v1 vive em `contracts/v1/`:

- `manifest.json` — versão, readiness e política de compatibilidade;
- `openapi.json` — superfície HTTP OpenAPI 3.1;
- `asyncapi.json` — superfície de eventos AsyncAPI 3.0;
- `schemas/fm-fiscal.schema.json` — JSON Schema Draft 2020-12 com os tipos canônicos.

A versão inicial é `1.0.0`. Mudança incompatível exige novo diretório major (`contracts/v2/`). Mudanças aditivas compatíveis podem evoluir dentro de `v1`.

## Princípio arquitetural

```text
produto consumidor
      ↓ HTTP / eventos
FM Fiscal Bridge
      ↓ tradução / binding
FM Fiscal Core
```

A ponte conhece contratos públicos. O Core não conhece Kordena, Iron, Vendedor IA, CampaIA nem qualquer domínio privado de host.

## Identidade de escopo no transporte

O OpenAPI carrega a identidade externa em headers explícitos:

- `X-FM-Host-Namespace`;
- `X-FM-Tenant-Id`;
- `X-FM-Unit-Id`;
- `X-FM-Environment`;
- `X-Correlation-Id`;
- `X-Causation-Id` opcional.

Operações mutáveis também exigem `Idempotency-Key`.

Esses headers **não constituem autorização** no V2-04. O V2-05 deve autenticar a workload e provar que ela pode declarar o host/tenant/unidade recebidos antes de qualquer binding para o Core.

## Contratos HTTP cobertos

O OpenAPI v1 define contratos para:

- emissão;
- consulta;
- cancelamento;
- inutilização;
- capabilities/readiness;
- reconciliação;
- archive reference.

Os endpoints são contrato, não promessa de runtime já implantado. O `servers` usa domínio `.invalid` propositalmente e o documento marca `x-fm-contract-readiness: CONTRACT_ONLY`.

## Contrato de emissão

A emissão recebe:

- `FiscalOperation` neutra do V2-03;
- tipo solicitado `nfe`, `nfce` ou `nfse`;
- linhas econômicas neutras com `item_reference`;
- destinatário fiscal genérico quando aplicável.

O contrato público não aceita regras tributárias, CST/CFOP calculados pelo host, classes Python, XML de provedor, certificado ou segredo. Classificação e decisão fiscal permanecem autoridade do FM Fiscal.

## Erro canônico

`CanonicalError` é independente de provedor e contém:

- `code`;
- `category`;
- `message`;
- `retryable`;
- `correlation_id`;
- `details`.

Mensagens internas ou payloads privados de fornecedor não fazem parte do contrato público.

## Eventos

O AsyncAPI v1 define envelopes para:

- `fiscal.issuance.updated`;
- `fiscal.document.authorized`;
- `fiscal.document.rejected`;
- `fiscal.document.cancelled`;
- `fiscal.reconciliation.updated`;
- `fiscal.archive.reference.created`.

O envelope preserva host scope, `correlation_id`, `causation_id` e `idempotency_key` quando aplicável. A entrega durável, retries, DLQ, inbox/outbox e estado de webhook pertencem ao V2-08.

## Capabilities

O V2-04 congela apenas o formato do contrato. A autoridade operacional e a lógica de readiness serão implementadas no V2-06. Os estados públicos já reservados são:

- `CONTRACT_ONLY`;
- `HOMOLOGATION_READY`;
- `PRODUCTION_APPROVED`.

## Fora de escopo

- autenticação S2S/workload identity e autorização: V2-05;
- lógica real de capabilities/readiness: V2-06;
- application service e persistência: V2-07;
- delivery de eventos/webhooks/inbox/outbox: V2-08;
- adapters concretos de produtos FM: V2-10/V2-16;
- endpoints reais, DNS, deploy ou credenciais.

## Gate

- artefatos JSON parseáveis;
- OpenAPI 3.1 versionada;
- JSON Schema 2020-12 canônico;
- AsyncAPI 3.0 versionada;
- contratos de emissão, consulta, cancelamento, inutilização, capabilities, reconciliação e archive reference presentes;
- headers de idempotency/correlation/causation e escopo presentes;
- erro canônico provider-neutral;
- nenhum contrato público contém namespace ou import de Kordena;
- testes de contract lint verdes;
- Install, Ruff, Mypy strict e Pytest verdes;
- diff auditado;
- PR Draft registrada.

## Certificação

- PR #5 criada em Draft sobre V2-03;
- base: `5014bbfe838f22137451b05203f4b0449061c6f8`;
- gate final SHA: `86689b3d3d7d47740b56bcc22594aa8c8e0b08c7`;
- GitHub Actions run `34655024269`: **SUCCESS**;
- Install: PASS — `fm-fiscal-core==0.1.0.dev0`;
- Ruff: PASS;
- Mypy strict: PASS — **47 source files sem issues**;
- Pytest: PASS — **269 passed em 0.72s**;
- diff auditado contra V2-03 e restrito a contratos públicos, documentação, contract tests e CI temporário;
- nenhuma alteração em `src/` nesta fase;
- CI retornado a `workflow_dispatch` após o gate verde.

## Decisão

V2-04 está **CONCLUÍDO E CERTIFICADO**. A fronteira pública do FM Fiscal passa a ser `contracts/v1/`, independente de linguagem e sem autoridade de segurança implícita. V2-05 — Auth S2S + workload identity + webhook security está liberado.
