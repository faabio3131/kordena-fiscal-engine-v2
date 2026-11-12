# NFCore V1 — NFS-e Nacional: XML autorizado em emissão e recuperação (P0)

**Data:** 2026-11-12. **Status:** IMPLEMENTADO EM BRANCH / TESTES CRIADOS / CI INTEGRADA NÃO COMPROVADA.
**Owner:** Agente B. **PR:** #454. **Dependências:** #427 (nDPS durável), #451/#456 (XSD 1.01), #450 (emissor nativo), reconciliação funcional com #446 (Agente A).
**Sem:** merge, deploy, transmissão, A1 real, migração v22, homologação ou autorização produtiva.

## Achado CURRENT no candidato #427

1. gateway/nfse_national_query.py:_validate_official_nfse() conferia raiz e infNFSe/@Id vinculados à chave retornada pelo GET nacional, mas não devolvia o XML descomprimido.
2. gateway/nfse_national_query.py:NfseNationalHomologationQueryGateway.query() devolvia apenas invoice_reference e provider_request_id. O XML que acabara de ser obtido desaparecia.
3. application/service.py:reconcile_prepared_nfse_authorization() registrava PROVIDER_RESPONSE, marcava AUTHORIZED e committava sem inserir AUTHORIZED_XML.
4. application/service.py:authorize_prepared_document() arquivava AUTHORIZED_XML somente quando o resultado era de NF-e/NFC-e (AuthorizationResult), não NFS-e (NfseAuthorizationResult).

**Risco:** estado terminal AUTHORIZED sem o documento fiscal autorizado, impedindo prova, reimpressão e custódia; a chave sozinha não basta.

## Alteração implementada

- issuance/nfe_nfse.py: NfseAuthorizationResult tem authorized_xml opcional tipado e limitado (2 MiB); somente AUTHORIZED permite esse campo; REJECTED/PENDING com XML falha fechado.
- gateway/nfse_national_query.py: _validate_official_nfse() devolve os bytes originais após descompressão limitada, parse XML e conferência da chave/Id. O GET nacional propaga esse XML para o resultado canônico, sem POST ou novo DPS.
- application/service.py: authorize_prepared_document() aceita authorized_xml de ambos os tipos de resultado fiscal e chama finalize_authorized com a mesma UoW/arquivo.
- application/service.py: reconcile_prepared_nfse_authorization() anexa AUTHORIZED_XML dentro da mesma UoW que grava estado AUTHORIZED, reserva/idempotência e PROVIDER_RESPONSE. Falha transacional impede metade do commit.
- tests/gateway/test_national_nfse_query_receipt_archive.py: conserva bytes, rejeita XML de chave divergente e teste do contrato de estados/limites.
- tests/application/test_nfse_recovered_receipt_atomicity.py: casos sintéticos de emissão direta, timeout/recovery com consulta, AUTHORIZED_XML e PROVIDER_RESPONSE uma só vez; replay não chama outra emissão/consulta.

## Limitações de evidência

Os testes construídos são **sintéticos**. O fake de recibo não tem assinatura ICP-Brasil real nem autenticação SEFIN. O gateway real consulta com mTLS e valida raiz/Id, mas a verificação de XMLDSig, schema oficial integral, vínculo de protocolo e certificação independente precisam ser implementados/verificados no gate B11 antes de considerar o fluxo internamente certificado.

O pacote XSD do ZIP oficial 1.01 precisa ser comparado byte a byte ao recurso versionado (ver dossiê de #454). A reconciliação dos arquivos e resultados com #450 e último HEAD da #446 é obrigatória: preservar as regras de elegibilidade SP/MG e o número reservado da #427; nunca copiar builder hash anterior da #446.

## Gates

- [x] Implementação da cadeia de dados sem segunda API/motor/persistência.
- [x] Testes unitários e sintéticos de replay/atômicos adicionados.
- [ ] Pytest/PG/Ruff/Mypy/CI **no HEAD integrado exato**.
- [ ] XMLDSig independente e schema completo de NFSe autorizada.
- [ ] Resposta oficial SEFIN com A1 autorizado em homologação.
- [ ] Conciliação final de #427/#450/#446 por função.
- [ ] Autorização humana separada para migration v22, merge e homologação.

**Classificação:** INTERNAL_IMPLEMENTATION_CANDIDATE / INTERNAL_CERTIFICATION_PENDING /
EXTERNAL_HOMOLOGATION_PENDING. Nunca tratar status AUTHORIZED sintético como nota emitida.
