## CURRENT reconciliado — continuidade 05/11/2026

Este registro prevalece sobre o snapshot de planejamento abaixo, sem promover estados globais.

- Repositório atual: faabio3131/nf-core-v001; main 3f56084041fc9cd441af9a61dcc9532ba6090a85.
- PRs #355/#356/#359 MERGED; #358 OPEN, destino production, sem merge nesta execução.
- PR #360 OPEN/DRAFT, base deste incremento feedf8b41085914b831c9585bec1b34675742008:
  inventário prioritário, bindings negativos e catálogo MG 55/65; Governança #1120 SUCCESS;
  CI #1689 ainda em execução na consulta inicial. Não presumir certificação.
- Branch deste incremento: feat/nfcore-nat03-mg-provenance, baseada no HEAD da #360.
- NAT-00 AUDITED (reconciliação interna; production não promovida).
- NAT-01 IMPLEMENTING: pesquisa/inventário em #360; contrato/ADRs globais ainda pendentes.
- NAT-03/04 IMPLEMENTING: autorização MG NF-e 55 reutiliza transporte SOAP e Vault;
  requer validador XSD confiável. Não registra provider/binding nem modifica runtime.
- NAT-UF-MG IMPLEMENTING/PARTIAL; RJ/PR/MT/MS sem módulos internos completos.
- Detalhes, mapa de impacto e critérios:
  docs/NFV1_NAT03_MG_AUTHORIZATION_CONTINUITY_2026-11-05.md.
- Ruff global PASS; Mypy direcionado PASS. Mypy global Windows encontrou 8 erros
  em 5 arquivos fora desta mudança: APIs POSIX ausentes no Windows e dependência
  brazilfiscalreport.danfe ausente. Não desabilitar verificações; CI Linux é gate obrigatório.
- Nenhuma transmissão fiscal real, credencial nova, migration, deploy ou homologação.
- Próxima ação: certificar CI desta candidata; congelar XSD/WSDL reais e composição
  com autoridade XmlSchemaValidator; depois demais operações MG, NFC-e e NFS-e BH.
- Merge main e promoção production aguardam autorização específica.

---

# NFCore National Expansion — Ledger de Estado e Continuidade

**Documento:** NFV1-NAT-LEDGER-001  
**Data:** 2026-11-05  
**Status:** planejamento documental, NÃO certificação técnica.  
**Fonte superior:** GitHub current, código, CI e evidência.  
**Escopo:** `docs/NFV1_NATIONAL_EXPANSION_MASTER_ARCHITECTURE_2026-11-05.md` + `docs/NFV1_NATIONAL_EXPANSION_MASTER_EXECUTION_SCHEDULE_2026-11-05.md`.

## Checkpoint atual

- Repositório: `faabio3131/nf-core-v001`.
- Branch deste planejamento: `docs/nfcore-national-fiscal-expansion-architecture-20261105`; baseada na `main` e sem alterações de runtime.
- PR #355: roteamento municipal SP em branch separada, em Draft na última checagem; **não absorvida neste planejamento**.
- Production/Contabo: nenhuma modificação por esta entrega.
- Cuidado: prontidão multi-tenant, modelos/UF na arquitetura **não** são homologação externa.
- Próximo bloco: **NAT-00**, reconciliação PR #355 + contratos canônicos + bootstrap de fontes oficiais MG.
- Go/No-Go: aprovação de arquitetura e cronograma pelo Diretor antes de implementação definitiva; aprovação específica para deploy/migrations/credenciais e homologação oficial.

## Ledger plataforma

