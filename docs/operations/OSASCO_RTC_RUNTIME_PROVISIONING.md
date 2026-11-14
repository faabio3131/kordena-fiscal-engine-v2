# Osasco RTC: ativação api:app e contrato municipal atualizado

**Fonte primária municipal atual:** Prefeitura de Osasco, [Geração de NFS-e via Web Service v2.2, OUT/2026](https://nfe.osasco.sp.gov.br/EissnfeWebApp/Portal/Manual/Geracao%20de%20NFS-e%20Via%20Web%20Service%202.2.pdf), publicada na página [Manuais do Sistema](https://nfe.osasco.sp.gov.br/EissnfeWebApp/Portal/Manuais.aspx). Substitui v2.1 abril/2026.

## Invariantes da ativação

A API canônica aceita a variável NFCORE_OSASCO_RTC_CONFIG_PATH com caminho absoluto para manifesto operador de homologação. Não existe API paralela ou outro banco; o mesmo FiscalApplicationService/UoW reserva o RPS original antes do POST. O binding do contribuinte permanece no Control Plane, separado por tenant/unidade/CNPJ/inscrição municipal/perfil fiscal, com resolução de referência de credencial pelo mesmo SecretResolutionService, FiscalSecretVault e GSM com identidade de workload. O manifesto não contém chaves fiscais, segredos ou senha.

O modo reviewed-homologation exige SHA-256 de WSDL original e cada XSD do conjunto revisado; verifica os métodos RTC_EmitirNFE, ConsultarNotaCompleta e Cancelar na binding SOAP 1.1; valida XML de solicitação, consulta e cancelamento e as respostas oficiais com o schema específico. Um HTML de landing page WCF NÃO substitui o arquivo XML WSDL.

O RTC municipal é somente para competência 2026 em diante e contribuinte com regime NORMAL (TaxRegimeCode=3) e perfil fiscal revisado. Simples Nacional segue o roteamento nacional pertinente.

## Fontes oficiais para baixar os artefatos

- WSDL homologação: https://homolog-nfe.osasco.sp.gov.br/EissnfeWebServices/NotaFiscalEletronica.svc?wsdl
- WSDL único homologação: https://homolog-nfe.osasco.sp.gov.br/EissnfeWebServices/NotaFiscalEletronica.svc?singleWsdl
- Produção, para referência SEM SUBMETER OPERAÇÃO: https://nfe.osasco.sp.gov.br/EissnfeWebServices/NotaFiscalEletronica.svc?wsdl

Na estação autorizada, obter BYTES originais (não XML convertido em texto sem atributos). Verificar estrutura, imports/includes, binding e SOAPActions; salvar cada arquivo XSD revisado e calcular SHA-256. Recomenda-se:

    curl --fail --location --proto '=https' --tlsv1.2 \
      'https://homolog-nfe.osasco.sp.gov.br/EissnfeWebServices/NotaFiscalEletronica.svc?singleWsdl' \
      --output osasco-homolog-2026.wsdl
    sha256sum osasco-homolog-2026.wsdl

As ferramentas de leitura públicas consultadas retornaram o texto XML sem os atributos de namespaces/operadores; esse texto não pode ser usado como prova byte-a-byte nem para gerar hash verdadeiro. Não inventar hash, XSD, SOAPAction ou retorno fiscal.

## Manifesto operador

Exatamente estes grupos JSON: mode, wsdl_file, wsdl_sha256, binding_name, xsd_resources, xsd_roots, issuers e gsm.

- mode: reviewed-homologation.
- wsdl_file: nome relativo seguro de WSDL local; wsdl_sha256: hash real.
- binding_name: SOAP 1.1 revisada no WSDL vigente.
- xsd_resources: dicionário nome local → SHA-256 real, preservando imports do conjunto.
- xsd_roots: nome de arquivo raiz para cada um dos cinco documentos: RTC_EmitirNFE, ConsultarNotaCompleta, Cancelar, ConsultarNotaCompletaResponse e CancelarResponse.
- issuers: lista de tenant_id, unit_id, issuer_cnpj, profile_id, profile_version, tax_regime=3, policy. Cada policy contém: source_normative, rule_version, effective_from, effective_through, municipal_service_code, national_taxation_code, activity, class_trib, nbs_code, incidence_location, operation_indicator, service_city, service_city_ibge, service_state, recipient_street_type, iss_rate, pis, cofins, csll, income_tax, inss, other_taxes, test_only. Opcionalmente no_iss_incidence e additional_info. Valores de tributos sempre strings decimais exatas.
- gsm: project_id, project_number, resources (allowlist explícita de nomes projects/<projeto>/secrets/<identificador>), workload_id=nfcore-api.

A configuração usa os dados da versão LEGALMENTE REVISADA por perfil, não valores fabricados. No staging, uma identidade federada WIF montada em NFCORE_OSASCO_GSM_WIF_FILE é necessária. Na produção, usa a identidade da API já validada pelo mecanismo production_credentials, sem ADC ou arquivo genérico. Não imprimir segredo nos logs.

## Correções da v2.2 (outubro/2026)

O manual atual adicionou os campos ResponsavelTributario (P=prestador, T=tomador) e ValoresCartorios (somente perfis autorizados de cartórios). ResponsavelTributario é opcional, derivado de SubstituicaoTributaria quando ausente, e o adaptador pode enviá-lo com a mesma classificação fiscal canônica. Os montantes dos cartórios não podem ser inventados.

O manual manda valor Aliquota 0.00 no regime NORMAL, calculado pela Prefeitura; exceção para ST de serviço prestado fora de Osasco, quando a alíquota revisada da localidade externa deve ser informada. Separar ISS retido, PIS/COFINS retidos e PIS/COFINS próprios. Os códigos ClassTrib, NBS e IndOperacao são classificados por fonte verificada; não deduzir bases de IBS/CBS de valores brutos.

As notas RTC usam RPS durável original e emissão com tentativa idempotente, consulta read-only pelo recibo e XML completo. Cancelar N versus S exige aprovação humana, prova oficial e vínculo por nota. O teste sintético não é homologação externa.

## Critérios de fechamento

CI no HEAD final, incluindo Ruff, MyPy, Pytest, PostgreSQL, Portal HTTP com transporte SOAP simulado, operações de emissão/consulta/cancelamento/substituição e A1 sem perda de isolamento. A versão real de WSDL/XSD, a chave municipal autorizada e os recibos reais do fisco devem ser validados separadamente. Nenhuma implantação produtiva, DDL, mudança de segredo ou emissão fiscal real é parte desta execução.
