# Bling — pedido revisado até NF-e preparada e retorno ao ERP

Estado: **IMPLEMENTED_CANDIDATE / bloco original EM EXECUÇÃO / NOT_DEPLOYED**.

## Implementação executável

`POST /webhooks/bling` autentica o corpo exato com HMAC SHA-256, valida empresa,
versão v1 e evento `order.created`, `order.updated` ou `order.deleted`. Confirma 202
somente após a transação que grava inbox e job. Duplicatas não criam novos jobs;
mesmo evento com conteúdo diferente recebe 409. Corpo máximo: 1 MiB.

O Worker existente, no modo `NFCORE_WORKER_CONNECTOR=bling`, resolve novamente o
vínculo exato a cada despacho. Consulta o pedido por OAuth no host fixo oficial,
confirma a identidade da empresa OAuth em `/empresas/me/dados-basicos`,
preserva os valores decimais e arquiva o snapshot. Essa confirmação é refeita
quando o hash do token muda; token de outra empresa não acessa pedidos nem escreve
situações. A inicialização local não exige comunicação com o Bling. Pedidos incompletos ficam em
revisão. A normalização consultiva nunca determina impostos nem produz XML.

O operador revisa o snapshot e os dados fiscais do destinatário. A ação `prepare`
resolve os perfis versionados do emitente e dos produtos, aplica o `TaxRuleEngine`,
reconcilia itens/ajustes/pagamentos, reserva numeração, gera XML modelo 55, assina
com o cofre A1 e valida o XSD oficial e a assinatura. Documento, numeração, arquivo
assinado, vínculo do pedido e job de emissão são gravados na mesma transação.
O handoff `approve-prepared` continua disponível para documentos canônicos existentes. Um documento não pode atender a
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
| `NFCORE_BLING_FISCAL_POLICY_FILE` | Arquivo JSON de política fiscal da instalação |
| `NFCORE_BLING_FISCAL_POLICY_SHA256` | SHA-256 dos bytes exatos da política revisada |
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
PYTHONPATH=src python scripts/admin/bling_order.py retry-status 9001 \
  --request-id RETORNO_001 --actor-id OPERADOR
PYTHONPATH=src python scripts/admin/bling_order.py reconcile 9001
```

Seleção de novo snapshot só ocorre antes de vincular um documento. O retry de
captação é idempotente pelo request-id e preserva a tentativa anterior na DLQ.
O retry-status repete somente o retorno ao ERP, mantendo a emissão final intacta.
`retry-issuance` aceita o mesmo order-id/request-id/actor-id e só agenda o documento
original se o lifecycle canônico ainda for READY_TO_TRANSMIT. Após transmissão,
exige `reconcile`; não produz outro documento nem reenvia uma operação incerta.
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

A preparação nativa está implementada e integrada ao portal/CLI. A certificação
interna exige os testes no HEAD desta entrega, inclusive PostgreSQL e navegador;
resultados anteriores não certificam código novo. Certificado sintético é gerado
apenas nos testes: o código de produto usa exclusivamente o cofre configurado.

### Escopo fiscal executável

Esta candidata prepara vendas de mercadorias NF-e modelo 55 em **homologação**,
usando regras fiscais versionadas por empresa, unidade, NCM, regime e destinatário.
Não usa sugestões do ERP como autoridade; não define alíquotas legais padrão.
Grupos legados: CSOSN 102/103/300/400; ICMS 00/10/40/41/50;
PIS/COFINS 01/02/04/06/07/08/09.

**ICMS-ST e FCP-ST (CST 10):** exigem `st_rate`, `st_mva_rate` e
`st_base_mode` (`net_mva` ou `net_plus_ipi_mva`); `fcp_st_rate` é opcional
somente com ST. O motor calcula a base ST por MVA, subtrai o ICMS próprio do
ICMS-ST e inclui `vST` e `vFCPST` no total da NF-e e nas parcelas conferidas.
A base/percentual da operação devem ser aprovados pela regra fiscal local.
Outras modalidades de base (pauta, tabelado, redução), CSTs de ST e regimes
específicos não devem usar indevidamente esse caminho: exigem implementação
especializada e permanecem bloqueados.

**FCP próprio e DIFAL de destino:** `fcp_rate` exige ICMS 00/10;
o grupo ICMS10 informa também `vBCFCP`. Para destinatário final não
contribuinte em outra UF, ICMS 00 exige `difal_destination_rate`,
`difal_interstate_rate` (4, 7 ou 12) e `difal_destination_share`
(100 na política desta candidata); `fcp_destination_rate` permite
o FCP específico do destino. O XML informa ICMSUFDest, e os totais
`vFCPUFDest` e `vICMSUFDest` são calculados sem duplicar `vNF`.
Aplicações de DIFAL em outros CSTs/regimes, bases duplas ou benefícios
precisam de política e caminho próprio.

**IPI:** além de saída tributada CST 50 por alíquota (`ipi_rate`,
`ipi_enquiry_code` e `ipi_calculation_mode: net_icms_excluded`),
o CST 50 aceita valor fixo por unidade tributável (`ipi_unit_amount`,
`ipi_cst: 50` e `ipi_calculation_mode: per_taxable_unit`) com quantidade
tributável exata. CSTs de saída 51/52/53/54/55 geram IPINT, exigindo
`ipi_cst`, `ipi_enquiry_code` e `ipi_calculation_mode: non_taxed`.
O IPI devido integra o `vNF` e a conciliação de pedido/pagamento.
Cálculos mistos, entradas ou outras bases não são inferidos.

**RTC (IBS/CBS de 2026):** caminho inicialmente restrito a tributação
plena CST IBS/CBS `000` com `ibs_cbs_classification_code` de seis dígitos,
`ibs_cbs_classification_table_version`, e as três alíquotas explícitas
`rtc_uf_rate`, `rtc_municipal_rate`, `rtc_cbs_rate`. Exige
`rtc_base_mode: net` ou `net_less_icms_pis_cofins` e
`rtc_financial_mode: informational_2026`. Calcula grupos `IBSCBS`
por item, `IBSCBSTot` e `vNFTot`; preserva conciliação comercial com
o `vNF` legado, sem presumir recolhimento. Só aceita data de emissão
em 2026. A versão informada da tabela é proveniência de configuração,
**não** uma homologação automática da classificação legal.
Regimes monofásicos, redução, diferimento, suspensão, créditos, IS,
desonerações e demais CSTs/combinações continuam exigindo sua própria
modelagem e validação normativa. O sistema falha fechado nesses caminhos.

Em todos os grupos, o enquadramento, a base, a vigência, as alíquotas e
suas fontes normativas são responsabilidade da política aprovada para
a empresa e operação, nunca do pedido Bling. O código não prova
homologação SEFAZ, legalidade universal, produção ativada ou aptidão
para todos os produtos. Testes sintéticos de assinatura/XSD não
substituem homologação externa com certificado e credenciais reais.

Para um produto cuja unidade tributável difere da comercial, a vinculação de
produto da política pode incluir `taxable_factor` como decimal positivo em texto.
O fator é a quantidade tributável por unidade comercial; por exemplo, `"2"`
converte 3 unidades comerciais em 6 unidades tributáveis. O fator é versionado e
arquivado com a política, e quantidade e valor tributáveis são fixados no snapshot.
Precisão incompatível ou valores que não reconciliem bloqueiam a preparação.

Para cartões integrados, `card_integration_type: 1` na política exige revisão de
CNPJ da instituição, código de bandeira e autorização por parcela do pedido. Os
dados revisados são associados ao snapshot fiscal e ao XML; o formulário não
solicita número do cartão ou código de segurança. Para cartões não integrados, use o
tipo 2 sem dados de integração. O operador deve conferir os dados recebidos do
processador; a preparação não comprova por si só a liquidação do pagamento.

### Configuração fiscal reproduzível

O exemplo `contracts/integrations/bling-fiscal-policy.example.json` documenta as
chaves exatas. Substituir identificadores sintéticos por perfis existentes e regras
revisadas, fixar suas versões e calcular `sha256sum ARQUIVO`. O namespace do binding
e dos perfis deve ser `bling`. `products` mapeia código do ERP para ID/versão do
perfil fiscal; `payment_methods` mapeia ID da forma de pagamento do ERP para método
canônico. `sale_options` explicita natureza, presença e modalidade de frete;
venda remota exige indicador de intermediador, e marketplace exige CNPJ e cadastro.

Cada política é arquivada integralmente. Reutilizar ID/versão com outro conteúdo é
conflito; revisão exige nova versão e novo hash. O formulário envia o hash que foi
apresentado na consulta: troca da política durante revisão bloqueia a preparação.
Não há fallback de regra, perfil, destinatário ou assinatura.

```bash
PYTHONPATH=src python scripts/admin/bling_order.py prepare 9001 \
  --review-file REVISAO.json --actor-id OPERADOR
