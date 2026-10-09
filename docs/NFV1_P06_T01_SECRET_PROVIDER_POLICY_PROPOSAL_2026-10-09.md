# NFV1-P06-T01 — Seleção de Secret Manager e política proposta

Data: 2026-10-09. Produto: FM NFCORE V1. Estado: PROPOSTA PARA DECISÃO HUMANA.
Autorização recebida: “Pode executar”, para estudar/selecionar o provider e publicar resultado revisável. Nenhuma conta, IAM, credencial, compra ou implantação foi executada. A escolha abaixo é recomendação técnica; não é provider operacional certificado.

## Recomendação

Selecionar **Google Cloud Secret Manager (GSM)** como primeiro backend concreto, mantendo `ExternalSecretClient`, `ExternalFiscalSecretVault` e `SecretResolver` como boundaries canônicas. API e Worker permanecem no Railway. Nenhum domínio fiscal, comercial, auth ou tenant é transferido ao Google.

Motivo: serviço gerenciado com IAM por secret, versões, auditoria de acesso, recuperação de versões mediante destruição adiada e custo proporcional baixo; evita operar um cluster Vault. AWS Secrets Manager é alternativa tecnicamente adequada se a FM já possuir identidade/conta AWS governada. Azure Key Vault é alternativa se a FM já possuir Entra/assinatura governada. A existência dessas contas não foi presumida. A escolha deve ser reavaliada se uma identidade existente eliminar o bootstrap sensível de outra opção.

Proposta de segurança para aprovação em conjunto: isolamento por projeto/ambiente e workload, acesso somente leitura, bindings duráveis de referências, resolução sem cache de material, rotação controlada, auditoria e recuperação descritas abaixo. Aprovar este documento autoriza a seleção e o desenho para execução interna posterior em T02; conta real, gasto, IAM externo, credencial e deploy continuam dependentes da autorização operacional específica.

## CURRENT confirmado e arquitetura FM

Entrada: PR #152 MERGED; main `b87b64567b91b775a6b6a26b06724c33faf82645`, árvore `20fa0d0a70a43005489308adfa517e765a0b7052`. CI #734/run37952628383 e Governance #155/run37952628603 SUCCESS. Zero PRs abertas antes deste bloco. P0..P4 certificados internamente,23/59 concluídas. Ordem aprovada P6 antes de P5.

Railway somente leitura: API/Portal/PostgreSQL1/1; Worker0/1, deployments históricos inalterados. Label `production` pertence ao projeto FM NFCORE Staging e não aprova produção. Nenhum acesso a valor de variável, SQL, material secreto ou conta de provider. Runtime real de secrets não confirmado.

Fontes organizacionais fornecidas pelo dono: Documento Mestre de Fundação — Arquitetura Única Evolutiva FM Tecnologia v1.0,13/09/2026 (§4.3,5,8,11,12), e FM Cognitive Vertical Core V1 (§2,5,6,9,16). Aplicação: adapter de infraestrutura sobre a mesma linha de produto; configuração por ambiente; autoridade determinística e aprovação humana; nenhum segredo em IA/prompt; fatos separados de targets. O System Design GERENTE é de outro produto e não redefine a autoridade fiscal independente deste repositório. Pagamentos centralizados no Command não tornam o Command distribuidor de certificados fiscais nem justificam novo serviço central de secrets sem decisão própria.

Inventário auditado:

| Boundary existente | Capacidade comprovada pelo código | Lacuna para T02..T04 |
|---|---|---|
| `vault/external.py` | `fetch(reference_id)`, record redacted, tipo/ref, tenant/unit/environment/provider antes do fetch, expiração, material efêmero, audit metadata, sem cache | Driver real e binding governado de ref→recurso/versão; purpose/workload não devem ser presumidos como autorização já implementada |
| `security/secrets.py` | `sec_` opaco, scope tenant/unit/purpose, versão inteira, revogação/expiração, backend inseguro rejeitado em staging/production | Backend real de assinatura, ambiente e workload/provider no binding; produção-safe declarativo não certifica provider |
| `product/platform_configuration.py` e `tenant_configuration.py` | referências/metadados, estados missing/configured/verified; cliente novo configurável | Plataforma `secret_backend` não é registry operacional; provar integração com autoridade/persistência existentes |
| `runtime/config.py` | produção exige perfil `external` | Perfil não instancia provider; não mudar para `gcp` e quebrar contrato |
| `worker_composition.py` / `worker_main.py` | registry canônico exige WebhookSecurity; sem dependência não consome jobs | Bootstrap de assinatura pelo resolver real; T02 deve reapresentar mapa mínimo antes de implementar, sem criar handler/fila paralelo |

