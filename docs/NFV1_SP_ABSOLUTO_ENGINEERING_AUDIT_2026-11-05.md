# NFCore Absoluto — Auditoria técnica e operacional de São Paulo

**Data:** 2026-11-05  
**Repositório:** `faabio3131/nf-core-v001`  
**Base auditada:** `main@32106a0a1b10fbf606392cc07cbdec1941acc205`  
**Production (histórico observado):** `a6cd98d278fb8b34af2a6add6ce70af36974c19b`  
**Branch de trabalho:** `feat/nfcore-sp-municipal-routing-r16`  
**PR:** https://github.com/faabio3131/nf-core-v001/pull/355

## Classificação

Este documento distingue código inspecionado, benchmark medido, hipóteses e
certificação ainda pendente. Nenhuma transmissão externa com A1 real ou aprovação
municipal é reivindicada. Não houve mudança de produção nesta PR.

## 1. Auditoria funcional Web

| Jornada | Evidência observada no código | Status técnico |
| --- | --- | --- |
| Empresas, matriz, filiais, CNPJ, IE e IM | `portal/app.js` expõe menu Empresas/Unidades e formulário de perfil fiscal inicial com CNPJ, IE, endereço e IBGE; não demonstra cadastro completo matriz/filial e IM nessa jornada | PARCIAL / E2E PENDENTE |
| Upload A1/PFX | `portal/app.js` inclui `a1-upload-form`; `web/portal_api.py` registra `POST /v1/portal/certificates/a1`, verifica sessão, CSRF e `certificate.manage` e chama Vault criptografado | IMPLEMENTADO / UPLOAD REAL AUTENTICADO PENDENTE |
| Emissão NF-e/NFC-e/NFS-e | Menu de Emissões com `issueFiscalDocument` por documento previamente preparado; não é evidência de editor completo de notas | PARCIAL / E2E PENDENTE |
| Histórico fiscal | Views Documentos/Emissões e consulta de referência de arquivo, com escopo e paginação | PARCIAL / E2E PENDENTE |
| Espelho, download XML e DANFE | Não identificados no `portal/app.js` e `portal/index.html` auditados; não presumir que existem em outra superfície | NÃO COMPROVADO |
| Erros 400/401/403/404/500 | Tratamento de erros e mensagens no `api()`; nenhum teste de navegador autenticado realizado nesta auditoria | E2E PENDENTE |

**Limite da auditoria:** o navegador remoto da contabilidade não foi autenticado.
O Portal respondeu HTTP 200 em preflight operacional anterior, o que não valida o
comportamento após login. A falta de A1 não pode derrubar sessão nem autorizar emissão.

## 2. Benchmark externo real em Contabo: GET /health/ready

**Evidência reproduzível:** https://github.com/faabio3131/nf-core-v001/actions/runs/42042622376  
**Artefato:** https://github.com/faabio3131/nf-core-v001/actions/runs/42042622376/artifacts/13423430806

O benchmark executou **duas fases separadas** usando concorrência de 50 e 100
clientes, com 100 requests em cada fase, via runner GitHub Actions. O endpoint
HTTP é somente leitura: `https://api.nfcore.com.br/health/ready`.

| Métrica | 50 paralelos | 100 paralelos |
| --- | ---: | ---: |
| Total | 100 | 100 |
| HTTP 200 | 100 | 100 |
| Falhas | 0 | 0 |
| Duração da fase (s) | 2,812 | 2,197 |
| Vazão observada (req/s) | 35,56 | 45,51 |
| Latência média (ms) | 1.144,975 | 1.538,499 |
| P50 (ms) | 1.155,661 | 1.536,037 |
| P95 (ms) | 1.582,857 | 2.126,993 |
| P99 (ms) | 1.627,901 | 2.181,674 |
| Máximo (ms) | 1.644,109 | 2.189,815 |
| Meta média < 350 ms | NÃO | NÃO |

O cliente inclui conexões, TLS, rede e fila de concorrência; este resultado não
isola a latência do handler dentro da Contabo. A medição de 100% HTTP 200
não demonstra prontidão transacional ou fiscal.

