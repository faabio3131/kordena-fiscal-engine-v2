# CHECKPOINT — NFV1-P06-T01 — Selecionar provider

Data: 2026-10-09. Produto: FM NFCORE V1.
Repository: faabio3131/kordena-fiscal-engine-v2. Main: main.
Main HEAD: b87b64567b91b775a6b6a26b06724c33faf82645.
Main tree:20fa0d0a70a43005489308adfa517e765a0b7052.
Branch: codex/nfv1-p06-t01-secret-provider-selection.
Branch HEAD/PR/CI PR: registrados na PR desta entrega após publicação; pendentes neste commit inicial.
CI main de entrada: #734/run37952628383 e Governance #155/run37952628603 SUCCESS; PR #152 MERGED. Gates finais PR152 superam as pendências históricas de mainCI731 e integração da ordem nos documentos anteriores.

CURRENT: boundaries provider-neutral, sem backend concreto certificado;P6 primeira pendência após P4 e ordem aprovada;23/59 concluídas.
TARGET desta entrega: estudo comparativo e proposta concreta de seleção/política para decisão humana, sem antecipar adapterT02.

## Mudanças e autoridades

Comparação GSM/AWS/Azure/Vault por seis critérios e proposta GSM em `docs/NFV1_P06_T01_SECRET_PROVIDER_POLICY_PROPOSAL_2026-10-09.md`. Preserva ExternalSecretClient/ExternalFiscalSecretVault e SecretResolver, dois formatos canônicos de referência, auth/RBAC/tenant/unidade/persistência existentes. Sem copiar domínio privado de SaaS consumidor, centralização nova de secrets ou segundo plano mestre. Fundação FM e CognitiveCore fornecidos pelo dono usados como contexto arquitetural; autoridade técnica continua Git/CI/runtime deste produto.

Arquivos alterados: cronograma mestre,ledger,CURRENT,proposta acima e este checkpoint. Migrations: nenhuma. Código/workflows/testes/configuração real: preservados.

## Escopo e aceite

Estudo/publicação autorizados por “Pode executar”. IAM, rotação, disponibilidade, auditoria, custo e recovery comparados com fontes oficiais atuais. Recomendação condicionada à aprovação da política e confirmação operacional. Não declarar selecionado/homologado por inferência. T01 permanece não concluída e primeira pendência;T02 não iniciada.

Security/Tenant/Unit: proposta por escopo completo e workload, versão pinada, cloudIAM mínimo, identidade distinta, sem cache/fallback; bootstrap Railway/WIF não confirmado. Proposta de exceção serviceaccountkey exclusivamente staging exige aceitação específica, nunca herdada em produção. Zero valor de segredo/PII real lido ou escrito.

Staging read-only reconfirmado:

| Serviço | Deployment | Running |
|---|---|---|
| API | c0f8fb2b-30e3-45f8-a814-73c0ba97506b | 1/1 |
| Portal | 35b7aafc-b509-4851-a572-c0bd46781977 | 1/1 |
| Worker | 3215f498-0aa1-4ce3-8e61-cc74b72b68b6 | 0/1 |
| PostgreSQL | ce9b66e7-6de7-4c70-9852-8ca1936a719b | 1/1 |

SUCCESS de deployment Worker não prova processo. Patch histórico vazio inalterado; nenhuma alteração externa. Projeto FM NFCORE Staging; label production não autoriza produção.

## Blockers e riscos

- P6-T01-B01: aprovar seleçãoGSM e política sensível proposta. AGENTS.md exige parar antes de “mudança de segurança sensível”, “gasto ou conta real”, “segredo/certificado/credencial real” e “merge quando não autorizado”. Documento preparado antes de pedir decisão.
- P6-T01-B02: conta/projeto/região/billing/orçamento/identidade/IAM/canal operacional ainda não confirmados. Não buscar token nem criar conta para contornar esta lacuna. ApósT01 certificado, permite desenho/teste internoT02; impede operação externa até autorização própria.
- Recovery: destruição adiada protege versão, não delete/expiry do secret inteiro; canal de reemissão/custódia ainda precisa prova antes de uso real. Envelope GSM64KiB, tamanho de certificado real não confirmado; rejectoverflow obrigatório.
- Auditing: Null/tolerância de sink no código existente não prova recibo real. Provider não fica certificado por flag external/production_safe.
- P5 blockers backup/SQL/compatibilidade/bootstrap/driver preservados. Fiscalprovider/homologação/produção não certificados.

## Verificação e continuidade

Verificação desta proposta: planvalidator, secret scan, diffcheck; Ruff/Mypy e testes existentes dirigidos aos contratos de vault/secrets/configuração. Resultados e CI do HEAD registrados na PR; não usar suíte antiga como prova da nova proposta. Sem novos testes que apenas espelhem documento. CI integral existente mantém seus gates.

Gate de saída T01: BLOQUEADO por aceitaçãoB01, integração autorizada e certificação correspondente. Gate faseP6: não satisfeito; provider real não testado. PRODUCTION_APPROVED=NO;COMMERCIAL_LIVE=NO.

Próxima ação: revisar/aceitar a seleção/política concreta e integrar esta PR somente mediante autorização específica; certificar main; entãoT02 como próxima tarefa, sem conta/gasto/IAM/credencial/deploy por inferência. Autorização de operação externa será baseada em projeto/região/budget/grants/identidade concretos.