Há dois formatos de referência existentes (`ref:` fiscal e `sec_` assinatura), com versões string e inteiro respectivamente. Não convertê-los implicitamente nem substituir um pelo outro. Usar mecanismo de acesso GSM comum na infraestrutura e projeções específicas para cada contrato, conservando autoridades. Não declarar que apenas implementar `ExternalSecretClient` resolve o bootstrap Worker.

## Comparação das opções

Fontes oficiais consultadas em 2026-10-09 estão no final. Avaliação qualitativa aplicada ao runtime Railway, não benchmark nem garantia de SLA ponta a ponta.

| Critério | Google Secret Manager | AWS Secrets Manager | Azure Key Vault | Vault / HCP Vault Dedicated |
|---|---|---|---|---|
| IAM/bootstrap | IAM por secret; WIF externa ou service account. Identidade Railway não confirmada | IAM por ARN; STS/federação ou Roles Anywhere com X.509. Identidade externa também necessária | Entra/RBAC; managed identity fora de Azure não presumida; federação/certificado exige emissor | Policies por path; AppRole/JWT/cert. SecretID/CA e renovação não eliminam bootstrap |
| Rotação | Versões; schedule envia Pub/Sub. Não altera credencial no terceiro por si só | Versões/stages; managed rotation de serviços suportados ou Lambda; integração com terceiro exige implementação | Versões; Event Grid/Functions para secret externo; auto-rotation de chave não equivale a secret | KV v2 versiona; engines podem gerar/rotacionar credenciais suportadas; KV estático não renova certificado fiscal |
| Disponibilidade | Serviço gerenciado; SLO99.95% nas operações de acesso, com condições/exclusões | Serviço gerenciado; replicação regional disponível, sem presumir failover no adapter | Serviço gerenciado; topologia/recovery precisam validação na região contratada | Self-host exige HA, unseal, storage, upgrades. HCP Essentials99.9%; Development sem SLA/HA/audit streaming/restore |
| Auditoria | Data Access habilitado para AccessSecretVersion + Admin Activity; testar recibo | CloudTrail para eventos/API; retenção/destino devem ser configurados | Diagnostic logging/Monitor; habilitar destino/retention | Audit devices configurados; por padrão off em novo cluster; falha de todos bloqueia requests |
| Custo consultado | US$0.06/versão ativa/mês/location; US$0.03/10mil acessos, franquia compartilhada6versões/10mil acessos | US$0.40/secret/mês;US$0.05/10mil API; extras de Lambda/KMS/log/replica conforme uso | Cobrança por10mil operações; página oficial retornou `$-`, valor numérico não confirmado | Self-host inclui compute/HA/operador/backups. HCP cobra base/hora+clientes nos tiers comerciais; cotação exata pendente |
| Recovery | Versão desabilitada recuperável; delayed destruction1..1000dias. Delete do secret/expiração do secret ignora delay | Recuperação durante janela antes da exclusão definitiva; replication não é backup independente | Soft-delete7..90dias e purge protection; restaurar vault não restaura bindingsRBAC/EventGrid | KV v2 undelete antes de destroy; snapshot/restore e recoverykeys operados; HCP varia por tier |
| Decisão neste contexto | Recomendado com condições de identidade/recovery | Reserva válida, especialmente com IAM FM existente | Reserva válida, especialmente com Entra FM existente | Não selecionar cluster novo para este escopo; excesso de operação/custo sem requisito demonstrado |

Variáveis Railway continuam necessárias para identidade/bootstrap/configuração de plataforma; não são o backend dos segredos fiscais/comerciais de clientes. Banco/Supabase não substitui vault por guardar bytes criptografados sem identidade, rotação e recovery certificados. Nenhum desses caminhos é fallback autorizado.

## Custos reproduzíveis, sem contratação

