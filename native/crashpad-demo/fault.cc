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

#include <stdint.h>

// Keep this ordinary scalar store in a separate translation unit. The caller
// supplies nullptr only after Crashpad startup and witness persistence succeed.
// Disassemble the built executable to establish the compiler-produced fault
// instruction and its address; the function entry need not be the fault site.
extern "C"
#if defined(_MSC_VER)
    __declspec(noinline)
#else
    __attribute__((noinline))
#endif
    void AriadneCrashDemoFault(volatile uint32_t* destination) {
  *destination = 5;
}
