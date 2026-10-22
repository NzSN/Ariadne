(* Narrow opt-in producer protocol. The BIL comes from patched upstream BAP. *)
open Core_kernel[@@warning "-D"]
open Bap.Std

let str s = `String s
let obj fields = `Assoc fields
let canonical_hex s n = String.length s = n && String.for_all s ~f:(function
    | '0'..'9' | 'a'..'f' -> true | _ -> false)

let variable v =
  let width = match Var.typ v with Type.Imm n -> n | _ -> failwith "non-scalar flag" in
  obj ["name", str (Var.name v); "index", `Int (Var.index v);
       "virtual", `Bool (Var.is_virtual v); "width", `Int width; "type", str "imm"]

let rec expression = function
  | Bil.Int w -> obj ["kind", str "int"; "value", str (Word.to_string w)]
  | Bil.Var v -> obj ["kind", str "var"; "var", variable v]
  | Bil.UnOp (Bil.NOT, x) -> obj ["kind", str "unop"; "op", `Int 0; "arg", expression x]
  | _ -> failwith "producer expression outside four-flag runtime scope"

let statement = function
  | Bil.Move (v, e) -> obj ["kind", str "move"; "var", variable v; "value", expression e]
  | _ -> failwith "producer statement outside four-flag runtime scope"

let () =
  match Array.to_list Sys.argv with
  | [_; target; snapshot; va; code]
    when List.mem ["windows-amd64"; "linux-amd64"] target ~equal:String.equal
         && canonical_hex snapshot 64 && String.is_prefix va ~prefix:"0x"
         && canonical_hex (String.drop_prefix va 2) 16
         && List.mem ["f5"; "f8"; "f9"; "fd"] code ~equal:String.equal ->
    let address = Word.of_string (va ^ ":64") in
    let bytes = String.of_char (Char.of_int_exn (Int.of_string ("0x" ^ code))) in
    let memory = Or_error.ok_exn (Memory.create LittleEndian address (Bigstring.of_string bytes)) in
    let bil = X86_lifter.disasm_instr X86_types.X8664 memory address in
    (match Type.check bil with Ok () -> () | Error _ -> failwith "ill-typed producer BIL");
    let _, _, _, next = X86_disasm.parse_instr X86_types.X8664 memory address in
    let length = Or_error.ok_exn (Word.to_int Word.(next - address)) in
    if length <> 1 || List.length bil <> 1 then failwith "producer extent/statement scope";
    let response = obj ["schema", str "ariadne.bap-source-flags/v1";
                        "build_id", str Build_identity.build_id;
                        "target", str target; "snapshot", str snapshot;
                        "va", str va; "bytes", str code; "length", `Int length;
                        "bil", `List (List.map bil ~f:statement)] in
    Caml.print_endline (Yojson.Safe.to_string response)
  | _ -> invalid_arg "expected target, snapshot SHA256, canonical VA and one admitted flag byte"
