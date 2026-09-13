# V2-17 — Convergência e Cutover — Execução Governada

Data de início: 2026-09-13  
Branch: `v2/convergence-cutover`  
Base: V2-16 `v2/fm-products-integration@6998d5a4b7370621160e2520bbadabafca86bda0`

## Escopo desta autorização

A V2-17 é iniciada apenas como preparação e certificação interna de convergência. **Cutover real, produção, migração produtiva e arquivamento/desativação do motor legado permanecem proibidos.**

## Referência correta do motor legado

O repositório `faabio3131/kordena-fiscal-engine` tem `main` em um commit inicial/placeholder (`b050d4540227ea1ab6dd7b367284daca2ed9a7ac`). Esse ref NÃO é o baseline fiscal a ser usado em convergência.

O baseline fiscal público FISC-00..FISC-19 certificado está preservado em:

- branch: `feat/fisc-19-rtc-multiuf-hardening`;
- SHA: `b336def47ad4f5188307102203f4e04b98406014`.

Esse SHA foi a origem certificada usada pela V2-00 e é a referência histórica correta para equivalência/migração. Git, por si só, não prova qual runtime está implantado em produção; nenhuma autoridade operacional produtiva é inferida daqui.

## V2-17.1 — Convergence Readiness + Single Fiscal Authority

### Matriz de pré-condições

| Requisito | Estado atual | Evidência / motivo |
|---|---|---|
| Equivalência funcional | `READY_INTERNAL` | V2-00 + regressões cumulativas preservadas |
| Multiproduto certificado | `READY_INTERNAL` | V2-16.7 cross-product closure |
| Kordena operando no V2 | `BLOCKED_PRODUCT` | PR #118 ainda funcionalmente PARCIAL; FISC-20 não liberado |
| Regressão fiscal completa | `READY_INTERNAL` | gate V2-16.7 verde |
| Migração estado/documentos definida | `BLOCKED_PRODUCT` no checkpoint B17.1 | pertence à V2-17.2 |
| Migração testada | `BLOCKED_PRODUCT` no checkpoint B17.1 | pertence à V2-17.2 |
| Rollback documentado | `BLOCKED_PRODUCT` no checkpoint B17.1 | pertence à V2-17.2 |
| Evidência operacional externa oficial | `BLOCKED_EXTERNAL` | V2-15 mantém homologações oficiais pendentes |
| Aprovação humana de cutover | `HUMAN_APPROVAL_REQUIRED` | autorização desta janela proíbe cutover real |

O código `kordena_fiscal.convergence.readiness` materializa essa matriz de forma descritiva/fail-closed. Ele não promove readiness e `require_cutover_ready()` falha enquanto qualquer requisito obrigatório não estiver `READY_INTERNAL`.

### Single Fiscal Authority

A convergência futura deve atribuir ao FM Fiscal Core V2 uma única autoridade para:

- sequence;
- idempotency;
- document lifecycle;
- archive;
- reconciliation;
- provider state;
- fiscal binding;
- capability;
- readiness;
- audit;
- events.

`SingleFiscalAuthorityPlan` exige cobertura de todos esses domínios, um único `future_authority` e proíbe que uma autoridade legado distinta permaneça `READ_WRITE` após cutover.

Isso é um plano/invariante pré-cutover. Nenhum writer foi desligado por esta implementação.

### Writers e split-brain

Antes de um cutover real será obrigatório:

1. identificar os writers efetivamente ativos no ambiente alvo;
2. congelar/cessar writers legados na janela governada;
3. impedir dual-write entre legado e V2;
4. transferir autoridade apenas após migração/reconciliation;
5. manter o legado somente `READ_ONLY` ou `DISABLED` após cutover;
6. executar rollback se os invariantes falharem.

Nenhum desses atos operacionais é executado nesta fase preparatória.

### Regra normativa

O baseline legado `b336def...` permanece evidência histórica. Correções normativas novas não devem ser aplicadas apenas ao legado depois da convergência; enquanto o cutover não ocorre, qualquer divergência normativa material deve ser reconciliada explicitamente, nunca por dual authority silenciosa.

## Próximo bloco autorizado

Após o gate verde da V2-17.1, avançar automaticamente para **V2-17.2 — State/Document Migration + Rollback Rehearsal**.
