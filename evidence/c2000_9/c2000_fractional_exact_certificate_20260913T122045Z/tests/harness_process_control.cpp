#include <algorithm>
#include <chrono>
#include <csignal>
#include <cctype>
#include <cerrno>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unistd.h>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

struct Process {
    int pid;
    int parent_pid;
    std::string command;
    std::string python_optimize;
};

static std::string read_file(const fs::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return {};
    }
    std::ostringstream contents;
    contents << input.rdbuf();
    return contents.str();
}

static std::string command_line(std::string raw) {
    for (char& character : raw) {
        if (character == '\0') {
            character = ' ';
        }
    }
    while (!raw.empty() && raw.back() == ' ') {
        raw.pop_back();
    }
    return raw;
}

static std::string environment_value(const std::string& raw, const std::string& key) {
    const std::string prefix = key + "=";
    std::size_t begin = 0;
    while (begin < raw.size()) {
        std::size_t end = raw.find('\0', begin);
        if (end == std::string::npos) {
            end = raw.size();
        }
        const std::string entry = raw.substr(begin, end - begin);
        if (entry.rfind(prefix, 0) == 0) {
            return entry.substr(prefix.size());
        }
        begin = end + 1;
    }
    return "<unset>";
}

static int parent_pid(int pid) {
    std::ifstream status("/proc/" + std::to_string(pid) + "/status");
    std::string key;
    while (status >> key) {
        if (key == "PPid:") {
            int value = -1;
            status >> value;
            return value;
        }
        std::string remainder;
        std::getline(status, remainder);
    }
    return -1;
}

static std::vector<Process> scan(const std::string& root) {
    std::vector<Process> result;
    for (const fs::directory_entry& entry : fs::directory_iterator("/proc")) {
        const std::string name = entry.path().filename().string();
        if (name.empty() || !std::all_of(name.begin(), name.end(), [](unsigned char character) {
                return std::isdigit(character);
            })) {
            continue;
        }
        int pid;
        try {
            pid = std::stoi(name);
        } catch (...) {
            continue;
        }
        if (pid == getpid()) {
            continue;
        }
        const std::string raw_command = read_file(entry.path() / "cmdline");
        const std::string command = command_line(raw_command);
        if (command.find(root) == std::string::npos ||
            (command.find("verify_fractional_coloring.py") == std::string::npos &&
             command.find("verify_sum_master.py") == std::string::npos)) {
            continue;
        }
        const std::string environment = read_file(entry.path() / "environ");
        result.push_back({pid, parent_pid(pid), command, environment_value(environment, "PYTHONOPTIMIZE")});
    }
    std::sort(result.begin(), result.end(), [](const Process& left, const Process& right) {
        return left.pid < right.pid;
    });
    return result;
}

static long long milliseconds_since(Clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - start).count();
}

static void install_stub(const fs::path& target, const std::string& behavior) {
    fs::path temporary = target;
    temporary += ".process_test_tmp";
    std::ofstream output(temporary, std::ios::trunc);
    if (!output) {
        throw std::runtime_error("cannot create checker stub");
    }
    if (behavior == "exit_zero") {
        output << "print('CONTROL: invalid child exited zero')\nraise SystemExit(0)\n";
    } else if (behavior == "unrelated_one") {
        output << "import sys\nprint('UNRELATED CHILD FAILURE', file=sys.stderr)\nraise SystemExit(1)\n";
    } else if (behavior == "exit_two") {
        output << "import sys\nprint('REJECT: VerificationError: wrong status', file=sys.stderr)\nraise SystemExit(2)\n";
    } else if (behavior == "syntax_error") {
        output << "this is not valid Python syntax ???\n";
    } else if (behavior == "empty_one") {
        output << "raise SystemExit(1)\n";
    } else if (behavior == "timeout") {
        output << "import time\ntime.sleep(120)\n";
    } else {
        throw std::runtime_error("unknown stub behavior: " + behavior);
    }
    output.close();
    if (!output) {
        throw std::runtime_error("cannot write checker stub");
    }
    fs::rename(temporary, target);
}

