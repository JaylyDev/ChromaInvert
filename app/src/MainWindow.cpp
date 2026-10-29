#include "MainWindow.h"

#include <commctrl.h>
#include <commdlg.h>

namespace {

const wchar_t* kWindowClass = L"ChromaInvertMain";
const wchar_t* kImageFilter =
    L"Image files (*.png;*.tif;*.tiff;*.bmp;*.jpg)\0"
    L"*.png;*.tif;*.tiff;*.bmp;*.jpg\0"
    L"All files (*.*)\0*.*\0";
const wchar_t* kCubeFilter = L"LUT files (*.cube)\0*.cube\0All files (*.*)\0*.*\0";

enum ControlId : int {
  IDC_SOURCE_EDIT = 101,
  IDC_BROWSE_SOURCE = 102,
  IDC_REFERENCE_EDIT = 103,
  IDC_BROWSE_REFERENCE = 104,
  IDC_OUTPUT_EDIT = 105,
  IDC_BROWSE_OUTPUT = 106,
  IDC_STRENGTH_EDIT = 107,
  IDC_LUT_COMBO = 108,
  IDC_DEVICE_COMBO = 109,
  IDC_MATCH_BUTTON = 110,
  IDC_CANCEL_BUTTON = 111
};

std::wstring getEditText(HWND edit) {
  int length = GetWindowTextLengthW(edit);
  std::wstring text(static_cast<size_t>(length + 1), L'\0');
  GetWindowTextW(edit, text.data(), length + 1);
  text.resize(static_cast<size_t>(length));
  return text;
}

HWND createChild(const wchar_t* className, const wchar_t* text, DWORD style,
                 HWND parent, int id, int x, int y, int width, int height) {
  return CreateWindowExW(0, className, text, style | WS_CHILD | WS_VISIBLE, x, y,
                         width, height, parent, reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
                         GetModuleHandleW(nullptr), nullptr);
}

bool pickOpenFile(HWND owner, const wchar_t* filter, std::wstring& selected) {
  wchar_t path[4096] = {0};
  OPENFILENAMEW dialog = {0};
  dialog.lStructSize = sizeof(dialog);
  dialog.hwndOwner = owner;
  dialog.lpstrFilter = filter;
  dialog.lpstrFile = path;
  dialog.nMaxFile = sizeof(path) / sizeof(path[0]);
  dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST;
  if (!GetOpenFileNameW(&dialog)) {
    return false;
  }
  selected = path;
  return true;
}

bool pickSaveFile(HWND owner, const wchar_t* filter, const wchar_t* defExt,
                  std::wstring& selected) {
  wchar_t path[4096] = {0};
  OPENFILENAMEW dialog = {0};
  dialog.lStructSize = sizeof(dialog);
  dialog.hwndOwner = owner;
  dialog.lpstrFilter = filter;
  dialog.lpstrDefExt = defExt;
  dialog.lpstrFile = path;
  dialog.nMaxFile = sizeof(path) / sizeof(path[0]);
  dialog.Flags = OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST;
  if (!GetSaveFileNameW(&dialog)) {
    return false;
  }
  selected = path;
  return true;
}

}  // namespace

MainWindow::MainWindow(HINSTANCE instance) : instance_(instance) {}

MainWindow::~MainWindow() {
  if (font_ != nullptr) {
    DeleteObject(font_);
  }
}

