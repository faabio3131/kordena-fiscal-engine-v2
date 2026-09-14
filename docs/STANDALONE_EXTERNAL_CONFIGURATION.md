# FM Fiscal — Standalone External Configuration

Status: configuração interna implementada para eliminar alterações de código por cliente dentro das capacidades já suportadas.

## Objetivo

Novo cliente/tenant/unidade deve entrar por **dados + referências seguras + evidências**, e não por alteração de fonte.

A regra é:

> se o tipo de documento, jurisdição e provider/profile já são suportados pela plataforma, cadastrar um novo cliente não exige novo adapter, commit ou deploy específico do cliente.

Novas integrações de provider/protocolo ainda podem exigir evolução de plataforma; diferenças de cliente dentro de integrações suportadas não exigem código.

## Duas camadas de configuração

### PlatformExternalConfiguration

Configuração global da FM Tecnologia:

- deployment profile;
- URL pública HTTPS;
- referência da conta cloud;
- referência de controle DNS;
- referência do backend de secrets;
- referência da conta do gateway comercial;
- evidência/referência de ativação de produção.

Nenhum segredo é armazenado nesse objeto.

### TenantExternalConfiguration

Snapshot imutável e versionado por tenant/unidade:

- `tenant_id`, `company_id`, `unit_id`;
- canais NF-e, NFC-e e NFS-e habilitados;
- ambiente homologation/production;
- UF e/ou município;
- `provider_profile_id`;
- referência de certificado;
- referências de CSC ID/token para NFC-e;
- referência de credencial do provider;
- evidência de homologação oficial;
- gateway/account/webhook secret por referência;
- oferta, edição e preço configuráveis;
- aprovação jurídica por referência/evidência;
- aprovação de piloto real;
- ativação de produção.

## Estados externos

Cada dependência externa usa um dos estados:

- `missing`: ainda não fornecida;
- `configured`: referência cadastrada, mas não verificada;
- `verified`: referência verificada e acompanhada de `evidence_reference`.

`verified` sem evidência é rejeitado.

Configuração presente **não** significa homologação, readiness ou produção aprovada.

## Regras fiscais

- NF-e/NFC-e exigem UF;
- NFS-e exige código de município;
- CSC é aceito somente para NFC-e;
- readiness externo do canal exige certificado, credencial/provider e homologação verificados;
- NFC-e exige adicionalmente CSC ID + CSC token verificados;
- canais desabilitados não participam de production readiness.

## Preço e cobrança

Preço deixa de ser decisão de código. `CommercialOfferConfiguration` suporta:

- `fixed`;
- `per_document`;
- `tiered`;
- `custom`;
- moeda;
- valor base;
- valor por documento;
- referência externa para tabela/proposta/checkout.

O gateway permanece desacoplado por `gateway_profile_id` e referências externas.

## Versionamento e concorrência

`TenantConfigurationRegistry` aplica optimistic concurrency:

- primeiro snapshot começa em versão 1;
- atualizações incrementam uma versão por vez;
- `expected_version` incorreto falha fechado;
- snapshots são imutáveis.

Em produção, a mesma semântica deve ser preservada pelo repositório durável de configuração.

## O que fica externo, mas não exige código

Os seguintes itens podem permanecer pendentes sem bloquear desenvolvimento adicional:

- certificado real;
- CSC;
- credenciais SEFAZ/prefeitura/provider;
- evidência de homologação oficial;
- conta cloud;
- DNS/domínio;
- conta de gateway;
- preço final;
- aprovação jurídica;
- piloto real;
- ativação de produção.

Quando esses itens existirem, o objetivo é apenas registrar/provisionar suas referências e evidências no perfil correspondente.

## Segurança

- certificado PFX/PEM, senha, CSC token, API key e webhook secret não pertencem ao Git nem ao perfil de configuração;
- configurações armazenam somente referências opacas;
- material secreto deve ser resolvido via Vault/secret backend já governado pelo Core;
- não existe promoção automática de `configured` para `verified`;
- não existe `PRODUCTION_APPROVED` inferido por presença de dados.