**Rota incorreta no escopo executivo:** no código `src/kordena_fiscal/web/app.py`,
o endpoint fiscal existente é `POST /v1/issuances`. Não existe rota
`/v2/documents/issue` nesse registro. Não tratar 404 nesse caminho como
falha da rota canônica e não criar segunda API por conveniência.

**NÃO MEDIDOS:** 50/100 autorizações fiscais simultâneas; limitação Starter
120/min, Pro 600/min, Business 2.400/min; pool/conexões PostgreSQL, colisões,
deadlocks, isolamento e idempotência sob carga. Esses testes exigem ambiente
isolado e dados sintéticos, sem envio real à SEFAZ nem impacto em produção.
A disponibilidade do health check não comprova esses itens.

**Reprodução:** `scripts/bench/nfcore_readiness_load.py`; ambiente compartilhado
exige autorização explícita na flag; não há mutação fiscal.

## 3. Envelopes, XMLDSig e XSD

| Componente | CURRENT confirmado | Verificação ainda exigida |
| --- | --- | --- |
| NF-e 4.00 SEFAZ-SP | `nfe_sp_homologation.py` usa SOAP 1.2, `enviNFe`, `tpAmb=2`, HTTPS/mTLS e parser de retorno | Conferência de WSDL e XSD oficiais vigentes e assinatura criptográfica com XML de caso real |
| Assinador NF-e | `nfe_xmldsig.py` usa RSA-SHA256, C14N, `Reference#infNFe`, `Signature`, `KeyInfo/X509Data` | Verificador independente XMLDSig, XSD, transformadas e interoperabilidade |
| NFS-e Nacional | `nfse_nacional_homologation.py` recebe DPS assinada e POST JSON/mTLS | Layout oficial DPS, XSD, contrato API SEFIN, ciclo emissão/consulta; ADN não é gateway de emissão |
| Assinador DPS | `nfse_xmldsig.py` usa RSA-SHA256, C14N, `infDPS`, `X509Data` | Verificação externa e amostras representativas do layout vigente |
| Paulistana | Manual Webservice v3.4 publicado 27/10/2026 | Adaptador, XSD de reforma tributária, assinatura e retorno em homologação NÃO CERTIFICADOS |

Fontes normativas para congelamento e verificação:
- Documentação NFS-e Nacional atualizada em 31/10/2026: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual
- XSD Nacional `NFSe-ESQUEMAS_XSD-v1.01-20260209` e layout `ANEXO_I-SEFIN_ADN-DPS_NFSe-SNNFSe-v1.01-20260209`.
- Nota Paulistana, anúncio do manual WS v3.4 em 27/10/2026: https://notadomilhao.sf.prefeitura.sp.gov.br/noticias/nova-versao-do-manual-de-utilizacao-do-webservice-de-nfs-e/
- Esquemas municipais: https://notadomilhao.sf.prefeitura.sp.gov.br/manuais/

**Crítica de arquitetura:** há dois módulos nacionais de transporte distintos
`nfse_nacional_homologation.py` e `nfse_national_homologation.py`.
Eles precisam ser reconciliados em uma única autoridade canônica; nenhum
terceiro gateway deve ser criado. Não presumir que RSA-SHA1 legado é
intercambiável com RSA-SHA256: aplicação somente por contrato específico,
sem downgrade automático.

## 4. Matriz municipal R16

A ordem enumera **22 municípios**, apesar do título "21".
A PR #355 implementa catálogo consultivo para todos os 22 códigos IBGE.

**Garantia da camada R16:** resolve somente NFS-e por IBGE **do prestador**,
consultando vínculo governado por host, tenant, unidade, ambiente, versão,
aprovação e operação. Não escolhe o provedor com base na localização do tomador;
não usa a tabela consultiva como autoridade; falha fechado sem configuração.

