# FM Tecnologia — Padrão de Execução de Plano Mestre por IA

**Status:** PADRÃO APROVADO PARA O NFCORE V1  
**Aprovado por instrução do dono do projeto:** 2026-10-05  
**Origem:** kit padrão de execução fornecido pelo dono do projeto em 2026-10-05.  
**Aplicação ativa:** FM NFCORE V1 — Commercial Launch.

## 1. Finalidade

Este padrão transforma um plano mestre persistido no repositório em uma disciplina de execução verificável para qualquer executor: ChatGPT/Codex, Claude, outra IA ou pessoa.

Ele existe para impedir:

- perda de contexto;
- execução fora de ordem;
- escopo ampliado silenciosamente;
- tarefa marcada como concluída sem prova;
- teste ignorado para obter CI verde;
- simulação tratada como integração real;
- pendência mantida apenas no chat;
- divergência entre plano e PR;
- avanço com predecessor não certificado.

## 2. Fontes de verdade e precedência no NFCore

O kit genérico dizia que o arquivo do plano prevalece sobre a conversa. No NFCore, essa regra é aplicada sem violar a hierarquia técnica do projeto:

1. código CURRENT no Git/GitHub;
2. branches, HEAD, PRs, merges e main;
3. CI, testes, builds e evidências de runtime;
4. cronograma mestre de conclusão;
5. ledger de execução;
6. ADRs, System Design e certificações;
7. conversa/memória como contexto e fonte de autorizações humanas.

Portanto:

- o cronograma governa o que executar, em que ordem e com quais gates;
- o ledger governa estado e prova por tarefa;
- Git/CI/runtime governam o que realmente existe e funciona;
- a conversa pode autorizar uma decisão, mas a alteração de escopo deve ser persistida no cronograma/ledger antes de virar execução.

## 3. Arquivos ativos do NFCore

- Cronograma: docs/NFCORE_V1_COMPLETION_MASTER_EXECUTION_SCHEDULE_2026-10-05.md
- Ledger: docs/NFCORE_V1_EXECUTION_LEDGER.md
- Validador: scripts/check_nfcore_plan.py
- CI: .github/workflows/nfcore-plan-governance.yml
- Template de PR: .github/PULL_REQUEST_TEMPLATE.md
- Instruções do executor: AGENTS.md

Não criar um segundo plano mestre concorrente.

## 4. Regra de execução

1. Antes de qualquer trabalho, reconfirmar main, HEAD, PRs, CI e ambiente afetado.
2. Ler AGENTS.md, o cronograma inteiro e o ledger.
3. Executar somente a primeira tarefa não concluída, salvo alteração de ordem aprovada e persistida.
4. Releia a tarefa imediatamente antes de executar.
5. Copie para a PR o critério de aceite e a verificação aplicável.
6. Uma PR de execução deve ter escopo de uma tarefa NFV1-Pxx-Tyy.
7. Teste que falha deve ter a causa corrigida; é proibido apagar, pular ou enfraquecer teste válido.
8. Tarefa somente vira concluída depois de implementação, testes, CI, evidência e merge quando aplicável.
9. Ao concluir, preencher a prova no ledger com PR, CI e commit/SHA.
10. Rodar python3 scripts/check_nfcore_plan.py antes de considerar o item certificável.

## 5. Não inventar

Tudo que não estiver comprovado deve ser classificado como:

- não confirmado;
- bloqueado internamente;
- bloqueado externamente;
- implementado não integrado;
- integrado não implantado;
- implantado não certificado.

Simulação, fake, synthetic, mock, harness interno ou teste unitário não comprovam integração externa real.

## 6. Quando parar para decisão humana

Parar antes de:

- decisão de produto não prevista;
- preço/comercial;
- texto jurídico;
- mudança de segurança;
- tratamento novo de dado pessoal;
- gasto/conta real;
- segredo/certificado real;
- outro repositório fora do escopo;
- mudança de visibilidade;
- merge quando não autorizado;
- deploy;
- migration produtiva;
- DNS;
- emissão fiscal de produção;
- operação irreversível.

O bloqueio deve ser registrado no ledger/checkpoint, não ficar apenas na conversa.

## 7. Prova obrigatória

Uma tarefa marcada como concluída deve conter no campo **Prova**:

- referência da PR;
- CI final correspondente;
- commit/SHA certificado.

Para tarefas que exigem ambiente externo, a PR/CI não substitui evidência de runtime. A evidência externa também deve ser registrada no checkpoint da fase.

## 8. Relação cronograma x ledger

O cronograma contém o escopo e todos os IDs NFV1-Pxx-Tyy.

O ledger contém exatamente os mesmos IDs, na mesma ordem.

O validador falha se:

- um ID existir no cronograma e faltar no ledger;
- um ID existir no ledger e faltar no cronograma;
- a ordem divergir;
- houver numeração quebrada;
- faltar campo obrigatório;
- uma tarefa posterior estiver concluída antes de uma anterior;
- uma tarefa estiver marcada concluída sem PR + CI + SHA;
- o plano estiver CONCLUIDO com pendências.

Isso transforma esquecimento estrutural em falha de CI.

## 9. Estado do plano

Valores válidos:

- RASCUNHO
- APROVADO
- EM EXECUCAO
- CONCLUIDO

Somente o dono/aprovador pode mudar RASCUNHO para APROVADO.

CONCLUIDO somente é permitido quando todas as tarefas estiverem concluídas e o gate comercial final estiver comprovado.

## 10. Estado da tarefa

Valores operacionais:

- pendente
- em execução
- concluído
- bloqueado interno
- bloqueado externo

Somente concluído pode usar checkbox [x].

## 11. Exceção de bootstrap

A PR que instala inicialmente o cronograma, o ledger e esta automação de governança pode conter os arquivos de bootstrap em conjunto. Ela não executa P0 e não autoriza marcar nenhuma tarefa como concluída.

Depois do bootstrap, aplica-se a regra de uma tarefa de execução por PR.

## 12. Limite da automação

O validador garante estrutura, ordem e presença formal de prova. Ele não consegue determinar sozinho se a prova é verdadeira ou suficiente.

A qualidade final continua dependendo de:

- critérios de aceite;
- testes reais;
- revisão;
- CI;
- evidência de runtime;
- homologação externa quando aplicável;
- decisão humana nos gates obrigatórios.
