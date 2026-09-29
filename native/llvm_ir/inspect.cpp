#include "llvm/Config/llvm-config.h"
#include "llvm/IR/CFG.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Verifier.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/FormatVariadic.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"

#include <map>
#include <string>
#include <vector>

using namespace llvm;

static StringRef terminator_kind(const Instruction &inst) {
  if (isa<BranchInst>(inst)) return "br";
  if (isa<SwitchInst>(inst)) return "switch";
  if (isa<IndirectBrInst>(inst)) return "indirectbr";
  if (isa<InvokeInst>(inst)) return "invoke";
  if (isa<CallBrInst>(inst)) return "callbr";
  if (isa<ReturnInst>(inst)) return "ret";
  if (isa<ResumeInst>(inst)) return "resume";
  if (isa<UnreachableInst>(inst)) return "unreachable";
  if (isa<CatchSwitchInst>(inst)) return "catchswitch";
  if (isa<CatchReturnInst>(inst)) return "catchret";
  if (isa<CleanupReturnInst>(inst)) return "cleanupret";
  return "unsupported";
}

static StringRef successor_kind(const Instruction &inst, unsigned n) {
  if (auto *branch = dyn_cast<BranchInst>(&inst))
    return branch->isConditional() ? (n == 0 ? "true" : "false") : "next";
  if (isa<SwitchInst>(inst)) return n == 0 ? "default" : "case";
  if (isa<IndirectBrInst>(inst)) return "indirect";
  if (isa<InvokeInst>(inst)) return n == 0 ? "normal" : "unwind";
  if (isa<CallBrInst>(inst)) return n == 0 ? "fallthrough" : "indirect";
  if (isa<CatchSwitchInst>(inst)) return "catch";
  if (isa<CatchReturnInst>(inst)) return "catch";
  if (isa<CleanupReturnInst>(inst)) return "cleanup";
  return "next";
}

static StringRef value_kind(const Value &value) {
  if (isa<Instruction>(value)) return "instruction";
  if (isa<Argument>(value)) return "argument";
  if (isa<GlobalValue>(value)) return "global";
  if (isa<Constant>(value)) return "constant";
  return "external";
}

