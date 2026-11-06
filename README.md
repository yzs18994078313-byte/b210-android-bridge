# B210 Android Bridge

在已 root 的 Android 手机上，通过 USB 接收 USRP B210，并以本机 SpyServer 向 OnAir 提供 **16-bit IQ**。无需修改 OnAir 或使用 Linux chroot。

支持调频、增益和采样率控制、自定义 FPGA 加载、接收统计及日志导出。当前版本 **1.0.0**。

## 快速开始

1. 从 [Releases](https://github.com/yzs18994078313-byte/b210-android-bridge/releases) 下载并安装 ARM64 APK。
2. 给 B210 外置供电，通过 USB 3 连接手机，天线接到 **RF A / RX2**。
3. 打开“B210 本机桥接”，启动服务并授予 root 权限，等待日志显示 `READY`。
4. 在 OnAir 选择 **SpyServer**，连接 `127.0.0.1:5555`，再选择采样率并调谐。

结束接收时，点击 App 或通知中的“停止服务”；退出界面不会停止接收。

## 已验证环境

**一加 8T（KB2000）· Android 16 自定义 ROM · root · USB 3 · B210 外置供电 · OnAir 3.6.0**

已确认接收、调频正常，1.0.0 实机复测未再出现之前的溢出。其他设备和系统组合尚未实测。

## 构建与文档

构建环境为 **Windows + Android NDK r28c**，使用 UHD 4.8、libusb 1.0.27 和 Boost 1.85。

- [构建步骤](BUILD.md)
- [采样率、FPGA、溢出诊断与实现说明](docs/DETAILS.md)
- [测试记录](docs/android-test-1.0.0.txt) · [更新记录](CHANGELOG.md)

目前支持单通道接收和本机单客户端连接；SatDump 接入尚未验证。

## 许可证

[GPL-3.0-or-later](LICENSE)。第三方组件遵循[各自许可证](third_party/README.md)。
