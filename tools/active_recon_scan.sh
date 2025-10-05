#!/usr/bin/env bash
# Lightweight but powerful orchestration for active recon tasks.
# Runs nmap, nikto, whatweb, gobuster/dirb if available and stores outputs under a target-specific directory.

set -euo pipefail

USAGE="Usage: $0 -t target_or_file [-o output_dir] [-p ports] [--fast] [--only nmap,nikto,whatweb,gobuster]
Examples:
  $0 -t example.com
  $0 -t targets.txt -o /tmp/out --only nmap,whatweb
"

OUT_DIR="khoba_active"
PORTS="1-65535"
ONLY=""
FAST=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--target)
      TARGET="$2"; shift 2;;
    -o|--output)
      OUT_DIR="$2"; shift 2;;
    -p|--ports)
      PORTS="$2"; shift 2;;
    --fast)
      FAST=1; shift;;
    --only)
      ONLY="$2"; shift 2;;
    -h|--help)
      echo "$USAGE"; exit 0;;
    *)
      echo "Unknown arg: $1"; echo "$USAGE"; exit 2;;
  esac
done

if [[ -z "${TARGET:-}" ]]; then
  echo "No target specified."; echo "$USAGE"; exit 2
fi

mkdir -p "$OUT_DIR"

run_cmd(){
  local name="$1"; shift
  echo "[+] Running $name: $*"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "DRY: $*"
    return
  fi
  "$@"
}

check_and_run(){
  local tool="$1"; shift
  if [[ -n "$ONLY" && ! ",${ONLY}," == *",${tool},*" ]]; then
    echo "[i] Skipping $tool (not in --only)"
    return
  fi
  if command -v $tool >/dev/null 2>&1; then
    run_cmd "$tool" "$@"
  else
    echo "[!] $tool not installed; skipping"
  fi
}

process_one(){
  local tgt="$1"
  local tdir="$OUT_DIR/$(echo "$tgt" | sed 's#[/:]#_#g')"
  mkdir -p "$tdir"

  # Nmap quick scan
  if [[ "$FAST" -eq 1 ]]; then
    check_and_run nmap -Pn -sS -p "$PORTS" -oA "$tdir/nmap" "$tgt"
  else
    check_and_run nmap -Pn -sS -p "$PORTS" -A -T4 -oA "$tdir/nmap" "$tgt"
  fi

  # Nikto
  check_and_run nikto -host "$tgt" -o "$tdir/nikto.txt"

  # WhatWeb
  check_and_run whatweb -v -a 3 -o "$tdir/whatweb.txt" "$tgt"

  # Gobuster (dir) fallback to dirb
  if command -v gobuster >/dev/null 2>&1; then
    check_and_run gobuster dir -u "http://$tgt" -w /usr/share/wordlists/dirb/common.txt -o "$tdir/gobuster.txt" || true
  elif command -v dirb >/dev/null 2>&1; then
    check_and_run dirb "http://$tgt" /usr/share/wordlists/dirb/common.txt -o "$tdir/dirb.txt" || true
  else
    echo "[!] No dir discovery tool (gobuster/dirb) installed; skipping"
  fi

  # Save HTTP headers
  check_and_run curl -sI "http://$tgt" -o "$tdir/headers_http.txt" || true
  check_and_run curl -sI "https://$tgt" -o "$tdir/headers_https.txt" || true

  echo "[+] Finished: $tgt -> $tdir"
}

# If target is a file, iterate
if [[ -f "$TARGET" ]]; then
  while IFS= read -r l; do
    l=$(echo "$l" | sed 's/[[:space:]]*#.*//')
    if [[ -n "$l" ]]; then
      process_one "$l" &
    fi
  done < "$TARGET"
  wait
else
  process_one "$TARGET"
fi

echo "All done. Outputs in $OUT_DIR"
