# NFV1-P03-T03 — eventos comerciais do Command

Data: 2026-10-08. Status: POLICY_APPROVED_FOR_INTERNAL_IMPLEMENTATION.
Decisão comercial vigente: pagamentos centralizados no Command da FM Tecnologia.
Não declara integração implementada, implantação ou homologação externa.

## CURRENT e divergência T03-B01

Main `0bbd02984aa6ac357d9ffc48d43dcfc1c1cc9c89`, PR #136 integrada;
CI #688/run37842407176 e Governance #109/run37842407307 SUCCESS.
Nenhuma PR aberta na retomada. Ambiente afetado: código/contrato interno;
staging não reconfirmado e nenhum deploy autorizado.

O cronograma descreve Cakto quando selecionada. `runtime/cakto.py` já compõe
receiver/inbox/processor por injeção; `runtime/api.py` registra essa rota somente
com receiver injetado. Não há contrato Command no código auditado do NFCore.
Não foi auditado ou alterado o repositório do Command nesta tarefa.
Compatibilidade com o emissor real do Command permanece não confirmada.

Autoridades a reutilizar: `WebhookSecurity`/`WebhookSignature`,
`CommercialFulfillmentService`, `ValidatedCommercialEvent`, persistência comercial
canônica, claim, provisioning e `CommercialCustomerActivationService`.

## Política proposta como conjunto

1. Command é o emissor comercial autorizado deste canal. Gateway e conta Asaas
   pertencem ao Command; NFCore recebe fatos comerciais autenticados e conserva
   seu próprio estado operacional. Não recebe nem administra a chave Asaas.
2. Ingresso S2S usa a assinatura HMAC-SHA256 existente `X-NFCore-Signature`
   (`t`, `kid`, `v1`), verificada sobre timestamp e bytes exatos pelo mecanismo
   canônico. Janela de replay proposta: 300 segundos. Chave ausente, expirada,
   revogada, backend indisponível ou assinatura inválida bloqueia qualquer efeito.
3. A chave autentica um binding governado do Command com produto, ambiente e
   versão. IDs no payload não concedem autoridade. Produto/ambiente diferentes,
   binding desativado e versão desconhecida são rejeitados. Somente administração
   da plataforma pode gerir esse binding; nenhum tenant se autoriza como Command.
4. Contrato versionado inclui event_id, event_type, occurred_at, product_id,
   environment, command_customer_id, command_subscription_id, command_invoice_id,
   acquisition_id e referências canônicas de plano/preço. Schema estrito: negar
   campos desconhecidos, tenant/unidade/role/permissão livre e estado de pagamento
   fornecido pelo browser. Não transmitir CPF, cartão, chave, senha ou e-mail bruto.
5. Aquisição inicial exige aquisição canônica persistida e válida. Plano/preço e
   identidade são resolvidos/verificados no servidor. Eventos seguintes exigem
   correlação persistida com a mesma compra, cliente, produto, assinatura e ambiente.
   Mapeamentos e identificadores externos são configuração/estado durável auditado,
   não condicionais de código por cliente. IDs de outro produto/cliente não se misturam.
6. Inbox durável armazena identidade e fingerprint sanitizados. Mesmo event_id e
   mesmo conteúdo é replay; mesmo event_id com conteúdo diferente é conflito.
   Deduplicação e efeitos canônicos devem sobreviver a concorrência/restart.
   A assinatura temporal não substitui essa deduplicação. Persistência indisponível
   não recebe confirmação de sucesso.
7. Pagamento não ignora claim, pricing/release, provisioning ou ativação existentes.
   Nenhum evento pode conceder platform_admin ou aprovação fiscal de produção.
   Falha após persistir evento permite recuperação idempotente; não se pode marcar
   como processado antes de registrar o resultado canônico. Worker contínuo é P4.
8. Referências de segredos e bindings por ambiente são configuráveis e auditados;
   resolução efêmera e rotação/revogação sem código/deploy por cliente. Rate limit
   reutiliza a autoridade existente; seu limite por processo não será apresentado
   como proteção global distribuída. Corpo limitado a 64 KiB antes do processamento.
   Logs/leituras/respostas não expõem segredo, payload bruto ou tokens de ativação.

## Verificação necessária após aprovação

Testes HTTP de assinatura inválida/stale/futura, revogação, rotação, configuração
ausente, backend indisponível, schema e tamanho; spoofing de emissor/produto/ambiente,
cliente/assinatura/fatura e permissões; plano/preço/aquisição incompatíveis;
inbox/replay/conflito/concorrência/restart/rollback/perda de resposta em PostgreSQL;
recuperação sem duplicar org/OWNER/subscription/activation; purchase readiness
fail-closed. Ruff/Mypy/suíte completa/gates de CI e validador do cronograma.
Testes sintéticos não certificam Asaas nem o transporte real Command→NFCore.

## Escopo e decisão

Mantém o ID NFV1-P03-T03 e a ordem original. Cakto permanece adapter histórico;
não será ativada diretamente como autoridade comercial do lançamento por inferência.
Nenhum novo repositório, preço, segredo real, cobrança, deploy ou emissão fiscal.
Nenhuma mudança de código desta política foi executada antes da decisão humana.

Decisão: política acima aprovada como conjunto para implementação interna
governada. O AGENTS.md exige autorização específica antes de mudança de segurança
sensível; este binding amplia a autoridade comercial recebida de um sistema externo.
T03-B01 RESOLVIDO: dono respondeu “Autorizado” em 2026-10-08 à política completa.
Implementação interna, testes e PR Draft autorizados. Em autorização específica posterior, o dono aprovou integrar a PR #137 e validar a main após o merge. PR #137 integrada em `bfb31e5f8d6924f4fff8f92c37c8e420b04c871f`; deploy permanece não autorizado.
T04 não foi iniciada.
