# NFCore V1 — Reconciliação canônica de PRs — 03/11/2026

**CURRENT auditado:** `faabio3131/nf-core-v001`, `main@d810dca6f3b4ab7ca0ffd7d1a8c1b81cee9a3183`.
**Estado:** `RECONCILED_CANDIDATES_PENDING_AUTHORIZATION_AND_POST_MERGE_GATES`.
**Limite:** não equivale a produto comercialmente pronto, homologação fiscal, integração em `main` ou deploy Contabo.

## Resultado da auditoria das 11 PRs legadas + PR #333

PRs fechadas sem merge, com comentário técnico e histórico acessível:
- #165 — checkpoint P05/GSM staging antigo, histórico;
- #188 — Worker/telemetria histórica; testes úteis recuperados na #335;
- #201 — overflow de métricas recuperado na #334;
- #205 — matriz P09 histórica;
- #238 — decisões de uso e blueprint Contabo preservados na #339;
- #243 — cache GSM de Worker preservado na #336;
- #286 — checklist NO-GO de piloto 02/11, histórico;
- #298 — ingresso Command e separação de trial preservados na #337;
- #299 — decisão aprovada de planos, trial e identidade preservada na #339;
- #302 — scripts COG-02 de preflight/ensaio + gate CI preservados na #338;
- #313 — teste antigo de RTC baseline v3 incompatível com baseline v5;
- #296 — PR release antiga SUPERSEDED em auditoria prévia (fora das 12 acima).

Todas as PRs acima foram fechadas **sem merge**. A PR #297 também já estava encerrada como SUPERSEDED.

## Candidatas novas publicadas, NÃO mergeadas

| PR | Delta preservado | Evidência na branch | Gate pendente |
|---|---|---|---|
| #333 | COG-1 ERP Bling/Tiny consultivo e matriz cross-tax | 69 testes PASS; Ruff PASS; Mypy PASS; CI/Gov SUCCESS | aprovação de merge + CI pós-merge |
| #334 | MetricsRegistry overflow fail-closed | 24 testes PASS; Ruff/Mypy PASS; CI/Gov SUCCESS | aprovação de merge + CI pós-merge |
| #335 | regressões HTTP/Worker/telemetria sem vazamento de escopo | 8 testes PASS; Ruff PASS; CI/Gov SUCCESS | aprovação de merge + CI pós-merge |
| #336 | cache de transporte GSM por identidade do Worker | patch limpo; Ruff PASS; Linux CI de qualidade necessário | CI/Gov + aprovação de merge |
| #337 | ingresso Command assinado e trial fail-closed | 41 testes PASS; Ruff/Mypy dirigido PASS | CI/Gov + revisão de auth e aprovação |
| #338 | Contabo COG-02 preflight, migration19 rehearsal e deny CI | código apenas versionado; testes PG SKIP sem DB descartável | CI/Gov, ensaios Linux, autorização própria |
| #339 | decisões comerciais aprovadas e histórico de preços | documentos reconciliados, `git diff --check` PASS | CI/Gov + aprovação |

**Observação sobre baseline comercial:** documento de 20/10 citava R$ 149 Essencial, superado pela decisão posterior de 01/11: Essencial R$ 179, Crescimento R$ 299, Escala R$ 499. Decisão de preço não é catálogo publicado.

## Prontidão operacional NÃO comprovada

A `main` e a branch `production@d7cf5e4d58cce8ab43105b17e13b2237edc551fb` divergem; nenhum merge, release ou deploy desta reconciliação foi realizado. O SHA real em contêiner Contabo não foi certificado. Em levantamento público, `/health/live` e `/health/ready` responderam HTTP 200; o runtime anunciou checkout/trial/provedor fiscal real não configurados e produção fiscal desativada. Isto permite somente preparação de ensaio controlado, não Go comercial ou fiscal.

## Bloqueios e decisões

- **MERGE:** autorização explícita do Diretor por PR(s), após CI/Gov verdes no SHA exato e revisão de impacto; não executar apenas porque checks ficaram verdes.
- **CONTABO:** preflight read-only, migração produtiva, aprovação de migration19, deploy code-only e promoção da branch production são decisões separadas; jamais executar indiretamente via merge.
- **FISCAL:** baseline RTC v5 é `REFERENCE_ONLY_NOT_PRODUCTION_APPROVED`; tabelas, XSD, CFOP e golden cases ainda exigem fonte oficial/verificação, homologação externa e gates.
- **COMERCIAL:** não habilitar aquisição/trial/checkout públicos antes de catálogo, release authority, identidade, segurança e aceite E2E demonstrados.
- **COG:** não dar autoridade fiscal à matriz consultiva; sem segunda classificação tributária, nem criação de endpoint sem proteção tenant/unidade/RBAC.

## Próxima ação

Confirmar quality de #336–#339, obter aprovação humana explícita para merges elegíveis na `main`, integrar sequencialmente com pós-merge CI/Gov, revalidar `production` e executável na Contabo read-only. Solicitar autorização **separada** antes de qualquer promoção/deploy e outra para migration, segredos ou ativação fiscal.
