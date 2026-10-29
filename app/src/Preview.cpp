#include "Preview.h"
#include "ffmpeg.h"

#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

namespace {
bool inputOk(const std::string& p) {
    std::error_code ec;
    return fs::exists(p, ec) && fs::is_regular_file(p, ec) && fs::file_size(p, ec) > 0;
}
}

bool Preview::generatePreview(const std::string& srcVideo, const std::string& cubeFile, const std::string& workDir, std::string& outPreviewVideo, std::string& errMsg) {
    if (!inputOk(srcVideo)) { errMsg = "source video missing"; return false; }
    if (!inputOk(cubeFile)) { errMsg = "cube file missing"; return false; }
    std::error_code dcEc;
    fs::create_directories(workDir, dcEc);
    if (dcEc) { errMsg = "failed to create output directory"; return false; }
    std::string preview = workDir + "/graded.mp4";
    std::string logCmd;
    if (!Ffmpeg::applyLutPreview(srcVideo, cubeFile, preview, logCmd, errMsg)) return false;
    outPreviewVideo = preview;
    return true;
}

bool Preview::grabBeforeAfter(const std::string& srcVideo, const std::string& gradedVideo, double timestamp, const std::string& outBefore, const std::string& outAfter, std::string& errMsg) {
    if (!Ffmpeg::grabFrameAt(srcVideo, timestamp, outBefore, errMsg)) return false;
    if (!Ffmpeg::grabFrameAt(gradedVideo, timestamp, outAfter, errMsg)) return false;
    return true;
}