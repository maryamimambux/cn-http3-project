import asyncio, statistics, subprocess, sys, time
from aioquic.asyncio import connect, QuicConnectionProtocol
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DataReceived, HeadersReceived
from aioquic.quic.configuration import QuicConfiguration

CA = subprocess.check_output(['mkcert', '-CAROOT']).decode().strip() + '/rootCA.pem'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20


class H3Client(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._h3 = H3Connection(self._quic)
        self._waiting = {}
        self.t_headers = None

    def _finish(self, stream_id):
        fut = self._waiting.pop(stream_id, None)
        if fut is not None and not fut.done():
            fut.set_result(time.perf_counter())

    def quic_event_received(self, event):
        for e in self._h3.handle_event(event):
            if isinstance(e, HeadersReceived):
                if self.t_headers is None:
                    self.t_headers = time.perf_counter()
                if e.stream_ended:
                    self._finish(e.stream_id)
            if isinstance(e, DataReceived) and e.stream_ended:
                self._finish(e.stream_id)

    async def get(self, authority, path):
        sid = self._quic.get_next_available_stream_id()
        self._h3.send_headers(stream_id=sid, headers=[
            (b':method', b'GET'), (b':scheme', b'https'),
            (b':authority', authority.encode()), (b':path', path.encode())],
            end_stream=True)
        fut = asyncio.get_running_loop().create_future()
        self._waiting[sid] = fut
        self.transmit()
        return await fut


async def run_once(ticket, wait_connected, store):
    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN, cafile=CA)
    cfg.server_name = 'localhost'
    if ticket is not None:
        cfg.session_ticket = ticket
    t0 = time.perf_counter()
    async with connect('127.0.0.1', 8443, configuration=cfg, create_protocol=H3Client,
                       session_ticket_handler=store.append,
                       wait_connected=wait_connected) as c:
        t_done = await asyncio.wait_for(c.get('localhost:8443', '/'), 15)
        tls = c._quic.tls
        early = getattr(tls, 'early_data_accepted', None)
        await asyncio.sleep(0.3)  # lets the server's new ticket arrive
    return (c.t_headers - t0) * 1000, (t_done - t0) * 1000, early


async def main():
    full, resumed, zero, accepted, failed = [], [], [], 0, 0
    await run_once(None, True, [])  # warm-up, not counted
    for i in range(N):
        try:
            s1, s2, s3 = [], [], []
            full.append(await run_once(None, True, s1))
            resumed.append(await run_once(s1[-1], True, s2))
            r = await run_once(s2[-1], False, s3)
            zero.append(r)
            accepted += 1 if r[2] else 0
        except Exception as e:
            failed += 1
            print('run failed:', type(e).__name__, e)

    def line(name, rows):
        fb = [r[0] for r in rows]
        tt = [r[1] for r in rows]
        print(f'{name:28}: first byte median {statistics.median(fb):6.1f} ms | page complete median {statistics.median(tt):6.1f} ms')

    print(f'runs = {N}, failed = {failed}')
    if full and resumed and zero:
        line('A. QUIC full handshake', full)
        line('B. QUIC resumed (1-RTT)', resumed)
        line('C. QUIC 0-RTT', zero)
        print(f'0-RTT accepted by server in {accepted}/{len(zero)} runs')
        gain = statistics.median([r[1] for r in full]) - statistics.median([r[1] for r in zero])
        print(f'0-RTT gain vs full handshake (median page complete): {gain:.1f} ms')


asyncio.run(main())
