import csv, json, os, subprocess, time
import numpy as np
import pandas as pd
from playwright.sync_api import sync_playwright
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

URL = 'https://localhost:8443/'
ONE_WAY_DELAY_MS = 25
LOSS_LEVELS = [2, 5]
RUNS = 10
JS = 'JSON.stringify(performance.getEntriesByType("resource").map(r => r.responseEnd))'
COLORS = {'h2': 'tab:red', 'h3': 'tab:blue'}

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


def finish_times(p, proto):
    if proto == 'h2':
        args = ['--disable-quic', TRUST]
    else:
        args = ['--enable-quic', '--origin-to-force-quic-on=localhost:8443', TRUST]
    b = p.chromium.launch(args=args)
    page = b.new_page()
    page.goto(URL, wait_until='load', timeout=180000)
    page.wait_for_timeout(300)
    used = page.evaluate("performance.getEntriesByType('navigation')[0].nextHopProtocol")
    t = sorted(json.loads(page.evaluate(JS)))
    b.close()
    if used != proto:
        raise Exception('wrong protocol used: ' + used)
    return t


raw = {}
rows = []
try:
    with sync_playwright() as p:
        for loss in LOSS_LEVELS:
            netem_on(loss)
            time.sleep(1)
            for i in range(RUNS):
                for proto in ['h2', 'h3']:
                    try:
                        t = finish_times(p, proto)
                    except Exception as e:
                        print('FAILED', loss, proto, i, e)
                        continue
                    gaps = np.diff(t)
                    rows.append([loss, proto, i, len(t), round(t[0]), round(t[-1]),
                                 round(float(gaps.max())), int((gaps > 1000).sum())])
                    raw.setdefault(f'{loss}_{proto}', []).append(t)
                    print('loss', loss, proto, 'run', i, 'images', len(t), 'last', round(t[-1]),
                          'ms | longest pause', round(float(gaps.max())), 'ms')
                    time.sleep(0.5)
finally:
    netem_off()
    print('netem removed')

with open('hol_metrics.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['loss', 'proto', 'run', 'images', 'first_ms', 'last_ms', 'longest_gap_ms', 'gaps_over_1s'])
    w.writerows(rows)
json.dump(raw, open('hol_raw.json', 'w'))

df = pd.read_csv('hol_metrics.csv')
print()
print('Medians per loss level and protocol:')
print(df.groupby(['loss', 'proto'])[['first_ms', 'last_ms', 'longest_gap_ms', 'gaps_over_1s']].median().round(0).to_string())

fig, axs = plt.subplots(1, len(LOSS_LEVELS), figsize=(11, 4.2))
for ax, loss in zip(axs, LOSS_LEVELS):
    for proto in ['h2', 'h3']:
        for k, t in enumerate(raw.get(f'{loss}_{proto}', [])):
            ax.step([x / 1000 for x in t], range(1, len(t) + 1), where='post', color=COLORS[proto],
                    alpha=0.4, lw=1, label=proto if k == 0 else None)
    ax.set_title(f'{loss}% packet loss ({RUNS} runs per protocol)')
    ax.set_xlabel('Time since navigation start (seconds)')
    ax.set_ylabel('Images finished (out of 30)')
    ax.grid(alpha=0.3)
    ax.legend()
plt.tight_layout()
plt.savefig('hol_steps.png', dpi=150)
plt.close()

fig, ax = plt.subplots(figsize=(6.5, 4.2))
data, labels = [], []
for loss in LOSS_LEVELS:
    for proto in ['h2', 'h3']:
        data.append(df[(df.loss == loss) & (df.proto == proto)]['longest_gap_ms'].values / 1000)
        labels.append(str(loss) + '%\n' + proto)
bp = ax.boxplot(data, patch_artist=True)
ax.set_xticklabels(labels)
for i, b in enumerate(bp['boxes']):
    b.set_facecolor('#EF9A9A' if i % 2 == 0 else '#90CAF9')
ax.set_ylabel('Longest pause between two images finishing (seconds)')
ax.set_title('Longest pause per run (red = h2, blue = h3)')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('hol_longest_gap.png', dpi=150)
plt.close()
print('saved hol_metrics.csv hol_raw.json hol_steps.png hol_longest_gap.png')
