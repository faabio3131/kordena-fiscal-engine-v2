# V2-02 — Host Namespace + Fiscal Account Binding

Status: **EM EXECUÇÃO**  
Data: 2026-09-11

## Objetivo

Eliminar colisões de identidade entre produtos consumidores e estabelecer uma fronteira explícita entre identidades externas de SaaS e o escopo fiscal interno.

## Princípio

O FM Fiscal não pode assumir que `tenant_id=123` do Kordena representa a mesma organização que `tenant_id=123` do Iron ou de qualquer outro consumidor.

Toda identidade externa deve ser qualificada por um **Host Namespace**.

```text
host namespace + external tenant + external unit
                    ↓
          Fiscal Account Binding
                    ↓
      fiscal account + fiscal unit
                    ↓
             FM Fiscal Core
```

## Invariantes

1. `HostNamespace` identifica o sistema consumidor, não o cliente fiscal.
2. `HostScope` é sempre composto por namespace + tenant externo + unidade externa.
3. A chave de binding é exata; não existe fallback implícito entre hosts, tenants ou unidades.
4. Dois produtos podem usar o mesmo `tenant_id`/`unit_id` externo sem colisão desde que tenham namespaces distintos.
5. `FiscalAccountBinding` mapeia a identidade externa para IDs internos canônicos do FM Fiscal.
6. O Core não recebe entidades privadas do host.
7. O binding não concede autorização; autenticação S2S e workload identity pertencem ao V2-05.
8. Persistência durável e lifecycle operacional de bindings pertencem ao V2-07/V2-11.

## Convenção de namespace

Formato canônico: lowercase ASCII com segmentos separados por `.`, `-` ou `_` quando necessário.

Exemplos:

- `fm.kordena`
- `fm.iron`
- `fm.vendedor-ia`
- `fm.campaia`
- `partner.erp-x`

O namespace deve ser estável e não conter tenant, unidade, ambiente ou credenciais.

## Escopo desta fase

V2-02 introduz apenas os value objects e contratos puros de binding, mais testes de isolamento. Não adiciona banco, API HTTP, secrets, permissões, provisioning nem integrações reais.

## Gate

- Host namespace validado e normalizado;
- Host scope possui chave canônica sem colisão cross-product;
- binding resolve exclusivamente o escopo exato;
- resolução produz `ExecutionScope` interno sem carregar IDs externos como autoridade fiscal;
- testes explícitos de isolamento cross-host;
- Ruff PASS;
- Mypy strict PASS;
- Pytest PASS;
- diff auditado sem regressão fiscal.
