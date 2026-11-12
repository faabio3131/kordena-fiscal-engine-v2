# NFCore — SP4: Cajamar, Barueri, Osasco e Jundiaí (12/11/2026)

**Escopo pedido pelo proprietário:** concluir um único bloco operacional antes do aceite, sem promover casos parciais como municípios prontos. Escopo adicional SP4 dentro da issue #445 e PR #446. Não alterar BH #440, Bling, credenciais e Contabo.

**NÃO É FECHAMENTO.** A homologação da contabilidade está planejada para 13/11, 09h BRT. Todo código deste documento é de **branch isolada**, sem merge/deploy; testes executados com serviços sintéticos não são respostas oficiais de prefeitura. A ausência de credencial do emissor/contrato não autoriza simular uma NFS-e real.

## Auditoria atual: quatro municípios e dois canais distintos

| Emissor (IBGE) | Canal federal quando MEI (desde 01/09/2023) / ME-EPP Simples (competência desde 01/11/2026) | Canal municipal quando legalmente aplicável | Código interno nesta PR | Critério ainda não comprovado |
|---|---|---|---|---|
| Cajamar (`3509205`) | NFS-e Nacional, apenas com binding e A1 do contribuinte | GeisWeb, versão/endpoint e liberação por CNPJ a conferir na fonte municipal | `cajamar_geisweb_homologation.py` fail-closed | WSDL/XSD próprio vigente, XMLDSig de Cajamar, credenciamento e E2E de emissão, consulta e cancelamento |
| Barueri (`3505708`) | NFS-e Nacional, idem | Prefeitura, RPS em arquivo PMB004; WebService de remessa/status/retorno | `barueri_pmb004_homologation.py` fail-closed | Builder/validador de **todos** os campos PMB004, numeração única, resposta final correlacionada ao XML e lifecycle |
| Osasco (`3534401`) | NFS-e Nacional, idem | Prefeitura EissNfe, WCF SOAP com métodos RTC_ e chave própria do contribuinte | `osasco_rtc_homologation.py` fail-closed | WSDL/hash vivo validado, XML completo do RTC, conversão do resultado em NFS-e oficial e fluxo de cancelamento |
| Jundiaí (`3525904`) | NFS-e Nacional, idem | GissOnline V2 (ABRASF 2.04+RTC, **não** usar Ginfes legado) | `jundiai_giss_homologation.py` fail-closed | Pacote XSD vigente validado, XMLDSig envelope, prova por RPS/lote e cancelamento com resposta oficial |

O roteador principal `_GovernedNfseRouter` reconhece os canais Nacional e WebISS Extrema. Nesta PR, os quatro transportes municipais foram criados como fronteiras opt-in **mas ainda não são adaptadores completos do domínio `NfseAuthorizationRequest` nem compõem o runtime de produção**. Não são consideráveis operacionalmente integrados.

## Entregas implementadas na branch sem fingir E2E

- Nacional (comum aos 4): guard SP obrigatório por regime e competência antes do A1; autorização mTLS para homologação; XML oficial ligado à chave; DPS determinística recuperada por ID; GET /dps -> GET /nfse sem novo POST; binding específico `QUERY` no Control Plane antes da consulta; testes de regressão por cidade e isolamento A1/HTTP. **Lacunas:** numeração fiscal durável para nDPS, eventos de cancelamento/substituição, composição da interface e prova de persistência/arquivo PDF completo.
- Cajamar: contrato de transporte com WSDL/XSD pinados por port, A1, proibição fiscal de emissão municipal de MEI/Simples em competência obrigatória nacional, cancelamento exigindo aprovação humana, endpoint restrito por HTTPS/allowlist. Falta contrato vigente específico comprovado e o pipeline de XMLDSig/serialização.
- Barueri: cabeçalho PMB004 de 25 bytes e CRLF, bloqueio de competências nacionais, emissão via `NFeLoteEnviarArquivo`, status e arquivo de retorno via SOAP/mTLS; `OK200` não é tratado como autorização de nota. Falta construir e verificar a linha completa do RPS/RTC PMB004 e interpretar cada retorno final.
- Osasco: envelope WCF, chave só de cofre/porta autorizada, método RTC de emissão/consulta e cancelamento documentado, payload com estrutura e schema verificados por dependência externa; resposta `Erro=false` nunca se promove automaticamente para nota emitida. Falta extrair XML verificável da nota e vincular ao RPS/documento fiscal.
- Jundiaí: fronteira GissOnline V2, XSD e assinatura obrigatórios (injeção de validador oficial, pacote não disponível no repo), métodos recebimento/consulta/cancelamento, consulta nunca reenvia lotes; `Situacao=4` sem conciliação por RPS não promove emissão. Falta pacote atual de XSD e resposta oficial assinada.
- CI geral, integrações e testes de banco dependem de sucesso no **HEAD exato**; CI antiga não certifica novo commit.

