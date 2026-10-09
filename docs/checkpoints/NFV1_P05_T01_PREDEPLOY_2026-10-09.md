# NFV1-P05-T01 — Pré-deploy — 2026-10-09

Estado: BLOQUEADO EXTERNO, com pré-requisitos internos remanescentes. 23/59 tarefas concluídas. T02 não iniciada. O dono autorizou iniciar T01 (“Executar”); não houve deploy, alteração Railway, migration externa, criação/restauração de backup real ou acesso a material de credencial.

## Decisão posterior — 2026-10-09 — aprovada e merge #151 realizado

O dono respondeu “Autorizado” ao pedido explícito de integrar PR #151 e antecipar P6 antes de P5. PR #151 MERGED; HEAD `8bfa783180c99a8e0532822142ba128375f399bb`, main `250afa737fa970411d13fe1f48735b6147f9e13d`, árvore PR/main idêntica `7ff6b29b182e499ca5d1710d84ad43e93c6a4fb8`. CI PR #730/run37947093378 e Governance #151/run37947093342 SUCCESS:41/41 etapas,1673 Python/PostgreSQL,14 frontend,28 Playwright,zero FAIL/SKIP;um warning TestClient existente. Rehearsal PostgreSQL16 sintético pelo script canônico: backup,checksum -c,restore,sentinel,migrations e readiness PASS. Pós-merge CI #731/run37950345107 e Governance #152/run37950345322 ainda em validação na criação deste registro.

A ordem aprovada está aplicada neste diff documental: P6-T01..T04 antes de P5-T01..T05, mesmos59 IDs e todos os gates;23/59 concluídas. P6 depende de P1..P4 certificados e infraestrutura staging existente com autorizações próprias;P5 depende também de gate P6. Nenhum teste/validador foi alterado para permitir a nova ordem. P6-T01 só inicia após integração/certificação deste registro. B03 correções integradas;B04 decisão de ordem resolvida,adapter/assinatura/bootstrap reais pendentes;B01/B02/B05 continuam blockers. Reconfirmação read-only: deployments históricos inalterados,API/Portal/PostgreSQL1/1,Worker0/1. Nenhum deploy/migration externa/secret real.

O texto abaixo preserva o histórico da auditoria e da proposta anterior à aprovação. As frases “não aplicada”/“necessária decisão” abaixo são históricas e superadas pela decisão acima. Autorização de ordem/merge não seleciona provider nem autoriza conta/custo/IAM/credencial ou operação externa. Continuidade atual: integrar/certificar o registro de ordem aprovado e então NFV1-P06-T01 — Selecionar provider;P5 permanece não concluída.

## Revisão de entrada certificada

PR #150 MERGED, main `5b63449d9ef3bbe7fdf7023e1d9bdfd96235f00c`, árvore `ac9adaf6d763e00c1fd0c6aa030b3e49a6eafa68`, idêntica ao HEAD documental `8de87802792fcc97943026dfdc3106f256bfd164`. CI #728/run37942395431/job113859830414 e Governance #149/run37942395342 SUCCESS. 41/41 etapas;1666 Python/PostgreSQL,14 frontend,28 Playwright PASS,zero FAIL/zero SKIP. Gate P4 interno certificado; nenhuma PR aberta na entrada.

Esta prova supera as condições históricas do fechamento P4 nos documentos anteriores. A revisão final candidata ao deploy deve ser reconfirmada após qualquer nova integração; não implantar automaticamente este SHA de entrada.

## Runtime observado somente leitura

Projeto Railway FM NFCORE Staging `b84b290d-f3b4-46a1-9023-0b761cb96b0d`; ambiente `c9878b9b-62b2-4a97-b8ba-743c8a3e99ec` tem rótulo `production`, mas é o ambiente do projeto de staging. O rótulo não é autorização de produção. Região sfo.

| Serviço | Deployment atual / candidato a rollback | Revisão atual | Running |
|---|---|---|---|
| API | c0f8fb2b-30e3-45f8-a814-73c0ba97506b | f9b5b2c5b436045947159f1e76be9303f5a95d90 | 1/1 |
| Portal | 35b7aafc-b509-4851-a572-c0bd46781977 | f9b5b2c5b436045947159f1e76be9303f5a95d90 | 1/1 |
| Worker | 3215f498-0aa1-4ce3-8e61-cc74b72b68b6 | 1c34ba001935952f83ec0b065144e0b8311a5650 | 0/1 |
| PostgreSQL | ce9b66e7-6de7-4c70-9852-8ca1936a719b | imagem postgres-ssl:18 | 1/1 |

