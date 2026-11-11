# NFCore — provisionamento da identidade Google EXISTENTE e transição GSM para Contabo

Data: 2026-11-11 · Estado: implementação interna candidata, ainda NÃO executada na VPS.
Issue de continuidade: #424 · Repositório: `faabio3131/nf-core-v001`.

## CURRENT confirmado

- O Plano B de auditoria na Contabo foi instalado e comprovado com `GSM_PLAN_B_GATE_INSTALLED_AUDIT_ONLY` e inventário real com `HOST/SOURCE_VS_DEPLOYED/DEPLOY_VS_PIN=PASS`.
- `nfcore-db`, `nfcore-api`, `nfcore-portal` estão saudáveis; `nfcore-worker` e `nfcore-bling-worker` ausentes. **Não repetir esse diagnóstico**.
- Railway `nfcore-worker` e demais serviços estão offline no último levantamento; volume PostgreSQL antigo deve permanecer até reconciliação.
- A service account Google `nfcore-worker@fm-nfcore-prod.iam.gserviceaccount.com` já foi criada, segundo evidências e proprietário; não duplicar.
- A execução contínua em `production` exige um JSON de chave de serviço existente montado, owner UID 10001, modo 0600, metadata da key ID e ciclo máximo de 90 dias. A existência da SA no GCP/Secret Manager **não comprova** que essa identidade privada já está montada na VPS.
- Código/corte de produção permanece em `production`. Integração de código Bling PR #422 na `main` **não aplica DDL 20/21**.

## TARGET da ferramenta

O script `deploy/contabo/stage-existing-gsm-identity.py` é um provisionador de escopo restrito, operado como root na VPS, com argumentos:
- `--mode check|stage`
- `--expected-production-sha SHA40`
- `--existing-identity-file /etc/nfcore/incoming/existing-worker.json`
- `--iam-key-created-at DATA_ISO8601_COM_FUSO` — data efetiva de criação da chave, conferida no Google IAM pelo operador; não usar data do arquivo.

Valida: servidor `vmi3692211`, checkout e `.deployed` da MESMA release `production`, conta `nfcore-worker` do projeto `fm-nfcore-prod`, token_uri oficial, ID de chave, validade até 90 dias, origem NFCore, owner root/mode 0600 do arquivo fornecido, diretórios confiáveis, ausência de target anterior; rejeita chave de outro SaaS ou IAM/SA de API.

**Somente `--stage`** cria sem sobrescrever:
- `/etc/nfcore/worker/worker-identity.json`: UID/GID 10001, 0600, namespace privado.
- `/opt/fm/nfcore/.env.worker`: metadados e flags do modo multiempresa, sem credencial privada.
- `/opt/fm/nfcore/.worker-compose.env`: apenas o bind path esperado pelo Compose; não altera o `.env` principal.

Os três arquivos são novos, gravados com criação exclusiva e tentativa de rollback em falha. O arquivo original autorizado é preservado no inbox até reconciliação; nenhum segredo é enviado ao GitHub, chat ou logs. Não cria conta GCP, IAM, Key, Secret Manager, tenant, binding, webhook, banco, imagem, fila ou worker. Não toca IRON nem expansão nacional.

## Operação após PR e CI verde, com aprovação do provisionamento

1. Localizar **fora do chat e do repositório** a chave privada da service account **existente** no cofre/arquivo seguro já administrado pela FM. Se o conteúdo privado antigo não existe, NÃO é possível rebaixá-lo do Console Google apenas pelo Key ID; qualquer emissão/rotação exige aprovação específica. Não confundir "SA criada" com posse de seu JSON.
2. Conferir o key ID e a data/hora de criação da chave no Google IAM, sem copiar a chave privada aqui. Confirmar que a chave ainda está habilitada e pertence à SA exata. Validar IAM `secretmanager.versions.access` por recurso/versão aprovada, nunca `secretAccessor` em projeto inteiro.
3. Por canal administrativo seguro, colocar o JSON autorizado, root:root 0600, em `/etc/nfcore/incoming/existing-worker.json` (pais `/etc/nfcore` e `incoming` root-owned, 0700). Não usar arquivo na pasta IRON, Railway, GitHub ou armazenamento compartilhado.
4. Carregar o script **do SHA revisado e integrado de main**, nunca da branch em Draft; preservar checkout `production`. O operador confere o SHA e instala cópia root-only do script no host via `git show`.
5. Executar `--mode check` com SHA completo atual da release implantada, caminho do JSON e data do IAM. Resultado obrigatório: `EXISTING_GSM_IDENTITY_STAGE_PREFLIGHT_PASS`.
6. Executar `--mode stage` com os mesmos argumentos. Resultado obrigatório: `GSM_EXISTING_IDENTITY_STAGED_NO_CONTAINER_STARTED`.
7. Executar **somente validação da composição**, sem subir serviço:
   `docker compose --env-file .env --env-file .worker-compose.env -f docker-compose.yml -f src/deploy/contabo/compose.worker.opt-in.yml --profile worker-authorized config --quiet`, na pasta `/opt/fm/nfcore`.
8. **Antes da ativação**: prova IAM real de acesso apenas a segredos autorizados, unicidade de consumidor/outbox e leases, backup+restore em banco isolado, integridade da imagem oriunda de `production`, plano de rollback e Go/No-Go. Sem estes gates, não executar `up`.
9. Ativar **somente** `nfcore-worker` após autorização operacional específica e manter os serviços API/Portal/DB intactos. Exigir health fresco, UID10001, rede interna, mount RO, nenhuma entrega fora de tenant/unidade homologada, logs redigidos, restart e recuperação de lease/retry.
10. Bling é fase independente: migrations 20/21 e OAuth/segredos do aplicativo próprios, API overlay na mesma API e worker opt-in. Não usar chave GSM para OAuth ou cofre fiscal.

## Decisões e limites

- Construir uma vez no runtime canônico; não copiar containers Railway, não criar segunda API, segundo cofre ou segundo worker de ensaio.
- Metadados de uma chave Google não equivalem à prova de chave privada válida nem de acesso IAM.
- Este utilitário **não certifica** backup/restore, entrega E2E, emissão de NF-e/NFS-e nem a segurança comercial. Esses gates precisam de evidências reais.
- A prioridade do teste contábil continua o percurso Web → RBAC/tenant/unidade → A1 legítimo → SEFAZ/prefeitura em HOMOLOGAÇÃO, independentemente do webhook GSM quando não for parte da jornada.