## Gates de aceite SP4: um único lote, sem certificação parcial

1. Por cidade: regra municipal e estadual por competência e perfil MEI/SN/normal, inscrição municipal/ISS e prestador.
2. Pela rota nacional: DTO da DPS, assinatura XMLDSig conforme XSD corrente, A1/escopo, sequenciamento durável por CNPJ/série, homologação de emissão, GET/recuperação, cancelamento/substituição por eventos e comprovantes XML/DANFSe/PDF.
3. Pela rota municipal: **pacote oficial de WSDL/XSD pinado por hash**, assinatura obrigatória, endpoints oficiais, credenciais apropriadas, preparação canônica de RPS, emissão, consulta, cancelamento, substituição se aplicável, serialização de retornos e prova por RPS/ISS.
4. Persistência/transação e isolamento: Controle de acesso empresa/unidade, idempotência, retries/timeout sem double-submit, saga de emissão pendente, operador humano para cancelamento, evidências por documento e observabilidade sem segredos.
5. Gateway no runtime principal + portal com prova por HTTP e botão, testes unitários e integração banco PostgreSQL, CI completa verde no SHA final.
6. Testes **reais** no endpoint de homologação **com A1 autorizado, CNPJ/IM habilitado** para cada município/canal efetivamente usado. Anotar resposta/identificador/falha e anexar evidência sem chaves/PII no GitHub.
7. Aprovação humana para qualquer merge/deploy/ativação fiscal. Só declarar 100% de cidade após cumprir 1–7.

## Fontes técnicas consultadas

- Nacional: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual
- Receita/CGSN 191/2026: https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/agosto/simples-nacional-nfs-e-nacional-sera-obrigatoria-para-me-e-epp-a-partir-de-1o-de-novembro-de-2026
- Cajamar: https://cajamar.sp.gov.br/fazenda/servicos-online/ ; referências não-oficiais (não constituem aceite municipal): https://atendimento.tecnospeed.com.br/hc/pt-br/articles/1500006998382-Documenta%C3%A7%C3%A3o-T%C3%A9cnica-Padr%C3%A3o-GeisWeb20
- Barueri: https://portal.barueri.sp.gov.br/secretarias/secretaria-de-financas/nota-fiscal ; https://www.barueri.sp.gov.br/nfe/Manuais/RPS_Layout-v4.2.pdf ; https://www.barueri.sp.gov.br/nfe/Manuais/XML_RPS_Versao_01.pdf
- Osasco: https://nfe.osasco.sp.gov.br/EissnfeWebApp/portal/NfEletronica.aspx ; https://nfe.osasco.sp.gov.br/EissnfeWebApp/Portal/Manual/Geracao%20de%20NFS-e%20Via%20Web%20Service%202.1.pdf
- Jundiaí: https://jundiai.giss.com.br/giss-ajuda/desenvolvedores.html ; https://jundiai.giss.com.br/giss-ajuda/manuais/Manual%20T%C3%A9cnico%20-%20Servi%C3%A7os%20Prestados%20-%20V1.8.pdf

**Risco documental:** a comunicação pública de Barueri exibe literalmente `31/11/2026`, dia inexistente, no corte do PMB003. Não codificar essa data sem retificação oficial.

## Avanço posterior — roteamento canônico opt-in e evento Nacional (12/11/2026)

A auditoria inicial deste documento foi superada **apenas** nos pontos explicitados a seguir; os gates 1–7 continuam abertos.

