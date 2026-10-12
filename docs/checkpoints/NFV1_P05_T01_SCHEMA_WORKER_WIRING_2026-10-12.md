# NFV1-P05-T01 — schema read-only plan + Worker GSM bootstrap — 2026-10-12

## CURRENT confirmado
- Main de partida: `1d84598e71cd164ebbf57b078c212075fb2c6c36`; PR #174 integrada; CI pós-merge #823 ainda não declarada verde nesta abertura.
- Railway STAGING project `b84b290d-f3b4-46a1-9023-0b761cb96b0d`; API e Portal permanecem na revisão 04/10, Worker anterior sem handler de assinatura GSM e com política de reinício NEVER.
- Operador provou backup lógico age/SHA e restauração PG18 de 34 tabelas. PostgreSQL Railway reportou migrations fiscais 1..12; rastreio Cakto ausente. **Não refazer essa evidência por rotina**.
- Projeto GSM `fm-nfcore-staging`: checkpoint PR #165 informa API habilitada e contas de serviço segregadas, mas **nenhuma chave user-managed, IAM reader, versão de segredo, bootstrap Railway ou read/deny real** comprovados. A PR #165 permanece Draft e não mergeada.

## Current -> Target — escopo estrito desta PR
1. `scripts/ci/migration_guard.py --plan-staging`: consultar o banco por porta canônica somente leitura e identificar exatamente fiscal pendente 13..17 e Cakto 1..2; rejeitar esquemas inesperados/ordem não contígua; sem criação de tabela, sem DDL, sem aprovação implícita.
2. `worker_main` conecta a inicialização containerizada ao builder de assinatura GSM já existente, somente com modo explícito `scoped-staging-sa-v1` e um único tenant/unidade de PILOTO; sem fallback de segredo, ambiente, chave, escopo ou handler.
3. Verificar segurança do arquivo de identidade fora de Git (permissão 0600, ownership e regular file), projeto e workload `nfcore-worker`, janela de rotação <=30 dias conforme política existente, binding canônico por referência/version e read GSM efetivo antes de readiness. Material jamais gravado em logs.
4. Preservar `NFCORE_WORKER_ONESHOT=true` exclusivamente para smoke sem dispatch e falha fechada quando o modo contínuo não tiver assinatura.

## Critérios e restrições
- Esta composição é um caminho **limitado a uma unidade em staging**, para habilitar piloto real após credenciais aprovadas. **Não resolve o roteamento/assinatura multi-tenant dinâmicos**. Não se deve publicar staging como completo com essa limitação. Workload não deve compartilhar fila ativa com outros tenants usando esse modo sem isolamento operacional comprovado.
- Não ler/gerar chave GCP neste PR. A política de IAM, API secret bindings e prova de acesso ainda dependem de ação externa controlada. A metadata de expiração fornecida por operador deve ser reconciliada com IAM; não é prova independente da idade da chave.
- Nenhum merge, migration aplicada, deploy ou alteração de variáveis Railway automática é parte desta PR. Não disponibiliza assinatura fiscal nem homologação oficial. A criação de uma chave SA para staging, se necessária, requer decisão do responsável; idealmente avaliar WIF gerenciada.
- Gates: CI/segurança, testes de schema read-only, identidade, revogação, scope mismatch, secret read denied, oneshot e E2E anteriores; staging real ainda pendente.

## Próxima execução
1. Integrar PR após CI verde e aprovação específica.
2. Executar `--plan-staging` com conexão segura read-only, sem revelar DSN.
3. Escolher e provisionar identidade GSM aprovada (IAM exact-secret, WIF preferencial ou chave SA staging <=30 dias).
4. Confirmar worker dispatch multi-tenant ou isolamento de fila antes de publicar todos serviços no mesmo SHA.
5. Com autorização separada: executar migrations canônicas fiscal 13..17 e Cakto 1..2, deploy coordenado API/Worker/Portal, smoke/E2E Web.

**Status:** NFV1-P05-T01 permanece BLOCKED_EXTERNAL; P05-T02 NOT_STARTED. Target é a Web real, não conclusão documental.
