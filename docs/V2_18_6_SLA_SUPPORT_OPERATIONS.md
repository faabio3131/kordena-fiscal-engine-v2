# V2-18.6 — SLA + SUPPORT + OPERATIONS

Data: 2026-09-13

Status: **EM CERTIFICAÇÃO INTERNA**.

## Escopo

A fase define **targets técnicos internos**, não compromissos contratuais finais de SLA.
Qualquer SLA comercial publicado continua sujeito à aprovação do Diretor e validação contratual.

## Severidades

- SEV1 — perda material de authority/segurança/desastre;
- SEV2 — degradação material/provider/outage/backlog/reconciliation;
- SEV3 — impacto limitado/onboarding;
- SEV4 — baixa urgência.

A implementação fornece metas técnicas de acknowledgement/update para orientar operação.

## Runbooks cobertos

- expiração de certificado;
- provider outage;
- SEFAZ outage;
- município/provider NFS-e outage;
- queue backlog;
- unknown outcome;
- sequence gap;
- reconciliation incident;
- security incident;
- customer onboarding incident;
- disaster recovery.

## Princípios operacionais

- unknown outcome nunca vira blind retry;
- sequence gap congela o escopo afetado antes de novas alocações;
- segurança preserva audit trail e faz rotação governada;
- disaster recovery restaura authority state antes de reabrir writers;
- onboarding retoma checkpoint e não bypassa readiness;
- backpressure e DLQ permanecem mecanismos governados.

## Health contract

Estados técnicos padronizados:

`operational`, `degraded`, `partial_outage`, `major_outage`, `maintenance`.

Esse contrato pode alimentar um futuro status surface sem declarar disponibilidade comercial não
medida.