static void log_process(std::ofstream& log, const Process& process, std::size_t ordinal,
                        Clock::time_point start) {
    log << "ordinal=" << ordinal << " t_ms=" << milliseconds_since(start)
        << " pid=" << process.pid << " ppid=" << process.parent_pid
        << " PYTHONOPTIMIZE=" << process.python_optimize
        << " cmd=" << process.command << '\n';
    log.flush();
}

int main(int argc, char** argv) {
    try {
        if (argc < 2) {
            throw std::runtime_error("mode required");
        }
        const std::string mode = argv[1];
        if (mode == "observe") {
            if (argc != 6) {
                throw std::runtime_error("observe ROOT EXPECTED LOG TIMEOUT_MS");
            }
            const std::string root = argv[2];
            const int expected = std::stoi(argv[3]);
            const fs::path log_path = argv[4];
            const int timeout_ms = std::stoi(argv[5]);
            std::ofstream log(log_path);
            std::set<int> seen;
            const auto start = Clock::now();
            while (milliseconds_since(start) < timeout_ms) {
                for (const Process& process : scan(root)) {
                    if (seen.insert(process.pid).second) {
                        log_process(log, process, seen.size(), start);
                    }
                }
                if (static_cast<int>(seen.size()) >= expected) {
                    return 0;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            log << "TIMEOUT seen=" << seen.size() << '\n';
            return 1;
        }
        if (mode == "replace_after") {
            if (argc != 8) {
                throw std::runtime_error("replace_after ROOT COUNT TARGET BEHAVIOR LOG TIMEOUT_MS");
            }
            const std::string root = argv[2];
            const int count = std::stoi(argv[3]);
            const fs::path target = argv[4];
            const std::string behavior = argv[5];
            const fs::path log_path = argv[6];
            const int timeout_ms = std::stoi(argv[7]);
            std::ofstream log(log_path);
            std::set<int> seen;
            int last_seen_pid = -1;
            const auto start = Clock::now();
            while (milliseconds_since(start) < timeout_ms) {
                for (const Process& process : scan(root)) {
                    if (seen.insert(process.pid).second) {
                        log_process(log, process, seen.size(), start);
                        last_seen_pid = process.pid;
                    }
                }
                if (static_cast<int>(seen.size()) >= count) {
                    const fs::path last_process = "/proc/" + std::to_string(last_seen_pid);
                    while (fs::exists(last_process) && milliseconds_since(start) < timeout_ms) {
                        std::this_thread::sleep_for(std::chrono::milliseconds(2));
                    }
                    if (fs::exists(last_process)) {
                        log << "TIMEOUT waiting_for_pid=" << last_seen_pid << '\n';
                        return 1;
                    }
                    install_stub(target, behavior);
                    log << "ACTION after_pid_exit=" << last_seen_pid
                        << " replaced=" << target << " behavior=" << behavior << '\n';
                    log.flush();
                    return 0;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            log << "TIMEOUT seen=" << seen.size() << '\n';
            return 1;
        }
        if (mode == "signal_mutation") {
            if (argc != 6) {
                throw std::runtime_error("signal_mutation ROOT SCRATCH_MARKER LOG TIMEOUT_MS");
            }
            const std::string root = argv[2];
            const std::string scratch_marker = argv[3];
            const fs::path log_path = argv[4];
            const int timeout_ms = std::stoi(argv[5]);
            std::ofstream log(log_path);
            std::set<int> seen;
            const auto start = Clock::now();
            while (milliseconds_since(start) < timeout_ms) {
                for (const Process& process : scan(root)) {
                    if (seen.insert(process.pid).second) {
                        log_process(log, process, seen.size(), start);
                    }
                    if (process.command.find(scratch_marker) != std::string::npos) {
                        errno = 0;
                        const int result = ::kill(process.pid, SIGTERM);
                        log << "ACTION signal=SIGTERM pid=" << process.pid
                            << " kill_rc=" << result << " errno=" << errno << '\n';
                        log.flush();
                        return result == 0 ? 0 : 1;
                    }
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            log << "TIMEOUT signal_sent=false\n";
            return 1;
        }
        throw std::runtime_error("unknown mode: " + mode);
    } catch (const std::exception& exception) {
        std::cerr << "PROCESS CONTROL ERROR: " << exception.what() << '\n';
        return 2;
    }
}
