# NFCore / Bling — matriz fiscal de construção interna (NF-e modelo 55)

**Data:** 2026-11-09. **Trilha:** PR #404 sobre a base cumulativa da PR #403.
**Estado:** implementação candidata em branch; **não homologada externamente / sem deploy / sem merge**.
**Autoridade:** a venda Bling fornece apenas fatos; alíquotas, CST/CSOSN, CFOP, vigência, NCM, FCP, IPI e RTC vêm da política fiscal com hash, regra versionada e escopo tenant/unidade.

## Escopo e prova esperada

A matriz testa o caminho suportado para **NF-e 55 de venda de mercadorias em homologação**, com A1 sintético e esquema XML oficial disponível no repositório.
"Suportado" significa que existe cálculo determinístico para o recorte indicado; não implica elegibilidade tributária de qualquer contribuinte, NCM, operação, localidade ou homologação SEFAZ.
O parser da política recusa parâmetros desconhecidos; regras nunca são inferidas do ERP. CST/CSOSN/combinações não implementadas falham fechadas.

| Família | Cenários internos suportados | Restrições fail-closed |
| --- | --- | --- |
| ICMS normal | CST 00, 10, 20, 30, 40, 41, 50, 70 | Redução explícita para 20/70; ST explícita para 10/30/70; não suporta pauta, base tabelada ou desoneração implícita |
| ICMS Simples | CSOSN 102, 103, 300, 400 | Não informa créditos fictícios; demais CSOSN exigem caminho especializado |
| ICMS-ST | CST 10/30/70: MVA na base líquida ou base líquida + IPI, ICMS-ST líquido do ICMS próprio | Sem ST automática, ST negativa ou base não modelada |
| FCP próprio/ST | Próprio em ICMS tributado 00/10/20/70; FCP-ST em 10/30/70 | Percentuais explícitos; FCP-ST requer ST; retenção histórica não pode ser inferida |
| DIFAL/FCP destino | Consumidor final não contribuinte interestadual ICMS 00, percentuais 4/7/12, participação destino 100% em 2026 | Sem inferência de UF/IE/partilha ou bases duplas, reduções e benefícios não modelados; DIFAL não duplica vNF |
| IPI saída | CST 50/99 ad valorem sobre base líquida e por unidade tributável; CST 51/52/53/54/55 como IPINT | Enquadramento e modo explícitos; IPI devido compõe vNF e a conciliação |
| PIS/COFINS | CST 01/02 percentual, 03 por quantidade; 04/06/07/08/09 não tributados; 49/99 Outras por zero/percentual/unidade | Não mistura valor por unidade e percentual; modo obrigatório para 49/99 |
| RTC 2026 | IBS/CBS CST 000 integral, 200 redução por UF/Mun/CBS, 410 sem incidência nem grupo padrão; totalizadores IBSCBSTot e vNFTot | Informativo 2026, cClassTrib coerente com CST e versão explicitada; outros regimes não são habilitados |
| Integração | Pedido revisado → regra → total → pagamento → XML → assinatura → XSD | Fail-closed por divergência de pedido, unidade, escopo, política, valores e assinatura |

## Parâmetros novos nesta revisão

- **icms_reduction_rate:** redução para CST 20/70, proibida nos demais.
- **pis_unit_amount / cofins_unit_amount:** valores por quantidade tributável com 4 casas; necessários para CST 03.
- **pis_other_mode / cofins_other_mode:** zero, percentage ou per_unit; obrigatórios nos CSTs 49/99.
- **rtc_uf_reduction_rate / rtc_municipal_reduction_rate / rtc_cbs_reduction_rate:** redução independente e explícita para CST 200; alíquota efetiva com 4 casas.
- **rtc_base_mode = non_taxed** para RTC CST 410; taxas IBS/CBS ausentes e modo informational_2026.
- ICMS CST 30 agora admite ST sem ICMS próprio; CST 70 reduz base própria com ST; IPI tributado aceita CST 99.
- Campos opcionais preservam políticas legadas, sem introduzir default tributário.

## Testes e evidência esperada

**Arquivo:** tests/test_bling_canonical.py. Matrizes assinadas com A1 sintético e validadas contra XSD oficial: ICMS 20/30/70, ST/FCP-ST, IPI 99, PIS/COFINS CST 03 por quantidade, 49/99 em três modalidades, RTC 200/410; cenários anteriores de IPI 50/51–55, DIFAL/FCP destino e RTC 000 permanecem.

Negativos: redução sem regra, ST ausente, modo misto de contribuição, CST 49/99 sem modalidade, RTC CST 200 sem reduções, CST 410 com tributo, cClassTrib divergente, valores/ordem/tenant incompatíveis, idempotência e XSD.

**Gate interno:** Ruff, Mypy e testes de integração no HEAD final; **gate remoto:** FM NFCORE V1 CI e NFCore Plan Governance com SUCCESS no SHA publicado. Teste sintético não é transmissão nem homologação fiscal externa.

## Limites deliberados — não concluir cobertura universal

**Ainda não suportados neste builder:** CST ICMS 60 (ST previamente retida), ICMS 51/90; CSOSN 101/201/202/203/500/900; FCP-ST histórico retido; crédito e restituição, isenções com desoneração, IPI de entrada, produtos/regimes especiais, DIFAL com bases diferenciadas ou outros regimes; RTC CST 010/011/220/221/222/400/510/515/550/620/800/810/811/820/830, monofasia, crédito e diferimento. Todos exigem modelagem e testes próprios; **não são silenciosamente convertidos para CST já suportado**.

Configuração externa posterior: políticas tributárias revisadas pela contabilidade e códigos oficiais vigentes, A1 real, autorização, homologação do ambiente e evidências de emissão por operação. Segredos não entram no repositório.

## Cadeia de PRs

- PR #403: ingresso, preparação canônica, portal, Worker, assinatura e retorno ao Bling.
- PR #404: incorpora a #403 e acrescenta conversão de unidade, cartão e esta matriz fiscal.
- Validar que não exista trabalho exclusivo na #403; evitar merges redundantes. **Este documento não autoriza merge nem deploy.**
