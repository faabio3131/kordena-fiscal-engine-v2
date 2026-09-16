# POST-WEB-12-A — External Readiness Reconciliation & Evidence Intake

Baseline: `main @ 3092eea30e12a1f50ee7d93716909604053f3ffa`

Status do bloco: **EXECUÇÃO INTERNA / EVIDÊNCIA EXTERNA NÃO FORNECIDA**.

## Descoberta de sequência

A auditoria da `main`, branches, PRs abertas, Plano Mestre Web e documentação atual não encontrou uma continuação oficial numerada depois de `WP-WEB-12`. Este trabalho usa portanto o identificador provisório `POST-WEB-12-A` e não cria `WP-WEB-13` artificialmente.

## Autoridades preservadas

Este bloco não cria segundo gateway, ledger, Control Plane, homologation registry, secret vault ou production authority.

A reconciliação reutiliza:

- `DurableHomologationEnvironmentReadinessService` como leitura durável de configuração/segredos por referência;
- `HomologationEvidenceRecord` como evidência de homologação persistida;
- `HumanProductionApproval`, `ProductionActivationKey` e `ProductionActivationRecord` como objetos canônicos de aprovação/ativação;
- `SecretReference` como única representação persistida de certificado/CSC/credenciais no Control Plane.

## Gap interno encontrado

A propriedade `officially_homologated` aceitava `external_official=true` + `external_evidence_id` sem exigir `recorded_at`. Isso era mais permissivo que `OfficialHomologationProof.from_record()`, que corretamente exige timestamp oficial. A projeção de readiness foi alinhada ao boundary canônico e agora também exige `external_recorded_at`.

Foi adicionada uma projeção read-only por célula exata que relata, sem conceder autoridade:

- `READY_INTERNAL`;
- `MISSING_EXTERNAL_CREDENTIAL`;
- `MISSING_OFFICIAL_EVIDENCE`;
- `MISSING_PILOT_AUTHORIZATION`;
- `MISSING_HUMAN_APPROVAL`;
- `BLOCKED_EXTERNAL`.

A projeção aceita somente objetos canônicos de aprovação/ativação e rejeita mismatch da célula exata tenant/unidade/provider/documento/jurisdição/operação.

## Realidade externa preservada

Nenhum A1 real, CSC real, credential de provider real, resposta oficial de SEFAZ/prefeitura/provider, autorização de piloto ou decisão humana `PRODUCTION_APPROVED` foi fornecida nesta execução.

Fixtures, referências sintéticas e matrizes internas permanecem classificadas como internas/sintéticas. Nada foi promovido a evidência oficial.

## Critério de fechamento

O bloco só pode ser certificado após testes direcionados e CI completa 100% verde no HEAD correspondente. O estado externo continuará `BLOCKED_EXTERNAL` enquanto faltarem fatos externos reais.
