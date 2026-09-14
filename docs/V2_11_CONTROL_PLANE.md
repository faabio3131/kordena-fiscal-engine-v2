# V2-11 — Control Plane independente

Status: **CONCLUÍDA / CERTIFICADA**  
Branch: `v2/control-plane`  
Base certificada: `v2/product-contract-packs` @ `156a945cc8e2708eba21551b128ac3d673bb0cdc`

> Evidência detalhada de fechamento: `docs/V2_11_CLOSURE_CERTIFICATION.md`.

## Objetivo concluído

A V2-11 estabeleceu um Control Plane independente e host-neutral para o FM Fiscal, com RBAC administrativo, isolamento por tenant/unidade/ambiente, persistência durável, perfis fiscais versionados, governança de Capability/Readiness, visões operacionais somente leitura e trilha de auditoria.

## Blocos certificados

### Bloco 1 — Foundation administrativa

Foram certificados organização/unidade, atores administrativos, RBAC, ambientes explícitos, referências opacas e audit trail.

Gate: `eaeca06739f756d31085617c1eecabebcc846dd7`  
Run: `34708472525`  
Resultado: **406 PASS**, 81 source files.

### Bloco 2 — Persistência durável + perfis fiscais

A migration V4 `v2_11_control_plane_durable_state` integrou o estado administrativo ao UoW SQLite comum. `FiscalProfile` permaneceu a fonte fiscal única, com vigências `[effective_from, effective_to)`, adjacência válida, overlap rejeitado e restart safety.

Gate: `fb485d180a2fba689c0465b61fbec206c02c3cf4`  
Run: `34709564947`  
Resultado: **416 PASS**, 83 source files.

### Bloco 3 — Capability/Readiness governance

`GovernedCapabilityReadinessService` valida o contexto administrativo e delega a decisão à autoridade de Capability/Readiness existente. A configuração administrativa não eleva readiness por conta própria.

Gate: `292abfda6ffa02c599b5b01d0ec2ba766267f994`  
Run: `34709912172`  
Resultado: **424 PASS**, 84 source files.

### Bloco 4 — Operational Control Plane

`OperationalControlPlaneService` fornece leitura governada de delivery/outbox, tentativas, erros, archive e reconciliation reutilizando os stores certificados, sem criar estado operacional paralelo. As views expõem apenas os metadados necessários e mantêm `operations.read` separado de `audit.read`.

Gate: `a0b0ddd101942c2e1fa68550575b20a11470dcfe`  
Run: `34710207596`  
Job: `103597482579`  
Resultado: **430 PASS em 2.01s**, 85 source files.

### Bloco 5 — Certificação end-to-end

A suíte `tests/control_plane/test_v2_11_end_to_end.py` certifica os quatro blocos em conjunto, cobrindo:

- as permissões administrativas usadas pela fase e comportamento fail-closed;
- isolamento multi-tenant/unidade e de estado operacional;
- HOMOLOGATION explícito e produção não implícita;
- perfis/vigências e rejeição de overlap;
- persistência/restart e migration V4 idempotente;
- readiness central sem autoridade paralela;
- visões operacionais sanitizadas;
- neutralidade cross-product;
- boundary arquitetural da próxima fase.

Gate final: `eed6b056e9d1941da435179c5eaf805c261f6622`  
Run: `34736942613`  
Job: `103669941388`  
Install: PASS  
Ruff: PASS  
Mypy strict: **85 source files PASS**  
Pytest: **437 PASS em 1.99s**.

## Auditoria final V2-10 -> V2-11

No gate funcional final, o compare da base `156a945cc8e2708eba21551b128ac3d673bb0cdc` para `eed6b056e9d1941da435179c5eaf805c261f6622` registrou:

- **55 commits à frente**;
- **0 atrás**;
- **26 arquivos líquidos**.

As mudanças ficaram concentradas em Control Plane, integração de persistência/UoW, migration V4, testes, documentação e ajustes históricos necessários para a nova migration. A regressão integral passou com 437 testes.

## Limites pós-V2-11

A V2-11 não executa integração externa produtiva. Adapters produtivos de gateway, assinatura e cofre de identidade permanecem para a V2-12 e fases posteriores. Também não houve homologação externa, deploy, promoção ou cutover.

## Fechamento

O CI foi restaurado para `workflow_dispatch` no commit `df2c961db5ee7db20d6269afa6b2213e3bc30698`.

A PR #12 permanece Draft e sem merge. A V2-11 está **CONCLUÍDA / CERTIFICADA**.
