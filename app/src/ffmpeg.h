#pragma once

#include <string>
#include <vector>

namespace host {

bool probe_duration(const std::string& ffprobe, const std::string& video, double& seconds);
int extract_frame(const std::string& ffmpeg, const std::string& video, double at_seconds, const std::string& out_png);
int apply_lut(const std::string& ffmpeg, const std::string& input, const std::string& cube, const std::string& output);
bool is_video_path(const std::string& path);

}  // namespace host

class Ffmpeg {
public:
    struct ProbeResult {
        std::string codec;
        int width;
        int height;
        double fps;
        double duration;
        std::string pixFmt;
        std::string primaries;
        std::string transfer;
        std::string matrix;
        std::string range;
        int bitDepth;
        bool hasAudio;
    };

    static bool checkFfmpeg(std::string& outVersion, std::string& errMsg);
    static bool checkFfprobe(std::string& outVersion, std::string& errMsg);
    static ProbeResult probeVideo(const std::string& path, std::string& errMsg);
    static std::vector<std::string> extractFrames(const std::string& video, const std::string& outDir, int count, std::string& logCmd, std::string& errMsg);
    static bool applyLutPreview(const std::string& srcVideo, const std::string& cubeFile, const std::string& outVideo, std::string& logCmd, std::string& errMsg);
    static bool grabFrameAt(const std::string& video, double timestamp, const std::string& outPath, std::string& errMsg);
    static std::string formatProbeHuman(const ProbeResult& r);

private:
    static std::string shellQuote(const std::string& s);
    static double parseFps(const std::string& frac);
};
