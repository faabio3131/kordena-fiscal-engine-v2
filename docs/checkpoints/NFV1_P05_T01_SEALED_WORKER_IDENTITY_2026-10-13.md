# NFV1-P05-T01 — sealed Worker GSM identity, candidata

## CURRENT reconfirmado

- Main `59963946c876b5db1c89f3f7b3047e44c2a51d79`, PR #176 MERGED.
- CI #833/run38324737715 SUCCESS:41/41 etapas,2208 Python/PostgreSQL PASS,
  zero FAIL/SKIP,1 warning TestClient preexistente; Governance #254/run38324737719 SUCCESS.
- Worker Railway staging deployment `3215f498-0aa1-4ce3-8e61-cc74b72b68b6`,
  legado Oct1, restart NEVER; sem nova revisão/publicação, sem volume/domain,
  seis nomes de variáveis existentes. SUCCESS não prova processo1/1.
- GCP CLI/secret/IAM informado pelo dono, não consultado autenticadamente nesta
  sessão. Sem Commander/Console retries nem comando no computador do dono.

## Escopo autorizado e mudança

Continuação P05-T01 conforme instrução atual do dono; não fecha P09 nem altera
ordem/IDs/contagem. Ledger27/59, P05 BLOCKED_EXTERNAL. Cronograma e ledger
atualizados antes do patch. #176 isolamento pré-claim preservado.

Bootstrap aceita fonte JSON sealed exclusiva, bounded/unique strict SA fields,
project/email/token_uri/universe fixos, key_id pin por recibo IAM. Parse somente
após binding; preserva SecretResolver, policy de rotação, allowlist, seleção de
claim e resolução GSM real antes de readiness. Não grava identidade no container.
Fonte privada de arquivo preservada. Sem ADC/user token/fallback.

Procedimento `scripts/deploy/provision_worker_sealed_identity.py` é **operator
local**, Windows-only/terminal interativo. Requer placeholder previamente sealed,
Google-expiry efetiva <=30dias, diretório owner-only em BitLocker ON, aprovação
específica e dono de rotação. CLI oficial cria arquivo privado efêmero; SDK
identity futura recebe sealed JSON em memória. Transferência HTTPS sem deploy,
recibo isSealed antes/depois, metadata real IAM, chave nova revogada em falha.
Não lê valores Railway/GSM para gerar recibo nem altera políticas IAM. Sem
prova operacional real desse helper no Windows/API. Signer/strings Python não
prometem zeroização. Runbook detalha proteção, gates e campos reais pendentes.

## Validação candidata

Ruff src/tests/scripts PASS; Mypy strict203 módulos PASS; migration policy PASS
fiscal1..17/Cakto2; check_nfcore_plan PASS59 tarefas,27 certificadas preservadas.
Testes novos de sealed/bootstrap e operador: sintéticos, sem rede/cloud real.
Suite completa e CI desta candidata serão registradas na PR após execução.
Não substituir prova SQL remoto ou Windows pelo teste sintético.

## Gates reais pendentes

1. Credencial protegida sealed + recibo IAM efetivo/dono/rotação (ainda não criada).
2. IDs reais de tenant/unidade/host/destino/provider/reference/canonicalversion;
   binding governado e envelope GSM exato na versão cloud1. Não inventados.
3. Canal PostgreSQL privado, preflight somente leitura e integridade atual do
   mesmo backup age (checksum/decrypt/janela72h). RestorePG18 já comprovado não
   será repetido. Arquivo backup/identidade age não disponíveis neste workspace.
4. Aprovações específicas: merge adicional; credencial real; eventual metadata
   de binding/envelope; migrations13..17/Cakto1..2; deploy mesmoSHA dos3serviços.
5. Runtime real1/1/SHA/readiness/GSM + jornadasWeb, sem concluir por mocks/CI.

Plano migration preparado no [runbook](../runbooks/NFV1_P05_WORKER_SEALED_GSM_2026-10-13.md).
Nenhuma alteração schema, migration, IAM/secret/key real, env real ou publicação
executada. P05-T01 e P05 completa permanecem não concluídas.