Os três deployments de aplicação têm status SUCCESS e canRollback=true. Isso identifica candidatos, não prova restauração operacional. O Worker candidato já está parado; não pode ser chamado de baseline saudável. Fonte Git main, Dockerfiles próprios; Postgres volume 5000 MB. Nenhuma alteração efetiva staged; environment_status também retorna um patch histórico vazio `8d720a42-c942-4afb-8bf5-cc22fce595cd`, enquanto describe_environment retorna staged=null.

HTTP observado nesta execução: API /health/live e /health/ready HTTP200 com status live/ready, Portal / HTTP200. Readiness da API prova o contrato de saúde da versão antiga; não certifica SHA novo, restore, schema atual ou E2E P5. Não houve consulta SQL direta; logs recentes do Postgres retornaram vazios.

API possui preDeployCommand `python scripts/ci/migration_guard.py --apply`. Antes do futuro deploy, coordenar esse comando com a migration única governada do fluxo, para impedir aplicação antes do backup confirmado. Worker restartPolicyType=NEVER, sem healthcheck de plataforma configurado; nome NFCORE_WORKER_ONESHOT presente e NFCORE_DEPLOY_REVISION ausente. Valores não lidos: nomes não provam configuração segura nem que ONESHOT está true. API/Portal têm nome NFCORE_DEPLOY_REVISION. Nenhum segredo/raw DSN foi registrado.

## Aceite de T01 e blockers

| Critério | Prova / lacuna | Estado |
|---|---|---|
| Main CI verde / SHA imutável | CI728/Gov149 e SHA acima; recertificar candidato final | PASS na entrada |
| Backup | Nenhum ID/status de conclusão/retention/cobertura confirmado pelo plugin | T01-B01 externo |
| Migrations governadas | Política local 1..16, Cakto2 PASS; versões reais atuais e compatibilidade ainda não lidas | T01-B02 externo |
| Rollback baseline | Três IDs candidatos acima; Worker0/1; nenhuma prova de compatibilidade pós-migration | T01-B02 externo |
| Scripts de restore / ordem | Correções descritas abaixo; certificação depende da CI desta PR | T01-B03 interno |
| Secrets fora de Git | Scan obrigatório; somente nomes de variáveis, nenhuma leitura de material. Backend concreto/IAM não certificado | T01-B04 externo |
| Postgres saudável | Replica1/1 e readiness da API antiga HTTP200; consulta SQL/versionamento/restore não confirmados | T01-B02 externo |
| Driver pode certificar deploy | SUCCESS pode ser antigo/Worker0; backup apenas solicitado; protocolo real de recibo/saúde não amostrado | T01-B01/B05 bloqueado |

T01 permanece não concluída. CI sintética não fecha B01/B02/B04/B05. T02 não pode executar enquanto estes pré-requisitos persistirem.

## Correções internas mínimas

1. pg_restore recebe a conexão por --dbname, mantendo checksum e --exit-on-error. Checksum usa -c, compatível GNU/BusyBox do Alpine. Antes recebia dois argumentos posicionais (URI e dump), que o cliente não aceita.
2. Validação de revisão usa comprimento40 e caracteres hex; o padrão anterior tinha39 posições e rejeitava SHA40 válido.
3. Novo prepare-rollback captura os três targets antes de backup/migration. Deploy exige arquivo preexistente e três entradas; não recaptura targets durante deploy parcial. Capturar IDs ainda não certifica sua saúde ou compatibilidade.
4. CI usa os scripts canônicos postgres_backup.sh/postgres_restore.sh no rehearsal PostgreSQL16 existente, mantendo sentinel, migration ledger e readiness após restore. Dados apenas sintéticos.
5. Testes de subprocesso: checksum corrompido não chama restore; falha de restore não anuncia sucesso; argumentos preservam caminho com espaços; falha em baseline/backup/migration impede fases seguintes; deploy sem baseline não inicia uploads.

Verificação local: 20 testes dirigidos PASS/zero SKIP, Ruff PASS, Mypy strict PASS(196 arquivos), migration policy PASS(1..16/Cakto2). CI inicial #729/run37945593582 (HEAD4adfd6ff6ea3bb2a615ce8028558868fe2eaf78d) passou testes/frontend/Playwright/containers, mas falhou no restore: BusyBox rejeita --check. Causa corrigida por -c; regressão exige opção portátil e checksum real. CI final da revisão corrigida ainda pendente neste commit. Não há PostgreSQL/CLI Railway locais para certificar integração externa.

## Plano concreto de migration e recuperação, ainda não autorizado

