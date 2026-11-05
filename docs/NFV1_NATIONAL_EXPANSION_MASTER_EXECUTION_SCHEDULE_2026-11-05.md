# FM NFCORE V1 — Cronograma Mestre de Construção Nacional por Módulos Completos

**Documento:** NFV1-NAT-SCHEDULE-001  
**Data:** 05/11/2026  
**Status:** PROPOSTA DE PLANO, sem módulos implementados/certificados nesta nova frente  
**Arquitetura vinculante proposta:** `docs/NFV1_NATIONAL_EXPANSION_MASTER_ARCHITECTURE_2026-11-05.md`  
**Base:** main CURRENT; PR #355 em trilha independente e não mergeada  
**Autorização vigente:** planejar; **não** promover `main`, `production`, migrations produtivas, DNS ou emissões oficiais por esta PR.

## 1. Definição de módulo completo (não fragmentar)

Um módulo `NAT-UF-XX` só recebe **INTERNAL_COMPLETE** quando NF-e 55, NFC-e 65 e o fluxo NFS-e de sua primeira cidade-alvo possuem: contrato oficial e XSD auditados; matriz de capacidades por operação; binding governado por UF/modelo/município; regras específicas do emissor; emissão/preparo/XMLDSig; adaptador real; consulta, cancelamento, inutilização quando aplicável; CSC/QR para NFC-e; NFS-e DPS/RPS conforme contrato municipal; histórico, XML/PDF; RBAC, isolamento tenant/unidade, idempotência, reprocessamento; integração Web; testes unit/integration/PostgreSQL e CI; observabilidade e runbook. Ausência de contrato municipal confirmado é **BLOCKER explícito**, não motivo para marcar o módulo como completo.

`EXTERNAL_HOMOLOGATED` requer transmissão e resposta oficial `tpAmb=2` por estabelecimento elegível, tipo de documento e operação, com evidência, sem compartilhamento de segredos no repositório. `PRODUCTION_APPROVED` requer autorização humana e controles operacionais. A execução pode evoluir internamente com mocks confiáveis enquanto a homologação real estiver bloqueada, mas os estados são distintos.

**Regra de fluxo:** não declarar a UF completa por um único serviço verde, por apenas NF-e, nem pelo uso de SVRS; versionar e reutilizar o mesmo conector para múltiplas UFs quando o contrato é idêntico. Nenhum fallback silencioso entre fiscal 55/65/serviços ou produção/homologação.

## 2. Prioridade executiva e backlog nacional

**Fase A — Primeiro lote obrigatório (sequência estrita):**

| Ordem | ID | UF | Primeiro município NFS-e para contrato/piloto | Particularidades prioritárias |
|---:|---|---|---|---|
| 1 | NAT-UF-MG | Minas Gerais | Belo Horizonte (3106200) | NF-e e NFC-e autorizadores próprios, vigência de endpoints distinta, competência ISS |
| 2 | NAT-UF-RJ | Rio de Janeiro | Rio de Janeiro (3304557) | NF-e via SVRS conforme catálogo atual; verificar NFC-e separadamente; NFS-e municipal |
| 3 | NAT-UF-PR | Paraná | Curitiba (4106902) | NFC-e própria, CSC e credenciamento estadual; NF-e SEFA/PR e serviço municipal |
| 4 | NAT-UF-MT | Mato Grosso | Cuiabá (5103403) | NF-e própria e NFC-e própria; CSC/QR e piloto NFS-e |
| 5 | NAT-UF-MS | Mato Grosso do Sul | Campo Grande (5002704) | NF-e/NFC-e próprias; credenciamento e NFS-e municipal |

**Importante:** município inicial é alvo de **pesquisa e comprovação**, não declaração de provedor integrado, nem garantia de emissão. Municípios adicionais são inseridos por configuração governada se o adaptador/contrato já estiver certificado.

**Fase B — Demais estados, mantendo módulos completos por UF e sem atalhos de homologação:**

