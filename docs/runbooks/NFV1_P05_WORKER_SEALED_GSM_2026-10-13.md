# NFV1-P05-T01 — Worker GSM no Railway, procedimento do operador

Candidata sobre main `59963946c876b5db1c89f3f7b3047e44c2a51d79` (#176).
CI #833/run38324737715 e Governance #254/run38324737719 SUCCESS.
Não certifica P05, IAM real, envelope, SQL remoto ou processo Worker. Não fazer
merge/migrations/deploy sem autorização específica. Nenhum comando deste
procedimento foi executado no computador do proprietário pelo agente.

## Auditoria e menor adaptação

`worker_staging_gsm_bootstrap` mantém modo `scoped-staging-sa-v1`, identidade
restrita a staging e SA Worker, política de rotação, binding durável, IAM,
SecretResolver, DurableGsmReader, allowlist e seleção pré-claim de #176.
Adiciona alternativa exclusiva `NFCORE_WORKER_GSM_CREDENTIAL_JSON` (sealed)
à fonte existente `NFCORE_WORKER_GSM_CREDENTIAL_FILE`; não aceitar ambas.
JSON só é interpretado após o binding canônico válido. SDK recebe informação
em memória; não grava JSON no container nem aceita ADC/user credentials,
endpoint OAuth arbitrário, outro projeto/SA/universe ou key ID diferente do
recibo IAM. Erros são sanitizados. Retira a variável de `os.environ` ao consumir.
Não promete zeroização do signer SDK, strings Python, ambiente inicial do
processo ou leitura por administrador do host. Railway fornece variáveis aos
builds e runtime; não adicionar impressão de env, build hooks ou debug.

O bootstrap atual é de **um piloto governado**; não é registry comercial
multitenant dinâmico. Tenant/unidade/destino não vêm do payload outbox.
A readiness exige leitura GSM real com CRC32C/envelope/binding/version checks.

## Configuração não secreta preparada, sem deploy

Projeto Railway `b84b290d-f3b4-46a1-9023-0b761cb96b0d`, ambiente
`c9878b9b-62b2-4a97-b8ba-743c8a3e99ec` (label `production`, projeto **Staging**),
Worker `b3bde804-fa29-4c67-841d-7cda050c40e7`.

| Variável | Valor/autoridade |
|---|---|
| NFCORE_ENVIRONMENT | staging |
| NFCORE_PERSISTENCE_BACKEND | postgres |
| NFCORE_SECRET_BACKEND | external |
| NFCORE_REQUIRE_HTTPS | true |
| NFCORE_WORKER_ONESHOT | false, apenas no futuro deploy aprovado |
| NFCORE_WORKER_GSM_MODE | scoped-staging-sa-v1 |
| NFCORE_WORKER_GSM_RESOURCE | projects/fm-nfcore-staging/secrets/nfcore-stg-pilot-webhook-signing |
| NFCORE_WORKER_GSM_KEY_ID / KEY_CREATED_AT / KEY_NOT_AFTER | recibo IAM real do procedimento |
| NFCORE_WORKER_GSM_TENANT_ID / UNIT_ID / HOST_NAMESPACE | **pendentes**, registro/binding aprovado do piloto |
| NFCORE_WORKER_GSM_SIGNING_REFERENCE / SIGNING_VERSION | **pendentes**, binding canônico; cloud version 1 não determina versão canônica |
| NFCORE_WORKER_GSM_PROVIDER_ID / DESTINATION_ID | **pendentes**, adapter/egress registry governado real |
| DATABASE_URL | manter referência privada existente; não copiar valor |

Sem aplicar esta tabela enquanto faltarem IDs, binding e destino. Restart policy
legada NEVER e processo 0/1 precisam ser reconciliados no deploy aprovado, junto
com política canônica de drain/backlog. Não tratar deployment SUCCESS como RUNNING.

GCP informado pelo proprietário: Secret Manager habilitado; segredo acima com
cloud versão1 ENABLED; SA `nfcore-stg-worker@fm-nfcore-staging.iam.gserviceaccount.com`
com secretAccessor só nesse segredo; nenhuma chave criada. Não constatamos
conteúdo: o segredo **precisa conter `encode_gsm_envelope(binding, material)`**,
esquema1, binding exato (inclusive revisão/cloud_version), material base64 e
password null para assinatura. Chave aleatória sem envelope falha fechado.
Não alterar conteúdo/binding por suposição; reconciliar metadata antes de
provisionar e submeter qualquer criação/alteração necessária separadamente.

## Procedimento único Windows (CLI Google já autenticado)

Não usar Cloud Console/Commander nem exportar ADC. Executar localmente após
revisar a PR. Nunca enviar chave, token, DSN, PEM ou identidade age ao chat.

1. No Railway **Worker staging**, criar placeholder não secreto
   `NFCORE_WORKER_GSM_CREDENTIAL_JSON={"provisioning_pending":true}` e usar
   menu **Seal**. Deixar mudanças staged; **não Apply/Deploy**. O placeholder
   selado deve aparecer nos metadados da API para o script continuar; se
   staging não o tornar visível, parar, não publicar para contornar. Placeholder
   nunca é credencial válida. O conector MCP não tem flag sealed; não usá-lo
   para transferir a chave. O procedimento atualiza exclusivamente essa
   variável **já sealed**, com `skipDeploys=true`, sem replace global.
2. Pré-requisitos do operador: Python3.11+, gcloud oficial instalado/autenticado;
   token Railway limitado a este projeto/ambiente (entrada oculta getpass);
   diretório local fora de Git, OneDrive/Dropbox e backups automáticos, volume
   BitLocker 100% criptografado com proteção ON. O helper cria subdiretório
   efêmero e ACL somente SID atual **antes** de gcloud criar arquivo. Sem volume
   criptografado ou ACL válida, não cria chave. Administradores locais mantêm
   seu poder; não usar computador compartilhado.
3. O operador precisa de: `orgpolicy.policy.get` para política efetiva de
   expiração; `secretmanager.versions.get` para metadados versão1;
   `iam.serviceAccountKeys.list`, `.create`, `.delete` **nessa SA** para o fluxo
   aprovado. Não conceder Owner nem adicionar secretAccessor de projeto.
   Token Railway precisa ler metadados e atualizar variáveis desse Worker.
4. Expiração efetiva Google `constraints/iam.serviceAccountKeyExpiryHours`
   deve ser finita <=720h (preferir168h). Helper consulta política efetiva via
   gcloud e reconcilia `validAfterTime`, `validBeforeTime` e ID reais depois da
   criação. Sem política aplicável/permissão, **BLOCKED**, zero chave criada.
   O helper não muda Org Policy, IAM ou restrições de criação. Se a organização
   proíbe chaves, não contornar: nova decisão WIF será necessária. Datas
   locais do bootstrap não substituem revogação IAM.
5. Definir dono de rotação (ID interno não pessoal), vencimento no registro
   operacional e alertas antes de24h do prazo. Substituição requer novo recibo,
   variável sealed e deploy aprovado; revogar chave anterior só após validar
   novo Worker, deixando sobreposição curta. Falha de transferência revoga
   apenas chave recém-criada, não uma chave antiga em uso.
6. Executar primeiro **somente leitura** (sem chave/config/deploy):

   ```powershell
   python scripts/deploy/provision_worker_sealed_identity.py --protected-directory D:\NFCorePrivate --rotation-owner OPERADOR_ID
   ```

   Substituir caminho e ID por valores reais locais; nunca chave/token como
   argumento. O prompt pede token de forma oculta. O script não lê valores
   Railway nem material GSM. `READ_ONLY_PREFLIGHT_PASS` confirma pré-requisitos
   externos consultados, não prontidão Worker nem proteção do disco (esta é
   verificada imediatamente antes de criar a chave).
7. **Gate credencial real:** obter autorização específica para criar chave
   temporária protegida nessa SA, nesse segredo e nesse Worker, pelo prazo
   real comprovado, com dono/rotação. Aprovação de implementação/PR não é
   aprovação automática de credencial. Só então repetir o **mesmo helper**:

   ```powershell
   python scripts/deploy/provision_worker_sealed_identity.py --protected-directory D:\NFCorePrivate --rotation-owner OPERADOR_ID --approve-key-creation
   ```

   A chave passa do arquivo owner-only em disco criptografado para memória e
   HTTPS oficial Railway; nunca argv/clipboard/stdout. Metadata + JSON enviados
   em uma atualização sem deploy. Recibo confere isSealed antes/depois;
   nunca read-back do valor. Arquivo efêmero removido; não afirma secure erase.
   Erros HTTP/CLI brutos suprimidos. Não ativar transcript, --log-http, debug,
   captura de corpo HTTP ou encaminhamento de logs. A operação real desse
   helper **ainda não foi homologada** no Windows/Railway; testes são sintéticos.
8. Compartilhar só recibo `SEALED_CONFIGURED_NO_DEPLOY` e metadados não secretos
   (ID/validade/dono/selado). Não chave JSON. Conferir que não surgiu deployment
   novo e nenhuma mudança staged foi publicada. Se houver falha, usar mensagem
   BLOCKED curada para identificar requisito; não compartilhar stderr bruto.
   Revogação falha exige intervenção imediata no IAM local, antes de prosseguir.

Referências oficiais: [Railway sealed variables](https://docs.railway.com/variables),
[API variables](https://docs.railway.com/integrations/api/manage-variables),
[CLI snapshot/schema](https://github.com/railwayapp/cli/tree/a12a2571c87027655e8aeeb6b7d4519766aaa2be),
[Google expiry](https://docs.cloud.google.com/iam/docs/service-account-creds),
[gcloud org policies](https://docs.cloud.google.com/sdk/gcloud/reference/resource-manager/org-policies/describe),
[gcloud key lifecycle](https://docs.cloud.google.com/iam/docs/keys-create-delete).
O schema público do CLI não expõe opção sealed no upsert. Seu teste
`sealed_rotate_emits_update` e aplicação por `variableCollectionUpsert`
confirmam caminho de atualização de variável existente sealed; recibo runtime
continua obrigatório, pois código do fornecedor não prova execução neste ambiente.

## Após configuração GSM: preflight somente leitura e backup existente

GSM exige a credencial, binding/env/destino reais e envelope válido; schema17
é pré-requisito do binding durável. Sequência: configurar sealed, coletar preflight
SQL/backup, obter aprovação de migrations e binding governado se ausente, e só
então Worker novo consegue provar GSM runtime. Não exigir Worker RUNNING antes
de schema17 nem declarar GSM pronto apenas por selar a variável.

Postgres staging18 é privado, sem TCP proxy. Usar canal privado já autorizado
pelo operador; não criar endpoint público/proxy ou novo deploy para acessar SQL.
No checkout da revisão exata, fornecer DATABASE_URL em ambiente local protegido
(entrada oculta), NFCORE_ENVIRONMENT=staging e
PGOPTIONS=`-c default_transaction_read_only=on` ao processo; retirar DSN após uso.
Executar autoridade existente:

```text
python scripts/ci/migration_guard.py --plan-staging
```

Só SELECT, verifica fiscal e Cakto, versões contíguas/nomes/drift. Capturar
recibo sem DSN/payload. Resultado esperado com base na evidência de12/10,
**a reconfirmar**: fiscal1..12 e Cakto ausente; pendentes fiscal13..17/Cakto1..2.
Não executar --apply, initialize ou startup dos serviços como preflight.

Integridade **atual** do mesmo backup: executar helper canônico
`scripts/deploy/logical_backup_evidence.py` localmente com os envs documentados
no checkpoint de backup. SHA esperado
`58ae2d97cc40f26c89900e7f349211f89770255f57427231d38ac5f8bafeded6`,
78572 bytes; não atualizar mtime nem regenerar recibo para contornar janela72h.
Ele confirma checksum/header age e decrypt completo PGDMP em memória, sem
escrever plaintext. Restauração PG18,34tabelas/exit0 já atestada: não repeti-la.
Se backup não estiver acessível ou passar72h, gate bloqueado; eventual novo
backup segue autoridade existente e não recebe certificação herdada.

| Migration pendente | Impacto canônico |
|---|---|
| Fiscal13 | escopo fiscal e índices |
| Fiscal14 | configuração/revisões/metadados egress |
| Fiscal15 | ingress comercial Command |
| Fiscal16 | períodos/contratos comerciais |
| Fiscal17 | metadados de bindings de segredo |
| Cakto1 | tabelas comerciais Cakto |
| Cakto2 | callback/subscription metadata |

Executar policy check/testes/CI da candidata sem tocar banco remoto. Fiscal e
Cakto têm transações separadas: não afirmar atomicidade conjunta. Migrar schema
Cakto não ativa gateway nem aprova transação real. Autoridade apply única mantém
opt-in humano e rejeita execução dentro de Railway. Backup real atual + plano
SQL real + revisão exata + baseline/rollback + approval específicos precedem
aplicação. Merge adicional, migrations e publicação têm aprovações separadas.
Depois desses gates, API/Portal/Worker na mesma revisão, verificar réplicas
RUNNING/readiness/SHA e jornadas Web reais; piloto sintético/CI não substitui E2E.
