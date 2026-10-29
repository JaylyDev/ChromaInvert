#include "Preview.h"
#include "Ffmpeg.h"

bool Preview::generatePreview(const std::string& srcVideo, const std::string& cubeFile, const std::string& workDir, std::string& outPreviewVideo, std::string& errMsg) {
    outPreviewVideo = workDir + "/graded.mp4";
    std::string logCmd;
    return Ffmpeg::applyLutPreview(srcVideo, cubeFile, outPreviewVideo, logCmd, errMsg);
}

bool Preview::grabBeforeAfter(const std::string& srcVideo, const std::string& gradedVideo, double timestamp, const std::string& outBefore, const std::string& outAfter, std::string& errMsg) {
    if (!Ffmpeg::grabFrameAt(srcVideo, timestamp, outBefore, errMsg)) return false;
    if (!Ffmpeg::grabFrameAt(gradedVideo, timestamp, outAfter, errMsg)) return false;
    return true;
}