Estimativas em USD, mês completo, uma localização faturável por versão (replicação automática GSM conta uma), todos os limites gratuitos disponíveis na conta de billing. Versões desabilitadas continuam faturáveis. Cenários ilustrativos, não inventário real. Seja N secrets com duas versões retidas, A acessos, R notificações:

`GSM = max(2N-6,0)*0.06 + max(A-10000,0)/10000*0.03 + max(R-3,0)*0.05`

`AWS = N*0.40 + A/10000*0.05` (sem replica/automação).

| Cenário sintético | GSM com franquia | GSM sem franquia disponível, R=0 | AWS base |
|---|---|---|---|
| N=10,A=100000,R=0 | US$1.11 | US$1.50 | US$4.50 |
| N=100,A=1000000,R=0 | US$14.61 | US$15.00 | US$45.00 |

GSM usa versões numéricas no binding; leitura pinada evita consulta de metadata em cada acesso e torna custo estimável. Somar acessos de API, Worker e readiness; proibir probe por secret a cada heartbeat. Audit Logging, retenção, Pub/Sub, executor de rotação, rede, impostos e câmbio são extras não estimados. Não assumir gratuito nem converter para BRL sem cotação. Azure/HCP não receberam número inventado.

Proposta de início: alerta de billing a US$5 e US$10/mês no projeto staging, com objetivo de manter primeiro cenário abaixoUS$10 incluindo extras. **Alertas não são teto automático de cobrança**; billing deve ser revisado e conta não deve ser contratada antes de orçamento aprovado. Inventário real pode exigir novo orçamento; não desligar secretos automaticamente por custo. Produção terá conta/região/orçamento aprovados separadamente em P11.

## Política proposta de identidade e acesso

1. Projetos separados staging/production; principals distintos API e Worker em cada ambiente. Portal/browser sem permissão GSM. Não reutilizar credencial staging em produção ou entre SaaS.
2. Preferir WIF com emissor OIDC/X.509 governado comprovado. A documentação Railway encontrada é OAuth/OIDC de **login de usuário**, não prova emissor de identidade de processo. GitHub Actions OIDC também não autentica container Railway em execução. Não forjar subject, reutilizar token humano ou criar serviço de identidade novo por inferência.
3. Para staging, propor exceção explícita: service-account key por workload, somente leitura de secrets allowlisted, armazenada exclusivamente no canal protegido do runtime Railway, nunca Git/chat/artifact/build args/imagem. Rotação máxima30dias, revogação imediata em incidente, inventário de keyIDs/dono/data e revisão mensal. Alterar chave bootstrap pode exigir restart controlado; segredos de clientes continuam resolvidos em runtime sem código/deploy por cliente. A exceção é configuração do mesmo adapter, não uma segunda aplicação. **Nada foi criado ou lido. Produção não herda essa exceção**; WIF comprovada ou aprovação específica em P11.
4. Readers recebem `roles/secretmanager.secretAccessor` somente nos recursos necessários. Não dar Owner/Editor/Admin, criação/atualização/delete, setIamPolicy, gestão de billing nem list amplo ao runtime. Egress somente endpoint oficial e exchange de identidade allowlisted; timeouts limitados, sem URL do cliente.
5. Operador de rotação/provisionamento separado do reader; papel customizado mínimo para addVersion/disable/metadata requer revisão da política IAM concreta antes de aplicar. Delete do secret, redução de delay, alteração de IAM e purge ficam fora do operador rotineiro; dupla revisão humana para ações destrutivas. A escolha de papel no documento não é aplicação IAM.
6. Plataforma administra provider/account/IAM/bootstrap. Tenant autorizado administra somente referências/configuração de seu escopo pela autoridade existente; jamais principal da plataforma, recurso arbitrário, raw material em respostas de leitura ou grant IAM. Platform admin de app não se converte automaticamente em administrador de cloud.

## Binding, versão e falha fechada

Target para T02, sujeito à política aprovada: binding durável dentro da persistência/configuração existente, sem segundo control plane. Deve incluir referência opaca, tenant, unidade exata (incluindo sem-unidade quando permitido pelo contrato), ambiente runtime e ambiente fiscal quando aplicável, provider fiscal/comercial, purpose/kind, workload autorizado, recursoGSM completo allowlisted, versão canônica, versãoGSM numérica, state e expiry timezone-aware. Secret IDs não contêm CPF/CNPJ/nome de cliente. ResourceGSM não vem de request/browser.

