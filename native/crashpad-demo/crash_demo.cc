// Copyright 2026 The Crashpad Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <algorithm>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "base/files/file_path.h"
#include "build/build_config.h"
#include "client/crash_report_database.h"
#include "client/crashpad_client.h"
#include "client/crashpad_info.h"
#include "client/settings.h"
#include "util/file/file_io.h"
#include "util/file/filesystem.h"
#include "util/misc/tri_state.h"

#if BUILDFLAG(IS_WIN)
#include <windows.h>

#include "client/simple_address_range_bag.h"
#else
#include <errno.h>
#include <unistd.h>

#include "util/linux/exception_handler_client.h"
#endif

extern "C" void AriadneCrashDemoFault(volatile uint32_t* destination);
#if BUILDFLAG(IS_WIN)
extern "C" void AriadneCrashDemoBapWorkload(const uint64_t* inputs,
                                        uint64_t expected_checksum);
extern "C" const uint8_t AriadneCrashDemoBapWorkloadProducer[];
extern "C" const uint8_t AriadneCrashDemoBapWorkloadFault[];
extern "C" const uint8_t AriadneCrashDemoBapWorkloadEnd[];
#endif

namespace crashpad {
namespace {

constexpr size_t kCodeExtentBytes = 256;
constexpr uint32_t kIndirectMemoryBudget = 4u * 1024u * 1024u;
constexpr char kIntegrationProfile[] = "ariadne-crashpad-null-write-v1";
constexpr char kBapIntegrationProfile[] = "ariadne-crashpad-bap-workload-v1";

#if BUILDFLAG(IS_WIN)
constexpr size_t kMaxWorkloadCodeExtentBytes = 1024;
constexpr uint64_t kWorkloadInputs[] = {3, 5, 8, 13, 21, 34, 55, 89};

// Independent unsigned reference for the assembly's data-dependent checksum.
// Unsigned operations intentionally wrap modulo 2^64.
constexpr uint64_t WorkloadChecksum() {
  uint64_t value = kWorkloadInputs[0];
  for (size_t index = 0; index < 8; ++index) {
    value = ~(value + kWorkloadInputs[index]) + index + 1;
    value = value * 4 + index;
    value += index + 3;
  }
  for (size_t index = 0; index < 4; ++index) {
    value += kWorkloadInputs[index];
  }
  value += (value & 1) ? 11 : 7;
  return value + 17;
}
constexpr uint64_t kExpectedWorkloadChecksum = WorkloadChecksum();
static_assert(kExpectedWorkloadChecksum == UINT64_C(0x4bea2),
              "Controlled workload checksum changed");

// CrashpadInfo keeps a nonowning pointer; the bag must survive until capture.
SimpleAddressRangeBag g_code_ranges;

size_t ReadableRegionBytes(uintptr_t address) {
  MEMORY_BASIC_INFORMATION region = {};
  if (VirtualQuery(reinterpret_cast<const void*>(address),
                   &region,
                   sizeof(region)) != sizeof(region) ||
      region.State != MEM_COMMIT || (region.Protect & PAGE_GUARD) != 0) {
    fprintf(stderr, "Cannot query requested capture memory.\n");
    return 0;
  }

  switch (region.Protect & 0xff) {
    case PAGE_READONLY:
    case PAGE_READWRITE:
    case PAGE_WRITECOPY:
    case PAGE_EXECUTE_READ:
    case PAGE_EXECUTE_READWRITE:
    case PAGE_EXECUTE_WRITECOPY:
      break;
    default:
      fprintf(stderr, "Requested capture memory is not readable.\n");
      return 0;
  }

  const uintptr_t region_start = reinterpret_cast<uintptr_t>(region.BaseAddress);
  return region.RegionSize - (address - region_start);
}
#endif

bool ConfigureCapture(uintptr_t function_entry,
                      bool bap_workload,
                      size_t* code_extent_bytes) {
  CrashpadInfo* info = CrashpadInfo::GetCrashpadInfo();
  info->set_gather_indirectly_referenced_memory(TriState::kEnabled,
                                              kIndirectMemoryBudget);
  *code_extent_bytes = kCodeExtentBytes;

#if BUILDFLAG(IS_WIN)
  const size_t readable_bytes = ReadableRegionBytes(function_entry);
  if (bap_workload) {
    const uintptr_t producer =
        reinterpret_cast<uintptr_t>(AriadneCrashDemoBapWorkloadProducer);
    const uintptr_t fault =
        reinterpret_cast<uintptr_t>(AriadneCrashDemoBapWorkloadFault);
    const uintptr_t end =
        reinterpret_cast<uintptr_t>(AriadneCrashDemoBapWorkloadEnd);
    if (!(function_entry < producer && producer < fault && fault < end) ||
        end - function_entry > kMaxWorkloadCodeExtentBytes ||
        end - function_entry > readable_bytes) {
      fprintf(stderr, "Cannot capture the complete controlled workload.\n");
      return false;
    }
    *code_extent_bytes = end - function_entry;
    if (ReadableRegionBytes(reinterpret_cast<uintptr_t>(kWorkloadInputs)) <
            sizeof(kWorkloadInputs) ||
        !g_code_ranges.Insert(const_cast<uint64_t*>(kWorkloadInputs),
                              sizeof(kWorkloadInputs))) {
      fprintf(stderr, "Cannot register all controlled workload inputs.\n");
      return false;
    }
  } else {
    // Preserve the original null-write profile's bounded 256-byte request.
    *code_extent_bytes = std::min(kCodeExtentBytes, readable_bytes);
  }
  if (*code_extent_bytes == 0 ||
      !g_code_ranges.Insert(reinterpret_cast<void*>(function_entry),
                            *code_extent_bytes)) {
    fprintf(stderr, "Cannot register fault-function memory.\n");
    return false;
  }
  info->set_extra_memory_ranges(&g_code_ranges);
#else
  (void)function_entry;
  (void)bap_workload;
#endif

  return true;
}

bool WriteWitness(const base::FilePath& path,
                  uintptr_t function_entry,
                  size_t code_extent_bytes,
                  const std::string& mode,
                  bool bap_workload) {
#if BUILDFLAG(IS_WIN)
  const uint64_t process_id = GetCurrentProcessId();
  constexpr char kExplicitRangeRegistered[] = "true";
#else
  const uint64_t process_id = static_cast<uint64_t>(getpid());
  constexpr char kExplicitRangeRegistered[] = "false";
#endif

  std::string workload_fields;
#if BUILDFLAG(IS_WIN)
  if (bap_workload) {
    char addresses[1024];
    const int length = snprintf(
        addresses,
        sizeof(addresses),
        ",\n  \"explicit_input_range_registered\": true,\n"
        "  \"workload\": {\n"
        "    \"entry\": \"0x%016" PRIxPTR "\",\n"
        "    \"producer\": \"0x%016" PRIxPTR "\",\n"
        "    \"fault\": \"0x%016" PRIxPTR "\",\n"
        "    \"end\": \"0x%016" PRIxPTR "\",\n"
        "    \"expectedDecodedStarts\": 98,\n"
        "    \"inputsAddress\": \"0x%016" PRIxPTR "\",\n"
        "    \"expectedChecksum\": \"0x%" PRIx64 "\",\n"
        "    \"inputs\": [",
        function_entry,
        reinterpret_cast<uintptr_t>(AriadneCrashDemoBapWorkloadProducer),
        reinterpret_cast<uintptr_t>(AriadneCrashDemoBapWorkloadFault),
        reinterpret_cast<uintptr_t>(AriadneCrashDemoBapWorkloadEnd),
        reinterpret_cast<uintptr_t>(kWorkloadInputs),
        kExpectedWorkloadChecksum);
    if (length < 0 || static_cast<size_t>(length) >= sizeof(addresses)) {
      fprintf(stderr, "Cannot format controlled workload addresses.\n");
      return false;
    }
    workload_fields.assign(addresses, static_cast<size_t>(length));
    for (size_t index = 0; index < 8; ++index) {
      if (index) {
        workload_fields += ", ";
      }
      workload_fields += std::to_string(kWorkloadInputs[index]);
    }
    workload_fields += "]\n  }";
  }
#endif

  // This records the intended access and capture request, not a claim that the
  // dump exists or that the function entry equals the faulting instruction.
  char witness[4096];
  const int length = snprintf(
      witness,
      sizeof(witness),
      "{\n"
      "  \"schema_version\": 1,\n"
      "  \"process_id\": %" PRIu64 ",\n"
      "  \"fault_function_entry\": \"0x%" PRIxPTR "\",\n"
      "  \"expected_data_address\": \"0x0\",\n"
      "  \"expected_access\": \"write\",\n"
      "  \"expected_width_bytes\": 4,\n"
      "  \"expected_store_value\": 5,\n"
      "  \"dump_mode\": \"%s\",\n"
      "  \"integration_profile\": \"%s\",\n"
      "  \"expected_code_extent\": {\"address\": \"0x%" PRIxPTR
      "\", \"size_bytes\": %zu},\n"
      "  \"explicit_code_range_registered\": %s%s\n"
      "}\n",
      process_id,
      function_entry,
      mode.c_str(),
      bap_workload ? kBapIntegrationProfile : kIntegrationProfile,
      function_entry,
      code_extent_bytes,
      kExplicitRangeRegistered,
      workload_fields.c_str());
  if (length < 0 || static_cast<size_t>(length) >= sizeof(witness)) {
    fprintf(stderr, "Cannot format witness JSON.\n");
    return false;
  }

  ScopedFileHandle file(LoggingOpenFileForWrite(
      path, FileWriteMode::kCreateOrFail, FilePermissions::kOwnerOnly));
  if (!file.is_valid() ||
      !LoggingWriteFile(file.get(), witness, static_cast<size_t>(length))) {
    return false;
  }

#if BUILDFLAG(IS_WIN)
  if (!FlushFileBuffers(file.get())) {
    fprintf(stderr, "Cannot flush witness JSON.\n");
    return false;
  }
#else
  int result;
  do {
    result = fsync(file.get());
  } while (result < 0 && errno == EINTR);
  if (result < 0) {
    perror("Cannot flush witness JSON");
    return false;
  }
#endif
  return true;
}

int CrashDemoMain(int argc, base::FilePath::CharType* argv[]) {
  if (argc < 4 || argc > 6) {
    fprintf(stderr,
            "Usage: ariadne_crash_demo HANDLER NEW_DATABASE WITNESS_JSON "
            "[partial|full] [null-write|bap-workload]\n"
            "The database and witness must not already exist. This demo "
            "deliberately crashes its own process after setup.\n");
    return EXIT_FAILURE;
  }

  const base::FilePath::StringType requested_mode =
      argc >= 5 ? argv[4] : FILE_PATH_LITERAL("partial");
  std::string mode;
  if (requested_mode == FILE_PATH_LITERAL("partial")) {
    mode = "partial";
  } else if (requested_mode == FILE_PATH_LITERAL("full")) {
#if BUILDFLAG(IS_WIN)
    mode = "full";
#else
    fprintf(stderr, "Full dump mode is supported only on Windows.\n");
    return EXIT_FAILURE;
#endif
  } else {
    fprintf(stderr, "Dump mode must be partial or full.\n");
    return EXIT_FAILURE;
  }

  const base::FilePath::StringType requested_profile =
      argc == 6 ? argv[5] : FILE_PATH_LITERAL("null-write");
  const bool bap_workload =
      requested_profile == FILE_PATH_LITERAL("bap-workload");
  if (!bap_workload && requested_profile != FILE_PATH_LITERAL("null-write")) {
    fprintf(stderr, "Profile must be null-write or bap-workload.\n");
    return EXIT_FAILURE;
  }
#if !BUILDFLAG(IS_WIN)
  if (bap_workload) {
    fprintf(stderr, "The bap-workload profile is supported only on Windows.\n");
    return EXIT_FAILURE;
  }
#endif

  const base::FilePath handler_path(argv[1]);
  const base::FilePath database_path(argv[2]);
  const base::FilePath witness_path(argv[3]);
  if (!LoggingCreateDirectory(
          database_path, FilePermissions::kOwnerOnly, false)) {
    fprintf(stderr, "Cannot create a fresh database directory.\n");
    return EXIT_FAILURE;
  }

  std::unique_ptr<CrashReportDatabase> database =
      CrashReportDatabase::Initialize(database_path);
  if (!database || !database->GetSettings()->SetUploadsEnabled(false)) {
    fprintf(stderr, "Cannot initialize the database with uploads disabled.\n");
    return EXIT_FAILURE;
  }

  uintptr_t function_entry = reinterpret_cast<uintptr_t>(&AriadneCrashDemoFault);
#if BUILDFLAG(IS_WIN)
  if (bap_workload) {
    function_entry = reinterpret_cast<uintptr_t>(&AriadneCrashDemoBapWorkload);
  }
#endif
  size_t code_extent_bytes;
  if (!ConfigureCapture(function_entry, bap_workload, &code_extent_bytes)) {
    return EXIT_FAILURE;
  }

  CrashpadClient client;
  const std::map<std::string, std::string> annotations = {
      {"integration_profile",
       bap_workload ? kBapIntegrationProfile : kIntegrationProfile},
      {"dump_mode", mode},
  };
  const std::vector<std::string> arguments = {
      "--no-periodic-tasks", "--dump-mode=" + mode};
  if (!client.StartHandler(handler_path,
                           database_path,
                           base::FilePath(),
                           "",
                           annotations,
                           arguments,
                           false,
                           false)) {
    fprintf(stderr, "Cannot start Crashpad synchronously.\n");
    return EXIT_FAILURE;
  }

#if BUILDFLAG(IS_LINUX)
  // StartHandler may skip its credentials handshake when Yama is unavailable.
  // Confirm readiness before the deliberate fault on that configuration too.
  int handler_socket;
  if (!CrashpadClient::GetHandlerSocket(&handler_socket, nullptr)) {
    fprintf(stderr, "Cannot obtain the Crashpad handler socket.\n");
    return EXIT_FAILURE;
  }
  ExceptionHandlerClient handler_client(handler_socket, true);
  ucred handler_credentials;
  if (!handler_client.GetHandlerCredentials(&handler_credentials)) {
    fprintf(stderr, "Cannot confirm Crashpad handler readiness.\n");
    return EXIT_FAILURE;
  }
#endif

  if (!WriteWitness(
          witness_path, function_entry, code_extent_bytes, mode, bap_workload)) {
    fprintf(stderr, "Cannot persist the witness; exiting normally.\n");
    return EXIT_FAILURE;
  }

#if BUILDFLAG(IS_WIN)
  if (bap_workload) {
    AriadneCrashDemoBapWorkload(kWorkloadInputs, kExpectedWorkloadChecksum);
  } else {
    AriadneCrashDemoFault(nullptr);
  }
#else
  AriadneCrashDemoFault(nullptr);
#endif
  fprintf(stderr, "The expected null write unexpectedly returned.\n");
  return EXIT_FAILURE;
}

}  // namespace
}  // namespace crashpad

#if BUILDFLAG(IS_WIN)
int wmain(int argc, wchar_t* argv[]) {
  return crashpad::CrashDemoMain(argc, argv);
}
#else
int main(int argc, char* argv[]) {
  return crashpad::CrashDemoMain(argc, argv);
}
#endif
