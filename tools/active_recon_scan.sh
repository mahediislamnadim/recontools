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
DRY_RUN=0
WORDLIST="/usr/share/wordlists/dirb/common.txt"
NMAP_ARGS=""
GOBUSTER_ARGS=""
MAX_CONCURRENCY=10
AGGRESSIVE=0
SHOW_COMMANDS=0

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
    --dry-run)
      DRY_RUN=1; shift;;
    --aggressive)
      AGGRESSIVE=1; shift;;
    --show-commands)
      SHOW_COMMANDS=1; shift;;
    --wordlist)
      WORDLIST="$2"; shift 2;;
    --nmap-args)
      NMAP_ARGS="$2"; shift 2;;
    --gobuster-args)
      GOBUSTER_ARGS="$2"; shift 2;;
    -c|--concurrency)
      MAX_CONCURRENCY="$2"; shift 2;;
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
  # Build full command string for display
  local cmd="$name"
  for a in "$@"; do
    cmd+=" $a"
  done
  echo "[+] Running $name: $*"
  if [[ "${SHOW_COMMANDS:-0}" == "1" ]]; then
    echo "CMD: $cmd"
  fi
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "DRY: $cmd"
    return
  fi
  # Execute the command
  eval "$cmd"
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
    nm_extra="$NMAP_ARGS"
    if [[ "$AGGRESSIVE" -eq 1 ]]; then
      nm_extra="$nm_extra -sV -sC --script vuln"
    fi
    check_and_run nmap -Pn -sS -p "$PORTS" $nm_extra -oA "$tdir/nmap" "$tgt"
  else
    nm_extra="$NMAP_ARGS -A -T4"
    if [[ "$AGGRESSIVE" -eq 1 ]]; then
      nm_extra="$nm_extra -sV -sC --script vuln"
    fi
    check_and_run nmap -Pn -sS -p "$PORTS" $nm_extra -oA "$tdir/nmap" "$tgt"
  fi

  # Nikto
  check_and_run nikto -host "$tgt" -o "$tdir/nikto.txt"

  # WhatWeb
  check_and_run whatweb -v -a 3 -o "$tdir/whatweb.txt" "$tgt"

  # Gobuster (dir) fallback to dirb
  if command -v gobuster >/dev/null 2>&1; then
    # if aggressive and user didn't set -t in GOBUSTER_ARGS, bump threads
    if [[ "$AGGRESSIVE" -eq 1 && ! "$GOBUSTER_ARGS" =~ "-t" ]]; then
      gb_args="$GOBUSTER_ARGS -t 50"
    else
      gb_args="$GOBUSTER_ARGS"
    fi
    check_and_run gobuster dir -u "http://$tgt" -w "$WORDLIST" $gb_args -o "$tdir/gobuster.txt" || true
  elif command -v dirb >/dev/null 2>&1; then
    check_and_run dirb "http://$tgt" "$WORDLIST" -o "$tdir/dirb.txt" || true
  else
    echo "[!] No dir discovery tool (gobuster/dirb) installed; skipping"
  fi

  # Optional aggressive TLS checks
  if [[ "$AGGRESSIVE" -eq 1 ]]; then
    if command -v sslscan >/dev/null 2>&1; then
      check_and_run sslscan --no-failed -o "$tdir/sslscan.txt" "$tgt" || true
    elif command -v sslyze >/dev/null 2>&1; then
      check_and_run sslyze --regular "$tgt" > "$tdir/sslyze.txt" || true
    fi
  fi

  # Save HTTP headers
  check_and_run curl -sI "http://$tgt" -o "$tdir/headers_http.txt" || true
  check_and_run curl -sI "https://$tgt" -o "$tdir/headers_https.txt" || true

  echo "[+] Finished: $tgt -> $tdir"
}

# If target is a file, iterate
if [[ -f "$TARGET" ]]; then
  running=0
  while IFS= read -r l; do
    l=$(echo "$l" | sed 's/[[:space:]]*#.*//')
    if [[ -n "$l" ]]; then
      process_one "$l" &
      running=$((running+1))
      if [[ "$running" -ge "$MAX_CONCURRENCY" ]]; then
        wait -n || true
        running=$((running-1))
      fi
    fi
  done < "$TARGET"
  # wait for remaining
  wait
else
  process_one "$TARGET"
fi

echo "All done. Outputs in $OUT_DIR"
