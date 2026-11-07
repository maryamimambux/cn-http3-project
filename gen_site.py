import os
from PIL import Image

os.makedirs('site/img', exist_ok=True)
N = 30
for i in range(1, N + 1):
    img = Image.frombytes('RGB', (200, 200), os.urandom(200 * 200 * 3))
    img.save(f'site/img/pic{i}.png')

html = ['<!doctype html><html><head><meta charset=utf-8><title>Test page</title></head><body><h1>Test page</h1>']
for i in range(1, N + 1):
    html.append(f'<img src=img/pic{i}.png width=100 height=100>')
html.append('</body></html>')
open('site/index.html', 'w').write(''.join(html))
print('site created')
