# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Última fase concluída: **V2-00 — Clone técnico + prova de equivalência**  
Próxima fase liberada: **V2-01 — Identidade FM + neutralização de branding**

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`.

Nenhum bloco pode ser marcado `CONCLUÍDO` sem branch, SHA, PR, CI, testes/gates, revisão do diff e riscos residuais documentados.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-00 | Clone técnico + equivalência | **CONCLUÍDO** | PR #1 Draft; baseline `b336def47ad4f5188307102203f4e04b98406014`; `src/` tree `bd756be69685cecad0907816e93fca8616482553`; `tests/` tree `af98a932eca692a1eb2307879de7afbd01d1f003`; gate SHA `9da776e353b31d03a8453a83c6e61a736e6ed00b`; Actions run `34633874565` SUCCESS; Ruff PASS; Mypy PASS; Pytest 215 PASS |
| V2-01 | Identidade FM + neutralização de branding | PENDENTE | liberado após V2-00; branch/PR ainda não iniciados |
| V2-02 | Host namespace + fiscal account binding | PENDENTE | depende V2-01 |
| V2-03 | Fiscal Operation Contract genérico | PENDENTE | depende V2-02 |
| V2-04 | FM Fiscal Bridge — OpenAPI/JSON Schema/AsyncAPI | PENDENTE | depende V2-03 |
| V2-05 | Auth S2S + workload identity + webhook security | PENDENTE | depende V2-04 |
| V2-06 | Capability & Readiness API | PENDENTE | depende V2-04/V2-05 |
| V2-07 | Application service + persistência durável | PENDENTE | depende V2-05 |
| V2-08 | Events/Webhooks/Inbox/Outbox | PENDENTE | depende V2-07 |
| V2-09 | Modularização de verticais | PENDENTE | após contratos core estabilizados |
| V2-10 | Contract Packs Kordena/Iron/Vendedor/CampaIA | PENDENTE | depende V2-03..V2-09 |
| V2-11 | Control Plane independente | PENDENTE | depende core operacional |
| V2-12 | Gateway/Signer/Vault production adapters | PENDENTE | depende V2-11 |
| V2-13 | Observabilidade + Compliance Operations | PENDENTE | depende V2-07/V2-12 |
| V2-14 | Hardening sistêmico | PENDENTE | regressão/carga/falhas/segurança |
| V2-15 | Homologação + pilotos controlados | PENDENTE | depende V2-14 |
| V2-16 | Integração produtos FM | BLOQUEADO PARCIAL | Kordena aguarda V1 Web Premium; demais aguardam V2 universal certificado |
| V2-17 | Convergência/cutover + arquivamento original | PENDENTE | somente após equivalência e integrações certificadas |
| V2-18 | Produto comercial independente | PENDENTE | posterior ao uso interno certificado |

## Checkpoint V2-00.1 — Bootstrap — 2026-09-11

- Repositório privado V2 confirmado e acessível pelo GitHub App.
- `main` inicializada e README atualizado com a estratégia de fork transitório.
- Branch de execução: `v2/foundation-equivalence-and-master-plan`.
- Plano Mestre criado em `docs/PLANO_MESTRE_EXECUCAO_V2.md`.
- Baseline de origem fixado em `b336def47ad4f5188307102203f4e04b98406014`.
- Manifest de equivalência criado em `docs/BASELINE_EQUIVALENCE_MANIFEST.md`.

## Checkpoint V2-00.2 — Execução iniciada — 2026-09-11

- PR #1 criada em Draft: `V2-00 — Foundation, Master Plan and Baseline Equivalence`.
- `.gitignore` e `pyproject.toml` do baseline importados sem alteração semântica.
- CI criada com os mesmos gates Ruff + Mypy + Pytest; durante a cópia massiva ficou temporariamente em `workflow_dispatch` para evitar consumo desnecessário de minutos.
- Primeiro slice técnico importado do SHA certificado: `src/kordena_fiscal/__init__.py` e todo o pacote `src/kordena_fiscal/domain/`.
- Nenhuma refatoração multiproduto foi iniciada; os arquivos importados preservaram o comportamento original.

## Checkpoint V2-00.3 — Equivalência certificada — 2026-09-11

- Árvore completa `src/` transportada sem mudança semântica.
- Suíte completa de 24 arquivos de teste transportada byte-for-byte.
- Tree SHA `src/` no original e no V2: `bd756be69685cecad0907816e93fca8616482553`.
- Tree SHA `tests/` no original e no V2: `af98a932eca692a1eb2307879de7afbd01d1f003`.
- Commit submetido ao gate: `9da776e353b31d03a8453a83c6e61a736e6ed00b`.
- GitHub Actions run `34633874565`: **SUCCESS**.
- Install: PASS.
- Ruff: PASS.
- Mypy: PASS — 45 source files sem issues.
- Pytest: PASS — **215 passed**.
- Diff auditado: diferenças fora da árvore fiscal são apenas governança/documentação/CI do V2 (`INFRA-ONLY`).
- Risco residual de equivalência: nenhum desvio conhecido em relação ao baseline certificado.
- CI retornado a `workflow_dispatch` após o gate verde para controlar consumo de minutos.

Decisão: **V2-00 CONCLUÍDO. V2-01 está LIBERADO, mas permanece PENDENTE até a abertura formal de sua branch/PR.**
