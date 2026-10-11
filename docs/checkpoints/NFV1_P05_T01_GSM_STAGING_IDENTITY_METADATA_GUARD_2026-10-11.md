# NFV1-P05-T01 — preparação segura do bootstrap GSM staging

Data: 2026-10-11. Não certifica provider externo nem habilita Worker.
CURRENT verificado antes do patch: main `d90f6f91ba7b86b6b66ff0160ba34a5a1d47e06f`, PR #164 merged, #165 aberta (Draft), CI main #786/Governance #207 SUCCESS.

## Decisão operacional
O dono autorizou preparar a exceção staging somente, **sem criar ou distribuir chaves** até revisão específica. Houve tentativa de publicar carregador que acessava bytes de uma credencial selada, bloqueada por segurança. Não foi contornada. Este patch limitado NÃO lê variável de credencial, private_key, disco, SDK ADC ou serviço remoto.

## CURRENT → TARGET limitado
- CURRENT: `build_google_sdk_access` exige credencial explícita e prazo <=30 dias para SA staging, mas a identidade esperada de API/Worker não está vinculada ao projeto/workload nessa factory.
- TARGET interno: validar `ServiceAccountCredentials` já fornecida pelo canal autorizado, ambiente exato `staging`, projeto `fm-nfcore-staging`, identity email distinta por workload, emissão <= horário atual e expiração futura <=30 dias da emissão; delegar ao adapter GSM canônico, sem novo transporte ou secrets store. Falha antes de inicializar o client Google.
- Sem assumir que timestamp fornecido pelo operador prova data real da chave: comparação IAM keyID/time ainda obrigatória.

## Alterações
- `src/kordena_fiscal/runtime/gsm_staging_identity_policy.py`: guarda apenas de metadados (não chama getDefaultCredentials; não descobre chaves nem lê env), API e Worker estáticos e distintos; delega a `build_google_sdk_access`.
- `tests/runtime/test_p05_t01_gsm_staging_identity_policy.py`: testes parametrizados com objetos Mock do SDK, nenhuma credencial real, sem cloud; aceite API/Worker, bloqueio ambiente e workload incompatíveis, projeto errado, expiração, janela futura, timezone e identidade ambiente. Mock de client verifica zero I/O antecipado.

## Excluído / bloqueado
- NÃO implementado: parser/carregador de Railway sealed variable nem mecanismo de distribuição de service-account key. Não alegar `bootstrap` operacional.
- NÃO gerar key JSON, grants extra, variáveis Railway, IAM externo, SQL/backup, deploy nem código de autorização multitenant Worker.
- `NFV1-P05-T01=[ ] BLOCKED_EXTERNAL`, `EXTERNAL_SECRET_BACKEND_CERTIFIED=NOT MET`, `STAGING_CURRENT_SHA_E2E_CERTIFIED=NOT MET`; 27/59 tarefas internas inalteradas.
- Tests/CI e PR externos ainda exigem gates; merge somente quando especificamente autorizado.

## Próximos gates
Ruff, Mypy strict, testes novos, pytest/PostgreSQL full, frontend/E2E/container/SBOM/secret scan/plan validator e CI remoto sobre SHA exato. Depois revisar estratégia de material selado via Railway sem jamais aceitar secrets em git/log/prompts, provar key inventory e Data Access/restore antes de qualquer deploy.
