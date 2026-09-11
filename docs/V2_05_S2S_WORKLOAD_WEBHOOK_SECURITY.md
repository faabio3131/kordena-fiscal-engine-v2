# V2-05 — Auth S2S, Workload Identity e Webhook Security

Status: **EM EXECUÇÃO**  
Data: 2026-09-11

## Objetivo

Autenticar cada produto consumidor como workload independente, vincular a identidade autenticada ao `host_namespace` autorizado e impedir falsificação de host, tenant, unidade, capability e contexto fiscal.

O V2-05 também define assinatura/verificação de webhooks com rotação de chave e janela antirreplay, sem acoplar o FM Fiscal a um provedor de IAM, API Gateway, cloud ou vault específico.

## Princípio de autoridade

Headers e payloads recebidos do consumidor são **claims não confiáveis**.

A autoridade nasce desta sequência:

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

## Contratos de identidade

`CallerIdentity` contém:

- `caller_id`;
- `host_namespace` fixo;
- capabilities explícitas;
- grants de tenant/unidade dentro do host.

`HostScopeGrant` suporta três níveis intencionais:

- todos os tenants/unidades do host;
- todas as unidades de um tenant específico;
- uma unidade exata de um tenant.

Não existe grant cross-host porque o namespace está fixado na identidade autenticada.

## Credenciais e rotação

`WorkloadCredentialRecord` armazena somente:

- `credential_id`;
- identidade do caller;
- SHA-256 de um token de alta entropia;
- janela `valid_from` / `expires_at`;
- estado de revogação.

O token bruto é aceito apenas no momento da autenticação e não é retido.

Múltiplos `credential_id` podem apontar para a mesma `CallerIdentity`, permitindo overlap controlado durante rotação. Credenciais desconhecidas, revogadas, futuras, expiradas ou com segredo incorreto falham fechado.

Este mecanismo é a implementação provider-neutral de referência. Integrações futuras podem substituir a origem da identidade por workload identity gerenciada, mTLS, OIDC ou API Gateway sem alterar a semântica de autorização.

## Autorização

`S2SAuthorizer` exige simultaneamente:

1. caller autenticado;
2. `host_namespace` solicitado idêntico ao da identidade;
3. capability permitida;
4. tenant/unidade cobertos por `HostScopeGrant`;
5. rate policy aprovada, quando configurada;
6. `FiscalAccountBinding` exato existente;
7. environment e correlation válidos.

Somente depois dessas validações é criado o `ExecutionScope` fiscal interno.

### Capabilities V2-05

- `fiscal.issue`;
- `fiscal.query`;
- `fiscal.cancel`;
- `fiscal.inutilize`;
- `fiscal.capabilities.read`;
- `fiscal.reconcile`;
- `fiscal.archive.read`.

Capabilities funcionais/readiness do estabelecimento continuam no V2-06. Aqui tratamos apenas **autoridade do caller**.

## Proteção tenant/unit/profile

Tenant e unidade externos nunca são promovidos diretamente para autoridade fiscal. O binding exato converte o escopo externo em `FiscalAccountId` e `FiscalUnitId`.

Perfil fiscal não é aceito como autoridade vinda do caller. A seleção/autorização de perfil permanece propriedade interna do FM Fiscal e será conectada ao application service/control plane nas fases correspondentes.

## Rate limiting

`FixedWindowRateLimiter` fornece semântica executável e testável de rate limit por `caller_id`.

Ele é propositalmente in-memory nesta fase. Persistência/distribuição e coordenação multi-instância pertencem ao V2-07/V2-11 e infraestrutura de runtime.

## Audit trail

Toda decisão de autorização registra:

- timestamp;
- caller;
- credential id;
- host namespace;
- tenant;
- unidade;
- capability;
- decisão allowed/denied;
- reason code;
- correlation id.

O sink de referência é in-memory. Persistência durável e observabilidade operacional ficam para V2-07/V2-13.

## Webhook security

`WebhookSecurity` usa HMAC-SHA256 sobre:

```text
unix_timestamp + "." + raw_body
```

O header canônico é:

```text
t=<unix>,kid=<key-id>,v1=<sha256-hmac>
```

A verificação exige:

- `key_id` conhecido;
- HMAC válido com comparação constant-time;
- assinatura não expirada;
- timestamp não excessivamente futuro;
- corpo byte-for-byte idêntico.

`InMemoryWebhookKeyRing` aceita múltiplas chaves simultaneamente, permitindo rotação com uma chave ativa para assinatura e chaves anteriores ainda válidas para verificação.

Segredos reais, vault e rotação operacional são V2-12. Delivery state, retries, DLQ e inbox/outbox de webhook são V2-08.

## Fail-closed obrigatório

Devem falhar:

- credencial desconhecida;
- segredo incorreto;
- credencial revogada;
- credencial fora da janela de validade;
- spoofing Kordena → Iron ou qualquer cross-host;
- capability ausente;
- tenant não autorizado;
- unidade não autorizada;
- binding inexistente;
- limite excedido;
- webhook adulterado;
- webhook stale;
- webhook com timestamp futuro além da tolerância;
- key id de webhook desconhecido.

## Fora de escopo

- escolha de provedor IAM/cloud;
- armazenamento real de segredo;
- OAuth/OIDC/JWT específico de fornecedor;
- mTLS infrastructure;
- persistência distribuída de rate limit;
- application service;
- banco/migrations;
- delivery durável de webhook;
- rules de capability/readiness fiscal do estabelecimento.

## Gate

- autenticação provider-neutral implementada;
- rotação/revogação/expiração cobertas;
- autorização capability + host + tenant + unit fail-closed;
- binding caller → host provado;
- audit trail de decisões provado;
- rate policy provada;
- assinatura e verificação de webhook provadas;
- rotação de key de webhook provada;
- contratos públicos atualizados para exigir workload auth;
- testes negativos cross-host/cross-tenant/cross-unit verdes;
- Install, Ruff, Mypy strict e Pytest verdes;
- diff auditado;
- PR Draft registrada.
