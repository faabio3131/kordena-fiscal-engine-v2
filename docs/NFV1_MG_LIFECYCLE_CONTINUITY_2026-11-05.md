# NFCore MG — ciclo operacional interno

Data: 05/11/2026. Branch: feat/nfcore-mg-lifecycle-20261105.
Base: PR #361, HEAD 7739fd1587f2cb59f07032523b282c218da6a210.
main reconfirmada: 3f56084041fc9cd441af9a61dcc9532ba6090a85.
Autorização do proprietário: continuar construção para teste da contabilidade.
Sem nova autorização para deploy/migration/credencial/emissão real nesta entrega.

## CURRENT → TARGET e escopo congelado

CURRENT: transporte autorização MG com schema NFe e assinatura próprios; operações
query/cancel/inutilize ainda fixas SP. CI #1691 em execução ao iniciar.
TARGET: reutilizar implementação das três operações com configuração interna MG55,
validação XSD offline, correlação estrita de resposta, assinatura de eventos compatível,
sem registrar bindings ou conceder prontidão por catálogo.

Impacto: gateway de operações, assinador canônico (perfil explícito de evento),
XmlSchemaValidator (entrada raw reutilizando a mesma compilação), recursos oficiais
e testes. Sem segunda API/auth/tenant/banco/regras tributárias. Wrapper SP preservado.

## Fontes e composição auditável

Os pacotes 010g/f/e são atualizações parciais, não pacotes completos de todos serviços.
Foi capturado PL009q para raízes de envelope/status/inutilização/recibo, PL010d
para consulta/inutilização atualizadas e envelope de eventos, e PL010g para NFe.
Snapshot interno composto: MG_LIFECYCLE_20261105. Cada arquivo preserva bytes,
hash, membro do ZIP, URL e hash do arquivo de origem. Não é versão oficial unificada
nem prova de vigência por ambiente: é configuração de compatibilidade para testes.
Nenhum schema de eventos RTC foi misturado com evento genérico cancelamento.

## Aceite

Consultas/cancelamentos conferem UF31/modelo55/ambiente antes do Vault; inutilização
exige resolvedor confiável de unidade e modelo55 antes de certificado.
XML de entrada validado no schema fixado; assinatura por perfil explícito.
Resposta oficial deve correlacionar chave/evento/faixa/emitente antes de aceitar.
Redirect, SOAP Fault e escopo divergente falham fechados; sem replay de mutação.
Testes com A1 e documentos sintéticos; nenhum envio oficial ou certificado real.

## Gates e pendências

Ruff, Mypy dirigido, testes de gateways/XML/operações, regressão, wheel e CI no HEAD.
Validar consulta, cancelamento, inutilização e isolamento de escopo com respostas locais.
Faltam ainda golden case de NF-e completa, binding/runtime governado por unidade,
CSC/QR NFC-e, NFS-e BH, frontend operacional e certificação de carga/CI.
Homologação com contribuinte e produção permanecem estados separados.

## Resultados de construção e causas raiz

- Snapshot oficial composto: 27 recursos exatos com manifesto SHA-256
  41a818efb4e6ba37eeead3c271957b02ac995dee14425b7809e9591c641ac718.
- Compilam offline raízes de autorização enviNFe, consulta, cancelamento genérico,
  inutilização, status e recibo. Status/recibo ainda não são operações completas no runtime.
- XmlSchemaValidator ganhou validate_document; a entrada antiga por NfceXmlPayload
  continua validando identidade antes de delegar. Nenhuma segunda autoridade XSD.
- Entrada de consulta anterior usava CONS_SIT; XSD exige CONSULTAR. Corrigido.
- SOAPAction usava nfeDadosMsg; transporte usa agora o método da tabela de serviço.
  Validação WSDL/mTLS com autorizador ainda é pendência externa/de contrato.
- Perfil explícito RSA-SHA1 de evento MG reutiliza signer; restringe tpAmb=2.
- O teste criptográfico após montagem do SOAP revelou digest alterado por namespaces
  herdados. Wrappers usam namespaces default, sem inserir prefixes no contexto assinado.
  Testes verificam digest e SignatureValue na carga final, em autorização/cancelamento/
  inutilização, não apenas antes de construir SOAP.
- Teste NF-e sintética completa passou validação XSD de enviNFe assinada, resposta
  local correlacionada, geração de nfeProc e validação XSD oficial de procNFe.
  É golden estrutural de transporte; não aprovação contábil, tributária ou SEFAZ.

## Isolamento e negativas

UF/modelo/ambiente divergentes falham antes do Vault; inexistência de A1 é erro
fiscal explícito. Respostas de cancelamento correlacionam órgão/chave/tipo/sequência;
inutilização confere UF/ano/CNPJ/modelo/série/faixa. SOAP Fault, destinos desconhecidos,
redirecionamentos, schema/manifesto inválido e XML excessivo são recusados.
Sem retry automático de mutação e nenhuma transmissão real na suíte.

## Pendências materiais preservadas

Este bloco NÃO encerra NAT-UF-MG e não disponibiliza por si só o piloto Web.
Ainda é necessária composição por provider binding aprovado no runtime, conexão
à preparação Web/API, jornada persistente/autorização/arquivo/recuperação, matriz
fiscal normativa, CSC/QR NFC-e e DPS/ISS NFS-e BH, carga e CI no HEAD.
A inutilização canônica ainda deriva ano do relógio do gateway: recuperação atravessando
o ano fiscal requer evoluir o contrato de ano/identidade sem alterar silenciosamente
idempotência histórica. Registrar como gap interno, não homologação externa.
A parametrização vigente do snapshot composto deve ser revisada no dossiê T01;
conter schemas oficiais não comprova sua ativação em determinado contribuinte/tpAmb.

## Evidência anterior reconfirmada

PR #361: CI #1691 SUCCESS e Governança #1122 SUCCESS no HEAD 7739fd1.
Ela permanece Draft: as correções de SOAP e operações deste incremento precisam
ser consideradas antes de qualquer integração para não promover um fluxo conhecido
como incompleto. Nenhum merge ou deploy foi feito nesta continuidade.

## Gates finais locais

- 265 PASS em 97,55s: gateways, XML, operações, control_plane e A1 sintético.
- Ruff global PASS; Mypy dirigido de cinco módulos PASS após ajuste localizado
  da tipagem lxml-stubs para namespace default None (suportado pelo lxml real e
  indispensável para preservar canonicalização; padrão já usado no repositório).
- Plano de 59 tarefas e validador BUILD PASS; não promovem estado funcional.
- Wheel construída; conferir hashes dos 27 recursos no índice Git e na distribuição.
- Diff check de código/docs PASS; recursos oficiais preservam whitespace original.
- SHA, PR e CI remotos serão registrados na PR após publicação.
