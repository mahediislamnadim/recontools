# recontools
Cybersecurity Enthusiast | Building Recon &amp; Port Scanner Tools in Python | Learning Bug Bounty &amp; Ethical Hacking
# 🔎 ReconTools

A powerful and flexible recon tool for ethical hackers, bug bounty hunters, and penetration testers. Built with Python.

## ⚙️ Features

- 🔍 Fast and multi-threaded port scanner
- 🌐 Subdomain finder using DNS brute-force
- 📁 Directory brute-forcer
- 📡 IP and ASN lookup
- 🛠️ Easy to extend and customize

## 🧠 Usage

 Scan full port range with 500 threads
```bash
python3 scanner.py 192.168.0.1 -s 1 -e 65535 -t 500
