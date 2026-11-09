# Bling — ingresso durável e handoff fiscal

Estado: **IMPLEMENTED_CANDIDATE / bloco original EM EXECUÇÃO / NOT_DEPLOYED**.

## Implementação executável

`POST /webhooks/bling` autentica o corpo exato com HMAC SHA-256, valida empresa,
versão v1 e evento `order.created`, `order.updated` ou `order.deleted`. Confirma 202
somente após a transação que grava inbox e job. Duplicatas não criam novos jobs;
mesmo evento com conteúdo diferente recebe 409. Corpo máximo: 1 MiB.

O Worker existente, no modo `NFCORE_WORKER_CONNECTOR=bling`, resolve novamente o
vínculo exato a cada despacho. Consulta o pedido por OAuth no host fixo oficial,
preserva os valores decimais e arquiva o snapshot. Pedidos incompletos ficam em
revisão. A normalização consultiva nunca determina impostos nem produz XML.

Um operador vincula o hash revisado a um documento modelo 55 **já preparado pela
aplicação fiscal canônica**, no mesmo namespace, tenant, unidade e ambiente.
Essa aprovação e o job de emissão são atômicos. Um documento não pode atender a
pedidos diferentes. A aplicação canônica reserva a transmissão antes de chamar o
provedor: timeout ou retomada exige reconciliação, sem retransmitir automaticamente.

Resultados são persistidos e enfileirados atomicamente para:

- consulta S2S `GET /v1/integrations/bling/orders/{order_id}`, capability `fiscal.query`;
- webhook de resultado pelo Worker de entrega já existente, com assinatura e política
  de destino canônicas, configurado separadamente no mesmo escopo;
- alteração de situação no Bling, apenas para resultados finais autorizado/rejeitado.

O retorno oficial usa `PATCH /pedidos/vendas/{idPedidoVenda}/situacoes/{idSituacao}`
e exige HTTP 204. Os IDs são configuração da instalação, nunca um significado
comercial presumido. Antes da escrita, consulta a situação atual: se já corresponde
à desejada, conclui; se diverge da situação original por mudança interveniente,
encaminha a falha para revisão. Timeout após escrita é resolvido pela consulta antes
da próxima tentativa. A API do provedor não oferece neste contrato um CAS/ETag;
a checagem não elimina uma mudança externa concorrente entre GET e PATCH.

O retorno de situação não importa XML ou protocolo para um cadastro de NF-e no
Bling. Protocolo/referência permanecem na consulta NFCore e no webhook assinado.
Eventos de mudança apenas de `situacao` não modificam a identidade fiscal do pedido.
Exclusão do pedido não cancela automaticamente uma nota autorizada.

## Configuração posterior

Nenhum segredo ou certificado real acompanha o código. Sem configuração Bling, a
API permanece com seu comportamento anterior. Configuração parcial do ingresso é
rejeitada. A instalação precisa de um binding canônico no namespace `bling`.

| Variável | Uso |
| --- | --- |
| `NFCORE_BLING_CLIENT_SECRET` | Segredo da aplicação Bling para autenticar eventos na API |
| `NFCORE_BLING_COMPANY_ID` | Identificador opaco exato da empresa Bling |
| `NFCORE_BLING_TENANT_ID` / `NFCORE_BLING_UNIT_ID` | Identidades externas do binding, não IDs fiscais presumidos |
| `NFCORE_BLING_ENVIRONMENT` | `homologation` no Worker desta candidata |
| `NFCORE_WORKER_CONNECTOR` | `bling`, em instância do Worker dedicada ao escopo |
| `NFCORE_BLING_ACCESS_TOKEN_FILE` | Arquivo montado com access token OAuth; relido por requisição para rotação |
| `NFCORE_BLING_AUTHORIZED_STATUS_ID` | Situação Bling escolhida para autorização fiscal |
| `NFCORE_BLING_REJECTED_STATUS_ID` | Situação Bling escolhida para rejeição fiscal; distinta da anterior |
| `NFCORE_A1_VAULT_DIR` / `NFCORE_A1_VAULT_KEY_BASE64` | Cofre A1 existente; cadastro do certificado segue sua autoridade |

