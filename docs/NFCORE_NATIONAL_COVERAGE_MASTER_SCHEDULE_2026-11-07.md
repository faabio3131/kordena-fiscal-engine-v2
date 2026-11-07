# NFCore — Cronograma Mestre da Cobertura Nacional (NF-e/NFC-e/NFS-e por UF)

**Documento:** NFV1-NATCOV-MASTER-001
**Data:** 2026-11-07
**Status:** cronograma de governança/ordem de execução. NÃO é certificação técnica nem homologação.
**Autoridade:** decisão expressa do proprietário em 07/11/2026, registrada em `AGENTS.md`.
**Fonte superior:** GitHub CURRENT, código, CI e runtime. Este documento rege ORDEM; não substitui `docs/NFV1_NATIONAL_EXPANSION_EXECUTION_LEDGER_2026-11-05.md`, `docs/NFV1_NATIONAL_EXPANSION_MASTER_ARCHITECTURE_2026-11-05.md` nem `docs/NFV1_NATIONAL_EXPANSION_MASTER_EXECUTION_SCHEDULE_2026-11-05.md`, que continuam regendo escopo/critério técnico de cada bloco NAT-xx.

## Regra obrigatória de sequenciamento

1. **Uma UF por vez.** Nenhuma UF nova pode ser iniciada (pesquisa normativa, contrato, envelope, transporte, assinatura ou homologação) enquanto a UF ATIVA não estiver marcada `UF_100_COMPLETA` nesta tabela.
2. **UF completa inclui seus municípios em escopo.** Uma UF só é `UF_100_COMPLETA` quando: (a) NF-e 55 e NFC-e 65 estaduais estão com transporte mTLS/A1 comprovado, autorização, consulta, cancelamento e inutilização homologados; e (b) **todos os municípios daquela UF que estão no escopo comercial atual** (não todos os ~5.570 municípios do Brasil — ver critério de escopo abaixo) têm NFS-e (Nacional ou municipal/ABRASF, conforme o contrato do município) com envelope, assinatura, transmissão e consulta homologados.
3. **Escopo municipal por UF:** por padrão, escopo = capital da UF + municípios onde já existe evidência de demanda/piloto registrada em ledger. Qualquer município fora desse escopo entra como `FORA_DE_ESCOPO_ATUAL`, não bloqueia a UF, mas também não pode ser trabalhado antes da UF ativa fechar.
4. **Não é retrabalho interromper para corrigir regressão da UF ativa** — isso continua dentro da mesma UF. É proibido, sim, abrir pesquisa/código de outra UF antes da ativa fechar.
5. **Pré-condição para esta trilha começar/retomar:** por decisão do proprietário de 07/11/2026, a Expansão Nacional só é retomada depois que (a) o piloto com o escritório contábil de segunda-feira estiver destravado, e (b) tudo que já está em construção/funcionando no NFCore (RTC-04 interno, blocos BLD-03 a BLD-08) estiver 100% pronto. Ver banner `AGENTS.md` de 07/11/2026.
6. Nenhuma homologação externa real, certificado real de cliente, migration produtiva ou deploy é autorizado por este cronograma; cada UF exige autorização específica para esses itens quando chegar sua vez.

## Critério de aceite "UF_100_COMPLETA" (checklist por UF)

- [ ] Transporte estadual mTLS com A1 elegível comprovado (não apenas GET WSDL sem credencial).
- [ ] NF-e 55: emissão, autorização, consulta, cancelamento, inutilização — com SHA/PR/CI no HEAD exato.
- [ ] NFC-e 65 (quando aplicável na UF): idem + CSC/QR code quando exigível.
- [ ] Para cada município em escopo: contrato de envelope identificado (Nacional vs ABRASF 1.x/2.03/2.04/layout próprio) com fonte oficial citada.
- [ ] Para cada município em escopo: envelope implementado, assinado (A1 do escopo), transmitido e consultável em ambiente de homologação do provedor.
- [ ] Testes dirigidos + CI verde no SHA exato para toda a UF (estadual + municipal).
- [ ] Checkpoint de fechamento registrado no ledger NAT com evidência, sem pendência aberta.
- Só então a UF muda de estado e a próxima pode ser iniciada.

