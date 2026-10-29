cmake_minimum_required(VERSION 3.20)

project(ChromaInvertApp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(ChromaInvert WIN32
  src/main.cpp
  src/MainWindow.cpp
  src/JobRunner.cpp
  src/MainWindow.h
  src/JobRunner.h
)

target_include_directories(ChromaInvert PRIVATE src)

target_compile_definitions(ChromaInvert PRIVATE
  UNICODE
  _UNICODE
  WIN32_LEAN_AND_MEAN
  NOMINMAX
  WINVER=0x0A00
  _WIN32_WINNT=0x0A00
)

if(MSVC)
  target_compile_options(ChromaInvert PRIVATE /W4)
else()
  target_compile_options(ChromaInvert PRIVATE -Wall -Wextra)
endif()

if(MINGW)
  target_link_options(ChromaInvert PRIVATE -municode)
endif()

target_link_libraries(ChromaInvert PRIVATE comctl32 gdi32)

add_executable(chromainvert-host
  src/host_main.cpp
  src/job_runner.cpp
  src/ffmpeg.cpp
)

target_include_directories(chromainvert-host PRIVATE src)

if(MSVC)
  target_compile_options(chromainvert-host PRIVATE /W4)
else()
  target_compile_options(chromainvert-host PRIVATE -Wall -Wextra)
endif()
