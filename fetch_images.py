from pathlib import Path
import hashlib
import urllib.request
import zipfile

root = Path(__file__).resolve().parent
manifest = root / 'third_party/uhd-images-manifest.txt'
dest = root / 'prefix/share/uhd/images'
dest.mkdir(parents=True, exist_ok=True)
(root / 'downloads').mkdir(exist_ok=True)
for line in manifest.read_text().splitlines():
    cols = line.split()
    if len(cols) < 4 or cols[0] not in ('b2xx_b210_fpga_default', 'b2xx_common_fw_default'):
        continue
    name, _, relative, expected = cols[:4]
    archive = root / 'downloads' / (name + '.zip')
    if not archive.exists():
        with urllib.request.urlopen('https://files.ettus.com/binaries/cache/' + relative, timeout=60) as r:
            archive.write_bytes(r.read())
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError('Image checksum mismatch: ' + name)
    with zipfile.ZipFile(archive) as z:
        print(name + ': ' + ', '.join(z.namelist()), flush=True)
        z.extractall(dest)
    print('Verified ' + actual, flush=True)
