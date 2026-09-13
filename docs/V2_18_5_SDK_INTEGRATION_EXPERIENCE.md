# V2-18.5 — SDKs + INTEGRATION EXPERIENCE

Data: 2026-09-13

Status: **EM CERTIFICAÇÃO INTERNA**.

## Python SDK

Pacote público: `fm_fiscal_sdk`.

O SDK é deliberadamente fino e independente do pacote privado do Core. Ele fornece:

- Bridge request construction;
- workload credential header;
- bearer transport header;
- host/tenant/unit/environment scope;
- correlation/causation;
- stable idempotency;
- transport-only retry policy;
- capability query;
- issuance/query/reconciliation helpers;
- HMAC-SHA256 webhook verification.

Nenhuma regra tributária, provider selection, readiness promotion ou acesso a banco privado existe
no SDK.

## TypeScript SDK

Referência inicial em `sdks/typescript/src/index.ts` com os mesmos contratos públicos de scope,
headers e endpoints. A implementação não importa domínio privado do Core.

## Retry safety

O cliente só repete erros explicitamente classificados como **transport retryable**. Erros fiscais
semânticos não são automaticamente transformados em retry. Mutations reutilizam a mesma chave de
idempotência.

## Exemplos

Todos os testes e exemplos usam identifiers e tokens sintéticos. O SDK aceita credencial em runtime,
mas não contém credencial, certificado, CSC ou endpoint privado hardcoded.
