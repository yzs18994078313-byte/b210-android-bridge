"""Isolated, hardware-free Android tests. Does not start the installed app or open USB."""
from pathlib import Path
import os, re, socket, struct, subprocess, threading, time

ROOT = Path(__file__).resolve().parent
ADB = Path(os.environ.get('ADB', 'adb'))
(ROOT / 'tmp').mkdir(exist_ok=True)
(ROOT / 'build').mkdir(exist_ok=True)
ENV = dict(os.environ, TEMP=str(ROOT / 'tmp'), TMP=str(ROOT / 'tmp'))
REMOTE = '/data/local/tmp/b210bridge-1.0-test'
REPORT = ROOT / 'build/android-test.txt'
report = []
def log(s):
    print(s, flush=True); report.append(s)
def adb(*args, **kwargs):
    return subprocess.run([str(ADB), *args], env=ENV, check=True, text=True, capture_output=True, **kwargs).stdout
devices = [x.split()[0] for x in adb('devices').splitlines()[1:] if '\tdevice' in x]
if len(devices) != 1: raise RuntimeError('Expected exactly one available Android device')
SERIAL = devices[0]
def dev(*args): return adb('-s', SERIAL, *args)
log('Device: ' + SERIAL)
dev('shell', 'mkdir', '-p', REMOTE)
files = {
    'queue_tests': ROOT / 'build/bridge/queue_tests',
    'libusrp_bridge.so': ROOT / 'build/bridge/libusrp_bridge.so',
    'libuhd.so': ROOT / 'package/lib/libuhd.so',
    'libusb1.0.so': ROOT / 'prefix/lib/libusb1.0.so',
    'libc++_shared.so': ROOT / 'package/lib/libc++_shared.so',
}
for name, source in files.items(): dev('push', str(source), REMOTE + '/' + name)
dev('shell', 'chmod', '755', REMOTE + '/queue_tests', REMOTE + '/libusrp_bridge.so')
log(dev('shell', f'LD_LIBRARY_PATH={REMOTE} {REMOTE}/queue_tests').strip())
dev('forward', 'tcp:15556', 'tcp:5556')

