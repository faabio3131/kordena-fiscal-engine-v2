# NFCore — handler fiscal canônico via factory pós-composição (04/11/2026)

## CURRENT verificado

- Repositório: `faabio3131/nf-core-v001`, base `main@16b320e41726e846ac3cf1ffb753b566e979842b`.
- O `runtime/api.py` inicializava o PostgreSQL e montava `FiscalApplicationService` na composição durável, mas somente aceitava um mapa de handlers pré-montado, criado **antes** de o serviço aplicativo existir.
- `build_provider_operation_handlers` já é a autoridade canônica de query, cancelamento, inutilização, emissão preparada e reconciliação; não foi duplicado.

## Delta implementado (CURRENT → TARGET)

- `build_postgres_runtime_composition` passa a aceitar uma **factory opcional explicitamente injetada**, avaliada exatamente após instanciar o mesmo `FiscalApplicationService(database)` e antes de criar o `CanonicalFiscalOperationPath`.
- `RuntimeApi` e `create_runtime_app` propagam esse contrato sem descoberta de segredo, provider ou permissões por ambiente.
- É proibido fornecer factory e mapa direto ao mesmo tempo; retorno inválido ou erro de configuração torna composição indisponível, em vez de criar fallback ou handler sintético.
- `queryArchiveReference` permanece read-only e é incluído pelo mesmo mecanismo canônico.
- O wiring legado com mapa explícito permanece compatível.

## Evidência/aceite

- Regressões: mesma instância de `FiscalApplicationService` passada ao executor, operações do adapter canônico injetadas sem segunda persistência, bloqueio HTTP anônimo, runtime com dependência duplicada ou inválida retorna readiness 503.
- Os 4 flags `fiscal_*_real_configured` continuam **false** por design até existirem clientes externos, assinatura, Vault e transporte real certificados. Handler sintético de teste não pode promovê-los.
- Sem certificados reais, sem emissões, sem migrations, sem deploy, sem mudança Contabo ou na branch `production`.

## Dependências restantes

Factory está pronta para receber o cliente/provedor e gateway oficiais homologados, mas o entrypoint de produção ainda não possui tais objetos; a mera presença da factory **não configura** o cliente. Falta XMLDSig/mTLS, provider oficial autenticado, secret e CNPJ por tenant/unidade, E2E autenticado, homologação e autorização de ativação.

Fonte: código e testes neste branch; gates remotos precisam confirmar o SHA final.
