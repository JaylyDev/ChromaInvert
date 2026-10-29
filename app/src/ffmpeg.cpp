#include "ffmpeg.h"

#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <sstream>
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

namespace fs = std::filesystem;

namespace {
int runCaptureRc(const std::string& cmd, std::string& out) {
    out.clear();
    FILE* p = POPEN(cmd.c_str(), "r");
    if (!p) return -1;
    char buf[4096];
    while (fgets(buf, sizeof(buf), p)) out += buf;
    return PCLOSE(p);
}

std::string firstLine(const std::string& s) {
    size_t nl = s.find('\n');
    return (nl == std::string::npos) ? s : s.substr(0, nl);
}

std::string runCapture(const std::string& cmd) {
    std::string out;
    runCaptureRc(cmd, out);
    return out;
}

bool fileNonEmpty(const std::string& p) {
    std::error_code ec;
    return fs::exists(p, ec) && fs::is_regular_file(p, ec) && fs::file_size(p, ec) > 0;
}

bool hasUnsafePathChars(const std::string& s) {
    return s.find('%') != std::string::npos || s.find('"') != std::string::npos
        || s.find('\n') != std::string::npos || s.find('\r') != std::string::npos;
}

std::string escapeLut3dPath(const std::string& p) {
    std::string s;
    for (char c : p) {
        if (c == '\\') s += '/';
        else if (c == ':') s += "\\\\:";
        else if (c == '\'') s += "\\\\\\'";
        else if (c == ',' || c == ';' || c == '[' || c == ']') { s += '\\'; s += c; }
        else s += c;
    }
    return s;
}
}

bool Ffmpeg::checkFfmpeg(std::string& outVersion, std::string& errMsg) {
    std::string out;
    int rc = runCaptureRc("ffmpeg -version 2>&1", out);
    if (rc != 0 || out.empty()) { errMsg = "FFmpeg not found on PATH"; return false; }
    outVersion = firstLine(out);
    std::cout << "ffmpeg: " << outVersion << "\n";
    return true;
}

bool Ffmpeg::checkFfprobe(std::string& outVersion, std::string& errMsg) {
    std::string out;
    int rc = runCaptureRc("ffprobe -version 2>&1", out);
    if (rc != 0 || out.empty()) { errMsg = "ffprobe not found on PATH"; return false; }
    outVersion = firstLine(out);
    std::cout << "ffprobe: " << outVersion << "\n";
    return true;
}

Ffmpeg::ProbeResult Ffmpeg::probeVideo(const std::string& path, std::string& errMsg) {
    ProbeResult r{};
    if (hasUnsafePathChars(path)) { errMsg = "unsafe characters in path"; return r; }
    std::string cmd = "ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate,avg_frame_rate,pix_fmt,color_primaries,color_transfer,color_space,color_range,bits_per_raw_sample,bit_depth -show_entries format=duration -of json " + shellQuote(path);
    std::string out;
    int rc = runCaptureRc(cmd, out);
    if (rc != 0) { errMsg = "ffprobe failed"; return r; }
    if (out.empty()) { errMsg = "ffprobe returned no output"; return r; }
    auto getStr = [&](const std::string& key) {
        std::string needle = "\"" + key + "\": \"";
        size_t pos = out.find(needle);
        if (pos == std::string::npos) return std::string();
        size_t s = pos + needle.size();
        size_t e = out.find("\"", s);
        if (e == std::string::npos) return std::string();
        return out.substr(s, e - s);
    };
    auto getToken = [&](const std::string& key) {
        std::string needle = "\"" + key + "\": ";
        size_t pos = out.find(needle);
        if (pos == std::string::npos) return std::string();
        size_t s = pos + needle.size();
        while (s < out.size() && (out[s] == ' ' || out[s] == '"')) ++s;
        size_t e = s;
        while (e < out.size() && out[e] != ',' && out[e] != '}' && out[e] != '"' && out[e] != '\n' && out[e] != '\r') ++e;
        return out.substr(s, e - s);
    };
    auto getInt = [&](const std::string& key) {
        const std::string tok = getToken(key);
        if (tok.empty()) return 0;
        return static_cast<int>(std::strtol(tok.c_str(), nullptr, 10));
    };
    auto getDouble = [&](const std::string& key) {
        const std::string tok = getToken(key);
        if (tok.empty()) return 0.0;
        return std::strtod(tok.c_str(), nullptr);
    };
    r.codec = getStr("codec_name");
    r.width = getInt("width");
    r.height = getInt("height");
    if (r.codec.empty() || r.width <= 0 || r.height <= 0) {
        errMsg = "ffprobe returned no video stream";
        return r;
    }
    r.fps = parseFps(getStr("avg_frame_rate"));
    if (r.fps == 0.0) r.fps = parseFps(getStr("r_frame_rate"));
    r.duration = getDouble("duration");
    r.pixFmt = getStr("pix_fmt");
    r.primaries = getStr("color_primaries");
    r.transfer = getStr("color_transfer");
    r.matrix = getStr("color_space");
    r.range = getStr("color_range");
    r.bitDepth = getInt("bits_per_raw_sample");
    if (r.bitDepth == 0) r.bitDepth = getInt("bit_depth");
    std::string acmd = "ffprobe -v error -select_streams a:0 -show_entries stream=codec_type -of json " + shellQuote(path);
    r.hasAudio = runCapture(acmd).find("audio") != std::string::npos;
    return r;
}

