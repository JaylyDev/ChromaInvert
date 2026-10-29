#include "JobRunner.h"

#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <vector>

namespace {

std::string toUtf8(const std::wstring& wide) {
  if (wide.empty()) {
    return std::string();
  }
  int needed = WideCharToMultiByte(CP_UTF8, 0, wide.c_str(), -1, nullptr, 0, nullptr, nullptr);
  if (needed <= 1) {
    return std::string();
  }
  std::string out(static_cast<size_t>(needed - 1), '\0');
  WideCharToMultiByte(CP_UTF8, 0, wide.c_str(), -1, out.data(), needed, nullptr, nullptr);
  return out;
}

std::wstring toWide(const std::string& text) {
  if (text.empty()) {
    return std::wstring();
  }
  int needed = MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, nullptr, 0);
  if (needed <= 1) {
    return std::wstring();
  }
  std::wstring out(static_cast<size_t>(needed - 1), L'\0');
  MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, out.data(), needed);
  return out;
}

void appendJsonString(std::string& out, const std::string& text) {
  out.push_back('"');
  for (char c : text) {
    switch (c) {
      case '"': out += "\\\""; break;
      case '\\': out += "\\\\"; break;
      case '\n': out += "\\n"; break;
      case '\r': out += "\\r"; break;
      case '\t': out += "\\t"; break;
      default:
        if (c >= 0 && c < 0x20) {
          char escape[8] = {0};
          snprintf(escape, sizeof(escape), "\\u%04x", c);
          out += escape;
        } else {
          out.push_back(c);
        }
        break;
    }
  }
  out.push_back('"');
}

std::wstring parentDir(const std::wstring& path) {
  size_t pos = path.find_last_of(L"\\/");
  if (pos == std::wstring::npos) {
    return std::wstring();
  }
  return path.substr(0, pos);
}

const char* skipSpaces(const char* p) {
  while (*p == ' ' || *p == '\t') {
    ++p;
  }
  return p;
}

bool fieldValue(const std::string& line, const char* key, const char*& value) {
  std::string quoted = std::string("\"") + key + "\"";
  size_t pos = line.find(quoted);
  if (pos == std::string::npos) {
    return false;
  }
  const char* p = skipSpaces(line.c_str() + pos + quoted.size());
  if (*p != ':') {
    return false;
  }
  value = skipSpaces(p + 1);
  return true;
}

bool parseIntField(const std::string& line, const char* key, int& out) {
  const char* value = nullptr;
  if (!fieldValue(line, key, value)) {
    return false;
  }
  char* end = nullptr;
  long parsed = strtol(value, &end, 10);
  if (end == value) {
    return false;
  }
  out = static_cast<int>(parsed);
  return true;
}

bool parseDoubleField(const std::string& line, const char* key, double& out) {
  const char* value = nullptr;
  if (!fieldValue(line, key, value)) {
    return false;
  }
  char* end = nullptr;
  double parsed = strtod(value, &end);
  if (end == value) {
    return false;
  }
  out = parsed;
  return true;
}

bool parseStringField(const std::string& line, const char* key, std::string& out) {
  const char* value = nullptr;
  if (!fieldValue(line, key, value) || *value != '"') {
    return false;
  }
  out.clear();
  for (const char* p = value + 1; *p != '\0'; ++p) {
    if (*p == '\\' && *(p + 1) != '\0') {
      ++p;
      out.push_back(*p);
      continue;
    }
    if (*p == '"') {
      return true;
    }
    out.push_back(*p);
  }
  return false;
}

wchar_t* dupWide(const std::wstring& text) {
  size_t count = text.size() + 1;
  wchar_t* copy = static_cast<wchar_t*>(malloc(count * sizeof(wchar_t)));
  if (copy == nullptr) {
    return nullptr;
  }
  for (size_t i = 0; i < text.size(); ++i) {
    copy[i] = text[i];
  }
  copy[text.size()] = L'\0';
  return copy;
}

}  // namespace

JobRunner::JobRunner() = default;

JobRunner::~JobRunner() {
  cancel();
  if (thread_ != nullptr) {
    WaitForSingleObject(thread_, INFINITE);
    CloseHandle(thread_);
  }
  if (child_ != nullptr) {
    CloseHandle(child_);
  }
}

