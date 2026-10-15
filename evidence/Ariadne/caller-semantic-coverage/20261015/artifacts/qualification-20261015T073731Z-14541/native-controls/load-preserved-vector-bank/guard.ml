(* Independent admission check for proof-gated captured MOVAPS recovery.
   This profile does not construct edges or infer effects from a crash register. *)
open Recovery

module Sha256 = struct
  open Int32
  let k = Array.map of_string [|
    "0x428a2f98";"0x71374491";"0xb5c0fbcf";"0xe9b5dba5";
    "0x3956c25b";"0x59f111f1";"0x923f82a4";"0xab1c5ed5";
    "0xd807aa98";"0x12835b01";"0x243185be";"0x550c7dc3";
    "0x72be5d74";"0x80deb1fe";"0x9bdc06a7";"0xc19bf174";
    "0xe49b69c1";"0xefbe4786";"0x0fc19dc6";"0x240ca1cc";
    "0x2de92c6f";"0x4a7484aa";"0x5cb0a9dc";"0x76f988da";
    "0x983e5152";"0xa831c66d";"0xb00327c8";"0xbf597fc7";
    "0xc6e00bf3";"0xd5a79147";"0x06ca6351";"0x14292967";
    "0x27b70a85";"0x2e1b2138";"0x4d2c6dfc";"0x53380d13";
    "0x650a7354";"0x766a0abb";"0x81c2c92e";"0x92722c85";
    "0xa2bfe8a1";"0xa81a664b";"0xc24b8b70";"0xc76c51a3";
    "0xd192e819";"0xd6990624";"0xf40e3585";"0x106aa070";
    "0x19a4c116";"0x1e376c08";"0x2748774c";"0x34b0bcb5";
    "0x391c0cb3";"0x4ed8aa4a";"0x5b9cca4f";"0x682e6ff3";
    "0x748f82ee";"0x78a5636f";"0x84c87814";"0x8cc70208";
    "0x90befffa";"0xa4506ceb";"0xbef9a3f7";"0xc67178f2"|]
  let init = Array.map of_string [|
    "0x6a09e667";"0xbb67ae85";"0x3c6ef372";"0xa54ff53a";
    "0x510e527f";"0x9b05688c";"0x1f83d9ab";"0x5be0cd19"|]
  let rotr x n = logor (shift_right_logical x n) (shift_left x (32-n))
  let sigma0 x = logxor (logxor (rotr x 7) (rotr x 18)) (shift_right_logical x 3)
  let sigma1 x = logxor (logxor (rotr x 17) (rotr x 19)) (shift_right_logical x 10)
  let big0 x = logxor (logxor (rotr x 2) (rotr x 13)) (rotr x 22)
  let big1 x = logxor (logxor (rotr x 6) (rotr x 11)) (rotr x 25)
  let digest text =
    let length=String.length text in
    let padded=((length+9+63)/64)*64 in
    let bytes=Bytes.make padded '\000' in
    Bytes.blit_string text 0 bytes 0 length;
    Bytes.set bytes length '\128';
    let bits=Int64.mul (Int64.of_int length) 8L in
    for n=0 to 7 do
      Bytes.set bytes (padded-8+n)
        (Char.chr (Int64.to_int (Int64.logand
          (Int64.shift_right_logical bits ((7-n)*8)) 255L)))
    done;
    let h=Array.copy init in
    let w=Array.make 64 zero in
    for block=0 to padded/64-1 do
      for n=0 to 15 do
        let at=block*64+n*4 in
        let byte index=of_int (Char.code (Bytes.get bytes index)) in
        w.(n) <- logor (shift_left (byte at) 24)
          (logor (shift_left (byte (at+1)) 16)
            (logor (shift_left (byte (at+2)) 8) (byte (at+3))))
      done;
      for n=16 to 63 do
        w.(n) <- add (add (add (sigma1 w.(n-2)) w.(n-7))
          (sigma0 w.(n-15))) w.(n-16)
      done;
      let a=ref h.(0) and b=ref h.(1) and c=ref h.(2) and d=ref h.(3)
      and e=ref h.(4) and f=ref h.(5) and g=ref h.(6) and z=ref h.(7) in
      for n=0 to 63 do
        let choose=logxor (logand !e !f) (logand (lognot !e) !g) in
        let majority=logxor (logxor (logand !a !b) (logand !a !c))
          (logand !b !c) in
        let t1=add (add (add (add !z (big1 !e)) choose) k.(n)) w.(n) in
        let t2=add (big0 !a) majority in
        z:= !g;g:= !f;f:= !e;e:=add !d t1;
        d:= !c;c:= !b;b:= !a;a:=add t1 t2
      done;
      let values=[|!a;!b;!c;!d;!e;!f;!g;!z|] in
      for n=0 to 7 do h.(n)<-add h.(n) values.(n) done
    done;
    Array.to_list h |> List.map (Printf.sprintf "%08lx") |> String.concat ""
end
let () =
  require (Sha256.digest ""=
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" &&
    Sha256.digest "abc"=
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" &&
    Sha256.digest
      "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"=
    "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")
    "native guard SHA-256 self-test"
let encoded j = Yojson.Safe.to_string j
let hash_json j = Sha256.digest (encoded j)
let rec canonical_value=function
  | `Assoc rows->`Assoc(List.map(fun(key,value)->key,canonical_value value)rows|>
    List.sort(fun(a,_)(b,_)->String.compare a b))
  | `List rows->`List(List.map canonical_value rows)
  | value->value
let value_hash value=hash_json(canonical_value value)
let rec same_shape a b = match a,b with
  | `Assoc a,`Assoc b ->
    let sort=List.sort (fun (x,_) (y,_) -> compare x y) in
    let a=sort a and b=sort b in
    List.length a=List.length b && List.for_all2 (fun (ka,va) (kb,vb) ->
      ka=kb && same_shape va vb) a b
  | `List a,`List b ->
    List.length a=List.length b && List.for_all2 same_shape a b
  | _ -> a=b
let replace_field j name value =
  `Assoc (List.map (fun (key,old) ->
    if key=name then key,value else key,old) (fields j))
let tuples values = `List values
let digest_array values = hash_json (tuples values)
(* serde_json serializes typed structs in declaration order, while Value maps
   on the transport are key-sorted. Rebuild only the reviewed typed shapes
   before checking their source-bound SHA-256 tuples. *)
let ordered j keys = `Assoc (List.map (fun key -> key,get j key) keys)
let ordered_list make j = `List (List.map make (list j))
let ordered_activation j = ordered j ["thread_id";"frame_activation"]
let ordered_root j = ordered j ["site";"function_entry";"anchor_sha256"]
let ordered_producer j = ordered j ["helper_sha256";"runtime_sha256";
  "decoder_sha256";"projection"]
