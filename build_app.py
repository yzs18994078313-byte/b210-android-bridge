from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import zipfile

root = Path(__file__).resolve().parent
tools = root / 'tools'
ndk = Path(os.environ.get('ANDROID_NDK_HOME', str(tools / 'android-ndk-r28c')))
jdk = tools / 'jdk-17.0.17+10'
buildtools = next(tools.glob('*/aapt2.exe')).parent
android = tools / 'android-35/android.jar'
out = root / 'build/app'
out.mkdir(parents=True, exist_ok=True)
classes, dex = out / 'classes', out / 'dex'
classes.mkdir(exist_ok=True); dex.mkdir(exist_ok=True)
env = dict(os.environ, JAVA_HOME=str(jdk))
env['PATH'] = str(jdk / 'bin') + os.pathsep + env.get('PATH', '')
def run(*args):
    print('Running ' + str(args[0]), flush=True)
    subprocess.run([str(x) for x in args], check=True, env=env)

run(jdk / 'bin/javac.exe', '-encoding', 'UTF-8', '-source', '8', '-target', '8', '-bootclasspath', str(android) + os.pathsep + str(buildtools / 'core-lambda-stubs.jar'),
    '-d', classes, *sorted((root / 'app/src').rglob('*.java')))
jar = out / 'app-classes.jar'
with zipfile.ZipFile(jar, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in classes.rglob('*.class'): z.write(p, p.relative_to(classes).as_posix())
run(jdk / 'bin/java.exe', '-cp', buildtools / 'lib/d8.jar', 'com.android.tools.r8.D8', '--lib', android, '--min-api', '28', '--output', dex, jar)
unsigned = out / 'unsigned.apk'
run(buildtools / 'aapt2.exe', 'link', '-I', android, '--manifest', root / 'app/AndroidManifest.xml', '-o', unsigned)

sdk = root / 'package'
(sdk / 'lib').mkdir(parents=True, exist_ok=True)
(sdk / 'bin').mkdir(exist_ok=True)
(sdk / 'share/uhd/images').mkdir(parents=True, exist_ok=True)
payload = {
 'libuhd.so': root / 'build/uhd/lib/libuhd.so',
 'libusb1.0.so': root / 'prefix/lib/libusb1.0.so',
 'libc++_shared.so': ndk / 'toolchains/llvm/prebuilt/windows-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so',
 'libusrp_bridge.so': root / 'build/bridge/libusrp_bridge.so',
}
strip = ndk / 'toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-strip.exe'
for name, src in payload.items():
    shutil.copy2(src, sdk / 'lib' / name)
    if name != 'libc++_shared.so': run(strip, '--strip-unneeded', sdk / 'lib' / name)
with zipfile.ZipFile(unsigned, 'a') as z:
    z.write(dex / 'classes.dex', 'classes.dex', compress_type=zipfile.ZIP_DEFLATED)
    for name in payload: z.write(sdk / 'lib' / name, 'lib/arm64-v8a/' + name, compress_type=zipfile.ZIP_STORED)
    for name in ('usrp_b200_fw.hex', 'usrp_b210_fpga.bin'):
        src = root / 'prefix/share/uhd/images' / name
        z.write(src, 'assets/images/' + name, compress_type=zipfile.ZIP_DEFLATED)
        shutil.copy2(src, sdk / 'share/uhd/images' / name)
aligned = out / 'aligned.apk'
run(buildtools / 'zipalign.exe', '-P', '16', '-f', '4', unsigned, aligned)
key = root / 'build/debug-signing.p12'
if not key.exists():
    run(jdk / 'bin/keytool.exe', '-genkeypair', '-keystore', key, '-storetype', 'PKCS12', '-alias', 'b210-bridge', '-storepass', 'android', '-keypass', 'android', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '3650', '-dname', 'CN=B210 Bridge Development')
deliverables = Path(os.environ.get('B210_DIST_DIR', str(root / 'dist'))).resolve()
deliverables.mkdir(parents=True, exist_ok=True)
apk = deliverables / 'B210-Bridge-1.0.0-arm64.apk'
run(jdk / 'bin/java.exe', '-jar', buildtools / 'lib/apksigner.jar', 'sign', '--ks', key, '--ks-key-alias', 'b210-bridge', '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', apk, aligned)
run(jdk / 'bin/java.exe', '-jar', buildtools / 'lib/apksigner.jar', 'verify', '--verbose', apk)
run(buildtools / 'aapt2.exe', 'dump', 'badging', apk)
print('APK: ' + str(apk), flush=True)
print('SHA256: ' + hashlib.sha256(apk.read_bytes()).hexdigest(), flush=True)
