# Incidente técnico — XSD Nacional DPS 1.01 rejeita série fiscal válida
**Data:** 12/11/2026. **Owner do sequenciador:** PR #427. **Patch isolado:** PR #451, HEAD 334821b53ae3b562b72ae667f2a6c0968bfb2140. **Status:** REPRODUZIDO / NÃO CORRIGIDO / CI VERMELHA.

## Evidência efetiva, não estimativa
- [Workflow run #2420](https://github.com/faabio3131/nf-core-v001/actions/runs/43239881490) terminou **FAILURE** na job quality (ID 131257103085).
- Pytest terminou em **9 failed, 3792 passed, 3 skipped, 2 warnings**.
- As nove falhas incluem testes de builder/assinatura e integração de pré-auditoria; exceção: XmlSchemaValidationError. O validador rejeita o campo **serie** nos valores 1 e 17.
- O schema hash-pinado **NFSE_NACIONAL_1.01/tiposSimples_v1.01.xsd**, tipo TSSerieDPS, contém a restrição:
  
      <xs:pattern value="^0{0,4}\d{1,5}$"/>

- O builder em #451 escreve o campo **serie** com o valor de document.dps_series sem padding; para o Id da DPS usa a mesma série com zero-padding em cinco dígitos.

## Diagnóstico mínimo reproduzido
Um schema XSD mínimo validado localmente pelo mesmo motor lxml mostra:

| Regex do xs:pattern | '1' | '17' | '00001' | '^1$' |
|---|---|---|---|---|
| ^0{0,4}\d{1,5}$ | REJEITA | REJEITA | REJEITA | ACEITA |
| 0{0,4}\d{1,5} | ACEITA | ACEITA | ACEITA | REJEITA |

**Interpretação:** em XSD, a regex é implicitamente ancorada, e os caracteres ^/$ não são âncoras no sentido de PCRE. Isso explica a rejeição observada em CI. **Não prova** que a alteração local de um XSD oficialmente publicado seja permitida nem que outras validações 1.01 estejam corretas. Ver https://www.w3.org/TR/xmlschema/#regexs .

## Gate de correção sem regressão ou falsificação
1. Comparar a cópia hash-pinned com o ZIP/XSD oficial atualizado e verificar erratas, versão e vigência; preservar byte a byte o artefato original e SHA-256.
2. Reproduzir com validador XSD **independente**, além do ensaio lxml mínimo; validar as séries usadas em homologação segundo norma oficial, inclusive limites e zeros à esquerda.
3. Se for necessário um derivado corrigido/normalizado do schema, formalizar a exceção técnica, sua proveniência, diff e hash próprios; não alterar o original silenciosamente nem desativar validação.
4. Exigir congruência entre serie XML, série reservada pela UoW, ID de infDPS, número durável e identificador usado na consulta GET nacional; testar diferentes tenants/unidades, rollback, idempotência, concorrência, replay e recuperação.
5. Validar o XML final contra XSD aplicável e **verificar XMLDSig independentemente sobre infDPS final**; preservar fixture legacy 1.00 sem downgrade indevido da 1.01.
6. Só declarar PASS após CI completa no HEAD certificado da PR #427 e, novamente, na árvore de integração que também contém #450 e delta atual de #446.

## Mudanças já entregues pela #451 que NÃO fecharam o incidente
- Adicionou endNac/cMun/CEP no lugar exigido pelo endereço do XSD DPS 1.01;
- Explicitou versao=1.00 na fixture sintética legada de assinatura;
- Criou regressão para o endereço Nacional. 
Essas correções reduziram a classe de falhas observadas, mas **não corrigiram a rejeição da série**.

**Limites operacionais:** PR #427 permanece Draft/conflitante; v22 não aplicada; #451 não é certificada. Nenhum merge, deploy, autorização fiscal externa ou produção aprovado.
