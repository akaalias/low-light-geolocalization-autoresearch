#!/usr/bin/env bash
# Train ONE area on the remote RunPod GPU worker and bring the result home.
#
# The pod is a STATELESS worker: it holds data/ + venv + the frozen pipeline,
# trains whatever model/ code we push, and returns the ONNX + train_info. It
# runs NO git and NO loop — the laptop stays the single source of truth and the
# single writer, so the two-writer divergence that broke the old pod setup
# cannot recur here by construction.
#
# Wifi-tolerant: training is launched DETACHED on the pod (nohup + a .done
# marker) and this script then reconnect-polls for completion, so a dropped ssh
# only pauses the poll — the GPU keeps working and we pick back up. A genuine
# failure returns non-zero, which loop.sh already treats as a failed train
# (scores 1e9 → the experiment reverts), so nothing is corrupted.
#
# Usage: infra/remote_train.sh <area> <local-out-dir> <epochs> <max-crops-per-bucket>
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
REMOTE_DIR="/workspace/low-light-geolocalization-autoresearch"
AREA="$1"; LOCAL_OUT="$2"; EPOCHS="${3:-8}"; CROPS="${4:-6000}"
POLL_TRIES="${REMOTE_POLL_TRIES:-360}"     # ×10s ≈ 60 min ceiling per area

read -r IP PORT < <(infra/runpod.sh _endpoint) || { echo "remote_train: no pod endpoint"; exit 3; }
SSHO="-i $SSH_KEY -p $PORT -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o ServerAliveInterval=15 -o ServerAliveCountMax=3"
sshx()   { ssh $SSHO "root@$IP" "$@"; }
rsyncx() { rsync -a --timeout=90 --partial -e "ssh $SSHO" "$@"; }
retry()  { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; echo "  ..retry $n"; sleep 8; done; }

TAG="${AREA}_$(date +%s)"
REMOTE_OUT="$REMOTE_DIR/_remote_train/$TAG"
DONE="$REMOTE_OUT/.done"; LOG="$REMOTE_OUT/train.log"

# 1. push the agent-editable model code + the frozen pipeline (data/ + venv +
#    render_cache already live on the pod volume, never re-uploaded).
retry rsyncx model/ "root@$IP:$REMOTE_DIR/model/"        || { echo "remote_train: push model/ failed"; exit 1; }
retry rsyncx pipeline/ "root@$IP:$REMOTE_DIR/pipeline/"  || { echo "remote_train: push pipeline/ failed"; exit 1; }
retry rsyncx areas.yaml "root@$IP:$REMOTE_DIR/areas.yaml" || true

# 2. launch training DETACHED so an ssh drop can't kill it; capture exit code.
retry sshx "mkdir -p '$REMOTE_OUT' && cd '$REMOTE_DIR' && \
  nohup sh -c 'OMP_NUM_THREADS=8 RENDER_CACHE=render_cache .venv/bin/python -m model.train \
    --area $AREA --out-dir \"$REMOTE_OUT\" --epochs $EPOCHS --max-crops-per-bucket $CROPS \
    > \"$LOG\" 2>&1; echo \$? > \"$DONE\"' >/dev/null 2>&1 </dev/null &" \
  || { echo "remote_train: launch failed"; exit 1; }

# 3. reconnect-poll for the .done marker (tolerates transient ssh failures).
rc=""
for _ in $(seq 1 "$POLL_TRIES"); do
  rc="$(sshx "cat '$DONE' 2>/dev/null" 2>/dev/null || echo "")"
  [ -n "$rc" ] && break
  sleep 10
done
if [ "${rc:-}" != "0" ]; then
  echo "remote_train: training failed on pod (rc=${rc:-timeout}) — tail:"
  sshx "tail -6 '$LOG'" 2>/dev/null || true
  exit 1
fi

# 4. bring back ONLY the deliverables (ONNX + train_info), never the scratch.
mkdir -p "$LOCAL_OUT/models"
retry rsyncx "root@$IP:$REMOTE_OUT/models/" "$LOCAL_OUT/models/"           || { echo "remote_train: pull onnx failed"; exit 1; }
retry rsyncx "root@$IP:$REMOTE_OUT/train_info.json" "$LOCAL_OUT/train_info.json" || { echo "remote_train: pull train_info failed"; exit 1; }
sshx "rm -rf '$REMOTE_OUT'" 2>/dev/null || true     # free the pod's scratch
echo "remote_train: $AREA done on GPU"
