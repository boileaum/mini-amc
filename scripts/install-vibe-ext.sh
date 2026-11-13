#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
ALIAS="vibe-ext"
for a in "$@"; do
  case "$a" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) echo "usage: $0 [--dry-run] [alias]"; exit 0 ;;
    *) ALIAS="$a" ;;
  esac
done

command -v uv >/dev/null 2>&1 || { echo "erreur: uv introuvable dans le PATH" >&2; exit 1; }

best=""
for d in "$HOME"/.vscode/extensions/mistralai.mistral-vibe-code-*/bin/_internal/mistral_vibe-*.dist-info; do
  [ -d "$d" ] || continue
  v="${d##*/mistral_vibe-}"
  v="${v%.dist-info}"
  if [ -z "$best" ] || [ "$(printf '%s\n%s\n' "$best" "$v" | sort -V | tail -1)" = "$v" ]; then
    best="$v"
  fi
done
[ -n "$best" ] || { echo "erreur: aucun mistral_vibe-*.dist-info sous ~/.vscode/extensions/mistralai.mistral-vibe-code-*" >&2; exit 1; }

ROOT="$HOME/.vibe-tools/$ALIAS"
TOOL_DIR="$ROOT/tool"
BIN_DIR="$ROOT/bin"
echo "version agent embarquee (extension VS Code): $best"
echo "commande: UV_TOOL_DIR=$TOOL_DIR UV_TOOL_BIN_DIR=$BIN_DIR uv tool install mistral-vibe==$best"
[ "$DRY_RUN" = 1 ] && exit 0

UV_TOOL_DIR="$TOOL_DIR" UV_TOOL_BIN_DIR="$BIN_DIR" uv tool install "mistral-vibe==${best}"
mkdir -p "$HOME/.local/bin"
ln -sf "$BIN_DIR/vibe" "$HOME/.local/bin/$ALIAS"
"$HOME/.local/bin/$ALIAS" --version
echo "alias: $HOME/.local/bin/$ALIAS -> $BIN_DIR/vibe"
