# V2-18.7 — LGPD + RETENTION + LEGAL/COMPLIANCE PACKAGE

Data: 2026-09-13

Status: **EM CERTIFICAÇÃO INTERNA — DRAFT TÉCNICO, NÃO PARECER JURÍDICO**.

## Escopo técnico auditado

- account identity;
- fiscal profile;
- fiscal documents;
- audit trail;
- operational telemetry;
- webhook metadata;
- billing metadata;
- secret references;
- backups;
- export/portability boundaries;
- deletion restrictions;
- legal hold capability;
- access control/subprocessor boundaries como requisito contratual futuro;
- incident logging e backup governance.

## Retention matrix

A implementação não inventa prazo legal. Categorias que dependem de interpretação jurídica,
contábil, fiscal, privacy ou política contratual recebem explicitamente:

`LEGAL_VALIDATION_REQUIRED`

Fiscal documents, fiscal profiles, audit evidence, webhook delivery evidence, billing metadata e
backups possuem deletion restrictions técnicas até existir política aprovada.

## Secrets

FM Fiscal armazena **referências**, não raw private keys, PFX password, CSC ou bearer secrets na
superfície comercial. Secret references não são customer-exportable.

## Portability/export

O pacote técnico permite classificar como exportáveis, por contrato:

- account identity;
- fiscal profile;
- fiscal document references/content conforme autoridade e política aprovada;
- billing metadata quando aplicável.

Audit/security evidence e secret references não são exportados como se fossem dados comuns de
conta.

## Draft técnico de responsabilidades

### Customer responsibilities

- fornecer dados empresariais/fiscais corretos;
- manter authority legítima sobre dados enviados;
- proteger credenciais do cliente;
- configurar usuários/roles;
- atender requisitos de certificado/CSC/provider quando aplicável.

### FM Fiscal responsibilities

- isolamento tenant/host/unit;
- segurança de processamento;
- trilha de auditoria;
- integridade de archive/lifecycle;
- gestão reference-only de material sensível;
- suporte a export/retention conforme política aprovada;
- incident logging e runbooks.

### Provider/subprocessor responsibilities

Devem ser documentadas por contrato e registro de subprocessadores antes de produção comercial.
Esta fase não inventa lista jurídica nem DPA final.

## Pendências humanas

- política de privacidade final: `LEGAL_VALIDATION_REQUIRED`;
- DPA/termos: `LEGAL_VALIDATION_REQUIRED`;
- retention periods definitivos: `LEGAL_VALIDATION_REQUIRED`;
- base legal/finalidades: `LEGAL_VALIDATION_REQUIRED`;
- subprocessadores e transferências: `LEGAL_VALIDATION_REQUIRED`;
- revisão por advogado/contador/DPO quando aplicável: `LEGAL_VALIDATION_REQUIRED`.

Essas validações não bloqueiam a conclusão da engenharia técnica, mas bloqueiam a declaração de
pacote jurídico final aprovado.
