# 第三方组件

| 组件 | 来源 / 固定版本 | 许可证 |
|---|---|---|
| UHD host | EttusResearch/uhd，v4.8.0.0，308126a479ca19dfaebfe4784b375e608788d763 | GPL-3.0-or-later，另见上游单文件声明 |
| libusb | libusb/libusb，v1.0.27 | LGPL-2.1-or-later |
| Boost | boost-1.85.0-cmake.tar.xz | Boost Software License 1.0 |
| libc++ runtime | Android NDK r28c | 见 NDK-LLVM-NOTICE |
| B210 FPGA / FX3 镜像 | UHD 4.8 镜像清单 | 见对应上游包与文件声明 |

`uhd-android.patch` 记录 Android Bionic 路径展开、host ID、静态 Boost、pthread 链接和无版本 SONAME 适配。`patch_uhd.py` 实施同样的可重复补丁。

`uhd-images-manifest.txt` 是本次构建使用的官方镜像清单；下载时按其中的 SHA-256 校验目标镜像归档。

上游源码和工具链由构建脚本下载到忽略目录。GPL 许可证全文、UHD 原始许可说明、libusb、Boost 及 NDK LLVM 的许可说明随仓库保留。OnAir 是独立客户端，本项目不包含或修改其代码。