let ordered_premise j = `Assoc [
  "origin",get j "origin";"snapshot",get j "snapshot";
  "query_scope_sha256",get j "query_scope_sha256";
  "root",get j "root";"point",get j "point";
  "activation",ordered_activation(get j "activation");
  "policy",get j "policy";"evidence_sha256",get j "evidence_sha256";
  "rsp_residues",get j "rsp_residues";"rsp_value",get j "rsp_value"]
let ordered_limits j = ordered j ["max_sites";"max_edges";
  "max_residue_updates";"max_transfer_evaluations";
  "max_closure_rounds";"max_evidence_bytes";"max_elapsed_ms"]
let ordered_control j = ordered j ["kind";"fall";"targets";"complete"]
let ordered_site j = `Assoc [
  "site",get j "site";"bytes_hex",get j "bytes_hex";
  "ast",get j "ast";"control",ordered_control(get j "control");
  "opaque",get j "opaque"]
let ordered_transfer j = ordered j ["site";"bytes_sha256";"ast_sha256";
  "rule";"relation";"relation_sha256"]
let ordered_fact j = ordered j ["site";"residues"]
let ordered_decision j = ordered j ["site";"verdict";"input_residues";
  "address_residues";"original_ast_sha256";"normal_ast";
  "normal_ast_sha256";"removed_statement_paths";"residual";
  "receipt_sha256"]
let ordered_input j = `Assoc [
  "snapshot",get j "snapshot";"artifact_sha256",get j "artifact_sha256";
  "query_scope_sha256",get j "query_scope_sha256";
  "preparation_sha256",get j "preparation_sha256";
  "platform",get j "platform";
  "roots",ordered_list ordered_root (get j "roots");
  "seeds",get j "seeds";
  "activation",ordered_activation(get j "activation");
  "premises",ordered_list ordered_premise (get j "premises");
  "producer",ordered_producer(get j "producer");
  "policy",get j "policy";"model_version",get j "model_version";
  "model_sha256",get j "model_sha256";
  "limits",ordered_limits(get j "limits");
  "candidate_epoch",get j "candidate_epoch";
  "closure_complete",get j "closure_complete";
  "barriers",get j "barriers";
  "sites",ordered_list ordered_site (get j "sites");
  "normal_flow",Terminal.ordered_flow(get j "normal_flow")]
let ordered_report j = `Assoc [
  "schema",get j "schema";"profile",get j "profile";
  "checker_sha256",get j "checker_sha256";
  "input",ordered_input(get j "input");
  "intent_id",get j "intent_id";
  "candidate_graph_sha256",get j "candidate_graph_sha256";
  "transfers",ordered_list ordered_transfer (get j "transfers");
  "facts",ordered_list ordered_fact (get j "facts");
  "guards",ordered_list ordered_decision (get j "guards");
  "stop",get j "stop";
  "final_request_sha256",get j "final_request_sha256"]
let contains text needle =
  let n=String.length text and m=String.length needle in
  let rec search at =
    at+m<=n && (String.sub text at m=needle || search (at+1)) in
  search 0

let hash value =
  let s=str value in
  require (String.length s=64 && string_all (fun c ->
    (c>='0' && c<='9') || (c>='a' && c<='f')) s) "guard digest";
  s
let nonnegative = function
  | `Int n when n>=0 -> n
  | _ -> raise (Invalid "guard nonnegative integer")
let signed = function
  | `Int n -> n
  | _ -> raise (Invalid "guard integer")
let mask value =
  let n=nonnegative value in
  require (n<=65535) "guard residue mask";n
let hex_bytes text =
  require (String.length text mod 2=0 && String.length text<=30 &&
    string_all (fun c -> (c>='0' && c<='9') || (c>='a' && c<='f')) text)
    "guard bytes";
  List.init (String.length text / 2) (fun n ->
    int_of_string ("0x" ^ String.sub text (n*2) 2))
let bytes_digest text =
  let b=hex_bytes text |> Array.of_list in
  Sha256.digest (String.init (Array.length b) (fun n -> Char.chr b.(n)))
let field j k = get j k
let variable v name width ty =
  exact v ["name";"index";"virtual";"width";"type"];
  string v "name"=name && get v "index"=`Int 0 &&
  get v "virtual"=`Bool false && get v "width"=`Int width &&
  string v "type"=ty
let var_ref e name width ty =
  string e "kind"="var" && variable (get e "var") name width ty
let number e =
  if string e "kind"<>"int" then None else
  match String.split_on_char ':' (string e "value") with
  | [n;w] when w="64u" || w="64s" ->
    (try Some (Int64.of_string n) with _ -> None)
  | _ -> None
let number_is e n = number e=Some n
let rsp_offset e =
  match string e "kind" with
  | "var" when var_ref e "RSP" 64 "imm" -> Some 0L
  | "binop" when get e "op"=`Int 18 &&
                  var_ref (get e "lhs") "RSP" 64 "imm" -> number (get e "rhs")
  | _ -> None
let movaps_encoding text =
  let b=hex_bytes text in
  let b,high=match b with 0x40::rest -> rest,0 | 0x44::rest -> rest,8 | _ -> b,0 in
  match b with
  | 0x0f::operation::modrm::sib::rest
      when List.mem operation [0x28;0x29] && modrm land 7=4 && sib=0x24 ->
    let bank=((modrm lsr 3) land 7)+high in
    (match modrm lsr 6,rest with
     | 0,[] -> Some (0L,bank)
     | 1,[d] -> Some (Int64.of_int (if d>=128 then d-256 else d),bank)
     | 2,[a;b;c;d] ->
       let n=Int64.logor (Int64.of_int a)
         (Int64.logor (Int64.shift_left (Int64.of_int b) 8)
           (Int64.logor (Int64.shift_left (Int64.of_int c) 16)
             (Int64.shift_left (Int64.of_int d) 24))) in
       Some (Int64.shift_right (Int64.shift_left n 32) 32,bank)
     | _ -> None)
  | _ -> None
let load_encoding text=
  let b=hex_bytes text in
  let b=match b with 0x40::rest|0x44::rest->rest|_->b in
  match b with 0x0f::0x28::_->true|_->false
let pending_rule site=if load_encoding(string site "bytes_hex") then
  "pending-legacy128-movaps-load-rsp-identity/v1"
  else "pending-legacy128-movaps-rsp-identity/v1"
