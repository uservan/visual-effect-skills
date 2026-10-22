#!/usr/bin/env bash
# One command after every node (re)start: local Python env + local model copies.
# Needs /tmp/instance_storage/visual_effect_models writable by this user; on a fresh node run once:
#   sudo mkdir -p /tmp/instance_storage/visual_effect_models && sudo chown $USER /tmp/instance_storage/visual_effect_models
# Usage: scripts/setup_node.sh [model_dir_name ...]   (default: all models)
set -euo pipefail
here=$(dirname "$0")
"$here/setup_env.sh"
"$here/stage_models.sh" "$@"
