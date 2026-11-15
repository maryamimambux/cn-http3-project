import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

df = pd.read_csv('results.csv')
print('rows:', len(df))
bad = df[df.proto != df.nextHop]
print('rows with wrong protocol (removed):', len(bad))
ok = df[df.proto == df.nextHop].copy()


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
    load_mean=('load', 'mean'),
    load_std=('load', 'std'),
    load_q25=('load', q25),
    load_q75=('load', q75),
).round(1)
print()
print(summary.to_string())
summary.to_csv('summary.csv')

# h3 compared with h2 (medians)
med = ok.groupby(['loss', 'proto'])[['ttfb_nav', 'load']].median().unstack('proto')
rows = []
for loss in sorted(ok.loss.unique()):
    row = {'loss_%': loss}
    for m in ['ttfb_nav', 'load']:
        h2 = med[m]['h2'][loss]
        h3 = med[m]['h3'][loss]
        row[m + '_h2'] = round(h2, 1)
        row[m + '_h3'] = round(h3, 1)
        row[m + '_h3_faster_%'] = round((h2 - h3) / h2 * 100, 1)
    rows.append(row)
imp = pd.DataFrame(rows)
print()
print(imp.to_string(index=False))
imp.to_csv('improvement.csv', index=False)

# paired wins: in how many runs was h3 faster than h2 (same loss, same run number)?
pv = ok.pivot_table(index=['loss', 'run'], columns='proto', values='load').dropna()
wins = (pv['h3'] < pv['h2']).groupby('loss').agg(['sum', 'count'])
wins.columns = ['h3_faster_runs', 'paired_runs']
print()
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


plot('load', 'Page load time', 'load_vs_loss.png')
plot('ttfb_nav', 'TTFB (from navigation start)', 'ttfb_nav_vs_loss.png')
plot('ttfb_req', 'TTFB (request to first byte)', 'ttfb_req_vs_loss.png')
plot('connect', 'Connection setup time', 'connect_vs_loss.png')

# box plot of page load times (seconds)
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
ax.set_title('Page load time per run (red = h2, blue = h3)')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('load_boxplot.png', dpi=150)
plt.close()
print()
print('graphs saved: load_vs_loss.png ttfb_nav_vs_loss.png ttfb_req_vs_loss.png connect_vs_loss.png load_boxplot.png')