**Integração existente:** `control_plane/commercial.py` já implementa
`DurableProviderBindingResolver`, que consulta `uow.commercial.resolve_provider_binding`
para tenant, unidade, ambiente, tipo fiscal, jurisdição IBGE e operação.
`ProviderGatewayService` já aceita o contrato `ProviderSelectionResolver`.
A nova classe `GovernedSpMunicipalProviderResolver` **delega diretamente ao
resolvedor durável existente**, acrescentando somente o gate R16 para municípios
SP; não cria outra persistência ou aprovação. Testes exercitam esse contrato.
A factory `runtime/sp_municipal_provider_composition.py` já compõe esse
resolvedor canônico com `ProviderGatewayService` e `ProviderRegistry`, com teste
de contrato em `tests/test_sp_municipal_provider_composition.py`.
**A ativação no entrypoint fiscal, os adapters municipais reais e a persistência
de vínculos aprovada para os 22 municípios ainda não estão certificados**;
a PR não declara provedor homologado.

**R16 sem deploy por cidade:** os 22 municípios são somente a lista inicial de
onboarding. O resolvedor aceita qualquer código IBGE de SP válido quando já
existe vínculo persistente autorizado no Control Plane, mesmo fora do catálogo.
Um teste adicional certifica o município de Adamantina (3500105), não listado
na ordem inicial, sem alteração da lógica.

Cidades do catálogo:
Barueri, São Paulo, Campinas, Sorocaba, Guarulhos, Santos, São Caetano do Sul,
Jundiaí, Suzano, Santana de Parnaíba, Osasco, Itapevi, Jandira, Mairiporã,
Arujá, Louveira, Valinhos, Itu, Salto, Monte Mor, Guarujá, São Vicente.

**Regra importante:** adesão ao ADN não implica uso do Emissor Público
Nacional por todos os contribuintes; cada município possui configuração própria
de produtos ativos e pode usar emissor municipal próprio.
Referência: https://www.gov.br/nfse/pt-br/municipios/produtos-disponiveis

## 5. Gates para promover PR #355

1. Ruff, Mypy, Pytest e governança verdes no HEAD.
2. Teste de integração com a persistência/aprovação canônica e ProviderRegistry.
3. Contratos fiscais oficiais por município e XSD, provedor, município e
   contribuinte verificados; nenhum endpoint inferido.
4. Testes E2E Web e autenticação, uploads A1 sintéticos e reais consentidos,
   sem vazamento de chave/senha.
5. Stress transacional em ambiente isolado, com 50/100 concorrentes, sem
   SEFAZ real; métricas e verificações PostgreSQL.
6. Correção dos gargalos até média externa < 350 ms no contexto medido,
   se a meta permanecer aplicável ao endpoint.
7. Homologação externa real e Go/No-Go humano antes de promover produção.

**Conclusão:** há base funcional implantada e roteamento R16 em construção,
mas não existe evidência para afirmar prontidão de emissão fiscal SP absoluta.

## 6. Execução da ordem de fechamento PR #355 — 05/11/2026

- **NFS-e no runtime:** `canonical_fiscal_composition.py` agora pode compor
  `NfseNacionalHomologationGateway` e injetá-lo como `prepared_nfse_gateway`
  de `build_provider_operation_handlers`. A injeção exige um callback confiável
  `trusted_signed_dps_builder` e Vault A1; não há fallback para XML montado
  diretamente do browser. **A composição da API em produção ainda não fornece
  uma autoridade real de montagem/assinatura DPS**, portanto NFS-e Nacional
  não pode ser classificada como operacional.
- **Runtime/profile:** os indicadores antes fixos agora derivam da presença de
  dependências reais via `fiscal_external_dependency_snapshot`, exposto por
  `fiscal_dependency_probe`. O status de dependências **não** demonstra
  certificado válido por tenant, autorização da SEFIN ou homologação externa.
  `fiscal_runtime_external_execution_ready` permanece falso na composição
  padrão sem preparador DPS.
- **Escalabilidade:** `Dockerfile.api` contém quatro workers Uvicorn e
  `--timeout-keep-alive 30`; o proxy `scripts/serve_portal.py` mantém
  pool limitado de conexões HTTP internas e não retransmite mutações fiscais
  quando encontra um socket obsoleto. **Benchmarks pós-deploy, limites de memória
  1 GiB por container e pool PostgreSQL x4 ainda não foram certificados.**
