# Osasco — engenharia isolada de NFS-e WCF RTC (13/11/2026)

**Status: IMPLEMENTING / NOT CERTIFIED.** PR sucessora de Cajamar #463@72f7ed5df2d57f77c2de72b00b9ccf19672b8337; a base nuclear #454 continua em Draft. Não há homologação oficial nem merge/deploy.

**Fontes municipais oficiais:**
- [Osasco — Manual Web Service v2.1, abril/2026](https://nfe.osasco.sp.gov.br/EissnfeWebApp/Portal/Manual/Geracao%20de%20NFS-e%20Via%20Web%20Service%202.1.pdf). RTC_EmitirNFE, RTC_EmitirNFELote, RTC_ConsultarNFE, RTC_ConsultarLote, ConsultarNotaCompleta e Cancelar; autenticação por chave específica de inscrição municipal.
- [Endpoint de homologação divulgado pela prefeitura](https://nfe.osasco.sp.gov.br/EissnfeWebApp/Portal/NfEletronica.aspx): https://homolog-nfe.osasco.sp.gov.br/EissnfeWebServices/NotaFiscalEletronica.svc?wsdl.
- [Orientação nacional de 29/10/2026](https://www.gov.br/nfse/pt-br/noticias/nfs-e-informa-diretrizes-sobre-a-obrigatoriedade-da-emissao-da-nfs-e-nacional-para-optantes-do-simples-nacional/) — ME/EPP Simples a partir de competência 01/11/2026 via NFS-e nacional; MEI desde 2023.

**Escopo planejado:** reaproveitamento seletivo dos cinco módulos e testes de Osasco originados na PR #461, sem importar Osasco/Barueri/Jundiaí por tabela ou copiar o núcleo B. Completar preparação no mesmo Portal e FiscalApplicationService/UoW, recibo original durável, dados RTC validados, credencial por tenant/unidade/CNPJ/IM, consulta do XML completo sem segundo POST, cancelamento de nota com aprovação e correlação, testes HTTP/E2E, mapeamento dos resultados, escopo e CI completa no HEAD exato.

**Dependências externas:** WSDL/schema vigente verificável, chave de autenticação municipal de contribuinte, resposta real de homologação e layout de impressão oficial. Não inserir segredos nem declarar 100% por artefatos sintéticos. Alterações às fronteiras protegidas do B exigem revisão e autorização de integração.
