(* Non-production source-built BAP flag-lifting pilot. No plugins are loaded. *)
open Core_kernel[@@warning "-D"]
open Bap.Std

let object_ fields = `Assoc fields
let string value = `String value

let variable var =
  object_ ["name", string (Var.name var);
           "width", `Int (match Var.typ var with Type.Imm bits -> bits | _ -> 0);
           "virtual", `Bool (Var.is_virtual var)]

let rec expression = function
  | Bil.Int word -> object_ ["kind", string "int";
                            "width", `Int (Word.bitwidth word);
                            "value", string (Word.to_string word)]
  | Bil.Var var -> object_ ["kind", string "var"; "var", variable var]
  | Bil.UnOp (Bil.NOT, arg) -> object_ ["kind", string "not"; "arg", expression arg]
  | value -> object_ ["kind", string "outside-flag-subset";
                      "text", string (Format.asprintf "%a" Exp.pp value)]

let statement = function
  | Bil.Move (var, value) -> object_ ["kind", string "move";
                                     "var", variable var; "value", expression value]
  | value -> object_ ["kind", string "outside-flag-subset";
                      "text", string (Format.asprintf "%a" Bil.pp [value])]

let decode hex =
  let n = String.length hex in
  if n = 0 || n > 30 || n mod 2 <> 0
     || not (String.for_all hex ~f:(function '0'..'9' | 'a'..'f' -> true | _ -> false))
  then invalid_arg "expected one to fifteen bytes of canonical hexadecimal";
  String.init (n / 2) ~f:(fun i ->
      Char.of_int_exn (Int.of_string ("0x" ^ String.sub hex ~pos:(i * 2) ~len:2)))

let observe hex =
  let common = ["schema", string "ariadne.bap-source-flag-observation/v1";
                "production", `Bool false; "bytes", string hex;
                "entry", string "X86_lifter.disasm_instr";
                "bilEncoding", string "flag-bil-subset/v1"] in
  let report fields = object_ (common @ fields) in
  try
    let code = decode hex in
    let address = Word.of_int ~width:64 0x401000 in
    let memory = Or_error.ok_exn (Memory.create LittleEndian address (Bigstring.of_string code)) in
    let bil = X86_lifter.disasm_instr X86_types.X8664 memory address in
    (match Type.check bil with
     | Ok () -> ()
     | Error error -> failwith (Format.asprintf "ill-typed BIL: %a" Type.Error.pp error));
    let _, _, _, next = X86_disasm.parse_instr X86_types.X8664 memory address in
    let consumed = Or_error.ok_exn (Word.to_int Word.(next - address)) in
    report ["status", string (if consumed <> String.length code then "trailing-bytes"
                              else if List.is_empty bil then "empty-bil" else "lifted");
            "length", `Int consumed; "wellTyped", `Bool true;
            "bil", `List (List.map bil ~f:statement);
            "bilText", string (Format.asprintf "%a" Bil.pp bil)]
  with
  | X86_utils.No_semantics -> report ["status", string "missing-semantics"; "bil", `List []]
  | exn -> report ["status", string "error"; "error", string (Exn.to_string exn)]

let () =
  let cases = List.tl_exn (Array.to_list Sys.argv) in
  if List.is_empty cases || List.length cases > 64 then
    invalid_arg "supply one to sixty-four finite byte cases";
  List.iter cases ~f:(fun hex ->
      Caml.print_endline (Yojson.Safe.to_string (observe hex)))
