#include <llvm/ADT/ArrayRef.h>
#include <llvm/ADT/StringRef.h>
#include <llvm/TargetParser/Triple.h>
#include <llvm/Config/llvm-config.h>
#include <llvm/MC/MCAsmInfo.h>
#include <llvm/MC/MCContext.h>
#include <llvm/MC/MCDisassembler/MCDisassembler.h>
#include <llvm/MC/MCInst.h>
#include <llvm/MC/MCInstrAnalysis.h>
#include <llvm/MC/MCInstrDesc.h>
#include <llvm/MC/MCInstrInfo.h>
#include <llvm/MC/MCRegisterInfo.h>
#include <llvm/MC/MCSubtargetInfo.h>
#include <llvm/MC/TargetRegistry.h>
#include <llvm/Support/TargetSelect.h>
#include <llvm/Support/raw_ostream.h>

#include <cstdint>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#if LLVM_VERSION_MAJOR != 20 || LLVM_VERSION_MINOR != 1 || LLVM_VERSION_PATCH != 2
#error Ariadne LLVM MC adapter requires LLVM 20.1.2
#endif

namespace {

bool parse_u64(const std::string &text, uint64_t &value) {
  if (text.empty() || text.front() == '-') return false;
  std::size_t consumed = 0;
  try {
    value = std::stoull(text, &consumed, 10);
  } catch (...) {
    return false;
  }
  return consumed == text.size();
}

bool parse_hex(const std::string &text, std::vector<uint8_t> &bytes) {
  if (text.empty() || text.size() > 30 || text.size() % 2 != 0) return false;
  bytes.clear();
  for (std::size_t i = 0; i < text.size(); i += 2) {
    auto digit = [](char c) -> int {
      if (c >= '0' && c <= '9') return c - '0';
      if (c >= 'a' && c <= 'f') return c - 'a' + 10;
      if (c >= 'A' && c <= 'F') return c - 'A' + 10;
      return -1;
    };
    const int high = digit(text[i]);
    const int low = digit(text[i + 1]);
    if (high < 0 || low < 0) return false;
    bytes.push_back(static_cast<uint8_t>((high << 4) | low));
  }
  return true;
}

struct Decoder {
  llvm::Triple triple{"x86_64-pc-windows-msvc"};
  std::unique_ptr<llvm::MCRegisterInfo> registers;
  std::unique_ptr<llvm::MCAsmInfo> assembly;
  std::unique_ptr<llvm::MCSubtargetInfo> subtarget;
  std::unique_ptr<llvm::MCInstrInfo> instructions;
  std::unique_ptr<llvm::MCInstrAnalysis> analysis;
  std::unique_ptr<llvm::MCContext> context;
  std::unique_ptr<llvm::MCDisassembler> disassembler;

  bool initialize() {
    LLVMInitializeX86TargetInfo();
    LLVMInitializeX86TargetMC();
    LLVMInitializeX86Disassembler();
    std::string error;
    const llvm::Target *target = llvm::TargetRegistry::lookupTarget(triple.str(), error);
    if (!target) {
      std::cerr << "LLVM target: " << error << '\n';
      return false;
    }
    registers.reset(target->createMCRegInfo(triple.str()));
    subtarget.reset(target->createMCSubtargetInfo(triple.str(), "generic", ""));
    instructions.reset(target->createMCInstrInfo());
    if (!registers || !subtarget || !instructions) return false;
    llvm::MCTargetOptions options;
    assembly.reset(target->createMCAsmInfo(*registers, triple.str(), options));
    analysis.reset(target->createMCInstrAnalysis(instructions.get()));
    if (!assembly || !analysis) return false;
    context = std::make_unique<llvm::MCContext>(triple, assembly.get(), registers.get(),
                                                subtarget.get());
    disassembler.reset(target->createMCDisassembler(*subtarget, *context));
    return static_cast<bool>(disassembler);
  }

