#!/usr/bin/env bash
# RunPod pod lifecycle + sync for the autoresearch loop.
#
# The pod is the compute host for Phase 2: the whole loop (headless agent +
# train + score) runs there; the laptop only provisions, syncs, and pulls
# lineage back. Eval data is rsynced up, NEVER re-fetched on the pod — the
# frozen held-out eval sets must stay byte-identical to the bootstrap ones.
#
# Usage:  infra/runpod.sh <up|status|ssh|sync-up|pull|stop|terminate>
# Needs:  .env with RUNPOD_API_KEY; ssh keypair (default ~/.ssh/id_ed25519)
#
# up         create a Secure Cloud RTX 4090 pod (idempotent: refuses if one
#            with the same name exists)
# status     desired status, $/hr, ssh endpoint
# ssh        open an interactive shell on the pod
# sync-up    rsync repo + data/ + experiments.sqlite to the pod
# pull       rsync new runs/ + experiments.sqlite + state/ back, then
#            fast-forward local main from the pod's git history
# stop       stop billing for GPU time; volume (and synced data) persists
# terminate  destroy the pod AND its volume (asks for confirmation)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
: "${RUNPOD_API_KEY:?RUNPOD_API_KEY missing from .env}"

POD_NAME="lowlight-autoresearch"
IMAGE="runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
REMOTE_DIR="/workspace/low-light-geolocalization-autoresearch"
API="https://api.runpod.io/graphql"

gql() {  # $1 = JSON request body on stdin-safe single arg
  curl -sS -X POST "$API" -H "Content-Type: application/json" \
    -H "Authorization: Bearer $RUNPOD_API_KEY" -d "$1"
}

pods_json() {
  gql '{"query":"query { myself { pods { id name desiredStatus costPerHr runtime { ports { ip isIpPublic privatePort publicPort type } } } } }"}'
}

# Echoes "IP PORT" of the named pod's public ssh port, or fails.
endpoint() {
  pods_json | python3 -c "
import json, sys
pods = json.load(sys.stdin)['data']['myself']['pods']
pod = next((p for p in pods if p['name'] == '$POD_NAME'), None)
assert pod, 'no pod named $POD_NAME — run: infra/runpod.sh up'
ports = (pod.get('runtime') or {}).get('ports') or []
tcp = next((p for p in ports if p['type'] == 'tcp' and p['isIpPublic']), None)
assert tcp, 'pod exists but ssh port not exposed yet (still starting?)'
print(tcp['ip'], tcp['publicPort'])
"
}

pod_id() {
  pods_json | python3 -c "
import json, sys
pods = json.load(sys.stdin)['data']['myself']['pods']
pod = next((p for p in pods if p['name'] == '$POD_NAME'), None)
assert pod, 'no pod named $POD_NAME'
print(pod['id'])
"
}

case "${1:-}" in
up)
  if pods_json | grep -q "\"name\":\"$POD_NAME\""; then
    echo "Pod '$POD_NAME' already exists:"; exec "$0" status
  fi
  PUBKEY="$(cat "$SSH_KEY.pub")"
  BODY="$(python3 - "$PUBKEY" <<'PYEOF'
import json, sys
mutation = """
mutation Deploy($input: PodFindAndDeployOnDemandInput) {
  podFindAndDeployOnDemand(input: $input) { id costPerHr }
}"""
variables = {"input": {
    "cloudType": "SECURE", "gpuCount": 1,
    "volumeInGb": 50, "containerDiskInGb": 30,
    "minVcpuCount": 8, "minMemoryInGb": 30,
    "gpuTypeId": "NVIDIA GeForce RTX 4090",
    "name": "lowlight-autoresearch",
    "imageName": "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
    "ports": "22/tcp", "volumeMountPath": "/workspace",
    "env": [{"key": "PUBLIC_KEY", "value": sys.argv[1].strip()}],
}}
print(json.dumps({"query": mutation, "variables": variables}))
PYEOF
)"
  gql "$BODY"; echo
  echo "Created. Wait ~1 min, then: infra/runpod.sh status && infra/runpod.sh sync-up"
  echo "First-time pod setup (venv, claude CLI): see docs/infra.md §Reproduce."
  ;;