1. Fixar novo SHA final com CI/Governance verdes e árvores/revisão conferidas. Congelar mutações concorrentes durante a janela aprovada.
2. Por canal operacional governado, consultar SQL SELECT1 e versões da fm_schema_migrations e schema Cakto, sem exportar dados de clientes ou DSN. Histórico de 2026-10-04 indicava1..12/Cakto2; não inferir estado atual.
3. Capturar baseline completo antes de mutação: IDs, SHA, config refs e estado running de cada aplicação. Recuperar Worker contínuo exige a composição real abaixo; histórico0/1 não é baseline operacional saudável.
4. Criar backup pelo canal aprovado e esperar recibo de conclusão: projeto/ambiente/serviço/volume corretos, ID, horário, status final, retention, recuperação disponível. BACKUP_REQUESTED não autoriza migration. Não habilitar PITR automaticamente: isso pode criar bucket e redeploy.
5. Em banco descartável isolado e autorizado, provar restore e compatibility dos baselines com migrations pendentes13..16 (se query confirmar12). Sem dados reais em Git/log; checar snapshot/idempotência/numeração/outbox/inbox. Nenhuma down-migration automática ou restore in-place para rollback de app.
6. Só após autorização específica T02: aplicar migration_guard uma vez com before/after registrados e backup confirmado; conciliar preDeploy da API; implantar três serviços no mesmo SHA; observar deployment da operação atual, revisão e processo/health contínuos.
7. T03 smoke/T04 E2E/T05 rehearsal continuam em ordem. Falha de migration ou deploy parcial precisa plano de recuperação explícito; o fluxo atual só invoca rollback ao falhar worker/smoke. Não habilitar esse fluxo para execução real até corrigir B01/B05 e esse tratamento de falha.

CLI oficial confirma `railway postgres pitr backup create` como solicitação e `backup list` para listar recibos. Plugin OAuth atual não expõe backup/PITR/SQL; CLI não instalada e nenhum token local foi buscado. Sem acesso autorizado ao canal operacional, status final do backup e query real permanecem externos.
Fonte oficial consultada: https://docs.railway.com/cli/postgres e https://docs.railway.com/guides/postgres-backups-restores .

## Decisão de dependência P5/P6 proposta ao dono

O CMD atual chama worker_main.run() sem WebhookSecurity injetada. Sem ONESHOT, a composição rejeita dependências ausentes antes de consumir jobs. ONESHOT apenas consulta DB e termina; fake CI não entra na imagem. Não basta mudar ONESHOT/restartPolicy ou adicionar NFCORE_SECRET_BACKEND=external.

P5 exige Worker running>0 com handler real; assinatura depende de ExternalSecretClient concreto, cujo adapter é P6. P6 hoje depende operacionalmente de P5. É um ciclo comprovado por código/cronograma, não resolvido por CI verde.

Proposta para aprovação, ainda NÃO aplicada:

- antecipar P6-T01..T04 como dependência antes de retomar/concluir P5-T01; manter os mesmos59 IDs, mover a seção P6 antes de P5 no cronograma e os quatro itens correspondentes no ledger (renumerando índices), preservar validador e todos os gates;
- substituir a dependência P6=P5 certificado por P1..P4 certificados + infraestrutura staging existente + autorização específica de provider/IAM e prova externa; P5 passa a exigir também gate P6;
- P6-T01 seleciona provider por IAM/rotação/auditoria/custo/recovery; nenhuma escolha, conta, custo ou credencial é aprovada por esta proposta;
- composição bootstrap do Worker usa apenas boundary canônica e referências escopadas; provider concreto, IAM e operação externa exigem aprovação própria; não permitir assinatura fake, backend memória ou worker sem operações;
- após P6 e retomada T01, corrigir/validar recibo do backup, identidade da operação/revisão e saúde real no driver com contrato de resposta observado; resolver B05 antes de qualquer deploy. Reconciliar restartPolicy/healthcheck/revision como configuração candidata revisável, aplicada somente no T02 autorizado;
- não antecipar P7/P8/P9/produção, deploy, DNS, compra, emissão fiscal ou tratamento novo de dados.

É necessária decisão explícita por alteração da ordem aprovada e boundary de segredo real. AGENTS.md exige autorização antes de “mudança de segurança sensível”, “segredo/certificado/credencial real” e “deploy”; o padrão exige persistir alteração de escopo antes de execução. Proposta revisável nesta PR, sem alteração efetiva de ordem.

## Continuidade

Integrar correções somente mediante autorização de merge específica. Mesmo integrada, esta PR não conclui T01 nem libera staging. Depois de decisão do dono, persistir a ordem aprovada em PR própria, recertificar governança e executar uma tarefa por vez. PRODUCTION_APPROVED=NO;COMMERCIAL_LIVE=NO.