| Ordem | ID | UF | Cidade inicial proposta |
|---:|---|---|---|
| 6 | NAT-UF-RS | Rio Grande do Sul | Porto Alegre |
| 7 | NAT-UF-SC | Santa Catarina | Florianópolis |
| 8 | NAT-UF-ES | Espírito Santo | Vitória |
| 9 | NAT-UF-GO | Goiás | Goiânia |
| 10 | NAT-UF-DF | Distrito Federal | Brasília |
| 11 | NAT-UF-BA | Bahia | Salvador |
| 12 | NAT-UF-PE | Pernambuco | Recife |
| 13 | NAT-UF-CE | Ceará | Fortaleza |
| 14 | NAT-UF-PA | Pará | Belém |
| 15 | NAT-UF-AM | Amazonas | Manaus |
| 16 | NAT-UF-MA | Maranhão | São Luís |
| 17 | NAT-UF-PB | Paraíba | João Pessoa |
| 18 | NAT-UF-RN | Rio Grande do Norte | Natal |
| 19 | NAT-UF-PI | Piauí | Teresina |
| 20 | NAT-UF-AL | Alagoas | Maceió |
| 21 | NAT-UF-SE | Sergipe | Aracaju |
| 22 | NAT-UF-TO | Tocantins | Palmas |
| 23 | NAT-UF-RO | Rondônia | Porto Velho |
| 24 | NAT-UF-AC | Acre | Rio Branco |
| 25 | NAT-UF-AP | Amapá | Macapá |
| 26 | NAT-UF-RR | Roraima | Boa Vista |

**SP (UF 27):** já é a base atual do produto, com R16 22 municípios **em PR #355 e não homologada globalmente**. Mantém `NAT-UF-SP-RECONCILE` para integrar a mesma matriz nacional, corrigir lacunas e certificar; não reconstruir SP nem considerá-la completa por ter 22 entradas consultivas.

A ordem B é uma **decisão de priorização inicial**, ajustável formalmente por critério de mercado/riscos antes de iniciar novo lote. Nenhuma duração em dias foi arbitrada sem estimar capacidade de engenharia e dependências oficiais.

## 3. Plataforma transversal (uma vez, antes da expansão de UFs)

| Bloco | Escopo de entrega | Critérios objetivos |
|---|---|---|
| NAT-00 | Auditoria de merge/CI PR #355, main e production; mapa de impacto; congelar escopo | CURRENT SHA/PR/CI confirmado, sem retrabalho de SP |
| NAT-01 | Arquitetura de autorizações por UF/modelo/município; contrato `ProviderBinding` versionado; catálogo de fontes | ADR aprovado, rollback/compatibilidade, fail-closed |
| NAT-02 | Contabilidade multicliente + estabelecimentos matriz/filial com CNPJ/IE/IM por unidade | RBAC/revogação/tenant isolation tests, nenhuma segunda auth |
| NAT-03 | Catálogo fiscal versionado de autorizadores/serviços/endpoints por `UF + modelo + tpAmb + operação` | Provedores de teste configuráveis, endpoint oficial com fonte/proveniência e vigência |
| NAT-04 | Adaptador comum NF-e/NFC-e e camada de XMLDSig, XSD, operações e eventos; divergências por família técnica | Golden cases 55/65 e contratos SOAP 1.2 por grupo; sem emissão simulada tratada como real |
| NAT-05 | CSC/QR NFC-e por UF e escopo, credenciamento, contingência autorizada | Sem CSC real em logs, verificação QR e testes de não downgrades |
| NAT-06 | NFS-e SEFIN Nacional + resolvedor municipal governado; competência ISS; adapters reutilizáveis | DPS/RPS assinada conforme fonte; ADN separada de autorização e nunca fallback automático |
| NAT-07 | Jornada Web completa multiempresa/filial, emissão 55/65/serviço, XML/PDF/erro/recovery | Chromium E2E, mobile, RBAC, CSRF, cookies, cenários de rejeição sem 500 |
| NAT-08 | Numeração/idempotência/recuperação, PostgreSQL concorrente, fila/outbox, telemetria | 50/100 concorrentes em ambiente isolado; sem duplicidades, locks ou perdas; P95 por rota |
| NAT-09 | Pipeline de certificação por UF com evidência, homologação e liberação governadas | Automação de gates CI, matrizes e status por documento e operação; documentação operacional |

**Dependências:** NAT-00 → NAT-01 → NAT-03/04/06; NAT-02 e NAT-07 podem construir internamente em paralelo após contratos; NAT-05 depende de NAT-03/04; NAT-08/09 entram antes do primeiro módulo ser considerado completo. Não iniciar adaptação de UF por código fixo como atalho.