bool JobRunner::start(const JobConfig& config, HWND notify) {
  if (running_.exchange(true)) {
    lastError_ = L"A job is already running.";
    return false;
  }
  if (notify == nullptr) {
    running_ = false;
    lastError_ = L"Internal error: notify window is null.";
    return false;
  }
  cancelRequested_ = false;
  lastError_.clear();
  struct ThreadArgs {
    JobRunner* self;
    JobConfig config;
    HWND notify;
  };
  ThreadArgs* args = new ThreadArgs{this, config, notify};
  thread_ = CreateThread(nullptr, 0, &JobRunner::threadEntry, args, 0, nullptr);
  if (thread_ == nullptr) {
    delete args;
    running_ = false;
    lastError_ = L"Could not start the worker thread.";
    return false;
  }
  return true;
}

void JobRunner::cancel() {
  cancelRequested_ = true;
  if (child_ != nullptr) {
    TerminateProcess(child_, 1);
  }
}

bool JobRunner::running() const {
  return running_;
}

std::wstring JobRunner::lastError() const {
  return lastError_;
}

DWORD WINAPI JobRunner::threadEntry(LPVOID param) {
  struct ThreadArgs {
    JobRunner* self;
    JobConfig config;
    HWND notify;
  };
  ThreadArgs* args = static_cast<ThreadArgs*>(param);
  args->self->run(args->config, args->notify);
  delete args;
  return 0;
}

bool JobRunner::writeJobJson(const JobConfig& config, const std::wstring& jobPath,
                             const std::wstring& reportPath, std::wstring& error) {
  std::string json;
  json += "{\n";
  json += "  \"contract_version\": 1,\n";
  json += "  \"source_frames\": [";
  appendJsonString(json, toUtf8(config.sourceFile));
  json += "],\n";
  json += "  \"reference_frames\": [";
  appendJsonString(json, toUtf8(config.referenceFile));
  json += "],\n";
  json += "  \"input_profile\": \"rec709\",\n";
  char numbers[256] = {0};
  snprintf(numbers, sizeof(numbers),
           "  \"coarse_size\": %d,\n  \"lut_size\": %d,\n  \"iterations\": %d,\n"
           "  \"fine_iterations\": %d,\n  \"strength\": %.4f,\n  \"seed\": %d,\n",
           config.coarseSize, config.lutSize, config.iterations,
           config.fineIterations, config.strength, config.seed);
  json += numbers;
  json += "  \"device\": ";
  appendJsonString(json, toUtf8(config.device));
  json += ",\n";
  json += "  \"output_cube\": ";
  appendJsonString(json, toUtf8(config.outputCube));
  json += ",\n";
  json += "  \"report_json\": ";
  appendJsonString(json, toUtf8(reportPath));
  json += "\n}\n";

  std::string narrowPath = toUtf8(jobPath);
  std::ofstream out(narrowPath, std::ios::binary);
  if (!out.is_open()) {
    error = L"Could not write job file: " + jobPath;
    return false;
  }
  out << json;
  out.close();
  if (!out) {
    error = L"Could not write job file: " + jobPath;
    return false;
  }
  return true;
}

