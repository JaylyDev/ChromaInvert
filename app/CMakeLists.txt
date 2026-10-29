cmake_minimum_required(VERSION 3.16)
project(ChromaInvertApp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Level 1 MVP: no linked libav. FFmpeg must be installed and available on PATH.
# Level 2 (libav) can be added later via vcpkg with find_package(FFmpeg) and linking
# libavformat / libavcodec / libswscale / libavutil.

find_program(FFMPEG_EXECUTABLE ffmpeg)
find_program(FFPROBE_EXECUTABLE ffprobe)
if(NOT FFMPEG_EXECUTABLE)
    message(WARNING "ffmpeg not found on PATH; install FFmpeg before running")
endif()
if(NOT FFPROBE_EXECUTABLE)
    message(WARNING "ffprobe not found on PATH; install FFmpeg before running")
endif()

add_executable(chromainvert_app
    src/main.cpp
    src/Ffmpeg.cpp
    src/JobRunner.cpp
    src/Preview.cpp
)

target_include_directories(chromainvert_app PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)

# Install note: ensure ffmpeg and ffprobe are on PATH for Level 1.
# On Windows use "winget install Gyan.FFmpeg" or download a static build.