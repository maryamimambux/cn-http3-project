import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

main = pd.read_csv('results.csv')
main['batch'] = 'main'
extra = pd.read_csv('results_extra.csv')
extra['batch'] = 'extra'
df = pd.concat([main, extra], ignore_index=True)
print('rows: main', len(main), '| extra', len(extra), '| total', len(df))
ok = df[df.proto == df.nextHop].copy()
print('rows with wrong protocol (removed):', len(df) - len(ok))

print()
print('1) Do the two batches agree? Median page load (ms) per batch:')
print(ok.groupby(['loss', 'proto', 'batch'])['load'].median().unstack('batch').round(0).to_string())


def q25(x):
    return x.quantile(0.25)


def q75(x):
    return x.quantile(0.75)


summary = ok.groupby(['loss', 'proto']).agg(
    n=('load', 'count'),
    connect_med=('connect', 'median'),
    ttfb_req_med=('ttfb_req', 'median'),
    ttfb_nav_med=('ttfb_nav', 'median'),
    load_med=('load', 'median'),
    load_q25=('load', q25),
    load_q75=('load', q75),
).round(1)
print()
print('2) Combined summary:')
print(summary.to_string())
summary.to_csv('summary_combined.csv')

rng = np.random.default_rng(1)


def boot_ci(a, b, n=5000):
    d = []
    for _ in range(n):
        d.append(np.median(rng.choice(a, len(a))) - np.median(rng.choice(b, len(b))))
    return np.percentile(d, [2.5, 97.5])


rows = []
for loss in sorted(ok.loss.unique()):
    a = ok[(ok.loss == loss) & (ok.proto == 'h2')]['load'].values
    b = ok[(ok.loss == loss) & (ok.proto == 'h3')]['load'].values
    lo, hi = boot_ci(a, b)
    if lo > 0:
        verdict = 'h3 faster (reliable)'
    elif hi < 0:
        verdict = 'h2 faster (reliable)'
    else:
        verdict = 'no clear difference'
    rows.append({'loss_%': loss, 'n_h2': len(a), 'n_h3': len(b),
                 'h2_median': round(float(np.median(a))), 'h3_median': round(float(np.median(b))),
                 'diff_h2_minus_h3': round(float(np.median(a) - np.median(b))),
                 'CI95_low': round(float(lo)), 'CI95_high': round(float(hi)), 'verdict': verdict})
res = pd.DataFrame(rows)
print()
print('3) Is the difference reliable? (page load, bootstrap 95% CI of median h2 minus h3, ms)')
print(res.to_string(index=False))
res.to_csv('reliability.csv', index=False)

ok['key'] = ok['batch'] + '_' + ok['run'].astype(str)
pv = ok.pivot_table(index=['loss', 'key'], columns='proto', values='load').dropna()
wins = (pv['h3'] < pv['h2']).groupby('loss').agg(['sum', 'count'])
wins.columns = ['h3_faster_runs', 'paired_runs']
print()
print('4) In how many paired runs was h3 faster?')
print(wins)


def plot(metric, title, fname):
    plt.figure(figsize=(6.4, 4.2))
    for proto, color in [('h2', 'tab:red'), ('h3', 'tab:blue')]:
        g = ok[ok.proto == proto].groupby('loss')[metric]
        m = g.median()
        lo = m - g.quantile(0.25)
        hi = g.quantile(0.75) - m
        plt.errorbar(m.index, m.values, yerr=[lo.values, hi.values], marker='o', capsize=3, color=color, label=proto)
    plt.xlabel('Packet loss (%)')
    plt.ylabel(title + ' (ms)')
    plt.title(title + ' vs packet loss (median, bars = quartiles)')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(fname, dpi=150)
    plt.close()


plot('load', 'Page load time', 'load_vs_loss_combined.png')
plot('ttfb_nav', 'TTFB (from navigation start)', 'ttfb_nav_vs_loss_combined.png')

fig, ax = plt.subplots(figsize=(7.5, 4.4))
data, labels = [], []
for loss in sorted(ok.loss.unique()):
    for proto in ['h2', 'h3']:
        data.append(ok[(ok.loss == loss) & (ok.proto == proto)]['load'].values / 1000)
        labels.append(str(loss) + '%\n' + proto)
bp = ax.boxplot(data, patch_artist=True)
ax.set_xticklabels(labels)
for i, b in enumerate(bp['boxes']):
    b.set_facecolor('#EF9A9A' if i % 2 == 0 else '#90CAF9')
ax.set_ylabel('Page load time (seconds)')
ax.set_title('Page load time per run (red = h2, blue = h3), combined runs')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('load_boxplot_combined.png', dpi=150)
plt.close()
print()
print('saved: summary_combined.csv reliability.csv load_vs_loss_combined.png ttfb_nav_vs_loss_combined.png load_boxplot_combined.png')
