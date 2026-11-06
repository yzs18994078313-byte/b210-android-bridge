$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot.Replace('\', '/')
$taskCmake = "$taskRoot/tools/py/cmake/data/bin/cmake.exe"
$taskNinja = "$taskRoot/tools/py/bin/ninja.exe"
if (-not (Test-Path -LiteralPath $taskNinja)) { $taskNinja = "$taskRoot/tools/py/ninja/data/bin/ninja.exe" }
$taskNdk = if ($env:ANDROID_NDK_HOME) { $env:ANDROID_NDK_HOME.Replace('\', '/') } else { "$taskRoot/tools/android-ndk-r28c" }
$env:PYTHONPATH = "$taskRoot/tools/py"
$taskPython = (Get-Command python.exe).Source
$taskBoostIncludes = Get-ChildItem "$taskRoot/src/boost-1.85.0/libs" -Directory | ForEach-Object {
  $taskInclude = ($_.FullName + '/include').Replace('\', '/')
  if (Test-Path -LiteralPath $taskInclude) { '-I"' + $taskInclude + '"' }
}
[System.IO.File]::WriteAllLines("$taskRoot/build/boost-includes.rsp", [string[]]$taskBoostIncludes)
$taskArgs = @(
  '-S', "$taskRoot/src/uhd-git/host", '-B', "$taskRoot/build/uhd", '-G', 'Ninja',
  "-DCMAKE_MAKE_PROGRAM=$taskNinja",
  "-DCMAKE_TOOLCHAIN_FILE=$taskNdk/build/cmake/android.toolchain.cmake",
  '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-26', '-DANDROID_STL=c++_shared',
  '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
  "-DCMAKE_CXX_FLAGS=@$taskRoot/build/boost-includes.rsp",
  '-U', 'HAVE_CXX_BOOST_ATOMICS_WITHOUT_LIB', '-U', 'HAVE_CXX_BOOST_ATOMICS_WITH_LIB',
  '-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,max-page-size=16384',
  '-DCMAKE_EXE_LINKER_FLAGS=-Wl,-z,max-page-size=16384',
  "-DCMAKE_INSTALL_PREFIX=$taskRoot/prefix", "-DCMAKE_PREFIX_PATH=$taskRoot/prefix",
  "-DCMAKE_FIND_ROOT_PATH=$taskRoot/prefix",
  "-DBoost_DIR=$taskRoot/prefix/lib/cmake/Boost-1.85.0",
  "-DBOOST_ROOT=$taskRoot/prefix", "-DPYTHON_EXECUTABLE=$taskPython",
  "-DRUNTIME_PYTHON_EXECUTABLE=$taskPython",
  "-DLIBUSB_LIBRARIES=$taskRoot/prefix/lib/libusb1.0.so",
  "-DLIBUSB_INCLUDE_DIRS=$taskRoot/prefix/include/libusb-1.0",
  '-DUHD_IMAGES_DIR=/data/local/uhd/share/uhd/images',
  '-DENABLE_C_API=ON', '-DENABLE_USB=ON', '-DENABLE_B200=ON',
  '-DENABLE_STATIC_LIBS=OFF', '-DENABLE_EXAMPLES=ON', '-DENABLE_UTILS=ON',
  '-DENABLE_PYTHON_API=OFF', '-DENABLE_PYMOD_UTILS=OFF', '-DENABLE_TESTS=OFF',
  '-DENABLE_MANUAL=OFF', '-DENABLE_DOXYGEN=OFF', '-DENABLE_DPDK=OFF',
  '-DENABLE_B100=OFF', '-DENABLE_USRP1=OFF', '-DENABLE_USRP2=OFF',
  '-DENABLE_X300=OFF', '-DENABLE_MPMD=OFF', '-DENABLE_N300=OFF',
  '-DENABLE_N320=OFF', '-DENABLE_E300=OFF', '-DENABLE_E320=OFF',
  '-DENABLE_X400=OFF', '-DENABLE_N230=OFF', '-DENABLE_OCTOCLOCK=OFF'
)
& $taskCmake @taskArgs *> "$taskRoot/build/uhd-configure.log"
$taskExit = $LASTEXITCODE
Get-Content "$taskRoot/build/uhd-configure.log" -Tail 75
if ($taskExit -ne 0) { throw "UHD configure failed: $taskExit" }
& $taskCmake --build "$taskRoot/build/uhd" --parallel 8 --target uhd uhd_find_devices uhd_usrp_probe rx_samples_to_file *> "$taskRoot/build/uhd-build.log"
$taskExit = $LASTEXITCODE
Get-Content "$taskRoot/build/uhd-build.log" -Tail 65
if ($taskExit -ne 0) { throw "UHD build failed: $taskExit" }