void JobRunner::run(const JobConfig& config, HWND notify) {
  std::wstring error;
  std::wstring dir = parentDir(config.outputCube);
  std::wstring jobPath = (dir.empty() ? std::wstring() : dir + L"\\") + L"job.json";
  std::wstring reportPath = (dir.empty() ? std::wstring() : dir + L"\\") + L"report.json";
  if (dir.empty()) {
    jobPath = L"job.json";
    reportPath = L"report.json";
  }

  bool launched = false;
  PROCESS_INFORMATION childInfo = {0};
  HANDLE readPipe = nullptr;

  if (writeJobJson(config, jobPath, reportPath, error)) {
    SECURITY_ATTRIBUTES security = {sizeof(security), nullptr, TRUE};
    HANDLE writePipe = nullptr;
    if (CreatePipe(&readPipe, &writePipe, &security, 0)) {
      SetHandleInformation(readPipe, HANDLE_FLAG_INHERIT, 0);
      STARTUPINFOW startup = {0};
      startup.cb = sizeof(startup);
      startup.dwFlags = STARTF_USESTDHANDLES;
      startup.hStdOutput = writePipe;
      startup.hStdError = writePipe;
      startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
      std::wstring command = L"python -m chromainvert run \"" + jobPath + L"\"";
      std::vector<wchar_t> commandLine(command.begin(), command.end());
      commandLine.push_back(L'\0');
      launched = CreateProcessW(nullptr, commandLine.data(), nullptr, nullptr, TRUE,
                                CREATE_NO_WINDOW, nullptr, nullptr, &startup, &childInfo) != 0;
      CloseHandle(writePipe);
      if (launched) {
        child_ = childInfo.hProcess;
        CloseHandle(childInfo.hThread);
      } else {
        error = L"Could not start the engine. Is Python on PATH with chromainvert installed?";
      }
    } else {
      error = L"Could not create the engine output pipe.";
    }
  }

  if (!launched) {
    if (readPipe != nullptr) {
      CloseHandle(readPipe);
    }
    wchar_t* summary = dupWide(error.empty() ? L"Job setup failed." : error);
    PostMessageW(notify, WM_JOB_DONE, static_cast<WPARAM>(1),
                 reinterpret_cast<LPARAM>(summary));
    running_ = false;
    return;
  }

  std::string pending;
  char chunk[4096] = {0};
  DWORD bytesRead = 0;
  BOOL pipeOpen = TRUE;
  bool gotDone = false;
  while (pipeOpen && !cancelRequested_) {
    pipeOpen = ReadFile(readPipe, chunk, sizeof(chunk) - 1, &bytesRead, nullptr);
    if (!pipeOpen || bytesRead == 0) {
      break;
    }
    chunk[bytesRead] = '\0';
    pending.append(chunk, bytesRead);
    size_t pos = 0;
    while ((pos = pending.find('\n')) != std::string::npos) {
      std::string line = pending.substr(0, pos);
      pending.erase(0, pos + 1);
      if (!line.empty() && line.back() == '\r') {
        line.pop_back();
      }
      if (line.find("\"progress\"") != std::string::npos) {
        int iter = 0;
        int iters = 0;
        double loss = 0.0;
        if (parseIntField(line, "iter", iter) && parseIntField(line, "iters", iters) &&
            iters > 0) {
          parseDoubleField(line, "loss", loss);
          int percent = static_cast<int>((static_cast<double>(iter) * 100.0) /
                                         static_cast<double>(iters));
          int lossMilli = static_cast<int>(loss * 1000.0);
          PostMessageW(notify, WM_JOB_PROGRESS, static_cast<WPARAM>(percent),
                       static_cast<LPARAM>(lossMilli));
        }
        continue;
      }
      if (line.find("\"done\"") != std::string::npos) {
        std::string cube;
        double seconds = 0.0;
        parseStringField(line, "cube", cube);
        parseDoubleField(line, "seconds", seconds);
        wchar_t text[512] = {0};
        swprintf(text, sizeof(text) / sizeof(text[0]),
                 L"Done in %.1f s: %ls", seconds, toWide(cube).c_str());
        wchar_t* summary = dupWide(text);
        PostMessageW(notify, WM_JOB_DONE, static_cast<WPARAM>(0),
                     reinterpret_cast<LPARAM>(summary));
        gotDone = true;
        continue;
      }
      if (line.size() > 4096) {
        line.resize(4096);
      }
      wchar_t* copy = dupWide(toWide(line));
      PostMessageW(notify, WM_JOB_LOG, 0, reinterpret_cast<LPARAM>(copy));
    }
  }
  CloseHandle(readPipe);

  DWORD exitCode = 1;
  if (!cancelRequested_) {
    WaitForSingleObject(child_, INFINITE);
    GetExitCodeProcess(child_, &exitCode);
  } else {
    exitCode = 1;
  }
  CloseHandle(child_);
  child_ = nullptr;

  if (cancelRequested_) {
    wchar_t* summary = dupWide(L"Cancelled.");
    PostMessageW(notify, WM_JOB_DONE, static_cast<WPARAM>(1),
                 reinterpret_cast<LPARAM>(summary));
  } else if (exitCode != 0 && !gotDone) {
    wchar_t text[256] = {0};
    swprintf(text, sizeof(text) / sizeof(text[0]),
             L"Engine failed with exit code %lu. See the log above.", exitCode);
    wchar_t* summary = dupWide(text);
    PostMessageW(notify, WM_JOB_DONE, static_cast<WPARAM>(1),
                 reinterpret_cast<LPARAM>(summary));
  }
  running_ = false;
}