- **Inscrição municipal:** o formulário do Portal passa `municipal_registration`
  à autoridade canônica de cadastro fiscal; o backend valida e armazena a IM no
  `FiscalProfile`, incluindo comparação idempotente em replays. Campo opcional
  conforme vínculo/capacidade municipal, sem afrouxar IE obrigatória.
- **XML e DANFE:** não há contrato canônico demonstrado de arquivos autorizados
  e PDF. Não foram criados links artificiais, endpoints 404 ou botões sem
  download; exige serviço de artefatos com autorização por tenant, prontidão do
  documento, XML protocolado e DANFE correspondente.
- **Tomador/descrição/ISS:** o domínio NFS-e já possui
  `NfseCanonicalDocument` e `NfseServiceLine`, mas a jornada Web de
  preparação governada do tomador e tributação ISS ainda precisa de implementação
  e regras legais municipais validadas.
- **Merge, produção e deploy:** proibido declarar encerramento 100% até a
  matriz de CI/E2E passar, a operação fiscal ser real e o benchmark de
  latência sub-400 ms ser medido e aprovado.

## 7. Benchmark repetido e entrega XML/DANFE — 05/11/2026

**Execução verificada na Contabo, antes do deploy das otimizações desta PR:**
`git show FETCH_HEAD:scripts/bench/nfcore_readiness_load.py` em
`/tmp/nfcore_readiness_bench_r16.py`; GET somente leitura
`https://api.nfcore.com.br/health/ready`, duas fases independentes com
100 requisições cada e 50/100 concorrentes. Nenhuma nota foi emitida.

| Medição | 50 concorrentes | 100 concorrentes |
| --- | ---: | ---: |
| HTTP 200 / total | 100 / 100 | 100 / 100 |
| Falhas | 0 | 0 |
| Latência média (ms) | 1.197,799 | 607,366 |
| P95 (ms) | 2.328,829 | 854,918 |
| P99 (ms) | 2.449,957 | 950,589 |
| Vazão (req/s) | 31,83 | 55,63 |
| Média inferior a 400 ms | NÃO | NÃO |

O benchmark mede o acesso via hostname público a partir da própria VPS,
incluindo proxy, rede/TLS e concorrência. Não é medida isolada do handler
nem validação de performance de emissão fiscal. O contêiner implantado
não contém a configuração de quatro workers e keep-alive da PR #355;
é obrigatório repetir esse benchmark depois de um deploy aprovado.

**Jornada de arquivo fiscal:** a API da sessão humana passou a expor
`GET /v1/portal/documents/{document_reference}/artifacts/{kind}`, limitada
a `authorized_xml` e `danfe`, com unidade/ambiente filtrados por RBAC,
isolamento por tenant, hash de integridade do arquivo canônico, MIME estrito,
`Cache-Control: no-store` e download XML/visualização PDF. A listagem do
Portal só apresenta links quando o item já está efetivamente arquivado.
A ausência do artefato responde com 404 controlado (não substitui
o documento por conteúdo simulado).

**Evolução posterior à medição:** o adaptador SEFAZ-SP passou a
montar `nfeProc` somente após confirmar `cStat=100`, chave coincidente,
protocolo e `tpAmb=2`. O serviço fiscal persiste `AUTHORIZED_XML` na mesma
transação que marca a emissão como autorizada (sem novo envio fiscal).
Para o DANFE/PDF, o Portal agora pode renderizar localmente o arquivo
a partir do `nfeProc` autenticado, usando BrazilFiscalReport 1.3.1
(LGPL-3.0), sem transmitir XML à biblioteca remota; PDF já arquivado
continua sendo preferido. A geração só ocorre sob sessão, escopo e arquivo
autorizado efetivos. **Ainda faltam E2E com NF-e homologada real,
verificação independente de XMLDSig após o `nfeProc`, validação visual de
DANFE e a jornada completa de preparação da DPS/tomador/serviço/ISS.
Portanto, não está certificada emissão fiscal integral NFS-e/NF-e.**