Antes do I/O: autenticar ator e validar binding/RBAC/contexto exato; impedir cross-tenant/unit/environment/provider/purpose/workload. Depois do I/O: validar versão retornada, integridade CRC32C, envelope/schema/kind/reference/expiry. Erro, missing, revogado/desabilitado, versão destruída, permission denied, timeout e payload inválido falham fechado com códigos sanitizados. Nunca anexar SDK exception, headers, body, bytes, senha ou chave em log/trace/telemetria.

Envelope versionado contém material e metadata consistentes, inclusive senhaPKCS12, quando aplicável; só circula no boundary efêmero. Limite GSM64KiB inclui envelope/base64: rejeitar overflow antes de upload e testar borda. Não criar storage complementar silencioso. Certificado real com envelope acima do limite é blocker de seleção/capacidade que exige decisão específica; seu tamanho não foi lido.

Rotação: operador cria/valida nova versão sem ativá-la; verifica versão/binding/integridade; grava nova versão pinada na configuração durável com controle concorrente/versionamento/idempotência/audit; próxima resolução lê configuração atual. Nunca usar `latest` como autorização nem mapear inteiro NFCore para versãoGSM sem binding explícito. Se escrita canônica falhar, nova versão não ativa; se publicação succeeds e request de leitura falhar, não voltar a versão antiga automaticamente.

Desabilitar versão antiga após janela proposta máxima24h, somente quando destinatário aceita período de sobreposição e sem comprometer revogação. Revogação por incidente não tem grace nem fallback. Protocolos que não suportam duas chaves exigem cutover coordenado e readiness bloqueada durante a troca. Uma versão desabilitada retida30dias pode ser restaurada somente por aprovação e revalidação; comprometida nunca é reativada. Rotação de certificate/CSC/credencial externa requer atualização/validação na autoridade emissora, não só uploadGSM.

Sem cache de material secreto entre operações, nem cópia em DB/disk/env de segredo do cliente. `SecretMaterial.close` é zeroização best-effort; Python/SDK podem produzir cópias transitórias, não prometer eliminação física completa. Access tokens do SDK têm lifetime próprio; revogar uma keybootstrap não garante invalidação instantânea de tokens já emitidos. Incidente exige remover grants/desabilitar versão, parar workload afetado por canal autorizado e verificar negação real.

## Auditoria, disponibilidade e recovery

Habilitar Data Access em GSM sem exclusões de readers e Admin Activity; retenção proposta90dias em destino separado, acesso restrito para auditor. Correlacionar workload/refopaca/versão/resultado/tempo/eventoNFCore e recibo cloud sem bytes, senha, token ou identidade pessoal desnecessária. Audit do vault atual tolera exporter failure: não muda a autoridade nem prova recibo externo; exigir observação cloud real nas provasT03/T04. Logs/apontamentos ausentes bloqueiam certificação, não liberar provider pelo `production_safe=True`.

Propor destruição adiada30dias para versões. **Excluir secret inteiro ou usar expiry automática do secret destrói material sem respeitar esse delay**. Por isso expiry do material é metadata canônica com negação em runtime; não configurar expiry destrutiva do recurso como substituto. IAM operacional não concede delete do secret; backups de bindings não contêm bytes. Replicação/disponibilidade do GSM não é backup de material contra exclusão total/comprometimento.

Recovery cobre: restaurar versão desabilitada/não destruída; restaurar binding durável de backup governado; reemitir/reprovisionar credencial na origem após perda definitiva ou comprometimento. Não exportar material real para Git ou artifact como backup. Antes do primeiro uso real, dono deve confirmar canal de reemissão/custódia de certificado/CSC por escopo; sem isso recovery não é certificável. Não criar vault paralelo de backup por esta decisão.

Objetivos propostos, ainda não medidos: RPO0 para binding confirmado em armazenamento durável e versãoGSM confirmada; RTO≤30min para rollback seguro de binding/versão recuperável. Perda definitiva exige reemissão e não tem RTO garantido neste estudo. Testar indisponibilidade/timeout e negação; API dependente retorna bloqueio, Worker não assina nem entrega e preserva retry canônico. Sem fallback para memória/env/chaveantiga. SLA do provider não é SLA da jornadaNFCore.

## Mapa de impacto e aceite

