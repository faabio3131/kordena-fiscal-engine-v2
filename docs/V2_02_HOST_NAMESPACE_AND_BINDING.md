# V2-02 — Host Namespace + Fiscal Account Binding

Status: **CONCLUÍDO**  
Data: 2026-09-11

## Objetivo

Eliminar colisões de identidade entre produtos consumidores e estabelecer uma fronteira explícita entre identidades externas de SaaS e o escopo fiscal interno.

## Princípio

O FM Fiscal não pode assumir que `tenant_id=123` do Kordena representa a mesma organização que `tenant_id=123` do Iron, Vendedor IA, CampaIA ou qualquer outro consumidor.

Toda identidade externa deve ser qualificada por um **Host Namespace**.

```text
host namespace + external tenant + external unit
                    ↓
          Fiscal Account Binding
                    ↓
      fiscal account + fiscal unit
                    ↓
   host + account + unit + environment
                    ↓
             FM Fiscal Core
```

## Invariantes

1. `HostNamespace` identifica o sistema consumidor, não o cliente fiscal.
2. `HostScope` é sempre composto por namespace + tenant externo + unidade externa.
3. A chave de binding é exata; não existe fallback implícito entre hosts, tenants ou unidades.
4. Dois produtos podem usar os mesmos IDs externos e até mapear para os mesmos IDs fiscais internos sem colisão, porque o host continua presente na partição universal.
5. `FiscalAccountBinding` mapeia a identidade externa para IDs internos canônicos do FM Fiscal.
6. `ExecutionScope.identity_partition_key` representa `host + fiscal account + fiscal unit + environment`.
7. O `partition_key` legado permanece disponível para compatibilidade com o baseline V1, mas novas fronteiras host-facing do V2 devem operar com identidade resolvida por binding.
8. O Core não recebe entidades privadas do host.
9. O binding não concede autorização; autenticação S2S e workload identity pertencem ao V2-05.
10. Persistência durável e lifecycle operacional de bindings pertencem ao V2-07/V2-11.
11. Composição de documento, issuer e product profile deve falhar fechado quando o `host_namespace` divergir, mesmo que conta/unidade internas coincidam.

## Convenção de namespace

Formato canônico: lowercase ASCII com segmentos separados por `.`, `-` ou `_` quando necessário.

Exemplos:

- `fm.kordena`
- `fm.iron`
- `fm.vendedor-ia`
- `fm.campaia`
- `partner.erp-x`

O namespace deve ser estável e não conter tenant, unidade, ambiente ou credenciais.

## Propagação obrigatória certificada

A dimensão de host foi propagada para os pontos definidos no Plano Mestre:

- **Execution Context:** `ExecutionScope` carrega `host_namespace`, `identity_partition_key` e `identity_material`;
- **Sequence Manager:** a chave de sequência inclui host para scopes V2 vinculados;
- **Idempotency:** a chave de emissão inclui host quando presente;
- **Archive/Audit:** identidade de archive, índice por documento e manifest incluem a partição universal; `FiscalDomainEvent` preserva o scope com host;
- **Outbox:** a identidade determinística de outbox inclui host;
- **Reconciliation:** comparação de escopo falha fechado quando o host diverge e o fingerprint inclui host;
- **Canonical serialization:** snapshots canônicos incluem `host_namespace` quando o scope é V2-bound;
- **Canonical document composition:** issuer e product profile são validados pela partição universal, impedindo composição cross-host.

Compatibilidade: quando `host_namespace` é `None`, materiais determinísticos legados preservam a composição V1 para evitar alteração silenciosa de hashes/tokens do baseline.

## Testes de isolamento

A suíte cobre explicitamente os namespaces:

- `fm.kordena`;
- `fm.iron`;
- `fm.vendedor-ia`;
- `fm.campaia`.

Com os mesmos IDs locais, os quatro produtos recebem partições, sequências, chaves de idempotência, identidades de outbox, archive/manifests e fingerprints independentes. Tentativas cross-host em reconciliação e composição de documentos falham fechado.

## Gate final certificado

- Gate SHA: `4fa8a2a8c74db65622099cd7dca43d2e8d19aea3`;
- GitHub Actions run: `34637445978` — **SUCCESS**;
- Install: PASS — `fm-fiscal-core==0.1.0.dev0`;
- Ruff: PASS;
- Mypy strict: PASS — **46 source files sem issues**;
- Pytest: PASS — **239 passed em 0.48s**;
- diff auditado contra a base V2-01 `00f8136fa2a2b2ad38e4752a8b55bdc542f239ae`;
- nenhuma regra tributária, cálculo fiscal, emissão, state machine ou provider contract foi alterado;
- CI retornado a `workflow_dispatch` após o gate verde.

## Riscos residuais e limites

- `ExecutionScope` legado continua construtível sem `host_namespace` exclusivamente por compatibilidade interna com o baseline; novas fronteiras externas do V2 não podem usar esse caminho.
- autenticação/autorização do caller será endurecida no V2-05;
- persistência durável de bindings será implementada no V2-07/V2-11;
- reconciliação ainda usa semântica de `sale/HostSettlement`; sua neutralização é objetivo do V2-03.

## Decisão

V2-02 está **CONCLUÍDO E CERTIFICADO**. O contrato universal de identidade multiproduto está estabelecido e V2-03 está liberado para construção do Fiscal Operation Contract genérico.
