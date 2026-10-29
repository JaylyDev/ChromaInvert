#include "job_runner.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>

#ifdef _WIN32
#define POPEN _popen
#define PCLOSE _pclose
#else
#define POPEN popen
#define PCLOSE pclose
#endif

namespace host {
namespace {

std::string json_escape(const std::string& value) {
  std::string out;
  for (char c : value) {
    switch (c) {
      case '\\':
      case '"':
        out += '\\';
        out += c;
        break;
      case '\b':
        out += "\\b";
        break;
      case '\f':
        out += "\\f";
        break;
      case '\n':
        out += "\\n";
        break;
      case '\r':
        out += "\\r";
        break;
      case '\t':
        out += "\\t";
        break;
      default:
        if (static_cast<unsigned char>(c) < 0x20) {
          char escaped[8];
          std::snprintf(escaped, sizeof(escaped), "\\u%04x", c);
          out += escaped;
        } else {
          out += c;
        }
        break;
    }
  }
  return out;
}

void write_string_list(std::ofstream& job, const std::vector<std::string>& items) {
  job << "[";
  for (size_t i = 0; i < items.size(); ++i) {
    if (i > 0) {
      job << ", ";
    }
    job << "\"" << json_escape(items[i]) << "\"";
  }
  job << "]";
}

void append_utf8(std::string& out, unsigned code) {
  if (code < 0x80) {
    out += static_cast<char>(code);
  } else if (code < 0x800) {
    out += static_cast<char>(0xC0 | (code >> 6));
    out += static_cast<char>(0x80 | (code & 0x3F));
  } else {
    out += static_cast<char>(0xE0 | (code >> 12));
    out += static_cast<char>(0x80 | ((code >> 6) & 0x3F));
    out += static_cast<char>(0x80 | (code & 0x3F));
  }
}

bool decode_hex4(const std::string& line, size_t pos, unsigned& code) {
  if (pos + 4 > line.size()) {
    return false;
  }
  code = 0;
  for (size_t k = 0; k < 4; ++k) {
    char c = line[pos + k];
    code *= 16;
    if (c >= '0' && c <= '9') {
      code += static_cast<unsigned>(c - '0');
    } else if (c >= 'a' && c <= 'f') {
      code += static_cast<unsigned>(c - 'a' + 10);
    } else if (c >= 'A' && c <= 'F') {
      code += static_cast<unsigned>(c - 'A' + 10);
    } else {
      return false;
    }
  }
  return true;
}

bool find_string_field(const std::string& line, const std::string& key, std::string& value) {
  size_t pos = line.find("\"" + key + "\"");
  if (pos == std::string::npos) {
    return false;
  }
  pos = line.find(':', pos);
  if (pos == std::string::npos) {
    return false;
  }
  pos = line.find('"', pos);
  if (pos == std::string::npos) {
    return false;
  }
  std::string out;
  for (size_t i = pos + 1; i < line.size(); ++i) {
    char c = line[i];
    if (c == '"') {
      value = out;
      return true;
    }
    if (c != '\\') {
      out += c;
      continue;
    }
    if (++i >= line.size()) {
      return false;
    }
    switch (line[i]) {
      case '"':
      case '\\':
      case '/':
        out += line[i];
        break;
      case 'b':
        out += '\b';
        break;
      case 'f':
        out += '\f';
        break;
      case 'n':
        out += '\n';
        break;
      case 'r':
        out += '\r';
        break;
      case 't':
        out += '\t';
        break;
      case 'u': {
        unsigned code = 0;
        if (!decode_hex4(line, i + 1, code)) {
          return false;
        }
        i += 4;
        if (code >= 0xD800 && code <= 0xDBFF && line.compare(i + 1, 2, "\\u") == 0) {
          unsigned low = 0;
          if (!decode_hex4(line, i + 3, low) || low < 0xDC00 || low > 0xDFFF) {
            return false;
          }
          i += 6;
          code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00);
          out += static_cast<char>(0xF0 | (code >> 18));
          out += static_cast<char>(0x80 | ((code >> 12) & 0x3F));
          out += static_cast<char>(0x80 | ((code >> 6) & 0x3F));
          out += static_cast<char>(0x80 | (code & 0x3F));
        } else {
          append_utf8(out, code);
        }
        break;
      }
      default:
        return false;
    }
  }
  return false;
}

bool find_number_field(const std::string& line, const std::string& key, double& value) {
  size_t pos = line.find("\"" + key + "\"");
  if (pos == std::string::npos) {
    return false;
  }
  pos = line.find(':', pos);
  if (pos == std::string::npos) {
    return false;
  }
  const char* start = line.c_str() + pos + 1;
  char* end = nullptr;
  double parsed = std::strtod(start, &end);
  if (end == start) {
    return false;
  }
  value = parsed;
  return true;
}

}  // namespace

std::string quote_arg(const std::string& arg) {
  std::string out = "\"";
  for (char c : arg) {
    if (c == '"') {
      out += '\\';
    }
    out += c;
  }
  out += '"';
  return out;
}

