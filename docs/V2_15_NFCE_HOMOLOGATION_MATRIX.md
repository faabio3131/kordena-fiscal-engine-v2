# V2-15 B3 — MATRIZ DE HOMOLOGAÇÃO NFC-e

Status: **CONCLUÍDA / CERTIFICADA INTERNAMENTE**  
Ambiente certificado: `HOMOLOGATION`.  
Homologação oficial externa: **NÃO DECLARADA / NÃO EXECUTADA**.

## Matriz técnica certificada

A matriz NFC-e foi exercitada com providers sintéticos configuráveis, jurisdição SP e operações `AUTHORIZE`, `QUERY` e `CANCEL`. A autorização exige CSC provider-scoped e certificado por referência opaca.

| Dimensão | Resultado interno |
|---|---|
| Documento | NFC-e |
| Ambiente | HOMOLOGATION only |
| Provider | resolvido por ProviderBinding durável |
| Jurisdição | resolução exata |
| Certificado | referência opaca por unidade/ambiente |
| Credenciais | referência provider-scoped |
| CSC | referência provider-scoped para AUTHORIZE |
| Runtime policy | timeout/retry/circuit durável |
| AUTHORIZE | tecnicamente certificado no harness sintético |
| QUERY | tecnicamente certificado no harness sintético |
| CANCEL | tecnicamente certificado no harness sintético |
| Cross-provider CSC | fail-closed; sem fallback |
| HOMOLOGATION → PRODUCTION | proibido; fail-closed |
| Persistência de segredo | somente referências opacas; sem material secreto |
| Evidência oficial externa | ausente / não alegada |

## Invariantes certificados

- CSC de provider A jamais cai para provider B;
- ausência de CSC do provider selecionado torna o readiness interno falso;
- credenciais e CSC permanecem isolados por tenant/unidade/ambiente/provider;
- escopo `PRODUCTION` é rejeitado pelo avaliador de homologação;
- persistência contém `SecretReference`, não segredo, senha ou chave privada;
- restart preserva configuração e isolamento;
- evidência técnica interna não promove homologação oficial.

## Gate B3

- SHA: `5507d4ea4c721af4ea77b576e162c684b551eb38`
- Run: `34776525383`
- Job: `103775530828`
- Install: PASS
- Ruff: PASS
- Mypy strict: PASS — **110 source files**
- Pytest: **605 PASS em 6.94s**
- CI restaurado posteriormente para `workflow_dispatch` only no commit `210c4f5ec2a47ce619c8eb4ca56c165454ce9d6f`.

## Evidência externa pendente

A certificação deste bloco é interna e usa dados sintéticos. Nenhum CSC real, certificado privado real, credencial real, endpoint produtivo ou emissão produtiva foi utilizado. A homologação oficial externa de provider/UF/operação continua dependente de execução real e evidência oficial correspondente.