let recognized site =
  try
    let displacement,bank=match movaps_encoding (string site "bytes_hex") with
      | Some v -> v | None -> raise Not_found in
    let control=get site "control" in
    let start=Int64.of_string (address(string site "site")) in
    let next=Int64.add start (Int64.of_int
      (String.length (string site "bytes_hex") / 2)) in
    require (Int64.unsigned_compare next start>0)
      "guard ordinary continuation overflow";
    require (string control "kind"="ordinary" &&
      list (get control "targets")=[] &&
      get control "fall"=`List [`String (Printf.sprintf "0x%016Lx" next)] &&
      get control "complete"=`Bool true)
      "guard pending control";
    let ast=Yojson.Safe.from_string (string site "ast") in
    json_shape 0 ast;
    Capture.validate_bil_ast ast;
    match list ast with
    | [store;check] ->
      let value=get store "value" in
      require(string store "kind"="move")"guard normal assignment";
      if load_encoding(string site "bytes_hex") then begin
        let high=get value "lhs" and low=get value "rhs" in
        require(variable(get store "var")("YMM"^string_of_int bank)256 "imm" &&
          string value "kind"="concat" && string high "kind"="extract" &&
          get high "hi"=`Int 255 && get high "lo"=`Int 128 &&
          true &&
          string low "kind"="cast" && get low "op"=`Int 3 && get low "width"=`Int 128)
          "guard load vector merge";
        let payload=get low "arg" in
        require(string payload "kind"="load" && get payload "width"=`Int 128 &&
          var_ref(get payload "mem")"mem" 0 "mem" &&
          rsp_offset(get payload "addr")=Some displacement)"guard load address"
      end else begin
        require (variable (get store "var") "mem" 0 "mem" &&
          string value "kind"="store" && get value "width"=`Int 128 &&
          var_ref (get value "mem") "mem" 0 "mem" &&
          rsp_offset (get value "addr")=Some displacement) "guard store shape";
        let payload=get value "value" in
        require (string payload "kind"="cast" && get payload "op"=`Int 0 &&
          get payload "width"=`Int 128 &&
          var_ref (get payload "arg") ("YMM"^string_of_int bank) 256 "imm")
          "guard vector source"
      end;
      let condition=get check "condition" in
      let bit_and=get condition "lhs" in
      require (string check "kind"="if" &&
        list (get check "yes")=[] &&
        (match list (get check "no") with
         | [fault] -> string fault "kind"="exception" &&
                      get fault "number"=`Int 13
         | _ -> false) &&
        string condition "kind"="binop" && get condition "op"=`Int 5 &&
        number_is (get condition "rhs") 0L &&
        string bit_and "kind"="binop" && get bit_and "op"=`Int 8 &&
        number_is (get bit_and "rhs") 15L &&
        rsp_offset (get bit_and "lhs")=Some displacement) "guard predicate shape";
      Some (displacement,bank,store)
    | _ -> None
  with Not_found | Invalid _ -> None

let top=65535
let shift values delta =
  let d=Int64.to_int (Int64.logand delta 15L) in
  let result=ref 0 in
  for r=0 to 15 do if values land (1 lsl r)<>0 then
    result := !result lor (1 lsl ((r+d) land 15)) done;
  !result
let combine left right subtract =
  let result=ref 0 in
  for r=0 to 15 do if right land (1 lsl r)<>0 then
    result := !result lor shift left (Int64.of_int (if subtract then (16-r) land 15 else r)) done;
  !result
let key v =
  string v "name" ^ ":" ^ string_of_int (signed (get v "index")) ^ ":" ^
  string_of_bool (boolean (get v "virtual"))
(* A finite independent type gate for any transfer allowed to narrow RSP.
   Unsupported or malformed BIL yields TOP rather than an identity relation. *)
exception Untyped
type bil_type = Bits of int | Memory | Unknown
let typed_require condition = if not condition then raise Untyped
let starts text prefix = String.length text>=String.length prefix &&
  String.sub text 0 (String.length prefix)=prefix
let ends text suffix = String.length text>=String.length suffix &&
  String.sub text (String.length text-String.length suffix)
    (String.length suffix)=suffix
let equal_type left right = match left,right with
  | Unknown,t | t,Unknown -> t
  | a,b when a=b -> a
  | _ -> raise Untyped
let scalar_type = function Memory -> raise Untyped | t -> t
let vector_type name width =
  let bank prefix expected =
    if width<>expected || not(starts name prefix) then false
    else let suffix=String.sub name (String.length prefix)
      (String.length name-String.length prefix) in
      match int_of_string_opt suffix with
      | Some n -> n>=0 && n<16 && string_of_int n=suffix
      | None -> false in
  bank "XMM" 128 || bank "YMM" 256
let typed_var v =
  exact v ["name";"index";"virtual";"width";"type"];
  let name=string v "name" and index=signed(get v "index")
  and width=nonnegative(get v "width")
  and virtual_=boolean(get v "virtual") in
  typed_require (name<>"" && String.length name<=128 && index>=0);
  let ty=match string v "type" with
    | "imm" when width>=1 && width<=256 -> Bits width
    | "mem" when width=0 -> Memory
    | _ -> raise Untyped in
  if not virtual_ then begin
    let gpr=List.mem name ["RAX";"RCX";"RDX";"RBX";"RSP";
      "RBP";"RSI";"RDI";"R8";"R9";"R10";"R11";
      "R12";"R13";"R14";"R15";"RIP"] in
    let flag=List.mem name ["CF";"PF";"AF";"ZF";"SF";"OF";"DF"] in
    typed_require (index=0 &&
      ((gpr && ty=Bits 64) || (flag && ty=Bits 1) ||
       (name="mem" && ty=Memory) || vector_type name width))
  end;ty
let typed_integer text =
  let number,width=match String.split_on_char ':' text with
    | [n;w] -> n,w | _ -> raise Untyped in
  let width=if ends width "u" || ends width "s" then
      String.sub width 0 (String.length width-1) else width in
  let width=try int_of_string width with _ -> raise Untyped in
  typed_require (width>=1 && width<=256 && number<>"");
  if starts number "0x" then begin
    let digits=String.sub number 2 (String.length number-2) in
    typed_require (digits<>"" && string_all (fun c ->
      (c>='0' && c<='9') || (c>='a' && c<='f') ||
      (c>='A' && c<='F')) digits);
    String.iteri (fun n c ->
      let value=int_of_string ("0x"^String.make 1 c) in
      for bit=0 to 3 do
        if (String.length digits-1-n)*4+bit>=width then
          typed_require (value land (1 lsl bit)=0)
      done) digits
  end else begin
    let valid=string_all (fun c -> c>='0' && c<='9') number ||
      (String.length number>1 && number.[0]='-' &&
       string_all (fun c -> c>='0' && c<='9')
         (String.sub number 1 (String.length number-1))) in
    typed_require valid;
    (* This finite checker conservatively declines wide decimal literals. *)
    let parsed=try Some(Int64.of_string number) with _ -> None in
    typed_require (parsed<>None);
    let parsed=Option.get parsed in
    if parsed>=0L && width<63 then
      typed_require (Int64.compare parsed (Int64.shift_left 1L width)<0);
    if parsed<0L && width<=63 then
      typed_require
        (Int64.compare parsed (Int64.neg(Int64.shift_left 1L (width-1)))>=0)
  end;Bits width
