# Extrema/MG — Reconciliação de documentos WebISS RTC (11/11/2026)

**Estado:** `OFFICIAL_PUBLIC_LINKS_VERIFIED / UPLOADED_BYTES_AUDITED / SCHEMA_COMPILED_OFFLINE_NOT_RUNTIME_PINNED / NOT_INTERNALLY_CERTIFIED / NOT_EXTERNALLY_HOMOLOGATED`. Esta entrega é **somente documental**, baseada em arquivos compartilhados pelo proprietário. Nenhuma transmissão fiscal, certificado real, cadastro CeC, merge ou deploy.

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
- O XSD **importa** `xmldsig-core-schema20020212.xsd` por `http://www.w3.org/2000/09/xmldsig#`. Esse arquivo **foi recuperado em seguida** no ZIP `Material de Apoio WebService - Versão 5.0.zip`, vinculado pelo portal oficial. A compilação local do schema RTC+XMLDSig agora **PASSOU** com lxml 6.1.1, sem acesso à rede. O par ainda **não** está embutido/pinado no runtime da PR #423; não preencher `PINNED_WEBISS_MG_2026_SCHEMA_DIGESTS['3125101']` sem governança de distribuição dos bytes, SHA de pacote e golden tests revisados. Os exemplos foram validados contra o XSD completo e os **oito falharam por placeholders obrigatórios vazios**, portanto não são fixtures positivas.

## Exemplos recebidos: não constituem fixtures golden

- ZIP contém `GerarNfseEnvio`, `CancelarNfseEnvio`, `EnviarLoteRpsSincronoEnvio`, `ConsultarNfseServicoPrestadoEnvio`, `ConsultarNfseFaixaEnvio`, `ConsultarNfseServicoTomadoEnvio` e `ConsultarNfseRpsEnvio`; o `SubstituirNfseEnvio` veio separado.
- Os oito XMLs são sintaticamente parseáveis, mas têm de 5 a 69 tags folha vazias. **Não** são mensagens prontas para envio nem prova de assinatura válida.
- O XML de lote síncrono ilustrativo contém só **uma** assinatura e `Reference URI=\"id-rps\"` sem `#`; o manual §3.2.3 orienta assinar RPS individualmente e lote depois. Não usar como teste positivo criptográfico.
- Substituição ilustrativa contém duas assinaturas, valores `http://tempuri.org`, campos vazios e certificado histórico embutido. **Não** commitar esse arquivo ou dados de identidade; construir fixtures sintéticas novas.
- Manual §3.2.2 separa A1/A3 de **assinatura** (emitente/matriz) do certificado TLS de **transmissão** (responsável, CNPJ potencialmente diverso). O adaptador atual é deliberadamente mais restritivo ao usar A1 vinculado ao emissor para ambos; transmissão delegada exige política formal de representação, nunca relaxamento automático de escopo.

## Deltas de construção na autoridade canônica PR #423

O gateway `src/kordena_fiscal/gateway/mg_webiss_soap.py` da #423 cobre parcialmente cinco operações (gerar, lote não-síncrono, cancelar, consultar lote, consultar prestados), mas não expõe contratualmente lote síncrono, substituição, consulta por RPS, consulta de serviços tomados e por faixa. Completar **no adaptador canônico** sem duplicar o transporte; PR #429 foi encerrada por redundância. Além disso faltam builders ABRASF 2.02/RTC 5.2, assinatura real, retorno correlacionado, persistência e E2E API/Web, no contexto das provas do cronograma MG.

Próximos gates: formalizar em artefato aprovado o pacote compilado e verificar licenciamento/proveniência; capturar WSDL vivo e `soap:address` sem POST; montar pacote offline hash-pinned; validar mensagens totalmente preenchidas e assinadas; implementar cinco operações faltantes na #423 com vínculo/correlação/compensação e testes; executar Ruff, Mypy, Pytest, banco, frontend e CI no mesmo HEAD; aprovar homologação externa separadamente.

**Sem mudanças** em AGENTS.md, EGM, branches do Bling, workers, Contabo, `main` ou `production`; esta PR documental não certifica Extrema.