status)
  pods_json | python3 -c "
import json, sys
pods = json.load(sys.stdin)['data']['myself']['pods']
for p in pods:
    if p['name'] != '$POD_NAME': continue
    ports = (p.get('runtime') or {}).get('ports') or []
    tcp = next((x for x in ports if x['type'] == 'tcp' and x['isIpPublic']), None)
    ssh = f\"ssh -i $SSH_KEY -p {tcp['publicPort']} root@{tcp['ip']}\" if tcp else '(no ssh port yet)'
    print(f\"{p['id']}  {p['desiredStatus']}  \${p['costPerHr']}/hr  {ssh}\")
    break
else: print('no pod named $POD_NAME')
"
  ;;
ssh)
  read -r IP PORT < <(endpoint)
  exec ssh -i "$SSH_KEY" -p "$PORT" "root@$IP"
  ;;
sync-up)
  read -r IP PORT < <(endpoint)
  # Guard: sync-up mirrors local state INCLUDING .git refs onto the pod. If
  # the pod holds kept-experiment commits that local main doesn't have yet,
  # that would orphan them — refuse until they've been pulled.
  if GIT_SSH_COMMAND="ssh -i $SSH_KEY" \
     git fetch "ssh://root@$IP:$PORT$REMOTE_DIR" main:refs/remotes/pod/main 2>/dev/null; then
    if ! git merge-base --is-ancestor refs/remotes/pod/main HEAD; then
      echo "REFUSING sync-up: the pod has commits local main lacks (kept experiments?)."
      echo "Run 'infra/runpod.sh pull' first, then retry."
      exit 1
    fi
  fi
  rsync -a --stats -e "ssh -i $SSH_KEY -p $PORT" \
    --exclude '.venv' --exclude '__pycache__' --exclude '.env' --exclude '.DS_Store' \
    ./ "root@$IP:$REMOTE_DIR/"
  ;;
pull)
  read -r IP PORT < <(endpoint)
  rsync -a --stats -e "ssh -i $SSH_KEY -p $PORT" \
    "root@$IP:$REMOTE_DIR/experiments.sqlite" \
    "root@$IP:$REMOTE_DIR/state/" ./state-pod-tmp/
  rsync -a --stats -e "ssh -i $SSH_KEY -p $PORT" \
    "root@$IP:$REMOTE_DIR/runs/" ./runs/
  mv ./state-pod-tmp/experiments.sqlite ./experiments.sqlite
  rsync -a ./state-pod-tmp/ ./state/ --exclude experiments.sqlite
  rm -rf ./state-pod-tmp
  # Kept improvements are commits on the pod; fast-forward local main onto them.
  GIT_SSH_COMMAND="ssh -i $SSH_KEY" \
    git fetch "ssh://root@$IP:$PORT$REMOTE_DIR" main:refs/remotes/pod/main
  git merge --ff-only refs/remotes/pod/main || echo "NOTE: local main diverged from pod — merge manually."
  echo "Pulled. Re-render gallery locally with: .venv/bin/python -m autoresearch.gallery"
  ;;
stop)
  ID="$(pod_id)"
  gql "{\"query\":\"mutation { podStop(input: {podId: \\\"$ID\\\"}) { id desiredStatus } }\"}"; echo
  ;;
terminate)
  ID="$(pod_id)"
  echo "This DESTROYS pod $ID and its volume (synced data, un-pulled runs)."
  read -r -p "Type the pod name to confirm: " CONFIRM
  [ "$CONFIRM" = "$POD_NAME" ] || { echo "aborted"; exit 1; }
  gql "{\"query\":\"mutation { podTerminate(input: {podId: \\\"$ID\\\"}) }\"}"; echo
  ;;
*)
  grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -20; exit 1
  ;;
esac
