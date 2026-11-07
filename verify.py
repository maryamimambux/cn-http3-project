import os, subprocess, sys
from playwright.sync_api import sync_playwright

CERT = os.path.expanduser('~/cnproj/certs/localhost+1.pem')
HASH = subprocess.check_output(
    'openssl x509 -in ' + CERT + ' -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -binary | base64',
    shell=True).decode().strip()
TRUST = '--ignore-certificate-errors-spki-list=' + HASH

mode = sys.argv[1]
URL = 'https://localhost:8443/'
if mode == 'h3':
    args = ['--enable-quic', '--origin-to-force-quic-on=localhost:8443', TRUST]
else:
    args = ['--disable-quic', TRUST]

with sync_playwright() as p:
    b = p.chromium.launch(args=args)
    page = b.new_page()
    page.goto(URL, wait_until='load')
    page.wait_for_timeout(300)
    proto = page.evaluate("performance.getEntriesByType('navigation')[0].nextHopProtocol")
    print('mode', mode, '-> protocol used:', proto)
    b.close()
