# Extrema/MG — Reconciliação de documentos WebISS RTC (11/11/2026)

**Estado:** `OFFICIAL_PUBLIC_LINKS_VERIFIED / UPLOADED_BYTES_AUDITED / SCHEMA_BUNDLE_INCOMPLETE / NOT_INTERNALLY_CERTIFIED / NOT_EXTERNALLY_HOMOLOGATED`. Esta entrega é **somente documental**, baseada em arquivos compartilhados pelo proprietário. Nenhuma transmissão fiscal, certificado real, cadastro CeC, merge ou deploy.

## Portal municipal e enlaces oficiais

Fonte de Extrema: https://extremamg.webiss.com.br/externo/manual/visualizar — seção `Nota Fiscal de Serviços Eletrônica`, `Documentação Técnica — Adequações relativas ao IBS e à CBS`:

- XSD: https://drive.google.com/file/d/14yTC_mKUsBEYfmiv35JyYC_FP_6z2U-T/view
- Manual: https://drive.google.com/file/d/1s97wqsgksPKtIL4tTZjKF_zXzO-JAAYX/view
- Guia: https://drive.google.com/file/d/1VxSQDysYbJ7YM-4_6t8fsKt8B-x9DX7U/view
- Exemplos XML: https://drive.google.com/drive/mobile/folders/1sJeZC_iB5GPz1ox4q9BEd9zppbG3olls
- **WSDL publicado para homologação:** https://homologacao.webiss.com.br/ws/nfse.wsdl
- Endpoint web de homologação: https://homologacao.webiss.com.br/

**A página municipal publica essas URLs**, provando a associação oficial dos links a Extrema. Os bytes foram obtidos por upload do usuário, **não por download binário independente do link**. O WSDL de homologação é prova do documento de descoberta, **não** prova de `soap:address` para POST; não inventar `/ws/nfse.asmx` como destino de teste. A mesma página exige criação de usuário, CeC, aprovação e contato com `callcenter2@webiss.com.br` para uso operacional. Não criar CeC usando CNPJ de terceiro sem representação autorizada.

## Manifesto SHA-256 dos uploads

| Arquivo | SHA-256 |
|---|---|
| `nfse_v2_02-IBSCBS.xsd` | `4caeadd9b4993b7741d7a83aa80601ac5743524d5af7bdd14f862fed053c7003` |
| `Guia Técnico Rápido.pdf` | `f2c5f3497a5ae449dd226ad0a899fe8d78ffde2c896e3ab1aa62cdda5531823d` |
| `Manual de Integração ... V5.0.pdf` | `6b772a4d43ad61dcec24f01f5c1a2aecb55c98cf1d9549769a98148d6da5e04a` |
| ZIP dos sete XMLs | `76d0f6485c60b3edc930c93ba5d8c66e4137930c9a544ffd8eb10a9d4c80a84e` |
| `SubstituirNfseEnvio.xml` separado | `e95c317961a6bdc3a01cd816b766ba634b7e626889eec863f3de4d4acb8c1066` |

O SHA do XSD coincide com o previamente documentado pela PR #423 como arquivo de referência **Formiga/MG**, evidenciando base compartilhada pelo fornecedor. Agora existe link municipal direto publicado para o arquivo de nome idêntico. Não substituir a política de município por confiança genérica no XSD de outro município.

**Versão do manual:** filename `V5.0`, mas a primeira página diz **"Versão do Manual 5.2"**; histórico registra 5.1 (retenção PIS/COFINS e NIF do tomador) e 5.2 (endereço de obra). Não ignorar esses campos por causa do nome do PDF.

## Estrutura XSD inspecionada (sem alegar validação)