| ID | CURRENT | TARGET | Status | Dependência | Evidência exigida |
| --- | --- | --- | --- | --- | --- |
| NAT-00 | PR #355 não integrada no momento da leitura | conciliar PR, main, production, CI | NOT_STARTED | CI + revisão | SHA e diff atuais, CI, decisões |
| NAT-01 | ProviderBinding/Resolver canônicos | contrato nacional versionado e governado | NOT_STARTED | NAT-00 | ADR+tests sem dupla autoridade |
| NAT-02 | tenant/unidade e perfil fiscal | vínculo escritório↔clientes e matriz/filial | NOT_STARTED | NAT-00 | RBAC, revogação, testes isolamento |
| NAT-03 | routing persistente por jurisdição | catálogo oficial versionado de endpoints | NOT_STARTED | NAT-01 | fontes/proveniência/approval |
| NAT-04 | gateway NF-e SP / modelos canônicos | adaptadores reutilizáveis UF/modelo/operação | NOT_STARTED | NAT-03 | XSD/SOAP/assinatura/ops |
| NAT-05 | Vault A1/CSC parcialmente existente | CSC/QR NFC-e governados por UF | NOT_STARTED | NAT-03/04 | QR oficial, sem logs de segredo |
| NAT-06 | NFS-e nacional + SP em construção | competências e famílias municipais | NOT_STARTED | NAT-01/03 | contratos municipais/nacionais |
| NAT-07 | Portal fiscal parcial | jornadas Web completas 55/65/serviço | NOT_STARTED | NAT-02/04/06 | Chromium+RBAC+download |
| NAT-08 | CI e idempotência existentes | stress PostgreSQL/recovery/observabilidade | NOT_STARTED | NAT-04/05/06 | 50/100, locks, métricas |
| NAT-09 | governança e CI existentes | certificação/gates por UF/doc/ambiente | NOT_STARTED | NAT-00..08 | ledger e gates completos |

## Ledger UF — todas as 27 unidades federativas

`NOT_STARTED` indica que **a nova expansão nacional** ainda não foi executada, não nega componentes anteriores ou trabalho da PR #355.

| Ordem | ID | Status nacional | Bloqueio ou próxima ação |
| ---: | --- | --- | --- |
| 0 (reconciliar) | NAT-UF-SP-RECONCILE | NOT_STARTED | revisar PR #355, não duplicar código |
| 1 | NAT-UF-MG | NOT_STARTED | contratos oficiais MG NF-e/NFC-e e Belo Horizonte NFS-e |
| 2 | NAT-UF-RJ | NOT_STARTED | SVRS NF-e e NFC-e RJ independente; NFS-e Rio |
| 3 | NAT-UF-PR | NOT_STARTED | PR NF-e/NFC-e, CSC/credenciamento, Curitiba |
| 4 | NAT-UF-MT | NOT_STARTED | MT NF-e/NFC-e, CSC/QR, Cuiabá |
| 5 | NAT-UF-MS | NOT_STARTED | MS NF-e/NFC-e, Campo Grande |
| 6 | NAT-UF-RS | NOT_STARTED | Porto Alegre, autorizador próprio |
| 7 | NAT-UF-SC | NOT_STARTED | Florianópolis; SVRS/contratos atuais |
| 8 | NAT-UF-ES | NOT_STARTED | Vitória; SVRS/contratos atuais |
| 9 | NAT-UF-GO | NOT_STARTED | Goiânia |
| 10 | NAT-UF-DF | NOT_STARTED | Brasília |
| 11 | NAT-UF-BA | NOT_STARTED | Salvador |
| 12 | NAT-UF-PE | NOT_STARTED | Recife |
| 13 | NAT-UF-CE | NOT_STARTED | Fortaleza |
| 14 | NAT-UF-PA | NOT_STARTED | Belém |
| 15 | NAT-UF-AM | NOT_STARTED | Manaus |
| 16 | NAT-UF-MA | NOT_STARTED | São Luís; SVAN NF-e |
| 17 | NAT-UF-PB | NOT_STARTED | João Pessoa |
| 18 | NAT-UF-RN | NOT_STARTED | Natal |
| 19 | NAT-UF-PI | NOT_STARTED | Teresina |
| 20 | NAT-UF-AL | NOT_STARTED | Maceió |
| 21 | NAT-UF-SE | NOT_STARTED | Aracaju |
| 22 | NAT-UF-TO | NOT_STARTED | Palmas |
| 23 | NAT-UF-RO | NOT_STARTED | Porto Velho |
| 24 | NAT-UF-AC | NOT_STARTED | Rio Branco |
| 25 | NAT-UF-AP | NOT_STARTED | Macapá |
| 26 | NAT-UF-RR | NOT_STARTED | Boa Vista |