## Ordem de execução das UFs

> A ordem abaixo é uma PROPOSTA baseada no estado real de evidência em 07/11/2026 (não em preferência arbitrária). O proprietário pode reordenar a qualquer momento; até reordenar, esta é a sequência vigente.

| Ordem | UF | Estado em 07/11/2026 | Município(s) em escopo inicial | Justificativa da posição |
|---|---|---|---|---|
| **1 (ATIVA)** | **MG — Minas Gerais** | `NAT-UF-MG IMPLEMENTING/PARTIAL` — autorização NF-e 55 em construção (NAT-03), reutiliza transporte SOAP/Vault existente; falta validador XSD confiável, NFC-e 65, e módulo NFS-e de Belo Horizonte | Belo Horizonte (BHISS, contrato "Emissor Nacional" já identificado) | É a UF com mais progresso real de autorização estadual já registrado no ledger (`docs/NFV1_NAT03_MG_AUTHORIZATION_CONTINUITY_2026-11-05.md`); terminar o que já está em andamento antes de abrir outra. |
| 2 | SP — São Paulo | Município capital com preparo de lote avançado (`prepare_paulistana_test_batch`, XSD 02-7 pinado, SHA conferido), mas SEM módulo estadual (NF-e/NFC-e) iniciado para SP e sem WSDL de homologação confirmado | São Paulo capital (Nota Paulistana) | Maior volume de trabalho municipal já investido de qualquer UF; mas como UF ainda não tem estadual iniciado, fica atrás de MG, que já tem os dois eixos em andamento. |
| 3 | RJ — Rio de Janeiro | Transporte SVRS pesquisado para NF-e/NFC-e (inconclusivo, falha de handshake sem A1); município Rio de Janeiro mapeado só como evidência de contrato ("Nota Carioca") | Rio de Janeiro capital | Pesquisa normativa existente, zero código. |
| 4 | RS — Rio Grande do Sul | Transporte SVRS pesquisado (mesmo transporte de RJ/MG via SVRS), zero módulo de autorização | A definir quando chegar a vez | Compartilha transporte SVRS já pesquisado; decisão de incluir/mesclar com MG/RJ fica para quando chegar a vez. |
| 5 | PR — Paraná | Município Curitiba mapeado só como evidência de contrato | Curitiba | Pesquisa normativa parcial, zero código. |
| 6 | MT — Mato Grosso | Município Cuiabá mapeado só como evidência de contrato | Cuiabá | Pesquisa normativa parcial, zero código. |
| 7 | MS — Mato Grosso do Sul | Município Campo Grande mapeado como evidência, mas WSDL municipal não resolveu por DNS na última tentativa | Campo Grande | Pesquisa normativa parcial, zero código, pendência técnica extra (DNS). |
| — | Demais 21 UFs + ~5.500 municípios restantes | `NOT_STARTED` | — | Fora de escopo até reavaliação do proprietário após a UF nº 7. |

## Próxima ação concreta (quando a trilha for retomada)

1. Confirmar GitHub CURRENT e reconciliar com `docs/NFV1_NAT03_MG_AUTHORIZATION_CONTINUITY_2026-11-05.md` antes de qualquer código.
2. Fechar NAT-03 para MG: validador XSD confiável + autorização NF-e 55 com CI no HEAD exato.
3. Implementar NFC-e 65 de MG (mesma UF, mesmo transporte).
4. Implementar módulo NFS-e de Belo Horizonte (município em escopo de MG).
5. Rodar o checklist `UF_100_COMPLETA` inteiro para MG antes de tocar em qualquer arquivo/pesquisa de SP, RJ ou qualquer outra UF.
6. Só depois disso, abrir a UF nº 2 (SP) por este mesmo cronograma.

## Registro de mudanças

- **2026-11-07:** criação do cronograma, com MG definida como UF ativa (proposta) por ser a que já tinha mais evidência de progresso real na reconciliação de 05/11/2026.
