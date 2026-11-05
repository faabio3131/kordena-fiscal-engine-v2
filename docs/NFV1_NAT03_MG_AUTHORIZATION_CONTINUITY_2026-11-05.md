# NAT-03/04 — continuidade e autorização NF-e MG

Data: 05/11/2026. Escopo: construção interna parcial; não homologação oficial.

## CURRENT confirmado antes da alteração

Repositório atual: faabio3131/nf-core-v001 (renomeado do histórico).
main: 3f56084041fc9cd441af9a61dcc9532ba6090a85.
PR #356 integrada; #359 integrada; #358 aberta para production, sem execução nesta entrega.
PR #360 Draft: feedf8b41085914b831c9585bec1b34675742008.
Governança #1120 SUCCESS; CI #1689 ainda em execução na consulta inicial.
A base desta branch é exatamente o HEAD da #360; preservar sua revisão separada.

## CURRENT → TARGET e impacto congelado

CURRENT: catálogo MG 55/65 com dez operações; transporte de autorização fixo SP.
TARGET deste incremento: mesma implementação SOAP de autorização com alvo MG NF-e 55,
selecionado exclusivamente por configuração de engenharia, com validação estrita
da identidade fiscal. Não cria novo router, persistência, API, auth ou regra tributária.

Arquivo comum evoluído: gateway/nfe_sp_homologation.py. O nome histórico é preservado
para compatibilidade de imports; SefazSpHomologationGateway permanece wrapper SP.
SefazHomologationAuthorizationGateway implementa o transporte compartilhado.
Fonte de endpoint MG: mg_official_homologation_catalog.py da #360.
ProviderRegistry e DurableProviderBindingResolver continuam autoridades da aplicação.
A configuração deste adapter não cria nem aprova binding e não altera readiness.

Mapa de impacto: autorização SOAP/mTLS e metadados de provider; wrapper SP,
métodos auxiliares e formato AuthorizationResult preservados. Redirecionamento HTTP
é bloqueado também em SP para impedir mudança de destino de comunicação mTLS.
Sem alteração de DB/migrations, Portal, DNS, credenciais, production ou Contabo.

## Critérios de aceite e controles

- Alvo MG exige chave UF 31/modelo 55, XML único com Id, cUF/mod/tpAmb e CNPJ coerentes.
- Rejeição de escopo antes de consultar Vault; nenhuma seleção implícita de SP.
- Assinatura MG pertence ao Vault: XML previamente assinado é recusado enquanto
  não existir validação criptográfica explícita para esse caminho.
- Callback XSD confiável obrigatório na construção MG e executado sobre XML assinado
  antes do transporte. Deve lançar exceção em schema inválido.
- A1 continua validado por emitente/escopo; SOAP, TLS e respostas reutilizam código atual.
- Resposta deve identificar MG, homologação, chave/protocolo e digest do XML assinado.
- Sem replay automático de mutação fiscal e sem redirecionamento HTTP.
- Endpoint não vem do navegador, tenant, inventário municipal ou URL livre.

## Fontes oficiais reconferidas

- https://portalsped.fazenda.mg.gov.br/spedmg/nfe/webservices/
- https://portalsped.fazenda.mg.gov.br/spedmg/nfce/web-services/

As páginas sustentam os endereços de referência; não constituem XSD/WSDL congelado,
aprovação do contribuinte ou prova de homologação. Fonte não foi artificialmente
marcada com hash de bytes não capturados.

## Evidência e limitações

Testes usam certificado RSA PKCS#12 sintético, namespace SOAP e respostas locais.
O validador XSD é um spy nos testes de transporte: estes testes NÃO certificam
schema oficial. O endpoint HTTPS é exercitado com opener local, sem chamada fiscal.
Asserções incluem assinatura real, protocolo/nfeProc, UF/modelo/ambiente/emitente,
schema rejeitado, resposta inconsistente, redirect e compatibilidade de URL SP.

Gates finais e SHA: registrar no ledger e na PR após execução.
Esta entrega não integra automaticamente à main; merge exige autorização específica.
A PR #358 pode acionar deploy automático em production e não foi mesclada.

## Pendências e próximo bloco

