# V2-05 — Auth S2S, Workload Identity e Webhook Security

Status: **CONCLUÍDO E CERTIFICADO**  
Data: 2026-09-11

## Objetivo

Autenticar cada produto consumidor como workload independente, vincular a identidade autenticada ao `host_namespace` autorizado e impedir falsificação de host, tenant, unidade, capability e contexto fiscal.

O V2-05 também define assinatura/verificação de webhooks com rotação de chave e janela antirreplay, sem acoplar o FM Fiscal a um provedor de IAM, API Gateway, cloud ou vault específico.

## Princípio de autoridade

Headers e payloads recebidos do consumidor são **claims não confiáveis**. A autoridade segue obrigatoriamente:

```text
credencial de workload
        ↓ autenticação
CallerIdentity
        ↓ autorização
host namespace + capability + scope grant
        ↓ binding exato
FiscalAccountBinding
        ↓
ExecutionScope interno
```

O caller nunca escolhe diretamente `FiscalAccountId`, `FiscalUnitId`, perfil fiscal, certificado ou segredo interno.

## Identidade e credenciais

`CallerIdentity` contém `caller_id`, `host_namespace` fixo, capabilities explícitas e grants de tenant/unidade. `HostScopeGrant` permite todos os tenants/unidades do host, todas as unidades de um tenant ou uma unidade exata. Não existe grant cross-host.

`WorkloadCredentialRecord` retém somente `credential_id`, identidade do caller, SHA-256 do token de alta entropia, janela `valid_from`/`expires_at` e estado de revogação. O token bruto é apresentado na autenticação e não é armazenado pelo contrato de referência.

Múltiplos `credential_id` podem apontar para a mesma `CallerIdentity`, permitindo overlap controlado durante rotação. Credenciais desconhecidas, revogadas, futuras, expiradas ou com segredo incorreto falham fechado.

A implementação é provider-neutral. Uma implantação futura pode obter a identidade via workload identity gerenciada, mTLS, OIDC ou API Gateway sem mudar a semântica de autorização do Core.

## Autorização fail-closed

`S2SAuthorizer` exige simultaneamente:

1. caller autenticado;
2. `host_namespace` solicitado idêntico ao da identidade;
3. capability permitida;
4. tenant/unidade cobertos pelo grant;
5. rate policy aprovada, quando configurada;
6. `FiscalAccountBinding` exato existente;
7. environment e correlation válidos.

Somente depois dessas validações é criado o `ExecutionScope` fiscal interno.

Capabilities de autoridade do caller introduzidas nesta fase:

- `fiscal.issue`;
- `fiscal.query`;
- `fiscal.cancel`;
- `fiscal.inutilize`;
- `fiscal.capabilities.read`;
- `fiscal.reconcile`;
- `fiscal.archive.read`.

Capabilities/readiness funcionais do estabelecimento continuam no V2-06.

## Proteção de tenant, unidade e perfil

Tenant e unidade externos nunca são promovidos diretamente para autoridade fiscal. O binding exato converte o escopo externo em `FiscalAccountId` e `FiscalUnitId` internos. Perfil fiscal não é aceito como autoridade fornecida pelo caller; sua seleção permanece propriedade interna do FM Fiscal.

## Rate limiting e audit trail

`FixedWindowRateLimiter` fornece semântica executável de rate limit por `caller_id`. Nesta fase ele é in-memory; coordenação distribuída pertence ao runtime/persistência posterior.

Toda decisão de autorização registra timestamp, caller, credential id, host namespace, tenant, unidade, capability, resultado allowed/denied, reason code e correlation id. O sink de referência é in-memory; persistência durável e observabilidade ficam para V2-07/V2-13.

## Webhook security

`WebhookSecurity` usa HMAC-SHA256 sobre:

```text
unix_timestamp + "." + raw_body
```

Header canônico:

```text
t=<unix>,kid=<key-id>,v1=<sha256-hmac>
```

A verificação exige `key_id` conhecido, HMAC válido com comparação constant-time, assinatura dentro da janela antirreplay, tolerância limitada para clock futuro e corpo byte-for-byte idêntico. `InMemoryWebhookKeyRing` aceita múltiplas chaves, permitindo rotação com uma chave ativa de assinatura e chaves anteriores ainda válidas para verificação.

Segredos reais/vault e rotação operacional ficam no V2-12. Delivery state, retries, DLQ e inbox/outbox de webhook ficam no V2-08.

## Contrato público V1.1

O FM Fiscal Bridge foi elevado de `1.0.0` para `1.1.0` de forma aditiva:

- OpenAPI exige **dois fatores do contrato de workload**: `X-FM-Workload-Credential-Id` + `Authorization: Bearer <opaque-secret>`;
- `X-FM-Host-Namespace`, tenant, unidade e ambiente permanecem claims e não autoridade;
- todas as operações documentam 401, 403 e 429 por meio de `CanonicalError` provider-neutral;
- AsyncAPI exige `X-FM-Webhook-Signature` e registra algoritmo, janela antirreplay e rotação por `key_id`;
- `https://fiscal.invalid` continua sendo apenas placeholder não roteável; nenhum endpoint real foi declarado.

## Fail-closed certificado

A suíte cobre negativamente credencial desconhecida/incorreta/revogada/expirada/futura, spoofing cross-host, capability ausente, cross-tenant, cross-unit, binding inexistente, rate limit, webhook adulterado, webhook stale, timestamp futuro e header malformado. Também cobre rotação de credencial e rotação de chave de webhook.

## Certificação

- branch: `v2/s2s-workload-webhook-security`;
- PR: **#6 Draft**;
- base V2-04: `1eadc6d95f779b8e5e2a8eaddee03941bc18bf4a`;
- gate final: `196928d1b0cfe896df0c4741839ce72258f8f4d4`;
- GitHub Actions run: `34656535435` — **SUCCESS**;
- Install: PASS — `fm-fiscal-core==0.1.0.dev0`;
- Ruff: PASS;
- Mypy strict: PASS — **48 source files sem issues**;
- Pytest: PASS — **290 passed em 0.82s**;
- diff auditado contra V2-04: alterações limitadas a segurança S2S/webhook, contratos públicos, testes, documentação e CI temporário;
- README e demais domínios fiscais permanecem sem mudança de conteúdo em relação à base;
- nenhum merge ou deploy realizado.

Os gates intermediários `34656063690` e `34656471412` falharam exclusivamente em lint (ordenação de import e uma linha E501). As correções foram somente de formatação; o gate definitivo acima ficou integralmente verde.

## Riscos residuais governados

- capability/readiness operacional: V2-06;
- persistência durável e rate limit distribuído: V2-07/V2-11;
- delivery/retry/DLQ de webhook: V2-08;
- secret manager/vault e adapters de identidade de produção: V2-12;
- observabilidade operacional persistente: V2-13.

## Decisão

**V2-05 CONCLUÍDO E CERTIFICADO. V2-06 — Capability & Readiness API está LIBERADO.**
