(* Independent control-only local-normal terminal receipt replay. *)
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
    "native terminal SHA-256 self-test"

let ordered value keys=`Assoc(List.map(fun key->key,get value key)keys)
let ordered_properties value=ordered value
  ["jump";"conditional";"indirect";"call";"return";"control"]
let ordered_bap value=`Assoc["status",get value "status";"length",get value "length";
  "bytes_hex",get value "bytes_hex";"opcode",get value "opcode";
  "properties",ordered_properties(get value "properties")]
let ordered_reference value=ordered value ["length";"opcode";"control";"decoder_record"]
let ordered_receipt value=`Assoc[
  "schema",get value "schema";"rule",get value "rule";"site",get value "site";
  "bytes_hex",get value "bytes_hex";"ast_sha256",get value "ast_sha256";
  "exception",get value "exception";"annotation",get value "annotation";
  "resumption",get value "resumption";"bap",ordered_bap(get value "bap");
  "reference",ordered_reference(get value "reference")]
let ordered_flow value=`Assoc["kind",get value "kind";"scope",get value "scope";
  "terminals",`List(List.map ordered_receipt(list(get value "terminals")))]
let nonnegative=function `Int n when n>=0->n|_->raise(Invalid "terminal nonnegative integer")
let bytes text=
  require(String.length text>0 && String.length text<=30 && String.length text mod 2=0 &&
    string_all(fun c->(c>='0'&&c<='9')||(c>='a'&&c<='f'))text)
    "terminal captured byte encoding";
  Array.init(String.length text/2)(fun n->int_of_string("0x"^String.sub text(n*2)2))
let decimal text=
  require(text<>"" && string_all(fun c->c>='0'&&c<='9')text)"terminal decimal";
  let value=ref 0L in String.iter(fun c->let digit=Int64.of_int(Char.code c-48) in
    require(Int64.unsigned_compare !value
      (Int64.unsigned_div(Int64.sub Int64.minus_one digit)10L)<=0)"terminal decimal overflow";
    value:=Int64.add(Int64.mul !value 10L)digit)text;!value
let signed text=
  let digits=if String.length text>0 && (text.[0]='-'||text.[0]='+')
    then String.sub text 1(String.length text-1)else text in
  require(digits<>"" && string_all(fun c->c>='0'&&c<='9')digits)"terminal signed decimal";
  try Int64.of_string text with Failure _->raise(Invalid "terminal signed decimal overflow")
let tokens text=
  let whitespace=function ' '| '\t'|'\n'|'\r'|'\011'|'\012'->true|_->false in
  let rec scan at start acc=
    if at=String.length text then List.rev(if at>start then String.sub text start(at-start)::acc else acc)
    else if whitespace text.[at] then
      scan(at+1)(at+1)(if at>start then String.sub text start(at-start)::acc else acc)
    else scan(at+1)start acc in scan 0 0 []
let name text=text<>"" && String.length text<=96 && string_all(fun c->
  (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c='_')text
let reference_facts site expected_length reference=
  exact reference ["length";"opcode";"control";"decoder_record"];
  let text=string reference "decoder_record" in
  require(String.length text<4096)"terminal decoder record budget";
  let input=ref(tokens text) in
  let take()=match !input with x::xs->input:=xs;x|[]->raise(Invalid "terminal truncated decoder record") in
  let count()=let text=take()in let n=decimal text in
    require(Int64.unsigned_compare n 32L<=0)"terminal decoder count";Int64.to_int n in
  require(take()="v2")"terminal decoder schema";
  let opcode=take()in require(name opcode)"terminal decoder opcode";
  let operands=count()in
  for _=1 to operands do
    let operand=take()in
    if String.length operand>=2 && String.sub operand 0 2="r:" then
      require(name(String.sub operand 2(String.length operand-2)))"terminal decoder register"
    else if String.length operand>=2 && String.sub operand 0 2="i:" then
      ignore(signed(String.sub operand 2(String.length operand-2)))
    else require(operand="x:unsupported")"terminal decoder operand"
  done;
  let defs=count()in require(defs<=operands)"terminal decoder definition count";
  let flags=count()in require(flags<=7)"terminal decoder descriptor flags";
  for _=1 to 2 do for _=1 to count()do require(name(take()))"terminal decoder implicit register"done done;
  for index=0 to operands-1 do let tied=signed(take())in
    require(tied>=(-1L) && tied<Int64.of_int operands && tied<>Int64.of_int index)
      "terminal decoder tied operand"done;
  let decoded_site=decimal(take())in let status=take()in let length=decimal(take())in
  let control=take()in let target=take()in
  require(!input=[] && decoded_site=Int64.of_string site && status="ok" &&
    length=Int64.of_int expected_length && expected_length>=1 && expected_length<=15 &&
    nonnegative(get reference "length")=expected_length &&
    string reference "opcode"=opcode && string reference "control"="stop" &&
    control="stop" && target="-")"terminal independent reference facts";
  opcode
let ud1_extent data=
  let length=Array.length data in
  let prefix=if length>0 && data.(0)=0x67 then 1 else 0 in
  if length<prefix+3 || data.(prefix)<>0x0f || data.(prefix+1)<>0xb9 then None else
  let modrm=data.(prefix+2)in let mode=modrm lsr 6 and rm=modrm land 7 in
  let extent=ref(prefix+3)in
  let valid=ref true in
  if mode<>3 && rm=4 then begin
    if !extent>=length then valid:=false else begin
      let sib=data.(!extent)in incr extent;
      if mode=0 && sib land 7=5 then extent:= !extent+4
    end
  end else if mode=0 && rm=5 then extent:= !extent+4;
  if mode=1 then incr extent else if mode=2 then extent:= !extent+4;
  if !valid && !extent<=length then Some(prefix,mode)else None
let validate_source source receipt=
  exact receipt ["schema";"rule";"site";"bytes_hex";"ast_sha256";"exception";
    "annotation";"resumption";"bap";"reference"];
  let site=address(string receipt "site")in
  require(string receipt "schema"="ariadne.normal-terminal/v1" &&
    string receipt "annotation"="exception-exit" &&
    string receipt "resumption"="exception-resumption-outside-local-scope")
    "terminal rule scope or exception annotation";
  let control=get source "control"in
  require(string source "site"=site && get source "bytes_hex"=get receipt "bytes_hex" &&
    boolean(get source "opaque") && string control "kind"="stop" &&
    get control "complete"=`Bool true && get control "fall"=`List [] &&
    get control "targets"=`List [])"terminal candidate has normal successor or unsupported effects";
  let full=string receipt "bytes_hex"in let captured=bytes full in
  let ast=string source "ast"in
  require(string receipt "ast_sha256"=Sha256.digest ast)"terminal original AST digest";
  let bil=try Yojson.Safe.from_string ast with Yojson.Json_error _->
    raise(Invalid "terminal malformed original BIL")in json_shape 0 bil;ignore(list bil);
  let bap=get receipt "bap"in exact bap ["status";"length";"bytes_hex";"opcode";"properties"];
  let properties=get bap "properties"in
  exact properties ["jump";"conditional";"indirect";"call";"return";"control"];
  require(string bap "status"="decoded" && List.for_all(fun(_,value)->not(boolean value))(fields properties))
    "terminal original BAP properties";
  let consumed=string bap "bytes_hex"in
  require(Array.length(bytes consumed)=nonnegative(get bap "length"))"terminal BAP consumed extent";
  let reference=reference_facts site(Array.length captured)(get receipt "reference")in
  (match string receipt "rule" with
  | "int3-exception/v1"->
    require(full="cc" && consumed=full && string bap "opcode"="INT3" &&
      reference="INT3" && get receipt "exception"=`Int 3 &&
      (match bil with `List[statement]->exact statement ["kind";"number"];
        string statement "kind"="exception" && get statement "number"=`Int 3|_->false))
      "terminal INT3 source rule"
  | "ud2-empty-lift/v1"->
    require(full="0f0b" && consumed=full && string bap "opcode"="TRAP" &&
      reference="TRAP" && get receipt "exception"=`Int 6 && bil=`List [])
      "terminal UD2 source rule"
  | "ud1-pinned-extent/v1"->
    let prefix,mode=match ud1_extent captured with Some shape->shape|None->
      raise(Invalid "terminal full UD1 extent")in
    require(string bap "opcode"="UD2B" && get receipt "exception"=`Int 6 &&
      bil=`List [] && consumed=String.sub full 0((prefix+2)*2) &&
      reference=(if mode=3 then "UD1Lr"else "UD1Lm"))
      "terminal pinned UD1 consumed extent"
  | _->raise(Invalid "terminal unknown rule"))
let validate_flow sources evidence=
  exact evidence ["kind";"scope";"terminals"];
  require(string evidence "kind"="local_normal_completion" &&
    string evidence "scope"="local-normal-completion/v1")"terminal normal-flow scope";
  let rows=list(get evidence "terminals")in
  let sites=List.map(fun receipt->address(string receipt "site"))rows in
  require(sites=List.sort_uniq String.compare sites)"terminal receipt order or duplicate";
  List.iter(fun receipt->let site=string receipt "site"in
    let source=match M.find_opt site sources with Some source->source|None->
      raise(Invalid "terminal source absent from candidate")in
    validate_source source receipt)rows;
  List.fold_left(fun set site->S.add site set)S.empty sites
