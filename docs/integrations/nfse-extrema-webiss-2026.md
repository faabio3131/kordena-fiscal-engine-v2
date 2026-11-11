# NFCore — NFS-e Extrema/MG · WebISS 2.02 + RTC (11/11/2026)

**Classificação:** `IMPLEMENTED_NOT_WIRED` / `EXTERNAL_CONTRACT_PENDING`. **Não é homologação, emissão nem certificação completa.**

## Governança consultada

- `AGENTS.md` na `main`: regras fiscais, fail-closed, tenant/unidade, assinatura, aprovação e proibição de merge/deploy automático; cronograma antigo Centro-Oeste preservado, com reconciliação de prioridade MG na PR #423.
- `agentes.md`: unidade de entrega funcional completa, sem stubs para produção, testes E2E e separação de configuração externa da construção interna.
- `docs/NFCORE_NATIONAL_COVERAGE_MASTER_SCHEDULE_2026-11-07.md` e `docs/NFV1_NAT03_MG_AUTHORIZATION_CONTINUITY_2026-11-05.md`: MG ainda não é UF completa.
- A busca recursiva no índice da `main` (1.286 entradas, `82c383bc`) não encontrou um arquivo chamado `EGM` ou `EGM.md`. O EGM citado em outras PRs **não foi declarado lido/executado** nesta entrega. Se for uma regra externa, deve ser anexada/identificada antes da certificação.

## Fontes e contrato municipal verificados

- Portal WebISS de Extrema: https://extremamg.webiss.com.br/ . O aviso público disponibiliza documentação específica de WebService para IBS/CBS, XSDs, amostras XML e orientação de homologação no menu **Manuais → Nota Fiscal de Serviços Eletrônica**. Os bytes do pacote oficial RTC 2026 ainda não foram obtidos/pinados.
- Serviço oficial público: https://extremamg.webiss.com.br/ws/nfse.asmx . **Endereço de produção; nunca usar como ambiente de testes.**
- Lista pública de métodos do serviço: `GerarNfse`, `RecepcionarLoteRps`, `RecepcionarLoteRpsSincrono`, `ConsultarLoteRps`, `ConsultarNfsePorRps`, `ConsultarNfsePorFaixa`, `ConsultarNfseServicoPrestado`, `ConsultarNfseServicoTomado`, `CancelarNfse` e `SubstituirNfse`.
- Exemplo ASMX da consulta: https://extremamg.webiss.com.br/ws/nfse.asmx?op=ConsultarNfseServicoPrestado . SOAP 1.1, `SOAPAction: "http://nfse.abrasf.org.br/ConsultarNfseServicoPrestado"`, campos `nfseCabecMsg` e `nfseDadosMsg` sem namespace; saída em `outputXML`.
- Os nomes das raízes XML ABRASF 2.02 são **hipóteses de contrato sob validação**, não evidência de conformidade RTC 2026 de Extrema. A configuração deve recusar XSD 2.03 genérico e casar cada raiz com o XSD municipal congelado.

## Implementado nesta branch isolada

1. `gateway/nfse_webiss_extrema.py`: catálogo imutável das dez operações, preparação de SOAP 1.1, cabeçalho ABRASF 2.02, validação XSD hash-pinned injetada da configuração de engenharia, verificação de raiz, identidade do emitente/tomador e município IBGE `3125101`, limite XML, bloqueio DTD/XXE e resposta estrita (SOAP Fault e respostas ambíguas são rejeitadas).
2. `gateway/nfse_webiss_extrema_transport.py`: transporte mTLS sem redirecionamentos, com A1 recuperado do Vault por escopo após validações, timeout, limite de resposta, erro sanitizado e **sem retry de mutações**; somente mediante cadastro prévio de endpoint de homologação com referência de evidência. O host público de produção é bloqueado.
3. Testes dirigidos sintéticos do contrato SOAP, cenários negativos, tenant/emitente, alvo seguro, mTLS/PKCS#12 e limites. **O XSD de teste é deliberadamente permissivo, não o oficial.**
4. A leitura da resposta **não** cria `AuthorizationStatus.AUTHORIZED`; correlação da NFS-e com intenção fiscal, documento, RPS, emitente, ambiente, protocolo e efeitos de cancelamento/substituição continua com a aplicação canônica.

## Bloqueios e atividades internas ainda obrigatórias

- **Contrato oficial faltante:** download autenticado ou público do manual WebISS Extrema RTC 2026, XSDs/exemplos/XML hash-pinned, namespace/ordem de tags de IBS/CBS, versões de cabeçalho, endpoints verdadeiros de homologação, identidade do serviço e raízes de todas as dez operações. Nunca sintetizar arquivos fiscais oficiais.
- **Integração de aplicação ainda pendente:** ligar o adapter ao ProviderRegistry/BindingResolver, pré-auditoria, gerador ABRASF 2.02/RTC, Vault A1 e assinador canônico de RPS/Lote/Cancelamento/Substituição (com verificação XMLDSig de verdade, não somente presença estrutural).
- **Jornada ainda pendente:** comando autorizado → persistência/outbox → transporte → retorno correlacionado → consulta antes de retransmitir → arquivo histórico → status/erros → API/Web; operações não suportadas contratualmente devem ser `NOT_APPLICABLE_VERIFIED`.
- **Certificação ainda pendente:** fixture e XSD reais, golden XMLs assinados, todos os dez métodos aplicáveis, RTC, RBAC, isolamento multi-tenant, idempotência/concurrency, transação e recuperação após falha, migrations, regressão completa, Ruff, Mypy, Pytest e CI no SHA exato; homologação externa somente com CNPJ/A1 habilitados e aprovação.
- **Sem mudanças** em `AGENTS.md`, EGM não localizado, cronogramas nacionais, PRs #423/#427/#422, branch `production`, Contabo, segredos reais, banco ou autorização fiscal.

## Decisão de gate

Esta branch constitui **base interna de contrato/transporte**, sem exposição operacional na aplicação. Não integrar nem marcar Extrema `INTERNAL_COMPLETE` até fechar os itens de código acima e os testes no HEAD; não implantar nem transmitir. Atualizar o ledger nacional em PR de reconciliação coordenada com a PR #413 após certificação técnica.
