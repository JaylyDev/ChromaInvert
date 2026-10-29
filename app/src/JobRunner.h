#pragma once

#include <windows.h>

#include <atomic>
#include <string>

enum JobMessage : UINT {
  WM_JOB_PROGRESS = WM_APP + 100,
  WM_JOB_LOG = WM_APP + 101,
  WM_JOB_DONE = WM_APP + 102
};

struct JobConfig {
  std::wstring sourceFile;
  std::wstring referenceFile;
  std::wstring outputCube;
  int coarseSize = 17;
  int lutSize = 33;
  int iterations = 400;
  int fineIterations = 30;
  double strength = 1.0;
  int seed = 42;
  std::wstring device = L"auto";
};

class JobRunner {
 public:
  JobRunner();
  ~JobRunner();

  JobRunner(const JobRunner&) = delete;
  JobRunner& operator=(const JobRunner&) = delete;

  bool start(const JobConfig& config, HWND notify);
  void cancel();
  bool running() const;
  std::wstring lastError() const;

 private:
  struct ThreadArgs {
    JobRunner* self;
    JobConfig config;
    HWND notify;
  };

  static DWORD WINAPI threadEntry(LPVOID param);
  void run(const JobConfig& config, HWND notify);
  bool writeJobJson(const JobConfig& config, const std::wstring& jobPath,
                    const std::wstring& reportPath, std::wstring& error);

  HANDLE thread_ = nullptr;
  std::atomic<HANDLE> child_ = nullptr;
  std::atomic<bool> cancelRequested_ = false;
  std::atomic<bool> running_ = false;
  std::wstring lastError_;
};
