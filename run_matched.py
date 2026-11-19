import csv, json, os, re, subprocess, time
from playwright.sync_api import sync_playwright

URL = 'https://localhost:8443/'
JS = 'JSON.stringify(performance.getEntriesByType("navigation")[0])'
LEVELS = [('2pct', {'h2': 2, 'h3': 3.25}), ('5pct', {'h2': 5, 'h3': 8.2})]
RUNS = 20
CERT = os.path.expanduser('~/cnproj/certs/localhost+1.pem')
HASH = subprocess.check_output(
    'openssl x509 -in ' + CERT + ' -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64',
    shell=True).decode().strip()
TRUST = '--ignore-certificate-errors-spki-list=' + HASH

def set_loss(l):
    subprocess.run(['sudo', 'tc', 'qdisc', 'del', 'dev', 'lo', 'root'], stderr=subprocess.DEVNULL)
    subprocess.run(['sudo', 'tc', 'qdisc', 'add', 'dev', 'lo', 'root', 'netem',
                    'delay', '25ms', 'loss', f'{l}%', 'limit', '100000'], check=True)

def counters():
    out = subprocess.run(['tc', '-s', 'qdisc', 'show', 'dev', 'lo'],
                         capture_output=True, text=True).stdout
    m = re.search(r'Sent \d+ bytes (\d+) pkt \(dropped (\d+),', out)
    return int(m[1]), int(m[2])

def one_run(p, proto):
    args = ['--disable-quic', TRUST] if proto == 'h2' else \
           ['--enable-quic', '--origin-to-force-quic-on=localhost:8443', TRUST]
    b = p.chromium.launch(args=args)
    page = b.new_page()
    page.goto(URL, wait_until='load', timeout=180000)
    page.wait_for_timeout(300)
    nav = json.loads(page.evaluate(JS))
    b.close()
    return nav

subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', 'lo', 'mtu', '1500'], check=True)
try:
    with open('results_matched.csv', 'w', newline='') as f, sync_playwright() as p:
        w = csv.writer(f)
        w.writerow(['level', 'proto', 'configured', 'run', 'nextHop', 'ttfb_req',
                    'ttfb_nav', 'load', 'connect', 'pkts', 'dropped'])
        for level, cfg in LEVELS:
            for i in range(RUNS):
                for proto in ['h2', 'h3']:
                    try:
                        set_loss(cfg[proto])
                        time.sleep(0.5)
                        n = one_run(p, proto)
                        pk, dr = counters()
                        if n['loadEventEnd'] == 0:
                            print('incomplete, skipped'); continue
                        w.writerow([level, proto, cfg[proto], i, n['nextHopProtocol'],
                                    round(n['responseStart'] - n['requestStart'], 1),
                                    round(n['responseStart'], 1),
                                    round(n['loadEventEnd'], 1),
                                    round(n['connectEnd'] - n['connectStart'], 1), pk, dr])
                        f.flush()
                        print(level, proto, i, 'load =', round(n['loadEventEnd']), 'ms', n['nextHopProtocol'])
                    except Exception as e:
                        print('FAILED', level, proto, i, str(e)[:80])
                    time.sleep(0.5)
finally:
    subprocess.run(['sudo', 'tc', 'qdisc', 'del', 'dev', 'lo', 'root'], stderr=subprocess.DEVNULL)
    subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', 'lo', 'mtu', '65536'])
    print('netem removed')
