# NFCore — promoção Web e correção de conexão ociosa

Data: 05/11/2026. Autorização: Diretor pediu conferir, integrar, promover e subir Web.
CURRENT: PR #362 integrada em main ab364903e6a760f73a0d8931d9265c33d55adab8.
PR #360 incorporada pela mesma cadeia; #361 fechada supersedida, commits preservados.
production/Contabo ainda 5f2641d219c481fafba8741017cb533be19e57f5 na auditoria inicial.
PR #358 foi reescrita como promoção code-only completa, não apenas documentação.
Sem migration, DNS, credencial nova, provider binding ou emissão oficial.

## Auditoria operacional

Contabo vmi3692211: API, Portal e PostgreSQL healthy, 151 GiB livres.
Migration policy PASS e production schema READ_ONLY CURRENT, versões 1..19/Cakto2.
Nenhuma migration necessária/aplicada. Merge-tree main/production sem conflito.
Refs remotas do servidor foram atualizadas explicitamente: fetch nominal sem refspec
não atualizava origin/main de forma confiável para esta comparação.
Gates CI/Gov da PR #362 SUCCESS no HEAD a4cca63.

## Problema bloqueador do preflight Web

Preflight real retornou login_protected=false porque GET anônimo de bootstrap
recebia 502. Chamada seguinte idêntica retornou 401 SESSION_REQUIRED.
Logs sanitizados do Portal confirmaram três respostas 502 na janela investigada.
O proxy guardava sockets HTTP em pool sem idade máxima; API usa keep-alive 30s.
Hipótese causal sustentada por código e teste TCP: socket ocioso expira no upstream,
mas continuava sendo selecionado como reutilizável na primeira chamada seguinte.

## CURRENT → TARGET / impacto congelado

Adicionar timestamp monotônico ao pool em memória, expiração de ociosidade 10s
(menor que timeout 30s da API), descarte de socket já fechado e nova conexão antes
de enviar a requisição. Sem retry de GET ou mutações, sem novo router/auth/tenant.
Não aumentar timeout para mascarar falha; não mudar gate login_protected.
Apenas scripts/serve_portal.py, testes direcionados e este checkpoint.

## Validação

Pool saudável continua reutilizado; socket expirado/fechado é descartado.
Teste TCP local modela upstream encerrando conexão após resposta: primeira chamada
posterior ao limite recebe 401 em conexão nova; exatamente duas requisições para
duas intenções, sem replay. Suíte de segurança do Portal e preflight incluídas.
Ruff e Mypy direcionado do script PASS. Resultado final de testes/CI/SHA na PR.

## Promoção governada

Não promover #358 antes de integrar este fix e obter CI/Gov no HEAD final.
Deploy canônico acompanha production, faz backup verificado e schema guard read-only.
Pós-deploy: conferir SHA, DEPLOY OK, containers/TLS, proteção sem sessão e bootstrap
após intervalo maior que timeout de keep-alive, sem aquecimento prévio.
Histórico técnico/operacional final será registrado na PR de release.

## Limite do aceite

Publicação do código e estabilidade Web não certificam preparação/jornadas fiscais
MG completas, provider binding, NFC-e, NFS-e BH, regras/RTC ou homologação contábil.
Esses estados não podem ser promovidos por health ou CI. Nenhuma emissão real.
