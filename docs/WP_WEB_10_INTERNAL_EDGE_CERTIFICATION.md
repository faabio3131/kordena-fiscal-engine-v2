# WP-WEB-10 — Internal Edge Security Certification

Status: **INTERNAL_EDGE_READY / BLOCKED_EXTERNAL**

## Certified internal scope

The repository-controlled, provider-neutral portion of WP-WEB-10 is implemented and fail-closed:

- explicit trusted-host enforcement;
- explicit CORS allowlist with production wildcard rejection;
- API Content-Security-Policy and defensive response headers;
- HSTS policy for production-like HTTPS profiles;
- rejection of spoofed forwarding headers from untrusted peers;
- explicit trusted-proxy CIDR validation;
- rejection of `0.0.0.0/0` / `::/0` style global proxy trust in production-like profiles;
- Uvicorn implicit proxy-header trust disabled;
- production profile requires explicit public hostname authority;
- hardened static portal server with browser security headers;
- provider-neutral environment contract for hostname, origins, trusted hosts and proxy ranges;
- tests for host, CORS, CSP/security headers, HSTS, proxy spoofing, invalid/global proxy networks and portal headers.

## Code gate evidence

Code/prompt HEAD `f891b51f4e2842dcdff7eef0a1a290b8998de69f` completed CI run `35014670042` with `success` across the full quality/security/recovery matrix, including secret scan, migration policy, Ruff, Mypy, Pytest, dependency audits, frontend gates, critical E2E, compose validation, runtime image build, non-root checks, insecure-production rejection, API/worker/portal smokes, image secret inspection, vulnerability policy, SBOM generation, PostgreSQL backup/restore rehearsal and restored-database readiness.

The final documentation HEAD must also complete its own CI successfully before merge.

## External boundary — deliberately not claimed

The repository does **not** claim any of the following as provisioned or validated:

- ownership/use of an official production domain;
- DNS records at a real DNS provider;
- a real public ingress/CDN/reverse proxy;
- real TLS certificate issuance, installation or renewal;
- real HTTP-to-HTTPS edge redirect;
- real WAF or provider rate-limiting policy;
- real cloud network/production isolation;
- real production PostgreSQL or Secret Manager endpoints;
- real public production endpoint smoke.

Those items depend on real domain/cloud/network/credential inputs and remain `BLOCKED_EXTERNAL` until objective evidence exists.

## Readiness decision

`INTERNAL_EDGE_READY / BLOCKED_EXTERNAL`

This classification authorizes merge of the internally complete provider-neutral preparation. It does not authorize a production deployment and does not change fiscal production readiness or human Go/No-Go authority.
