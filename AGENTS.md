# AGENTS.md — FM Fiscal Core V2

## Autoridade

Este repositório implementa a evolução independente e multiproduto do motor fiscal brasileiro da FM Tecnologia.

O Fiscal Core não é autoridade do domínio de negócio de Kordena, Iron Fit, Vendedor IA, CampaIA ou qualquer consumidor. Ele recebe contratos fiscais neutros, executa regras e lifecycle fiscais e devolve resultados/eventos auditáveis.

## Estratégia de transição

1. O repositório `faabio3131/kordena-fiscal-engine` permanece baseline congelado durante a transição.
2. O baseline certificado de origem é `b336def47ad4f5188307102203f4e04b98406014`.
3. O V2 deve provar equivalência antes de refatoração multiproduto.
4. O fork é temporário. Depois do cutover certificado, o V2 vira a única arquitetura fiscal ativa e o original é preservado como histórico/auditoria.

## Regras obrigatórias

1. Nunca adicionar segredo, certificado real, senha, CSC, token, credencial, endpoint privado ou dado real de cliente.
2. Todo dado de exemplo deve ser sintético.
3. Alterações fiscais relevantes exigem teste correspondente.
4. Emissão deve ser idempotente por construção.
5. Numeração fiscal não pode usar estratégia concorrencialmente insegura como `MAX + 1`.
6. Regras tributárias devem possuir versão/vigência e ficar atrás do Tax Rule Engine.
7. Documento autorizado deve preservar snapshot histórico; cadastro atual não reescreve passado.
8. Adapters externos não podem inventar regra de negócio.
9. IA pode sugerir classificação, nunca alterar silenciosamente configuração fiscal de alto impacto.
10. Falhas de escopo, assinatura, schema, autorização, capability ou segredo são fail-closed.
11. Core não importa domínios privados dos SaaS consumidores.
12. Integração multiproduto exige `host_system_id`/namespace e binding governado de tenant/unidade.
13. Nenhum merge, deploy, promoção para produção ou cutover é automático.

## Disciplina de entrega

Para cada bloco V2:

- confirmar escopo em `docs/EXECUTION_TRACKER_V2.md`;
- implementar somente o bloco ativo e dependências mínimas;
- executar testes dirigidos;
- executar Ruff, Mypy strict e Pytest;
- revisar diff;
- registrar SHA, PR e CI;
- registrar riscos residuais;
- somente então alterar o estado para `CONCLUÍDO`.

Nenhuma etapa é concluída por declaração sem evidência.