  void decode(uint64_t address, const std::vector<uint8_t> &bytes) {
    llvm::MCInst instruction;
    uint64_t size = 0;
    std::string comments;
    llvm::raw_string_ostream comment_stream(comments);
    analysis->resetState();
    const auto status = disassembler->getInstruction(
        instruction, size, llvm::ArrayRef<uint8_t>(bytes), address, comment_stream);
    if (status != llvm::MCDisassembler::Success || size == 0 || size > bytes.size()) {
      std::cout << address << " invalid 0 - -\n";
      return;
    }
    if (address > std::numeric_limits<uint64_t>::max() - size) {
      std::cout << address << " unsupported " << size << " - -\n";
      return;
    }
    analysis->updateState(instruction, address);
    // LLVM's generic control-flow flags do not mark all system transitions or
    // transactional aborts. These cannot be given an ordinary fallthrough.
    const llvm::StringRef name = instructions->getName(instruction.getOpcode());
    const bool opaque_control =
        name.starts_with("INT") || name.starts_with("IRET") ||
        name.starts_with("LRET") || name.starts_with("LCALL") ||
        name.starts_with("LJMP") || name.starts_with("SYS") ||
        name.starts_with("VMCALL") || name.starts_with("VMMCALL") ||
        name.starts_with("VMLAUNCH") || name.starts_with("VMRESUME") ||
        name.starts_with("VMRUN") || name.starts_with("XBEGIN") ||
        name.starts_with("XEND") || name.starts_with("XABORT") ||
        name.starts_with("RSM");
    if (opaque_control) {
      std::cout << address << " unsupported " << size << " - -\n";
      return;
    }
    uint64_t target = 0;
    const bool direct_target = analysis->evaluateBranch(instruction, address, size, target);
    std::string kind;
    if (analysis->isReturn(instruction)) {
      kind = "return";
    } else if (analysis->isCall(instruction)) {
      kind = "call";
    } else if (analysis->isConditionalBranch(instruction)) {
      kind = direct_target ? "conditional" : "unsupported";
    } else if (analysis->isIndirectBranch(instruction)) {
      kind = "indirect";
    } else if (analysis->isBranch(instruction)) {
      kind = direct_target ? "jump" : "indirect";
    } else if (instructions->get(instruction.getOpcode()).isTrap()) {
      kind = "stop";
    } else if (analysis->mayAffectControlFlow(instruction, *registers) ||
               analysis->isTerminator(instruction)) {
      kind = "unsupported";
    } else {
      kind = "ordinary";
    }
    if (kind == "unsupported") {
      std::cout << address << " unsupported " << size << " - -\n";
      return;
    }
    std::cout << address << " ok " << size << ' ' << kind << ' ';
    if ((kind == "conditional" || kind == "jump" || kind == "call") && direct_target)
      std::cout << target;
    else
      std::cout << '-';
    std::cout << '\n';
  }
};

}  // namespace

int main(int argc, char **argv) {
  if (argc == 2 && std::string(argv[1]) == "--version") {
    std::cout << "ariadne-llvm-mc 20.1.2\n";
    return 0;
  }
  if (argc != 1) {
    std::cerr << "usage: ariadne-llvm-mc [--version]\n";
    return 2;
  }
  Decoder decoder;
  if (!decoder.initialize()) {
    std::cerr << "LLVM MC initialization failed\n";
    return 2;
  }
  std::string line;
  while (std::getline(std::cin, line)) {
    std::istringstream stream(line);
    std::string address_text, hex_text, extra;
    uint64_t address = 0;
    std::vector<uint8_t> bytes;
    if (!(stream >> address_text >> hex_text) || stream >> extra ||
        !parse_u64(address_text, address) || !parse_hex(hex_text, bytes)) {
      std::cerr << "invalid decoder input line\n";
      return 2;
    }
    decoder.decode(address, bytes);
  }
  return std::cin.bad() ? 2 : 0;
}
