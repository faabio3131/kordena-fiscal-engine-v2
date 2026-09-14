# V2-18.3 — SELF-SERVICE ONBOARDING

Data: 2026-09-13

Status: **EM CERTIFICAÇÃO INTERNA**.

## Fluxo governado

O onboarding comercial utiliza uma sequência explícita e resumível:

1. organização;
2. empresa;
3. tenant;
4. unidade;
5. usuários/roles;
6. ambiente;
7. fiscal profile;
8. document capabilities;
9. certificate reference;
10. CSC reference;
11. provider binding;
12. webhook configuration;
13. workload/API provisioning reference;
14. readiness checklist.

## Propriedades

- ordenado e fail-closed;
- evidências armazenadas apenas como referências;
- retry da mesma etapa é idempotente;
- alteração conflitante é recusada;
- checkpoint/restore permite interrupção e retomada;
- produção exige readiness explícito depois do checklist completo;
- homologação não pode receber flag de production readiness;
- onboarding finalizado torna-se imutável.

## Secret boundary

O fluxo não recebe material de certificado, CSC ou credencial. Apenas identifiers/references seguros
são aceitos. Material secreto continua sob Vault/Secret Manager aprovado.

## Relação com o Control Plane

Esta camada representa a jornada self-service comercial. Ela não substitui as authorities do
Control Plane já certificadas; seu papel é conduzir a configuração até as referências e gates que
essas authorities validam.