let rec typed_expr allow_data env depth e =
  if depth>64 then raise Untyped;
  match string e "kind" with
  | "var" ->
    let v=get e "var" in let ty=typed_var v in
    if boolean(get v "virtual") then begin
      let bound=try M.find (key v) env with Not_found -> raise Untyped in
      ignore(equal_type ty bound);bound
    end else ty
  | "int" -> typed_integer (string e "value")
  | "unknown" -> Unknown
  | "unsupported" -> if allow_data then Unknown else raise Untyped
  | "load" ->
    let width=nonnegative(get e "width") in
    typed_require ((List.mem width [8;16;32;64;128;256] ||
      (allow_data && width>=1 && width<=256)) &&
      typed_expr allow_data env (depth+1) (get e "mem")=Memory &&
      typed_expr allow_data env (depth+1) (get e "addr")=Bits 64);
    Bits width
  | "store" ->
    let width=nonnegative(get e "width") in
    typed_require ((List.mem width [8;16;32;64;128;256] ||
      (allow_data && width>=1 && width<=256)) &&
      typed_expr allow_data env (depth+1) (get e "mem")=Memory &&
      typed_expr allow_data env (depth+1) (get e "addr")=Bits 64);
    ignore(equal_type (Bits width)
      (typed_expr allow_data env (depth+1) (get e "value")));Memory
  | "binop" ->
    let op=signed(get e "op") in
    typed_require (op>=0 && (op<=18 || allow_data));
    let left=scalar_type (typed_expr allow_data env (depth+1) (get e "lhs")) in
    let right=scalar_type (typed_expr allow_data env (depth+1) (get e "rhs")) in
    let ty=if List.mem op [9;10;11] then left else equal_type left right in
    if op>18 then Unknown else if op<=5 then Bits 1 else ty
  | "unop" ->
    let op=signed(get e "op") in
    typed_require (op>=0 && (op<=1 || allow_data));
    let ty=scalar_type (typed_expr allow_data env (depth+1) (get e "arg")) in
    if op>1 then Unknown else ty
  | "cast" ->
    let op=signed(get e "op") and width=nonnegative(get e "width") in
    typed_require (op>=0 && (op<=3 || allow_data) && width>=1 && width<=256);
    let source=scalar_type (typed_expr allow_data env (depth+1) (get e "arg")) in
    (match source with Bits n ->
       if op<=3 then typed_require
         (if op<2 then width<=n else width>=n)
     | _ -> ());Bits width
  | "extract" ->
    let hi=nonnegative(get e "hi") and lo=nonnegative(get e "lo") in
    let source=scalar_type (typed_expr allow_data env (depth+1) (get e "arg")) in
    typed_require (lo<=hi && hi<256);
    (match source with Bits n -> typed_require (hi<n) | _ -> ());
    Bits (hi-lo+1)
  | "concat" ->
    let left=scalar_type (typed_expr allow_data env (depth+1) (get e "lhs")) in
    let right=scalar_type (typed_expr allow_data env (depth+1) (get e "rhs")) in
    (match left,right with
     | Bits a,Bits b when a+b<=256 -> Bits(a+b)
     | _ when allow_data -> Unknown
     | _ -> raise Untyped)
  | "ite" ->
    let condition=scalar_type (typed_expr allow_data env (depth+1) (get e "condition")) in
    typed_require (condition=Bits 1 || condition=Unknown);
    equal_type (typed_expr allow_data env (depth+1) (get e "yes"))
      (typed_expr allow_data env (depth+1) (get e "no"))
  | "let" ->
    let v=get e "var" in
    typed_require (boolean(get v "virtual"));
    let ty=typed_var v in
    ignore(equal_type ty (typed_expr allow_data env (depth+1) (get e "value")));
    typed_expr allow_data (M.add (key v) ty env) (depth+1) (get e "body")
  | _ -> raise Untyped
let rec has_unknown e =
  match string e "kind" with
  | "unknown" | "unsupported" -> true
  | "load" -> has_unknown(get e "mem") || has_unknown(get e "addr")
  | "store" -> has_unknown(get e "mem") || has_unknown(get e "addr") ||
      has_unknown(get e "value")
  | "binop" | "concat" -> has_unknown(get e "lhs") || has_unknown(get e "rhs")
  | "unop" | "cast" | "extract" -> has_unknown(get e "arg")
  | "ite" -> has_unknown(get e "condition") || has_unknown(get e "yes") ||
      has_unknown(get e "no")
  | "let" -> has_unknown(get e "value") || has_unknown(get e "body")
  | _ -> false
