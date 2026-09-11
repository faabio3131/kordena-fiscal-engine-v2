# V2-06 — Capability & Readiness API

Status: **CONCLUÍDO E CERTIFICADO**  
Branch: `v2/capability-readiness-api`  
PR: **#7 Draft**  
Gate definitivo: `e6c7b2b9e507116ef4919812153f8e54f84173f3`  
Actions run: `34659021574` — **SUCCESS**  
Dependências certificadas: V2-02, V2-04 e V2-05.

## Objetivo

Transformar a capability/readiness já prevista no FM Fiscal Bridge em uma autoridade consultável e fail-closed. O consumidor pergunta ao FM Fiscal o que pode executar em um contexto explícito; nenhum SaaS pode inferir localmente documento, ação, jurisdição, ambiente ou nível de prontidão.

## Autoridade canônica

A autoridade parte de `JurisdictionCapabilityMatrix` e de regras `JurisdictionCapabilityRule` versionadas. V2-06 adiciona ações fiscais explícitas por regra e o `CapabilityReadinessService` como superfície canônica de consulta e autorização.

Contexto mínimo governado:

- família documental: NF-e, NFC-e ou NFS-e;
- UF;
- município IBGE quando existir regra municipal aplicável;
- ambiente: homologação ou produção;
- instante efetivo da consulta;
- ação fiscal requerida, quando houver execução.

A resolução permanece sem fallback nacional implícito. Regra municipal mais específica pode prevalecer sobre regra estadual; ausência ou ambiguidade continua sendo erro fail-closed.

## Ações explícitas

`FiscalActionCapability` declara as ações públicas já previstas pelo Bridge:

- `issue`;
- `query`;
- `cancel`;
- `inutilize`;
- `contingency`;
- `reconcile`;
- `archive_reference`.

A família documental não implica nenhuma ação. Uma regra pode declarar NF-e, NFC-e ou NFS-e e ainda assim não autorizar emissão, cancelamento ou qualquer outra operação.

## Readiness

Os níveis permanecem os três estados canônicos já certificados no baseline regulatório:

- `CONTRACT_ONLY`: contrato e representação existem, mas o contexto não está autorizado para execução;
- `HOMOLOGATION_READY`: execução pode ser liberada somente em homologação e apenas para ações explicitamente declaradas;
- `PRODUCTION_APPROVED`: execução em produção exige regra de produção explicitamente aprovada e a ação também declarada.

`CapabilityReadinessService.require_action(...)` aplica esse gate. Em homologação exige no mínimo `HOMOLOGATION_READY`; em produção exige `PRODUCTION_APPROVED`.

## Versionamento e proveniência

Cada regra expõe um `capability_version` determinístico e público. O token incorpora a versão governada e um fingerprint SHA-256 truncado do conteúdo semântico da regra, incluindo jurisdição, documento, ambiente, readiness, modo de validação, vigência, prioridade, ações e proveniência.

Consequência: mesmo uma alteração semântica indevida sem incremento do número de versão muda o fingerprint público, evitando que consumidores confundam duas declarações semanticamente distintas. O identificador interno `rule_id` não é exposto diretamente.

A proveniência pública vem de `source_normative` e é transportada pelo campo `provenance` já existente no contrato V1. A presença de uma referência normativa não promove automaticamente readiness: o nível continua sendo uma decisão explícita da regra governada.

A governança continua exigindo incremento de versão para alterações semânticas; o fingerprint é uma defesa adicional, não substituto do versionamento formal.

## Compatibilidade com o FM Fiscal Bridge

V2-06 reutiliza, sem quebra, o contrato público já existente em `contracts/v1`:

- `POST /v1/capabilities/query`;
- `CapabilityRequest`;
- `CapabilityResponse`;
- `contract_version = 1.0.0` dentro do payload canônico;
- OpenAPI do Bridge em 1.1.0 com autenticação S2S certificada no V2-05.

O `CapabilityReadinessSnapshot.to_bridge_response(...)` serializa a resposta na forma pública existente, incluindo readiness, `capability_version`, capabilities, correlation id e provenance.

A permissividade estrutural histórica de campos opcionais em `CapabilityRequest` foi preservada para não introduzir breaking change no V1. A autoridade V2-06, porém, exige contexto tipado e explícito para resolver uma regra. A composição HTTP definitiva pertence ao V2-07.

## Certificação

Gate definitivo executado sobre o SHA `e6c7b2b9e507116ef4919812153f8e54f84173f3` no run `34659021574`:

- Install: **PASS**;
- Ruff: **PASS** — `All checks passed!`;
- Mypy strict: **PASS** — `Success: no issues found in 49 source files`;
- Pytest completo: **305 PASS em 0.85s**.

O baseline V2-05 possuía 290 testes; V2-06 adicionou 15 testes novos cobrindo autoridade de capability/readiness, versionamento semântico e compatibilidade do contrato público.

## Auditoria do diff

Comparação final contra `v2/s2s-workload-webhook-security` no gate:

- branch estava 14 commits à frente e 0 atrás;
- alterações restritas a compliance/capability, exports, testes, documentação/tracker e ativação temporária do CI de PR;
- nenhum contrato público existente foi quebrado ou versionado artificialmente;
- nenhuma mudança em providers, emissão, numeração, archive, lifecycle, reconciliação, segurança S2S ou assinatura de webhook;
- nenhum segredo, endpoint produtivo, migration, banco ou dependência nova foi introduzido.

## Riscos residuais governados

- V2-06 não persiste nem distribui regras dinamicamente; persistência durável pertence ao V2-07 e governança de control plane ao V2-11;
- a composição HTTP/transport do endpoint público pertence ao V2-07;
- não há regras reais promovidas para produção nesta fase; os cenários `PRODUCTION_APPROVED` da suíte são sintéticos e validam apenas a semântica do gate;
- promoção operacional real depende de evidência oficial, adapters e homologação controlada nas fases posteriores;
- cobertura nacional/municipal real será alimentada por regras governadas, não por fallback implícito.

## Limites desta fase

V2-06 não adiciona servidor HTTP produtivo, banco, migrations, endpoint roteável, segredo, certificado, homologação externa, promoção automática de regra ou deploy. Persistência durável e application service pertencem ao V2-07; delivery assíncrono e webhooks duráveis pertencem ao V2-08.

Nenhuma marca de consumidor entra na autoridade de capability. Kordena, Iron Fit, Vendedor IA, CampaIA e produtos futuros continuam consumidores do mesmo contrato host-neutral.

## Decisão

**V2-06 está CONCLUÍDO E CERTIFICADO. V2-07 — Application service + persistência durável fica LIBERADO. PR #7 permanece Draft, sem merge e sem deploy.**
