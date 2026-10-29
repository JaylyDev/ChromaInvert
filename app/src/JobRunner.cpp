#include "JobRunner.h"

#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>

namespace {
std::string quotePath(const std::string& s) {
    std::string out = "\"";
    for (char c : s) {
        if (c == '"') out += "\\\"";
        else out += c;
    }
    out += "\"";
    return out;
}

std::string jsonEscape(const std::string& s) {
    std::string out;
    for (char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default: out += c; break;
        }
    }
    return out;
}

std::string readTail(const std::string& path, size_t maxChars) {
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f.is_open()) return "";
    std::streamoff size = static_cast<std::streamoff>(f.tellg());
    std::streamoff maxOff = static_cast<std::streamoff>(maxChars);
    std::streamoff off = (size > maxOff) ? (size - maxOff) : std::streamoff(0);
    f.seekg(off);
    std::ostringstream s;
    s << f.rdbuf();
    return s.str();
}
}

void* JobRunner::childHandle = nullptr;

bool JobRunner::writeJobJson(const std::string& path, const std::string& sourceFramesJsonArray, const std::string& refFramesJsonArray, const std::string& outCube, const std::string& reportJson, const std::string& inputProfile, int lutSize, int coarseSize, int iterations, double strength, int seed, int fineIterations, const std::string& device) {
    std::ofstream f(path);
    if (!f.is_open()) return false;
    f << "{\n";
    f << "  \"contract_version\": 1,\n";
    f << "  \"source_frames\": " << sourceFramesJsonArray << ",\n";
    f << "  \"reference_frames\": " << refFramesJsonArray << ",\n";
    f << "  \"input_profile\": \"" << jsonEscape(inputProfile) << "\",\n";
    f << "  \"lut_size\": " << lutSize << ",\n";
    f << "  \"coarse_size\": " << coarseSize << ",\n";
    f << "  \"iterations\": " << iterations << ",\n";
    f << "  \"fine_iterations\": " << fineIterations << ",\n";
    f << "  \"strength\": " << strength << ",\n";
    f << "  \"seed\": " << seed << ",\n";
    f << "  \"device\": \"" << jsonEscape(device) << "\",\n";
    f << "  \"output_cube\": \"" << jsonEscape(outCube) << "\",\n";
    f << "  \"report_json\": \"" << jsonEscape(reportJson) << "\"\n";
    f << "}\n";
    return true;
}

JobRunner::RunResult JobRunner::runEngine(const std::string& jobJsonPath, double timeoutSec, std::function<void(const std::string& line)> onProgress) {
    RunResult res{false, -1, "", {}};
    std::string outLog = jobJsonPath + ".stdout";
    std::string errLog = jobJsonPath + ".stderr";
    std::ostringstream cmd;
    cmd << "python -m chromainvert run " << quotePath(jobJsonPath) << " > " << quotePath(outLog) << " 2> " << quotePath(errLog);
    std::cout << cmd.str() << "\n";
    auto start = std::chrono::steady_clock::now();
    int rc = std::system(cmd.str().c_str());
    double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    res.exitCode = rc;
    std::ifstream in(outLog);
    std::string line;
    bool hasDone = false;
    while (std::getline(in, line)) {
        res.events.push_back(line);
        if (line.find("\"done\"") != std::string::npos) hasDone = true;
        if (onProgress) onProgress(line);
    }
    std::string errTail = readTail(errLog, 2000);
    if (timeoutSec > 0 && elapsed > timeoutSec) {
        res.error = "engine timed out";
    } else if (rc != 0 || !hasDone) {
        res.error = "engine failed: " + errTail;
    } else {
        res.ok = true;
    }
    return res;
}

void JobRunner::cancel() {
    std::cout << "cancel is not supported in this revision: close the engine window instead\n";
}