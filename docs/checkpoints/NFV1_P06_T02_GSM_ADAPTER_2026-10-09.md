# CHECKPOINT — NFV1-P06-T02 — Implementar adapter de infraestrutura

Data:2026-10-09. Produto FM NFCORE V1. Repo faabio3131/kordena-fiscal-engine-v2.
Main de entrada:a32891ca74616e4a435c9c11055e6b4f8ba3bb64;PR154 MERGED;CI738/run37966054249 e Governance159/run37966054229 SUCCESS;41/41 etapas,1673 Python/PostgreSQL,14frontend,28Playwright,zeroFAIL/SKIP. Fechamento T01 integrado/certificado;24/59 concluídas. PR154 registra prova final e supera campos históricos pendentes dos documentos T01.

Autorização: “Executar” em2026-10-09;política T01 integral já aprovada para implementação interna. CURRENT: boundaries externas sem driverconcreto. TARGET: acesso GSM pelo SDK oficial, versões numéricas pinadas/CRC32C/envelope estrito;bindings metadata-only no mesmo banco/UOW;projeções ref:fiscal e sec_assinatura distintas, contexto validado antes do I/O, composição explícita reutilizando vault/resolver/worker canônicos. Nenhuma regra fiscal no adapter.

Mapa mínimo: security/secrets contexto antes de fetch;vault/external contexto antes de fetch;novo adapter infraestrutura e binding;persistência canônica SQLite/PostgreSQL com migration17 aditiva;factoryruntime recebe identidade explícita, nunca ADC implícita/URL do browser. Não criar auth/control-plane/queue/serviço de segredos paralelos. Writer de binding somente autoridade platform_admin existente, CAS/audit na mesma transação;reader não escreve. Worker usa dependência de assinatura explícita e nega escopo incompatível, sem alegar que client fiscal sozinho resolve bootstrap. Perfilruntime external preservado.

Teste:SDK fake transport com dados exclusivamente sintéticos (não prova cloudreal),envelope/schema/CRC/versão/timeout/exception sanitization/semcache;binding durável restart/CAS/rollback/no material,SQLite ePostgreSQL,migrationfresh/upgrade;contratos existentes vault/security/Worker. Ruff/Mypy/Pytest/fullCI eplanvalidator obrigatórios. PR/HEAD/CI finais serão registrados na PR após publicação.

Staging read-only:API/Portal/PostgreSQL1/1,Worker0/1;deployments históricos inalterados. SemSQLreal,conta,gasto,IAM,keyreal,deploy,DNS ouprodução. B02externo permanece:account/project/region/billing/budget/identity/IAM/canal não confirmados. WIFRailway não comprovada;bootstrapreal não executado. P06T03/T04 não antecipadas como certificação. Providerreal exige autorização e evidência posteriores;production_safe não é homologação.

GateT02:IN_PROGRESS,não concluído. Próxima ação:implementar/testar/publicar Draft ecertificar todos gates;merge exige autorização própria. GateP6 não satisfeito;PRODUCTION_APPROVED=NO;COMMERCIAL_LIVE=NO.

## Revisão e testes locais

Implementação presente:driver SDK,readerdurável/projeções,adminbinding platform_admin/CAS/replay/audit,composição vault/resolver/Worker explícita. Semnovo endpoint/handler/queue ouextraauth. Migration17 metadata-only é aditiva;testesantigos exigem17 preservando todos os checksanteriores;fixtures deupgrade reconstroem o esquema anterior inclusive removendo tabela17 somente em teste. DependênciasSDK/CRC acrescentadas explicitamente ao contrato estrutural. Código não importa domínio privado deoutroSaaS. Reader não administra cloud;envelopeencoder não fazupload. Runtimeconfigexternal preservado;bindingserveclientes porconfiguração,semalterarcódigoporreferência. A composiçãoWorker destaT02 é explicitamente limitada ao escopofornecido;fora dele nega antes deI/O/delivery. Registro dinâmico multitenant deassinatura/runtimeRailway não declaradooperacional;bootstrapreal continuaB02/P5.

Ruff eMypy strict201arquivos PASS.38testesnovos locais semPostgreSQL PASS;30casosnovos PostgreSQL ficam naCI integral,sem mudar skips/seleção remotos.25casoscompatibilidade/migration PASS. Ambiente local não disponibilizou PostgreSQLnemcontainer:tentativa deisolamento localnãoiniciouservidor,semusarDBreal/credencial. Resultados locais não substituemPostgreSQLnaCI. Revisão ampla encontrouexpectativasantigasdemigration/dependências;corrigidas mantendoassertsexatos,semmascararfalha. CI integral obrigatória antes depropor merge.

