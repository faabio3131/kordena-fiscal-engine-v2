#!/bin/sh
set -eu

command="${1:-}"
case "$command" in
  contract)
    echo "nfcore-staging-driver-v1"
    exit 0
    ;;
  *)
    echo "staging deploy driver: BLOCKED_EXTERNAL real provider driver is not provisioned"
    exit 42
    ;;
esac
