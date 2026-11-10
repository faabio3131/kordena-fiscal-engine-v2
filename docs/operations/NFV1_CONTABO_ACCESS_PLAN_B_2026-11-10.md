# NFCore — Plano B de acesso e auditoria Contabo sem Desktop Commander

**Data:** 2026-11-10. **Prioridade:** preparar homologação fiscal de 11/11.
**Estado:** implementação candidata; nenhum acesso SSH, chave, ambiente GitHub ou mudança no host é confirmado por este documento.
**Servidor alvo conhecido:** Contabo `vmi3692211`, aplicação em `/opt/fm/nfcore`.
**Autoridade:** produção é o host real; o código e a CI do GitHub não provam estado do host.

## Objetivo e limites

Substituir a dependência operacional do Desktop Commander por canais permanentes:
1. **SSH local** pelo computador do operador: alternativa imediata, sem conector pago.
2. **GitHub Actions manual com SSH restrito:** uma auditoria de host com saída sanitizada, por chave dedicada e comando forçado; não é um deploy.
3. **Contabo VNC:** recuperação de emergência quando o SSH está indisponível. A Contabo exige cliente VNC externo e ativação pode exigir reboot; não habilitar nem reiniciar por conveniência em véspera de homologação.

Este plano não cria API, worker, persistência, agente ou credencial paralela. Não instala software de gestão remota de terceiros no host.

## A. Diagnóstico imediato via SSH local — sem automação/credencial nova

No computador já autorizado, usar Windows PowerShell ou terminal Unix:

```powershell
ssh -V
ssh fmadmin@<IP_OU_HOST_VALIDADO_DA_VPS>
```

`fmadmin` é a identidade registrada nos runbooks, **não prova** que a chave local já existe. O endereço vem do painel Contabo, nunca de um IP inventado no chat. Em primeira conexão, confirmar a impressão digital do host por meio independente antes de aceitá-la. A senha/chave privada nunca é enviada para ChatGPT.

No shell do host, **comandos somente leitura**:

```bash
printf 'DEPLOYED='
sed -n 's/^SHA=//p' /opt/fm/nfcore/.deployed
printf 'FAILED_SHA_PRESENT='
test -s /opt/fm/nfcore/.failed-sha && echo YES || echo NO
printf 'BRANCH='
git -C /opt/fm/nfcore/src rev-parse HEAD
printf 'DEPLOY_LOG_MARKER='
grep -E 'DEPLOY OK [a-f0-9]+' /opt/fm/nfcore/deploy.log | tail -n 1
printf 'API='
docker inspect --format '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' nfcore-api
printf 'PORTAL='
docker inspect --format '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' nfcore-portal
printf 'DATABASE='
docker inspect --format '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}' nfcore-db
```

NÃO executar `docker compose up`, `deploy.sh` sem `--check`, migrations, `cat .env` ou comandos que revelem Docker environment/segredos. Não publicar a saída de `docker inspect` completa, IDs de tokens, arquivos A1 ou logs brutos de aplicação. Se `fmadmin` não tiver acesso de leitura ao Docker, interromper e usar um operador autorizado; não elevar privilégios automaticamente.

O diagnóstico do Bling completo está em `deploy/contabo/bling-operational-host-audit.sh` (main). Pode ser executado no host **apenas após obter uma cópia revisada, conferir seu SHA-256 e confirmar permissões**, com o SHA exato da branch `production`. Ele exige que a API e o Worker Bling estejam ativados para retornar PASS; se apenas o teste fiscal direto estiver em escopo, classificar essas pendências separadamente, não fingir que o Bling foi homologado.

## B. Canal auditável e reutilizável: GitHub Actions → SSH com comando forçado

Workflow proposto: `.github/workflows/contabo-readonly-host-audit.yml`.

**Pré-condições de ativação humana, fora do repositório:**
- Aprovar formalmente uso da identidade de auditoria no host, validando privilégios Docker necessários. Evitar root SSH. Acesso ao socket Docker equivale a privilégios elevados: não delegá-lo indiscriminadamente.
- Criar um novo par Ed25519 exclusivo para esta auditoria em equipamento seguro; **não reutilizar** chave pessoal ou credencial de deploy e **não publicá-la** no repositório ou no chat.
- Instalar os arquivos revisados `host-audit-command.sh` e `bling-operational-host-audit.sh` no diretório **`/opt/fm/nfcore/audit/`**, ownership `root:root`, sem symlinks, e modo `0755`. A instalação inicial exige aprovação específica e conferência do SHA-256 contra o commit aprovado. **Esta PR NÃO instala os arquivos no host.**
- Restringir a chave pública em `authorized_keys` com `restrict,command="/opt/fm/nfcore/audit/host-audit-command.sh"`. Isso veta shell arbitrário, encaminhamentos e pseudo-terminal para a chave de auditoria. Conservar a chave SSH de acesso de emergência do operador separada.
- No GitHub, criar environment `nfcore-contabo-audit` e, quando disponível no plano, exigir revisão humana e limitar execuções à branch `main`. Configurar os segredos **nesse environment**, não em arquivos versionados:

