#pragma once

#include <string>
#include <vector>

namespace host {

struct RunOptions {
  std::string workdir = "work";
  std::string job_file = "job.json";
  std::vector<std::string> source_frames;
  std::vector<std::string> reference_frames;
  std::string input_profile = "rec709";
  int coarse_size = 17;
  int lut_size = 33;
  int iterations = 400;
  int fine_iterations = 30;
  double strength = 1.0;
  int seed = 42;
  std::string device = "auto";
  std::string output_cube = "out.cube";
  std::string report_json = "report.json";
  std::string python = "python";
};

struct EngineResult {
  bool ok = false;
  std::string cube;
  double seconds = 0.0;
  std::string error;
};

std::string quote_arg(const std::string& arg);
std::string shell_command(const std::string& cmd);
bool contains_shell_metachars(const std::string& arg);
int write_job_json(const std::string& path, const RunOptions& opts);
EngineResult run_engine(const RunOptions& opts, const std::string& job_path);
int print_report_summary(const std::string& report_path);

}  // namespace host
