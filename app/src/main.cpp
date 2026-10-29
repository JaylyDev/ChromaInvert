#include "Ffmpeg.h"
#include "JobRunner.h"
#include "Preview.h"

#include <iostream>
#include <string>

int main(int argc, char** argv) {
    std::string ver, err;
    if (!Ffmpeg::checkFfmpeg(ver, err)) { std::cerr << err << "\n"; return 1; }
    if (!Ffmpeg::checkFfprobe(ver, err)) { std::cerr << err << "\n"; return 1; }

    std::string video = (argc > 1) ? argv[1] : "";
    if (!video.empty()) {
        auto probe = Ffmpeg::probeVideo(video, err);
        std::cout << Ffmpeg::formatProbeHuman(probe) << "\n";
        std::string outDir = "work";
        std::string logCmd;
        auto frames = Ffmpeg::extractFrames(video, outDir, 3, logCmd, err);
        for (auto& f : frames) std::cout << "frame: " << f << "\n";

        std::string srcArr = "[";
        for (size_t i = 0; i < frames.size(); ++i) {
            if (i) srcArr += ",";
            srcArr += "\"" + frames[i] + "\"";
        }
        srcArr += "]";
        std::string refArr = "[]";
        JobRunner::writeJobJson(outDir + "/job.json", srcArr, refArr, outDir + "/out.cube", outDir + "/report.json", "rec709", 33, 17, 200, 1.0, 42);
        std::cout << "wrote " << outDir << "/job.json\n";

        std::string cube = outDir + "/out.cube";
        std::string preview, perr;
        if (Preview::generatePreview(video, cube, outDir, preview, perr)) {
            std::cout << "preview: " << preview << "\n";
        } else {
            std::cout << "preview skipped: " << perr << "\n";
        }
    }
    return 0;
}