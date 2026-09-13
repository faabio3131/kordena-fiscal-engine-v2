# V2-15 B5 — Pilotos Controlados + Go/No-Go

Status: **CONCLUÍDO / CERTIFICADO INTERNAMENTE**

## Princípio

Piloto controlado é um processo governado e fail-closed. Ele não é produção, não promove `PRODUCTION_APPROVED` e não substitui homologação oficial externa.

O mecanismo B5 compõe primitives já certificadas: S2S/AuthorizedFiscalRequest, provider binding exato, homologation readiness, configuração comercial durável, módulo por unidade como kill-switch, audit trail e observabilidade já existente no Core.

## Escopo explícito

Cada `ControlledPilotScope` declara sem wildcard:

- `pilot_id`;
- host/tenant/unidade/ambiente;
- document kind;
- jurisdição e município quando NFS-e;
- provider exato;
- allowlist explícita de operações.

Somente `FiscalEnvironment.HOMOLOGATION` é aceito.

## Decisão determinística

Estados certificados:

- `GO_INTERNAL`: S2S compatível, pilot kill-switch ativo, operação allowlisted, provider exato e technical homologation gate internamente pronto;
- `NO_GO`: qualquer condição interna obrigatória ausente/incompatível;
- `BLOCKED_EXTERNAL`: trabalho interno pronto, porém falta evidência oficial externa para um piloto externo.

Um CI verde nunca, sozinho, autoriza piloto oficial externo.

## Kill-switches

- piloto/unidade: `UnitModuleBinding` durável `pilot.<pilot_id>` pode ser habilitado/desabilitado sem código;
- provider/documento/operação: o `ProviderBinding.enabled` exato pode ser desligado sem código;
- a ausência/desativação de qualquer binding necessário converte a decisão em `NO_GO`.

O kill-switch do piloto sobrevive a restart.

## Audit trail

Ativação, desativação, mudança de escopo governada e decisão Go/No-Go geram `ControlPlaneAuditEvent` append-only contendo ator, timestamp, correlation id, tenant/unidade, ação e motivo/status sanitizado. Nenhum segredo ou payload fiscal bruto é registrado.

## Runbook operacional

### Ativação

1. confirmar environment `HOMOLOGATION`;
2. confirmar identidade S2S e escopo exato;
3. confirmar provider binding/capability/readiness;
4. confirmar SecretReferences necessárias sem expor material;
5. confirmar technical homologation evidence;
6. ativar `pilot.<pilot_id>`;
7. registrar audit event;
8. executar decisão `GO_INTERNAL` antes de qualquer trabalho sintético.

### Rollback / kill-switch

1. desativar imediatamente `pilot.<pilot_id>`;
2. se necessário, desabilitar o provider binding da operação afetada;
3. interromper novas tentativas;
4. preservar lifecycle/archive/audit já duráveis;
5. reconciliar operações com resultado desconhecido antes de qualquer nova autorização.

### Unknown outcome

- nunca repetir cegamente uma autorização;
- classificar como resultado desconhecido;
- consultar/reconciliar conforme capability/provider;
- manter pilot em `NO_GO` se o estado não puder ser reconciliado com segurança.

### Rejection spike

- observar métricas/alertas de rejeição;
- desabilitar operação/piloto quando o limiar operacional exigir;
- investigar regra/config/provider sem promover alteração normativa automática.

### Provider outage

- circuit breaker/backpressure permanecem ativos;
- não fazer fallback silencioso para outro provider;
- aplicar kill-switch se necessário;
- aguardar recuperação/reconciliation governada.

### Certificate/credential unavailable

- fail-closed;
- não fazer fallback cross-provider ou cross-unit;
- corrigir somente SecretReference/configuração segura;
- nunca inserir material secreto em log, banco ou Git.

### Queue backlog / dead-letter

- usar alertas já certificados da observabilidade;
- suspender novas autorizações pelo kill-switch quando o risco operacional justificar;
- processar/reconciliar backlog sem duplicar emissão.

### Sequence gap

- preservar autoridade da sequência durável;
- não preencher gap por inferência silenciosa;
- investigar/reconciliar antes de reabilitar a operação.

## Estado externo desta execução

Nenhum segredo real, certificado real, endpoint externo oficial ou autorização de homologação externa foi fornecido nesta execução. O gate certificou `GO_INTERNAL` para cenário sintético válido e `BLOCKED_EXTERNAL` quando a decisão exige evidência oficial.

Isso é resultado correto e esperado, não falha de engenharia.

## Gate certificado

SHA `d7fa063c8a842480179b178a1e45f37061fe8e18`, run `34777597412`, job `103778446003`: Install PASS, Ruff PASS, Mypy PASS em **111 source files**, Pytest **616 PASS em 6.82s**. O gate cobre testes negativos, fail-closed, kill-switch durável após restart, operation/provider disable por configuração e audit trail. Warning Node 20→24 apenas informativo. CI restaurado para `workflow_dispatch` only em `116edbe9bbf4142bae6962d2ec0c598a3348d781`.
