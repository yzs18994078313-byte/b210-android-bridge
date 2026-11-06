from pathlib import Path

root = Path(__file__).resolve().parent / 'src' / 'uhd-git'
changes = {
 'host/lib/utils/pathslib.cpp': [
  ('#ifdef BOOST_MSVC\n#    include <windows.h>', '#if defined(__ANDROID__)\n#    include <cstdlib>\n#    include <cctype>\n#elif defined(BOOST_MSVC)\n#    include <windows.h>'),
  ('#ifdef BOOST_MSVC\n    constexpr size_t max_pathlen', '''#if defined(__ANDROID__)
    // Bionic has no wordexp(). Expand variables and ~/ without invoking a shell.
    std::string expanded;
    size_t pos = 0;
    if (path[0] == '~' && (path.size() == 1 || path[1] == '/')) {
        const char* home = std::getenv("HOME");
        expanded = home ? home : "~";
        pos = 1;
    }
    while (pos < path.size()) {
        if (path[pos] != '$') { expanded += path[pos++]; continue; }
        const size_t dollar = pos++;
        const bool braced = pos < path.size() && path[pos] == '{';
        if (braced) ++pos;
        const size_t begin = pos;
        while (pos < path.size() && (std::isalnum(static_cast<unsigned char>(path[pos])) || path[pos] == '_')) ++pos;
        if (pos == begin || (braced && (pos == path.size() || path[pos] != '}'))) {
            expanded += path[dollar]; pos = dollar + 1; continue;
        }
        const std::string key = path.substr(begin, pos - begin);
        if (braced) ++pos;
        if (const char* value = std::getenv(key.c_str())) expanded += value;
    }
    return expanded;
#elif defined(BOOST_MSVC)
    constexpr size_t max_pathlen'''),
 ],
 'host/lib/utils/platform.cpp': [
  ('#else\n    return uint32_t(gethostid());', '''#elif defined(__ANDROID__)
    // gethostid() is not part of Bionic. This ID is used with the process ID.
    char hostname[256] = {};
    if (gethostname(hostname, sizeof(hostname) - 1) == 0)
        return uint32_t(boost::hash<std::string>()(std::string(hostname)));
    return 0;
#else
    return uint32_t(gethostid());'''),
 ],
 'host/cmake/Modules/UHDBoost.cmake': [
  ('set(Boost_USE_STATIC_LIBS ${ENABLE_STATIC_LIBS})', 'if(ANDROID)\n    set(Boost_USE_STATIC_LIBS ON)\nelse()\n    set(Boost_USE_STATIC_LIBS ${ENABLE_STATIC_LIBS})\nendif()'),
  ('if(ENABLE_STATIC_LIBS)\n    set(BUILD_SHARED_LIBS FALSE)', 'if(ENABLE_STATIC_LIBS OR ANDROID)\n    set(BUILD_SHARED_LIBS FALSE)'),
 ],
 'host/lib/CMakeLists.txt': [
  ('target_link_libraries(uhd ${Boost_LIBRARIES} ${libuhd_libs})', 'if(ANDROID)\n    # Bionic provides pthread functions in libc; there is no separate libpthread.\n    list(REMOVE_ITEM libuhd_libs pthread)\nendif()\ntarget_link_libraries(uhd ${Boost_LIBRARIES} ${libuhd_libs})'),
  ('if(NOT LIBUHDDEV_PKG)\n    set_target_properties(uhd PROPERTIES SOVERSION', 'if(NOT LIBUHDDEV_PKG AND NOT ANDROID)\n    set_target_properties(uhd PROPERTIES SOVERSION'),
  ('endif(NOT LIBUHDDEV_PKG)', 'endif()'),
 ],
}
for name, replacements in changes.items():
    path = root / name
    text = path.read_text(encoding='utf-8')
    for old, new in replacements:
        if new in text:
            continue
        if text.count(old) != 1:
            raise RuntimeError(f'Expected one match in {name}: {old}')
        text = text.replace(old, new)
    path.write_text(text, encoding='utf-8', newline='\n')
    print('Patched ' + name)
