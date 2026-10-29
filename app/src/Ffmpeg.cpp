#include "Ffmpeg.h"

#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <sstream>

namespace {
std::string runCapture(const std::string& cmd) {
    std::string out;
    FILE* p = popen(cmd.c_str(), "r");
    if (!p) return out;
    char buf[4096];
    while (fgets(buf, sizeof(buf), p)) out += buf;
    pclose(p);
    return out;
}
}

bool Ffmpeg::checkFfmpeg(std::string& outVersion, std::string& errMsg) {
    std::string cmd = "ffmpeg -version 2>&1 | head -n 1";
    std::string out = runCapture(cmd);
    if (out.empty()) { errMsg = "FFmpeg not found on PATH"; return false; }
    outVersion = out;
    std::cout << "ffmpeg: " << out;
    return true;
}

bool Ffmpeg::checkFfprobe(std::string& outVersion, std::string& errMsg) {
    std::string cmd = "ffprobe -version 2>&1 | head -n 1";
    std::string out = runCapture(cmd);
    if (out.empty()) { errMsg = "ffprobe not found on PATH"; return false; }
    outVersion = out;
    std::cout << "ffprobe: " << out;
    return true;
}

Ffmpeg::ProbeResult Ffmpeg::probeVideo(const std::string& path, std::string& errMsg) {
    ProbeResult r{};
    std::string cmd = "ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate,avg_frame_rate,pix_fmt,color_primaries,color_transfer,color_space,color_range,bit_depth -show_entries format=duration -of json " + shellQuote(path);
    std::string out = runCapture(cmd);
    if (out.empty()) { errMsg = "ffprobe failed"; return r; }
    auto getStr = [&](const std::string& key) {
        std::string needle = "\"" + key + "\": \"";
        size_t pos = out.find(needle);
        if (pos == std::string::npos) return std::string();
        size_t s = pos + needle.size();
        size_t e = out.find("\"", s);
        return out.substr(s, e - s);
    };
    auto getInt = [&](const std::string& key) {
        std::string needle = "\"" + key + "\": ";
        size_t pos = out.find(needle);
        if (pos == std::string::npos) return 0;
        size_t s = pos + needle.size();
        return std::stoi(out.substr(s));
    };
    auto getDouble = [&](const std::string& key) {
        std::string needle = "\"" + key + "\": ";
        size_t pos = out.find(needle);
        if (pos == std::string::npos) return 0.0;
        size_t s = pos + needle.size();
        size_t e = out.find_first_of(",}", s);
        return std::stod(out.substr(s, e - s));
    };
    r.codec = getStr("codec_name");
    r.width = getInt("width");
    r.height = getInt("height");
    r.fps = parseFps(getStr("r_frame_rate"));
    r.duration = getDouble("duration");
    r.pixFmt = getStr("pix_fmt");
    r.primaries = getStr("color_primaries");
    r.transfer = getStr("color_transfer");
    r.matrix = getStr("color_space");
    r.range = getStr("color_range");
    r.bitDepth = getInt("bit_depth");
    r.hasAudio = out.find("\"codec_type\": \"audio\"") != std::string::npos;
    return r;
}

std::vector<std::string> Ffmpeg::extractFrames(const std::string& video, const std::string& outDir, int count, std::string& logCmd, std::string& errMsg) {
    std::vector<std::string> files;
    for (int i = 0; i < count; ++i) {
        double t = (i + 1.0) * 0.25; // spread
        std::string outPath = outDir + "/src_" + std::to_string(i) + ".png";
        std::ostringstream cmd;
        cmd << "ffmpeg -y -ss " << t << " -i " << shellQuote(video)
            << " -frames:v 1 -pix_fmt rgb48be " << shellQuote(outPath) << " 2>&1";
        logCmd = cmd.str();
        std::cout << logCmd << "\n";
        int rc = std::system(logCmd.c_str());
        if (rc != 0) { errMsg = "frame extraction failed"; return files; }
        files.push_back(outPath);
    }
    return files;
}

bool Ffmpeg::applyLutPreview(const std::string& srcVideo, const std::string& cubeFile, const std::string& outVideo, std::string& logCmd, std::string& errMsg) {
    std::ostringstream cmd;
    cmd << "ffmpeg -y -i " << shellQuote(srcVideo)
        << " -vf lut3d=file=" << shellQuote(cubeFile) << ":interp=tetrahedral "
        << shellQuote(outVideo) << " 2>&1";
    logCmd = cmd.str();
    std::cout << logCmd << "\n";
    int rc = std::system(logCmd.c_str());
    if (rc != 0) { errMsg = "lut3d apply failed"; return false; }
    return true;
}

bool Ffmpeg::grabFrameAt(const std::string& video, double timestamp, const std::string& outPath, std::string& errMsg) {
    std::ostringstream cmd;
    cmd << "ffmpeg -y -ss " << timestamp << " -i " << shellQuote(video)
        << " -frames:v 1 " << shellQuote(outPath) << " 2>&1";
    int rc = std::system(cmd.str().c_str());
    if (rc != 0) { errMsg = "grab frame failed"; return false; }
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
    size_t slash = frac.find('/');
    if (slash == std::string::npos) {
        try { return std::stod(frac); } catch (...) { return 0.0; }
    }
    double num = std::stod(frac.substr(0, slash));
    double den = std::stod(frac.substr(slash + 1));
    if (den == 0.0) return 0.0;
    return num / den;
}