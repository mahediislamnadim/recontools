#!/usr/bin/env python3
"""Top-level CLI for Active Recon tools

Subcommands:
- ctf-scan: run tools/ctf_scanner.py
- passive: run recon1.0.py (passive recon)
- web-ui: run tools/web_ui.py (Flask)
- study: run studytimer/study.sh
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def run_ctf_scan(args):
    cmd = [sys.executable, str(ROOT / 'tools' / 'ctf_scanner.py')] + args
    return subprocess.call(cmd)


def run_passive(args):
    cmd = [sys.executable, str(ROOT / 'recon1.0.py')] + args
    return subprocess.call(cmd)


def run_web_ui(args):
    cmd = [sys.executable, str(ROOT / 'tools' / 'web_ui.py')] + args
    return subprocess.call(cmd)


def run_study(args):
    cmd = [str(ROOT / 'studytimer' / 'study.sh')] + args
    return subprocess.call(cmd)


def main():
    ap = argparse.ArgumentParser(prog='active-recon')
    sub = ap.add_subparsers(dest='cmd')

    sc = sub.add_parser('ctf-scan')
    sc.add_argument('rest', nargs=argparse.REMAINDER)

    sp = sub.add_parser('passive')
    sp.add_argument('rest', nargs=argparse.REMAINDER)

    sw = sub.add_parser('web-ui')
    sw.add_argument('rest', nargs=argparse.REMAINDER)

    ss = sub.add_parser('study')
    ss.add_argument('rest', nargs=argparse.REMAINDER)

    args = ap.parse_args()
    if args.cmd == 'ctf-scan':
        sys.exit(run_ctf_scan(args.rest))
    if args.cmd == 'passive':
        sys.exit(run_passive(args.rest))
    if args.cmd == 'web-ui':
        sys.exit(run_web_ui(args.rest))
    if args.cmd == 'study':
        sys.exit(run_study(args.rest))

    ap.print_help()


if __name__ == '__main__':
    main()