## Registro obrigatoriamente preenchido a cada bloco

```
Data:
ID:
CURRENT branch + SHA:
TARGET:
Fontes oficiais + URL + data + versão/hash:
Escopo congelado:
Dependências e áreas protegidas:
Alterações de domínio/application/infra/DB/API/Web:
Testes Ruff/Mypy/pytest/postgres/frontend/Chromium/Docker/security:
CI/Governança (run e conclusion):
PR:
Merge (quando autorizado):
Smoke/homologação externa (se aplicável):
Riscos/blockers:
Próximo bloco:
```

**Nunca marcar CHECKED/CONCLUÍDO apenas por documentação, PR aberta, health 200 ou teste sintético.**

## NAT-03/04 — evidência incremental na PR #361

- Branch: feat/nfcore-nat03-mg-provenance. Primeiro commit a027b967c26af6869f3cb21f3be97df055653628.
- PR base #360: CI #1689 SUCCESS e Governança #1120 SUCCESS confirmadas.
- PR #361: Governança #1121 SUCCESS no primeiro commit; CI #1690 iniciada no SHA.
- Regressão local do primeiro incremento: 178 PASS; 18 testes MG PASS; Ruff global e Mypy direcionado PASS.
- Segundo incremento: download oficial PL_010g v1.03, cinco XSD NFe exatos, manifesto com hash,
  loader offline via SchemaResource/SchemaSet/XmlSchemaValidator, composição explícita MG com
  validação real da NFe assinada e negativa de XML incompleto antes de transporte.
- Testes XML + transporte MG após o incremento: 34 PASS; Ruff global PASS; Mypy dos dois módulos PASS.
- Zip original: b329ecbe7e4c05a41bfbc1527f105defb7047328acfeada7c77e1666da485eaf.
- Limite: não contém schema completo de envelope/eventos/WSDL; não representa vigência homologada,
  golden case autorizado, provider ativado, tributação/RTC certificada ou integração estadual completa.
- Evidência final de SHA/CI e packaging: registrar na PR #361; estados globais permanecem IMPLEMENTING.
- Próximo bloco: pacote completo enviNFe e operações, vigência por tpAmb e golden cases oficiais MG;
  em seguida NFC-e MG e NFS-e BH, depois RJ → PR → MT → MS.

### NAT-04 — incompatibilidade de assinatura identificada e correção MG

O XMLDSig do pacote oficial exige RSA-SHA1/SHA1; default anterior gera SHA256.
Perfil explícito NFE4_OFFICIAL_RSA_SHA1 adicionado ao assinador existente e
selecionado apenas no alvo MG homologação. Signature validada contra XSD real
e verificada criptograficamente em teste. Default SP e eventos não foram alterados;
sua compatibilidade oficial permanece PENDÊNCIA, sem homologação declarada.
Wheel e hashes exatos dos cinco XSD no índice/distribuição PASS.
Mypy dirigido de três módulos PASS. Não promover estados globais.

Regressão final do segundo incremento: **196 PASS em 60,31s**, zero falhas,
abrangendo XML, gateways, control_plane e A1 sintético. Ruff global PASS,
Mypy dirigido PASS, plano 59 IDs PASS. CI Linux no SHA final continua gate pendente.

## Continuidade MG — branch feat/nfcore-mg-lifecycle-20261105

