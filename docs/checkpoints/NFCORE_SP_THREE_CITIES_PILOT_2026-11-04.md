# NFCore - three SP municipalities, three document types

2026-11-04. CURRENT main 16b320e, production afc2d6d.
Cajamar 3509205, Sao Bernardo do Campo 3548708, Sao Paulo 3550308.

The customer's accountant will test with his own client-company certificates.
FM Tecnologia is never the issuing taxpayer.

Official NFS-e update 2026-10-29: for tax regime Simples Nacional,
the national issuer is mandatory for service competence starting 2026-11-01,
regardless of municipal legacy systems.
https://www.gov.br/nfse/pt-br/noticias/nfs-e-informa-diretrizes-sobre-a-obrigatoriedade-da-emissao-da-nfs-e-nacional-para-optantes-do-simples-nacional/

SP capital also documents the 2026-11-01 change:
https://prefeitura.sp.gov.br/web/fazenda/w/usoemissornacional
National NFS-e API restrictive test and production:
https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao
NFS-e schemas and manuals (current):
https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual
Sao Paulo municipal legacy WebService manual, relevant to eligible historical/other regimes:
https://notadomilhao.sf.prefeitura.sp.gov.br/manuais-reforma-tributaria/
SEFAZ SP NF-e:
https://portal.fazenda.sp.gov.br/servicos/nfe/Paginas/URL-WEBSERVICES.aspx
SEFAZ SP NFC-e:
https://portal.fazenda.sp.gov.br/servicos/nfce/Paginas/WebServices.aspx

Current code only classifies a logical channel for 3 pilot municipalities and
nfe/nfce/nfse, considering UF, tax regime and competence. A channel does NOT
grant transmission or certify any provider. Non-Simples service taxpayers and
retroactive service competence require independent official municipal evidence.

Target remains: secure A1 certificate vault provisioning by CNPJ and tenant,
mTLS XMLDSig, official providers with precise layouts, official homologation,
idempotent issue/query/cancel/recovery, RBAC, tenant isolation, staging E2E
and separately authorized production. No invented fiscal approvals.
