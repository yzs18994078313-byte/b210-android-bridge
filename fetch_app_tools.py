from pathlib import Path
import concurrent.futures
import hashlib
import subprocess
import zipfile

root = Path(__file__).resolve().parent
(root / 'downloads').mkdir(exist_ok=True)
(root / 'tools').mkdir(exist_ok=True)
items = [
 ('platform35.zip', 'https://dl.google.com/android/repository/platform-35_r02.zip', '0bb560a90a7a2cbd0dd8348224d518b638fe7949'),
 ('buildtools35.zip', 'https://dl.google.com/android/repository/build-tools_r35_windows.zip', 'af059bb67cf7786f45ee0db85e2d24985df1b4b6'),
 ('jdk17.zip', 'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.17%2B10/OpenJDK17U-jdk_x64_windows_hotspot_17.0.17_10.zip', None),
]
def fetch(item):
    name, url, sha1 = item
    p = root / 'downloads' / name
    if not p.exists():
        print('Downloading ' + name, flush=True)
        tmp = p.with_suffix('.part')
        subprocess.run(['C:/Windows/System32/curl.exe','--fail','--location','--silent','--show-error','--retry','2','--max-time','300','--output',str(tmp),url],check=True)
        tmp.replace(p)
    actual = hashlib.sha1(p.read_bytes()).hexdigest()
    if sha1 and actual != sha1:
        raise RuntimeError('Checksum mismatch: ' + name)
    marker = root / 'tools' / (name + '.extracted')
    if not marker.exists():
        print('Extracting ' + name, flush=True)
        with zipfile.ZipFile(p) as z:
            z.extractall(root / 'tools')
        marker.write_text(actual)
    print('Ready ' + name, flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(fetch, items))