Esta entrega altera apenas cronograma,ledger,CURRENT,este documento e checkpointT01. Código, migrations, workflows, contratos, testes e configuração externa protegidos. Não antecipa T02..T04, P5deploy, fiscal real ou outrorepo.

| Aceite T01 | Evidência nesta entrega | Gate restante |
|---|---|---|
| IAM | comparação e matriz de identidade/grants/bootstrap | aprovação políticaB01; configuração/identidadeB02 |
| Rotação | versão pinada, troca canônica, revoke e ausência de fallback | provasT02/T04 e autoridade externa |
| Disponibilidade | comparação gerenciado/cluster, SLA com limites, timeoutfailclosed | teste realT04 |
| Auditoria | cloud + auditNFCore, retenção proposta e recibos | provarT03/T04 |
| Custo | fórmula, cenários, extras e números não confirmados explícitos | conta/região/billing/orçamentoB02 |
| Recovery | retenção, delete/expiry hazard e reemissão | rehearsal realT04 e runbookP9 |

T01 somente pode ser concluída após aceitação da seleção/política, PR/CI/merge autorizado e CI main. FaseP6 somente apósT02..T04 e provider real testado. CheckboxT01 continua vazia;23/59 concluídas.

Blockers: **P6-T01-B01**, decisão humana sobre provider/política sensível; **P6-T01-B02**, conta/região/orçamento/bootstrap/IAM e canal operacional não confirmados. B02 é gate de operação externa; não impede estudo nem implementação internaT02 apósT01 certificado. Payloadlimit/reemissão ficam condições obrigatórias de capacidade/recovery emT03/T04, sem criar tarefa paralela. P5-B01/B02/B04/B05 preservados.

## Fontes oficiais consultadas — 2026-10-09

- GSM pricing: https://cloud.google.com/secret-manager/pricing
- GSM SLA: https://cloud.google.com/secret-manager/sla
- IAM: https://docs.cloud.google.com/secret-manager/docs/access-control
- Access/version: https://docs.cloud.google.com/secret-manager/docs/access-secret-version
- WIF: https://docs.cloud.google.com/iam/docs/workload-identity-federation
- X.509: https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-x509-certificates
- GSM audit: https://docs.cloud.google.com/secret-manager/docs/audit-logging?hl=en
- GSM practices: https://docs.cloud.google.com/secret-manager/docs/best-practices?hl=en
- GSM rotation: https://docs.cloud.google.com/secret-manager/docs/secret-rotation
- GSM delayed destruction: https://docs.cloud.google.com/secret-manager/docs/delay-destruction-of-secret-versions
- GSM payload: https://docs.cloud.google.com/secret-manager/docs/reference/rest/v1/SecretPayload
- Railway userOAuth: https://docs.railway.com/integrations/oauth
- AWS pricing: https://aws.amazon.com/secrets-manager/pricing/
- AWS rotation: https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html
- AWS IAM: https://docs.aws.amazon.com/secretsmanager/latest/userguide/auth-and-access_iam-policies.html
- AWS externalidentity: https://docs.aws.amazon.com/pt_br/secretsmanager/latest/userguide/auth-and-access-on-prem.html
- AWS audit: https://docs.aws.amazon.com/secretsmanager/latest/userguide/monitoring-cloudtrail.html
- AWS recovery: https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_restore-secret.html
- Azure pricing: https://azure.microsoft.com/en-us/pricing/details/key-vault/
- Azure roles: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/security
- Azure secretrotation: https://learn.microsoft.com/en-us/azure/key-vault/secrets/tutorial-rotation
- Azure logs: https://learn.microsoft.com/en-us/azure/key-vault/general/logging
- Azure recovery: https://learn.microsoft.com/en-us/azure/key-vault/general/soft-delete-overview
- HCP tiers/pricingmodel: https://developer.hashicorp.com/vault/cloud/get-started/deployment-considerations/tiers-and-features
- Vault AppRole: https://developer.hashicorp.com/vault/docs/auth/approle
- Vault KVv2: https://developer.hashicorp.com/vault/docs/secrets/kv/kv-v2
- Vault audit: https://developer.hashicorp.com/vault/docs/audit

Resultados são leitura documental, não contratação/benchmark. URLs não retornadas e valores dinâmicos não extraídos não foram usados como prova numérica.
