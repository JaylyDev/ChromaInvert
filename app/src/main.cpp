#include "Ffmpeg.h"
#include "JobRunner.h"
#include "Preview.h"

#include <filesystem>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

int main(int argc, char** argv) {
    std::string ver, err;
    if (!Ffmpeg::checkFfmpeg(ver, err)) { std::cerr << err << "\n"; return 1; }
    if (!Ffmpeg::checkFfprobe(ver, err)) { std::cerr << err << "\n"; return 1; }

    std::string video = (argc > 1) ? argv[1] : "";
    if (!video.empty()) {
        auto probe = Ffmpeg::probeVideo(video, err);
        if (!err.empty() || probe.codec.empty() || probe.width <= 0) {
            std::cerr << (err.empty() ? "probe found no video stream" : err) << "\n";
            return 1;
        }
        std::cout << Ffmpeg::formatProbeHuman(probe) << "\n";
        std::string outDir = "work";
        std::string logCmd;
        auto frames = Ffmpeg::extractFrames(video, outDir, 3, logCmd, err);
        if (!err.empty() || frames.empty()) {
            std::cerr << (err.empty() ? "frame extraction produced no frames" : err) << "\n";
            return 1;
        }
        for (auto& f : frames) std::cout << "frame: " << f << "\n";

        fs::path absOut = fs::absolute(outDir);
        for (auto& f : frames) f = fs::absolute(f).string();
        fs::path absCube = absOut / "out.cube";
        fs::path absReport = absOut / "report.json";
        std::string srcArr = "[";
        for (size_t i = 0; i < frames.size(); ++i) {
            if (i) srcArr += ",";
            srcArr += "\"" + JobRunner::jsonEscape(frames[i]) + "\"";
        }
        srcArr += "]";
        std::string refArr = "[]";
        if (!JobRunner::writeJobJson((absOut / "job.json").string(), srcArr, refArr, absCube.string(), absReport.string(), "rec709", 33, 17, 200, 1.0, 42)) {
            std::cerr << "failed to write job.json\n";
            return 1;
        }
        std::cout << "wrote " << (absOut / "job.json").string() << "\n";

        std::error_code ec;
        if (!fs::exists(absCube, ec)) {
            std::cout << "preview skipped: no cube yet (run the engine first)\n";
            return 0;
        }
        std::string preview, perr;
        if (Preview::generatePreview(video, absCube.string(), absOut.string(), preview, perr)) {
            std::cout << "preview: " << preview << "\n";
        } else {
            std::cerr << "preview failed: " << perr << "\n";
            return 1;
        }
    }
    return 0;
}