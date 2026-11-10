# NFCore × Bling — Trilha B: matriz, reconciliação e operação Web

**Checkpoint:** 2026-11-10.
**Baseline CURRENT auditada:** `main@a3a243b78a4f6ecb0c9cd7ce88cf84bfe88ec845`; PR #409 integrada.
**Trabalho:** PR #410, branch `feat/bling-b01-b05-operations-recovery`.
**Estado documental:** CANDIDATE, até CI e merge confirmados. Este arquivo não autoriza transmissão, migrations, ativação de Worker ou deploy.

## Fronteiras únicas

- Ordem de venda capturada no Bling é **fato externo**, jamais autoridade tributária.
- `BlingOrders.stage` / `fm_configuration_commands` + arquivo fiscal imutável são a fonte de verdade dos snapshots de pedidos. Nenhuma segunda tabela, fila ou motor fiscal.
- `FiscalApplicationService.resolve_scope` é a única autoridade tenant/unidade/ambiente para cada instalação Bling. HTTP exige sessão humana, `integration.manage`, RBAC por unidade; mutações exigem também `document.issue` e CSRF.
- Recuperação só registra uma versão para revisão. **Nunca envia automaticamente NF-e** nem associa pedido a certificado ou documento por inferência.
- `FiscalOutboxService` segue autoridade de emissão/retorno; a UI somente projeta entrada, estados, tentativas e dead-letter, sem payload sensível.

## B-01 — matriz fiscal aprovada e limites

O recorte com contrato e XSD disponíveis é **NF-e 55 de venda de mercadorias em homologação**, com regras versionadas e assinadas (não se confunde com homologação real):

| Família | IMPLEMENTADO e testável internamente | Não modelado — falhar fechado |
|---|---|---|
| ICMS normal | CST 00/10/20/30/40/41/50/70; redução e ST explícitas; casos 40/41/50 adicionais assinados e validados por XSD | 51/60/90, ST anteriormente retida, diferimento, benefício fiscal ou desoneração sem modelo |
| Simples/MEI | CSOSN 102/103/300/400, grupo ICMSSN102 sem créditos fictícios; 103/300/400 adicionais com assinatura/XSD | CSOSN 101/201/202/203/500/900, crédito e retenção não modelados |
| ICMS ST/FCP/DIFAL | ICMS ST (10/30/70), FCP próprio/ST e DIFAL interestadual para consumidor final no recorte aprovado | Retenção histórica, bases diferenciadas, regimes especiais |
| IPI/PIS/COFINS | IPI saída 50/99, não tributado 51–55, quantidade, PIS/COFINS 01/02/03/04/06/07/08/09/49/99 | Entrada industrial e demais hipóteses sem contrato |
| RTC IBS/CBS | CST 000/200/410, informativo 2026, regras explícitas e totais | Demais CSTs/regimes, monofasia, crédito e diferimento |

Os códigos que não têm cálculo determinístico **não recebem código substituto nem taxa zero inferida**. A ausência de regra fiscal específica e homologação externa não é preenchida com IA. A matriz é do software, não consultoria tributária individual.

## B-02 — recuperação de webhooks perdidos

O operador consulta `GET /v1/portal/integrations/bling/installations/{id}/provider-orders?limit=5` (API oficial GET `/Api/v3/pedidos/vendas?pagina=n&limite=m`, com no máximo 20 itens na prévia) e observa apenas IDs e presença do pedido no NFCore. Pode solicitar uma recuperação individual, ou `POST .../recovery/backfill` com lote **até cinco pedidos** e `request_id`. O comando:
1. Valida sessão, permissão de integração, permissão fiscal, unidade e CSRF.
2. Lê a instalação ativa, resolve o escopo pelo binding canônico e obtém OAuth associado exclusivamente a essa instalação.
3. Confirma a empresa OAuth, pagina a origem Bling com limites e falha fechada para 401/429/5xx.
4. Busca o pedido completo sob a mesma identidade, revalida a instalação e invoca `BlingOrders.stage`, que preserva a primeira versão e marca divergências para revisão.
5. Retorna `requires_review` ou `already_recorded`, sem invocar `issueFiscalDocument`. Repetições não produzem duas emissões.
6. Em sucesso parcial, o operador pode repetir a mesma página; itens já capturados são ignorados.

A paginação e o rate limit seguem a documentação Bling; requisições concorrentes de outras aplicações podem disparar 429. Os limites de 3 req/s e 120.000/dia são por conta, não por endpoint. O procedimento **não afirma** que o Bling tenha entregue todos os webhooks; descobre lacunas por consulta autenticada.

## B-03 — painel Web

Dentro da aba **Integrações**, sobre a mesma aplicação premium: seleção de instalação da unidade, listagem paginada de pedidos, revisão de snapshots, preparação fiscal existente, fila de jobs, alertas de dead-letter, busca paginada no Bling, recuperação para revisão e reenvio governado de retorno ao Bling. A UI é somente cliente das mesmas regras e autoridade de sessão. Renderização exclusivamente por `textContent`, sem executar HTML vindo do ERP.

## B-04 — observabilidade

Endpoints autorizados `/orders`, `/jobs`, `/metrics` retornam projeção limitada e escopada de recibos e outbox; sem tokens, certificados, payloads brutos ou CNPJ/CPF de comprador. Os totais exibidos são **amostrais da página consultada** e nunca se apresentam como contagem global. Tentativas e dead-letter permanecem auditáveis na outbox já existente.

## B-05 — matriz de testes/gates

Obrigatórios antes de fechar PR: Ruff, Mypy, Pytest SQLite e PostgreSQL isolado, assinatura e XSD NF-e de casos suportados, API/RBAC/CSRF/tenant, recuperação sem emissão, duplicidade/idempotência, interface Playwright, frontend lint/typecheck/build, Docker/API/Portal/Worker smoke, auditoria de dependências, CI remota + governança. Cada falha exige reparo, nunca desligar teste.

## Externalização separada

Bling OAuth real e homologação do app no provedor; regras validadas pela contabilidade; certificado A1 real de cada estabelecimento; ambiente oficial SEFAZ; aprovação humana de migrations/Worker/deploy. **Sem esses itens, não declarar operação comercial fiscal homologada**, embora o código interno tenha sua própria certificação.
