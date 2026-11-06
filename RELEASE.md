# B210 Android Bridge 1.0.0

适用于已 root 的 ARM64 Android 手机，通过 USB 连接 B210，以本机 SpyServer 向 OnAir 提供 16-bit IQ。

- 已验证：一加 8T / Android 16 自定义 ROM / USB 3 / B210 外置供电 / OnAir 3.6.0。
- 用户已验证真实接收与调频正常，复测反馈未再出现之前的溢出；实际采样率和测试时长未提供。
- 独立 USB 接收线程、约 0.5 秒预分配队列及扩大 USB 接收池。
- 分开统计 UHD 溢出事件和应用队列丢样，支持导出日志。
- 支持标准 FPGA / FX3 镜像、自定义 B210 FPGA 导入及恢复。
- 改进慢客户端、断开重连、STOP 和应用后端退出时的清理。

安装 APK 后，启动桥接服务，等待 `READY`，然后在 OnAir 中连接 SpyServer `127.0.0.1:5555`。使用 RF A / RX2 天线口。

APK 与原 0.1.0 测试版使用同一签名，可覆盖安装。其他 Android / ROM / 采样率组合尚未系统测试。

附件包括 ARM64 APK、附带原生依赖的源码包及 SHA-256 校验值。详情见仓库 README 和 BUILD.md。
