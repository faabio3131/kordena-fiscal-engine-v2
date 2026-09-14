# FM Fiscal — Baseline Comercial V1 e Roadmap V2

Data: 2026-09-13
Status: **FORMALIZADO**

## V1.0 — Commercial Launch Edition

Objetivo: lançar e começar faturamento sem aguardar as expansões de V2.

Escopo comercial da V1:

- NF-e;
- NFC-e;
- NFS-e;
- Core fiscal governado;
- Bridge/API versionada;
- webhooks;
- idempotência;
- reconciliation;
- archive/audit;
- Control Plane;
- onboarding configurável por tenant/unidade;
- plans/entitlements/billing foundation;
- SDK/documentação existente;
- portal premium com identidade FM Fiscal V1.0;
- configuração externa reference-only para certificado, CSC, provider, gateway, preço e gates de produção.

A V1 deve receber correções, segurança, atualização normativa obrigatória e melhorias incrementais, sem atrasar o lançamento esperando funcionalidades de expansão.

## Pendências externas que não bloqueiam o fechamento interno da V1

- certificado digital real;
- CSC quando aplicável;
- credenciais oficiais de SEFAZ, prefeitura ou provider;
- homologação oficial aplicável;
- conta/infraestrutura produtiva e domínio real;
- conta real de gateway de cobrança;
- preço final aprovado pelo Diretor;
- validação jurídica final;
- cliente piloto real;
- ativação de produção.

Esses itens devem entrar por configuração/evidência e não gerar mudança de código para clientes dentro das capacidades já suportadas.

## V2.0 — Competitive Expansion

A V2 será construída sobre a V1 estabilizada e deverá atacar as oito lacunas competitivas identificadas na pesquisa de mercado:

1. **CT-e + MDF-e + documentos fiscais recebidos/DF-e**;
2. **Sandbox e Developer Experience avançados** — playground, Postman, SDKs ampliados, CLI, webhook inspector e self-service developer onboarding;
3. **Fiscal Rules / Preflight Engine** — regras versionadas, validação determinística e prevenção de rejeições;
4. **Monitor Fiscal / Fiscal Intelligence** — documentos recebidos, divergências, anomalias e assistência explicável;
5. **Automations no-code/low-code** — fluxos orientados a eventos;
6. **White label / Embedded Fiscal Console**;
7. **Contingência offline/edge para NFC-e**;
8. **Homologação e operação ampliadas em escala**, incluindo cobertura jurisdicional e provas operacionais.

## Regra de versionamento comercial

O nome do repositório ou de fases internas de engenharia não define a versão comercial. Para o mercado:

- primeira versão vendida = **FM Fiscal V1.0**;
- expansão competitiva acima = **FM Fiscal V2.0**.

## Regra de comunicação

Não anunciar funcionalidades de V2 como disponíveis na V1. Roadmap pode ser apresentado apenas como roadmap, sem promessa de data ou disponibilidade até que cada capability esteja implementada e certificada.
