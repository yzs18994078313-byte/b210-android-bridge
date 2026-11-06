"""Package an existing tested APK with project and native dependency sources."""
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dependency-root', type=Path, default=ROOT)
args = parser.parse_args()
dependencies = args.dependency_root.resolve()
out = ROOT / 'dist'
out.mkdir(exist_ok=True)
apk = out / 'B210-Bridge-1.0.0-arm64.apk'
if not apk.is_file(): raise SystemExit('Build or copy the tested APK into dist/ first')
archive = out / 'B210-Bridge-1.0.0-source.zip'
excluded = {'.git', 'tools', 'downloads', 'src', 'build', 'prefix', 'package', 'dist', 'tmp', '__pycache__', '.idea', '.vscode'}
private_suffixes = {'.p12', '.pfx', '.jks', '.keystore', '.pem', '.key', '.pyc', '.pyo', '.apk', '.idsig'}
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    def add(source, relative, stored=False):
        if source.suffix.lower() in private_suffixes: raise RuntimeError('Unexpected private or generated file: ' + str(relative))
        z.write(source, 'b210-android-bridge-1.0.0/' + relative,
                compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
    for p in sorted(ROOT.rglob('*')):
        relative = p.relative_to(ROOT)
        if p.is_file() and relative.parts[0] not in excluded and '__pycache__' not in relative.parts:
            add(p, relative.as_posix())
    for folder in ('src/uhd-git/host', 'src/uhd-git/images', 'src/libusb-1.0.27'):
        base = dependencies / folder
        if not base.is_dir(): raise RuntimeError('Missing dependency source: ' + str(base))
        for p in sorted(base.rglob('*')):
            if p.is_file() and '.git' not in p.relative_to(base).parts: add(p, p.relative_to(dependencies).as_posix())
    add(dependencies / 'src/uhd-git/LICENSE.md', 'src/uhd-git/LICENSE.md')
    for name in ('boost.tar.xz', 'b2xx_b210_fpga_default.zip', 'b2xx_common_fw_default.zip'):
        add(dependencies / 'downloads' / name, 'downloads/' + name, stored=True)
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None: raise RuntimeError('Source archive integrity check failed')
    for required in ('README.md', 'app/src/org/usrp/b210bridge/MainActivity.java',
                     'app/src/org/usrp/b210bridge/BridgeService.java', 'bridge/server.cpp', 'downloads/boost.tar.xz'):
        if 'b210-android-bridge-1.0.0/' + required not in z.namelist():
            raise RuntimeError('Source archive omitted a required file: ' + required)
checksums = [hashlib.file_digest(p.open('rb'), 'sha256').hexdigest() + '  ' + p.name for p in (apk, archive)]
(out / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')
print('\n'.join(checksums))
