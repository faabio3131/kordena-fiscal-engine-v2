# CHECKPOINT — NFV1-P00-T02 — Congelar matriz de capacidades

Data: 2026-10-05  
Produto: FM NFCORE V1  
Repository: `faabio3131/kordena-fiscal-engine-v2`  
Main de origem: `faf529a0f1852c9107858da730c6103234a30b2f`  
Branch: `docs/nfv1-p00-t02-capability-matrix`  
PR: #103 — OPEN / DRAFT  
CI da main de origem: FM NFCORE V1 CI #583 — SUCCESS  
Plan Governance da main de origem: #12 — SUCCESS

## Objetivo

Congelar a matriz canônica:

`capacidade -> domínio -> application -> infra -> persistence -> API -> auth/RBAC -> tenant/unit -> Web -> tests -> CI -> staging -> production`

sem implementar correções de fases posteriores.

## CURRENT auditado

- main exact: `faf529a0f1852c9107858da730c6103234a30b2f`;
- PRs abertas no início: 0;
- CI técnico e Plan Governance verdes no exact main;
- 178 arquivos em `src/`;
- 161 arquivos em `tests/`;
- 137 arquivos em `docs/`;
- staging observado na T01 permanece em drift contra a main;
- produção continua não provada/não aprovada.

## Entrega

Criado:

`docs/NFCORE_V1_CAPABILITY_MATRIX_2026-10-05.md`

A matriz congela 17 famílias de capacidade e distingue:

- implementação interna;
- integração/composição;
- persistência;
- HTTP/API;
- auth/RBAC;
- tenant/unidade;
- Web;
- testes/CI;
- staging;
- produção;
- fase do cronograma responsável por cada gap.

## Achados centrais

1. Core fiscal, regras tributárias, documentos, XML, signing, lifecycle e persistence possuem base interna relevante.
2. Bridge HTTP fiscal existe, mas `security` + `executor` não são injetados pelo entrypoint oficial.
3. Portal API possui contrato/RBAC amplo, porém o executor durável implementa somente sete superfícies.
4. Pricing/release/commercial state são autoridades existentes e não devem ser reconstruídos.
5. Acquisition/trial/Cakto webhook possuem routers e serviços, mas dependem de injeções ausentes no global `app`.
6. Billing/subscription/entitlements possuem domínio/estado durável, mas superfícies Web operacionais são parciais.
7. Worker contínuo exige `handler_factory`; o entrypoint chama `run()` sem factory.
8. `FiscalProviderTransport` e `ExternalSecretClient` são boundaries; adapters reais externos não foram comprovados.
9. Observabilidade interna existe; tracing Railway permanece desabilitado.
10. Homologation/pilot/production authority possuem governança interna, mas não evidência oficial externa.
11. Staging não está no exact SHA da main; produção permanece NO-GO.

## Arquivos alterados

- `docs/NFCORE_V1_EXECUTION_LEDGER.md` — somente T02 para `em execução`;
- `docs/NFCORE_V1_CAPABILITY_MATRIX_2026-10-05.md` — nova matriz;
- este checkpoint.

## Código / migrations / runtime

Nenhuma alteração funcional.

Nenhuma migration.

Nenhuma mutação em Railway.

Nenhum segredo ou credencial lido/persistido.

## Verificações estruturais e gates

- cronograma x ledger: 59/59 IDs e mesma ordem — PASS;
- somente T02 em execução — PASS;
- T01 concluída — PASS;
- T03 pendente — PASS;
- diff contra exact main: 3 arquivos documentais, 3 commits ahead, 0 behind — PASS;
- `python3 scripts/check_nfcore_plan.py`: pendente do gate oficial da PR;
- CI completo da PR: pendente.

## Riscos / não confirmado

- uma matriz documental não prova que uma capacidade funciona externamente;
- staging drift será detalhado em T03, não nesta tarefa;
- adapters externos reais, homologação e produção continuam não confirmados;
- `PASS` em testes/CI significa evidência interna, não homologação externa.

## Gate de saída

IN_PROGRESS.

## Próxima ação

Validar estrutura/diff, abrir PR exclusiva da T02 e executar os gates. Não iniciar T03.
