# NFCore — Fase P0 catálogo, trial, quotas e escopo de segurança

**Data:** 06/11/2026. **PR:** #372. **Status:** candidato em branch, ainda sem merge/deploy/homologação externa.

## Fonte de verdade proposta
O usuário aprovou a tabela comercial do site:
| Plano | Mensalidade BRL | Docs mensais | CNPJs | RPM |
|---|---:|---:|---:|---:|
| Starter | 99.00 | 1000 | 1 | 120 |
| Pro | 249.00 | 5000 | 3 | 600 |
| Business | 590.00 | 25000 | 15 | 2400 |
| Enterprise | 1490.00 | ilimitado no catálogo | ilimitado no catálogo | política contratual separada |

O catálogo `config/commercial/plans.json` agora é `version=2`, `PUBLISHED_CATALOG_RUNTIME_GATED`: **publicado/versionado em Git, nunca automaticamente aprovado no banco de preços.** `publication.runtime_activated=false`. A administração de preços e a decisão formal de release continuam autoridade independente, como exigido pelo sistema atual.

Os valores anuais e cobranças por excedente não foram autorizados no prompt: permanecem desabilitados e seus previews fail-closed; notas além da franquia não se tornam cobrança implícita. **Enterprise ilimitado em documentos não significa token IA, CPU, fila ou infraestrutura sem teto**.

Trial `duration_days=14`, `production_docs_limit=50`; sem licença fiscal não há autorização de emitir, mesmo durante trial. Rota de browser `/v1/public/trial-plans` somente aparece quando config, origins, rate-limit durável, entrega de ativação, pricing-admin e release estão ativas; rota ausente na produção não deve ser ativada com fallback.

## IA e compatibilidade
`src/kordena_fiscal/cognitive/commercial_quotas.py`:
- novos IDs Starter/Pro/Business/Enterprise reconhecidos com teto conservador de tokens, sujeito ao snapshot **durável** da assinatura.
- tokens de entrada/saída respectivamente: Starter 1m/300k; Pro 3m/900k; Business 8m/2.4m; Enterprise temporariamente 8m/2.4m **até aprovação específica**, sem inferir IA ilimitada.
- planos legados `essencial/crescimento/escala` mantidos apenas na **leitura das assinaturas já persistidas** para prevenir regressão de clientes existentes. Não aparecem no novo catálogo publicável; sua migração será uma tarefa versionada, auditada e não automática.
- nega snapshots sem quotas, quotas fora do teto, assinaturas suspensas, trial expirado e estados desconhecidos; nenhuma recomendação IA concede permissão fiscal.

## Guardas P0 adicionadas
`src/kordena_fiscal/product/commercial_entitlement_guards.py` adiciona política pura e fail-closed para CNPJ, documentos (inclui reservas em voo) e RPM (inclui concorrência em janela 60s) por plano/versão/estado. **Ainda não está ligada ao ledger**: não representa enforcement ativo ou garantia de produção. A implementação real exige reservas e commit atômico em banco por tenant no caminho canônico antes da assinatura/transmissão, incluindo tratamento idempotente para retries.

## Autoridades não alteradas
- Billing/assinatura e cobrança permanecem no Command e na projeção canônica de assinatura já existente do NFCore, sem segunda fatura.
- Homologação externa (certificado A1, mTLS, CSC, Prefeitura/SEFAZ, esquema municipal/estadual) continua autoridade fiscal exclusiva NFCore.
- Não cadastrar tenants, abrir trial, liberar emissão, criar cobranças reais ou habilitar credenciais na instalação desta PR.

## Fases pendentes
1. Aprovar catálogo/quotas no pricing_admin e formalizar decisão de release em banco.
2. Implementar semântica de reserva durável docs/RPM/CNPJ no fiscal_runtime (atomicidade e replay), reconciliando contadores com documento efetivamente autorizado.
3. Endpoint read-only governado de consumo por tenant para Command (não usar contador de processo como medição contratual), sincronização por S2S e reconciliação dos eventos financeiros.
4. Testar início/expiração do trial, conversão paga, inadimplência, suspensões e downgrade, antes de ativar as rotas públicas.
5. Comprovar que todos os gates CI, integridade, regressão, segurança, autorização e deploy específico foram aprovados.

O checkpoint distingue claramente **trabalho implementado**, **não integrado**, **não homologado** e **não publicado em produção**.
