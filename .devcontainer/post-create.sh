#!/bin/bash
set -euo pipefail

LOG=/tmp/post-create.log
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== Lab environment post-create setup ==="

# Install kind v0.31.0
log "Installing kind..."
KIND_VERSION="v0.31.0"
case "$(uname -m)" in
  x86_64|amd64) ARCH=amd64 ;;
  arm64|aarch64) ARCH=arm64 ;;
  *) ARCH=amd64 ;;
esac
curl -fsSL "https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}/kind-linux-${ARCH}" \
  -o /usr/local/bin/kind
chmod +x /usr/local/bin/kind
log "kind $(kind --version) installed"

# Install jq
log "Installing jq..."
apt-get install -y -q jq 2>/dev/null || sudo apt-get install -y -q jq 2>/dev/null || true
log "jq installed"

# Install agentgateway CLI (used in Level 1)
log "Installing agentgateway..."
curl -sL https://agentgateway.dev/install | bash || log "agentgateway install failed — install manually via: curl -sL https://agentgateway.dev/install | bash"

# Shell aliases
cat >> /home/vscode/.bashrc <<'EOF'

# Lab shortcuts
alias k=kubectl
alias h=helm
alias kn='kubectl get nodes'
alias kp='kubectl get pods -A'
alias ks='kubectl get svc -A'

export PATH="$HOME/.local/bin:$HOME/bin:$PATH"
EOF

mkdir -p /home/vscode/.kube

log "=== post-create done ==="
log "Log saved to $LOG"