Sem cofre configurado, o Worker não reivindica jobs de emissão. Sem ambos os IDs de
situação, não reivindica jobs de retorno. São dependências provisionáveis, não
implementações simuladas. Token OAuth inválido não é aceito como autorização.
O modo Bling e o modo de entrega GSM não são selecionados na mesma instância:
workers separados compartilham a outbox e reivindicam apenas suas operações.

O container Worker instala as dependências Web usadas pela composição fiscal
canônica. Nenhuma migration nova ou fila paralela foi introduzida.

## Operação interna

`PYTHONPATH=src python scripts/admin/bling_order.py --help` mostra os comandos.
`status`, `select-snapshot` e `approve-prepared` não exigem token OAuth nem A1;
exigem apenas acesso administrativo ao banco, configuração do escopo e dados
canônicos persistidos. `reconcile` utiliza a composição de integração configurada.

```bash
PYTHONPATH=src python scripts/admin/bling_order.py status 9001
PYTHONPATH=src python scripts/admin/bling_order.py select-snapshot 9001 \
  --snapshot-sha256 HASH_REVISADO --actor-id OPERADOR
PYTHONPATH=src python scripts/admin/bling_order.py approve-prepared 9001 \
  --snapshot-sha256 HASH_REVISADO --document-id DOCUMENTO_PREPARADO --actor-id OPERADOR
PYTHONPATH=src python scripts/admin/bling_order.py retry-event ID_DA_INBOX \
  --request-id CORRECAO_001 --actor-id OPERADOR
PYTHONPATH=src python scripts/admin/bling_order.py reconcile 9001
```

Seleção de novo snapshot só ocorre antes de vincular um documento. O retry de
captação é idempotente pelo request-id e preserva a tentativa anterior na DLQ.
IDs de operador são evidência do comando administrativo, não substituem IAM;
esses comandos não são expostos como rotas públicas.

## Contrato oficial consultado

- https://developer.bling.com.br/webhooks
- https://developer.bling.com.br/referencia
- https://developer.bling.com.br/build/assets/openapi-CR5QY_N1.json
- SHA-256 do OpenAPI consultado em 09/11/2026:
  `acadd51a045644fd8f87577f3f89cfdfaef9449c8372d93b78173f35536486bb`.

## Aceite e trabalho restante

Testes usam banco, inbox/outbox, Worker, autenticação e lifecycle reais locais;
transportes externos e preparação assinada são sintéticos exclusivamente nos testes.
Cenários: replay, conflito, segregação, pedido incompleto, alteração de snapshot,
exclusão fora de ordem, timeout após autorização/escrita, retomada, resultado final,
retorno recusado, reprocessamento auditável e ausência de configuração externa.

O aceite original de `agentes.md` permanece aberto: faltam a transformação completa
do pedido em documento fiscal preparado e a jornada de revisão na interface. Não
são dependências externas. O CLI e a vinculação a documento preparado não devem ser
anunciados como emissão automática do pedido. CI/Docker/PostgreSQL da candidata
precisam de evidência no SHA publicado. Homologação com Bling/SEFAZ, credenciais reais
e deploy permanecem separados. Não iniciar Tiny nem promover este bloco incompleto.

### Evidência da candidata

PR de construção: https://github.com/faabio3131/nf-core-v001/pull/403 (Draft).
A regressão local executada durante esta entrega teve **3140 PASS / 477 SKIP**;
os skips não são contabilizados como certificação. Depois foi acrescentado teste
de aprovação concorrente e a matriz Bling foi parametrizada para PostgreSQL com
schema descartável exclusivo. Essa variante usa o banco provisionado pela CI;
a máquina local não possui PostgreSQL/Docker. Ruff e Mypy strict passaram.
A CI no HEAD da PR é a autoridade para PostgreSQL, imagem e checks remotos.
