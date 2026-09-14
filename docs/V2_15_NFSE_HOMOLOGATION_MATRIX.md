# V2-15 B4 — NFS-e Homologation Matrix

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**

## Escopo

A matriz NFS-e é deliberadamente `município + provider` specific. Não existe fallback de município para UF, de município para provider default, entre providers ou de `HOMOLOGATION` para `PRODUCTION`.

O escopo sintético de certificação usa tenant/unidade de teste, ambiente `HOMOLOGATION`, município explicitamente identificado por código IBGE, provider configurado por binding persistido e referências opacas de credenciais provider-scoped. Nenhum segredo real, endpoint produtivo ou dado real de cliente é utilizado.

## Capacidade interna certificada

A suíte `tests/homologation/test_v2_15_b4_nfse_matrix.py` cobre:

- resolução exata por tenant/unidade/ambiente/documento/UF/município/operação/provider;
- `AUTHORIZE`, `QUERY` e `CANCEL` somente para o provider sintético que declara essas capacidades;
- persistência e restart sem perda da configuração;
- obrigatoriedade do código IBGE municipal em binding e evidência NFS-e;
- ausência de fallback para outro município da mesma UF;
- ausência de fallback cross-provider de credenciais;
- rejeição explícita de escopo `PRODUCTION` pelo readiness de homologação;
- unknown authorization outcome sem retry cego, exigindo reconciliation;
- evidência técnica interna separada da evidência oficial externa.

A arquitetura não pressupõe protocolo municipal universal. Um protocolo/provider novo é evolução reutilizável via adapter/catálogo; não gera código específico por cliente.

## Evidência oficial externa

**Nenhuma homologação oficial externa foi executada neste bloco.**

Todos os registros sintéticos permanecem com `external_official = false`. Nenhum município/provider/operação é declarado oficialmente homologado sem resposta/evidência externa real correspondente.

## Bloqueios externos

Para homologação oficial futura serão necessários, conforme o município/provider selecionado, cadastro/credenciais/certificados e acesso efetivo ao ambiente externo autorizado. Esses itens não são simulados como evidência oficial.

## Riscos residuais

- particularidades de protocolos municipais reais devem ser certificadas provider a provider e município a município;
- operações não declaradas pelo descriptor/capability não podem ser inferidas;
- a certificação deste bloco prova o boundary interno, o isolamento e a governança, não a disponibilidade de um provedor/prefeitura externos.

## Gate certificado

SHA `2c152f0a86d4a80a97f91125bc9e9bbc50ee993a`, run `34777347753`, job `103777774112`: Install PASS, Ruff PASS, Mypy PASS em **110 source files**, Pytest **611 PASS em 6.27s**. Warning informativo: actions baseadas em Node 20 foram executadas em Node 24 pelo runner; não afetou o gate. CI restaurado para `workflow_dispatch` only em `eb54bae4e138bf8658a72f73970bee967c417d72`.