## Atualização de evidências — pacote WebService de 2012 recuperado diretamente do link público (11/11/2026)

- Link do arquivo exibido pelo usuário: `https://drive.google.com/file/d/0Bw7RBBzWF6breGxiS1c4ZVhwS2M/view?resourcekey=0-6QJapRF-I7HWOYG4I16DOA`.
- ZIP `Material de Apoio WebService - Versão 5.0.zip`: **1.004.364 bytes**, SHA-256 `de34ca49c34866a326b81f435c57364182c47e9b3dff908a98531a298b136269`. Contém dois ZIPs internos (schemas e WSDL), dois PDFs ABRASF **novembro/2012** e tabela de erros `.xlsx`.
- `schema_xml_nfse_v2-02.zip`: SHA-256 `be07167223779855fba935a3eada78ca40ba4b6d7ef5c2a65dbcbe5fe29228f6`. Contém `nfse v2 02.xsd` SHA `3be765d35f6b3ee0d42bc02f72a0f5f6e12544756fa78de0e9559854081a9d25` (**legado, não usar como substituto do XSD RTC**) e `xmldsig-core-schema20020212.xsd` SHA `13f29857c337bef574e59ea1023caaa9b407bcae0dea013c5c295385688708d4`.
- **Verificação real**: `lxml.XMLSchema` compilou `nfse_v2_02-IBSCBS.xsd` (SHA `4caeadd9...`) junto com o XMLDSig desse pacote, com `resolve_entities=False`, `no_network=True`, e compilou separadamente o legado 2.02. Sem usar XSD da rede.
- **Manifesto `SchemaSet.package_sha256`** seguindo o algoritmo do NFCore (sorted `resource.name`, NUL, SHA de arquivo, newline) para **exatamente** `nfse_v2_02-IBSCBS.xsd` e `xmldsig-core-schema20020212.xsd`: `8e0f2a9174cbfafa5a601a7003c5f3d4408ceadd01de1e87b9be12c09cc762ee`. É hash técnico do par verificado localmente, **não aprovação para habilitar transmissão**.
- **8/8 modelos XML falharam a validação XSD** por campos obrigatórios vazios: os sete XMLs do ZIP de exemplos anteriormente enviado e `SubstituirNfseEnvio.xml` separado. Isso é esperado de templates em branco; nenhum golden positivo de emissão, assinatura e cancelamento foi homologado.
- `wsdl_nfse_v2 02.zip` SHA `46f361f90aebb0dd86c6811d2eff72a7abd38803ed488d80b07eff30e53c86e3`, inclui `nfse.wsdl` SHA `ef24465f8ef05d466f6f2e6d226b7fe937e90bb727e4c4f372f762a389e25769`. **CRÍTICO:** `soap:address location="http://ws.pbh.gov.br"`. Trata-se de arquivo genérico/legado referente a Belo Horizonte, **nunca** fonte para o endpoint Extrema. As dez operações têm ações SOAP compatíveis com as páginas ASMX públicas, mas a `soap:address` municipal de homologação deve ser conferida no WSDL vivo divulgado pela prefeitura; não reutilizar esse endereço.
- Planilha `Relacao_de_Erros_e_Alertas.xls.xlsx` SHA `a8c0ce4a93656f3207d41cc6ae2e800f291383b9c67269646fcbc11cc30f5857`, aba `Erros e Alertas`: código **E160** = "Arquivo em desacordo com o XML Schema", mensagem **genérica** ABRASF 2.02. A evidência de posição de `dest` no RTC é restrição de ordenação do XSD atual, não uma redefinição isolada desse código.
- Links públicos `https://homologacao.webiss.com.br/ws/nfse.asmx?op=GerarNfse` expõem exemplo SOAP 1.1 do próprio domínio de homologação, **sem execução POST**. Ainda resta inspecionar autoridade do WSDL vivo e aprovar composição fiscal/credenciamento.

Nenhuma alteração de runtime, ponte do cofre, certificado, dados de contribuinte ou ativação do provedor foi feita. A PR #432 continua documental; certificação interna completa de Extrema **NÃO** está fechada.
