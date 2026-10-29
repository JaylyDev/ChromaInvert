#pragma once

#include <string>

class Preview {
public:
    static bool generatePreview(const std::string& srcVideo, const std::string& cubeFile, const std::string& workDir, std::string& outPreviewVideo, std::string& errMsg);
    static bool grabBeforeAfter(const std::string& srcVideo, const std::string& gradedVideo, double timestamp, const std::string& outBefore, const std::string& outAfter, std::string& errMsg);
};