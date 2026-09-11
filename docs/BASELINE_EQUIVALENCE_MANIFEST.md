# V2-00 — BASELINE EQUIVALENCE MANIFEST

Status: **EM EXECUÇÃO**  
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

## Adaptações permitidas no clone

- nome/descrição do repositório em documentação V2;
- workflow CI para reconhecer branches `v2/**`;
- governança V2 em `AGENTS.md`;
- documentos de Plano Mestre e tracker V2.

Essas adaptações não podem modificar semântica fiscal.

## Progresso

- [x] repositório V2 privado criado;
- [x] baseline SHA/tree congelados;
- [x] branch V2-00 criada;
- [x] Plano Mestre registrado;
- [x] tracker V2 registrado;
- [x] governança V2 registrada;
- [ ] árvore certificada integralmente importada;
- [ ] suíte integral executada;
- [ ] equivalência certificada.
