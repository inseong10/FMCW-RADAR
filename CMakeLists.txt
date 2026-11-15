cmake_minimum_required(VERSION 3.16)
project(FMCW_RADAR LANGUAGES NONE)

if(NOT UNIX)
    message(FATAL_ERROR "The C++ receiver requires Linux/macOS (WSL on Windows). Use receiver_numpy.py for native Windows.")
endif()
enable_language(CXX)

add_executable(udp_radar_receiver src/PS/receiver/udp_radar_receiver.cpp)
target_compile_features(udp_radar_receiver PRIVATE cxx_std_17)
target_compile_options(udp_radar_receiver PRIVATE -Wall -Wextra)
target_link_libraries(udp_radar_receiver PRIVATE ${CMAKE_DL_LIBS})
set_target_properties(udp_radar_receiver PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}")

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    enable_language(C)
    add_executable(fft128_receiver
        src/PS/fft128/native_receiver.c
        src/PS/fft128/native_core.c
        src/PS/fft128/mmio.c)
    target_compile_features(fft128_receiver PRIVATE c_std_11)
    target_compile_options(fft128_receiver PRIVATE -Wall -Wextra)
    target_link_libraries(fft128_receiver PRIVATE m)
    set_target_properties(fft128_receiver PROPERTIES
        OUTPUT_NAME "fft128-receiver"
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
endif()
