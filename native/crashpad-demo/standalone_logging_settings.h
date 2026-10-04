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

#ifndef ARIADNE_STANDALONE_BASE_LOGGING_SETTINGS_H_
#define ARIADNE_STANDALONE_BASE_LOGGING_SETTINGS_H_

// The fork includes Chromium's split header. Its pinned standalone
// mini_chromium already declares the Windows/Linux API in base/logging.h.
// This forwarding header is only installed in the isolated standalone build.
#include "base/logging.h"

#endif  // ARIADNE_STANDALONE_BASE_LOGGING_SETTINGS_H_
