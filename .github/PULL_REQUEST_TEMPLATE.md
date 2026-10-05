## Item do cronograma mestre

**Task ID:** NFV1-Pxx-Tyy  
**Título:** copie exatamente do cronograma/ledger.

## CURRENT auditado antes da mudança

**main SHA:**  
**branch / HEAD:**  
**CI da main:**  
**PRs abertas relevantes:**  
**ambiente afetado / SHA implantado, se aplicável:**  

## CURRENT -> TARGET

**CURRENT:**  
**TARGET:**  

## O que mudou

Descreva somente as mudanças necessárias para esta tarefa.

## Autoridades canônicas reutilizadas

Liste domínio, serviço, API, autenticação/RBAC, tenant/unidade, persistence, provider boundary ou outra autoridade existente reutilizada.

## O que NÃO mudou

Declare explicitamente as áreas protegidas e fora de escopo.

## Critério de aceite — como foi provado

Cole os critérios aplicáveis do cronograma e informe evidência observável.

## Verificação executada

Liste comandos/checks e resultado.  
"Não rodei" é uma resposta válida, mas a tarefa não pode ser marcada concluída.

## Segurança / Tenant / Unidade

- Auth/RBAC:
- Tenant isolation:
- Unit isolation:
- Secrets/PII:
- Idempotência:
- Fail-closed:

## Não confirmado / riscos / blockers

Tudo que não foi comprovado deve permanecer explicitamente não confirmado.

## Evidências

- PR:
- CI:
- commit/SHA:
- runtime/staging:
- evidência externa, quando aplicável:

## Checklist obrigatório

- [ ] Escopo contém somente uma tarefa NFV1-Pxx-Tyy, exceto bootstrap documental explicitamente identificado.
- [ ] Li AGENTS.md, o cronograma inteiro e o ledger antes de executar.
- [ ] Reconfirmei main/HEAD/PRs/CI antes da mudança.
- [ ] Não criei segunda autoridade de domínio/API/auth/tenant/user/persistence/frontend.
- [ ] Não introduzi segredo, certificado, token, credencial ou dado real no diff.
- [ ] Não removi, pulei ou enfraqueci teste válido para obter verde.
- [ ] `python3 scripts/check_nfcore_plan.py` passa.
- [ ] Testes aplicáveis do cronograma passam.
- [ ] Ledger só foi marcado `[x]` após PR + CI + commit/SHA e evidência necessária.
- [ ] Ações irreversíveis/produção/merge obedecem à autorização humana específica.