## Resultado local e bloqueio de publicação — 2026-10-09

Commit implementação local76881f52dff991ef8067bc6d93240ef1947b1c3e,tree4a885f735ee1ad199691934db69ff52f9c0fed00. SuítePython local final:1455PASS,0FAIL,286SKIP exclusivamente por pré-requisitos externos/DB ausentes;1warningTestClientpreexistente;115.93s.68casosnovos coletados (38 locais,30PostgreSQLnaCI). RuffPASS,MypystrictPASS201,planvalidatorPASS59/primeiraT02,secret scanPASS,diffcheckPASS. Este resultado não certifica os casos pulados nem providercloudreal. Nenhum gate remoto foi removido ouenfraquecido. Frontend/containers/backup-restore completos ePostgreSQL precisam daCIapós publicação.

P6-T02-B01 PUBLICATION_APPROVAL_REQUIRED: revisão automática rejeitougitpush. Primeiroalegou destinoGitHubnãoverificado;read-only confirmourepo canônicofaabio3131/kordena-fiscal-engine-v2 público epermissão deescrita. Nova tentativa apósverificação continuou rejeitada:autorização“Executar”cobreimplementação,mas nãodivulgação pública do código novo. Branchremota não existe (404),PRnãoaberta;nenhumpush concluído. Solicitar autorização explícita para publicar o diffconcreto no repo público eabrirPRDraft,entãoexecutarCIintegral. Não contornar rejeição porAPI/indireção. Maina328 permaneceintocada;T02 emexecução,24/59 concluídas. PolíticaGSMpermaneceaprovada;nenhumanovaaprovaçãodepolítica pedida. Merge/deploy seguemgatespróprios.

## Decisão superior — publicação autorizada

Em2026-10-09 às15:18 America/Sao_Paulo, após revisar o pedido explícito de divulgação no repositório público faabio3131/kordena-fiscal-engine-v2, abertura de PR Draft e CI completa, dono respondeu “Autorizado”. P6-T02-B01 RESOLVIDO; este registro supera o bloqueio histórico acima. Publicação/PR/CI autorizadas; merge exige autorização própria, operação externa/deploy não autorizados. Main reconfirmada a328, zero PRs abertas, CI738/Governance159 SUCCESS. Staging read-only: mesmos deployments, API/Portal/PostgreSQL1/1, Worker0/1. Auditoria local pip-audit: nenhuma vulnerabilidade conhecida.

## Certificação pós-merge e fechamento — registro superior

PR #155 MERGED; HEAD `5eb98614f4dfdc092871bb6e06c1efef7825e6ba`; main `8ad5a20e8ec954ef91f5e2c8f77a17ad09e8e62b`; árvore idêntica `5531ec7f0d7da61c59f92117b08f56807fae8715`. CI #739/run37973027312/job113964215052 (PR), #740/run37978308311/job113982097370 (main), Governance #160/run37973027313 e #161/run37978308448 SUCCESS. PR/main:41/41 etapas;1741 Python/PostgreSQL,14 frontend,28 Playwright PASS/zero FAIL/zero SKIP;um warning TestClient preexistente. Backup/restore PostgreSQL16 sintético, checksum e readiness PASS.

Autorização específica merge155: “Autorizo”,2026-10-09 às16:09 America/Sao_Paulo. MainPytest1741PASS/0FAIL/0SKIP,1warning em331.94s;Playwright28PASS em19.9s;frontend14PASS/0FAIL/0SKIP. Gates de segurança/migrations/auditorias/containers/SBOM/backup/restore/readiness PASS. Nenhum caso PostgreSQL ficou pulado naCI.

P6-T02-B01 RESOLVIDO;doccampos antigos deCI/mergependentes acima são históricos e superados. T02 DONE_CERTIFIED interno, condicionado à integração/gates deste fechamento documental. Ledger25/59 concluídas após fechamento;primeira pendenteT03,não iniciada. Esta revisão só atualiza plano/ledger/CURRENT/checkpoint;sem mudança de código/teste/migration/workflow. A evidência final de suaPR/CI será registrada naPR.

Read-only apósmerge confirmou mesmos deploymentsAPI/Portal/Worker/Postgres e réplicas1/1,1/1,0/1,1/1. B02 continua bloqueio de operação externa real; composição explícita não instala bootstrapRailway ouregistry dinâmico multitenant. T03/T04/P5 não certificados;gateP6não satisfeito;PRODUCTION_APPROVED=NO;COMMERCIAL_LIVE=NO. Semconta/IAM/gasto/keyreal/cloudI/O/deploy/SQLreal/DNS/emissãofiscal.