bool MainWindow::create() {
  INITCOMMONCONTROLSEX controls = {sizeof(controls), ICC_PROGRESS_CLASS};
  InitCommonControlsEx(&controls);

  NONCLIENTMETRICSW metrics = {sizeof(metrics)};
  if (SystemParametersInfoW(SPI_GETNONCLIENTMETRICS, sizeof(metrics), &metrics, 0)) {
    font_ = CreateFontIndirectW(&metrics.lfMessageFont);
  }

  WNDCLASSEXW cls = {sizeof(cls)};
  cls.lpfnWndProc = &MainWindow::windowProc;
  cls.hInstance = instance_;
  cls.hCursor = LoadCursorW(nullptr, IDC_ARROW);
  cls.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
  cls.lpszClassName = kWindowClass;
  if (!RegisterClassExW(&cls)) {
    return false;
  }

  hwnd_ = CreateWindowExW(0, kWindowClass, L"ChromaInvert", WS_OVERLAPPED | WS_CAPTION |
                          WS_SYSMENU | WS_MINIMIZEBOX, CW_USEDEFAULT, CW_USEDEFAULT,
                          660, 560, nullptr, nullptr, instance_, this);
  if (hwnd_ == nullptr) {
    return false;
  }

  createChild(L"STATIC", L"Source frame:", SS_LEFT, hwnd_, 0, 12, 12, 110, 24);
  sourceEdit_ = createChild(L"EDIT", L"", ES_LEFT | ES_AUTOHSCROLL | WS_BORDER,
                            hwnd_, IDC_SOURCE_EDIT, 124, 12, 380, 24);
  createChild(L"BUTTON", L"Browse...", BS_PUSHBUTTON, hwnd_, IDC_BROWSE_SOURCE,
              512, 12, 120, 24);

  createChild(L"STATIC", L"Reference frame:", SS_LEFT, hwnd_, 0, 12, 46, 110, 24);
  referenceEdit_ = createChild(L"EDIT", L"", ES_LEFT | ES_AUTOHSCROLL | WS_BORDER,
                               hwnd_, IDC_REFERENCE_EDIT, 124, 46, 380, 24);
  createChild(L"BUTTON", L"Browse...", BS_PUSHBUTTON, hwnd_, IDC_BROWSE_REFERENCE,
              512, 46, 120, 24);

  createChild(L"STATIC", L"Output .cube:", SS_LEFT, hwnd_, 0, 12, 80, 110, 24);
  outputEdit_ = createChild(L"EDIT", L"", ES_LEFT | ES_AUTOHSCROLL | WS_BORDER,
                            hwnd_, IDC_OUTPUT_EDIT, 124, 80, 380, 24);
  createChild(L"BUTTON", L"Browse...", BS_PUSHBUTTON, hwnd_, IDC_BROWSE_OUTPUT,
              512, 80, 120, 24);

  createChild(L"STATIC", L"Strength:", SS_LEFT, hwnd_, 0, 12, 114, 70, 24);
  strengthEdit_ = createChild(L"EDIT", L"1.0", ES_LEFT | ES_AUTOHSCROLL | WS_BORDER,
                              hwnd_, IDC_STRENGTH_EDIT, 86, 114, 80, 24);
  createChild(L"STATIC", L"LUT size:", SS_LEFT, hwnd_, 0, 176, 114, 64, 24);
  lutCombo_ = createChild(L"COMBOBOX", L"", CBS_DROPDOWNLIST | WS_VSCROLL,
                          hwnd_, IDC_LUT_COMBO, 244, 114, 70, 100);
  SendMessageW(lutCombo_, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"17"));
  SendMessageW(lutCombo_, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"33"));
  SendMessageW(lutCombo_, CB_SETCURSEL, 1, 0);
  createChild(L"STATIC", L"Device:", SS_LEFT, hwnd_, 0, 324, 114, 60, 24);
  deviceCombo_ = createChild(L"COMBOBOX", L"", CBS_DROPDOWNLIST | WS_VSCROLL,
                             hwnd_, IDC_DEVICE_COMBO, 388, 114, 100, 100);
  SendMessageW(deviceCombo_, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"auto"));
  SendMessageW(deviceCombo_, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"cuda"));
  SendMessageW(deviceCombo_, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"cpu"));
  SendMessageW(deviceCombo_, CB_SETCURSEL, 0, 0);

  matchButton_ = createChild(L"BUTTON", L"Match", BS_PUSHBUTTON, hwnd_,
                             IDC_MATCH_BUTTON, 12, 148, 120, 30);
  cancelButton_ = createChild(L"BUTTON", L"Cancel", BS_PUSHBUTTON | WS_DISABLED,
                              hwnd_, IDC_CANCEL_BUTTON, 140, 148, 120, 30);
  statusLabel_ = createChild(L"STATIC", L"Idle.", SS_LEFT, hwnd_, 0, 272, 152,
                             360, 24);

  progress_ = createChild(PROGRESS_CLASSW, L"", PBS_SMOOTH, hwnd_, 0, 12, 190,
                          620, 24);
  SendMessageW(progress_, PBM_SETRANGE, 0, MAKELPARAM(0, 100));

  createChild(L"STATIC", L"Log:", SS_LEFT, hwnd_, 0, 12, 222, 110, 24);
  logEdit_ = createChild(L"EDIT", L"", ES_LEFT | ES_MULTILINE | ES_AUTOVSCROLL |
                          ES_READONLY | WS_BORDER | WS_VSCROLL, hwnd_, 0, 12, 248,
                          620, 252);

  EnumChildWindows(hwnd_, [](HWND child, LPARAM font) -> BOOL {
    SendMessageW(child, WM_SETFONT, static_cast<WPARAM>(font), TRUE);
    return TRUE;
  }, reinterpret_cast<LPARAM>(font_));

  ShowWindow(hwnd_, SW_SHOW);
  UpdateWindow(hwnd_);
  return true;
}

