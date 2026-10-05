# FM Tecnologia — Modelo de Plano Mestre para Execução por IA

> **TEMPLATE, NÃO PLANO ATIVO.** O plano ativo do NFCore é o cronograma canônico indicado em AGENTS.md. Use este modelo somente para futuros planos que ainda não possuam estrutura própria.

## Cabeçalho

- **Objetivo:** uma frase.
- **Dono / aprovador:** nome/identificação e data da aprovação.
- **Estado:** RASCUNHO
- **Fora de escopo:** o que NÃO será feito.
- **Pode fazer sem perguntar:** ações reversíveis e já autorizadas.
- **Deve parar e perguntar:** preço, produto, segurança, dado pessoal, gasto, conta real, outro repositório, merge/deploy/produção ou ação irreversível.

Valores válidos de Estado:

- RASCUNHO
- APROVADO
- EM EXECUCAO
- CONCLUIDO

Somente o dono/aprovador promove RASCUNHO para APROVADO.

## Itens — ordem obrigatória, um por vez

### 1. ID-DO-ITEM — Título curto

- [ ] **Estado:** pendente
- **Objetivo:** uma ou duas frases.
- **Depende de:** nada.
- **Entregar:** lista objetiva de arquivos, rotas, telas, documentos ou evidências.
- **Não fazer:** limites explícitos.
- **Critério de aceite:** comportamento observável e provas necessárias.
- **Verificação:** comandos/checks exatos e resultado esperado.
- **Riscos / não confirmado:** tudo que ainda não foi provado.
- **Decisões do dono pendentes:** decisões que o executor não pode tomar.
- **Prova:** PENDENTE.

### 2. ID-DO-ITEM — Segundo item

- [ ] **Estado:** pendente
- **Objetivo:**
- **Depende de:** item 1 concluído/certificado.
- **Entregar:**
- **Não fazer:**
- **Critério de aceite:**
- **Verificação:**
- **Riscos / não confirmado:**
- **Decisões do dono pendentes:**
- **Prova:** PENDENTE.

## Regra de conclusão

Somente depois da verificação:

- alterar [ ] para [x];
- alterar Estado para concluído;
- preencher Prova com PR, CI e commit/SHA;
- registrar evidência externa quando aplicável.

## Relatório final

Registrar:

- entregas por item;
- PRs;
- commits de merge;
- CI do branch principal;
- testes e evidências executadas;
- o que NÃO está confirmado;
- riscos/blockers;
- pendências do dono;
- próxima ação recomendada.

## Limite

Automação de formato não prova que a evidência é verdadeira. Critérios de aceite, testes, revisão, CI e evidência de runtime continuam obrigatórios.
