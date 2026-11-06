# B210 Android Bridge 使用与实现说明

[返回项目首页](../README.md)

在已 root 的 Android 手机上，通过 USB 接收 USRP B210 的 IQ 数据，并用本机 SpyServer 协议交给 OnAir。无需修改 OnAir，也无需运行 Linux chroot。

当前版本 **1.0.0**。已在一加 8T、Android 16 自定义 ROM、USB 3 和 OnAir 3.6.0 上验证接收与调频。用户复测反馈：**未再出现之前的接收溢出**。尚未记录该次实测的采样率和持续时间，因此这一结果仅代表已测试组合。

```text
B210（RF A / RX2）
    │ USB 3，B210 外置供电
    ▼
Android 前台服务 → root 原生后端 → UHD / libusb 接收线程
                                      │ 有界 IQ 队列
                                      ▼
                           本机 SpyServer：127.0.0.1:5555
                                      │ 16-bit IQ
                                      ▼
                                    OnAir
```

## 功能

- 单通道接收，支持 OnAir 调频、调整增益和选择采样率。
- 本机 SpyServer IQ 模式，固定交错有符号 16-bit I/Q，不修改 OnAir。
- USB 接收与 TCP 发送分线程；预分配约 0.5 秒的环形队列。
- 分别统计 UHD 溢出事件和应用队列丢样，支持导出运行日志。
- 内置匹配 UHD 4.8 的 B210 FPGA / FX3 镜像，可导入自定义 FPGA `.bin`。
- 前台通知、接收期间唤醒锁、通知停止操作和后端退出清理。
- 无需电台或 root 的模拟 IQ 模式，用于核对连接与协议。

## 已验证环境

| 项目 | 配置 |
|---|---|
| 手机 | 一加 8T，KB2000，ARM64 |
| 系统 | Android 16 自定义 ROM，已 root |
| 电台 | USRP B210，外置供电 |
| USB | 已验证的 USB 3 连接 |
| 客户端 | adswill/OnAir 3.6.0 |
| 接收端口 | RF A 的 RX2 |

APK 声明最低 Android 9，目标 API 35；其他手机、ROM 和 Android 版本尚未实测。实际电台接收依赖 root 权限访问 USB 设备。

## 安装和连接

