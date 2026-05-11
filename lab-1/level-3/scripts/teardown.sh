#!/bin/bash
set -euo pipefail

CLUSTER_NAME="lab1-l3"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== Level 3 — Teardown ==="

pkill -f "kubectl port-forward" 2>/dev/null || true

if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  log "Deleting KinD cluster '${CLUSTER_NAME}'..."
  kind delete cluster --name "$CLUSTER_NAME"
  log "Cluster deleted"
else
  log "Cluster '${CLUSTER_NAME}' not found — nothing to delete"
fi

log "=== Teardown complete ==="
