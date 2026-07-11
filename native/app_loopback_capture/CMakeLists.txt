cmake_minimum_required(VERSION 3.20)
project(app_loopback_capture LANGUAGES CXX)

if(MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

add_executable(app_loopback_capture main.cpp)
set_target_properties(app_loopback_capture PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON)
target_link_libraries(app_loopback_capture PRIVATE ole32 mmdevapi uuid)

install(TARGETS app_loopback_capture RUNTIME DESTINATION ${CMAKE_SOURCE_DIR}/../../bin)