```

`REVISAO.json` usa as mesmas quatro chaves da API abaixo. Repetir a preparação com
os mesmos fatos recupera o documento e não consome outra numeração. Mudança de
snapshot durante a transação desfaz preparação e reserva; após transmissão incerta,
a recuperação continua por reconciliação do documento original.

### Evidência da candidata

PR de construção: https://github.com/faabio3131/nf-core-v001/pull/403.
`tests/test_bling_canonical.py` cobre mapeamento, arredondamento, regras, assinatura
A1 sintética, XSD oficial, replay, rollback e jornada sessão/CSRF → preparação →
Worker fiscal → retorno oficial, com transportes externos substituídos nos testes.
As transações são parametrizadas em SQLite e PostgreSQL (banco isolado da CI).
`tests/e2e/bling_review.spec.js` cobre revisão e envio dos fatos fiscais no navegador.

### Revisão autenticada no portal

Em **Integrações → Revisão de pedidos Bling**, informe o identificador interno do
pedido. A tela consulta os snapshots imutáveis selecionado e atualizado, mostra
seus dados como texto e permite selecionar a atualização antes de qualquer vínculo.
A preparação nativa exige destinatário, enquadramento IE/consumidor final explícitos
e confirmação de revisão. O formulário aparece quando a política está configurada.
O backend deriva empresa, unidade e ator da instalação e da sessão; exige
`integration.manage` para consulta e também `document.issue` e CSRF para mutações.
Nenhuma credencial OAuth ou certificado é necessário para consultar e revisar.

- `GET /v1/portal/integrations/bling/orders/{id}` — snapshots e estado, `no-store`.
- `POST .../{id}/select-snapshot` — corpo exclusivo `snapshot_sha256`.
- `POST .../{id}/prepare` — `snapshot_sha256`, `policy_sha256`, `issued_at`, `recipient`.
- `POST .../{id}/approve-prepared` — `snapshot_sha256` e `document_id`.

Atualização concorrente retorna conflito; a tela deve consultar novamente. A
aprovação repetida do mesmo vínculo é idempotente. Dados de outra organização ou
unidade não são expostos. A tela utiliza o preparador canônico real, sem receber
segredos ou permitir que o navegador determine tenant, unidade, regras ou alíquotas.