std::string shell_command(const std::string& cmd) {
#ifdef _WIN32
  return "call " + cmd;
#else
  return cmd;
#endif
}

bool contains_shell_metachars(const std::string& arg) {
#ifdef _WIN32
  const char* metachars = "%\"\r\n";
#else
  const char* metachars = "$`\"\r\n\\!";
#endif
  return arg.find_first_of(metachars) != std::string::npos;
}

int write_job_json(const std::string& path, const RunOptions& opts) {
  std::ofstream job(path, std::ios::binary | std::ios::trunc);
  if (!job) {
    return 1;
  }
  job << "{\n";
  job << "  \"contract_version\": 1,\n";
  job << "  \"source_frames\": ";
  write_string_list(job, opts.source_frames);
  job << ",\n  \"reference_frames\": ";
  write_string_list(job, opts.reference_frames);
  job << ",\n";
  job << "  \"input_profile\": \"" << json_escape(opts.input_profile) << "\",\n";
  job << "  \"coarse_size\": " << opts.coarse_size << ",\n";
  job << "  \"lut_size\": " << opts.lut_size << ",\n";
  job << "  \"iterations\": " << opts.iterations << ",\n";
  job << "  \"fine_iterations\": " << opts.fine_iterations << ",\n";
  job << "  \"strength\": " << std::setprecision(17) << opts.strength << ",\n";
  job << "  \"seed\": " << opts.seed << ",\n";
  job << "  \"device\": \"" << json_escape(opts.device) << "\",\n";
  job << "  \"output_cube\": \"" << json_escape(opts.output_cube) << "\",\n";
  job << "  \"report_json\": \"" << json_escape(opts.report_json) << "\"\n";
  job << "}\n";
  job.flush();
  return job ? 0 : 1;
}

EngineResult run_engine(const RunOptions& opts, const std::string& job_path) {
  EngineResult result;
  std::string cmd = quote_arg(opts.python) + " -m chromainvert.cli run " + quote_arg(job_path) + " 2>&1";
  std::printf("run: %s\n", cmd.c_str());
  std::fflush(stdout);
  FILE* pipe = POPEN(shell_command(cmd).c_str(), "r");
  if (pipe == nullptr) {
    result.error = "failed to spawn python engine";
    return result;
  }
  char buffer[65536];
  std::string tail;
  while (std::fgets(buffer, sizeof(buffer), pipe) != nullptr) {
    std::string line(buffer);
    while (!line.empty() && (line.back() == '\n' || line.back() == '\r')) {
      line.pop_back();
    }
    if (line.empty()) {
      continue;
    }
    std::string event;
    if (find_string_field(line, "event", event)) {
      if (event == "progress") {
        double iter = 0.0, iters = 0.0, loss = 0.0, elapsed = 0.0;
        find_number_field(line, "iter", iter);
        find_number_field(line, "iters", iters);
        find_number_field(line, "loss", loss);
        find_number_field(line, "elapsed_s", elapsed);
        std::printf("[engine %d/%d] loss=%.5f elapsed=%.1fs\n", static_cast<int>(iter),
                    static_cast<int>(iters), loss, elapsed);
        std::fflush(stdout);
      } else if (event == "done") {
        std::string cube;
        double seconds = 0.0;
        if (find_string_field(line, "cube", cube) && !cube.empty() &&
            find_number_field(line, "seconds", seconds)) {
          result.cube = cube;
          result.seconds = seconds;
          result.ok = true;
        }
      } else {
        std::printf("engine: %s\n", line.c_str());
        std::fflush(stdout);
      }
    } else {
      std::printf("engine: %s\n", line.c_str());
      std::fflush(stdout);
    }
    tail = line;
  }
  int status = PCLOSE(pipe);
  if (status != 0) {
    result.ok = false;
  }
  if (!result.ok) {
    if (status != 0) {
      result.error = "engine process exited with status " + std::to_string(status) + ": " + tail;
    } else {
      result.error = "engine ended without a done event: " + tail;
    }
  }
  return result;
}

int print_report_summary(const std::string& report_path) {
  std::ifstream report(report_path, std::ios::binary);
  if (!report) {
    std::fprintf(stderr, "error: cannot open %s\n", report_path.c_str());
    return 1;
  }
  std::ostringstream text;
  text << report.rdbuf();
  std::string body = text.str();
  std::string device;
  double seconds = 0.0, total = 0.0, neighbor = 0.0, lo = 0.0, hi = 0.0;
  find_string_field(body, "device", device);
  find_number_field(body, "seconds", seconds);
  find_number_field(body, "total", total);
  find_number_field(body, "max_neighbor_delta", neighbor);
  find_number_field(body, "lattice_min", lo);
  find_number_field(body, "lattice_max", hi);
  std::printf("report: device=%s seconds=%.1f final_loss=%.5f lattice=[%.3f, %.3f] max_neighbor_delta=%.4f\n",
              device.c_str(), seconds, total, lo, hi, neighbor);
  return 0;
}

}  // namespace host
