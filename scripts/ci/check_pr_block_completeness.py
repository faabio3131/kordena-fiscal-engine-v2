"""T2: verifica se uma PR marcada como pronta tem o bloco completo.

Le o evento do GitHub Actions (``GITHUB_EVENT_PATH``). Em Draft nao
reprova. Fora de Draft reprova quando a descricao:

* esta vazia ou curta demais;
* tem item de checklist sem marcar;
* nao declara prova de ponta a ponta nem ``NAO COMPROVADO``;
* se classifica como certificada sem link de execucao de CI.

A descricao e dado nao confiavel: so e lida, nunca executada.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

UNCHECKED = re.compile(r"^\s*[-*]\s+\[ \]", re.MULTILINE)
CERTIFIED = re.compile(r"DONE_CERTIFIED_(INTERNAL|OPERATIONAL)")
RUN_URL = re.compile(r"https://github\.com/[^\s)]+/actions/runs/\d+")
EVIDENCE_TOKENS = (
    "e2e",
    "ponta a ponta",
    "não comprovado",
    "nao comprovado",
)
MIN_BODY_CHARS = 200
FILES_WARNING_THRESHOLD = 40


def check_body(body: str | None) -> list[str]:
    """Devolve a lista de problemas da descricao; vazia significa OK."""
    text = body or ""
    problems: list[str] = []
    if len(text.strip()) < MIN_BODY_CHARS:
        problems.append(
            "Descrição vazia ou curta demais: preencha o modelo de PR."
        )
    pending = len(UNCHECKED.findall(text))
    if pending:
        problems.append(
            f"{pending} item(ns) do checklist sem marcar. "
            "PR pronta exige checklist 100% marcado."
        )
    lowered = text.lower()
    if not any(token in lowered for token in EVIDENCE_TOKENS):
        problems.append(
            "Declare a prova de ponta a ponta (E2E) ou escreva "
            "NÃO COMPROVADO onde faltar evidência."
        )
    if CERTIFIED.search(text) and not RUN_URL.search(text):
        problems.append(
            "Classificação certificada sem link de execução de CI "
            "(.../actions/runs/<id>). Sem evidência: "
            "IMPLEMENTED_NOT_CERTIFIED."
        )
    return problems


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("::error::GITHUB_EVENT_PATH ausente.")
        return 1
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pr = event.get("pull_request")
    if not pr:
        print("::notice::Evento sem pull_request; nada a verificar.")
        return 0
    changed = pr.get("changed_files") or 0
    if changed > FILES_WARNING_THRESHOLD:
        print(
            f"::warning::PR com {changed} arquivos alterados. "
            "Considere dividir o bloco em sub-blocos."
        )
    if pr.get("draft"):
        print("::notice::PR em Draft: verificação T2 não aplicada.")
        return 0
    problems = check_body(pr.get("body"))
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(
            "Volte a PR para Draft até o bloco estar completo "
            "(regra: um bloco, uma PR)."
        )
        return 1
    print("Bloco completo: descrição e checklist conferem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
