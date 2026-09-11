# FM FISCAL CORE V2 — EXECUTION TRACKER

Data de início: 2026-09-11  
Repositório: `faabio3131/kordena-fiscal-engine-v2`  
Status global: **EM EXECUÇÃO**  
Fase ativa: **V2-00 — Clone técnico + prova de equivalência**

## Regra de governança

Estados permitidos: `PENDENTE`, `EM EXECUÇÃO`, `BLOQUEADO`, `CONCLUÍDO`.

Nenhum bloco pode ser marcado `CONCLUÍDO` sem branch, SHA, PR, CI, testes/gates, revisão do diff e riscos residuais documentados.

| Bloco | Escopo | Status | Evidência / Gate |
|---|---|---|---|
| V2-00 | Clone técnico + equivalência | **EM EXECUÇÃO** | baseline `b336def47ad4f5188307102203f4e04b98406014`; importação e gates em andamento |
| V2-01 | Identidade FM + neutralização de branding | PENDENTE | depende V2-00 |
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
- Próximo gate: importar árvore técnica certificada do original sem alteração semântica e validar equivalência.

Decisão: **V2-00 permanece EM EXECUÇÃO.**
