# V2-15 — HOMOLOGAÇÃO + PILOTOS CONTROLADOS

Status: **EM EXECUÇÃO — PREPARAÇÃO/READINESS INTERNO**  
Branch: `v2/homologation-controlled-pilots`  
Base certificada: `v2/system-hardening` @ `15426a4460ed18c8861c807b92b98c6cfecb3126`  
Dependência: V2-14 concluída e certificada.

## Objetivo

Preparar e, somente quando houver evidência externa real e autorizada, executar homologação oficial e pilotos controlados do FM Fiscal Core por documento, provider e jurisdição. Evidência sintética/contract tests não pode ser rotulada como homologação oficial.

## Regras vinculantes

- somente `FiscalEnvironment.HOMOLOGATION` em pilotos desta fase;
- nenhum endpoint de produção, emissão produtiva ou cutover;
- segredo/certificado/CSC/credential real somente por boundaries seguros e nunca no Git;
- provider/jurisdição só pode receber status de homologado com evidência externa real correspondente;
- NFS-e permanece município/provider-specific;
- readiness técnico não promove `PRODUCTION_APPROVED`;
- ausência de credencial/certificado/CSC/provider/ambiente externo deve gerar bloqueio explícito, não certificação inventada;
- CI continua dispatch-only fora dos gates temporários.

## Blocos

1. Homologation Environment Readiness — EM EXECUÇÃO.
2. NF-e Homologation Matrix — PENDENTE.
3. NFC-e Homologation Matrix — PENDENTE.
4. NFS-e Homologation Matrix — PENDENTE.
5. Pilotos Controlados + Go/No-Go — PENDENTE.
6. Certificação/Fechamento — PENDENTE.

## Critério de fase

O trabalho interno pode ser certificado com ambientes sintéticos e contract tests. A fase somente será marcada totalmente CONCLUÍDA/CERTIFICADA se existirem evidências oficiais externas para o escopo exigido. Caso contrário, após concluir todo o trabalho interno, o status final será `BLOQUEADA PARCIAL`, com os bloqueios externos discriminados e sem promover produção.
