"""Download pinned native dependencies and optionally the Windows NDK."""
import argparse
import concurrent.futures
import hashlib
from pathlib import Path
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
UHD_COMMIT = '308126a479ca19dfaebfe4784b375e608788d763'

def obtain(name, url, algorithm, expected, folder):
    archive = ROOT / 'downloads' / name
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        partial = archive.with_suffix(archive.suffix + '.part')
        print('Downloading ' + name, flush=True)
        with urllib.request.urlopen(url, timeout=90) as response, partial.open('wb') as out:
            while chunk := response.read(1024 * 1024): out.write(chunk)
        actual = hashlib.file_digest(partial.open('rb'), algorithm).hexdigest()
        if actual != expected: raise RuntimeError('Checksum mismatch: ' + name)
        partial.replace(archive)
    actual = hashlib.file_digest(archive.open('rb'), algorithm).hexdigest()
    if actual != expected: raise RuntimeError('Checksum mismatch: ' + name)
    destination = ROOT / folder
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / (name + '.extracted')
    if not marker.exists():
        if name.endswith('.zip'):
            with zipfile.ZipFile(archive) as z: z.extractall(destination)
        else:
            with tarfile.open(archive) as t: t.extractall(destination, filter='data')
        marker.write_text(actual, encoding='ascii')
    print('Ready: ' + name, flush=True)

def uhd():
    path = ROOT / 'src/uhd-git'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        subprocess.run(['git', 'clone', '--depth', '1', '--filter=blob:none', '--sparse',
                        '--branch', 'v4.8.0.0', 'https://github.com/EttusResearch/uhd.git', str(path)], check=True)
        subprocess.run(['git', '-C', str(path), 'sparse-checkout', 'set', 'host', 'images'], check=True)
    if (path / '.git').exists():
        commit = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
        if commit != UHD_COMMIT: raise RuntimeError('Unexpected UHD commit: ' + commit)
    elif not (path / 'host/CMakeLists.txt').is_file():
        raise RuntimeError('Incomplete UHD source directory')
    print('Ready: UHD v4.8.0.0 (' + UHD_COMMIT + ')', flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-ndk', action='store_true', help='Use an existing NDK instead of downloading it')
    args = parser.parse_args()
    items = [
        ('boost.tar.xz', 'https://github.com/boostorg/boost/releases/download/boost-1.85.0/boost-1.85.0-cmake.tar.xz',
         'sha256', '0a9cc56ceae46986f5f4d43fe0311d90cf6d2fa9028258a95cab49ffdacf92ad', 'src'),
        ('libusb.tar.gz', 'https://codeload.github.com/libusb/libusb/tar.gz/refs/tags/v1.0.27',
         'sha256', 'e8f18a7a36ecbb11fb820bd71540350d8f61bcd9db0d2e8c18a6fb80b214a3de', 'src'),
    ]
    if not args.skip_ndk:
        items.append(('ndk.zip', 'https://dl.google.com/android/repository/android-ndk-r28c-windows.zip',
                      'sha1', '086bba43ff2f5eb0e387b15c8278bb4e0d89ba1d', 'tools'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(obtain, *item) for item in items] + [pool.submit(uhd)]
        for job in jobs: job.result()

if __name__ == '__main__': main()
