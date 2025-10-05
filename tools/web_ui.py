from flask import Flask, request, render_template_string, redirect, url_for
from pathlib import Path
import threading
import time

app = Flask(__name__)

HTML = '''
<h2>CTF Scanner Web UI</h2>
<form method="post">
  URLs (one per line):<br>
  <textarea name="urls" rows="6" cols="60"></textarea><br>
  <input type="submit" value="Start Scan">
</form>
<p>{{ status }}</p>
'''

SCAN_THREAD = None
STATUS = 'idle'

def run_scan_background(urls_text: str):
    global STATUS
    try:
        from tools import ctf_scanner
        tmp = Path('/tmp/web_ctf_urls.txt')
        tmp.write_text(urls_text)
        STATUS = 'running'
        ctf_scanner.main_args = ['-i', str(tmp), '--concurrency', '2']
        # call the main function (it parses args from argparse) by using its main()
        ctf_scanner.main()
        STATUS = 'completed'
    except Exception as e:
        STATUS = f'error: {e}'


@app.route('/', methods=['GET', 'POST'])
def index():
    global SCAN_THREAD, STATUS
    if request.method == 'POST':
        urls = request.form.get('urls', '')
        if urls.strip():
            STATUS = 'queued'
            SCAN_THREAD = threading.Thread(target=run_scan_background, args=(urls,))
            SCAN_THREAD.start()
            return redirect(url_for('index'))
    return render_template_string(HTML, status=STATUS)


if __name__ == '__main__':
    app.run(port=5001)
