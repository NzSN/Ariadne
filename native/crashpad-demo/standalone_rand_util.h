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

#ifndef ARIADNE_STANDALONE_BASE_RAND_UTIL_H_
#define ARIADNE_STANDALONE_BASE_RAND_UTIL_H_

#include "third_party/mini_chromium/mini_chromium/base/rand_util.h"

namespace base {

// Pinned mini_chromium's RandInt already includes both endpoints; the fork
// uses Chromium's newer explicit name for the same operation.
inline int RandIntInclusive(int min, int max) {
  return RandInt(min, max);
}

}  // namespace base

#endif  // ARIADNE_STANDALONE_BASE_RAND_UTIL_H_
