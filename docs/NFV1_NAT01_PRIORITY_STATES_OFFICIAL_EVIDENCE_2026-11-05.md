# NFCore NAT-01 — Primeiro lote nacional: inventário verificável MG / RJ / PR / MT / MS

**Data da investigação:** 05/11/2026  
**Classificação:** CURRENT de documentação pública e implementação interna proposta, **não homologação**  
**Branch:** `feat/nfcore-nat01-priority-uf-capability-catalog`  
**Dependência:** NAT-00 — PR #355 integrada; reconciliação `main`/`production` estava pendente na PR #358; CI de correção de Playwright #359 aprovada e integrada à main na consulta deste checkpoint. Revalidar HEAD antes de merge.  
**FONTE DE VERDADE:** arquivos do código, catálogos oficiais e CI do commit.

## Prioridade formal, município-piloto e homologação necessária

| Ordem | UF | Cidade-piloto | IBGE | NF-e modelo 55 | NFC-e modelo 65 | NFS-e (primeiro município) |
|---:|---|---|---|---|---|---|
| 1 | MG | Belo Horizonte | 3106200 | SEFAZ-MG, WS NF-e 4.00 publicados | WS NFC-e MG próprios, incluindo CSC/QR conforme manual | Obter contrato vigente BH/SEFIN, competência ISS, DPS/RPS e prova de emissão |
| 2 | RJ | Rio de Janeiro | 3304557 | SVRS conforme relação oficial NF-e | **Não inferir SVRS a partir da NF-e**; pesquisar contrato e credenciamento NFC-e RJ | Verificar emissor real e disponibilidade/parametrização nacional da cidade |
| 3 | PR | Curitiba | 4106902 | SEFA/PR, catálogo oficial | SEFA/PR NFC-e 4.00; CSC/QR e credenciamento | Verificar prefeitura/SEFIN, regras de competência |
| 4 | MT | Cuiabá | 5103403 | SEFAZ-MT no catálogo nacional NF-e | MT NFC-e (contrato distinto a confirmar) | Verificar emissor e parametrização municipais |
| 5 | MS | Campo Grande | 5002704 | SEFAZ-MS no catálogo nacional NF-e | MS NFC-e (contrato distinto a confirmar) | Verificar prefeitura/SEFIN e regras vigentes |

**IMPORTANTE:** Município listado em página de *conveniados* ao programa nacional da NFS-e não prova que a **emissão** municipal já está habilitada para cada contribuinte. A integração ao ADN é distinta da autorização fiscal. Verificar contrato, credenciamento, ambiente e capacidades por município antes de alterar qualquer binding de produção.

## Fontes oficiais de referência verificadas

