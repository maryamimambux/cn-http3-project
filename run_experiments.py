import csv, json, os, subprocess, time
from playwright.sync_api import sync_playwright

URL = 'https://localhost:8443/'
ONE_WAY_DELAY_MS = 25

LOSS_LEVELS = [0, 1, 2]
RUNS = 30
OUT = 'results_extra.csv'

# commented -- while doing more runs for 1% and 2%
# (it runs by itself, about 20 to 25 minutes)
""" LOSS_LEVELS = [0, 1, 2, 5]
RUNS = 20   # 2 = quick test, change to 20 for the real run
OUT = 'results_test.csv' if RUNS < 5 else 'results.csv' """

JS = 'JSON.stringify(performance.getEntriesByType("navigation")[0])'

CERT = os.path.expanduser('~/cnproj/certs/localhost+1.pem')
HASH = subprocess.check_output(
    'openssl x509 -in ' + CERT + ' -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64',
    shell=True).decode().strip()
TRUST = '--ignore-certificate-errors-spki-list=' + HASH


def netem_on(loss):
    subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', 'lo', 'mtu', '1500'], check=True)
    subprocess.run(['sudo', 'tc', 'qdisc', 'replace', 'dev', 'lo', 'root', 'netem',
                    'delay', f'{ONE_WAY_DELAY_MS}ms', 'loss', f'{loss}%', 'limit', '100000'], check=True)


def netem_off():
    subprocess.run(['sudo', 'tc', 'qdisc', 'del', 'dev', 'lo', 'root'])
    subprocess.run(['sudo', 'ip', 'link', 'set', 'dev', 'lo', 'mtu', '65536'])


def one_run(p, proto):
    if proto == 'h2':
        args = ['--disable-quic', TRUST]
    else:
        args = ['--enable-quic', '--origin-to-force-quic-on=localhost:8443', TRUST]
    browser = p.chromium.launch(args=args)
    page = browser.new_page()
    page.goto(URL, wait_until='load', timeout=180000)
    page.wait_for_timeout(300)
    nav = json.loads(page.evaluate(JS))
    browser.close()
    return nav


def main():
    try:
        with open(OUT, 'w', newline='') as f, sync_playwright() as p:
            w = csv.writer(f)
            w.writerow(['loss', 'proto', 'run', 'nextHop', 'ttfb_req', 'ttfb_nav', 'load', 'connect'])
            for loss in LOSS_LEVELS:
                netem_on(loss)
                time.sleep(1)
                for i in range(RUNS):
                    for proto in ['h2', 'h3']:
                        try:
                            n = one_run(p, proto)
                            if n['loadEventEnd'] == 0:
                                print('incomplete load, skipped')
                                continue
                            w.writerow([loss, proto, i, n['nextHopProtocol'],
                                        round(n['responseStart'] - n['requestStart'], 1),
                                        round(n['responseStart'], 1),
                                        round(n['loadEventEnd'], 1),
                                        round(n['connectEnd'] - n['connectStart'], 1)])
                            f.flush()
                            print('loss', loss, proto, 'run', i, 'load =', round(n['loadEventEnd']), 'ms', n['nextHopProtocol'])
                        except Exception as e:
                            print('FAILED', loss, proto, i, e)
                        time.sleep(0.5)
    finally:
        netem_off()
        print('netem removed')


main()