## 4. Template executável de **cada módulo estadual**

Cada `NAT-UF-{XX}` deve abrir seu próprio tracker com as tarefas abaixo; os IDs não se sobrepõem aos 59 IDs históricos:

| Subbloco | Contrato e implementação | Gate |
|---|---|---|
| T01 | Dossiê oficial NF-e/NFC-e/NFS-e e municípios; WSDL/XSD/NT/credenciamento, hashes, vigência | Fatos citados e fonte congelada; lista de capacidades sustentada |
| T02 | Perfil fiscal do estabelecimento, UF/IBGE/IE/IM, unidade e acesso contábil | Testes RBAC, pertencimento, matriz/filial, sem spoof |
| T03 | Binding de autorizadores por UF/documento/operação/ambiente, readiness e endpoint | Compatibilidade com registro canônico; nenhuma UF hardcoded no browser |
| T04 | NF-e 55: preparar, assinar, autorizar, consultar, cancelar, inutilizar (onde cabível), recuperar | XSD/XMLDSig, mTLS, XML nfeProc, DANFE, idempotência, CI |
| T05 | NFC-e 65: serviços próprios/SVRS se oficial, CSC, QR, eventuais contingências | XML, URL QR, regras modelo 65, credenciamento, PDF/recuperação, CI |
| T06 | NFS-e: cidade-piloto, competência/ISS, RPS/DPS, assinatura, autorização, eventos | Contrato municipal/SEFIN oficial e XSD; nada de provider presumido |
| T07 | Portal: cadastrar empresa/filiais e operar 55/65/serviço por unidade, histórico, downloads | E2E web/responsividade/401/403/404/validações/estados |
| T08 | Carga, isolamento e recuperação em PostgreSQL e concorrência 50/100; alertas | Benchmark reproduzível, sem deadlock/colisão, telemetria |
| T09 | PR + CI + segurança, revisão, evidência interna e merge quando autorizado | Gate positivo no HEAD, evidência persistente, pós-merge |
| T10 | Homologação com contribuinte elegível, serviços oficiais e Go/No-Go humano | tpAmb=2 comprovado, serviços e CNPJ/UF documentados, produção separada |

**Granularidade:** T01..T09 podem originar PRs pequenas sequenciais, auditáveis e reversíveis. Somente ao encerrar **todos** T01..T09 com provas se marca `INTERNAL_COMPLETE`; T10 governa externamente. Se um adaptador comum já foi certificado em MG e é realmente reutilizável no RJ, criar **configuração e testes exclusivos RJ**, não copiar o código.

## 5. Ondas e paralelismo permitidos

### Onda 0 — Preparar a arquitetura universal
**WP NAT-00..NAT-09**. Resolver contratos, segurança e integração do SP R16, congelar política de configuração; executar golden cases multi-tenant e endpoint registry. Critério: nenhuma autoridade concorrente e testes de módulo transversal verdes.

### Onda 1 — Minas Gerais (NAT-UF-MG)
NF-e MG → NFC-e MG → NFS-e Belo Horizonte → Web/archives → cargas/CI → certificação interna → homologação oficial. A equipe pode pesquisar RJ/PR em paralelo, mas **não dar módulo MG como concluído enquanto uma das três jornadas internas estiver pendente**.

### Onda 2 — Rio de Janeiro (NAT-UF-RJ)
Reutilizar transporte SVRS quando oficial para NF-e, verificar autorizações NFC-e próprias e municipal Rio de Janeiro; testar todos os fluxos da filial RJ sem contaminação da unidade MG.

### Onda 3 — Paraná (NAT-UF-PR)
Configuração NF-e; NFC-e exigindo CSC/credenciamento específicos PR; NFS-e Curitiba conforme contrato válido; idempotência, portal, XML/DANFE, CI.

### Onda 4 — Mato Grosso (NAT-UF-MT)
NF-e/NFC-e MT, CSC/QR, NFS-e Cuiabá, controle de competência; testes e liberação.

### Onda 5 — Mato Grosso do Sul (NAT-UF-MS)
NF-e/NFC-e MS, NFS-e Campo Grande; validação credenciamento, testes e liberação.

