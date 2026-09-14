# V2-15 B2 — MATRIZ DE HOMOLOGAÇÃO NF-e

Status: **CONCLUÍDA / CERTIFICADA INTERNAMENTE**  
Ambiente certificado: `HOMOLOGATION`.  
Homologação oficial externa: **NÃO DECLARADA / NÃO EXECUTADA**.

## Matriz técnica certificada

A matriz NF-e foi exercitada com provider sintético configurável, jurisdição SP e operações `AUTHORIZE`, `QUERY` e `CANCEL`. O objetivo é certificar o contrato e o comportamento do Core, não declarar homologação oficial de um provider real.

| Dimensão | Resultado interno |
|---|---|
| Documento | NF-e |
| Ambiente | HOMOLOGATION only |
| Provider | resolvido por ProviderBinding durável |
| Jurisdição | resolução exata, sem fallback entre UFs |
| Certificado | referência opaca por unidade/ambiente |
| Credenciais | referência provider-scoped |
| Runtime policy | timeout/retry/circuit durável |
| AUTHORIZE | tecnicamente certificado no harness sintético |
| QUERY | tecnicamente certificado no harness sintético |
| CANCEL | tecnicamente certificado no harness sintético |
| Rejeição fiscal | normalizada sem retry indevido |
| Unknown delivery em AUTHORIZE | não repete cegamente; exige reconciliação |
| Restart | configuração permanece resolvível |
| Evidência oficial externa | ausente / não alegada |

## Invariantes certificados

- NF-e não cai para provider de outra jurisdição;
- autorização com entrega ambígua realiza uma única tentativa e sinaliza reconciliação;
- `AUTHORIZE` permanece retry condicional e `QUERY` permanece safe-retry;
- rejeição fiscal normalizada não é tratada como indisponibilidade do provider;
- evidência técnica interna não promove homologação oficial;
- nenhum endpoint produtivo é usado.

## Gate B2

- SHA: `ec5a00dff67710a2d20e7931665e15e94d6de77b`
- Run: `34776372599`
- Job: `103775124030`
- Install: PASS
- Ruff: PASS
- Mypy strict: PASS — **110 source files**
- Pytest: **601 PASS em 22.18s**
- CI restaurado posteriormente para `workflow_dispatch` only.

## Evidência externa pendente

Esta matriz é uma certificação interna do FM Fiscal Core. Provider/UF/operação só poderá ser marcado como oficialmente homologado quando houver execução real no ambiente oficial externo e evidência correspondente. Até lá, o estado externo permanece explicitamente pendente e não bloqueia a certificação técnica interna do contrato.
