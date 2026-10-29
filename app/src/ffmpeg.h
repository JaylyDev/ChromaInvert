#pragma once

#include <string>

namespace host {

bool probe_duration(const std::string& ffprobe, const std::string& video, double& seconds);
int extract_frame(const std::string& ffmpeg, const std::string& video, double at_seconds, const std::string& out_png);
int apply_lut(const std::string& ffmpeg, const std::string& input, const std::string& cube, const std::string& output);
bool is_video_path(const std::string& path);

}  // namespace host
