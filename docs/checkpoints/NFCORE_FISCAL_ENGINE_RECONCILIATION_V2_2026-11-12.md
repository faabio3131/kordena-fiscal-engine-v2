# NFCore V1 — Reconciliação V2 da auditoria do motor fiscal
**Corte:** 12/11/2026, após CI #2420, UTC. **Natureza:** atualização documental; sem alteração de runtime, DDL, branches alheias, merge ou deploy.
**Autoridade de acompanhamento:** issue #447. **Baseline histórico da auditoria anexa:** production@ea4bdd3bcb9b61e6522081a14e5cc9ad1ced9599. **Main consultada:** ef7ebe7e104f0e49897075cd961d51a052948b43.

## Veredito reconciliado
- O NFCore **possui motor fiscal próprio**: domínio, preparação, numeração onde já suportada, Vault A1, XMLDSig, mTLS, gateway de homologação, ciclo de vida, idempotência, arquivo e operações do Portal. Bling, Odoo ou qualquer ERP não são autoridade de emissão nem pré-requisito arquitetural.
- A auditoria de production era válida para aquele SHA. É incorreto tratar ausência em production como ausência universal em main e branches candidatas.
- **Não foi apresentada prova oficial da cadeia inteira** com contribuinte autorizado, A1 real, SEFIN/SEFAZ, protocolo, XML autorizado e recuperação. Não declarar homologação, 22/22 municípios certificados nem tpAmb=1 liberado.
- Preparação de nota, integração de código, CI verde, status de health e transporte configurado não equivalem a autorização fiscal oficial.

## Status de engenharia comprovado
| Frente | Identidade/certificação | Observação |
|---|---|---|
| #449 emissor nativo | d6f8f1c37377e5dcb4077410ee035cb5b7ede0a4; CI #2399 SUCCESS registrada na #447 | prepareNativeNfse; tomador; XML autorizado; DANFSe; resultado saneado. Draft, sem deploy |
| #450 integração seletiva | 64e8f582985463e9ccb0dfea5f44e6e4d904bc6b; **CI #2413 SUCCESS**, governança aprovada | Combina #446@cdd097953761fd122abe1bc9c4469030749f399e e #449@d6f8f1c; mantém query Nacional GET e DPS/tomador. Não é merge |
| #446 SP4/SP22 | HEAD d7e42c4121d1f6a370a5918559fdb9022a382050 | **10 commits adicionais** após o snapshot da #450; arquivos adicionais de Barueri, Osasco, Jundiaí e bridges/testes. Nenhuma cidade oficialmente homologada por esta evidência |
| #427 série DPS | HEAD 859214a98fe0158223d795bfd841d5f80daa8b31 | Serial transacional v22, Draft e mergeable=false; não aplicar migração |
| #451 patch XSD 1.01 | HEAD 334821b53ae3b562b72ae667f2a6c0968bfb2140; **CI #2420 FAILURE** | endNac e fixture 1.00 corrigidos; **9 falhas restantes de serie XSD**; não certificada |

## Mapa atualizado de lacunas
- **G1/G2:** preparo nativo e tomador existem como candidatos #449/#450; faltam integração no HEAD final, mapeamento completo de endereço/IM e E2E.
- **G3/G9:** propagação do XML oficial, arquivo, DANFSe e retorno saneado candidatos na #450; confirmar com arquivo/assinatura/protocolo e uso seguro do Portal.
- **G4:** consulta Nacional GET e recuperação preservadas da #446 na #450; certificar timeout/replay/consulta sem segundo POST e XML recuperado.
- **G5/G11:** tributação por regime/competência, ISS, retenção, imunidade, exceções, catálogo oficial e preauditoria normativa ainda não completos. Falha deve bloquear emissão, não assumir valores.
- **G6:** o Emissor Nacional para ME/EPP do Simples é obrigatório desde **01/11/2026 pela competência**, por Resolução CGSN 191/2026; Cajamar comunicou adesão em 15/07/2026 referindo a data antiga de setembro. Não confirma CNPJ/A1 habilitado nem aceite via NFCore.
- **G8:** DPS sequencial candidata em #427, mas integração e XSD estão bloqueados pela #451. **P0 interno.**
- **G10:** evento/cancelamento NFS-e Nacional ainda não certificado como ciclo completo.
- **G13/G15:** main já contém componentes MG65 e WebISS Extrema que tornam obsoleta a expressão 'não existe municipal/NFC-e'. Fechamento ponta a ponta e município por município continuam pendentes. CT-e/MDF-e dependem de decisão explícita de escopo.
- **G7/G14 e E1-E4:** dependências externas distintas: A1 real, ambiente oficial, protocolos, homologação autorizada e ativação produtiva governada.
- **G12/G16:** backup/restore Vault, proteção da chave mestre e vigília normativa não foram revalidados nesta revisão.

