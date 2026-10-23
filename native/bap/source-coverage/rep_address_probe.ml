(* Source comparison only. Text is never interpreted as production effects. *)
open Core_kernel[@@warning "-D"]
open Bap.Std

let observe code =
  let common = ["schema", `String "ariadne.bap-source-rep-address-observation/v1";
                "bytes", `String code; "production", `Bool false] in
  let result fields = `Assoc (common @ fields) in
  try
    if String.length code = 0 || String.length code > 30 || String.length code mod 2 <> 0 then
      invalid_arg "bounded bytes required";
    let bytes = String.init (String.length code / 2) ~f:(fun i ->
        Char.of_int_exn (Int.of_string ("0x" ^ String.sub code ~pos:(2 * i) ~len:2))) in
    let address = Word.of_int ~width:64 0x401000 in
    let memory = Or_error.ok_exn (Memory.create LittleEndian address (Bigstring.of_string bytes)) in
    let bil = X86_lifter.disasm_instr X86_types.X8664 memory address in
    (match Type.check bil with
     | Ok () -> ()
     | Error error -> failwith (Format.asprintf "ill-typed BIL: %a" Type.Error.pp error));
    let _, _, _, next = X86_disasm.parse_instr X86_types.X8664 memory address in
    let consumed = Or_error.ok_exn (Word.to_int Word.(next - address)) in
    result ["status", `String (if consumed <> String.length bytes then "trailing-bytes"
                               else if List.is_empty bil then "empty-bil" else "lifted");
            "length", `Int consumed; "wellTyped", `Bool true;
            "bilText", `String (Format.asprintf "%a" Bil.pp bil)]
  with
  | X86_utils.No_semantics -> result ["status", `String "missing-semantics"]
  | exn -> result ["status", `String "error"; "error", `String (Exn.to_string exn)]

let () =
  let cases = List.tl_exn (Array.to_list Sys.argv) in
  if List.is_empty cases || List.length cases > 128 then invalid_arg "finite source cases required";
  List.iter cases ~f:(fun code -> Caml.print_endline (Yojson.Safe.to_string (observe code)))
