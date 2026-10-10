# CHECKPOINT — NFV1-P06-T03 — Certificar escopo

Data: 2026-10-10. Produto: FM NFCORE V1. Repositório: faabio3131/kordena-fiscal-engine-v2.
Main de entrada: `4855613613eb8d265fe62289fff39fe5ab710c4c`.
Branch: `test/nfv1-p06-t03-secret-scope`. HEAD/PR/CI desta entrega: registrar na PR após publicação.
Estado: IN_PROGRESS;25/59 tarefas concluídas;T03 não marcada concluída;T04 não iniciada.

## Predecessor e autorização

PR156 MERGED;fechamentoT02 certificado no mesmo SHA acima. CI742/run37989321439,
tentativa3/job114121909282 SUCCESS41/41;Governance163/run37989321416 SUCCESS.
1741Python/PostgreSQL,14frontend,28Playwright PASS/0FAIL/0SKIP;umwarningTestClient
preexistente;backup/restore/checksum/readiness/containers/security PASS.
DockerHub429 resolvido após intervalo sem alterar código/testes/workflow/registry.
Registro final da PR156 supera suas pendências históricas e as dos arquivos T02.
Retomada reconfirmou main/CI e zeroPRs abertas antes da mudança.

Dono autorizou execução P06-T03 em2026-10-10: “Pode executar”. Políticas T01/T02
continuam aprovadas;certificação usa suas autoridades sem nova política de segurança.
Autorização cobre implementação/testes internos,branch/PRDraft/evidência segundo ledger.
Merge,deploy,conta,gasto,IAM,credencialreal e operação cloud seguem gates próprios.

## CURRENT → TARGET e mapa de impacto

CURRENT: adapterGSM e migration17 integrados;testes T02 cobrem driver/binding e
assinatura,mas fiscal detalhado de escopo ainda exige matriz T03.
TARGET: provas reproduzíveis nas quatro classes(signature/certificate/csc/credentials),
SQLite e PostgreSQL reais para persistência;payloads de provider exclusivamente sintéticos.
Não afirmar homologação Google Cloud/IAM a partir destas provas.

Reutiliza SecretBindingAdministration,AuthenticatedHuman/platform_admin,SecretBinding,
DurableGsmReader,GoogleFiscalSecretClient,GoogleSignatureSecretBackend,SecretResolver,
ExternalFiscalSecretVault,mesma UOW/bindingrepository/controlplaneaudit.
Autoridades permanecem server-side;frontend não participa da decisão.

Mudanças: um arquivo novo de testes de certificação e este checkpoint;cronograma,
ledger e CURRENT recebem estado da tarefa e evidência final do predecessor.
Nenhum código deprodução,migration,API,auth,domínio,dependência,workflow ou serviço muda.

## Critério de aceite e matriz de prova

Critério específico: “Tenant, unidade, ambiente, provider, purpose, version e expiration.”

| Dimensão | Prova direta nesta revisão |
|---|---|
| Tenant/unidade | Binding fiscal diferente nega antes deI/O;referência/contexto discordantes negam no vault;admin não reatribui identidade existente;envelope adulterado nega nas4classes. |
| Ambiente | Separação staging/production runtime e homologation/production fiscal;reference/context;envelope;admin imutável. |
| Provider | CSC ecredentials particionados;provider diferente nega antes deI/O;assinatura/envelope;admin não muda provider existente. Certificado não possui providerbinding. |
| Purpose/kind | Contratos canônicos exigem pares válidos;envelope adulterado em4classes nega;referência kind divergente nega no vault;admin não muda purpose existente. |
| Version | Caminho de sucesso chama exatamente cloudversion9(pinned),não alias;envelopecanonical/cloudversion adulterados negam. Fiscal canonicalversion éstring fiscal-v3,auditada;signaturecanonicalversion éint3. TestesT02 preservados provam versão assinatura divergente antes deI/O e tipo estrito. Referência fiscal canônica não tem campo version;bindingdurável éautoridade dessa projeção. |
| Expiration | 1microsegundo antes permite,instante exato nega antes deI/O,expiração durante callbackprovider nega na revalidação após leitura,em4classes. |
| Workload | Fiscal divergente nega antes deI/O;envelope/admin impedem troca. |
| Acesso sem contexto | Métodos antigos unscoped de ambas projeções negam sem chamar provider. |
| Auditoria/persistência | Sucesso produz evento resolved metadata-only;negação não produz resolved;tamperingnãoleakmaterial;admin rejeitado não altera binding nem audit existente. |