class Backend:
    def __init__(self):
        self.lines = []; self.ready = threading.Event()
        self.process = subprocess.Popen([str(ADB), '-s', SERIAL, 'shell', '-T',
            f'LD_LIBRARY_PATH={REMOTE} exec {REMOTE}/libusrp_bridge.so --managed --synthetic --port 5556 --max-rate 8000000'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=ENV)
        def reader():
            for raw in self.process.stdout:
                line = raw.decode('utf-8', 'replace').strip(); self.lines.append(line)
                if line.startswith('READY'): self.ready.set()
        self.reader = threading.Thread(target=reader); self.reader.start()
        if not self.ready.wait(10): raise RuntimeError('Backend failed: ' + repr(self.lines))
    def finish(self, eof=False):
        start = time.monotonic()
        if not eof: self.process.stdin.write(b'STOP\n'); self.process.stdin.flush()
        self.process.stdin.close(); self.process.wait(timeout=3); self.reader.join(timeout=2)
        duration = time.monotonic() - start
        if self.process.returncode != 0: raise RuntimeError('Backend error: ' + repr(self.lines))
        if not any(x.startswith('STOPPED:') for x in self.lines): raise RuntimeError('Missing clean shutdown')
        log(('EOF' if eof else 'STOP') + f' clean exit: {duration:.3f} s')
        for line in self.lines:
            if line.startswith(('STAT:', 'Client disconnected:', 'CLIENT ERROR:', 'FATAL:')): log(line)
        return duration

VERSION = (2 << 24) | 1700
def exact(sock, count):
    out = bytearray()
    while len(out) < count:
        part = sock.recv(count - len(out))
        if not part: raise RuntimeError('Unexpected TCP EOF')
        out += part
    return out
def packet(sock):
    version, kind, stream, seq, size = struct.unpack('<5I', exact(sock, 20))
    assert version == VERSION and size <= 65536
    return kind, stream, seq, exact(sock, size)
def command(sock, kind, body): sock.sendall(struct.pack('<2I', kind, len(body)) + body)
def setting(sock, key, value): command(sock, 2, struct.pack('<2I', key, value))
def connect(small=False):
    sock = socket.socket(); sock.settimeout(4)
    if small: sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    sock.connect(('127.0.0.1', 15556))
    command(sock, 0, struct.pack('<I', VERSION) + b'B210-release-test')
    kind, stream, seq, body = packet(sock); info = struct.unpack('<12I', body)
    assert kind == 0 and info[0] == 0xb210 and info[2] == 8000000 and info[11] == 2
    assert packet(sock)[0] == 1
    return sock

try:
    backend = Backend(); sock = connect()
    # Fragmented control input, tuning and gain synchronisation.
    raw = struct.pack('<4I', 2, 8, 101, 145800000)
    for byte in raw: sock.sendall(bytes([byte]))
    kind, _, _, body = packet(sock); assert kind == 1 and struct.unpack('<9I', body)[2] == 145800000
    setting(sock, 2, 24); assert struct.unpack('<9I', packet(sock)[3])[1] == 24
    setting(sock, 102, 3); assert packet(sock)[0] == 1 # 1 MS/s
    setting(sock, 100, 2); assert packet(sock)[0] == 1
    setting(sock, 0, 1); assert packet(sock)[0] == 1
    setting(sock, 1, 1); assert packet(sock)[0] == 1
    end = time.monotonic() + 6; samples = 0; previous = None; tone = []
    while time.monotonic() < end:
        kind, stream, seq, body = packet(sock)
        assert kind == 101 and stream == 1 and len(body) % 4 == 0
        if previous is not None: assert seq == previous + 1
        previous = seq; samples += len(body) // 4
        if not tone: tone = list(struct.iter_unpack('<hh', body[:4000]))
    import math
    phase = sum(math.atan2(a[0]*b[1]-a[1]*b[0], a[0]*b[0]+a[1]*b[1]) for a,b in zip(tone,tone[1:]))
    hz = phase / (len(tone)-1) * 1000000 / (2*math.pi)
    assert abs(hz-35000) < 10 and samples >= 5000000
    log(f'PASS: fragmented commands, device info, forced sc16, tuning, gain, 1 MS/s IQ; tone={hz:.2f} Hz, samples={samples}')
    def next_kind(wanted):
        for _ in range(2000):
            result = packet(sock)
            if result[0] == wanted: return result
        raise RuntimeError('Missing expected message')
    # Exercise the new worker join/reset/restart path while receiving.
    setting(sock, 102, 4)
    assert next_kind(1)[0] == 1
    body = next_kind(101)[3]
    tone = list(struct.iter_unpack('<hh', body[:4000]))
    phase = sum(math.atan2(a[0]*b[1]-a[1]*b[0], a[0]*b[0]+a[1]*b[1]) for a,b in zip(tone,tone[1:]))
    hz = phase / (len(tone)-1) * 500000 / (2*math.pi)
    assert abs(hz-35000) < 10
    setting(sock, 101, 137100000)
    assert struct.unpack('<9I', next_kind(1)[3])[2] == 137100000
    setting(sock, 1, 0); assert next_kind(1)[0] == 1
    setting(sock, 1, 1); assert next_kind(1)[0] == 1
    assert next_kind(101)[3]
    log(f'PASS: live rate change to 500 kS/s, live tuning, stream stop/restart; tone={hz:.2f} Hz')
    sock.close(); time.sleep(.2)
    # Slow consumer must not stop capture. A full app queue must count exact dropped samples.
    sock = connect(small=True); setting(sock, 102, 0); assert packet(sock)[0] == 1
    setting(sock, 1, 1); assert packet(sock)[0] == 1
    time.sleep(1.5)
    end = time.monotonic() + 1; packets = 0
    while time.monotonic() < end: packet(sock); packets += 1
    assert packets > 0
    sock.close(); time.sleep(.2)
    # Stop while the network consumer is stalled.
    sock = connect(small=True); setting(sock, 1, 1); assert packet(sock)[0] == 1
    time.sleep(1)
    assert backend.finish() < 1.5
    sock.close()
    counts = [int(x) for line in backend.lines for x in re.findall(r'queue_dropped_samples=(\d+)', line)]
    assert counts and max(counts) > 0, 'Backpressure did not exercise queue drop accounting'
    assert not any('CLIENT ERROR:' in line or 'FATAL:' in line for line in backend.lines)
    log('PASS: slow client, bounded queue/drop accounting, reconnect, STOP during TCP backpressure')
    # App death (stdin EOF) must stop even with an incomplete client command.
    backend = Backend(); sock = socket.create_connection(('127.0.0.1', 15556), timeout=3); sock.sendall(b'\0')
    time.sleep(.1); assert backend.finish(eof=True) < 1.5; sock.close()
    log('PASS: managed stdin EOF interrupts partial command and exits cleanly')
finally:
    dev('forward', '--remove', 'tcp:15556')
    REPORT.write_text('\n'.join(report) + '\n', encoding='utf-8')
