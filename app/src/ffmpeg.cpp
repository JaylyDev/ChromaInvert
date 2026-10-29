#include "ffmpeg.h"

#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>

#include "job_runner.h"

#ifdef _WIN32
#define POPEN _popen
#define PCLOSE _pclose
#else
#define POPEN popen
#define PCLOSE pclose
#endif

namespace host {
namespace {

std::string lower_extension(const std::string& path) {
  size_t slash = path.find_last_of("/\\");
  size_t dot = path.find_last_of('.');
  if (dot == std::string::npos || (slash != std::string::npos && dot < slash)) {
    return "";
  }
  std::string ext = path.substr(dot);
  for (char& c : ext) {
    c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  }
  return ext;
}

std::string filter_escape(const std::string& path) {
  std::string out = "'";
  for (char c : path) {
    if (c == '\'') {
      out += "'\\''";
    } else {
      if (c == '\\' || c == ':') {
        out += '\\';
      }
      out += c;
    }
  }
  out += "'";
  return out;
}

int run_logged(const std::string& cmd) {
  std::printf("run: %s\n", cmd.c_str());
  std::fflush(stdout);
  return std::system(shell_command(cmd).c_str());
}

}  // namespace

bool is_video_path(const std::string& path) {
  std::string ext = lower_extension(path);
  return ext == ".mov" || ext == ".mp4" || ext == ".m4v" || ext == ".mkv" || ext == ".avi" ||
         ext == ".webm";
}

bool probe_duration(const std::string& ffprobe, const std::string& video, double& seconds) {
  std::string cmd = quote_arg(ffprobe) + " -v error -show_entries format=duration" +
                    " -of default=noprint_wrappers=1:nokey=1 " + quote_arg(video);
#ifdef _WIN32
  cmd += " 2>NUL";
#else
  cmd += " 2>/dev/null";
#endif
  FILE* pipe = POPEN(shell_command(cmd).c_str(), "r");
  if (pipe == nullptr) {
    return false;
  }
  char buffer[64] = {0};
  size_t count = std::fread(buffer, 1, sizeof(buffer) - 1, pipe);
  int status = PCLOSE(pipe);
  if (status != 0 || count == 0) {
    return false;
  }
  char* end = nullptr;
  double parsed = std::strtod(buffer, &end);
  if (end == buffer || !std::isfinite(parsed) || parsed <= 0.0) {
    return false;
  }
  while (*end != '\0' && std::isspace(static_cast<unsigned char>(*end))) {
    ++end;
  }
  if (*end != '\0') {
    return false;
  }
  seconds = parsed;
  return true;
}

int extract_frame(const std::string& ffmpeg, const std::string& video, double at_seconds, const std::string& out_png) {
  char seek[32];
  std::snprintf(seek, sizeof(seek), "%.3f", at_seconds);
  std::error_code stale_error;
  std::filesystem::remove(out_png, stale_error);
  std::string cmd = quote_arg(ffmpeg) + " -y -loglevel error -ss " + seek + " -i " + quote_arg(video) +
                    " -frames:v 1 " + quote_arg(out_png);
  int status = run_logged(cmd);
  if (status != 0) {
    return status;
  }
  std::error_code check_error;
  bool produced =
      std::filesystem::is_regular_file(out_png, check_error) && !check_error &&
      std::filesystem::file_size(out_png, check_error) > 0 && !check_error;
  if (!produced) {
    std::fprintf(stderr, "error: ffmpeg wrote no frame to %s\n", out_png.c_str());
    return 1;
  }
  return 0;
}

int apply_lut(const std::string& ffmpeg, const std::string& input, const std::string& cube, const std::string& output) {
  if (cube.find('\'') != std::string::npos) {
    std::fprintf(stderr, "error: cube path must not contain a single quote (ffmpeg lut3d cannot parse it)\n");
    return 1;
  }
  std::string cmd = quote_arg(ffmpeg) + " -y -loglevel error -i " + quote_arg(input) + " -vf \"lut3d=file=" +
                    filter_escape(cube) + "\"";
  std::string ext = lower_extension(output);
  if (ext == ".mp4" || ext == ".m4v") {
    cmd += " -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709";
  } else if (ext == ".png" || ext == ".jpg" || ext == ".jpeg" || ext == ".tif" || ext == ".tiff" ||
             ext == ".bmp") {
    cmd += " -frames:v 1";
  }
  cmd += " " + quote_arg(output);
  return run_logged(cmd);
}

}  // namespace host