int main(int argc, char **argv) {
  if (argc == 2 && StringRef(argv[1]) == "--version") {
    outs() << "Ariadne native LLVM IR " << LLVM_VERSION_STRING << "\n";
    return 0;
  }
  if (argc != 3) {
    errs() << "usage: ariadne-llvm-ir FILE.ll|FILE.bc FUNCTION\n";
    return 2;
  }
  LLVMContext context;
  SMDiagnostic diagnostic;
  auto module = parseIRFile(argv[1], diagnostic, context);
  if (!module) {
    diagnostic.print("ariadne-llvm-ir", errs());
    return 2;
  }
  if (verifyModule(*module, &errs())) {
    errs() << "LLVM verifier rejected input\n";
    return 2;
  }
  Function *function = module->getFunction(argv[2]);
  if (!function || function->isDeclaration() || function->empty()) {
    errs() << "missing or declaration-only function: " << argv[2] << "\n";
    return 2;
  }

  std::map<const BasicBlock *, std::string> block_ids;
  std::map<const Instruction *, std::string> instruction_ids;
  std::vector<const Instruction *> instructions;
  unsigned block_number = 0;
  unsigned instruction_number = 0;
  for (const BasicBlock &block : *function) {
    block_ids[&block] = "b" + std::to_string(block_number++);
    for (const Instruction &inst : block) {
      instruction_ids[&inst] = "i" + std::to_string(instruction_number++);
      instructions.push_back(&inst);
    }
  }
  if (instructions.empty()) return 2;
  if (instructions.size() > 4096) {
    errs() << "IR instruction limit exceeded\n";
    return 2;
  }
  std::map<const Value *, std::string> value_ids;
  std::vector<const Value *> values;
  auto value_id = [&](const Value *value) -> std::string {
    auto found = value_ids.find(value);
    if (found != value_ids.end()) return found->second;
    std::string id = "v" + std::to_string(values.size());
    value_ids.emplace(value, id);
    values.push_back(value);
    return id;
  };
  std::vector<const Instruction *> memory_writers;
  size_t memory_readers = 0;
  for (const Instruction *inst : instructions)
    if (inst->mayWriteToMemory()) memory_writers.push_back(inst);
  for (const Instruction *inst : instructions)
    if (inst->mayReadFromMemory()) ++memory_readers;
  if (memory_readers * memory_writers.size() > 100000) {
    errs() << "IR memory predecessor relation limit exceeded\n";
    return 2;
  }

  json::Array blocks;
  for (const BasicBlock &block : *function) {
    const Instruction *term = block.getTerminator();
    StringRef kind = terminator_kind(*term);
    if (kind == "unsupported") {
      errs() << "unsupported terminator in " << block_ids[&block] << "\n";
      return 2;
    }
    json::Array successors;
    for (unsigned n = 0; n < term->getNumSuccessors(); ++n) {
      successors.push_back(json::Object{
          {"dst", block_ids[term->getSuccessor(n)]},
          {"kind", successor_kind(*term, n).str()}});
    }
    blocks.push_back(json::Object{
        {"id", block_ids[&block]}, {"terminator", instruction_ids[term]},
        {"kind", kind.str()}, {"successors", std::move(successors)}});
  }

  json::Array rows;
  json::Array phi_nodes;
  json::Array call_sites;
  json::Array callees;
  json::Array complete_calls;
  json::Array obligations;
  std::map<std::string, bool> seen_callees;
  for (const BasicBlock &block : *function) {
    unsigned index = 0;
    for (const Instruction &inst : block) {
      json::Array uses;
      for (const Use &operand : inst.operands()) {
        if (!isa<BasicBlock>(operand.get()))
          uses.push_back(value_id(operand.get()));
      }
      json::Array phi;
      if (auto *node = dyn_cast<PHINode>(&inst)) {
        phi_nodes.push_back(instruction_ids[&inst]);
        for (unsigned n = 0; n < node->getNumIncomingValues(); ++n) {
          phi.push_back(json::Object{
              {"pred", block_ids[node->getIncomingBlock(n)]},
              {"value", value_id(node->getIncomingValue(n))}});
        }
      }
      json::Array memory_preds;
      if (inst.mayReadFromMemory()) {
        for (const Instruction *writer : memory_writers)
          if (writer != &inst) memory_preds.push_back(instruction_ids[writer]);
        obligations.push_back(json::Object{
            {"site", instruction_ids[&inst]},
            {"reason", "unknown-memory-alias"}});
      }
      json::Array targets;
      if (auto *call = dyn_cast<CallBase>(&inst)) {
        call_sites.push_back(instruction_ids[&inst]);
        if (Function *callee = call->getCalledFunction()) {
          std::string name = callee->getName().str();
          targets.push_back(name);
          if (!seen_callees[name]) {
            callees.push_back(name);
            seen_callees[name] = true;
          }
          complete_calls.push_back(instruction_ids[&inst]);
        }
      }
      rows.push_back(json::Object{
          {"id", instruction_ids[&inst]}, {"block", block_ids[&block]},
          {"index", index++}, {"uses", std::move(uses)},
          {"phi_incoming", std::move(phi)},
          {"memory_preds", std::move(memory_preds)},
          {"call_targets", std::move(targets)}});
    }
  }
  json::Array value_rows;
  for (const Value *value : values) {
    auto *inst = dyn_cast<Instruction>(value);
    auto found = inst ? instruction_ids.find(inst) : instruction_ids.end();
    StringRef kind = found == instruction_ids.end() ?
        (inst ? StringRef("external") : value_kind(*value)) : StringRef("instruction");
    value_rows.push_back(json::Object{
        {"id", value_ids[value]}, {"kind", kind.str()},
        {"def_site", found == instruction_ids.end() ? instruction_ids[instructions[0]] : found->second}});
  }
  std::string module_id = module->getModuleIdentifier();
  if (module_id.empty()) module_id = "<module>";
  json::Object root{
      {"schema", "ariadne-native-ir-v1"}, {"llvm_version", LLVM_VERSION_STRING},
      {"module_id", module_id}, {"function_id", function->getName().str()},
      {"entry_block", block_ids[&function->getEntryBlock()]},
      {"verified_ir", true}, {"blocks", std::move(blocks)},
      {"instructions", std::move(rows)}, {"values", std::move(value_rows)},
      {"phi_nodes", std::move(phi_nodes)}, {"call_sites", std::move(call_sites)},
      {"callees", std::move(callees)}, {"complete_calls", std::move(complete_calls)},
      {"obligations", std::move(obligations)}};
  outs() << formatv("{0:2}", json::Value(std::move(root))) << "\n";
  return 0;
}
