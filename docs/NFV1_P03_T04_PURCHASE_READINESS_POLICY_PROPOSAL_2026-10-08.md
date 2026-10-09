# NFV1-P03-T04 — Purchase readiness: auditoria e política proposta

Data: 2026-10-08 (America/Sao_Paulo). Status: POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION.
Produto: FM NFCORE V1. Repositório: faabio3131/kordena-fiscal-engine-v2.
CURRENT auditado: main `5888efb7eba206bb348b54da6881afb64a4f2c38` (PR #138).

## CURRENT → TARGET

CURRENT: a função canônica `commercial_purchase_ready` exige pricing, release,
checkout e quatro capacidades de delivery, mas recebe um booleano de processamento.
No runtime, Command usa a existência do receiver; outros projectors injetados podem
usar a flag recebida. A composição registra capacidades principalmente pela existência
da composição, sem revalidar a disponibilidade do banco na leitura da oferta.

TARGET: a oferta e o início da aquisição usam a mesma avaliação determinística,
atual e fail-closed do caminho efetivamente composto. A avaliação não aprova
preço/release, pagamento, assinatura, tenant, OWNER ou produção fiscal.

## Fatos confirmados e limites

1. `runtime/api.py` atribui processamento Command por `command_receiver is not None`.
2. `CommandCommercialReceiver.authenticate` consulta binding e resolve segredo
   por scope/version/expiry/revocation; a oferta não executa essa validação.
3. Probe HTTP sintético, usando as fixtures existentes e forçando
   `receiver.store.binding` a retornar `None`, devolveu `purchase_enabled=true`.
   Não houve cobrança, escrita externa ou segredo real. Isso comprova o gap interno,
   não o estado de qualquer oferta implantada.
4. Testes dirigidos do CURRENT: 56 PASS, 32 SKIP (DSN PostgreSQL local ausente),
   zero FAIL; warning de depreciação Starlette/TestClient visível.
5. Staging Railway reconfirmado somente leitura: Portal/API/Postgres com 1/1,
   Worker 0/1; mesmos deployments históricos; patch staged vazio. Nome do environment
   na plataforma: production, dentro do projeto FM NFCORE Staging. Nenhum deploy.
6. CI pós-merge #695/run37861991715/job113599648193 e Governance #116/run37861991879 SUCCESS no merge exato: 41/41 etapas; 1504 Python/PostgreSQL, 14 frontend, 28 Playwright PASS; zero FAIL/zero SKIP. Logs Pytest319.65s, Playwright25.1s, uma warning TestClient visível. Fechamento persistido no corpo da PR #138.

## Reprodução local do gap (somente harness sintético)

Executar na raiz do CURRENT auditado, com dependências dev instaladas:

```bash
PYTHONPATH=tests/runtime python3 - <<'PY'
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_p03_t01_acquisition import composition, publish, security
from test_p03_t03_command import Checkout, backend
from kordena_fiscal.runtime import api
from kordena_fiscal.security.secrets import SecretResolver
with patch.object(api, 'PostgresFiscalDatabase', composition._RuntimeDatabase):
    checkout = Checkout()
    app = api.create_runtime_app(
        composition._settings(),
        command_secret_resolver=SecretResolver(backend(), environment='staging'),
        commercial_checkout_projector=checkout,
        commercial_checkout_starter=checkout,
        commercial_acquisition_security=security(),
        password_reset_delivery=composition._ResetDelivery(),
    )
    publish(app)
    receiver = app.state.nfcore_command_commercial
    with patch.object(receiver.store, 'binding', return_value=None):
        with TestClient(app, base_url='https://testserver') as client:
            print(client.get('/v1/commercial/offer').json()['purchase_enabled'])
PY
```

Resultado observado: `True`. TARGET para esse cenário: `False`.
Nenhuma conexão PostgreSQL/provider real é feita nesse probe.

## Política proposta como conjunto — T04-B01

1. Reutilizar `commercial_purchase_ready`, composição, receiver, `CommandCommercialStore`,
   `SecretResolver`, pricing/release e UoW existentes. Não criar segunda autoridade.
2. No runtime canônico, flag de processamento isolada não comprova receiver.
   Provider sem receiver e cadeia canônica compostos falha fechado. Não ativar
   Cakto por inferência; sua integração histórica não substitui Command.
3. Para Command, verificar ao menos um binding governado vigente para o produto,
   ambiente e versão exatos; binding ausente, desabilitado ou expirado não habilita compra.
   A configuração permanece exclusiva da autoridade platform existente.
4. A validação da credencial reutiliza o resolver governado no servidor, somente para
   referências dos bindings já cadastrados pela plataforma. A requisição pública
   não escolhe key, referência, versão, tenant, unidade, purpose ou destino.
   Material resolvido fica efêmero no contexto seguro e é descartado imediatamente;
   não é revelado à resposta, cache, log, artifact ou metadado de readiness.
5. Falha de resolução, escopo, versão, revogação, expiração, backend ou banco retorna
   readiness falsa. Nenhum positivo é mantido em cache para ultrapassar revogação.
   A aquisição assinada revalida imediatamente antes de persistir/iniciar checkout;
   a oferta nunca substitui a autenticação e revalidação do evento posterior.
6. A leitura pública deve ser limitada contra amplificação: avaliação limitada aos
   bindings do escopo, orçamento finito de candidatos, rate limit nos acessos que
   disparam a avaliação e falha fechada ao esgotar o orçamento. Timeout de backend
   pertence ao contrato/adapter; backend sem limite operacional comprovado não
   certifica operação externa. Parâmetros técnicos serão registrados nos testes/PR.
7. Falha de readiness mantém compra desabilitada e checkout URLs ocultas; resposta
   pública sanitizada sem referência de segredo, exceção bruta ou inventário interno.
   Reutilizar observabilidade/auditoria existentes; nenhuma nova PII.
8. Persistência canônica deve estar disponível; fulfillment, provisioning, activation
   e delivery precisam existir efetivamente na mesma cadeia. Não fazer cobrança ou
   entrega de teste para avaliar readiness. Preservar contratos e idempotência.
9. Readiness interna não significa canal comercial externo certificado. Testes
   sintéticos não habilitam produção; P5/P6/P8 e Go/No-Go permanecem obrigatórios.

## Por que requer decisão humana

O cronograma já autoriza corrigir readiness, mas a solução acima introduz uma nova
origem de acessos ao resolver de segredos: avaliação iniciada pela leitura pública
da oferta. A política T03 aprovou resolução no ingresso autenticado de eventos.
Essa ampliação de superfície deve ser aprovada como mudança de segurança sensível,
conforme AGENTS.md, seção “Parada obrigatória para decisão humana”.

Não foi implementada a nova resolução nem alterado o runtime nesta proposta.
Decisão solicitada: POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION para T04-B01 como
conjunto. Essa decisão não autoriza merge, deploy, credencial/cobrança real ou produção.

## Escopo, impacto e testes após aprovação

Impacto: commercial_readiness; application/commercial_acquisition;
application/command_commercial; persistence/command_commercial (consulta governada);
runtime/api; web/app e web/commercial_release; respectivos testes.
Sem nova API, auth, frontend, fila, banco ou mudança fiscal. Migration só se a
implementação demonstrar necessidade, com governança existente.

Matriz obrigatória:

| Caso | Oferta / aquisição esperadas |
|---|---|
| pricing/release/checkout ausentes ou revogados | compra falsa / aquisição bloqueada |
| receiver ausente ou provider incompatível | compra falsa / aquisição bloqueada |
| binding ausente/desabilitado/expirado/scope incorreto | compra falsa / aquisição bloqueada |
| segredo missing/revoked/expired/version/scope/unavailable | compra falsa / aquisição bloqueada |
| rotação/revogação sem restart | próxima avaliação respeita CURRENT |
| banco/migrations indisponíveis | compra falsa / nenhum checkout iniciado |
| fulfillment/provisioning/activation/delivery ausentes | compra falsa / aquisição bloqueada |
| cadeia completa no harness interno | compra interna possível, sem certificação externa |
| oferta consultada antes de revogação; aquisição depois | aquisição bloqueada |
| orçamento/rate limit excedido | bloqueio sanitizado, sem amplificação ilimitada |
| reinício/replay/resposta perdida | mesmos IDs e nenhuma duplicação |

Executar SQLite quando aplicável e PostgreSQL real na CI, testes HTTP/segurança,
Ruff/Mypy, plan/secret/migration checks e CI integral. Não remover/enfraquecer testes
anteriores: corrigir fixtures para compor o receiver quando o cenário exige compra.
P03-T05 não inicia antes de T04 certificada.

## Próxima ação

Aprovar ou ajustar T04-B01. Depois implementar e testar somente P03-T04 na mesma
linha evolutiva. Estado atual: BLOCKED_INTERNAL por decisão humana pendente.
PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.

## Publicação da proposta

A tentativa de push dos três documentos foi rejeitada pela revisão automática por
ausência de autorização explícita para publicar novos documentos nesta retomada.
Remote confirmado: repositório canônico acima; branch da proposta ausente no remoto.
Documentos preservados localmente. Publicação/PR Draft requer autorização explícita;
nenhuma tentativa alternativa de contornar a rejeição foi realizada.

## Decisão humana — 2026-10-08

Dono respondeu “Autorizo” à solicitação explícita de aprovar T04-B01 como conjunto
para implementação interna e publicar estes três documentos (política, cronograma,
ledger), com abertura de PR Draft. T04-B01 RESOLVIDO. A publicação rejeitada acima
fica preservada como histórico; a nova autorização cobre a tentativa subsequente.
Implementação e testes internos autorizados; merge/deploy/credencial ou cobrança
real/produção não autorizados. A implementação deve respeitar integralmente a política.

## CHECKPOINT DE IMPLEMENTAÇÃO — NFV1-P03-T04

Data: 2026-10-08 (America/Sao_Paulo).
Main de entrada: `5888efb7eba206bb348b54da6881afb64a4f2c38`, PR #138 MERGED,
CI #695/Governance #116 SUCCESS. PR ativa: #139 DRAFT.
Branch: docs/nfv1-p03-t04-readiness-policy.
HEAD/árvore/CI finais: registrados no corpo da PR #139, evitando SHA circular.
A auditoria/proposta acima permanece snapshot histórico; este checkpoint é superior.
CURRENT: IMPLEMENTED_NOT_INTEGRATED, certificação remota ainda PENDENTE.
TARGET: mesma oferta/aquisição canônicas, revalidação atual e fail-closed.

Mudanças: predicate canônico agora aceita avaliação operacional, valida itens contra
planos/preços ativos e preserva contratos provider-neutral. Runtime de lançamento
exige Command composto, NFCore product exato, migrations1..15, banco e serviços reais
na composição. Legacy receiver/flag isolados não habilitam compra. Command lê até
8 bindings habilitados do escopo (LIMIT9 detecta excesso), revalida scope/expiry,
resolve referência/version/purpose, exige chave compatível com HMAC e relê binding
após resolução. Resolução sem cache positivo; material efêmero descartado.

Limites técnicos: 120 avaliações/minuto por processo, bucket global fixo sem chaves
fornecidas pelo cliente; no máximo8 resoluções por avaliação; consultas de bindings
com statement_timeout2s. Cada aquisição pode consumir duas avaliações: antes da
referência e imediatamente após seu commit, antes de iniciar checkout. Excesso
bloqueia; não há bypass para aquisição. Limite distribuído e timeout do adapter
externo concreto continuam dependências operacionais P6/P9, não provas deste harness.

Oferta: no-store, URLs ocultas ao bloquear; readers indisponíveis falham fechado,
sem exceção bruta ou referência secreta. Aquisição: revalida catálogo/receiver após
commit; revogação nesse intervalo impede iniciar checkout, mantendo referência para
replay seguro. Autenticação/assinatura/rate limit/idempotência existentes preservados.
Nenhuma nova API/auth/frontend/tenant/persistence/fila ou migration.

Testes novos:32 casos em test_p03_t04_readiness.py (29 locais PASS/3 PostgreSQL
pendentes). Cobrem binding/secret denial, ambiente/produto, scopes/version/expiry,
zeroização, ausência de cache, catálogo revogado/plan/price/projection inconsistentes,
serviços ausentes, DB/migrations/readers, orçamento global, rotação sem restart,
SQL scoped/budget e revogação após escrita sem iniciar checkout. Fixtures T01 agora
compõem receiver Command real do harness e binding governado para cenários positivos;
assertions de replay/persistência/isolamento/perda de resposta preservadas.

Verificação local dirigida final:90 PASS/35 PostgreSQL SKIP/zero FAIL;Ruff PASS,
Mypy0 issues em192 source files;plan59 PASS;secret scan PASS;migration policy1..15
(Cakto2) PASS;diff check PASS. Warning Starlette/TestClient preservado.
Suíte completa local em execução; PostgreSQL real e CI integral ainda obrigatórios.
CI deve executar todas as jornadas, frontend, Playwright, containers/non-root,
smokes, vulnerability policy/SBOM, backup/restore e readiness no HEAD final.

Security/Tenant/Unit: nenhuma origem pública escolhe segredo/binding/scope; autoridade
platform existente configura. GET não cria aquisição/purchase/subscription/OWNER.
Callbacks de eventos mantêm autenticação e revalidação próprias. Sem nova PII.
Staging: mesmos deployments históricos,Portal/API/Pg1/1 eWorker0/1;patch staged
vazio, reconfirmado somente leitura na retomada. Nenhum deploy.
Dependências externas: Secret Manager/checkout/Command emissor/delivery reais não
certificados. Readiness interna não certifica canal externo.

Gate de saída: PENDENTE (CI final/revisão/integração).
Próxima ação: concluir gates da PR #139 e propor merge somente após CI verde.
T04 não marcada concluída; T05 não iniciada.
PRODUCTION_APPROVED=NO; COMMERCIAL_LIVE=NO.