NAT-03/04 e NAT-UF-MG permanecem IMPLEMENTING, nunca INTERNAL_COMPLETE.
Ainda faltam congelar e verificar XSD/WSDL oficiais, compor o validador real com
proveniência, ligar adapter ao registro canônico governado, consulta/cancelamento/
inutilização/status/recibo, NFC-e CSC/QR, NFS-e BH, Web, carga e certificação completa.
Ausência de XSD real é lacuna interna de construção; A1/credenciamento/transmissão
oficial e homologação permanecem dependências externas distintas.

Sequência preservada: MG → RJ → PR → MT → MS. Nenhum município ou UF homologado.

## Incremento posterior na mesma execução — XSD oficial congelado

O download direto com sessão HTTP/cookies do Portal Nacional permitiu obter
PL_010g v1.03 (49.751 bytes), SHA-256 do ZIP original:
b329ecbe7e4c05a41bfbc1527f105defb7047328acfeada7c77e1666da485eaf.
URL: https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=EQhOQMgipXY=

Os cinco XSD do subdiretório NFe foram preservados byte a byte, com manifesto
ancorado por hash no loader. Eventos do ZIP NÃO foram incorporados nem declarados
certificados. .gitattributes evita transformação CRLF/LF dos artefatos.
Package-data inclui os recursos na distribuição Python.

O novo loader offline usa SchemaResource/SchemaSet/XmlSchemaValidator já canônicos.
build_mg_nfe_homologation_gateway compõe o transporte com validação real da NFe
assinada; não exige que o integrador escreva outro validador ou carregue schemas
dinamicamente. A composição foi testada recusando XML sintético incompleto antes
do transporte. Hash alterado do manifesto ou do XSD impede compilação/execução.

Limite de escopo: o pacote capturado é um subconjunto NFe de atualização e não
contém o XSD completo enviNFe, WSDL, regras de negócio/RTC, eventos ou prova de
vigência aplicada por ambiente. O wrapper confere estrutura mínima e documento
único, mas a validação XSD certificada nesta etapa é da NFe individual.
Não declarar validação completa de envelope/UF, golden case autorizado, binding
ativado ou homologação. Os blockers anteriores de ausência absoluta de bytes XSD
foram parcialmente resolvidos; demais operações/esquemas seguem pendentes.

### Causa raiz descoberta na integração de XMLDSig

O XSD oficial xmldsig-core-schema_v1.01.xsd fixa os algoritmos rsa-sha1 e sha1.
O assinador existente produzia RSA-SHA256/SHA256, incompatível com esse contrato.
Foi adicionado NfeSignatureProfile.NFE4_OFFICIAL_RSA_SHA1, selecionado explicitamente
pelo alvo MG NF-e em homologação. Não há algoritmo arbitrário recebido por HTTP
nem alteração de hash do manifesto, dos artefatos, certificado ou TLS.
O default anterior RSA_SHA256 e o assinador de eventos permanecem inalterados.
A compatibilidade do default SP com schemas oficiais é PENDÊNCIA explícita;
não declarar SP homologado ou sua assinatura compatível a partir desta entrega.

Teste novo valida a Signature contra o XSD oficial e verifica criptograficamente
o SignatureValue com RSA/SHA1. O teste também comprova que o default SHA256 não
satisfaz o mesmo XSD, evitando falso positivo. O perfil desconhecido é recusado.
O perfil legado se limita ao contrato de homologação já restrito a tpAmb=2.

### Packaging e integridade

Wheel construída com build isolation padrão: PASS. Tentativa inicial sem isolamento
falhou por setuptools.build_meta ausente no Python local; sem alteração global.
Os hashes dos cinco arquivos oficiais no índice Git e dentro da wheel conferem
exatamente com o manifesto. Whitespace original de XSD foi preservado: diff check
dos artefatos aponta espaços e CRLF do original, não corrigidos para não alterar
evidência. Diff check do código e da documentação deve permanecer verde.

Mypy dirigido dos três módulos modificados PASS; conjunto XML/transporte/A1
intermediário 36 PASS. Regressão ampliada final e CI do novo HEAD registradas na PR.
