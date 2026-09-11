# V2-06 — Capability & Readiness API

Status: **EM EXECUÇÃO**  
Branch: `v2/capability-readiness-api`  
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

Cada regra expõe um `capability_version` determinístico e público, derivado da versão governada e de um digest do identificador interno. O token não expõe diretamente o `rule_id`.

A proveniência pública vem de `source_normative` e é transportada pelo campo `provenance` já existente no contrato V1. A presença de uma referência normativa não promove automaticamente readiness: o nível continua sendo uma decisão explícita da regra governada.

Qualquer alteração semântica em readiness, ações, jurisdição, vigência ou proveniência deve gerar nova versão da regra; reutilizar silenciosamente a mesma versão é proibido pela governança operacional.

## Compatibilidade com o FM Fiscal Bridge

V2-06 reutiliza, sem quebra, o contrato público já existente em `contracts/v1`:

- `POST /v1/capabilities/query`;
- `CapabilityRequest`;
- `CapabilityResponse`;
- `contract_version = 1.0.0` dentro do payload canônico;
- OpenAPI do Bridge em 1.1.0 com autenticação S2S certificada no V2-05.

O `CapabilityReadinessSnapshot.to_bridge_response(...)` serializa a resposta na forma pública existente, incluindo readiness, `capability_version`, capabilities, correlation id e provenance.

A permissividade estrutural histórica de campos opcionais em `CapabilityRequest` é preservada para não introduzir breaking change no V1. A autoridade V2-06, porém, exige contexto tipado e explícito para resolver uma regra. A composição HTTP definitiva pertence ao V2-07.

## Limites desta fase

V2-06 não adiciona servidor HTTP produtivo, banco, migrations, endpoint roteável, segredo, certificado, homologação externa, promoção automática de regra ou deploy. Persistência durável e application service pertencem ao V2-07; delivery assíncrono e webhooks duráveis pertencem ao V2-08.

Nenhuma marca de consumidor entra na autoridade de capability. Kordena, Iron Fit, Vendedor IA, CampaIA e produtos futuros continuam consumidores do mesmo contrato host-neutral.

## Gate de fechamento

V2-06 só pode ser marcado `CONCLUÍDO` depois de:

- suíte nova cobrindo consulta, versionamento, readiness, ações explícitas, NFS-e municipal e fail-closed;
- contract tests garantindo aderência ao Bridge V1;
- Ruff PASS;
- Mypy strict PASS;
- Pytest completo PASS;
- CI definitivo verde com SHA e run registrados;
- auditoria do diff contra V2-05;
- riscos residuais documentados;
- PR Draft preservada, sem merge e sem deploy.