Base 7739fd1587f2cb59f07032523b282c218da6a210, PR #361, CI #1691 e Governança #1122 SUCCESS.
CURRENT main permanece 3f56084041fc9cd441af9a61dcc9532ba6090a85.
Escopo NAT-03/04 / NAT-UF-MG-T03/T04 parcial:
consulta, cancelamento e inutilização MG55 no transporte compartilhado, XSD
offline completo de operações/envelope e verificação criptográfica após SOAP.
Snapshot interno composto MG_LIFECYCLE_20261105 possui fontes e hashes por arquivo;
não representa homologação oficial ou vigência aprovada por contribuinte.
44 testes dirigidos de operações/schema passaram antes da regressão ampliada.
Teste positivo: NF-e sintética completa → assinatura → XSD enviNFe → SOAP com
digest/assinatura verificados → resposta local → nfeProc validado por XSD.
Bugs de causa raiz corrigidos: literal CONSULTAR, SOAPAction e namespaces SOAP
que alteravam a canonicalização. Detalhes e gaps internos:
docs/NFV1_MG_LIFECYCLE_CONTINUITY_2026-11-05.md.
Estados globais NAT-UF-MG e transversais continuam IMPLEMENTING.
Próximo bloco: runtime governado e preparação/recuperação Web; resolver ano explícito
de inutilização, seguir NFC-e MG e NFS-e BH antes de promover MG como completa.
PR/SHA/CI final devem constar na PR deste incremento. Sem merge/deploy nesta execução.

Gate local da continuidade MG: **265 PASS em 97,55s**; Ruff global, Mypy dirigido
(cinco módulos), plano de 59 tarefas e validação BUILD PASS. Wheel construída.
Cenário positivo de NF-e completa assinada e nfeProc validado é sintético e
comprova contrato estrutural/criptográfico; não comprova tributação ou homologação.


## NAT-UF-MG-T04 — consulta NF-e 55 na composição canônica

Em 05/11/2026, `main` estava em `b1769429d651ca58c94745904ea7378693b55652` e
`production` em `a2efbe3242be1e0569fa6513020458e920badff5`, com #362 e #358
integradas em suas respectivas bases. A última promoção tinha CI e Governança verdes.
Branch do incremento `feat/nfcore-mg-runtime-pilot`. SHA e checks na PR da branch.

A consulta direta e o cliente de consulta usado na recuperação de transmissão incerta
passam pelo gateway MG somente para NF-e 55 de homologação com vínculo persistente
habilitado para tenant, unidade, ambiente, UF e operação `query`, com provider
`sefaz-mg-homologacao-nfe4`. A fronteira usa o resolvedor durável, o Vault por escopo
e emitente e o adaptador MG com os XSD oficiais já congelados. O incremento cobre
consulta interna, com o caminho legado de SP e a injeção de gateways preservados.

Gates locais com 140 testes direcionados, Ruff global, Mypy dos módulos de aplicação
e composição e os dois validadores de governança. O teste novo usa SQLite migrado,
certificado A1 sintético, XSD real e resposta SOAP local. Exercita bloqueios antes
do Vault e transporte e uma consulta aceita com o vínculo correto.
A prova ponta a ponta autenticada em ambiente publicado e a homologação oficial
permanecem pendentes.

Próximo bloco interno de MG inclui seleção governada para autorização e cancelamento,
preparação Web, emissor e ano explícitos na inutilização, NFC-e MG e NFS-e de Belo
Horizonte. Em seguida, RJ, PR, MT e MS com seus municípios-piloto e expansão pelas
demais UFs e municípios. NAT-UF-MG permanece em implementação.


### NAT-UF-MG-T04 — autorização de NF-e 55 preparada

A PR #364 registrou CI e Governança verdes em a25e0d7 antes deste incremento.
A composição canônica seleciona MG para autorização somente com o vínculo
persistente da operação authorize. A seleção ocorre antes de iniciar a
transmissão durável. O gateway confere XSD, referência, algoritmos,
digest, assinatura e correspondência com o certificado A1 do Vault antes do
transporte. A preparação arquivada permanece no formato existente e a
recuperação consulta o autorizador com seu próprio vínculo.

A prova interna usa documento previamente assinado, SQLite migrado e
resposta SOAP local. A jornada de criação e preparação pelo Portal, o
teste autenticado em ambiente publicado e a homologação oficial permanecem
pendentes. As evidências de CI para o novo SHA estão na PR #364.
