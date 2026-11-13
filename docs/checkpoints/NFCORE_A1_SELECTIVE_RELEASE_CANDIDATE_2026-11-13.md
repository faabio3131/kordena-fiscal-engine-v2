# FM NFCORE V1 — A1/SISTEM selective release candidate (2026-11-13)

**CURRENT:** Candidate DRAFT, baseada em `production@ea4bdd3bcb9b61e6522081a14e5cc9ad1ced9599`.
**TARGET:** Publicar com segurança apenas a correção de cadastro e consulta A1 para o piloto SISTEM em ambiente fiscal de homologação, sem promover indiscriminadamente a `main`.

## Justificativa técnica

Na auditoria GitHub, `main@2e7fc0f68a18e1259a37f64e37fe9c7a66416f3b` e `production` estão **divergentes**: main possui 51 commits à frente e production 15 commits próprios, com 118 arquivos diferentes na comparação. Uma promoção integral não é automaticamente segura. A PR #462 já está integrada em main, com CI pós-merge #2699 SUCCESS (4109 PASS, 3 SKIP, ZERO FAIL).

## Escopo seletivo — mesma aplicação e mesmas autoridades

- Adiciona `EncryptedA1Vault.inspect` à implementação AES-GCM já existente, sem criar segundo Vault, sem mudar chave e sem persistir material em claro.
- Adiciona GET `/v1/portal/certificates/a1/status` à mesma API, com sessão, autorização por unidade e ambiente homologation, leitura por tenant/CNPJ e resposta sem segredo.
- Corrige o filtro de arquivo PFX/P12 da mesma tela do Portal; após POST, exige GET readback independente com SHA-256 do certificado igual antes de afirmar recuperável.
- Reconciliado `compose.prod.yml` com o bind já observado no host `/var/lib/nfcore/vault` -> mesmo destino, read-write, `create_host_path: false`. **Não muda o arquivo Compose instalado no host automaticamente.**
- Reaproveita o mecanismo de exportação offline apenas dos registros A1 cifrados com manifesto SHA-256 e ensaio de restauração em caminho isolado. O ZIP não aplica uma segunda camada de criptografia; manter chave externa separada.
- Testes regressivos: PFX sintético, HTTP POST/GET, certificado inválido, RBAC, escopo e rejeição do tenant alheio, readback após novo Vault, UI/regex, backup e recuperação sintética, mantendo Bling opt-in.
- Não altera motor fiscal, adaptadores SP/MG, XSD, Auth, Worker, Bling, billing, schema/migrations ou qualquer credencial real.

## Gates antes de merge nesta PR (merge disparará deploy automático!)

1. CI do HEAD exato desta PR para base `production`: Python, frontend, E2E, Compose, Docker/API, segurança e testes operacionais. **NÃO declarar READY apenas por abrir PR.**
2. Read-only no host: conferir `.deployed`, imagem API corrente, `/opt/fm/nfcore/docker-compose.yml` efetivo, bind `/var/lib/nfcore/vault`, diretório UID10001:10001/0700, ocorrências `*.a1.enc`, saúde, DB e acesso a rollback. Não imprimir `.env` ou segredos.
3. Auditoria já demonstrou formato AES-GCM 32 bytes e master-key escrow em GPG, com três cópias idênticas e descriptografia offhost no Windows; manter intactas todas as cópias e passphrase separada.
4. Backup da VPS Contabo pode ajudar no rollback de host, mas não substitui prova granular de `*.a1.enc`. No preflight de 13/11/2026 o Vault tinha zero registros: **não inventar teste de backup real**. Após cadastro autorizado, exportar registros já cifrados, copiar para PC/USB, comparar hashes e realizar teste isolado.
5. Compatibilidade de Compose/código, readiness/smoke, retorno GET `absent` no escopo correto antes do piloto. **Nunca** mudar a autoridade do Vault nem gerar nova chave mestra.
6. Publicação somente com go/no-go humano e preflight acima; merge nesta PR implica pull de `production` em cron. Upload do verdadeiro PFX SISTEM deve ser feito pelo operador autorizado **somente em homologação**, com prova de POST + GET e sem cópia do PFX/senha em log/chat/GitHub.

## Classificação

- `MAIN_A1_CODE_CERTIFIED=PASS` (PR #462 / CI #2699).
- `PRODUCTION_A1_CANDIDATE_CI=WAITING` (esta PR).
- `PRODUCTION_DEPLOY=NOT_EXECUTED`.
- `SISTEM_REAL_A1_UPLOAD=NOT_EXECUTED`.
- `REAL_A1_CIPHERTEXT_OFFSITE_BACKUP=NOT_EXECUTED`.

## Evidências

- https://github.com/faabio3131/nf-core-v001/pull/462
- https://github.com/faabio3131/nf-core-v001/actions/runs/43472485445
- https://github.com/faabio3131/nf-core-v001/issues/447

A PR é apenas candidata. Não fazer merge ou publicar apenas para obter um screenshot; sem o preflight operacional, manter Draft.
