#!/usr/bin/env python3
"""Valida o cronograma/ledger canônico do FM NFCORE V1. Sem dependências externas."""
from __future__ import annotations

import re
import sys
from pathlib import Path

PLAN_STATES = {"RASCUNHO", "APROVADO", "EM EXECUCAO", "CONCLUIDO"}
ITEM_STATES = {
    "pendente",
    "em execução",
    "em execucao",
    "concluído",
    "concluido",
    "bloqueado interno",
    "bloqueado externo",
}
FIELDS = [
    "Estado",
    "Objetivo",
    "Depende de",
    "Entregar",
    "Não fazer",
    "Critério de aceite",
    "Verificação",
    "Riscos / não confirmado",
    "Decisões do dono pendentes",
    "Prova",
]
TASK_ID = re.compile(r"NFV1-P\d{2}-T\d{2}")
PR = re.compile(r"(https?://\S+/pull/\d+|\bPR\s*#\d+\b|#\d+)", re.I)
CI = re.compile(r"(https?://\S+/actions/runs/\d+|\bCI\s*#\d+\b)", re.I)
SHA = re.compile(r"\b[a-f0-9]{7,40}\b", re.I)

DEFAULT_LEDGER = "docs/NFCORE_V1_EXECUTION_LEDGER.md"
DEFAULT_SCHEDULE = "docs/NFCORE_V1_COMPLETION_MASTER_EXECUTION_SCHEDULE_2026-10-05.md"


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def read(path: str, errors: list[str]) -> str:
    p = Path(path)
    if not p.exists():
        fail(errors, f"{path} não existe")
        return ""
    return p.read_text(encoding="utf-8")


def schedule_tasks(text: str, errors: list[str]) -> list[str]:
    ids = re.findall(r"^###\s+(NFV1-P\d{2}-T\d{2})\s+—\s+.+$", text, re.M)
    if not ids:
        fail(errors, "cronograma não contém tarefas NFV1-Pxx-Tyy")
        return []
    if len(ids) != len(set(ids)):
        fail(errors, "cronograma contém IDs de tarefa duplicados")
    return ids


def ledger_items(text: str, errors: list[str]) -> list[tuple[int, str, str, str]]:
    parts = re.split(r"^###\s+(\d+)\.\s+(NFV1-P\d{2}-T\d{2})\s+—\s+(.+)$", text, flags=re.M)
    items: list[tuple[int, str, str, str]] = []
    for i in range(1, len(parts) - 3, 4):
        items.append((int(parts[i]), parts[i + 1], parts[i + 2].strip(), parts[i + 3]))
    if not items:
        fail(errors, "ledger não contém itens numerados")
        return []
    numbers = [n for n, _, _, _ in items]
    if numbers != list(range(1, len(items) + 1)):
        fail(errors, f"itens fora de ordem ou com número faltando: {numbers}")
    ids = [task_id for _, task_id, _, _ in items]
    if len(ids) != len(set(ids)):
        fail(errors, "ledger contém IDs duplicados")
    return items


def main(ledger_path: str = DEFAULT_LEDGER, schedule_path: str = DEFAULT_SCHEDULE) -> int:
    errors: list[str] = []
    ledger = read(ledger_path, errors)
    schedule = read(schedule_path, errors)
    if errors:
        for error in errors:
            print("ERRO:", error)
        return 1

    state_match = re.search(r"^- \*\*Estado:\*\*\s*(.+)$", ledger, re.M)
    plan_state = state_match.group(1).strip() if state_match else ""
    if plan_state not in PLAN_STATES:
        fail(errors, f"Estado do plano inválido: '{plan_state}' (use {sorted(PLAN_STATES)})")

    expected = schedule_tasks(schedule, errors)
    items = ledger_items(ledger, errors)
    actual = [task_id for _, task_id, _, _ in items]

    if expected != actual:
        missing = [x for x in expected if x not in actual]
        extra = [x for x in actual if x not in expected]
        if missing:
            fail(errors, f"tarefas do cronograma ausentes no ledger: {missing}")
        if extra:
            fail(errors, f"tarefas do ledger ausentes no cronograma: {extra}")
        if not missing and not extra:
            fail(errors, "ordem do ledger diverge da ordem canônica do cronograma")

    seen_not_done = False
    in_progress = 0

    for number, task_id, _title, body in items:
        body = body.split("\n## ")[0]
        for field in FIELDS:
            if not re.search(rf"\*\*{re.escape(field)}:\*\*", body):
                fail(errors, f"item {number} {task_id}: campo '{field}' ausente")

        box = re.search(r"^- \[( |x)\] \*\*Estado:\*\*\s*(.*)$", body, re.M)
        if not box:
            fail(errors, f"item {number} {task_id}: linha de Estado ausente")
            continue

        checked = box.group(1) == "x"
        item_state = box.group(2).strip().lower()
        if item_state not in ITEM_STATES:
            fail(errors, f"item {number} {task_id}: estado inválido '{box.group(2).strip()}'")

        completed = item_state.startswith("conclu")
        if checked != completed:
            fail(errors, f"item {number} {task_id}: checkbox e Estado divergem")

        if item_state.startswith("em execu"):
            in_progress += 1

        if completed:
            if seen_not_done:
                fail(errors, f"item {number} {task_id}: concluído após item anterior não concluído")
            proof = re.search(r"^- \*\*Prova:\*\*\s*(.*)$", body, re.M)
            proof_text = proof.group(1).strip() if proof else ""
            if not PR.search(proof_text):
                fail(errors, f"item {number} {task_id}: concluído sem PR em Prova")
            if not CI.search(proof_text):
                fail(errors, f"item {number} {task_id}: concluído sem CI em Prova")
            if not SHA.search(proof_text):
                fail(errors, f"item {number} {task_id}: concluído sem commit/SHA em Prova")
        else:
            seen_not_done = True

    if in_progress > 1:
        fail(errors, f"mais de uma tarefa em execução simultaneamente: {in_progress}")

    if plan_state == "CONCLUIDO" and seen_not_done:
        fail(errors, "plano CONCLUIDO com tarefa não concluída")

    if plan_state == "RASCUNHO":
        print("AVISO: plano em RASCUNHO; execução deve permanecer bloqueada")

    for error in errors:
        print("ERRO:", error)

    if not errors:
        next_item = next(
            (
                task_id
                for _, task_id, _, body in items
                if not re.search(r"^- \[x\] \*\*Estado:\*\*", body, re.M)
            ),
            None,
        )
        suffix = f"; próximo item: {next_item}" if next_item else "; todas as tarefas concluídas"
        print(f"OK: {len(items)} tarefa(s), plano em '{plan_state}'{suffix}")
    return 1 if errors else 0


if __name__ == "__main__":
    ledger_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LEDGER
    schedule_arg = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SCHEDULE
    raise SystemExit(main(ledger_arg, schedule_arg))
