# NFCore — Pesquisa oficial de emissor NFS-e MG, W1 (11/11/2026)

**Status:** fontes públicas conferidas para 4 dos 20 municípios. **Não é contrato de integração XSD/API homologado, nem certificação de emissão.** Cada situação deve ser versionada por regime, contribuinte, competência, tpAmb e operação antes de definir um binding.

## Evidências e divergências materiais

| Município (IBGE) | Evidência de canal em 11/11/2026 | Fonte governamental | Atenção para o adaptador |
|---|---|---|---|
| **Belo Horizonte (3106200)** | Prefeitura confirma Emissor Nacional para ME/EPP Simples, com obrigação local anterior a novembro/2026; avisos adicionais impõem parâmetros ISS/competência para distintos cenários. | [BHISS — avisos oficiais](https://prefeitura.pbh.gov.br/fazenda/bhiss/avisos) | Não generalizar automaticamente MEI/Simples a todos os regimes; confirmar habilitação específica, cTribNac, ISS, RTC e responsabilidades do BHISS. |
| **Betim (3106705)** | Prefeitura afirma Emissor Nacional exclusivo desde 01/01/2026 e desligamento do Ginfes. Decreto municipal 53.621/2026 (setembro) fixa cancelamento diretamente no emissor em até **90 dias** e até **R$ 500 mil**, e substituição em até **180 dias**, com exceções exigindo processo administrativo. | [Aviso setembro/2026](https://www.betim.mg.gov.br/portal/noticias/0/3/15592/betim-amplia-prazos-para-substituicao-e-cancelamento-de-notas-fiscais-diretamente-no-sistema); [descontinuação Ginfes](https://www.betim.mg.gov.br/portal/noticias/0/3/14975/prefeitura-de-betim-chama-a-atencao-para-novo-padrao-de-emissao-de-notas-fiscais) | Operações cancelamento/substituição devem ser determinadas pelo contrato nacional mais política municipal; **não** enviar cancelamentos vedados ou fingir que serviço local antigo está ativo. Não codificar valores sem vigência/versão e revisão jurídica. |
| **Uberlândia (3170206)** | Prefeitura anunciou adesão com vigência a partir de 01/01/2026, mas o comunicado dizia que cronograma/orientações técnicas ainda seriam publicados. | [Comunicado 21/11/2025](https://www.uberlandia.mg.gov.br/2025/11/21/prefeitura-adere-ao-emissor-nacional-da-nota-fiscal-de-servicos-eletronica-nfs-e/) | `NATIONAL_ANNOUNCED_RECHECK_REQUIRED`; verificar cronograma posterior, credenciamento e operações antes do binding. |
| **Contagem (3118601)** | A própria Secretaria da Fazenda informa **Novo ISS Digital** próprio, com webservices de teste e produção e payload XML/JSON compatível com o leiaute nacional, em substituição à plataforma antiga desde 01/01/2026. | [Receita de Contagem — NFS-e](https://receita.contagem.mg.gov.br/nfe/) | `MUNICIPAL_NATIONAL_LAYOUT`: **compatibilidade de XML não significa identidade de endpoint, autenticação ou autorização**. Não reaproveitar diretamente o transporte SEFIN Nacional; verificar Swagger municipal, autenticação, endpoints, XSD e eventos contra o contrato vigente. |

**Alerta de segurança para a pesquisa de Contagem:** a versão HTML pública consultada exibia links aparentemente não relacionados a assuntos fiscais na área inicial da página. A identificação do emissor foi extraída do corpo da Secretaria da Fazenda, mas qualquer link para documentação externa/Swagger e endpoint operacional precisa ser reconfirmado pelo domínio/ato oficial e revisado antes de consumo automático. Nunca executar ou embutir URL derivada de conteúdo não confiável.

## Restantes 16 municípios W1

Uberaba, Juiz de Fora, Extrema, Ipatinga, Sete Lagoas, Pouso Alegre, Montes Claros, Nova Lima, Poços de Caldas, Varginha, Divinópolis, Araxá, Governador Valadares, Patos de Minas, Congonhas e Itabira: **`RESEARCH_REQUIRED`**. A ausência nesta matriz não prova que não haja integração: é apenas falta de verificação suficiente nesta auditoria.

## Implementação permitida e blockers

1. Reutilizar o builder e transporte NFS-e Nacional apenas onde contrato/competência aplicáveis e prova técnica permitirem; **não** confundir ADN, cadastro de conveniados e emissão autorizada.
2. Abrir um adaptador municipal ou configuração explícita distinta para Contagem, quando forem obtidos e versionados Swagger/WSDL, autenticação, XMLDSig, eventos, credenciais e erros oficiais. Jamais apontar rota municipal a host obtido exclusivamente de página HTML não verificada.
3. Cada capacidade precisa de `municipality_ibge + issuer channel + tax regime/competence + operation + tpAmb + binding` e motivo explícito de indisponibilidade. A1/CSC reais por contribuinte permanecem no cofre, não no catálogo.
4. Testar cancelamento/substituição Betim apenas com regras municipais validadas por especialista; atualização normativa pode alterar prazo ou limites. Teste local/sintético não é homologação oficial.
5. Até os contratos completos, todas as quatro cidades permanecem **`NOT_INTERNALLY_COMPLETE`** para esta onda; nenhuma mudança de runtime é autorizada por este documento.

**Proveniência:** prefeitura de BH, Betim, Uberlândia e Secretaria da Fazenda de Contagem (URLs acima, conferidas em 11/11/2026); classificação de análise, sujeita a revisão de vigência. Demais polos aguardam fontes oficiais. Alinhado à reconciliação `docs/NFCORE_MG_POLOS_ECONOMICOS_WAVE1_RECONCILIACAO_2026-11-11.md`.
