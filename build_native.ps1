$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot.Replace('\', '/')
$taskCmake = "$taskRoot/tools/py/cmake/data/bin/cmake.exe"
$taskNinja = "$taskRoot/tools/py/bin/ninja.exe"
if (-not (Test-Path -LiteralPath $taskNinja)) { $taskNinja = "$taskRoot/tools/py/ninja/data/bin/ninja.exe" }
$taskNdk = if ($env:ANDROID_NDK_HOME) { $env:ANDROID_NDK_HOME.Replace('\', '/') } else { "$taskRoot/tools/android-ndk-r28c" }
New-Item -ItemType Directory -Force -Path "$taskRoot/build", "$taskRoot/prefix" | Out-Null
function Invoke-TaskCmake {
    & $taskCmake @args
    if ($LASTEXITCODE -ne 0) { throw "CMake failed: $LASTEXITCODE" }
}
$taskCommon = @('-G', 'Ninja', "-DCMAKE_MAKE_PROGRAM=$taskNinja",
    "-DCMAKE_TOOLCHAIN_FILE=$taskNdk/build/cmake/android.toolchain.cmake",
    '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-26', '-DANDROID_STL=c++_shared',
    '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
    "-DCMAKE_INSTALL_PREFIX=$taskRoot/prefix")
& python.exe "$taskRoot/patch_uhd.py"
if ($LASTEXITCODE -ne 0) { throw 'UHD patch failed' }
Invoke-TaskCmake -S "$taskRoot/libusb-cmake" -B "$taskRoot/build/libusb" @taskCommon "-DLIBUSB_SRC=$taskRoot/src/libusb-1.0.27"
Invoke-TaskCmake --build "$taskRoot/build/libusb" --parallel 8
Invoke-TaskCmake --install "$taskRoot/build/libusb"
Invoke-TaskCmake -S "$taskRoot/src/boost-1.85.0" -B "$taskRoot/build/boost" @taskCommon '-DBUILD_SHARED_LIBS=OFF' '-DBOOST_ENABLE_MPI=OFF' '-DBOOST_ENABLE_PYTHON=OFF' '-DBOOST_INCLUDE_LIBRARIES=chrono;date_time;filesystem;program_options;serialization;system;thread;test'
Invoke-TaskCmake --build "$taskRoot/build/boost" --parallel 8
Invoke-TaskCmake --install "$taskRoot/build/boost"
& "$taskRoot/build_uhd.ps1"
Invoke-TaskCmake -S "$taskRoot/bridge" -B "$taskRoot/build/bridge" @taskCommon "-DUHD_SOURCE=$taskRoot/src/uhd-git/host" "-DUHD_BUILD=$taskRoot/build/uhd"
Invoke-TaskCmake --build "$taskRoot/build/bridge" --parallel 4 --target usrp_bridge queue_tests