int MainWindow::run() {
  MSG message = {0};
  while (GetMessageW(&message, nullptr, 0, 0)) {
    TranslateMessage(&message);
    DispatchMessageW(&message);
  }
  return static_cast<int>(message.wParam);
}

HWND MainWindow::handle() const {
  return hwnd_;
}

LRESULT CALLBACK MainWindow::windowProc(HWND hwnd, UINT message, WPARAM wParam,
                                        LPARAM lParam) {
  MainWindow* self = nullptr;
  if (message == WM_NCCREATE) {
    CREATESTRUCTW* created = reinterpret_cast<CREATESTRUCTW*>(lParam);
    self = static_cast<MainWindow*>(created->lpCreateParams);
    SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(self));
  } else {
    self = reinterpret_cast<MainWindow*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
  }
  if (self == nullptr) {
    return DefWindowProcW(hwnd, message, wParam, lParam);
  }
  return self->onMessage(message, wParam, lParam);
}

LRESULT MainWindow::onMessage(UINT message, WPARAM wParam, LPARAM lParam) {
  switch (message) {
    case WM_COMMAND: {
      int id = LOWORD(wParam);
      if (id == IDC_BROWSE_SOURCE) {
        onBrowseSource();
      } else if (id == IDC_BROWSE_REFERENCE) {
        onBrowseReference();
      } else if (id == IDC_BROWSE_OUTPUT) {
        onBrowseOutput();
      } else if (id == IDC_MATCH_BUTTON) {
        onMatch();
      } else if (id == IDC_CANCEL_BUTTON) {
        onCancel();
      }
      return 0;
    }
    case WM_JOB_PROGRESS:
      onJobProgress(static_cast<int>(wParam), static_cast<int>(lParam));
      return 0;
    case WM_JOB_LOG:
      onJobLog(reinterpret_cast<wchar_t*>(lParam));
      return 0;
    case WM_JOB_DONE:
      onJobDone(static_cast<int>(wParam), reinterpret_cast<wchar_t*>(lParam));
      return 0;
    case WM_CLOSE:
      runner_.cancel();
      DestroyWindow(hwnd_);
      return 0;
    case WM_DESTROY:
      PostQuitMessage(0);
      return 0;
    default:
      return DefWindowProcW(hwnd_, message, wParam, lParam);
  }
}

void MainWindow::onBrowseSource() {
  std::wstring selected;
  if (pickOpenFile(hwnd_, kImageFilter, selected)) {
    SetWindowTextW(sourceEdit_, selected.c_str());
  }
}

void MainWindow::onBrowseReference() {
  std::wstring selected;
  if (pickOpenFile(hwnd_, kImageFilter, selected)) {
    SetWindowTextW(referenceEdit_, selected.c_str());
  }
}

void MainWindow::onBrowseOutput() {
  std::wstring selected;
  if (pickSaveFile(hwnd_, kCubeFilter, L"cube", selected)) {
    SetWindowTextW(outputEdit_, selected.c_str());
  }
}

