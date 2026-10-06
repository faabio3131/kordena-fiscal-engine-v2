# NFV1-P02-T03 — implementação da política aprovada

Data: 2026-10-06. Repository: `faabio3131/kordena-fiscal-engine-v2`.
Task: NFV1-P02-T03. Status: IMPLEMENTAÇÃO INTERNA CANDIDATA / NÃO CERTIFICADA.
Branch: `feat/nfv1-p02-t03-approved-config`. SHA/PR finais são os da PR deste registro;
não criar referência circular ou declarar CI/main futuros como prova presente.

## CURRENT auditado / autoridade / decisão

Main inicial db2a8fb71097eb4e1f6e5919e1eb544c8a3167ac, PR #119 MERGED,
CI #641/Governance #62 SUCCESS. Revalidação durante implementação encontrou #120
mergeada: main `e203adc111d5e503c68a88bf6104df905b8fe18f`, CI #643
(run 37510102097) e Governance #64 (37510102061) SUCCESS; zero PRs abertas.
O checkpoint remoto foi incorporado; nenhum rollback do CURRENT.

AGENTS.md, cronograma, ledger, CURRENT, padrão mestre e checkpoints/proposta T03
lidos. Predecessor T02 certificado. Primeira Task incompleta: T03. Sem T04.
Dono aprovou `POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION` em 2026-10-06, como
conjunto, para implementação/testes/migrations aditivas/PR/CI internos da T03.
T03-B01 resolvido como decisão; nenhuma permissão externa/produção decorre disso.

## CURRENT → TARGET / escopo congelado / impacto

CURRENT de entrada: consultas sanitizadas, sem comandos/formulários completos.
TARGET interno: cinco formulários de configuração nas mesmas telas, comandos por
sessão/CSRF/permissão/unidade/ambiente, versões e replay duráveis; destino solicitado
separado de aprovação de plataforma e de entrega. Nenhum dado de cliente hardcoded.

Certificate/CSC/credentials: somente referência ref:... governada e provider conforme
SecretReference existente. Providers: binding exato documento/UF/município/operação.
Integrations: módulos configuráveis; bindings fiscais existentes permanecem visíveis,
com limitação de ambiente explicitada. Settings: políticas de runtime por provider.
Webhooks: destino HTTPS normalizado; enabled é intenção, nunca aprovação ou prova.
A mesma vista acompanha status/attempt/timestamps dos entries webhook_event da
outbox canônica no escopo exato (host/tenant/unit/env), até 100 por página. Não
projeta body, dedup key, assinatura, URL, headers, last_error ou referência bruta do
endpoint. Estado persistido do entry não é certificação de tráfego externo.

UoW/stores/control plane/commercial/HumanIdentity/AuthenticatedHuman/RBAC/sessão/CSRF
reutilizados; nenhuma segunda API/auth/tenant/unidade/RBAC/persistência/frontend/
Provider Registry/Vault/fila. Metadados novos pertencem aos mesmos stores canônicos.

Schema 14 aditivo compartilhado SQLite/PostgreSQL: fm_configuration_revisions,
fm_configuration_commands e seis colunas de aprovação na tabela de destinos existente.
Valor corrente continua nas tabelas canônicas; recibos guardam hash de fingerprint e
resultado sanitizado, nunca URL/body/headers/ref material. Audit, comando, versão e
valor commitam juntos. CAS por versão; replays persistem após recomposição. Falha
reverte tudo; não há promessa de restauração de material secreto histórico.

A decisão platform_admin é derivada exclusivamente da conta canônica da sessão.
Tenant não pode autoaprovar nem enviar platform_admin; approver independente do
requester. Aprovação exige URL exata, versão atual e validade com fuso (até 30 dias).
Mudança revoga eficácia anterior; pending/revoked/expired/disabled/missing negam.
Não se concede autoridade de produção fiscal, pagamento ou entitlement.

