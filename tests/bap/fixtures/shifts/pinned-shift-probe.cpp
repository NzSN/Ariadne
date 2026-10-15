// Concrete tests against the hash-pinned production BAP C API.
// This probe evaluates Word primitives and constant-folded BIL expressions.
// bap.h exposes no Exp.Type.infer entry point: construction/folding must not
// be advertised as direct static-typechecker qualification or an ISA proof.
#include <dlfcn.h>

#include <cstdint>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#define _Bool bool
#include <bap.h>

namespace {
static_assert(BAP_BINOP_ARSHIFT == 9);
static_assert(BAP_BINOP_RSHIFT == 10);
static_assert(BAP_BINOP_LSHIFT == 11);

std::string quote(const std::string& text) {
    std::ostringstream out;
    out << '"';
    constexpr char hex[] = "0123456789abcdef";
    for (unsigned char c : text) {
        if (c == '"' || c == '\\') {
            out << '\\' << static_cast<char>(c);
        } else if (c < 32) {
            out << "\\u00" << hex[c >> 4] << hex[c & 15];
        } else {
            out << static_cast<char>(c);
        }
    }
    out << '"';
    return out.str();
}

template <typename T>
T* checked(T* value, const char* operation) {
    if (!value) {
        const char* error = bap_error_get();
        throw std::runtime_error(std::string(operation) + ": " +
                                 (error ? error : "no BAP diagnostic"));
    }
    return value;
}

struct Objects {
    std::vector<void*> roots;
    template <typename T>
    T* hold(T* value, const char* operation) {
        roots.push_back(checked(value, operation));
        return value;
    }
    ~Objects() {
        for (auto it = roots.rbegin(); it != roots.rend(); ++it) {
            bap_release(*it);
        }
    }
};

std::string word_text(bap_word_t* value) {
    return checked(bap_word_to_string(value), "word_to_string");
}

bap_word_t* make_word(Objects& objects, const std::string& value, int width,
                      bool is_signed) {
    std::string text = value + ":" + std::to_string(width) +
                       (is_signed ? "s" : "u");
    auto* word = objects.hold(bap_word_of_string(text.data()), "word_of_string");
    if (bap_word_bitwidth(word) != width) {
        throw std::runtime_error("BAP did not retain input word width");
    }
    return word;
}

void run(char* program, char* plugin_directory) {
    char* libraries[] = {plugin_directory, nullptr};
    char* required_plugins[] = {nullptr};
    char* initialization_argv[] = {program, nullptr};
    bap_parameters_t parameters{};
    parameters.library = libraries;
    // The pinned header renames the C 'requires' member for C++20 and later.
    parameters.requires_ = required_plugins;
    parameters.argv = initialization_argv;
    if (bap_init2(1, const_cast<const char**>(initialization_argv), &parameters) < 0) {
        throw std::runtime_error(checked(bap_error_get(), "bap_init2"));
    }
    Dl_info library{};
    if (!dladdr(dlsym(RTLD_DEFAULT, "bap_word_lshift"), &library) ||
        !library.dli_fname) {
        throw std::runtime_error("cannot identify loaded BAP library");
    }
    std::cout << "{\"schema\":\"ariadne.bap-shift-probe-ready/v1\","
                 "\"version\":" << quote(checked(bap_version(), "bap_version"))
              << ",\"loaded_library\":" << quote(library.dli_fname)
              << ",\"initialization_argv\":[" << quote(program)
              << "],\"required_plugins\":[],\"static_typing_api_exercised\":false}"
              << std::endl;

    std::string line;
    std::size_t rows = 0;
    while (std::getline(std::cin, line)) {
        if (line.size() > 1024 || ++rows > 8192) {
            throw std::runtime_error("probe input limit");
        }
        std::istringstream input(line);
        std::string name, data_hex, count_hex, extra;
        int op = -1, data_width = 0, count_width = 0;
        int data_signed = -1, count_signed = -1;
        if (!(input >> name >> op >> data_width >> count_width >> data_hex >>
              count_hex >> data_signed >> count_signed) || input >> extra ||
            op < 9 || op > 11 || data_width < 1 || data_width > 256 ||
            count_width < 1 || count_width > 256 || data_signed < 0 ||
            data_signed > 1 || count_signed < 0 || count_signed > 1) {
            throw std::runtime_error("malformed probe row");
        }
        Objects objects;
        auto* data = make_word(objects, data_hex, data_width, data_signed != 0);
        auto* count = make_word(objects, count_hex, count_width, count_signed != 0);
        bap_word_t* raw_result = nullptr;
        if (op == 9) raw_result = bap_word_arshift(data, count);
        if (op == 10) raw_result = bap_word_rshift(data, count);
        if (op == 11) raw_result = bap_word_lshift(data, count);
        auto* result = objects.hold(raw_result, "word shift");

        auto* left = objects.hold(bap_exp_create_int(data), "data expression");
        auto* right = objects.hold(bap_exp_create_int(count), "count expression");
        auto* left_input = objects.hold(bap_exp_value(left), "data expression input value");
        auto* right_input = objects.hold(bap_exp_value(right), "count expression input value");
        auto* expression = objects.hold(
            bap_exp_create_binop(static_cast<bap_binop_t>(op), left, right),
            "mixed-width binary expression");
        const auto constructor_tag = bap_exp_tag(expression);
        bap_word_t* left_word = nullptr;
        bap_word_t* right_word = nullptr;
        bap_word_t* constructor_word = nullptr;
        if (constructor_tag == BAP_EXP_TAG_BINOP) {
            if (bap_exp_binop(expression) != static_cast<bap_binop_t>(op)) {
                throw std::runtime_error("constructor changed the binary operator");
            }
            auto* actual_left = objects.hold(bap_exp_lhs(expression), "expression lhs");
            auto* actual_right = objects.hold(bap_exp_rhs(expression), "expression rhs");
            left_word = objects.hold(bap_exp_value(actual_left), "expression lhs value");
            right_word = objects.hold(bap_exp_value(actual_right), "expression rhs value");
        } else if (constructor_tag == BAP_EXP_TAG_INT) {
            // The pinned API smart constructor may already fold literal inputs.
            // Record that result; it has no remaining operands to inspect and
            // establishes no static type-inference claim.
            constructor_word = objects.hold(bap_exp_value(expression), "constructor-folded value");
        } else {
            throw std::runtime_error("unsupported smart-constructor expression tag");
        }
        auto* folded = objects.hold(bap_exp_fold_consts(expression), "constant fold");
        if (bap_exp_tag(folded) != BAP_EXP_TAG_INT) {
            throw std::runtime_error("constant shift did not fold to an integer");
        }
        auto* folded_word = objects.hold(bap_exp_value(folded), "folded value");
        std::cout << "{\"schema\":\"ariadne.bap-shift-probe-row/v1\",\"name\":"
                  << quote(name) << ",\"op\":" << op
                  << ",\"data_width\":" << bap_word_bitwidth(data)
                  << ",\"count_width\":" << bap_word_bitwidth(count)
                  << ",\"data_word\":" << quote(word_text(data))
                  << ",\"count_word\":" << quote(word_text(count))
                  << ",\"primitive_width\":" << bap_word_bitwidth(result)
                  << ",\"primitive_word\":" << quote(word_text(result))
                  << ",\"input_expression_lhs_width\":" << bap_word_bitwidth(left_input)
                  << ",\"input_expression_rhs_width\":" << bap_word_bitwidth(right_input)
                  << ",\"constructor_expression_tag\":"
                  << quote(constructor_word ? "int" : "binop")
                  << ",\"constructor_operand_widths_observable\":"
                  << (constructor_word ? "false" : "true")
                  << ",\"constructor_lhs_width\":"
                  << (left_word ? std::to_string(bap_word_bitwidth(left_word)) : "null")
                  << ",\"constructor_rhs_width\":"
                  << (right_word ? std::to_string(bap_word_bitwidth(right_word)) : "null")
                  << ",\"constructor_folded_width\":"
                  << (constructor_word ? std::to_string(bap_word_bitwidth(constructor_word)) : "null")
                  << ",\"constructor_folded_word\":"
                  << (constructor_word ? quote(word_text(constructor_word)) : "null")
                  << ",\"folded_width\":" << bap_word_bitwidth(folded_word)
                  << ",\"folded_word\":" << quote(word_text(folded_word))
                  << ",\"static_type_inference_claimed\":false}" << std::endl;
    }
    if (rows == 0 || !std::cin.eof()) {
        throw std::runtime_error("empty or interrupted probe input");
    }
}
}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: pinned-shift-probe BAP_PLUGIN_DIRECTORY\n";
        return 2;
    }
    try {
        run(argv[0], argv[1]);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "pinned-shift-probe: " << error.what() << '\n';
        return 2;
    }
}