### Ondas 6–26 — Demais UFs
Concluir na ordem da tabela B (RS → RR). Usar a mesma template T01..T10 e status técnico. Reutilizar os adaptadores oficiais SVRS/SVAN quando o contrato é igual; não presumir que NFC-e ou NFS-e compartilham o autorizador.

### Onda final — Certificação nacional consolidada
Teste da contabilidade com clientes simultâneos em pelo menos MG/RJ/PR/MT/MS/SP e depois regressão pelas 27 UFs: CNPJ/IE/IM corretos, emissão e recuperação independente, certificados isolados, configurações auditadas, capacidade por plano, stress SQL, backup/recovery, responsividade, segurança, comercial e aprovação humana.

## 6. Registro de execução e evidência por tarefa

Cada registro no ledger deve conter:

`ID | UF | documento | operação | estado CURRENT | TARGET | fonte oficial + versão/hash | branch | PR | SHA | testes | CI | governança | Web/E2E | ambiente | homologação externa | riscos | blocker | próximo passo`.

Estados permitidos: `NOT_STARTED`, `AUDITED`, `DESIGNED`, `IMPLEMENTING`, `INTERNAL_TESTED`, `INTERNAL_COMPLETE`, `EXTERNAL_BLOCKED`, `EXTERNAL_HOMOLOGATED`, `PRODUCTION_APPROVED`, `PRODUCTION_LIVE`, `REGRESSION`. Falta de permissão oficial/certificado real = `EXTERNAL_BLOCKED`, não prova de falha de código nem autorização de bypass.

## 7. Gates de aceitação e saída de módulo

**Gate A — código:** alterações mínimas na arquitetura canônica, testes dirigidos, Ruff, Mypy strict, unit, integration, PostgreSQL, migrations em base descartável, lint/typecheck/build frontend, Chromium E2E, Docker e security pass.

**Gate B — domínio:** XSD/XMLDSig, competência e regras normativas versionadas, autorização/consulta/cancelamento/inutilização, idempotência e reconciliação, CSC/QR quando cabível, arquivos XML/PDF legítimos.

**Gate C — isolamento:** acesso contábil cliente autorizado, isolamento tenant/unidade/ambiente, step-up/role quando aplicável, sem vazamento certificado/CSC/CPF/CNPJ em telemetria.

**Gate D — operação:** medição interna e via proxy, P50/P95/P99 sob 50/100 concorrentes, segurança de pool e numeração, SLO, alertas/runbooks, backup/restore e plano de rollback.

**Gate E — externo:** evidência real tpAmb=2 com credencial elegível, aprovação jurídica/fiscal necessária e Go/No-Go humano para produção.

Não abrir T10 ou marcar uma UF `PRODUCTION_LIVE` por build, Docker healthy ou HTTP 200. Contabo permanece a única infraestrutura operacional atual; Railway e provedores históricos não retornam.

## 8. Capacidade e prazo

Este plano **não fixa promessa de datas** sem medir esforço de infraestrutura/contratos. Cada módulo recebe estimativa apenas após T01 (complexidade por autorizador, documentação municipal, disponibilidade de homologação, NFS-e própria versus SEFIN, parceria contábil e cobertura E2E). A ordem é prioridade executiva, não SLA automático.

Indicadores de acompanhamento: % módulos T01..T09 certificados, cobertura de operações por documento/UF, rotas com fonte oficial válida, execução de E2E, taxa de rejeição por provedor, latência, segurança e % dependências externas concluídas.

## 9. Próxima execução autorizável

1. Reconciliar `main`, PR #355 e CI no HEAD (separar documentação desta execução de código).
2. Validar e aprovar ADRs NAT-01..02, especialmente representação de contabilidade multicliente e competência NFS-e.
3. Criar o primeiro WP em branch de implementação `feat/nfcore-national-routing-core`, sem duplicar o resolvedor `DurableProviderBindingResolver`.
4. Pesquisar contratos oficiais MG NF-e/NFC-e e Belo Horizonte NFS-e; congelar fontes e testar.
5. Avançar internamente pelas T01..T09 até `INTERNAL_COMPLETE`; pedir autorização específica antes de mudanças produtivas/externas.

**O plano não altera a autorização de merge/deploy de outras PRs.**