Delivery: SignedWebhookOutboxHandler/WebhookSecurity/outbox/Worker existentes;
policy obrigatória, inclusive no retry; resolver lê a partição do entry. Adapter do
port de transport existente revalida antes da conexão, rejeita mudança de versão,
conecta endereço numérico validado, preserva hostname/SNI e validação TLS padrão.
DNS misto é negado; redes especiais são negadas explicitamente para estabilidade
entre versões Python. DNS não faz cadastro virar entrega. Não há proxy/tunnel/
redirect; 3xx é falha fatal, não delivery confirmado. Texto de resposta não é
persistido. Exceções do Worker já são sanitizadas por classe. Revogação vale antes
de iniciar a próxima tentativa; este contrato não promete cancelar bytes já enviados.
O helper de composição não ativa operações no Worker nem faz deploy.

## Aceite / testes / gates

Testes dirigidos SQLite: comandos nas cinco superfícies, replay/fingerprint/versão,
recomposição, CSRF/role/unidade/ambiente/spoofing, concorrência CAS, rollback quando
audit falha, aprovação independente/canonical platform flag, expiry/revoke, escopo,
DNS privado entre públicos/rebinding/revogação durante DNS, retry após revogação,
policy ausente, conexão numérica/SNI/TLS e redirect sem sucesso. Mesmo contrato é
parametrizado para PostgreSQL real na CI. Migração 14 reconstruída a partir da 13
preserva valores legados, defaults pending e versões zero; legacy URL inválida não
é projetada na revisão de plataforma nem pode obter autorização de delivery.

Fixtures históricas de migrations foram atualizadas para realmente remover metadata
14 ao reconstruir schemas anteriores; asserts continuam verificando os antigos IDs,
preservação e idempotência. Nenhum teste removido, desabilitado ou xfail novo.
Testes HMAC/retry/inbox preexistentes usam policy sintética explícita e transport em
processo; não fingem aprovação externa. Testes separados usam a policy durável real.

Plan checker, migration policy, secret scan, Ruff, Mypy strict e frontend
lint/typecheck/12 tests/build passaram localmente. Primeira execução ampla encontrou
asserts históricos de versão/enums de testes, corrigidos pela causa; rerun amplo local: 1167 PASS, 97 SKIP (PostgreSQL), sem falhas. Teste dirigido adicional passou para revisão legada sanitizada e comando sem versão. A CI do exact HEAD deve confirmar o conjunto final. Local PostgreSQL indisponível: skips condicionais
preexistentes são visíveis; certificação requer CI remota com zero skips. Playwright
local não executou por Chromium ausente; não é prova verde. CI remota deve executar
Playwright, audits, container builds/non-root/smokes/health/readiness, vulnerability
policy, SBOM, backup/restore e todas as outras etapas do workflow existente.

## Zero pendência invisível / riscos / ações não realizadas

- TODO/FIXME/HACK ausentes em src/portal na auditoria desta parcela.
- Cinco formulários têm comandos compostos; egress só aparece à plataforma autenticada.
- Integrações reais, material resolvido/secret externo/cert/CSC: P6/P7/P10, não comprovados.
- Worker operacional 0/1/observabilidade: P4/P9; SHA staging/rollback real: P5/P11.
- users: T04; billing/plans/usage: T05; premium/support: T07. P2 gate continua NOT MET.
- Test doubles somente em testes; nenhum driver fake habilitado para operação real.
- Configuração é por tenant/unit/environment/provider; não exige código por cliente.
- Migrations locais em dados sintéticos; nenhuma migration staging/produtiva executada.
- API/Portal staging f9b5b2c 1/1, Worker 1c34ba0 0/1, Postgres18/1/1/5000MB,
  staged patch vazio no audit READ-ONLY de entrada; nenhum serviço foi alterado.
- Sem real destination/DNS/network delivery, segredo/certificado real, compra/custo,
  homologação, fiscal/pagamento/cutover/piloto/Go-No-Go/deploy externo.
- Limitação residual: operação real depende de autoridades/recursos externos e fases
  posteriores. Não é blocker para configuração interna certificável; não é prontidão comercial.
- PR/CI/main/closeout/certificação ainda pendentes deste candidato.

Próxima ação: concluir gates/PR/main/closeout da própria T03. Próxima Task apenas
após DONE_CERTIFIED: P02-T04. PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.
