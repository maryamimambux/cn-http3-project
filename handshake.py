import asyncio, socket, ssl, statistics, subprocess, sys, time
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration

CA = subprocess.check_output(['mkcert', '-CAROOT']).decode().strip() + '/rootCA.pem'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 50

ctx = ssl.create_default_context(cafile=CA)
ctx.minimum_version = ssl.TLSVersion.TLSv1_3
ctx.set_alpn_protocols(['h2'])

def tcp_tls_once():
    t0 = time.perf_counter()
    s = socket.create_connection(('127.0.0.1', 8443))
    t1 = time.perf_counter()
    ss = ctx.wrap_socket(s, server_hostname='localhost')
    t2 = time.perf_counter()
    ss.close()
    return (t1 - t0) * 1000, (t2 - t1) * 1000

async def quic_once():
    cfg = QuicConfiguration(is_client=True, alpn_protocols=['h3'], cafile=CA)
    cfg.server_name = 'localhost'
    t0 = time.perf_counter()
    async with connect('127.0.0.1', 8443, configuration=cfg) as c:
        t1 = time.perf_counter()
    return (t1 - t0) * 1000

# warm-up (not counted)
tcp_tls_once()
asyncio.run(quic_once())

tcp_list, tls_list, quic_list = [], [], []
for _ in range(N):
    a, b = tcp_tls_once()
    tcp_list.append(a)
    tls_list.append(b)
    quic_list.append(asyncio.run(quic_once()))
    time.sleep(0.2)

total = [a + b for a, b in zip(tcp_list, tls_list)]

def show(name, v):
    print(f'{name:22}: mean {statistics.mean(v):6.1f} | median {statistics.median(v):6.1f} | std {statistics.pstdev(v):5.1f} ms')

print(f'runs = {N}')
show('TCP handshake', tcp_list)
show('TLS 1.3 handshake', tls_list)
show('TCP + TLS total', total)
show('QUIC (incl. TLS 1.3)', quic_list)
print(f'gap (TCP+TLS minus QUIC), median: {statistics.median(total) - statistics.median(quic_list):.1f} ms')
