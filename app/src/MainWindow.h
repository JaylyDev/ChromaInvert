#pragma once

#include <windows.h>

#include <string>

#include "JobRunner.h"

class MainWindow {
public:
  explicit MainWindow(HINSTANCE instance);
  ~MainWindow();

  MainWindow(const MainWindow&) = delete;
  MainWindow& operator=(const MainWindow&) = delete;

  bool create();
  int run();
  HWND handle() const;

private:
  static LRESULT CALLBACK windowProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam);
  LRESULT onMessage(UINT message, WPARAM wParam, LPARAM lParam);
  void onBrowseSource();
  void onBrowseReference();
  void onBrowseOutput();
  void onMatch();
  void onCancel();
  void onJobProgress(int percent, int lossMilli);
  void onJobLog(wchar_t* text);
  void onJobDone(int exitCode, wchar_t* summary);
  void appendLog(const std::wstring& text);
  void setStatus(const std::wstring& text);
  bool collectConfig(JobConfig& config);
  void enableInputs(bool enabled);

  HINSTANCE instance_ = nullptr;
  HWND hwnd_ = nullptr;
  HFONT font_ = nullptr;
  HWND sourceEdit_ = nullptr;
  HWND referenceEdit_ = nullptr;
  HWND outputEdit_ = nullptr;
  HWND strengthEdit_ = nullptr;
  HWND lutCombo_ = nullptr;
  HWND deviceCombo_ = nullptr;
  HWND matchButton_ = nullptr;
  HWND cancelButton_ = nullptr;
  HWND progress_ = nullptr;
  HWND statusLabel_ = nullptr;
  HWND logEdit_ = nullptr;
  JobRunner runner_;
};
