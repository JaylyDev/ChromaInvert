#include "JobRunner.h"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>

void* JobRunner::childHandle = nullptr;

bool JobRunner::writeJobJson(const std::string& path, const std::string& sourceFramesJsonArray, const std::string& refFramesJsonArray, const std::string& outCube, const std::string& reportJson, const std::string& inputProfile, int lutSize, int coarseSize, int iterations, double strength, int seed) {
    std::ofstream f(path);
    if (!f.is_open()) return false;
    f << "{\n";
    f << "  \"job_id\": \"demo01\",\n";
    f << "  \"source_frames\": " << sourceFramesJsonArray << ",\n";
    f << "  \"reference_frames\": " << refFramesJsonArray << ",\n";
    f << "  \"input_profile\": \"" << inputProfile << "\",\n";
    f << "  \"working_space\": \"rec709_scene\",\n";
    f << "  \"lut_size\": " << lutSize << ",\n";
    f << "  \"coarse_size\": " << coarseSize << ",\n";
    f << "  \"iterations\": " << iterations << ",\n";
    f << "  \"strength\": " << strength << ",\n";
    f << "  \"seed\": " << seed << ",\n";
    f << "  \"output_cube\": \"" << outCube << "\",\n";
    f << "  \"report_json\": \"" << reportJson << "\"\n";
    f << "}\n";
    return true;
}

JobRunner::RunResult JobRunner::runEngine(const std::string& jobJsonPath, double timeoutSec, std::function<void(const std::string& line)> onProgress) {
    RunResult res{false, -1, "", {}};
    std::string outLog = jobJsonPath + ".stdout";
    std::ostringstream cmd;
    cmd << "python -m chromainvert run " << jobJsonPath << " > " << outLog << " 2>&1";
    std::cout << cmd.str() << "\n";
    int rc = std::system(cmd.str().c_str());
    res.exitCode = rc;
    std::ifstream in(outLog);
    std::string line;
    while (std::getline(in, line)) {
        res.events.push_back(line);
        if (onProgress) onProgress(line);
    }
    if (rc == 0) res.ok = true;
    else res.error = "engine failed";
    return res;
}

void JobRunner::cancel() {
    std::system("taskkill /F /IM python.exe 2>nul");
}