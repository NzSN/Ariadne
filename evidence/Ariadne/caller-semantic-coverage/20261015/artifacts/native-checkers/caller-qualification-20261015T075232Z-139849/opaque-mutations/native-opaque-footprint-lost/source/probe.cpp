// A0 capability probe only. No Ariadne analysis algorithm or replay is run.
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>
#define _Bool bool
#define requires bap_requires
#include <bap.h>
#undef requires

namespace {
struct Handles {
  std::vector<void*> values;
  std::unordered_set<void*> seen;
  template <typename T> T* own(T* value) {
    if (!value) throw std::runtime_error("BAP returned a null handle");
    if (seen.insert(value).second) values.push_back(value);
    return value;
  }
  ~Handles() {
    for (auto i = values.rbegin(); i != values.rend(); ++i) bap_release(*i);
  }
};
bool any_tid(bap_tid_t*, void*) { return true; }
bool any_edge(bap_tidgraph_edge_t*, void*) { return true; }
void require(bool value, const char* reason) {
  if (!value) throw std::runtime_error(reason);
}
int nodes(Handles& h, bap_tidgraph_t* graph) {
  return bap_tid_seq_count(h.own(bap_tidgraph_nodes(graph)), any_tid, nullptr);
}
int edges(Handles& h, bap_tidgraph_t* graph) {
  return bap_tidgraph_edge_seq_count(h.own(bap_tidgraph_edges(graph)), any_edge, nullptr);
}
void run(const char* plugins) {
  char* paths[] = {const_cast<char*>(plugins), nullptr};
  char* required[] = {const_cast<char*>("llvm"), const_cast<char*>("x86"), nullptr};
  const char* args[] = {"ariadne-bap-core-probe", "--x86-lifter=legacy", nullptr};
  bap_parameters_t parameters{};
  parameters.library = paths;
  parameters.bap_requires = required;
  parameters.argv = const_cast<char**>(args);
  if (bap_init2(2, args, &parameters) < 0) throw std::runtime_error(bap_error_get());
  require(std::string(bap_version()) == "2.5.0-alpha", "unexpected BAP runtime");
  Handles h;
  auto* first = h.own(bap_tid_create());
  auto* second = h.own(bap_tid_create());
  require(!bap_tid_equal(first, second), "distinct terms share an identity");
  auto* original = h.own(bap_blk_create(first));
  auto* original_term = reinterpret_cast<bap_term_t*>(original);
  require(!bap_term_has_address(original_term), "new block has an invented address");
  const uint64_t high_va = UINT64_C(0xfffffffffffffff0);
  int64_t signed_bits;
  std::memcpy(&signed_bits, &high_va, sizeof(high_va));
  auto* word = h.own(bap_word_of_int64(64, signed_bits));
  auto* attributed = h.own(bap_term_set_address(original_term, word));
  auto* observed = h.own(bap_term_get_address(attributed));
  require(static_cast<uint64_t>(bap_word_to_int64(observed)) == high_va,
          "BAP truncated unsigned address attribution");
  require(!bap_term_has_address(original_term), "persistent update changed old term");
  require(bap_tid_equal(h.own(bap_term_tid(attributed)), first), "attribution changed TID");
  auto* twin = h.own(bap_blk_create(second));
  auto* twin_attributed = h.own(bap_term_set_address(reinterpret_cast<bap_term_t*>(twin), word));
  require(!bap_tid_equal(h.own(bap_term_tid(attributed)), h.own(bap_term_tid(twin_attributed))),
          "same VA collapsed distinct BIR terms");
  auto* g0 = h.own(bap_tidgraph_empty());
  auto* g1 = h.own(bap_tidgraph_node_insert(first, g0));
  auto* g2 = h.own(bap_tidgraph_node_insert(second, g1));
  require(nodes(h, g0) == 0 && nodes(h, g1) == 1 && nodes(h, g2) == 2,
          "BAP graph versions did not retain separate state");
  auto* label1 = h.own(bap_tid_create());
  auto* label2 = h.own(bap_tid_create());
  auto* edge1 = h.own(bap_tidgraph_edge_create(first, second, label1));
  auto* edge2 = h.own(bap_tidgraph_edge_create(first, second, label2));
  auto* g3 = h.own(bap_tidgraph_edge_insert(edge1, g2));
  auto* g4 = h.own(bap_tidgraph_edge_insert(edge2, g3));
  require(edges(h, g2) == 0 && edges(h, g3) == 1, "unexpected graph edge insertion");
  const int parallel = edges(h, g4);
  require(parallel == 1 || parallel == 2, "unexpected parallel-edge observation");
  require(nodes(h, g4) == 2 && edges(h, g4) == parallel, "observe mutated graph");
  auto* empty_again = h.own(bap_tidgraph_empty());
  require(nodes(h, empty_again) == 0 && edges(h, empty_again) == 0,
          "fresh graph inherited old state");
  std::cout << "{\"schema\":\"ariadne.bap-core-capabilities/v1\","
            << "\"passed\":true,\"runtime\":\"2.5.0-alpha\","
            << "\"stateOwner\":\"BAP OCaml term/graph objects\","
            << "\"unsignedAddressRoundtrip\":true,\"persistentTermUpdate\":true,"
            << "\"sameVaDistinctTerms\":true,\"graphNodeCounts\":[0,1,2],"
            << "\"parallelEdgeCount\":" << parallel << ","
            << "\"readOnlyObservation\":true,\"freshGraphEmpty\":true,"
            << "\"customOcamlPassExercised\":false,\"analysisAlgorithmsExercised\":false,"
            << "\"scope\":\"A0 runtime facilities only; no migrated solver or model conformance\"}\n";
}
}
int main(int argc, char** argv) {
  try {
    if (argc != 2) throw std::runtime_error("usage: ariadne-bap-core-probe PLUGIN_DIR");
    run(argv[1]);
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
