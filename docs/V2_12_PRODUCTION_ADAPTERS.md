# V2-12 — Gateway / Signer / Vault Production Adapters

Status: **EM EXECUÇÃO — BOOTSTRAP CONCLUÍDO**  
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

1. **Vault/KMS abstraction + Secret Resolution Boundary — EM EXECUÇÃO:** contratos provider-neutral, contexto autorizado, material efêmero, adapter sintético e contract tests de isolamento/zero persistence.
2. **Signer Boundary + assinatura por SecretReference — PENDENTE:** signer port, request/result tipados, integração exclusiva via Vault port, verificação/tamper detection e isolamento de escopo.

## Blocos posteriores da V2-12

- adapters concretos de providers/gateways;
- CSC/provider credentials por unidade/ambiente;
- timeout/retry/circuit breaker;
- homologation gates por documento/jurisdição;
- certificação cross-provider;
- fechamento end-to-end da V2-12.

## Gate por bloco

Cada bloco exige: implementação, Ruff, Mypy strict, Pytest completo, diff auditado, SHA/run/job registrados, documentação reconciliada e CI restaurado para `workflow_dispatch`.

## Governança

A PR da V2-12 deve permanecer Draft. Sem merge, deploy, produção real, homologação externa ou cutover automático.
