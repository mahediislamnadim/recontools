print("I am Mahedi Islam Nadim")
import socket
import threading
import argparse
from datetime import datetime

print_lock = threading.Lock()

def banner_grab(ip, port):
    try:
        s = socket.socket()
        s.settimeout(1)
        s.connect((ip, port))
        banner = s.recv(1024).decode().strip()
        return banner
    except:
        return ""
    finally:
        s.close()

def scan(ip, port, timeout):
    try:
        s = socket.socket()
        s.settimeout(timeout)
        result = s.connect_ex((ip, port))
        if result == 0:
            with print_lock:
                banner = banner_grab(ip, port)
                print(f"[+] Port {port} OPEN  {'| ' + banner if banner else ''}")
    except:
        pass
    finally:
        s.close()

def main():
    parser = argparse.ArgumentParser(description="Advanced Python Port Scanner")
    parser.add_argument("target", help="Target IP or Domain")
    parser.add_argument("-s", "--start", type=int, default=1, help="Start Port (default: 1)")
    parser.add_argument("-e", "--end", type=int, default=1024, help="End Port (default: 1024)")
    parser.add_argument("-t", "--threads", type=int, default=100, help="Number of threads (default: 100)")
    parser.add_argument("-to", "--timeout", type=int, default=1, help="Timeout in seconds (default: 1)")
    args = parser.parse_args()

    target_ip = socket.gethostbyname(args.target)
    print(f"\n[~] Scanning Target: {target_ip}")
    print(f"[~] Port Range: {args.start}-{args.end}")
    print(f"[~] Threads: {args.threads} | Timeout: {args.timeout}s")
    print(f"[~] Scan Start Time: {datetime.now()}\n")

    thread_list = []
    for port in range(args.start, args.end + 1):
        t = threading.Thread(target=scan, args=(target_ip, port, args.timeout))
        thread_list.append(t)
        t.start()

        # Wait when thread count reaches limit
        if len(thread_list) >= args.threads:
            for t in thread_list:
                t.join()
            thread_list = []

    # Join remaining threads
    for t in thread_list:
        t.join()

    print(f"\n[~] Scan Completed at: {datetime.now()}")

if __name__ == "__main__":
    main()
