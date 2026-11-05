// Legacy fallback host: the product path is the Electron GUI in app/gui with
// chromainvert-host as its FFmpeg sidecar. This Win32 host still builds but gets no new UI.
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
