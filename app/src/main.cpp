#include <cerrno>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <vector>

#include "ffmpeg.h"
#include "job_runner.h"

namespace {

struct CliOptions {
  std::string source_video;
  std::string reference;
  std::string preview_out;
  std::string ffmpeg = "ffmpeg";
  std::string ffprobe = "ffprobe";
  host::RunOptions run;
  std::vector<double> fractions = {0.25, 0.5, 0.75};
};

void usage() {
  std::printf(
      "usage:\n"
      "  chromainvert-host run --source-video SRC.mov --reference REF.png [options]\n"
      "  chromainvert-host run --source-frames A.png,B.png --reference-frames R.png [options]\n"
      "  chromainvert-host preview --input SRC --cube OUT.cube --output GRADED [--ffmpeg ffmpeg]\n"
      "\nrun options:\n"
      "  --workdir PATH  --job-file NAME  --output-cube NAME  --report-json NAME\n"
      "  --profile rec709  --coarse-size 17  --lut-size 33  --iterations 400\n"
      "  --fine-iterations 30  --strength 1.0  --seed 42  --device auto\n"
      "  --python PATH  --ffmpeg PATH  --ffprobe PATH  --preview-out PATH\n");
}

bool take_value(int argc, char** argv, int& i, std::string& out) {
  if (i + 1 >= argc) {
    return false;
  }
  out = argv[++i];
  return true;
}

std::string trim_spaces(const std::string& text) {
  size_t first = text.find_first_not_of(" \t");
  if (first == std::string::npos) {
    return "";
  }
  return text.substr(first, text.find_last_not_of(" \t") - first + 1);
}

std::vector<std::string> split_list(const std::string& text) {
  std::vector<std::string> items;
  std::string current;
  for (char c : text) {
    if (c == ',') {
      std::string item = trim_spaces(current);
      if (!item.empty()) {
        items.push_back(item);
      }
      current.clear();
    } else {
      current += c;
    }
  }
  std::string item = trim_spaces(current);
  if (!item.empty()) {
    items.push_back(item);
  }
  return items;
}

void absolutize_frames(std::vector<std::string>& frames) {
  for (std::string& frame : frames) {
    frame = std::filesystem::absolute(frame).string();
  }
}

bool parse_number(const std::string& text, double& value) {
  char* end = nullptr;
  errno = 0;
  double parsed = std::strtod(text.c_str(), &end);
  if (errno != 0 || end == text.c_str() || *end != '\0' || !std::isfinite(parsed)) {
    return false;
  }
  value = parsed;
  return true;
}

bool parse_int_value(const std::string& text, int& value) {
  char* end = nullptr;
  errno = 0;
  long parsed = std::strtol(text.c_str(), &end, 10);
  if (errno != 0 || end == text.c_str() || *end != '\0' || parsed < INT_MIN || parsed > INT_MAX) {
    return false;
  }
  value = static_cast<int>(parsed);
  return true;
}

bool is_job_basename(const std::string& name) {
  if (name.empty() || name == "." || name == "..") {
    return false;
  }
  if (name.find_first_of("/\\:") != std::string::npos) {
    return false;
  }
  return !std::filesystem::path(name).is_absolute();
}

bool parse_flag(int argc, char** argv, int& i, const std::string& arg, CliOptions& opts,
                std::string& preview_in, std::string& preview_cube, std::string& error) {
  double number = 0.0;
  if (arg == "--source-video") {
    return take_value(argc, argv, i, opts.source_video);
  }
  if (arg == "--reference") {
    return take_value(argc, argv, i, opts.reference);
  }
  if (arg == "--source-frames") {
    std::string list;
    if (!take_value(argc, argv, i, list)) {
      return false;
    }
    opts.run.source_frames = split_list(list);
    return true;
  }
  if (arg == "--reference-frames") {
    std::string list;
    if (!take_value(argc, argv, i, list)) {
      return false;
    }
    opts.run.reference_frames = split_list(list);
    return true;
  }
  if (arg == "--workdir") {
    return take_value(argc, argv, i, opts.run.workdir);
  }
  if (arg == "--job-file") {
    return take_value(argc, argv, i, opts.run.job_file);
  }
  if (arg == "--output-cube") {
    return take_value(argc, argv, i, opts.run.output_cube);
  }
  if (arg == "--report-json") {
    return take_value(argc, argv, i, opts.run.report_json);
  }
  if (arg == "--profile") {
    return take_value(argc, argv, i, opts.run.input_profile);
  }
  if (arg == "--python") {
    return take_value(argc, argv, i, opts.run.python);
  }
  if (arg == "--ffmpeg") {
    return take_value(argc, argv, i, opts.ffmpeg);
  }
  if (arg == "--ffprobe") {
    return take_value(argc, argv, i, opts.ffprobe);
  }
  if (arg == "--preview-out") {
    return take_value(argc, argv, i, opts.preview_out);
  }
  if (arg == "--input") {
    return take_value(argc, argv, i, preview_in);
  }
  if (arg == "--cube") {
    return take_value(argc, argv, i, preview_cube);
  }
  if (arg == "--output") {
    return take_value(argc, argv, i, opts.preview_out);
  }
  std::string text;
  if (arg == "--coarse-size" || arg == "--lut-size" || arg == "--iterations" || arg == "--fine-iterations" ||
      arg == "--seed" || arg == "--strength" || arg == "--device" || arg == "--fractions") {
    if (!take_value(argc, argv, i, text)) {
      return false;
    }
  } else {
    error = "unknown flag: " + arg;
    return false;
  }
  if (arg == "--device") {
    opts.run.device = text;
    return true;
  }
  if (arg == "--fractions") {
    opts.fractions.clear();
    for (const std::string& item : split_list(text)) {
      if (!parse_number(item, number)) {
        return false;
      }
      opts.fractions.push_back(number);
    }
    return !opts.fractions.empty();
  }
  if (arg == "--coarse-size") {
    return parse_int_value(text, opts.run.coarse_size);
  } else if (arg == "--lut-size") {
    return parse_int_value(text, opts.run.lut_size);
  } else if (arg == "--iterations") {
    return parse_int_value(text, opts.run.iterations);
  } else if (arg == "--fine-iterations") {
    return parse_int_value(text, opts.run.fine_iterations);
  } else if (arg == "--seed") {
    return parse_int_value(text, opts.run.seed);
  } else if (arg == "--strength") {
    if (!parse_number(text, number)) {
      return false;
    }
    opts.run.strength = number;
  }
  return true;
}

int cmd_preview(const std::string& ffmpeg, const std::string& input, const std::string& cube,
                const std::string& output) {
  if (input.empty() || cube.empty() || output.empty()) {
    std::fprintf(stderr, "error: preview needs --input, --cube, and --output\n");
    return 1;
  }
  if (host::contains_shell_metachars(ffmpeg) || host::contains_shell_metachars(input) ||
      host::contains_shell_metachars(cube) || host::contains_shell_metachars(output)) {
    std::fprintf(stderr, "error: refusing shell arguments with expansion characters\n");
    return 1;
  }
  if (host::apply_lut(ffmpeg, input, cube, output) != 0) {
    std::fprintf(stderr, "error: ffmpeg lut3d preview failed\n");
    return 1;
  }
  std::printf("preview: %s\n", output.c_str());
  return 0;
}

int cmd_run(CliOptions& opts) {
  if (opts.run.input_profile != "rec709") {
    std::fprintf(stderr, "error: contract v1 supports rec709 only, got %s\n", opts.run.input_profile.c_str());
    return 1;
  }
  if (!is_job_basename(opts.run.job_file) || !is_job_basename(opts.run.output_cube) ||
      !is_job_basename(opts.run.report_json)) {
    std::fprintf(stderr, "error: --job-file, --output-cube, and --report-json must be plain file names\n");
    return 1;
  }
  if (opts.run.strength < 0.0 || opts.run.strength > 1.0) {
    std::fprintf(stderr, "error: strength must be in [0, 1]\n");
    return 1;
  }
  if (opts.run.coarse_size < 2 || opts.run.lut_size < 2) {
    std::fprintf(stderr, "error: lattice sizes must be at least 2\n");
    return 1;
  }
  if (opts.run.iterations < 0 || opts.run.fine_iterations < 0 ||
      opts.run.iterations + opts.run.fine_iterations == 0) {
    std::fprintf(stderr, "error: iteration counts must be non-negative with a positive total\n");
    return 1;
  }
  for (double fraction : opts.fractions) {
    if (!(fraction >= 0.0 && fraction < 1.0)) {
      std::fprintf(stderr, "error: --fractions values must be in [0, 1)\n");
      return 1;
    }
  }
  std::vector<std::string> shell_args = {opts.source_video,        opts.reference, opts.preview_out,
                                         opts.ffmpeg,              opts.ffprobe,   opts.run.workdir,
                                         opts.run.python,          opts.run.device, opts.run.input_profile};
  shell_args.insert(shell_args.end(), opts.run.source_frames.begin(), opts.run.source_frames.end());
  shell_args.insert(shell_args.end(), opts.run.reference_frames.begin(), opts.run.reference_frames.end());
  for (const std::string& arg : shell_args) {
    if (host::contains_shell_metachars(arg)) {
      std::fprintf(stderr, "error: refusing shell arguments with expansion characters\n");
      return 1;
    }
  }
  std::error_code dir_error;
  std::filesystem::create_directories(opts.run.workdir, dir_error);
  if (dir_error) {
    std::fprintf(stderr, "error: cannot create workdir %s\n", opts.run.workdir.c_str());
    return 1;
  }

  std::string job_dir = opts.run.workdir;
  if (!opts.source_video.empty()) {
    double duration = 0.0;
    if (!host::probe_duration(opts.ffprobe, opts.source_video, duration)) {
      std::fprintf(stderr, "error: ffprobe could not read duration of %s\n", opts.source_video.c_str());
      return 1;
    }
    opts.run.source_frames.clear();
    for (size_t k = 0; k < opts.fractions.size(); ++k) {
      char name[64];
      std::snprintf(name, sizeof(name), "src_%03u.png", static_cast<unsigned>(k));
      std::string out = (std::filesystem::path(job_dir) / name).string();
      if (host::extract_frame(opts.ffmpeg, opts.source_video, opts.fractions[k] * duration, out) != 0) {
        std::fprintf(stderr, "error: frame extraction failed for %s\n", opts.source_video.c_str());
        return 1;
      }
      opts.run.source_frames.push_back(name);
    }
  } else {
    absolutize_frames(opts.run.source_frames);
  }
  if (!opts.reference.empty()) {
    if (host::is_video_path(opts.reference)) {
      double duration = 0.0;
      if (!host::probe_duration(opts.ffprobe, opts.reference, duration)) {
        std::fprintf(stderr, "error: ffprobe could not read duration of %s\n", opts.reference.c_str());
        return 1;
      }
      std::string out = (std::filesystem::path(job_dir) / "ref_000.png").string();
      if (host::extract_frame(opts.ffmpeg, opts.reference, 0.5 * duration, out) != 0) {
        std::fprintf(stderr, "error: frame extraction failed for %s\n", opts.reference.c_str());
        return 1;
      }
      opts.run.reference_frames = {"ref_000.png"};
    } else {
      opts.run.reference_frames = {opts.reference};
      absolutize_frames(opts.run.reference_frames);
    }
  } else {
    absolutize_frames(opts.run.reference_frames);
  }
  if (opts.run.source_frames.empty() || opts.run.reference_frames.empty()) {
    std::fprintf(stderr, "error: need source frames and reference frames\n");
    usage();
    return 1;
  }

  std::string job_path = (std::filesystem::path(job_dir) / opts.run.job_file).string();
  if (host::write_job_json(job_path, opts.run) != 0) {
    std::fprintf(stderr, "error: cannot write %s\n", job_path.c_str());
    return 1;
  }
  std::printf("job: %s\n", job_path.c_str());

  host::EngineResult engine = host::run_engine(opts.run, job_path);
  if (!engine.ok) {
    std::fprintf(stderr, "error: %s\n", engine.error.c_str());
    return 1;
  }
  std::printf("done: cube=%s seconds=%.1f\n", engine.cube.c_str(), engine.seconds);

  std::string report_path = (std::filesystem::path(job_dir) / opts.run.report_json).string();
  if (host::print_report_summary(report_path) != 0) {
    return 1;
  }

  if (!opts.preview_out.empty()) {
    std::string preview_in = opts.source_video.empty() ? opts.run.source_frames.front() : opts.source_video;
    if (!std::filesystem::path(preview_in).is_absolute()) {
      preview_in = (std::filesystem::path(job_dir) / preview_in).string();
    }
    if (host::contains_shell_metachars(engine.cube)) {
      std::fprintf(stderr, "error: refusing shell arguments with expansion characters\n");
      return 1;
    }
    std::string cube = engine.cube;
    if (host::apply_lut(opts.ffmpeg, preview_in, cube, opts.preview_out) != 0) {
      std::fprintf(stderr, "error: ffmpeg lut3d preview failed\n");
      return 1;
    }
    std::printf("preview: %s\n", opts.preview_out.c_str());
  }
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    usage();
    return 1;
  }
  std::string command = argv[1];
  CliOptions opts;
  bool preview_mode = command == "preview";
  std::string preview_in;
  std::string preview_cube;
  if (command != "run" && command != "preview") {
    usage();
    return 1;
  }
  for (int i = 2; i < argc; ++i) {
    std::string error;
    std::string flag = argv[i];
    if (!parse_flag(argc, argv, i, argv[i], opts, preview_in, preview_cube, error)) {
      std::fprintf(stderr, "error: bad flag %s %s\n", flag.c_str(), error.c_str());
      usage();
      return 1;
    }
  }
  if (preview_mode) {
    return cmd_preview(opts.ffmpeg, preview_in, preview_cube, opts.preview_out);
  }
  return cmd_run(opts);
}