- [Portal Nacional NF-e — serviços web e grupos de autorizadores](https://www.nfe.fazenda.gov.br/portal/webServices.aspx): RJ figura em SVRS para serviços NF-e; MG, PR, MT e MS têm autorizadores próprios; contingência é autoridade separada.
- [SPED MG — NF-e Web Services](https://portalsped.fazenda.mg.gov.br/spedmg/nfe/webservices/): NF-e 4.00, autorizacao, consulta, inutilizacao, status, recepcao evento, homologação e produção diferenciadas.
- [SPED MG — NFC-e Web Services](https://portalsped.fazenda.mg.gov.br/spedmg/nfce/web-services/): serviços distintos dos de NF-e, QR Code e ambientes.
- [SEFA/PR — NFC-e Web Services](https://sped.fazenda.pr.gov.br/NFCe/Pagina/Web-Services-NFC-e): endpoints oficiais NFC-e 4.00 e QR Code.
- [SEFA/PR — NF-e](https://sped.fazenda.pr.gov.br/NFe/Pagina/Servicos-web-services-disponiveis).
- [SEFAZ MT — NFC-e](https://www.sefaz.mt.gov.br/portal/nfce/).
- [SEFAZ MS — NF-e](https://www.sefaz.ms.gov.br/documentos-fiscais-eletronicos/nf-e/) e [NFC-e](https://www.sefaz.ms.gov.br/documentos-fiscais-eletronicos/nfc-e/).
- [NFS-e Nacional — municípios conveniados](https://www.gov.br/nfse/pt-br/municipios/municipios-conveniados): contexto histórico de adesão, não certificado de emissão.
- [Governo Federal — pendências municipais de parametrização](https://www.gov.br/nfse/pt-br/noticias/municipios-sem-adesao-ou-parametrizacao-da-nfs-e-ja-estao-sujeitos-a-bloqueio-de-transferencias) (28/05/2026): adesão e parametrização são exigências distintas.

## Descoberta municipal importante (05/11/2026): quatro rotas nacionais, uma distinta

Fontes oficiais atuais alteram a hipótese inicial de que seria preciso construir um adaptador local diferente por capital:

- **Belo Horizonte/MG:** aviso BHISS da prefeitura aponta NFS-e via Emissor Nacional e parâmetros próprios do ISS, IM e regimes municipais: https://prefeitura.pbh.gov.br/fazenda/bhiss/avisos.
- **Rio de Janeiro/RJ:** prefeitura determina padrão nacional desde 01/01/2026, mantendo Nota Carioca apenas para documentos de competências anteriores: https://fazenda.prefeitura.rio/noticias/emissao-do-iss-na-prefeitura-do-rio-tera-mudanca-a-partir-de-1o-de-janeiro-de-2026/.
- **Curitiba/PR:** guia oficial e Portaria municipal descrevem migração integral ao Emissor Nacional em 01/01/2026: https://lp.curitiba.pr.gov.br/notanacional/.
- **Cuiabá/MT:** comunicado da prefeitura de 24/08/2026 adia obrigatoriedade exclusiva do Emissor Nacional para **01/11/2026**, após encerramento do Free Nota/WS municipal: https://www.cuiaba.mt.gov.br/noticias/cuiaba-prorroga-prazo-para-emissao-de-nfs-e-pelo-emissor-nacional.
- **Campo Grande/MS:** comunicação da prefeitura indica **emissor próprio integrado ao padrão nacional**, portanto requer verificação de WSDL/API municipal, política de trânsito via ADN ou emissão pelo ambiente nacional. **Não presumir** o mesmo endpoint dos quatro anteriores: https://www.campogrande.ms.gov.br/cgnoticias/noticia/novo-sistema-de-nota-fiscal-trara-mais-agilidade-seguranca-e-estabilidade/.

**Decisão técnica de desenho:** implementar **um** adaptador canônico NFS-e Nacional (DPS, assinatura, comunicação, consulta, eventos, correlação e armazenamento) e parametrizar ISS/IM/competência por município; Campo Grande fica `MUNICIPAL_HYBRID_REVIEW` até evidência oficial de contrato. A classificação do catálogo é SOMENTE evidência de pesquisa, não `PRODUCTION_APPROVED` nem binding de cliente.

**Blocker:** obter e validar XSD, contratos de DPS/API, códigos de serviço, parametrização ISS e evidência de habilitação por CNPJ, município e tpAmb antes de transmitir.

## Implementação interna NAT-01 entregue nesta PR

- `src/kordena_fiscal/control_plane/national_priority_inventory.py`: estrutura imutável, 5 UFs exatas, IBGE das cidades iniciais, fonte pública para cada documento; validação cruzada UF/IBGE e HTTPS público, sem estado de produção declarado.
- `tests/control_plane/test_national_priority_inventory.py`: cobertura de ordem, cidades, fontes e negação de fallback, metadados imutáveis, sem criação de provider binding, emissão ou endpoint exposto.
- **Não substitui** o `DurableProviderBindingResolver`, o `ProviderRegistry`, o `TaxRuleEngine`, nem os adaptadores fiscais. Este catálogo não possui credenciais nem URLs de transporte; URLs são referências documentais apenas.

## Próximas etapas executáveis (não confundir com certificação)

**NAT-01-G01:** obter e versionar famílias de autorizador e contratos oficiais por modelo/UF; ADR de proveniência/validade/approval; confirmar que estado no catálogo é informativo, nunca autorização.

**NAT-03-MG:** criar o catálogo canônico de endpoints oficiais MG por ambiente/modelo/operação como configuração auditada, com hashes e versionamento; injetar no gateway existente somente depois de checar escopo, signer, A1 e readiness; testes de erro/mTLS, XSD/XMLDSig e negative tests.

**NAT-UF-MG-T04/05/06:** jornadas NF-e, NFC-e e NFS-e de BH separadas; adotar gateway de família existente quando tecnicamente compatível; não fazer fallback para SP nem usar catálogo público como fonte dinâmica de URL.

**NAT-02:** arquitetura escritório contábil↔clientes e CNPJ matriz/filiais, sem segunda auth e sem permitir elevação implícita de privilégios.

## Estado e blockers

- NAT-01: `IMPLEMENTING`, testes e CI remotos exigidos.
- NAT-UF-MG/RJ/PR/MT/MS: `NOT_STARTED` como **módulo completo**; há evidência inicial de serviços, não adaptadores liberados.
- Homologação de todos os municípios/SP e da onda nacional: `EXTERNAL_BLOCKED` até evidências reais.
- Não realizar mTLS com A1 real, emissão, deploy ou alterações de `production` por conta desta PR.
