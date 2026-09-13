# V2-15 B1 — HOMOLOGATION ENVIRONMENT READINESS

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**  
Escopo: ambiente `HOMOLOGATION` exclusivamente.  
Homologação oficial externa: **NÃO DECLARADA / NÃO EXECUTADA**.

## Objetivo

Certificar que a configuração comercial durável de cada tenant/unidade consegue resolver de forma exata e fail-closed os pré-requisitos técnicos de homologação, sem hardcode por cliente e sem promover readiness técnico para homologação oficial ou produção.

## Implementação certificada

Foi introduzido `DurableHomologationEnvironmentReadinessService` em `kordena_fiscal.runtime.homologation_readiness`, fora do núcleo do Control Plane. O serviço audita, para uma combinação exata de tenant, unidade, ambiente, documento, jurisdição e operação:

- unidade e ambiente habilitados;
- ProviderBinding persistido e habilitado;
- ProviderDescriptor/capability compatível;
- credencial do provider por `SecretReference` provider-scoped;
- policy durável de timeout/retry/circuit;
- evidência técnica durável;
- certificado por referência quando signer é requerido;
- CSC por referência provider-scoped quando requerido;
- separação explícita entre `internally_ready` e `officially_homologated`.

O serviço rejeita escopo `PRODUCTION` e não oferece fallback entre provider, jurisdição, tenant, unidade ou ambiente.

## Evidências de teste

Os testes de B1 certificam:

- restart/durability da configuração;
- readiness técnico interno sem alegar evidência oficial externa;
- ausência de fallback de credencial entre providers;
- resolução municipal exata para NFS-e;
- rejeição de escopo de produção;
- evidência registrada não mascara runtime policy ausente.

## Gate B1

- SHA: `4bd07f94db7c0d5e05c7896adbfc8ff80d377ac3`
- Run: `34776243989`
- Job: `103774775120`
- Install: PASS
- Ruff: PASS
- Mypy strict: PASS — **110 source files**
- Pytest: **597 PASS em 6.19s**
- CI restaurado posteriormente para `workflow_dispatch` only.

## Limite de certificação

Este bloco certifica readiness **técnico interno** com dados sintéticos e contract tests. Nenhum provider, UF, município ou operação recebe status de homologação oficial externa sem evidência externa real correspondente. Nenhum endpoint produtivo, emissão produtiva, deploy ou cutover foi utilizado.