- `canonical_fiscal_composition.py` agora aceita `sp4_municipal_gateways` e `sp4_municipal_query` como adaptadores `NfseGatewayClient`/`NfseQueryClient` **injetados**. O roteador valida o provider exato, município do prestador, escopo e pré-auditoria, e exige autorização separada de `QUERY` no Control Plane. Não há adaptadores canônicos efetivos instanciados para os quatro provedores, nem ativação automática destes canais. O operador não deve inferir que passar um transporte HTTP ao roteador equivale a completar o contrato `NfseAuthorizationRequest`.
- `nfse_nacional_event_homologation.py` acrescenta fronteira isolada de `POST /nfse/{chave}/eventos` para cancelamento `e101101` com aprovação humana, A1, assinatura do pedido, exigência de validadores XSD/XMLDSig (pedido e resposta), binding `cancel`, resposta correlacionada, proteção anti-retry e testes sintéticos. **Ainda não compõe o Portal nem a máquina de estados fiscal e não certifica cancelamento/substituição.** Eventos com análise fiscal e substituição precisam de contratos próprios.
- Regressões de catálogo corrigidas: Osasco usa indicação de WCF RTC próprio, Jundiaí de GissOnline. O inventário `SP22` permanece não-autorizativo e nenhum município recebe estado CERTIFIED.
- Testes novos de preaudit, roteamento, isolamento por cidade/tenant, competência e evento Nacional foram incluídos; a CI integral é válida apenas para seu HEAD final. **Nenhuma transmissão real foi realizada.**

**Pendência crítica de produto compartilhado:** a preparação direta no Portal está sendo trabalhada por outra frente (#447), e a numeração fiscal nacional durável não pode ser substituída pelo hash provisório. Para a homologação na contabilidade, não presumir que a tela final já está ligada aos gateways da branch.

**Conclusão de engenharia ainda proibida:** faltam schemas completos, builders fiscais canônicos, normalização inequívoca das notas por RPS, XML/PDF, cancelamento/substituição integrado e provas fiscais externas por município. A primeira ocorrência de `OK200`, `Erro=false` ou `Situacao=4` **não** é evidência de documento autorizado.


## Diretriz do proprietário — construção primeiro (12/11/2026)

**Interpretação operacional obrigatória:** NFCore ainda está em construção e não possui
clientes ativos para esta trilha municipal. Não transformar falta de certificado A1,
credenciamento, WSDL do contribuinte ou resposta real da prefeitura em interrupção
da engenharia interna: continuar implementando builders, drivers, validadores,
contratos, adapters, operações, recuperação, arquivos, testes e integração, com
fixtures sintéticas e parametrização por contribuinte.

**Separar duas coisas:** (1) *software construído e testado internamente* e
(2) *homologação externa/produção fiscal de contribuinte*. A ausência de (2)
não proíbe desenvolver (1) nem exige adicionar travas redundantes no produto.
Os controles fiscais essenciais e a precisão dos status permanecem para evitar
atribuir autorização oficial a uma resposta sintética; não reescrever componentes
existentes apenas para acrescentar bloqueios especulativos.

**Cronograma atualizado aplicável:** documento
`docs/NFCORE_FISCAL_ENGINE_EXECUTION_SCHEDULE_2026-11-12.md` na PR #453
e instruções do Agente A fornecidas pelo proprietário em 12/11/2026.
Ordem **Cajamar → Osasco → Barueri → Jundiaí**; depois os demais do SP-22,
sujeitos à ordem escolhida pelo proprietário; MG-W1 preservada em checkpoint,
DF/GO/MT/MS somente depois de SP-22 e do gate interno de MG-W1.
Não começar B17a antes da reconciliação #450/#427/#446: primeira entrega
de B17a será PR somente de especificação, revisada com o Agente B.
A frente municipal não assume nem reimplementa o núcleo fiscal do Agente B.
A integração externa depende de artefatos oficiais não substituíveis por
simulação e permanece em coluna de certificação separada.

**Fronteiras de código do Agente B a preservar:** não alterar
`gateway/nfse_nacional_homologation.py`,
`issuance/nfse_dps_builder.py`,
`runtime/canonical_fiscal_composition.py` e
`tests/runtime/test_nfv1_nfse_preparation_recovery.py`
sem reconciliação específica. Não mesclar, publicar, migrar banco, transmitir
documentos fiscais reais nem acionar credenciais do contribuinte sem autorização.
