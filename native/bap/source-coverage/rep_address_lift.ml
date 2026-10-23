(* Thirty-two exact REP memory forms, lifted by the patched pinned upstream BAP. *)
open Core_kernel[@@warning "-D"]
open Bap.Std

let str s = `String s
let obj fields = `Assoc fields
let codes = ["f3ac"; "66f3ad"; "f3ad"; "f348ad"; "67f3a4"; "6766f3a5"; "67f3a5"; "67f348a5"; "67f3aa"; "6766f3ab"; "67f3ab"; "67f348ab"; "67f3ac"; "6766f3ad"; "67f3ad"; "67f348ad"; "67f3a6"; "6766f3a7"; "67f3a7"; "67f348a7"; "67f2a6"; "6766f2a7"; "67f2a7"; "67f248a7"; "67f3ae"; "6766f3af"; "67f3af"; "67f348af"; "67f2ae"; "6766f2af"; "67f2af"; "67f248af"]
let canonical_hex s n = String.length s = n && String.for_all s ~f:(function
    | '0'..'9' | 'a'..'f' -> true | _ -> false)

let variable v =
  let width, typ = match Var.typ v with
    | Type.Imm n -> n, "imm"
    | Type.Mem _ -> 0, "mem"
    | _ -> failwith "REP address-size variable type outside typed AST scope" in
  obj ["name", str (Var.name v); "index", `Int (Var.index v);
       "virtual", `Bool (Var.is_virtual v); "width", `Int width; "type", str typ]

(* These are the measured pinned bap.h C API enumeration values. Matching
   constructors explicitly avoids depending on OCaml runtime tag numbers. *)
let binop = function
  | Bil.PLUS -> 18 | Bil.MINUS -> 17 | Bil.TIMES -> 16
  | Bil.AND -> 8 | Bil.NEQ -> 4 | Bil.EQ -> 5
  | Bil.XOR -> 6 | Bil.OR -> 7 | Bil.LT -> 3 | Bil.LE -> 2
  | Bil.SLT -> 1 | Bil.SLE -> 0
  | Bil.LSHIFT -> 11 | Bil.RSHIFT -> 10 | Bil.ARSHIFT -> 9
  | op -> failwith (Format.asprintf "REP address-size binary operator outside serializer scope: %a"
                      Exp.pp (Bil.BinOp (op, Bil.Int Word.b0, Bil.Int Word.b0)))
let cast = function
  | Bil.LOW -> 0 | Bil.HIGH -> 1 | Bil.SIGNED -> 2 | Bil.UNSIGNED -> 3

let nodes = ref 0
let budget depth =
  incr nodes;
  if depth > 64 || !nodes > 8192 then failwith "REP address-size AST budget"

let rec expression depth e =
  budget depth;
  let child = expression (depth + 1) in
  match e with
  | Bil.Int w -> obj ["kind", str "int"; "value", str (Word.to_string w)]
  | Bil.Var v -> obj ["kind", str "var"; "var", variable v]
  | Bil.UnOp (Bil.NOT, x) -> obj ["kind", str "unop"; "op", `Int 0; "arg", child x]
  | Bil.Load (m, a, LittleEndian, size) ->
    obj ["kind", str "load"; "width", `Int (Size.in_bits size);
         "mem", child m; "addr", child a]
  | Bil.Store (m, a, v, LittleEndian, size) ->
    obj ["kind", str "store"; "width", `Int (Size.in_bits size);
         "mem", child m; "addr", child a; "value", child v]
  | Bil.Let (v, value, body) -> obj ["kind", str "let"; "var", variable v;
                                    "value", child value; "body", child body]
  | Bil.BinOp (op, l, r) -> obj ["kind", str "binop"; "op", `Int (binop op);
                                "lhs", child l; "rhs", child r]
  | Bil.Cast (op, width, arg) -> obj ["kind", str "cast"; "op", `Int (cast op);
                                    "width", `Int width; "arg", child arg]
  | Bil.Extract (hi, lo, arg) -> obj ["kind", str "extract"; "hi", `Int hi;
                                    "lo", `Int lo; "arg", child arg]
  | Bil.Concat (l, r) -> obj ["kind", str "concat"; "lhs", child l; "rhs", child r]
  | Bil.Ite (c, y, n) -> obj ["kind", str "ite"; "condition", child c;
                             "yes", child y; "no", child n]
  | _ -> failwith "REP address-size expression outside typed serializer scope"

let rec statements depth values = `List (List.map values ~f:(statement depth))
and statement depth s =
  budget depth;
  let expr = expression (depth + 1) in
  match s with
  | Bil.Move (v, e) -> obj ["kind", str "move"; "var", variable v; "value", expr e]
  | Bil.While (c, body) -> obj ["kind", str "while"; "condition", expr c;
                              "body", statements (depth + 1) body]
  | Bil.If (c, y, n) -> obj ["kind", str "if"; "condition", expr c;
                            "yes", statements (depth + 1) y;
                            "no", statements (depth + 1) n]
  | _ -> failwith "REP address-size statement outside typed serializer scope"

let decode code = String.init (String.length code / 2) ~f:(fun i ->
    Char.of_int_exn (Int.of_string ("0x" ^ String.sub code ~pos:(2 * i) ~len:2)))

let () =
  match Array.to_list Sys.argv with
  | [_; target; snapshot; va; code]
    when List.mem ["windows-amd64"; "linux-amd64"] target ~equal:String.equal
         && canonical_hex snapshot 64 && String.is_prefix va ~prefix:"0x"
         && canonical_hex (String.drop_prefix va 2) 16
         && List.mem codes code ~equal:String.equal ->
    let address = Word.of_string (va ^ ":64") in
    let memory = Or_error.ok_exn (Memory.create LittleEndian address (Bigstring.of_string (decode code))) in
    let bil = X86_lifter.disasm_instr X86_types.X8664 memory address in
    (match Type.check bil with Ok () -> () | Error _ -> failwith "ill-typed REP address-size BIL");
    let _, _, _, next = X86_disasm.parse_instr X86_types.X8664 memory address in
    let length = Or_error.ok_exn (Word.to_int Word.(next - address)) in
    if length <> String.length code / 2 || List.is_empty bil then failwith "REP address-size extent/body";
    let response = obj ["schema", str "ariadne.bap-source-rep-address/v1";
                        "build_id", str Build_identity.build_id;
                        "target", str target; "snapshot", str snapshot;
                        "va", str va; "bytes", str code; "length", `Int length;
                        "bil", statements 0 bil] in
    let text = Yojson.Safe.to_string response in
    if String.length text > 65536 then failwith "REP address-size response budget";
    Caml.print_endline text
  | _ -> invalid_arg "expected target, snapshot SHA256, canonical VA and exact REP REP address-size bytes"