Arquivo: `tests/vault/test_p06_t03_scope_certification.py`.
98casos porbackend,196casos totais novos;cada um usa persistência real do backend
selecionado. Nenhuma alteração de teste antigo,skip policy ou seleção deCI.
PostgreSQL segue convenção vigente: só é skipped localmente semDSN;sua CI dispõe de
PostgreSQL16 e deve executar todos os casos com0SKIP. Nenhum acesso ao banco do staging.

## Gates e resultado local

RuffPASS;Mypystrict201PASS. Rodada dirigida T03+T02:136PASS,0FAIL,128SKIP por
PostgreSQL local ausente. Isso corresponde T03:98PASS/98SKIP eT02:38PASS/30SKIP.
Suíte local integral:1553PASS,0FAIL,384SKIP porprérequisitosPostgreSQL/externos locais ausentes;umwarningTestClientpreexistente;113.93s. MatrizT03 final com relógiosdeterminísticos nos dois boundaries:98PASS/98SKIP em1.29s,196coletados. Resultado local não substituiPostgreSQL/CI.
CI remota integral obrigatória para PostgreSQL/frontend/E2E/containers/security/restore.
Rode `python3 scripts/check_nfcore_plan.py`,secret scan,diffcheck antes daPR.
Não declarar itemcertificado só pelos resultados locais.

## Staging, blockers e riscos

Read-only reconfirmado2026-10-10:mesmos deploymentsAPIc0f8fb2b-30e3-45f8-a814-73c0ba97506b,
Portal35b7aafc-b509-4851-a572-c0bd46781977,Worker3215f498-0aa1-4ce3-8e61-cc74b72b68b6,
Postgresce9b66e7-6de7-4c70-9852-8ca1936a719b. Running1/1,1/1,0/1,1/1.
WorkerOnline não comprova processo ativo;driftmain/staging continuaP5.
Patchstaged histórico `8d720a42-c942-4afb-8bf5-cc22fce595cd` tem zerochanges.

P6-T01-B02:conta/projeto/região/billing/budget/identidade/IAM/bootstrap/canal e
prova de acesso real aoGSM não confirmados. SemKYC/cloudI/O/SQLreal/secretreal/deploy.
Bindingadmin interno exige identidade canônica autenticada;esta revisão não criaendpoint
ou claimbrowser capaz de concederplatform_admin. BootstrapRailway/registryWorker
dinâmicomultitenant não certificados. CompositionWorker limitada ao escopoexplicitamente
fornecido;T03 não promove production_safe para prova deprodução.

GateT03:IN_PROGRESS atéPR/CI/evidência/integração autorizada.
GateP6 externo não satisfeito;PRODUCTION_APPROVED=NO;COMMERCIAL_LIVE=NO.
Próxima ação:terminar gates locais,publicar PRDraft,certificar CI no HEAD exato;
solicitar merge somente após prova concreta. T04 permanecependente.

## Pré-publicação

Validador planoPASS59/primeiraT03;secret scanPASS;diffcheckPASS;migrationpolicy1..17PASS. Revisão final contém somente5arquivos(testes+4documentos);nenhumcódigodeprodução. Relógio fiscal eassinatura explicitamente fixados nos testes para não depender da data futura daCI. HEAD remoto eCI serão registrados no corpo daPR,sem reescrever árvore após certificação. Merge continua nãoautorizado.