bool MainWindow::collectConfig(JobConfig& config) {
  config.sourceFile = getEditText(sourceEdit_);
  config.referenceFile = getEditText(referenceEdit_);
  config.outputCube = getEditText(outputEdit_);
  if (config.sourceFile.empty() || config.referenceFile.empty() ||
      config.outputCube.empty()) {
    MessageBoxW(hwnd_, L"Pick a source frame, a reference frame, and an output .cube path.",
                L"ChromaInvert", MB_OK | MB_ICONWARNING);
    return false;
  }
  if (GetFileAttributesW(config.sourceFile.c_str()) == INVALID_FILE_ATTRIBUTES ||
      GetFileAttributesW(config.referenceFile.c_str()) == INVALID_FILE_ATTRIBUTES) {
    MessageBoxW(hwnd_, L"Source or reference file does not exist.", L"ChromaInvert",
                MB_OK | MB_ICONWARNING);
    return false;
  }
  wchar_t* end = nullptr;
  double strength = wcstod(getEditText(strengthEdit_).c_str(), &end);
  if (end == nullptr || *end != L'\0' || strength < 0.0) {
    MessageBoxW(hwnd_, L"Strength must be a number at or above 0.", L"ChromaInvert",
                MB_OK | MB_ICONWARNING);
    return false;
  }
  config.strength = strength;
  int lutIndex = static_cast<int>(SendMessageW(lutCombo_, CB_GETCURSEL, 0, 0));
  config.lutSize = (lutIndex == 0) ? 17 : 33;
  int deviceIndex = static_cast<int>(SendMessageW(deviceCombo_, CB_GETCURSEL, 0, 0));
  if (deviceIndex == 1) {
    config.device = L"cuda";
  } else if (deviceIndex == 2) {
    config.device = L"cpu";
  } else {
    config.device = L"auto";
  }
  return true;
}

void MainWindow::onMatch() {
  JobConfig config;
  if (!collectConfig(config)) {
    return;
  }
  if (!runner_.start(config, hwnd_)) {
    MessageBoxW(hwnd_, runner_.lastError().c_str(), L"ChromaInvert",
                MB_OK | MB_ICONERROR);
    return;
  }
  enableInputs(false);
  SendMessageW(progress_, PBM_SETPOS, 0, 0);
  setStatus(L"Running: writing job.json and starting the engine.");
  appendLog(L"Source: " + config.sourceFile);
  appendLog(L"Reference: " + config.referenceFile);
  appendLog(L"Output: " + config.outputCube);
}

void MainWindow::onCancel() {
  runner_.cancel();
  setStatus(L"Cancelling.");
}

void MainWindow::onJobProgress(int percent, int lossMilli) {
  SendMessageW(progress_, PBM_SETPOS, static_cast<WPARAM>(percent), 0);
  wchar_t text[128] = {0};
  swprintf(text, sizeof(text) / sizeof(text[0]), L"Optimizing: %d%% (loss %.3f)",
           percent, static_cast<double>(lossMilli) / 1000.0);
  setStatus(text);
}

void MainWindow::onJobLog(wchar_t* text) {
  if (text != nullptr) {
    appendLog(text);
    free(text);
  }
}

void MainWindow::onJobDone(int exitCode, wchar_t* summary) {
  if (summary != nullptr) {
    appendLog(summary);
    setStatus(summary);
    free(summary);
  }
  if (exitCode == 0) {
    SendMessageW(progress_, PBM_SETPOS, 100, 0);
  }
  enableInputs(true);
}

void MainWindow::appendLog(const std::wstring& text) {
  if (GetWindowTextLengthW(logEdit_) > 60000) {
    SetWindowTextW(logEdit_, L"");
  }
  SendMessageW(logEdit_, EM_SETSEL, static_cast<WPARAM>(-1), static_cast<LPARAM>(-1));
  std::wstring line = text + L"\r\n";
  SendMessageW(logEdit_, EM_REPLACESEL, FALSE, reinterpret_cast<LPARAM>(line.c_str()));
}

void MainWindow::setStatus(const std::wstring& text) {
  SetWindowTextW(statusLabel_, text.c_str());
}

void MainWindow::enableInputs(bool enabled) {
  BOOL flag = enabled ? TRUE : FALSE;
  EnableWindow(sourceEdit_, flag);
  EnableWindow(referenceEdit_, flag);
  EnableWindow(outputEdit_, flag);
  EnableWindow(strengthEdit_, flag);
  EnableWindow(lutCombo_, flag);
  EnableWindow(deviceCombo_, flag);
  EnableWindow(matchButton_, flag);
  EnableWindow(cancelButton_, !flag);
}
