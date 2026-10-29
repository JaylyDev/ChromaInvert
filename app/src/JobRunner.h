#pragma once

#include <functional>
#include <string>
#include <vector>

class JobRunner {
public:
    struct RunResult {
        bool ok;
        int exitCode;
        std::string error;
        std::vector<std::string> events;
    };

    static bool writeJobJson(const std::string& path, const std::string& sourceFramesJsonArray, const std::string& refFramesJsonArray, const std::string& outCube, const std::string& reportJson, const std::string& inputProfile, int lutSize, int coarseSize, int iterations, double strength, int seed, int fineIterations = 30, const std::string& device = "auto");

    static RunResult runEngine(const std::string& jobJsonPath, double timeoutSec, std::function<void(const std::string& line)> onProgress);

    static void cancel();

    static std::string jsonEscape(const std::string& s);
};
