import socket, ssl, subprocess, time
import statistics

CA = subprocess.check_output(['mkcert', '-CAROOT']).decode().strip() + '/rootCA.pem'
ctx = ssl.create_default_context(cafile=CA)
ctx.minimum_version = ssl.TLSVersion.TLSv1_3
ctx.set_alpn_protocols(['http/1.1'])

def conn(session=None):
    t0 = time.perf_counter()
    s = socket.create_connection(('127.0.0.1', 8443))
    ss = ctx.wrap_socket(s, server_hostname='localhost', session=session)
    t1 = time.perf_counter()
    ss.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
    while ss.recv(65536):
        pass
    sess, reused = ss.session, ss.session_reused
    ss.close()
    return (t1 - t0) * 1000, sess, reused
"""
t_full, sess, reused1 = conn()
print(f'Full handshake    : {t_full:.1f} ms  reused={reused1}')
for i in range(5):
    t_res, sess2, reused2 = conn(sess)
    print(f'Resumed handshake : {t_res:.1f} ms  reused={reused2}')
"""

N = 20
full, resumed, reuse_ok = [], [], 0
for i in range(N):
    t_full, sess, r1 = conn()
    full.append(t_full)
    t_res, sess2, r2 = conn(sess)
    resumed.append(t_res)
    reuse_ok += 1 if r2 else 0
print(f'runs = {N}, session reused in {reuse_ok}/{N} resumed connections')
print(f'TCP+TLS full handshake    : median {statistics.median(full):6.1f} ms | mean {statistics.mean(full):6.1f} ms')
print(f'TCP+TLS resumed handshake : median {statistics.median(resumed):6.1f} ms | mean {statistics.mean(resumed):6.1f} ms')



