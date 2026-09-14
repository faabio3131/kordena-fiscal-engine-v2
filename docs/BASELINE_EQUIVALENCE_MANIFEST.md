# V2-00 — BASELINE EQUIVALENCE MANIFEST

Status: **CONCLUÍDO**  
Data: 2026-09-11

## Fonte congelada

Repositório de origem: `faabio3131/kordena-fiscal-engine`  
Commit certificado: `b336def47ad4f5188307102203f4e04b98406014`  
Tree: `f835f3c8254b41c773650659a0b0119efc659315`

Este commit fecha FISC-00 a FISC-19 no tracker original e mantém FISC-20 bloqueado.

## Objetivo do V2-00

Copiar a árvore técnica certificada para este repositório sem mudança semântica e provar equivalência antes da universalização.

## Regras de importação

- arquivos de domínio, application/issuance, tax, documents, lifecycle, gateway, signing, XML, contingency, archive, reconciliation, operations, presentation, compliance, numbering e testes devem ser importados do baseline;
- qualquer adaptação necessária apenas para CI/branch/repo deve ser registrada como `INFRA-ONLY`;
- nenhuma regra fiscal, cálculo, lifecycle, idempotência ou comportamento de negócio pode ser alterado durante a importação;
- SHA de origem e caminho devem permanecer rastreáveis;
- fixtures continuam sintéticas;
- segredos/credenciais reais são proibidos.

## Gate de equivalência

V2-00 só poderá ser concluído quando:

1. inventário de arquivos do baseline estiver reconciliado;
2. package/configuração necessários à suíte estiverem presentes;
3. Ruff PASS;
4. Mypy strict PASS;
5. Pytest PASS;
6. comportamento público comparado sem regressão conhecida;
7. diff de importação auditado;
8. PR Draft e CI registrados no tracker.

## Evidência de equivalência certificada — 2026-09-11

Baseline certificado de origem: `b336def47ad4f5188307102203f4e04b98406014`.

Árvores Git comparadas:

- `src/` origem: `bd756be69685cecad0907816e93fca8616482553`;
- `src/` V2 no gate: `bd756be69685cecad0907816e93fca8616482553`;
- `tests/` origem: `af98a932eca692a1eb2307879de7afbd01d1f003`;
- `tests/` V2 no gate: `af98a932eca692a1eb2307879de7afbd01d1f003`;
- `pyproject.toml` preservado com blob `16d48cd0b47321b64837499e8b74bbabaeeacf22`.

A igualdade dos SHAs de árvore de `src/` e `tests/` prova igualdade byte-for-byte da árvore técnica e da suíte de regressão transportadas para o V2.

Commit submetido ao gate de equivalência: `9da776e353b31d03a8453a83c6e61a736e6ed00b`.

GitHub Actions:

- workflow: `FM Fiscal Core V2 CI`;
- run: `34633874565`;
- Install: **PASS**;
- Ruff: **PASS**;
- Mypy: **PASS** — 45 source files sem issues;
- Pytest: **PASS** — 215 passed;
- conclusão do job `quality`: **SUCCESS**.

Após o gate verde, o workflow foi devolvido a `workflow_dispatch` para evitar consumo desnecessário de minutos enquanto não houver novo gate autorizado.

## Auditoria do diff

A árvore fiscal `src/`, a suíte `tests/` e o `pyproject.toml` permanecem equivalentes ao baseline certificado. Diferenças deliberadas do V2 estão limitadas à governança e infraestrutura do novo repositório, incluindo README, `AGENTS.md`, Plano Mestre, tracker, manifest e configuração de acionamento do CI. Essas diferenças são classificadas como `INFRA-ONLY`/documentais e não alteram semântica fiscal.

Risco residual do V2-00: nenhum desvio conhecido de comportamento em relação ao baseline certificado. Integrações reais, credenciais, homologação externa e universalização pertencem às fases posteriores e não fazem parte do gate de equivalência.

## Adaptações permitidas no clone

- nome/descrição do repositório em documentação V2;
- workflow CI para reconhecer branches `v2/**`;
- governança V2 em `AGENTS.md`;
- documentos de Plano Mestre e tracker V2.

Essas adaptações não podem modificar semântica fiscal.

## Fechamento

- [x] repositório V2 privado criado;
- [x] baseline SHA/tree congelados;
- [x] branch V2-00 criada;
- [x] Plano Mestre registrado;
- [x] tracker V2 registrado;
- [x] governança V2 registrada;
- [x] árvore certificada integralmente importada;
- [x] suíte integral executada;
- [x] equivalência certificada.

Decisão: **V2-00 CONCLUÍDO. A universalização só pode avançar a partir desta base certificada.**