## Correção normativa importante
A Receita Federal em 14/08/2026 diferencia:
1. Uso obrigatório do Emissor Nacional por ME/EPP Simples a partir de 01/11/2026 (por competência);
2. Aplicação das regras de CBS/IBS ao optante do Simples segundo orientação a partir de 01/01/2027, quando cabível.
Datas de adoção de emissor não substituem a matriz de layouts, campos e tributação por competência/regime.
Fontes: https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/agosto/simples-nacional-nfs-e-nacional-sera-obrigatoria-para-me-e-epp-a-partir-de-1o-de-novembro-de-2026
https://www.gov.br/nfse/pt-br/noticias/nfs-e-informa-diretrizes-sobre-a-obrigatoriedade-da-emissao-da-nfs-e-nacional-para-optantes-do-simples-nacional/
https://cajamar.sp.gov.br/noticias/2026/07/15/empresas-do-simples-nacional-deverao-emitir-nfs-e-exclusivamente-pelo-emissor-nacional-a-partir-de-setembro/

## Ordem governada de fechamento
1. Eliminar as 9 falhas reais de XSD 1.01 da #451, com prova independente, sem desligar validação nem adulterar silenciosamente schema oficial. Ver documento de incidente complementar.
2. Concluir serial durável na autoridade da #427; validar reserva, ID, tomador, query, rollback/replay/concorrência e alinhar migração v22 antes de qualquer execução de DDL.
3. Incorporar seletivamente #427 à composição candidata #450 sem perder tomador/XML/DANFSe/consulta; reconciliar **também os 10 commits posteriores da #446** junto ao owner municipal.
4. Concluir regras fiscais internas por competência/município/regime e operações aplicáveis da V1 (NF-e, NFC-e, NFS-e e adaptadores municipais); não presumir regras/aliquotas nem usar status sintético como selo.
5. Certificar no **HEAD final** Ruff, Mypy, Pytest, PostgreSQL real, XML/XSD/XMLDSig independente, browser E2E, segurança, arquivos, PDF, falhas/recovery, containers e governança. Zero aprovação herdada de SHA anterior.
6. Só depois passar a E1-E4: A1 real autorizado, emissão/consulta/eventos oficiais, dossiê por município, aprovação humana de merge/deploy e ativação tpAmb=1 em processo separado.

**Proibido:** mesclar PRs alheias cegamente, invadir branches dos executores, aplicar v22 produtiva, transmitir fiscalmente com dados inventados, divulgar PFX/segredo, certificar SP22 pela matriz de catálogo ou prometer autorização fiscal oficial.

**Links:** issue #447 https://github.com/faabio3131/nf-core-v001/issues/447 ; #450 https://github.com/faabio3131/nf-core-v001/pull/450 ; #451 https://github.com/faabio3131/nf-core-v001/pull/451 ; CI #2413 https://github.com/faabio3131/nf-core-v001/actions/runs/43237571670 ; CI #2420 https://github.com/faabio3131/nf-core-v001/actions/runs/43239881490.
