#!/usr/bin/env bash
# Gamify Your Learning: Ultimate AI-Enhanced Study & Productivity Tracker
# Terminal-first, offline-friendly gamified study tracker
# Location: ~/.study_gamify/data.json (created automatically)

set -euo pipefail

ROOT_DIR="$HOME/.study_gamify"
DATA_FILE="$ROOT_DIR/data.json"
LOCK_FILE="$ROOT_DIR/active_session.json"

ensure_env() {
  mkdir -p "$ROOT_DIR"
  if [ ! -f "$DATA_FILE" ]; then
    cat > "$DATA_FILE" <<-JSON
{ "sessions": [], "config": { "xp_per_min": 1 }, "achievements": [] }
JSON
  fi
}

run_python() {
  # pass through to an embedded Python handler
  python3 - "$DATA_FILE" "$LOCK_FILE" "$@" <<'PY'
import sys, json, os, random, datetime, time

# Optional curses import (for big live timer)
try:
    import curses
except Exception:
    curses = None

DATA_FILE = sys.argv[1]
LOCK_FILE = sys.argv[2]
cmd = sys.argv[3] if len(sys.argv) > 3 else 'help'
args = sys.argv[4:]

def load():
    with open(DATA_FILE,'r',encoding='utf-8') as f:
        return json.load(f)

def save(d):
    with open(DATA_FILE,'w',encoding='utf-8') as f:
        json.dump(d,f,indent=2,ensure_ascii=False)

def secs_to_hm(s):
    m = int(s//60)
    return f"{m}m {int(s%60)}s"

# big-digit font for curses display
BIG_DIGITS = {
"0": [" ███ ","█   █","█   █","█   █"," ███ "],
"1": ["  █  "," ██  ","  █  ","  █  "," ███ "],
"2": [" ███ ","█   █","   █ ","  █  ","█████"],
"3": [" ███ ","█   █","  ██ ","█   █"," ███ "],
"4": ["   █ ","  ██ "," █ █ ","█████","   █ "],
"5": ["█████","█    ","████ ","    █","████ "],
"6": [" ███ ","█    ","████ ","█   █"," ███ "],
"7": ["█████","    █","   █ ","  █  ","  █  "],
"8": [" ███ ","█   █"," ███ ","█   █"," ███ "],
"9": [" ███ ","█   █"," ████","    █"," ███ "],
":": ["     ","  ░  ","     ","  ░  ","     "]
}

def format_big(mmss):
    # mm:ss -> assemble rows
    rows = [""]*5
    for ch in mmss:
        font = BIG_DIGITS.get(ch, ["     "]*5)
        for i in range(5):
            rows[i] += font[i] + "  "
    return "\n".join(rows)

if cmd == 'help':
    print('Gamified Study Tracker - Commands:')
    print('  start               Start a study session')
    print('  stop                Stop current session and earn XP')
    print('  status              Show if a session is active')
    print('  stats [period]      Show stats (period: all, week, month)')
    print('  config set KEY VAL  Set config (xp_per_min)')
    print('  ai                  Show an offline AI study suggestion')
    print('  achievements        Show unlocked achievements')
    print('  export              Print path to data file')
    print('  live [start]        Show a big live timer; use live start to start a session')
    print('  view                Show a live updating compact dashboard')
    print('\nLive controls inside the big timer:')
    print("  s = stop session and record; q = quit live view (doesn't stop by default)")
    sys.exit(0)

if cmd == 'start':
    if os.path.exists(LOCK_FILE):
        print('A session is already running. Use stop to finish it.')
        sys.exit(1)
    start_ts = datetime.datetime.utcnow().timestamp()
    with open(LOCK_FILE,'w',encoding='utf-8') as f:
        json.dump({'start': start_ts}, f)
    print('Session started. Good focus!')
    sys.exit(0)

if cmd == 'status':
    if os.path.exists(LOCK_FILE):
        d = json.load(open(LOCK_FILE))
        elapsed = datetime.datetime.utcnow().timestamp() - d['start']
        print(f"Active session: {secs_to_hm(elapsed)}")
    else:
        print('No active session.')
    sys.exit(0)

if cmd == 'stop':
    if not os.path.exists(LOCK_FILE):
        print('No active session to stop.')
        sys.exit(1)
    lock = json.load(open(LOCK_FILE))
    start = lock['start']
    end = datetime.datetime.utcnow().timestamp()
    duration = end - start
    data = load()
    xp_per_min = float(data.get('config',{}).get('xp_per_min',1))
    minutes = max(1, int(duration//60))
    xp = int(minutes * xp_per_min)
    session = {
        'start': datetime.datetime.utcfromtimestamp(start).isoformat(),
        'end': datetime.datetime.utcfromtimestamp(end).isoformat(),
        'duration_seconds': int(duration),
        'minutes': minutes,
        'xp': xp
    }
    data.setdefault('sessions',[]).append(session)
    save(data)
    os.remove(LOCK_FILE)
    print(f"Session stopped — {minutes} minutes, +{xp} XP")
    sys.exit(0)

if cmd == 'config':
    if len(args) >= 2 and args[0] == 'set':
        key = args[1]
        val = args[2] if len(args) > 2 else ''
        data = load()
        try:
            if key == 'xp_per_min':
                data.setdefault('config',{})['xp_per_min'] = float(val)
                save(data)
                print('Config updated.')
                sys.exit(0)
        except Exception as e:
            print('Invalid value:',e)
            sys.exit(1)
    print('Usage: config set xp_per_min 1.0')
    sys.exit(0)

if cmd == 'stats':
    period = args[0] if args else 'all'
    data = load()
    now = datetime.datetime.utcnow()
    sessions = data.get('sessions',[])
    def in_period(s):
        if period == 'all':
            return True
        st = datetime.datetime.fromisoformat(s['start'])
        if period == 'week':
            return (now - st).days < 7
        if period == 'month':
            return (now - st).days < 31
        return True
    sel = [s for s in sessions if in_period(s)]
    total_minutes = sum(s.get('minutes',0) for s in sel)
    total_xp = sum(s.get('xp',0) for s in sel)
    print(f"Period: {period}\nSessions: {len(sel)}\nMinutes: {total_minutes}\nXP: {total_xp}")
    # Level system
    levels = [('Legendary',3000),('Diamond',1500),('Gold',700),('Silver',300),('Bronze',100),('Beginner',0)]
    lvl = next((name for name,thr in levels if total_xp>=thr), 'Beginner')
    print(f"Level: {lvl}")
    sys.exit(0)

if cmd == 'ai':
    tips = [
        'Try the Pomodoro technique: 25m focus, 5m break.',
        'Write one small coding challenge and implement it in 30 minutes.',
        'Summarize what you learned in 5 bullet points after the session.',
        'Switch topics: if stuck, practice a different project for 20 minutes.',
        'Create a micro-goal: "Write 20 lines of code" and finish it.'
    ]
    challenges = [
        'Implement a CLI tool that counts word frequency in files.',
        'Build a small REST API with Flask that returns current time.',
        'Write a regex that validates email addresses and test it.'
    ]
    print('AI Tip: ' + random.choice(tips))
    print('Challenge: ' + random.choice(challenges))
    sys.exit(0)

if cmd == 'achievements':
    data = load()
    total_xp = sum(s.get('xp',0) for s in data.get('sessions',[]))
    badges = [(100,'First Blood'),(500,'Master Coder'),(1000,'Scholar'),(5000,'Legend')]
    unlocked = [name for thr,name in badges if total_xp>=thr]
    print('Unlocked Achievements:')
    for u in unlocked:
        print(' -',u)
    if not unlocked: print(' (none yet)')
    sys.exit(0)

if cmd == 'export':
    print(DATA_FILE)
    sys.exit(0)

if cmd == 'live':
    # live [start]
    start_new = len(args) > 0 and args[0] == 'start'
    # ensure session exists
    if start_new and os.path.exists(LOCK_FILE):
        print('Session already running; showing live view.')
    if start_new and not os.path.exists(LOCK_FILE):
        start_ts = datetime.datetime.utcnow().timestamp()
        with open(LOCK_FILE,'w',encoding='utf-8') as f:
            json.dump({'start': start_ts}, f)
    if not os.path.exists(LOCK_FILE):
        print('No active session. Use live start or start to begin one.')
        sys.exit(1)
    lock = json.load(open(LOCK_FILE))
    start = lock['start']

    def stop_and_record(duration):
        data = load()
        xp_per_min = float(data.get('config',{}).get('xp_per_min',1))
        minutes = max(1, int(duration//60))
        xp = int(minutes * xp_per_min)
        session = {
            'start': datetime.datetime.utcfromtimestamp(start).isoformat(),
            'end': datetime.datetime.utcfromtimestamp(start+duration).isoformat(),
            'duration_seconds': int(duration),
            'minutes': minutes,
            'xp': xp
        }
        data.setdefault('sessions',[]).append(session)
        save(data)
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
        print(f"Session stopped — {minutes} minutes, +{xp} XP")

    def run_curses(start):
        def _draw(stdscr):
            curses.curs_set(0)
            stdscr.nodelay(True)
            while True:
                now = datetime.datetime.utcnow().timestamp()
                elapsed = int(now - start)
                mm = elapsed//60
                ss = elapsed%60
                mmss = f"{mm:02d}:{ss:02d}"
                stdscr.erase()
                rows = format_big(mmss)
                for i, row in enumerate(rows.split('\n')):
                    try:
                        stdscr.addstr(i+1,2,row)
                    except Exception:
                        pass
                stdscr.addstr(8,2,"Press 's' to stop & record, 'q' to quit live view.")
                stdscr.refresh()
                ch = stdscr.getch()
                if ch == ord('q'):
                    break
                if ch == ord('s'):
                    stop_and_record(elapsed)
                    break
                time.sleep(0.5)
        curses.wrapper(_draw)

    if curses is not None:
        try:
            run_curses(start)
            sys.exit(0)
        except Exception as e:
            print('Curses live view failed:',e)
    # fallback simple live print loop
    try:
        while True:
            now = datetime.datetime.utcnow().timestamp()
            elapsed = int(now - start)
            mmss = f"{elapsed//60:02d}:{elapsed%60:02d}"
            print('\rLive: ' + mmss, end='', flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nLive view ended.')
    sys.exit(0)

# --- VIEW: show live updating compact dashboard (terminal-friendly)
if cmd == 'view':
    if not os.path.exists(LOCK_FILE):
        print('No active session. Use start or live start to begin one.')
        sys.exit(1)
    lock = json.load(open(LOCK_FILE))
    start = lock['start']

    def compute_totals(elapsed):
        data = load()
        xp_per_min = float(data.get('config',{}).get('xp_per_min',1))
        minutes = max(1, int(elapsed//60))
        current_xp = int(minutes * xp_per_min)
        total_xp = sum(s.get('xp',0) for s in data.get('sessions',[])) + current_xp
        return minutes, current_xp, total_xp

    def get_level(total_xp):
        levels = [('Legendary',3000),('Diamond',1500),('Gold',700),('Silver',300),('Bronze',100),('Beginner',0)]
        return next((name for name,thr in levels if total_xp>=thr), 'Beginner')

    def ansi_dashboard(start):
        try:
            while True:
                now = datetime.datetime.utcnow().timestamp()
                elapsed = int(now - start)
                mm = elapsed//60
                ss = elapsed%60
                minutes, cur_xp, total_xp = compute_totals(elapsed)
                level = get_level(total_xp)
                # clear screen
                print('\033[2J\033[H', end='')
                print('=== Study Live View ===')
                print(f'Elapsed: {mm:02d}:{ss:02d}  ({secs_to_hm(elapsed)})')
                print(f'Current session: {minutes} min | +{cur_xp} XP')
                print(f'Total XP (incl current): {total_xp} | Level: {level}')
                print("Controls: Ctrl-C to exit view; use 'stop' to finish session")
                time.sleep(1)
        except KeyboardInterrupt:
            print('\nExiting view.')

    def curses_dashboard(start):
        def _draw(stdscr):
            curses.curs_set(0)
            stdscr.nodelay(True)
            while True:
                now = datetime.datetime.utcnow().timestamp()
                elapsed = int(now - start)
                mm = elapsed//60
                ss = elapsed%60
                minutes, cur_xp, total_xp = compute_totals(elapsed)
                level = get_level(total_xp)
                stdscr.erase()
                header = ' Study Live View '
                try:
                    stdscr.addstr(1,2,header, curses.A_REVERSE)
                except Exception:
                    pass
                stdscr.addstr(3,4,f'Elapsed: {mm:02d}:{ss:02d} ({secs_to_hm(elapsed)})')
                stdscr.addstr(5,4,f'Current session: {minutes} min  +{cur_xp} XP')
                stdscr.addstr(6,4,f'Total XP (incl current): {total_xp}  Level: {level}')
                stdscr.addstr(8,4,"Press 'q' to quit view. Use stop to end session.")
                stdscr.refresh()
                ch = stdscr.getch()
                if ch == ord('q'):
                    break
                time.sleep(0.5)
        curses.wrapper(_draw)

    # run preferred dashboard
    if curses is not None:
        try:
            curses_dashboard(start)
            sys.exit(0)
        except Exception:
            pass
    ansi_dashboard(start)
    sys.exit(0)

print('Unknown command. Use help to see commands.')
PY
}

ensure_env

if [ ${#@} -eq 0 ]; then
  run_python help
  exit 0
fi

CMD="$1"; shift || true
run_python "$CMD" "$@"
