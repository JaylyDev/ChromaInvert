cmake_minimum_required(VERSION 3.16)
project(chromainvert-host VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(chromainvert-host
  src/main.cpp
  src/job_runner.cpp
  src/ffmpeg.cpp
)
target_include_directories(chromainvert-host PRIVATE src)

if(MSVC)
  target_compile_options(chromainvert-host PRIVATE /W4)
else()
  target_compile_options(chromainvert-host PRIVATE -Wall -Wextra)
endif()