let rec typed_statements allow_data env depth bil =
  if depth>64 then raise Untyped;
  List.fold_left (fun env stmt ->
    match string stmt "kind" with
    | "move" ->
      let v=get stmt "var" in
      let ty=typed_var v in
      typed_require (not (get v "virtual"=`Bool false &&
        string v "name"="RIP"));
      let value=get stmt "value" in
      (match ty with Bits width when width>1 ->
         typed_require (allow_data || not(has_unknown value)) | _ -> ());
      let value_ty=typed_expr allow_data env (depth+1) value in
      ignore(equal_type ty value_ty);
      typed_require (allow_data || value_ty<>Unknown || ty=Bits 1);
      M.add (key v) ty env
    | "jump" ->
      typed_require (typed_expr allow_data env (depth+1) (get stmt "target")=Bits 64);env
    | "if" ->
      let condition=typed_expr allow_data env (depth+1) (get stmt "condition") in
      typed_require (condition=Bits 1 || condition=Unknown);
      let yes=typed_statements allow_data env (depth+1) (list(get stmt "yes")) in
      let no=typed_statements allow_data env (depth+1) (list(get stmt "no")) in
      M.merge (fun _ left right ->
        match left,right with Some a,Some b when a=b -> Some a | _ -> None)
        yes no
    | _ -> raise Untyped
  ) env bil
let typed_site_mode allow_data site =
  try
    let bil=list(Yojson.Safe.from_string(string site "ast")) in
    typed_require (bil<>[] || string site "bytes_hex"="90");
    ignore(typed_statements allow_data M.empty 0 bil);true
  with Untyped | Invalid _ | Failure _ | Not_found -> false
let typed_site site = typed_site_mode false site
let rec expression depth env e =
  if depth>64 then top else
  match string e "kind" with
  | "var" ->
    let v=get e "var" in
    if get v "type"=`String "imm" && get v "width"=`Int 64 then
      (try M.find (key v) env with Not_found -> top) else top
  | "int" -> (match number e with Some n -> 1 lsl
      Int64.to_int (Int64.logand n 15L) | None -> top)
  | "binop" when get e "op"=`Int 17 || get e "op"=`Int 18 ->
    combine (expression (depth+1) env (get e "lhs"))
      (expression (depth+1) env (get e "rhs"))
      (get e "op"=`Int 17)
  | "cast" when get e "width"=`Int 64 &&
      List.mem (get e "op") [`Int 0;`Int 2;`Int 3] ->
    expression (depth+1) env (get e "arg")
  | "extract" when get e "hi"=`Int 63 && get e "lo"=`Int 0 ->
    expression (depth+1) env (get e "arg")
  | "let" ->
    let v=get e "var" in
    if get v "virtual"=`Bool true && get v "width"=`Int 64 then
      let value=expression (depth+1) env (get e "value") in
      expression (depth+1) (M.add (key v) value env) (get e "body")
    else top
  | _ -> top
let rec statements depth env bil =
  if depth>64 then M.add "RSP:0:false" top env else
  List.fold_left (fun env stmt ->
    match string stmt "kind" with
    | "move" ->
      let v=get stmt "var" in
      let name=string v "name" in
      if List.mem name ["RSP";"ESP";"SP";"SPL"] &&
          (not(variable v "RSP" 64 "imm")) then
        M.add "RSP:0:false" top env
      else if get v "type"=`String "imm" && get v "width"=`Int 64 then
        M.add (key v) (expression 0 env (get stmt "value")) env else env
    | "jump" -> env
    | "if" ->
      let left=statements (depth+1) env (list (get stmt "yes")) in
      let right=statements (depth+1) env (list (get stmt "no")) in
      M.merge (fun _ l r -> Some ((match l with Some n -> n | None -> top) lor
                                (match r with Some n -> n | None -> top))) left right
    | _ -> M.add "RSP:0:false" top env
  ) env bil
let rec unreviewed_control ordinary depth bil =
  if depth>64 then true else
  List.exists (fun stmt ->
    match string stmt "kind" with
    | "exception" | "special" | "while" | "unsupported" -> true
    | "jump" -> ordinary
    | "if" -> unreviewed_control ordinary (depth+1)
        (list(get stmt "yes")) ||
        unreviewed_control ordinary (depth+1) (list(get stmt "no"))
    | _ -> false) bil
let guarded_prefix bytes =
  let rec prefix = function
    | (0x66::rest) -> prefix rest
    | byte::rest when byte>=0x40 && byte<=0x4f -> prefix rest
    | byte::_ -> List.mem byte [0xf0;0xf2;0xf3;0x26;0x2e;0x36;
        0x3e;0x64;0x65;0x67]
    | [] -> false in
  prefix bytes
let opaque_ordinary_site source site =
  let control=get site "control" in
  boolean(get site "opaque") &&
  string control "kind"="ordinary" &&
  get source "status"=`String "opaque-ordinary" &&
  get source "quality"=`String "opaque" &&
  list(Yojson.Safe.from_string(string site "ast"))<>[] &&
  not(guarded_prefix(hex_bytes(string site "bytes_hex"))) &&
  typed_site_mode true site &&
  (let bil=list(Yojson.Safe.from_string(string site "ast")) in
   not(unreviewed_control true 0 bil))
let relation site pending =
  if pending then List.init 16 (fun r -> 1 lsl r)
  else if boolean (get site "opaque") ||
      string (get site "control") "kind"="call" ||
      not(typed_site site) then
    List.init 16 (fun _ -> top)
  else
    let ast=try list (Yojson.Safe.from_string (string site "ast"))
      with _ -> [] in
    List.init 16 (fun r ->
      let env=M.add "RSP:0:false" (1 lsl r) M.empty in
      try M.find "RSP:0:false" (statements 0 env ast) with Not_found -> top)
let apply rel values =
  List.fold_left (fun (r,out) after ->
    (r+1,if values land (1 lsl r)<>0 then out lor after else out)) (0,0) rel
  |> snd
let stopped_guard i capture site instruction =
  require (not(S.mem site i.decodable) &&
    instruction.kind="stop" && not instruction.complete &&
    S.is_empty instruction.fall && S.is_empty instruction.targets &&
    S.is_empty instruction.must &&
    S.equal instruction.uses i.locations &&
    S.equal instruction.may i.locations &&
    get capture "quality"=`String "opaque" &&
    get capture "status"=`String "guard-not-admitted")
    "guard stopped summary/capture contract"

let admit_current j snapshot =
  exact j ["normalized";"capture";"guard_admission"];
  let normalized=get j "normalized" and capture=get j "capture" in
  let i,capture_sites=Capture.admit
    (`Assoc ["normalized",normalized;"capture",capture]) snapshot in
  let report=get j "guard_admission" in
  exact report ["schema";"profile";"checker_sha256";"input";"intent_id";
    "candidate_graph_sha256";"transfers";"facts";"guards";"stop";
    "final_request_sha256"];
  require (string report "schema"="ariadne.guard-admission/v2" &&
    string report "profile"="bap-guard-admission-v2" &&
    string report "checker_sha256"=Build_identity.guard_engine_sha256)
    "guard report profile/checker identity";
  require (contains (string capture "semantic_profile")
    (":" ^ string report "profile" ^ ":" ^
     hash_json (ordered_report report)))
    "guard capture proof binding";
  require(contains(string capture "semantic_profile")
    ":normal-flow-scope=[local-normal-completion/v1]:exception-resumption-outside-local-scope")
    "guard capture normal-flow scope annotation";
  ignore (hash (get report "intent_id"));
  ignore (hash (get report "candidate_graph_sha256"));
  ignore (hash (get report "final_request_sha256"));
  let input=get report "input" in
  exact input ["snapshot";"artifact_sha256";"query_scope_sha256";
    "preparation_sha256";"platform";"roots";"seeds";"activation";
    "premises";"producer";"policy";"model_version";"model_sha256";
    "limits";"candidate_epoch";"closure_complete";"barriers";"sites";"normal_flow"];
  require (string input "snapshot"=snapshot &&
    get input "artifact_sha256"=get capture "artifact_sha256" &&
    string input "policy"="bap-guard-admission-v2" &&
    string input "model_version"="ariadne.predicate-admission/v2" &&
    string input "model_sha256"=Build_identity.guard_model_sha256)
    "guard source/model identity";
  List.iter (fun k -> ignore(hash(get input k)))
    ["artifact_sha256";"query_scope_sha256";"preparation_sha256"];
  let producer=get input "producer" in
  exact producer ["helper_sha256";"runtime_sha256";"decoder_sha256";"projection"];
  require (string producer "projection"="bap-bit-provenance-v8")
    "guard producer profile";
  List.iter (fun k -> ignore(hash(get producer k)))
    ["helper_sha256";"runtime_sha256";"decoder_sha256"];
  let expected_intent=digest_array [
    `String "ariadne-guard-intent/v2";get input "snapshot";
    get input "artifact_sha256";get input "query_scope_sha256";
    get input "preparation_sha256";
    ordered_list ordered_root (get input "roots");get input "seeds";
    ordered_activation(get input "activation");
    ordered_list ordered_premise (get input "premises");get input "platform";
    get input "policy";get input "model_version";get input "model_sha256";
    ordered_producer(get input "producer");ordered_limits(get input "limits");
    Terminal.ordered_flow(get input "normal_flow")] in
  require (string report "intent_id"=expected_intent) "guard intent digest";
  let limits=get input "limits" in
  exact limits ["max_sites";"max_edges";"max_residue_updates";
    "max_transfer_evaluations";"max_closure_rounds";"max_evidence_bytes";
    "max_elapsed_ms"];
  (* Defaults are not policy ceilings. Preserve the full unsigned wire range
     rather than narrowing caller budgets to OCaml's signed tagged integers. *)
  let budget k=Capture.uint(get limits k) in
  let max_sites=budget "max_sites" and max_edges=budget "max_edges" in
  let max_updates=budget "max_residue_updates" and
      max_evals=budget "max_transfer_evaluations" in
  let max_rounds=budget "max_closure_rounds" in
  let max_evidence=budget "max_evidence_bytes" in
  let max_elapsed=budget "max_elapsed_ms" in
  require (Int64.unsigned_compare
    (Int64.of_int(String.length (Yojson.Safe.to_string report))) max_evidence<=0)
    "guard evidence budget";
  let candidate_epoch=Capture.uint(get input "candidate_epoch") in
  let closure=boolean (get input "closure_complete") in
  let activation=get input "activation" in
  exact activation ["thread_id";"frame_activation"];
  ignore(nonnegative (get activation "thread_id"));
  require (string activation "frame_activation"<>"") "guard activation";
  let roots=List.fold_left (fun seen root ->
    exact root ["site";"function_entry";"anchor_sha256"];
    let site=address(string root "site") in
    ignore(boolean(get root "function_entry"));
    ignore(hash(get root "anchor_sha256"));
    require (S.mem site i.roots && not (M.mem site seen)) "guard root domain";
    M.add site root seen) M.empty (list(get input "roots")) in
  require (M.cardinal roots=S.cardinal i.roots) "guard missing root";
  require (S.equal (set ~addr:true (get input "seeds")) i.seeds)
    "guard seed domain";
  let states=M.fold (fun site _ acc -> M.add site top acc) roots M.empty in
  let states=List.fold_left (fun acc premise ->
    exact premise ["origin";"snapshot";"query_scope_sha256";"root";
      "point";"activation";"policy";"evidence_sha256";
      "rsp_residues";"rsp_value"];
    let root=address(string premise "root") in
    require (M.mem root roots && string premise "point"=root &&
      string premise "snapshot"=snapshot &&
      get premise "query_scope_sha256"=get input "query_scope_sha256" &&
      get premise "activation"=activation)
      "guard premise binding";
    ignore(hash(get premise "evidence_sha256"));
    let residues=mask(get premise "rsp_residues") in
    require (residues<>0) "guard empty premise";
    (match string premise "origin" with
     | "abi_normal_call" ->
       require (string input "platform"="windows-amd64" &&
         string premise "policy"="windows-amd64-normal-call-entry/v1" &&
         get (M.find root roots) "function_entry"=`Bool true &&
         residues=1 lsl 8 && get premise "rsp_value"=`Null)
         "guard ABI premise"
     | "captured_register" ->
       require (string premise "policy"="captured-register-at-root/v1" &&
         nonnegative(get activation "thread_id")<>0 &&
         residues=1 lsl (Int64.to_int (Int64.logand
           (Int64.of_string (address(str(get premise "rsp_value")))) 15L)))
         "guard captured RSP premise"
     | _ -> raise(Invalid "unsupported guard premise"));
    let next=(M.find root acc) land residues in
    require (next<>0) "guard conflicting premises";
    M.add root next acc) states (list(get input "premises")) in
  let rows=list(get input "sites") in
  require (rows=List.sort (fun a b -> compare (string a "site") (string b "site")) rows)
    "guard candidate order";
  let candidates=List.fold_left (fun acc site ->
    exact site ["site";"bytes_hex";"ast";"control";"opaque"];
    let at=address(string site "site") in
    ignore(hex_bytes(string site "bytes_hex"));
    let ast=Yojson.Safe.from_string (string site "ast") in
    json_shape 0 ast;ignore(list ast);
    Capture.validate_bil_ast ast;
    ignore(boolean(get site "opaque"));
    let control=get site "control" in
    exact control ["kind";"fall";"targets";"complete"];
    require (List.mem (string control "kind")
      ["ordinary";"conditional";"jump";"indirect";"call";"return";"stop"])
      "guard candidate control";
    ignore(boolean(get control "complete"));
    require (not(M.mem at acc)) "duplicate guard candidate";
    let source=try M.find at capture_sites with Not_found ->
      raise (Invalid "guard candidate absent from final captured domain") in
    require (string source "bytes"=string site "bytes_hex" &&
      (string site "bytes_hex"="" || get source "captured"=`Bool true))
      "guard candidate captured bytes";
    (match get source "ast_sha256" with
     | `Null -> require (string site "ast"="[]" &&
         boolean(get site "opaque") && string control "kind"="stop")
         "guard missing source AST is not opaque stop"
     | value -> require (hash value=Sha256.digest(string site "ast"))
         "guard candidate original AST digest");
    (match get source "helper_sha256",get source "runtime_sha256" with
     | `String helper,`String runtime ->
       require (helper=string producer "helper_sha256" &&
         runtime=string producer "runtime_sha256")
         "guard candidate producer identity"
     | `Null,`Null -> ()
     | _ -> raise (Invalid "guard candidate incomplete producer identity"));
    if recognized site=None then begin
      let projected=get source "status"=`String "projected" in
      require (boolean(get site "opaque")<>projected)
        "guard candidate opacity/source status mismatch";
      if projected then require (get source "quality"=`String "external_lift" &&
        get source "projection"=`String "bap-bit-provenance-v8")
        "guard narrowed transfer lacks projected v5 source"
    end;
    M.add at site acc) M.empty rows in
  let terminals=Terminal.validate_flow candidates(get input "normal_flow")in
  S.iter(fun at->if(M.find at i.instructions).kind="stop" then
    require(S.mem at terminals)"decoded Stop lacks terminal receipt")i.decodable;
  M.iter(fun at source->if get source "status"=`String "normal-flow-terminal" then
    require(S.mem at terminals)"terminal capture status lacks receipt")capture_sites;
  S.iter(fun at->
    let instruction=M.find at i.instructions and source=M.find at capture_sites in
    require(instruction.kind="stop" && instruction.complete &&
      S.is_empty instruction.fall && S.is_empty instruction.targets &&
      S.equal instruction.uses i.locations && S.equal instruction.may i.locations &&
      S.is_empty instruction.must && S.mem at i.captured && S.mem at i.decodable &&
      get source "captured"=`Bool true && get source "quality"=`String "opaque" &&
      get source "status"=`String "normal-flow-terminal" &&
      get source "ast_sha256"<>`Null &&
      get source "projection"=`String "bap-bit-provenance-v8")
      "terminal final normal-control or conservative-effect mismatch")terminals;
  S.iter (fun at -> require (M.mem at candidates)
    "guard admitted instruction missing candidate evidence") i.decodable;
  M.iter (fun root _ -> require (M.mem root candidates) "guard root not candidate") roots;
  let outgoing=M.fold (fun at site acc ->
    let control=get site "control" in
    let kind=string control "kind" in
    let fall=set ~addr:true (get control "fall") and
        targets=set ~addr:true (get control "targets") in
    require (S.cardinal fall=(if List.mem kind ["ordinary";"conditional";"call"] then 1 else 0) &&
      (not (List.mem kind ["ordinary";"return";"stop"]) || S.is_empty targets) &&
      (not (List.mem kind ["conditional";"jump"]) || S.cardinal targets=1))
      "guard candidate edge shape";
    if recognized site=None then begin
      let admitted=M.find at i.instructions in
      require (admitted.kind=kind && S.equal admitted.fall fall &&
        S.equal admitted.targets targets &&
        admitted.complete=boolean(get control "complete"))
        "guard nonpending candidate/final control mismatch";
      if not(List.mem kind ["call";"return"]) then begin
        let bil=list(Yojson.Safe.from_string(string site "ast")) in
        if unreviewed_control (kind="ordinary") 0 bil then
          require (admitted.kind="stop" && S.is_empty admitted.fall &&
            S.is_empty admitted.targets && S.is_empty admitted.must)
            "guard unreviewed source control continued"
      end
    end;
    let succ=if List.mem kind ["conditional";"jump";"indirect"] then
      S.union fall targets else fall in
    M.add at succ acc) candidates M.empty in
  let edges=M.fold (fun _ s n ->
    let count=S.cardinal s in
    require (n<=max_int-count) "guard edge count overflow";
    n+count) outgoing 0 in
  let edge_rows=List.concat_map (fun site ->
    let at=get site "site" and control=get site "control" in
    let kind=string control "kind" in
    let fall_kind=match kind with
      | "conditional" -> "fallthrough" | "call" -> "summary" | _ -> "next" in
    let record dst edge_kind=`Assoc ["src",at;"dst",dst;
      "kind",`String edge_kind] in
    let fall=List.map (fun dst -> record dst fall_kind)
      (list(get control "fall")) in
    let targets=if List.mem kind ["conditional";"jump";"indirect"]
      then List.map (fun dst -> record dst
        (if kind="conditional" then "taken"
         else if kind="jump" then "jump" else "indirect"))
        (list(get control "targets")) else [] in
    fall@targets) rows in
  let expected_graph=digest_array [
    `String "ariadne-guard-candidate/v2";
    ordered_list ordered_root (get input "roots");
    get input "candidate_epoch";get input "closure_complete";
    get input "barriers";ordered_list ordered_site (get input "sites");
    `List edge_rows;Terminal.ordered_flow(get input "normal_flow")] in
  require (string report "candidate_graph_sha256"=expected_graph)
    "guard candidate graph digest";
  let static_stop=if Int64.unsigned_compare
      (Int64.of_int(List.length rows)) max_sites>0 then Some "guard-site-limit"
    else if Int64.unsigned_compare (Int64.of_int edges) max_edges>0 then Some "guard-edge-limit"
    else if Int64.unsigned_compare candidate_epoch max_rounds>=0 then
      Some "guard-closure-round-limit"
    else if max_elapsed=0L || max_updates=0L || max_evals=0L then
      Some "guard-zero-work-budget" else None in
  let ()=match static_stop with
    | Some reason ->
      require (get report "stop"=`String reason &&
        list(get report "transfers")=[] && list(get report "facts")=[] &&
        list(get report "guards")=[]) "guard static stop payload";
      M.iter (fun at site ->
        if recognized site<>None then begin
          let instruction=M.find at i.instructions in
          let source=M.find at capture_sites in
          stopped_guard i source at instruction
        end) candidates
    | None -> begin
  let barriers=set ~addr:true (get input "barriers") in
  let closed=closure && S.is_empty barriers &&
    M.for_all (fun _ site ->
      let c=get site "control" in
      (string c "kind"<>"indirect" || boolean(get c "complete")) &&
      S.for_all (fun to_ -> M.mem to_ candidates)
        (M.find (address(string site "site")) outgoing) &&
      (recognized site<>None || S.mem(address(string site "site"))terminals ||
       List.mem (string c "kind") ["call";"return"] ||
       (string c "kind"<>"stop" && (typed_site site ||
         opaque_ordinary_site (M.find (address(string site "site")) capture_sites) site) &&
        (list(Yojson.Safe.from_string(string site "ast"))<>[] ||
          string site "bytes_hex"="90") &&
        (let bil=try list(Yojson.Safe.from_string(string site "ast"))
          with _ -> raise(Invalid "guard candidate AST") in
         not(unreviewed_control (string c "kind"="ordinary") 0 bil)))))
      candidates in
  let stop=get report "stop" in
  require (stop=`Null || List.mem stop [`String "candidate-coverage-incomplete";
      `String "guard-deadline-limit";`String "guard-residue-update-limit";
      `String "guard-transfer-evaluation-limit"])
    "guard unknown stop";
  (* The Rust checker can find an additional typed-admission barrier that this
     finite native shape checker does not recognize. Accept only its more
     conservative stop, never an aligned normal selection. *)
  require (closed || stop<>`Null)
    "guard coverage/stop mismatch";
  let transfers=M.fold (fun at site acc ->
    let pending=recognized site<>None in
    M.add at (relation site pending) acc) candidates M.empty in
  let reported_transfers=List.fold_left (fun acc row ->
    exact row ["site";"bytes_sha256";"ast_sha256";"rule";
      "relation";"relation_sha256"];
    let at=address(string row "site") in
    require (M.mem at candidates && not (M.mem at acc)) "guard transfer domain";
    List.iter (fun k -> ignore(hash(get row k)))
      ["bytes_sha256";"ast_sha256";"relation_sha256"];
    let actual=List.map mask (list(get row "relation")) in
    let pending=recognized (M.find at candidates)<>None in
    let rule=string row "rule" in
    let source=M.find at candidates in
    require (string row "bytes_sha256"=bytes_digest (string source "bytes_hex") &&
      string row "ast_sha256"=Sha256.digest (string source "ast") &&
      string row "relation_sha256"=digest_array
        [get row "rule";get row "relation"])
      "guard transfer source/relation digest";
    let rule_ok=if pending then
      rule=pending_rule source &&
      actual=List.init 16 (fun n -> 1 lsl n)
    else if rule="opaque-rsp-havoc/v1" then
      actual=List.init 16 (fun _ -> top)
    else rule="typed-bil-rsp-residue/v1" &&
      not(boolean(get source "opaque")) &&
      string (get source "control") "kind"<>"call" &&
      typed_site source &&
      actual=M.find at transfers in
    require (List.length actual=16 && rule_ok)
      "guard transfer relation";
    M.add at actual acc) M.empty (list(get report "transfers")) in
  require (M.cardinal reported_transfers=M.cardinal candidates)
    "guard transfer coverage";
  let facts=List.fold_left (fun facts row ->
    exact row ["site";"residues"];
    let at=address(string row "site") in
    require (M.mem at candidates && not(M.mem at facts))
      "guard candidate fact domain";
    M.add at (mask(get row "residues")) facts)
    M.empty (list(get report "facts")) in
  require (M.cardinal facts=M.cardinal candidates)
    "guard fact coverage";
  if stop=`Null || stop=`String "candidate-coverage-incomplete" then begin
    M.iter (fun root premise ->
      require (premise land (lnot(M.find root facts))=0)
        "guard omitted eligible root residue") states;
    if not closed || stop=`String "candidate-coverage-incomplete" then
      require (M.for_all (fun _ mask -> mask=top) facts)
      "guard unresolved incoming did not widen to top";
    M.iter (fun at next -> S.iter (fun target ->
      if M.mem target facts then
        require (apply (M.find at reported_transfers) (M.find at facts)
          land (lnot(M.find target facts))=0)
          "guard omitted candidate predecessor residue") next) outgoing
  end;
  let decisions=List.fold_left (fun seen d ->
    exact d ["site";"verdict";"input_residues";"address_residues";
      "original_ast_sha256";"normal_ast";"normal_ast_sha256";
      "removed_statement_paths";"residual";"receipt_sha256"];
    let at=address(string d "site") in
    require (M.mem at candidates && not(S.mem at seen)) "guard decision domain";
    let site=M.find at candidates in
    let displacement,_,store=match recognized site with
      | Some row -> row | None -> raise(Invalid "guard decision not a reviewed MOVAPS") in
    let input_residues=M.find at facts in
    let addresses=shift input_residues displacement in
    let verdict=if not closed || stop<>`Null then "unknown" else if input_residues=0 then
      "unreached" else if addresses=1 then "aligned" else if addresses land 1=0
      then "misaligned" else "unknown" in
    require (string d "verdict"=verdict &&
      mask(get d "input_residues")=input_residues &&
      mask(get d "address_residues")=addresses)
      "guard verdict mismatch";
    require (string d "original_ast_sha256"=
      Sha256.digest(string site "ast")) "guard original AST digest";
    ignore(hash(get d "receipt_sha256"));
    if verdict="aligned" then begin
      let selected=str(get d "normal_ast") in
      let selected_ast=Yojson.Safe.from_string selected in
      json_shape 0 selected_ast;
      require (same_shape selected_ast (`List [store]) &&
        list(get d "removed_statement_paths")=[`String "bil[1]"] &&
        string d "residual"="alignment-fault-refuted-under-premises")
        "guard checked normal BIL";
      require (string d "normal_ast_sha256"=Sha256.digest selected)
        "guard selected AST digest";
      let source=M.find at capture_sites in
      let ordinary=M.find at i.instructions in
      let is_load=load_encoding(string site "bytes_hex")in
      let expected_uses=List.fold_left (fun acc n ->
        S.add ("gpr:rsp:"^string_of_int n) acc)
        (if is_load then S.of_list["state:other";"memory:any"]else S.singleton "state:other")
        (List.init 8 Fun.id) in
      require (string source "projection"="bap-bit-provenance-v8")
        "guard normal producer profile";
      require (string source "status"="projected" &&
        string source "quality"="external_lift")
        "guard normal semantic status/quality";
      require (string source "bytes"=string site "bytes_hex" &&
        get source "ast_sha256"=get d "original_ast_sha256" &&
        get source "helper_sha256"=get producer "helper_sha256" &&
        get source "runtime_sha256"=get producer "runtime_sha256")
        "guard normal capture/BIL identity";
      let candidate_fall=set ~addr:true
        (get (get site "control") "fall") in
      require (ordinary.kind="ordinary" &&
        S.equal ordinary.fall candidate_fall &&
        S.is_empty ordinary.targets && ordinary.complete)
        "guard normal control summary";
      require (S.equal ordinary.may (S.singleton(if is_load then "state:other"else "memory:any")) &&
        S.is_empty ordinary.must) "guard normal write summary";
      require (S.equal ordinary.uses expected_uses)
        ("guard normal read summary: actual=" ^
          String.concat "," (S.elements ordinary.uses))
    end else begin
      require (get d "normal_ast"=`Null &&
        get d "normal_ast_sha256"=`Null &&
        list(get d "removed_statement_paths")=[])
        "guard unproved normal selection";
      (match M.find_opt at capture_sites with
       | None -> ()
       | Some source ->
         let instruction=M.find at i.instructions in
         stopped_guard i source at instruction)
    end;
    S.add at seen) S.empty (list(get report "guards")) in
  let expected=M.fold (fun at site seen ->
    if recognized site<>None then S.add at seen else seen) candidates S.empty in
  require (S.equal decisions expected) "guard decision coverage";
  end in
  let request_digest=value_hash normalized in
  require (string report "final_request_sha256"=request_digest)
    "guard final normalized request digest";
  List.iter (fun d ->
    let without=replace_field d "receipt_sha256" (`String "") in
    let digest=digest_array [
      `String "ariadne-guard-receipt/v2";get report "checker_sha256";
      get report "intent_id";get report "candidate_graph_sha256";
      get input "candidate_epoch";get input "model_version";
      get input "model_sha256";
      ordered_list ordered_premise (get input "premises");
      ordered_limits(get input "limits");
      ordered_list ordered_transfer (get report "transfers");
      ordered_list ordered_fact (get report "facts");get report "stop";
      get report "final_request_sha256";ordered_decision without] in
    require (string d "receipt_sha256"=digest) "guard receipt digest"
  ) (list(get report "guards"));
  let receipt_digests=List.map (fun d -> get d "receipt_sha256")
    (list(get report "guards")) |> List.sort compare in
  let analysis_id=digest_array [
    `String "ariadne-guard-analysis/v2";get report "intent_id";
    get report "final_request_sha256";`List receipt_digests] in
  require (string capture "query_id"=analysis_id)
    "guard capture analysis identity";
  i,capture_sites

let admit input snapshot=
  if string(get input "guard_admission")"schema"="ariadne.guard-admission/v1" then
    Legacy_guard.admit input snapshot
  else
    try admit_current input snapshot with
    | Yojson.Json_error _->raise(Invalid "guard malformed original BIL JSON")
    | Failure _->raise(Invalid "guard malformed source scalar")
