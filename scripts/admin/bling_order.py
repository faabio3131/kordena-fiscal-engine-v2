"""Trusted operator CLI for Bling order inspection and prepared-document handoff.

Uses configured PostgreSQL and the exact installation binding. Does not create
schemas, credentials, certificates or tax decisions. Never accepts webhook XML.
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from kordena_fiscal.application.bling_processing import BlingProcessingHandler
from kordena_fiscal.persistence.postgres import PostgresFiscalDatabase
from kordena_fiscal.runtime.bling_preparation import BlingSalePreparer
from kordena_fiscal.runtime.bling_worker import build_bling_orders, build_bling_worker
from kordena_fiscal.runtime.config import RuntimeSettings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "status",
            "prepare",
            "approve-prepared",
            "select-snapshot",
            "retry-event",
            "retry-status",
            "retry-issuance",
            "reconcile",
        ),
    )
    parser.add_argument("reference", help="order ID, or inbox entry ID for retry-event")
    parser.add_argument("--request-id")
    parser.add_argument("--review-file", help="reviewed preparation JSON, no secret material")
    parser.add_argument("--snapshot-sha256")
    parser.add_argument("--document-id")
    parser.add_argument("--actor-id")
    args = parser.parse_args()
    if args.action == "approve-prepared" and not all(
        (
            args.snapshot_sha256,
            args.document_id,
            args.actor_id,
        )
    ):
        parser.error("approval requires --snapshot-sha256, --document-id and --actor-id")
    settings = RuntimeSettings.from_environ()
    if settings.persistence_backend != "postgres" or settings.database_url is None:
        parser.error("durable PostgreSQL configuration is required")
    database = PostgresFiscalDatabase(settings.database_url)
    try:
        database.require_current_schema()
        orders = build_bling_orders(database, os.environ)
        if args.action == "retry-event":
            if not args.request_id or not args.actor_id:
                parser.error("retry requires --request-id and --actor-id")
            job_id = orders.retry_event(
                args.reference,
                request_id=args.request_id,
                actor_id=args.actor_id,
            )
            print(json.dumps({"job_id": job_id}))
            return 0
        order_id = int(args.reference)
        if args.action == "prepare":
            if not args.review_file or not args.actor_id:
                parser.error("preparation requires --review-file and --actor-id")
            with Path(args.review_file).open("rb") as stream:
                raw = stream.read(65_537)
            if len(raw) > 65_536:
                parser.error("review file exceeds 64 KiB")
            document_id = BlingSalePreparer(os.environ).prepare(
                orders, order_id, json.loads(raw), args.actor_id,
            )
            print(json.dumps({"document_id": document_id}))
            return 0
        if args.action in {"retry-status", "retry-issuance"}:
            if not args.request_id or not args.actor_id:
                parser.error("retry requires --request-id and --actor-id")
            retry = orders.retry_status if args.action == "retry-status" else orders.retry_issuance
            print(
                json.dumps(
                    {
                        "job_id": retry(
                            order_id,
                            request_id=args.request_id,
                            actor_id=args.actor_id,
                        )
                    }
                )
            )
            return 0
        if args.action == "approve-prepared":
            result = orders.approve_prepared(
                order_id,
                snapshot_sha256=args.snapshot_sha256,
                document_id=args.document_id,
                actor_id=args.actor_id,
                now=datetime.now(UTC),
            )
        elif args.action == "select-snapshot":
            if not args.snapshot_sha256 or not args.actor_id:
                parser.error("review requires --snapshot-sha256 and --actor-id")
            result = orders.select_snapshot(
                order_id,
                snapshot_sha256=args.snapshot_sha256,
                actor_id=args.actor_id,
                now=datetime.now(UTC),
            )
        elif args.action == "reconcile":
            composition = build_bling_worker(database, os.environ)
            handler = composition.handlers["process_bling_order"]
            assert isinstance(handler, BlingProcessingHandler)
            result = handler.reconcile(order_id)
        else:
            result = orders.get(order_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        # Credentials and provider errors must never reach operator output.
        print(json.dumps({"error": "BLING_COMMAND_REFUSED"}))
        return 1
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