| Nome | Conteúdo protegido |
|---|---|
| `NFCORE_AUDIT_HOST` | IP ou hostname validado da VPS, sem porta ou protocolo |
| `NFCORE_AUDIT_USER` | Conta SSH de auditoria com a chave pública restrita |
| `NFCORE_AUDIT_SSH_PRIVATE_KEY` | Chave privada exclusiva, sem passphrase, protegida no GitHub |
| `NFCORE_AUDIT_KNOWN_HOSTS` | Chave pública do **servidor SSH** validada fora da conexão; nunca confiar apenas em `ssh-keyscan` |

**Como acionar quando estiver configurado:** GitHub → Actions → `NFCore Contabo Read-only Host Audit (Plan B)` → Run workflow na branch `main`, informando o SHA completo **atual** de `production`. O workflow valida esse SHA no GitHub, a assinatura SSH do host previamente pinada e o digest SHA-256 do script de auditoria instalado no host. Toda requisição que falhar nesses gates retorna `NO_GO` e não tenta um deploy.

O comando forçado autoriza **somente** `nfcore-audit <SHA_40> <SHA256_SCRIPT_64>`; o script instalado é root-owned e a chave SSH não executa código fornecido pelo chamador. O workflow não faz checkout da branch `production` para execução remota, não envia arquivos executáveis, não habilita modos privilegiados do Docker e não imprime segredos.

**Evidência:** workflow com head `main`, SHA de `production`, status `DEPLOY_SHA_EXACT`, `SCHEMA_PRODUCTION_GUARD`, backups, API/Portal, Bling e `RESULT`. A saída de SSH é filtrada para chaves e estados permitidos; nem o stdout bruto nem o stderr bruto são publicados.

**Limite do resultado:** `HOST_GATES_PASS_EXTERNAL_STILL_UNVERIFIED` prova somente preflight local do host. OAuth Bling real, política do CNPJ/unidade do teste, A1 e resposta da SEFAZ permanecem gates próprios.

**Custos:** não há créditos do Desktop Commander envolvidos. Execuções GitHub Actions podem consumir minutos/recursos do plano contratado; confirmar limites e política da conta, sem pressupor custo zero ilimitado.

## C. Contingência VNC oficial da Contabo

Na indisponibilidade de SSH, entrar em `my.contabo.com`, localizar a VPS e verificar `Servers & Hosting → VPS/VDS → More → VNC control`. Segundo a documentação oficial, VNC exige um aplicativo cliente externo e a habilitação pode exigir reinicialização. Não reiniciar a VPS nem habilitar VNC em horário produtivo sem aprovação e janela segura. Preferir SSH se funcional.

Referências oficiais:
- https://contabo.freshdesk.com/en/support/solutions/articles/103000337806-how-do-i-enable-disable-vnc-for-my-server-
- https://contabo.freshdesk.com/en/support/solutions/articles/103000407800-how-to-connect-to-your-server-using-vnc

## Critério de aceite do Plano B

- [ ] Comandos SSH de somente leitura executados na VPS correta, com identidade do host verificada.
- [ ] Instalação root-owned dos dois scripts e digest pinado ao commit revisado (aprovação específica).
- [ ] Chave SSH exclusiva e restringida por forced command; sem shell interativo e sem forwardings.
- [ ] GitHub environment e secrets configurados fora do Git, com aprovação quando suportada.
- [ ] Execução do workflow em `main`, com SHA `production` correto, PASS/NO_GO real (não simulação).
- [ ] Audit trail persistente e classificação de erros sem informações confidenciais.
- [ ] Após verificação do host, gates separadamente autorizados para migration, OAuth, Worker e A1/homologação.

**NO-GO enquanto os itens não tiverem evidência.** Nenhuma parte do Plano B autoriza merge na branch `production`, mudança em firewall/DNS, instalação de credenciais ou emissão fiscal.