- Namespace `http://www.abrasf.org.br/nfse.xsd`, layout 2.02 + RTC/IBSCBS.
- Dez elementos de envio e dez de resposta: gerar; lote assíncrono; lote síncrono; cancelar; substituir; consultar lote; consultar RPS; consultar serviços prestados; tomados; faixa.
- Ordem `TCRTCInfoIBSCBS`: `finNFSe`, `indFinal?`, `cIndOp`, `tpOper?`, `gRefNFSe?`, `tpEnteGov?`, `indDest`, `dest?`, `imovel?`, `valores`. Em `dest`: escolha exclusiva `CNPJ/CPF/NIF/cNaoNIF` **primeiro**, depois `xNome`, `end?`, `fone?`, `email?`. Cobrir E160 sem reordenar assinatura.
- `tcInfNfse/ChaveAcesso` obrigatória no schema de retorno; `CodigoNbs`, `InscricaoEstadual`, `TCInfoPisCofins`, `NifTomador` presentes no pacote/manual.
- O XSD **importa** `xmldsig-core-schema20020212.xsd` por `http://www.w3.org/2000/09/xmldsig#`. Este arquivo não veio nos uploads; tentativa de `lxml.XMLSchema` falhou ao resolver `dsig:Signature`. **NÃO houve validação completa dos exemplos** e o arquivo SHA individual **não** é o `SchemaSet.package_sha256` do par. Não preencher `PINNED_WEBISS_MG_2026_SCHEMA_DIGESTS['3125101']` sem import original, hash do pacote e suíte golden revisada.

## Exemplos recebidos: não constituem fixtures golden

- ZIP contém `GerarNfseEnvio`, `CancelarNfseEnvio`, `EnviarLoteRpsSincronoEnvio`, `ConsultarNfseServicoPrestadoEnvio`, `ConsultarNfseFaixaEnvio`, `ConsultarNfseServicoTomadoEnvio` e `ConsultarNfseRpsEnvio`; o `SubstituirNfseEnvio` veio separado.
- Os oito XMLs são sintaticamente parseáveis, mas têm de 5 a 69 tags folha vazias. **Não** são mensagens prontas para envio nem prova de assinatura válida.
- O XML de lote síncrono ilustrativo contém só **uma** assinatura e `Reference URI=\"id-rps\"` sem `#`; o manual §3.2.3 orienta assinar RPS individualmente e lote depois. Não usar como teste positivo criptográfico.
- Substituição ilustrativa contém duas assinaturas, valores `http://tempuri.org`, campos vazios e certificado histórico embutido. **Não** commitar esse arquivo ou dados de identidade; construir fixtures sintéticas novas.
- Manual §3.2.2 separa A1/A3 de **assinatura** (emitente/matriz) do certificado TLS de **transmissão** (responsável, CNPJ potencialmente diverso). O adaptador atual é deliberadamente mais restritivo ao usar A1 vinculado ao emissor para ambos; transmissão delegada exige política formal de representação, nunca relaxamento automático de escopo.

## Deltas de construção na autoridade canônica PR #423

O gateway `src/kordena_fiscal/gateway/mg_webiss_soap.py` da #423 cobre parcialmente cinco operações (gerar, lote não-síncrono, cancelar, consultar lote, consultar prestados), mas não expõe contratualmente lote síncrono, substituição, consulta por RPS, consulta de serviços tomados e por faixa. Completar **no adaptador canônico** sem duplicar o transporte; PR #429 foi encerrada por redundância. Além disso faltam builders ABRASF 2.02/RTC 5.2, assinatura real, retorno correlacionado, persistência e E2E API/Web, no contexto das provas do cronograma MG.

Próximos gates: obter `xmldsig-core-schema20020212.xsd`; capturar WSDL e `soap:address` sem POST; montar pacote offline hash-pinned; validar mensagens totalmente preenchidas e assinadas; implementar cinco operações faltantes na #423 com vínculo/correlação/compensação e testes; executar Ruff, Mypy, Pytest, banco, frontend e CI no mesmo HEAD; aprovar homologação externa separadamente.

**Sem mudanças** em AGENTS.md, EGM, branches do Bling, workers, Contabo, `main` ou `production`; esta PR documental não certifica Extrema.
