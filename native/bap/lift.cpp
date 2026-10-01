#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <limits>
#define _Bool bool
#define requires bap_requires
#include <bap.h>
#undef requires

namespace {
constexpr int max_nodes=8192;
int nodes=0;
std::string quote(const std::string& s) {
  std::ostringstream out;out<<'"';
  const char hex[]="0123456789abcdef";
  for(unsigned char c:s) { if(c=='"'||c=='\\')out<<'\\'<<char(c); else if(c<32)out<<"\\u00"<<hex[c>>4]<<hex[c&15]; else out<<char(c); }
  out<<'"';return out.str();
}
void budget(int depth) { if(depth>64 || ++nodes>max_nodes)throw std::runtime_error("BIL AST budget exceeded"); }
std::string variable(bap_var_t* v) {
  if(!v)throw std::runtime_error("missing BIL variable");
  auto *typ=bap_var_type(v);auto tag=bap_type_tag(typ);
  int width=tag==BAP_TYPE_TAG_IMM?bap_type_imm_size(typ):0;
  return "{\"name\":"+quote(bap_var_name(v))+",\"index\":"+std::to_string(bap_var_index(v))+",\"virtual\":"+(bap_var_is_virtual(v)?"true":"false")+",\"width\":"+std::to_string(width)+",\"type\":"+quote(tag==BAP_TYPE_TAG_IMM?"imm":tag==BAP_TYPE_TAG_MEM?"mem":"unknown")+"}";
}
std::string expr(bap_exp_t*,int);
std::string statements(bap_stmt_seq_t*,int);
std::string expr(bap_exp_t* e,int depth) {
  budget(depth);if(!e)throw std::runtime_error("missing BIL expression");
  auto child=[&](bap_exp_t* p){return expr(p,depth+1);};
  switch(bap_exp_tag(e)) {
    case BAP_EXP_TAG_VAR:return "{\"kind\":\"var\",\"var\":"+variable(bap_exp_var(e))+"}";
    case BAP_EXP_TAG_INT: {
      auto *v=bap_exp_value(e);std::string value=bap_word_to_string(v);return "{\"kind\":\"int\",\"value\":"+quote(value)+"}";
    }
    case BAP_EXP_TAG_UNKNOWN:return "{\"kind\":\"unknown\",\"reason\":"+quote(bap_exp_unknown_msg(e))+"}";
    case BAP_EXP_TAG_LOAD:return "{\"kind\":\"load\",\"width\":"+std::to_string(bap_exp_size(e))+",\"mem\":"+child(bap_exp_mem(e))+",\"addr\":"+child(bap_exp_addr(e))+"}";
    case BAP_EXP_TAG_STORE:return "{\"kind\":\"store\",\"width\":"+std::to_string(bap_exp_size(e))+",\"mem\":"+child(bap_exp_mem(e))+",\"addr\":"+child(bap_exp_addr(e))+",\"value\":"+child(bap_exp_rhs(e))+"}";
    case BAP_EXP_TAG_BINOP:return "{\"kind\":\"binop\",\"op\":"+std::to_string(bap_exp_binop(e))+",\"lhs\":"+child(bap_exp_lhs(e))+",\"rhs\":"+child(bap_exp_rhs(e))+"}";
    case BAP_EXP_TAG_UNOP:return "{\"kind\":\"unop\",\"op\":"+std::to_string(bap_exp_unop(e))+",\"arg\":"+child(bap_exp_exp(e))+"}";
    case BAP_EXP_TAG_CAST:return "{\"kind\":\"cast\",\"op\":"+std::to_string(bap_exp_cast(e))+",\"width\":"+std::to_string(bap_exp_cast_size(e))+",\"arg\":"+child(bap_exp_exp(e))+"}";
    // These two accessors are reversed in the pinned packaged API; preserve
    // their measured meaning rather than normalizing an invalid range.
    case BAP_EXP_TAG_EXTRACT:return "{\"kind\":\"extract\",\"hi\":"+std::to_string(bap_exp_extract_lobit(e))+",\"lo\":"+std::to_string(bap_exp_extract_hibit(e))+",\"arg\":"+child(bap_exp_exp(e))+"}";
    case BAP_EXP_TAG_CONCAT:return "{\"kind\":\"concat\",\"lhs\":"+child(bap_exp_lhs(e))+",\"rhs\":"+child(bap_exp_rhs(e))+"}";
    case BAP_EXP_TAG_ITE:return "{\"kind\":\"ite\",\"condition\":"+child(bap_exp_exp(e))+",\"yes\":"+child(bap_exp_lhs(e))+",\"no\":"+child(bap_exp_rhs(e))+"}";
    case BAP_EXP_TAG_LET:return "{\"kind\":\"let\",\"var\":"+variable(bap_exp_var(e))+",\"value\":"+child(bap_exp_rhs(e))+",\"body\":"+child(bap_exp_exp(e))+"}";
    default:return "{\"kind\":\"unsupported\"}";
  }
}
std::string statement(bap_stmt_t* s,int depth) {
  budget(depth);if(!s)throw std::runtime_error("missing BIL statement");
  switch(bap_stmt_tag(s)) {
    case BAP_STMT_TAG_MOVE:return "{\"kind\":\"move\",\"var\":"+variable(bap_stmt_var(s))+",\"value\":"+expr(bap_stmt_exp(s),depth+1)+"}";
    case BAP_STMT_TAG_JMP:return "{\"kind\":\"jump\",\"target\":"+expr(bap_stmt_jmp(s),depth+1)+"}";
    case BAP_STMT_TAG_IF:return "{\"kind\":\"if\",\"condition\":"+expr(bap_stmt_exp(s),depth+1)+",\"yes\":"+statements(bap_stmt_true_stmts(s),depth+1)+",\"no\":"+statements(bap_stmt_false_stmts(s),depth+1)+"}";
    case BAP_STMT_TAG_WHILE:return "{\"kind\":\"while\",\"condition\":"+expr(bap_stmt_exp(s),depth+1)+",\"body\":"+statements(bap_stmt_stmts(s),depth+1)+"}";
    case BAP_STMT_TAG_CPUEXN:return "{\"kind\":\"exception\",\"number\":"+std::to_string(bap_stmt_cpuexn(s))+"}";
    case BAP_STMT_TAG_SPECIAL:return "{\"kind\":\"special\"}";
    default:return "{\"kind\":\"unsupported\"}";
  }
}
std::string statements(bap_stmt_seq_t* seq,int depth) {
  if(!seq)throw std::runtime_error("missing BIL statement sequence");
  std::string out="[";auto *it=bap_stmt_seq_iterator_create(seq);bool first=true;
  while(bap_stmt_seq_iterator_has_next(it)) {auto *s=bap_stmt_seq_iterator_next(it);if(!first)out+=",";first=false;out+=statement(s,depth+1);bap_release(s);}
  bap_release(it);return out+"]";
}
uint64_t parse_va(const std::string& text) {
  if(text.size()!=18 || text.substr(0,2)!="0x")throw std::runtime_error("VA requires full-width hex");
  for(auto c:text.substr(2))if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))throw std::runtime_error("noncanonical VA");
  return std::stoull(text.substr(2),nullptr,16);
}
std::vector<char> bytes(const std::string& hex) {
  if(hex.empty()||hex.size()>30||hex.size()%2)throw std::runtime_error("invalid prefix");
  std::vector<char> out;
  for(size_t n=0;n<hex.size();n+=2){auto digit=[](char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("noncanonical bytes");};out.push_back(char((digit(hex[n])<<4)|digit(hex[n+1])));}
  return out;
}
bool read_line(std::string& line,size_t limit) {
  line.clear();char c;
  while(std::cin.get(c)) {
    if(c=='\n')return true;
    if(line.size()>=limit)throw std::runtime_error("request line too long");
    line+=c;
  }
  if(!line.empty())throw std::runtime_error("unterminated request line");
  return false;
}
void run(const char* plugin_dir) {
  std::string header;if(!read_line(header,256))throw std::runtime_error("missing header");
  std::istringstream h(header);std::string schema,target,snapshot,extra;int version;
  if(!(h>>schema>>version>>target>>snapshot)||h>>extra||schema!="ARIADNE-BAP-LIFT"||version!=1||snapshot.size()!=64||(target!="windows-amd64"&&target!="linux-amd64"))throw std::runtime_error("invalid stream header");
  for(char c:snapshot)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))throw std::runtime_error("invalid snapshot token");
  char *libraries[]={const_cast<char*>(plugin_dir),nullptr};char *required_plugins[]={const_cast<char*>("llvm"),const_cast<char*>("x86"),nullptr};
  char *args[]={const_cast<char*>("ariadne-bap-lift"),const_cast<char*>("--x86-lifter=legacy"),nullptr};
  bap_parameters_t params{};params.library=libraries;params.bap_requires=required_plugins;params.argv=args;
  if(bap_init2(2,const_cast<const char**>(args),&params)<0)throw std::runtime_error(bap_error_get());
  if(std::string(bap_version())!="2.5.0-alpha")throw std::runtime_error("unexpected BAP library version");
  auto *decoder=bap_disasm_basic_create(BAP_ARCH_X86_64);if(!decoder)throw std::runtime_error(bap_error_get());
  std::cout<<"{\"schema\":\"ariadne.bap-ready/v1\",\"snapshot\":"<<quote(snapshot)<<",\"target\":"<<quote(target)<<",\"version\":\"2.5.0-alpha\",\"lifter\":\"legacy\"}"<<std::endl;
  std::string line;unsigned expected_batch=0,total=0;
  while(read_line(line,100)) {
    if(line.size()>100)throw std::runtime_error("batch header too long");
    std::istringstream b(line);std::string tag;unsigned id,count;
    if(!(b>>tag>>id>>count)||b>>extra||tag!="batch"||id!=expected_batch++||count==0||count>256||total+count>8192)throw std::runtime_error("invalid batch");
    total+=count;uint64_t previous=0;bool first=true;
    for(unsigned n=0;n<count;n++) {
      if(!read_line(line,80))throw std::runtime_error("missing row");
      std::istringstream row(line);std::string address,prefix;
      if(!(row>>address>>prefix)||row>>extra)throw std::runtime_error("invalid row");
      uint64_t va=parse_va(address);if(!first&&va<=previous)throw std::runtime_error("unordered/duplicate VA");first=false;previous=va;
      auto data=bytes(prefix);if(va>std::numeric_limits<uint64_t>::max()-data.size())throw std::runtime_error("address overflow");
      auto *code=bap_disasm_basic_next(decoder,data.data(),static_cast<int>(data.size()),static_cast<int64_t>(va));
      std::string common="{\"schema\":\"ariadne.bap-site/v1\",\"batch\":"+std::to_string(id)+",\"snapshot\":"+quote(snapshot)+",\"va\":"+quote(address);
      if(!code) {std::cout<<common<<",\"status\":\"invalid\",\"length\":0,\"bytes\":\"\",\"opcode\":null,\"properties\":null,\"bil\":[]}"<<std::endl;continue;}
      auto *insn=bap_code_insn(code);int length=bap_memory_length(bap_code_mem(code));
      if(length<1||length>static_cast<int>(data.size()))throw std::runtime_error("invalid decoded length");
      nodes=0;auto ast=statements(bap_insn_bil(insn),0);
      auto boolean=[](bool v){return v?"true":"false";};
      std::string props="{\"jump\":"+std::string(boolean(bap_insn_is_jump(insn)))+",\"conditional\":"+boolean(bap_insn_is_conditional(insn))+",\"indirect\":"+boolean(bap_insn_is_indirect(insn))+",\"call\":"+boolean(bap_insn_is_call(insn))+",\"return\":"+boolean(bap_insn_is_return(insn))+",\"control\":"+boolean(bap_insn_may_affect_control_flow(insn))+"}";
      std::cout<<common<<",\"status\":\"decoded\",\"length\":"<<length<<",\"bytes\":"<<quote(prefix.substr(0,static_cast<size_t>(length)*2))<<",\"opcode\":"<<quote(bap_insn_name(insn))<<",\"properties\":"<<props<<",\"bil\":"<<ast<<"}"<<std::endl;
      bap_release(insn);bap_release(code);
    }
    std::cout<<"{\"schema\":\"ariadne.bap-batch/v1\",\"batch\":"<<id<<",\"count\":"<<count<<"}"<<std::endl;
  }
  bap_disasm_basic_close(decoder);
}
}
int main(int argc,char**argv) {
  if(argc==2&&std::string(argv[1])=="--version") {std::cout<<"ariadne-bap-lift 1 BAP 2.5.0-alpha x86-legacy\n";return 0;}
  if(argc!=2){std::cerr<<"usage: ariadne-bap-lift PLUGIN_DIR\n";return 2;}
  try {run(argv[1]);return 0;}catch(const std::exception&e){std::cerr<<"ariadne-bap-lift: "<<e.what()<<'\n';return 2;}
}
