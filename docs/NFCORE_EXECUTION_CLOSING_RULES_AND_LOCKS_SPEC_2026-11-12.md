# NFCore — Regra de fechamento de bloco e especificação do pacote de travas

**Documento:** NFV1-CLOSING-RULES-001 (identificador proposto; confirmar no ledger)
**Data:** 2026-11-12
**Status:** **ESPECIFICAÇÃO. Nada deste documento está implementado.** Não altera CI, ruleset, `CODEOWNERS`, permissões, código, migração, merge nem deploy. Qualquer implementação exige autorização expressa do proprietário.
**Complementa:** `docs/NFCORE_FISCAL_ENGINE_EXECUTION_SCHEDULE_2026-11-12.md`.

## 1. Por que existe

Regras em texto (`AGENTS.md`, skills, cronogramas) são lidas pelo agente como contexto e podem ser ignoradas, esquecidas entre sessões ou "cumpridas" por escrita. Resultado observado: blocos iniciados e não completados, status "pronto" declarado por existência de código ou CI verde, PRs com escopo sem fim (#446: mais de 100 commits e 45 arquivos), três PRs no mesmo arquivo (#446, #449, #450), PRs em draft conflitantes (#427) ou vermelhas (#451). Só é lei o que roda fora do agente e bloqueia.

## 2. Divisão de responsabilidades

| Camada | Responsável | O que garante |
|---|---|---|
| Processo | Travas mecânicas (permissão e CI) e, como camada de planejamento, EGM | Quem pode fazer o quê; o que precisa estar provado para declarar pronto; quantas frentes ficam abertas; plano completo antes de construir |
| Implementação fiscal | Agentes construtores (A e B) | Regra fiscal implementada, fonte oficial lida, testes escritos, caminho de ponta a ponta percorrido |
| Verificação fiscal externa ao construtor | Norma oficial, validador independente, resposta real de homologação, revisão do contador | Correção fiscal. O construtor não é o único juiz de que sua entrega está correta |

Travas e EGM **não** verificam se uma alíquota, um campo ou uma regra municipal está certo. Para isso valem a norma citada com data e versão, o teste e o contador.

## 3. Regra de fechamento de bloco

1. **Um bloco, uma PR.** Cada bloco do cronograma (B0 a B19) tem uma PR própria. Não se abre PR nova para o mesmo bloco nem se fecha a PR para "testar".
2. **A PR do bloco permanece em draft** até que o checklist de aceite do bloco (coluna "Aceite" do cronograma) esteja 100% marcado e a CI do **HEAD exato** esteja verde. Aprovação de SHA anterior não é herdada.
3. **Uma frente por vez para cada agente (WIP = 1).** Não se abre bloco novo enquanto o anterior não estiver FECHADO ou `EXTERNAL_BLOCKED`, com o motivo escrito na PR.
4. **Definição de pronto:** o caminho real percorrido por teste de ponta a ponta (por exemplo, Portal → motor → gateway sintético → arquivo), além de testes unitários e CI. Código existente, CI verde, health e catálogo não equivalem a pronto.
5. **Vocabulário travado:** "certificado" e "homologado" só com a lista de evidências anexa. Sem ela, o status é `IMPLEMENTED_NOT_CERTIFIED`.
6. **Nada incompleto à vista.** Funcionalidade não completa fica desligada ou explicitamente `NÃO IMPLEMENTADO`, sem botão ou endpoint que prometa o que não existe.
7. **Dimensionar antes de começar.** Bloco grande demais para fechar sem virar monólito é dividido de antemão em sub-blocos independentes, cada um com PR e checklist próprios. Não se divide no meio do caminho.
8. **Testes sem fechar.** Durante o bloco roda-se o teste dirigido a cada passo; a suíte completa roda no fim do bloco e sob demanda. Parar para testar não é motivo para fechar ou trocar de PR.
9. **Integrar a main na branch com frequência** (merge do base no head, nunca reescrita de histórico em branch alheia), para o conflito aparecer cedo.
10. **Tamanho como alerta.** Passou de um limite a definir (sugestão inicial: 400 linhas alteradas fora de testes e fixtures, ou 20 arquivos), o agente justifica ou divide.
11. **Auditoria independente no fechamento.** Antes de abrir o bloco seguinte, outro agente ou pessoa, que não o construiu, confere o diff contra o checklist. Resultado INCOMPLETE conta como reprovado.
12. **Matriz viva** (requisito, código, teste, CI, ambiente, lacuna) como única fonte do que está pronto. O status de uma capacidade só sobe se o teste de ponta a ponta correspondente passar.

## 4. Pacote de travas (especificação; nada implementado)

| Trava | O que bloqueia | Como é verificada | Dono |
|---|---|---|---|
| T1 Permissões | Agente fazendo merge ou push em `main` e `production`; alterar CI ou ruleset | Ruleset exigindo checks e aprovação humana; token do agente com menor privilégio; `CODEOWNERS` com aprovação do proprietário para as quatro fronteiras protegidas, para `.github/workflows/**` e para os cronogramas | Proprietário |
| T2 Check de evidência | PR que usa "certificado", "homologado" ou "22/22" sem arquivo de evidência anexo e SHA conferido | Workflow que lê o corpo da PR e os documentos alterados | A definir |
| T3 Limite de frentes | Autor com mais de N PRs draft abertas, ou PR de bloco novo com o anterior não fechado | Workflow que consulta a API do GitHub | A definir |
| T4 Matriz ligada a testes | Subir o status de uma capacidade sem o teste de ponta a ponta correspondente | Comparação entre a matriz em arquivo e os resultados de teste | A definir |
| T5 Anti-stub | Marcadores `PROVISIONAL`, `NotImplemented`, `TODO` em caminho declarado pronto | Teste ou varredura estática | A definir |
| T6 Fronteira protegida | PR que altera `gateway/nfse_nacional_homologation.py`, `issuance/nfse_dps_builder.py`, `runtime/canonical_fiscal_composition.py` ou o teste de recuperação sem o dono | `CODEOWNERS` e check de caminho | Proprietário |

**Salvaguarda:** o agente pode tentar editar o próprio CI para afrouxá-lo. Por isso `.github/workflows/**`, o ruleset e o `CODEOWNERS` ficam sob aprovação do proprietário. Já existem `nfcore-plan-governance.yml` e o check `execution-plan`; o conteúdo exato deles não foi auditado e pode ser ampliado em vez de duplicado.

## 5. EGM (Elephant-Goldfish Model): camada de planejamento, em piloto

- O que é: plugin de código aberto (Apache 2.0, "not an officially supported Google product") com sete skills: `egm-brainstorm`, `egm-draft`, `egm-resolve`, `egm-bootstrap`, `egm-review` (cinco etapas, relatório por etapa), `egm-review-loop` e `egm-drift-report`. Revisão por subagentes em contexto novo; para se não houver subagente.
- O que não faz: não impede o agente de ignorar regras durante a implementação, não bloqueia merge, não conhece a norma fiscal. O próprio projeto diz que não substitui testes nem julgamento humano. O Claude Code tem comando de instalação documentado, mas não consta na lista de suporte oficial.
- Piloto proposto (duas semanas): (a) `egm-review` na especificação do B17a antes de qualquer código; (b) `egm-drift-report` semanal entre cronograma, documentos e código. O pacote de laboratório com Codex foi enviado pelo proprietário e nada nele foi executado.
- Métricas: achados Blocker pegos antes de existir código; PRs refeitas; drafts abertos; afirmações de "pronto" sem evidência. Se as métricas não mudarem, descarta-se.

## 6. Decisões pendentes do proprietário

1. Autorizar a implementação de T1 a T6, em ordem de retorno (T1, T2, T3 primeiro).
2. Definir N de T3 e o limite de tamanho da regra 10.
3. Autorizar o piloto do EGM e onde ele roda (Codex no Windows do proprietário ou outro).
4. Definir quem faz a auditoria independente de fechamento (regra 11).