std::vector<std::string> Ffmpeg::extractFrames(const std::string& video, const std::string& outDir, int count, std::string& logCmd, std::string& errMsg) {
    std::vector<std::string> files;
    if (hasUnsafePathChars(video) || hasUnsafePathChars(outDir)) { errMsg = "unsafe characters in path"; return files; }
    std::error_code dcEc;
    fs::create_directories(outDir, dcEc);
    if (dcEc) { errMsg = "failed to create output directory"; return files; }
    std::string perr;
    ProbeResult probe = probeVideo(video, perr);
    if (!perr.empty()) { errMsg = perr; return files; }
    for (int i = 0; i < count; ++i) {
        double t;
        if (probe.duration > 0.0) {
            t = probe.duration * (i + 1.0) / (count + 1.0);
        } else {
            t = (i + 1.0) * 0.5;
        }
        std::string outPath = outDir + "/src_" + std::to_string(i) + ".png";
        std::ostringstream cmd;
        cmd << "ffmpeg -y -ss " << t << " -i " << shellQuote(video)
            << " -frames:v 1 -pix_fmt rgb48be " << shellQuote(outPath) << " 2>&1";
        logCmd = cmd.str();
        std::cout << logCmd << "\n";
        int rc = std::system(logCmd.c_str());
        if (rc != 0 || !fileNonEmpty(outPath)) {
            std::ostringstream fallback;
            fallback << "ffmpeg -y -ss " << t << " -i " << shellQuote(video)
                << " -frames:v 1 -pix_fmt rgb24 " << shellQuote(outPath) << " 2>&1";
            logCmd = fallback.str();
            std::cout << "16-bit extraction failed, falling back to 8-bit\n" << logCmd << "\n";
            rc = std::system(logCmd.c_str());
            if (rc != 0) { errMsg = "frame extraction failed"; return files; }
        }
        if (!fileNonEmpty(outPath)) { errMsg = "frame extraction produced no output"; return files; }
        files.push_back(outPath);
    }
    return files;
}

bool Ffmpeg::applyLutPreview(const std::string& srcVideo, const std::string& cubeFile, const std::string& outVideo, std::string& logCmd, std::string& errMsg) {
    if (hasUnsafePathChars(srcVideo) || hasUnsafePathChars(cubeFile) || hasUnsafePathChars(outVideo)) {
        errMsg = "unsafe characters in path";
        return false;
    }
    std::string filter = "lut3d=file=" + escapeLut3dPath(cubeFile) + ":interp=tetrahedral";
    std::ostringstream cmd;
    cmd << "ffmpeg -y -i " << shellQuote(srcVideo)
        << " -vf " << shellQuote(filter)
        << " -c:v libx264 -pix_fmt yuv420p -colorspace bt709"
        << " -color_primaries bt709 -color_trc bt709 -color_range tv"
        << " -movflags +faststart "
        << shellQuote(outVideo) << " 2>&1";
    logCmd = cmd.str();
    std::cout << logCmd << "\n";
    int rc = std::system(logCmd.c_str());
    if (rc != 0 || !fileNonEmpty(outVideo)) { errMsg = "lut3d apply failed"; return false; }
    return true;
}

bool Ffmpeg::grabFrameAt(const std::string& video, double timestamp, const std::string& outPath, std::string& errMsg) {
    if (hasUnsafePathChars(video) || hasUnsafePathChars(outPath)) { errMsg = "unsafe characters in path"; return false; }
    std::ostringstream cmd;
    cmd << "ffmpeg -y -ss " << timestamp << " -i " << shellQuote(video)
        << " -frames:v 1 " << shellQuote(outPath) << " 2>&1";
    int rc = std::system(cmd.str().c_str());
    if (rc != 0 || !fileNonEmpty(outPath)) { errMsg = "grab frame failed"; return false; }
    return true;
}

std::string Ffmpeg::formatProbeHuman(const ProbeResult& r) {
    std::ostringstream s;
    s << "codec=" << r.codec << " " << r.width << "x" << r.height
      << " fps=" << r.fps << " dur=" << r.duration
      << " pixfmt=" << r.pixFmt << " primaries=" << r.primaries
      << " transfer=" << r.transfer << " matrix=" << r.matrix
      << " range=" << r.range << " bitdepth=" << r.bitDepth
      << " audio=" << (r.hasAudio ? "yes" : "no");
    return s.str();
}

std::string Ffmpeg::shellQuote(const std::string& s) {
    std::string out = "\"";
    for (char c : s) {
        if (c == '"') out += "\\\"";
        else out += c;
    }
    out += "\"";
    return out;
}

double Ffmpeg::parseFps(const std::string& frac) {
    if (frac.empty() || frac == "N/A" || frac == "0/0") return 0.0;
    size_t slash = frac.find('/');
    if (slash == std::string::npos) {
        return std::strtod(frac.c_str(), nullptr);
    }
    double num = std::strtod(frac.substr(0, slash).c_str(), nullptr);
    double den = std::strtod(frac.substr(slash + 1).c_str(), nullptr);
    if (den == 0.0) return 0.0;
    return num / den;
}
