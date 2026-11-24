import json, numpy as np, pandas as pd
from scipy.stats import wilcoxon
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

d = pd.read_csv('results_matched.csv')
d['real_loss'] = d.dropped / d.pkts * 100
rows, pairs = [], []
for lv in ['2pct', '5pct']:
    a = d[(d.level == lv) & (d.proto == 'h2')].set_index('run')
    b = d[(d.level == lv) & (d.proto == 'h3')].set_index('run')
    for proto, x in [('h2', a), ('h3', b)]:
        rows.append(dict(level=lv, proto=proto, n=len(x), configured=x.configured.iloc[0],
            real_loss_pct=round(x.real_loss.mean(), 2),
            load_median_s=round(x.load.median()/1000, 2), load_mean_s=round(x.load.mean()/1000, 2),
            load_std_s=round(x.load.std()/1000, 2),
            ttfb_nav_median_ms=round(x.ttfb_nav.median()), connect_median_ms=round(x.connect.median())))
    j = pd.concat([a.load, b.load], axis=1, keys=['h2', 'h3']).dropna()
    pairs.append(dict(level=lv, pairs=len(j), h3_faster=int((j.h3 < j.h2).sum()),
        improvement_pct=round((j.h2.median()-j.h3.median())/j.h2.median()*100, 1),
        wilcoxon_p=round(wilcoxon(j.h2, j.h3).pvalue, 5)))
s = pd.DataFrame(rows); p = pd.DataFrame(pairs)
s.to_csv('matched_summary.csv', index=False); p.to_csv('matched_pairs.csv', index=False)
print(s.to_string(index=False)); print(); print(p.to_string(index=False)); print()

r = json.load(open('hol_matched_raw.json'))
out = []
for L in ['2', '5']:
    h2, h3 = r[f'{L}_h2'], r[f'{L}_h3']; n = min(len(h2), len(h3))
    f = lambda t: dict(first=t[0]/1000, last=t[-1]/1000, gap_between=max(np.diff(t))/1000,
                       gap_with_start=max(np.diff([0]+list(t)))/1000)
    A = [f(t) for t in h2[:n]]; B = [f(t) for t in h3[:n]]
    for k in ['first', 'last', 'gap_between', 'gap_with_start']:
        x = np.array([q[k] for q in A]); y = np.array([q[k] for q in B])
        out.append(dict(loss=L, measure=k, h2_median=round(np.median(x), 2), h3_median=round(np.median(y), 2),
                        h3_smaller_pairs=f'{(y<x).sum()}/{n}', wilcoxon_p=round(wilcoxon(x, y).pvalue, 5)))
h = pd.DataFrame(out); h.to_csv('hol_matched_summary.csv', index=False)
print(h.to_string(index=False))

data = [d[(d.level == lv) & (d.proto == pr)].load.values/1000 for lv in ['2pct', '5pct'] for pr in ['h2', 'h3']]
fig, ax = plt.subplots(figsize=(6.5, 4.2))
bp = ax.boxplot(data, patch_artist=True)
ax.set_xticklabels(['2%\nh2', '2%\nh3', '5%\nh2', '5%\nh3'])
for i, bx in enumerate(bp['boxes']):
    bx.set_facecolor('#EF9A9A' if i % 2 == 0 else '#90CAF9')
ax.set_ylabel('Page load time (s)')
ax.set_title('Page load at matched real loss (20 runs each)')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig('matched_load_boxplot.png', dpi=150)
print('saved')
