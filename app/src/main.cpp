#include <windows.h>

#include "MainWindow.h"

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE /*prev*/, PWSTR /*cmd*/, int /*show*/) {
  SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_SYSTEM_AWARE);
  MainWindow window(instance);
  if (!window.create()) {
    MessageBoxW(nullptr, L"Could not create the main window.", L"ChromaInvert",
                MB_OK | MB_ICONERROR);
    return 1;
  }
  return window.run();
}
