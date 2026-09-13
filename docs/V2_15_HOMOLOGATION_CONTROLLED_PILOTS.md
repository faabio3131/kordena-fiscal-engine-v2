# V2-15 — HOMOLOGAÇÃO + PILOTOS CONTROLADOS

Status: **EM EXECUÇÃO — REMEDIAÇÃO DE CONFIGURABILIDADE COMERCIAL / ZERO-CODE ONBOARDING**  
Branch: `v2/homologation-controlled-pilots`  
Base certificada: `v2/system-hardening` @ `15426a4460ed18c8861c807b92b98c6cfecb3126`  
Dependência: V2-14 concluída e certificada.  
Auditoria vinculante: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

## Objetivo

Preparar e, somente quando houver evidência externa real e autorizada, executar homologação oficial e pilotos controlados do FM Fiscal Core por documento, provider e jurisdição. Antes disso, certificar que o FM Fiscal é comercialmente configurável e que o onboarding de novos clientes não exige alteração de código para diferenças fiscais já suportadas pela plataforma.

## Regra comercial superior

**Onboarding de cliente é configuração, não desenvolvimento.**

Tudo que varia apenas por host/cliente/tenant/unidade/ambiente/documento/jurisdição/município/provider/credencial/operação deve ser resolvido por configuração persistida e governada quando a capacidade correspondente já existe na plataforma.

Código novo só é admissível para evolução reutilizável do produto, como novo protocolo/provider ou nova capacidade fiscal universal. Regra fiscal/legal não pode virar campo arbitrário do cliente: deve permanecer em catálogos governados, versionados e auditáveis.

## Regras vinculantes

- mesmo source/binário deve atender clientes fiscalmente distintos por configuração;
- nenhum `if customer == ...` / `if tenant == ...` ou migration específica de cliente;
- somente `FiscalEnvironment.HOMOLOGATION` em pilotos desta fase;
- nenhum endpoint de produção, emissão produtiva ou cutover;
- segredo/certificado/CSC/credential real somente por boundaries seguros e nunca no Git;
- Control Plane persiste referências/metadados, não material secreto;
- provider/jurisdição só pode receber status de homologado com evidência externa real correspondente;
- NFS-e permanece município/provider-specific;
- readiness técnico não promove `PRODUCTION_APPROVED`;
- ausência de credencial/certificado/CSC/provider/ambiente externo deve gerar bloqueio explícito, não certificação inventada;
- tax/readiness/legal rules são catálogos governados, não configuração normativa livre do tenant;
- CI continua dispatch-only fora dos gates temporários.

## Blocos

0. **Commercial Configurability Audit + Zero-Code Customer Onboarding — AUDITORIA CONCLUÍDA / REMEDIAÇÃO EM EXECUÇÃO.**
1. Homologation Environment Readiness — AGUARDANDO GATE B0.
2. NF-e Homologation Matrix — PENDENTE.
3. NFC-e Homologation Matrix — PENDENTE.
4. NFS-e Homologation Matrix — PENDENTE.
5. Pilotos Controlados + Go/No-Go — PENDENTE.
6. Certificação/Fechamento — PENDENTE.

## B0 — Commercial Configurability + Zero-Code Onboarding

A revisão acumulada V2-00 -> V2-15 constatou que a fundação é majoritariamente parametrizada, porém a composição comercial durável ainda possui gaps que poderiam forçar configuração em bootstrap/runtime para clientes reais.

Remediações bloqueantes identificadas:

1. `SecretReference` provider-scoped para CREDENTIALS/CSC no Control Plane;
2. ProviderBinding/FiscalCapabilityBinding durável por tenant/unit/environment/document/jurisdiction/operation;
3. persistência/CRUD de `FiscalProductProfile`;
4. enablement durável de documentos/operações/módulos por unidade;
5. webhook destination config;
6. workload identity/grants/config de credencial administrável;
7. homologation evidence records duráveis;
8. numbering config;
9. policy profiles governados para timeout/retry/circuit/rate-limit;
10. catálogos legais/readiness/tax versionados e governados, sem edição normativa arbitrária pelo tenant.

O gate B0 exige um teste E2E com ao menos três clientes sintéticos fiscalmente diferentes (restaurante/SP, academia/serviços/NFS-e municipal e varejo/MG), configurados e persistidos sem alteração do source entre eles. Após restart, cada cliente deve continuar resolvendo exclusivamente sua configuração, provider e SecretReferences; cross-tenant/unit/provider/environment deve falhar fechado.

Detalhamento e severidades: `docs/V2_15_COMMERCIAL_CONFIGURABILITY_AUDIT.md`.

## B1 — Homologation Environment Readiness

Somente iniciar após B0 verde. Auditar ambiente HOMOLOGATION, provider catalog/bindings, Vault refs, signer, CSC, credentials, transport/TLS/schema/jurisdiction/readiness/telemetria e distinguir evidência técnica interna de evidência oficial externa.

## Critério de fase

O trabalho interno pode ser certificado com ambientes sintéticos e contract tests. A fase somente será marcada totalmente CONCLUÍDA/CERTIFICADA se existirem evidências oficiais externas para o escopo exigido. Caso contrário, após concluir todo o trabalho interno, o status final será `BLOQUEADA PARCIAL`, com os bloqueios externos discriminados e sem promover produção.

A V2-15 não pode avançar para homologação externa/pilotos enquanto o gate B0 Zero-Code Customer Onboarding não estiver certificado.