1. 从本仓库 [Releases](https://github.com/yzs18994078313-byte/b210-android-bridge/releases) 获取 `B210-Bridge-1.0.0-arm64.apk`，安装到手机。
2. 给 B210 外置供电，连接 USB 3，并将天线接到 RF A / RX2。
3. 打开“B210 本机桥接”，设置初始频率、增益和最高采样率，点击“启动本机服务”，在 root 管理器中授权。
4. 日志显示 `READY` 后，在 OnAir 选择网络电台 / SpyServer，地址填 `127.0.0.1`，默认端口填 `5555`。
5. 在 OnAir 中选择实际采样率，调谐频率并接收。结束时使用桥接 App 或通知中的“停止服务”。

退出 App 界面不会停止正在运行的接收服务。服务仅绑定本机回环地址。

“最高采样率”决定向客户端公告的上限；OnAir 可选择该值的 1、1/2、1/4、1/8 或 1/16。例如上限 4 MS/s 时，实际可选 4、2、1、0.5 或 0.25 MS/s。单通道 16-bit IQ 每个复数样本占 4 字节，4 MS/s 对应约 16 MB/s 的样本数据。

现有 0.1.0 测试版可用同一签名的 1.0.0 APK 覆盖安装，已导入的 FPGA 保留。自行构建时应继续使用自己的同一签名密钥，才能覆盖自己的旧版安装。

## 连续接收与溢出处理

1.0.0 将 USB 接收放到独立线程，TCP 发送、客户端控制与日志统计在另一线程处理，避免客户端暂时停止读取时直接阻塞 UHD `recv()`。

USB 接收池配置为 `128 × 16360` 字节，约 2 MiB。应用使用约 0.5 秒的预分配 IQ 队列；队列满时仍继续取走 USB 数据，并累计丢弃的复数样本数。root 后端尝试提高接收线程的 CFS nice 优先级，未修改内核 USB 中断处理程序、IRQ 亲和性或全局 USB 参数。

有限队列用于吸收短时调度抖动，不能补偿持续的吞吐不足。1.0.0 的改进已通过用户实机复测，但不能保证其他采样率、后台负载和设备组合都不会丢样。

### 诊断字段

接收中每 5 秒输出一条 `STAT:`，App 可显示主要指标并导出日志。

| 字段 | 含义 |
|---|---|
| `rate` | 实际采样率，S/s |
| `usb_overflows` | UHD 上报的接收溢出事件数，不是丢失样本数 |
| `queue_dropped_samples` | 应用队列满时丢失的复数样本数 |
| `queue` | 当前队列块数 / 容量 |
| `tcp_waits` | TCP 写入等待次数 |
| `send_peak_ms` | 单包发送耗时峰值 |
| `retune_discarded` | 调频时主动清理的已排队样本数 |

若应用队列丢样持续增加，先降低 OnAir 中的**实际采样率**进行比较。若主要是 `usb_overflows` 增加，请同时记录采样率、手机温度、后台负载及溢出前后的 UHD 日志。

## FPGA 与固件

默认镜像按 UHD 4.8 的官方清单下载并校验。停止服务后，可导入 B210 FPGA `.bin`，下次初始化时由 UHD 加载和检查兼容性。这个操作不是烧写永久存储。若自定义镜像加载失败，可点击“恢复标准 B210 镜像”。

自定义 FPGA 必须与所用 UHD、B210 USB 接口及数据格式兼容；仅有 `.bin` 扩展名不代表兼容。

## 构建

当前构建脚本面向 **Windows + Android NDK r28c**，无需 Android Studio。详细工具路径与步骤见 [BUILD.md](../BUILD.md)。

```powershell
python -m pip install --target tools/py -r requirements-build.txt
python fetch_sources.py
python fetch_app_tools.py
./build_native.ps1
python fetch_images.py
python build_app.py
```

生成的 APK 位于 `dist/`。首次下载包含 NDK、Boost、UHD 和 Android 构建工具，体积较大；已有 NDK 时可用 `python fetch_sources.py --skip-ndk`，并按构建文档设置工具路径。

| 依赖 | 版本 |
|---|---|
| UHD | v4.8.0.0，`308126a479ca19dfaebfe4784b375e608788d763` |
| libusb | 1.0.27 |
| Boost | 1.85.0，静态 PIC 链接 |
| Android NDK | r28c，arm64-v8a |
| Android SDK platform / build-tools | 35 / 35 |
| Java | JDK 17 |

运行时使用 Android 原生 Bionic 与 `libc++_shared.so`。包内 `libusrp_bridge.so` 是采用 `.so` 文件名打包的 PIE 可执行程序，由前台服务通过 `su -c` 启动；实际 UHD 动态库为 `libuhd.so`，桥接程序不是 JNI 插件。

## 测试

- **用户实机**：B210 接收和调频正常，1.0.0 复测反馈未再溢出。采样率和测试时长未提供。
- **手机模拟 IQ**：约 6 秒的 1 MS/s、35 kHz 测试载波，应用队列未丢样；接收中切换到 500 kS/s、调频、停流和重启均通过。
- **队列并发**：20 万次生产尝试，覆盖满队列、回绕、FIFO、持有块不被覆盖与丢样计数。
- **背压与退出**：慢客户端时继续采集、记录队列丢样，断开重连正常；STOP / 标准输入 EOF 清理约 0.1 秒。
- **APK**：签名验证、ARM64 依赖与 16 KiB 对齐检查通过，已覆盖安装到实机。

模拟测试记录见 [docs/android-test-1.0.0.txt](android-test-1.0.0.txt)。构建完成后可运行 `python test_android.py` 重测；它使用独立端口 5556 与模拟信号，不打开 B210。

## 项目结构

```text
app/                      Android 页面和前台服务
bridge/                   SpyServer、UHD 接收线程、有界队列及测试
libusb-cmake/             Android libusb 构建工程
third_party/              版本清单、UHD 补丁和第三方许可证
docs/                     使用说明和测试记录
build_native.ps1          原生依赖及桥接程序构建
build_app.py              Java / DEX / APK 打包与签名
fetch_sources.py           下载固定版本源码及 NDK
fetch_images.py            下载并验证 FX3 / FPGA 镜像
```

## 当前范围

仅实现单客户端、单通道接收及 SpyServer IQ 子集；不支持发射、FFT 流、多客户端或远程监听。桥接协议中的调谐范围为 70 MHz–4.29 GHz。SatDump 原生接入尚未验证，本仓库不包含 SatDump 移植。

## 许可证与上游

项目桥接代码采用 **GPL-3.0-or-later**，见 [LICENSE](../LICENSE)。第三方组件保留各自许可证，见 [third_party/README.md](../third_party/README.md)。仓库不包含签名私钥、工具链、下载缓存或本机设备标识。完整依赖源码包可作为 Release 附件分发。

- [Ettus Research UHD](https://github.com/EttusResearch/uhd/tree/v4.8.0.0)
- [libusb](https://github.com/libusb/libusb/tree/v1.0.27)
- [Boost](https://github.com/boostorg/boost/releases/tag/boost-1.85.0)
- [OnAir](https://github.com/adswill/OnAir)
