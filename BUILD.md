# Windows / Android NDK 构建

原生接收代码和 Android 应用源码与实机通过测试的 1.0.0 一致。仓库整理时仅调整了工具路径、依赖获取和产物输出方式；尚未在全新的空目录完整重建工具链。

## 工具

准备 Python 3.12 或更新版本、Git、PowerShell 和可访问上游下载站点的网络。在仓库根目录执行：

```powershell
python -m pip install --target tools/py -r requirements-build.txt
python fetch_sources.py
python fetch_app_tools.py
```

`fetch_sources.py` 下载并校验 Boost 1.85.0、libusb 1.0.27、Windows NDK r28c，并稀疏检出固定提交的 UHD host / images 目录。已有 NDK 可改用：

```powershell
python fetch_sources.py --skip-ndk
$env:ANDROID_NDK_HOME = 'C:/path/to/android-ndk-r28c'
```

`fetch_app_tools.py` 下载 Android SDK platform 35、build-tools 35 和 JDK 17。首次下载文件较大，缓存保留在 `downloads/`。

默认工具布局：

```text
tools/android-ndk-r28c/
tools/jdk-17.0.17+10/
tools/android-35/android.jar
tools/android-15/aapt2.exe
tools/android-15/zipalign.exe
tools/android-15/core-lambda-stubs.jar
tools/android-15/lib/d8.jar
tools/android-15/lib/apksigner.jar
tools/py/cmake/data/bin/cmake.exe
tools/py/bin/ninja.exe
```

`android-15` 是 build-tools 35 官方 Windows ZIP 内的目录名。脚本也接受 Ninja wheel 常见路径 `tools/py/ninja/data/bin/ninja.exe`。

## 编译与打包

```powershell
./build_native.ps1
python fetch_images.py
python build_app.py
```

原生脚本依次构建 libusb、静态 PIC Boost、动态 UHD 和桥接后端，并执行可重复的 Android 补丁。镜像脚本使用仓库内固定的 UHD 镜像清单，下载对应 FX3 / FPGA 镜像后验证 SHA-256。APK 脚本编译 Java、生成 DEX、打包原生库和镜像、执行 16 KiB ZIP 对齐并签名。

默认产物为 `dist/B210-Bridge-1.0.0-arm64.apk`。可通过 `B210_DIST_DIR` 环境变量指定其他输出目录。

`build/debug-signing.p12` 不存在时，会生成本地开发签名。仓库和 Release 源码包均不包含本次实机使用的签名私钥；重新生成的密钥不能覆盖采用其他密钥签署的已安装 APK。个人后续版本请持续使用自己的同一密钥并自行保管，勿提交到 Git。

## 测试

```powershell
# 确保 adb 在 PATH，或先设置它的实际路径：
$env:ADB = 'C:/path/to/adb.exe'
python test_android.py
```

测试要求电脑只连接一部可用 Android 设备，并使用构建和 APK 打包阶段产生的库。测试后端放在 `/data/local/tmp/b210bridge-1.0-test`，以模拟信号监听手机 `127.0.0.1:5556`；电脑端使用 15556 转发。它不访问 B210、不启动已安装 App，也不占用正式服务默认端口 5555。

测试记录写入 `build/android-test.txt`；仓库保留的既有记录在 `docs/android-test-1.0.0.txt`，已移除设备地址。

## 发布打包

```powershell
python package_release.py
```

脚本将 `dist/` 中的 APK 与当前项目源码及构建所需的 UHD host、libusb、Boost 源码归档打包，并生成 `SHA256SUMS.txt`。`--dependency-root` 可指定已有依赖的本地工作目录；默认使用当前仓库。所有签名密钥、工具链和缓存目录均排除。

本次发布沿用已通过实机测试的 APK，未因仓库整理重新签名或改变接收代码。
