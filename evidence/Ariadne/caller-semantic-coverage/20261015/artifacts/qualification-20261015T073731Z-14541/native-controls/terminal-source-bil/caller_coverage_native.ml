(* Independent native source-rule controls.  This driver does not replace the
   full captured-input admission checks exercised by the wire controls. *)
open Recovery
let replace=Guard.replace_field
let root=Sys.getenv "ARIADNE_CALLER_SOURCE_ROOT"
let fixtures=Yojson.Safe.from_file(root^"/tests/bap/fixtures/caller-coverage/dump-four-shapes.json")
let raw=Yojson.Safe.from_file(root^"/tests/bap/fixtures/caller-coverage/raw-bap-observations.json")
let find document id=List.find(fun row->string row "id"=id)(list(get document "cases"))
let rec reorder=function
  | `Assoc rows->`Assoc(List.rev_map(fun(key,value)->key,reorder value)rows)
  | `List rows->`List(List.map reorder rows)
  | value->value
let ast source transform=
  replace source "ast" (`String(Yojson.Safe.to_string(transform(Yojson.Safe.from_string(string source "ast")))))
let terminal id=
  let case=find fixtures id and observation=find raw id in
  let original=get case "bap_original" in
  let source=replace original "control"(replace(get original "control")"complete"(`Bool true))in
  let bap=get observation "raw_bap" and reference=get case "llvm_and_preparation" in
  let record=string reference "decoder_record" in
  let record=if id="int3" then String.concat " "(List.map(fun text->
    if text="unsupported" then "ok" else text)(Terminal.tokens record))else record in
  let record=if id="int3" then
    let parts=Terminal.tokens record in
    String.concat " "(List.mapi(fun index text->if index=List.length parts-2 then "stop"else text)parts)
    else record in
  let rule,exception_=match id with "int3"->"int3-exception/v1",3
    |"ud2"->"ud2-empty-lift/v1",6|_->"ud1-pinned-extent/v1",6 in
  let receipt=`Assoc["schema",`String "ariadne.normal-terminal/v1";
    "rule",`String rule;"site",get source "site";"bytes_hex",get source "bytes_hex";
    "ast_sha256",`String(Terminal.Sha256.digest(string source "ast"));"exception",`Int exception_;
    "annotation",`String "exception-exit";
    "resumption",`String "exception-resumption-outside-local-scope";
    "bap",`Assoc["status",get bap "status";"length",get bap "length";
      "bytes_hex",get bap "bytes";"opcode",get bap "opcode";"properties",get bap "properties"];
    "reference",`Assoc["length",get reference "length";"opcode",get reference "opcode";
      "control",`String "stop";"decoder_record",`String record]]in source,receipt
let digest source receipt=replace receipt "ast_sha256"(`String(Terminal.Sha256.digest(string source "ast")))
let source_check (source,receipt)=Terminal.validate_source source receipt
let terminal_negative variant=
  let source,receipt=terminal "int3"in
  match variant with
  |"bytes"->let source=replace source "bytes_hex"(`String "90")in
    source,replace(replace receipt "bytes_hex"(`String "90"))"bap"
      (replace(get receipt "bap")"bytes_hex"(`String "90"))
  |"prefixed"->let source=replace source "bytes_hex"(`String "66cc")in
    source,replace receipt "bytes_hex"(`String "66cc")
  |"extra-effect"->let source=ast source(fun bil->`List(list bil@list bil))in source,digest source receipt
  |"conditional"->let source=ast source(fun bil->`List[`Assoc["kind",`String "if";
      "condition",`Assoc["kind",`String "int";"value",`String "1:1u"];"yes",bil;"no",`List[]]])in
    source,digest source receipt
  |"exception"->let source=ast source(fun _->`List[`Assoc["kind",`String "exception";"number",`Int 1]])in
    source,digest source receipt
  |"bap-extent"->source,replace receipt "bap"(replace(get receipt "bap")"length"(`Int 2))
  |"bap-opcode"->source,replace receipt "bap"(replace(get receipt "bap")"opcode"(`String "NOOP"))
  |"bap-properties"->source,replace receipt "bap"(replace(get receipt "bap")"properties"
      (replace(get(get receipt "bap")"properties")"control"(`Bool true)))
  |"annotation"->source,replace receipt "annotation"(`String "")
  |"resumption"->source,replace receipt "resumption"(`String "")
  |"normal-successor"->replace source "control"(replace(get source "control")"fall"
      (`List[`String "0x00007ff77440b30e"])),receipt
  |"incomplete"->replace source "control"(replace(get source "control")"complete"(`Bool false)),receipt
  |"unknown-rule"->source,replace receipt "rule"(`String "ordinary-empty-bil/v1")
  |"ast-digest"->source,replace receipt "ast_sha256"(`String(String.make 64 '0'))
  |"decoder-length"->source,replace receipt "reference"(replace(get receipt "reference")"length"(`Int 2))
  |"decoder-record"->source,replace receipt "reference"(replace(get receipt "reference")"decoder_record"
      (`String(string(get receipt "reference")"decoder_record"^" extra")))
  |_->raise(Invalid "unknown terminal mutation")
let load_source()=
  let source=get(find fixtures "movaps-load")"bap_original"in
  let next=Int64.add(Int64.of_string(string source "site"))
      (Int64.of_int(String.length(string source "bytes_hex")/2))in
  replace source "control"(`Assoc["kind",`String "ordinary";
    "fall",`List[`String(Printf.sprintf "0x%016Lx" next)];"targets",`List[];"complete",`Bool true])
let on_first transform source=ast source(function
  |`List(first::rest)->`List(transform first::rest)|_->raise(Invalid "load unit AST"))
let on_value transform=on_first(fun stmt->replace stmt "value"(transform(get stmt "value")))
let load_negative variant=
  let source=load_source()in match variant with
  |"direction"->replace source "bytes_hex"(`String "0f29b42440020000")
  |"destination"->on_first(fun stmt->replace stmt "var"(replace(get stmt "var")"name"(`String "YMM7")))source
  |"high-bank"->on_value(fun value->replace value "lhs"(replace(get value "lhs")"arg"
      (replace(get(get value "lhs")"arg")"var"
        (replace(get(get(get value "lhs")"arg")"var")"name"(`String "YMM7")))))source
  |"high-extent"->on_value(fun value->replace value "lhs"(replace(get value "lhs")"lo"(`Int 127)))source
  |"load-width"->on_value(fun value->replace value "rhs"(replace(get value "rhs")"arg"
      (replace(get(get value "rhs")"arg")"width"(`Int 64))))source
  |"load-address"->on_value(fun value->replace value "rhs"(replace(get value "rhs")"arg"
      (replace(get(get value "rhs")"arg")"addr"(`Assoc["kind",`String "var";
        "var",`Assoc["name",`String "RSP";"index",`Int 0;"virtual",`Bool false;
          "width",`Int 64;"type",`String "imm"]]))))source
  |"polarity"->ast source(function `List[first;check]->`List[first;
      replace(replace check "yes"(get check "no"))"no"(`List[])]|_->raise(Invalid "load AST"))
  |"extra-effect"->ast source(fun bil->`List(list bil@[List.hd(list bil)]))
  |_->raise(Invalid "unknown load mutation")
let recognize source=require(Guard.recognized source<>None)"guard load source not recognized"
let store_source()=
  let source=load_source()in
  let source=on_first(fun stmt->
    let payload=get(get(get stmt "value")"rhs")"arg"in
    replace(replace stmt "var"(get(get payload "mem")"var"))"value"
      (`Assoc["kind",`String "store";"width",`Int 128;"mem",get payload "mem";
        "addr",get payload "addr";"value",`Assoc["kind",`String "cast";"op",`Int 0;
          "width",`Int 128;"arg",`Assoc["kind",`String "var";"var",get stmt "var"]]]))source in
  replace source "bytes_hex"(`String "0f29b42440020000")
let stopped ?(decoded=false)()=
  let site="0x0000000000000010"in
  let locations=S.singleton "memory:any"in
  let instruction={kind="stop";fall=S.empty;targets=S.empty;complete=false;
    uses=locations;may=locations;must=S.empty}in
  let addresses=S.singleton site in
  let input={snapshot="unit";addresses;roots=addresses;locations;seeds=S.empty;
    captured=addresses;files=S.empty;trusted=S.empty;
    decodable=(if decoded then addresses else S.empty);binary=false;
    instructions=M.singleton site instruction}in
  Guard.stopped_guard input (`Assoc["quality",`String "opaque";
    "status",`String "guard-not-admitted"]) site instruction
(* Recompute carrier seals for semantic negatives. This avoids credit for a
   stale checksum when the independent source/effect replay should reject. *)
let seal wire=
  let report=get wire "guard_admission"in let input=get report "input"in
  let ordered=Guard.ordered_list in
  let intent=Guard.digest_array[`String "ariadne-guard-intent/v2";get input "snapshot";
    get input "artifact_sha256";get input "query_scope_sha256";get input "preparation_sha256";
    ordered Guard.ordered_root(get input "roots");get input "seeds";
    Guard.ordered_activation(get input "activation");ordered Guard.ordered_premise(get input "premises");
    get input "platform";get input "policy";get input "model_version";get input "model_sha256";
    Guard.ordered_producer(get input "producer");Guard.ordered_limits(get input "limits");
    Terminal.ordered_flow(get input "normal_flow")]in
  let edges=List.concat_map(fun source->let control=get source "control"and from=get source "site"in
    let kind=string control "kind"in
    let row kind to_=`Assoc["src",from;"dst",to_;"kind",`String kind]in
    let falls=List.map(row(if kind="call"then "summary"else if kind="conditional"then "fallthrough"else "next"))
      (list(get control "fall"))in
    falls@(if List.mem kind["conditional";"jump";"indirect"]then List.map
      (row(if kind="conditional"then "taken"else if kind="jump"then "jump"else "indirect"))
      (list(get control "targets"))else []))(list(get input "sites"))in
  let graph=Guard.digest_array[`String "ariadne-guard-candidate/v2";
    ordered Guard.ordered_root(get input "roots");get input "candidate_epoch";get input "closure_complete";
    get input "barriers";ordered Guard.ordered_site(get input "sites");`List edges;
    Terminal.ordered_flow(get input "normal_flow")]in
  let report=replace(replace(replace report "intent_id"(`String intent))
    "candidate_graph_sha256"(`String graph))"final_request_sha256"(`String(Guard.value_hash(get wire "normalized")))in
  let decisions=List.map(fun decision->let without=replace decision "receipt_sha256"(`String "")in
    let receipt=Guard.digest_array[`String "ariadne-guard-receipt/v2";get report "checker_sha256";
      get report "intent_id";get report "candidate_graph_sha256";get input "candidate_epoch";
      get input "model_version";get input "model_sha256";ordered Guard.ordered_premise(get input "premises");
      Guard.ordered_limits(get input "limits");ordered Guard.ordered_transfer(get report "transfers");
      ordered Guard.ordered_fact(get report "facts");get report "stop";get report "final_request_sha256";
      Guard.ordered_decision without]in replace decision "receipt_sha256"(`String receipt))
    (list(get report "guards"))in
  let report=replace report "guards"(`List decisions)in
  let analysis=Guard.digest_array[`String "ariadne-guard-analysis/v2";get report "intent_id";
    get report "final_request_sha256";`List(List.map(fun d->get d "receipt_sha256")decisions|>List.sort compare)]in
  let capture=get wire "capture"in let profile=string capture "semantic_profile"in
  let marker=":"^string report "profile"^":"in
  let rec index at=if at+String.length marker>String.length profile then raise(Invalid "wire guard marker")else
    if String.sub profile at(String.length marker)=marker then at else index(at+1)in
  let start=index 0+String.length marker in
  let profile=String.sub profile 0 start^Guard.hash_json(Guard.ordered_report report)^
    String.sub profile(start+64)(String.length profile-start-64)in
  let capture=replace(replace capture "query_id"(`String analysis))"semantic_profile"(`String profile)in
  replace(replace wire "guard_admission" report)"capture"capture
let with_normalized wire transform=replace wire "normalized"(transform(get wire "normalized"))
let first_instruction field value wire=with_normalized wire(fun normalized->replace normalized "instructions"
  (`List(match list(get normalized "instructions")with row::rest->replace row field value::rest
    |_->raise(Invalid "wire lacks instruction"))))
let without_terminal wire=
  let report=get wire "guard_admission"in let input=get report "input"in
  replace wire "guard_admission"(replace report "input"(replace input "normal_flow"
    (replace(get input "normal_flow")"terminals"(`List[]))))
let proof_unit capsule=
  exact capsule["schema";"guard_report";"normalized";"sources"];
  require(string capsule "schema"="ariadne.caller-proof-unit/v1")"caller proof unit schema";
  let report=get capsule "guard_report"and normalized=get capsule "normalized"in
  let input=get report "input"in let sources=List.fold_left(fun map source->
    M.add(string source "site")source map)M.empty(list(get capsule "sources"))in
  require(Guard.same_shape(get capsule "sources")(get input "sites"))"proof unit sources differ";
  let current=string report "schema"="ariadne.guard-admission/v2"in
  let terminals=if current then Terminal.validate_flow sources(get input "normal_flow")else S.empty in
  let request=Recovery.admit normalized(string input "snapshot")in
  require(string report "final_request_sha256"=Guard.value_hash normalized)"proof unit final request hash";
  S.iter(fun site->let instruction=M.find site request.instructions in
    require(instruction.kind="stop" && instruction.complete && S.is_empty instruction.fall &&
      S.is_empty instruction.targets && S.is_empty instruction.must &&
      S.equal instruction.uses request.locations && S.equal instruction.may request.locations &&
      S.mem site request.captured && S.mem site request.decodable)"proof unit terminal footprint")terminals;
  List.iter(fun transfer->let source=M.find(string transfer "site")sources in
    let pending=if current then Guard.recognized source<>None else Legacy_guard.recognized source<>None in
    let relation=if current then Guard.relation source pending else Legacy_guard.relation source pending in
    require(get transfer "relation"=`List(List.map(fun value->`Int value)relation) &&
      string transfer "bytes_sha256"=Guard.bytes_digest(string source "bytes_hex") &&
      string transfer "ast_sha256"=Guard.Sha256.digest(string source "ast") &&
      string transfer "relation_sha256"=Guard.digest_array[get transfer "rule";get transfer "relation"])
      "proof unit independent transfer replay";
    if pending then require(string transfer "rule"=(if current then Guard.pending_rule source else
      "pending-legacy128-movaps-rsp-identity/v1"))"proof unit pending rule")
    (list(get report "transfers"));
  let facts=List.fold_left(fun map fact->M.add(string fact "site")(Guard.mask(get fact "residues"))map)
    M.empty(list(get report "facts"))in
  List.iter(fun decision->let site=string decision "site"in let source=M.find site sources in
    let displacement,_,normal=match Guard.recognized source with Some value->value
      |None->raise(Invalid "proof unit guard shape")in
    let residues=M.find site facts in let addresses=Guard.shift residues displacement in
    let expected=if get report "stop"<>`Null then "unknown"else if residues=0 then "unreached"
      else if addresses=1 then "aligned"else if addresses land 1=0 then "misaligned"else "unknown"in
    require(string decision "verdict"=expected && get decision "input_residues"=`Int residues &&
      get decision "address_residues"=`Int addresses)"proof unit independent verdict replay";
    let instruction=M.find site request.instructions in
    if expected="aligned"then begin
      require(Guard.same_shape(Yojson.Safe.from_string(str(get decision "normal_ast")))(`List[normal]) &&
        instruction.kind="ordinary" && S.is_empty instruction.must && S.mem site request.decodable)
        "proof unit aligned normal selection";
      let load=Guard.load_encoding(string source "bytes_hex")in
      let uses=List.fold_left(fun set index->S.add("gpr:rsp:"^string_of_int index)set)
        (if load then S.of_list["state:other";"memory:any"]else S.singleton "state:other")
        (List.init 8 Fun.id)in
      require(S.equal instruction.uses uses && S.equal instruction.may
        (S.singleton(if load then "state:other"else "memory:any")))"proof unit aligned read/write selection"
    end else require(get decision "normal_ast"=`Null && instruction.kind="stop" &&
      not(S.mem site request.decodable) && not instruction.complete &&
      S.equal instruction.uses request.locations && S.equal instruction.may request.locations &&
      S.is_empty instruction.must)"proof unit unproved normal effect selection")
    (list(get report "guards"))
let cases=ref[]
let add name expected action=cases:= !cases@[name,expected,action]
let ()=
  List.iter(fun id->add("terminal-"^id)true(fun()->source_check(terminal id)))["int3";"ud2";"ud1"];
  List.iter(fun variant->add("terminal-"^variant)false(fun()->source_check(terminal_negative variant)))
    ["bytes";"prefixed";"extra-effect";"conditional";"exception";"bap-extent";"bap-opcode";
     "bap-properties";"annotation";"resumption";"normal-successor";"incomplete";"unknown-rule";
     "ast-digest";"decoder-length";"decoder-record"];
  let pairs=List.map terminal ["int3";"ud2";"ud1"]in
  let sources=List.fold_left(fun map(source,_)->M.add(string source "site")source map)M.empty pairs in
  let receipts=List.map snd pairs|>List.sort(fun a b->compare(string a "site")(string b "site"))in
  let flow=`Assoc["kind",`String "local_normal_completion";
    "scope",`String "local-normal-completion/v1";"terminals",`List receipts]in
  add "flow-original" true(fun()->ignore(Terminal.validate_flow sources flow));
  add "flow-reordered-carrier"true(fun()->ignore(Terminal.validate_flow sources(reorder flow));
    require(Terminal.ordered_flow flow=Terminal.ordered_flow(reorder flow))"typed flow key order");
  add "flow-unknown-scope"false(fun()->ignore(Terminal.validate_flow sources
    (replace flow "scope"(`String "whole-machine/v1"))));
  add "flow-duplicate"false(fun()->ignore(Terminal.validate_flow sources
    (replace flow "terminals"(`List(receipts@[List.hd receipts])))));
  List.iter(fun hex->add("ud1-extent-"^hex)true(fun()->
    let bytes=Terminal.bytes hex in require(Terminal.ud1_extent bytes<>None)"UD1 extent rejected";
    for length=0 to Array.length bytes-1 do
      require(Terminal.ud1_extent(Array.sub bytes 0 length)=None)"UD1 truncated extent accepted"
    done;
    require(Terminal.ud1_extent(Array.append bytes[|0|])=None)"UD1 extra extent accepted"))
    ["0fb9c0";"0fb900";"0fb90420";"0fb9042500000000";"0fb90500000000";
     "0fb94012";"0fb9842000000000";"670fb9c0";"670fb94012"];
  List.iter(fun hex->add("ud1-prefix-"^hex)false(fun()->
    require(Terminal.ud1_extent(Terminal.bytes hex)<>None)"unsupported UD1 prefix"))
    ["660fb9c0";"480fb9c0";"67670fb9c0";"f30fb9c0"];
  add "ud1-extra-extent"false(fun()->require(Terminal.ud1_extent
    (Terminal.bytes "670fb9401200")<>None)"UD1 extra extent rejected");
  add "movaps-load-original"true(fun()->recognize(load_source()));
  List.iter(fun variant->add("movaps-load-"^variant)false(fun()->recognize(load_negative variant)))
    ["direction";"destination";"high-bank";"high-extent";"load-width";"load-address";"polarity";"extra-effect"];
  add "legacy-load-declined"true(fun()->require(Legacy_guard.recognized(load_source())=None)
    "legacy store-only recognizer admitted load");
  add "legacy-load-admitted"false(fun()->require(Legacy_guard.recognized(load_source())<>None)
    "legacy store-only policy rejects load");
  add "legacy-store-original"true(fun()->require(Legacy_guard.recognized(store_source())<>None)
    "legacy store source not recognized");
  add "current-store-original"true(fun()->recognize(store_source()));
  add "stopped-guard-original"true(fun()->stopped());
  add "stopped-guard-premature-decode"false(fun()->stopped ~decoded:true());
  add "normalized-reordered-carrier"true(fun()->let value=`Assoc["z",`Assoc["b",`Int 1;"a",`Int 2];"a",`Int 3]in
    require(Guard.value_hash value=Guard.value_hash(reorder value))"normalized Value key order");
  (match Sys.getenv_opt "ARIADNE_CALLER_RECEIPT_DIR"with None->()|Some directory->
    List.iter(fun name->let path=directory^"/"^name^"-unit.json"in
      let capsule=Yojson.Safe.from_file path in add("unit-"^name)true(fun()->proof_unit capsule))
      ["terminal-int3";"terminal-ud2";"terminal-ud1";"movaps-load-aligned";
       "movaps-load-misaligned";"movaps-load-unknown";"movaps-store-aligned";"legacy-store-aligned"]);
  (match Sys.getenv_opt "ARIADNE_CALLER_WIRE_DIR" with None->()|Some directory->
    List.iter(fun name->let path=directory^"/"^name^"-guarded-wire.json"in
      if Sys.file_exists path then let wire=Yojson.Safe.from_file path in
      add("wire-"^name)true(fun()->ignore(Guard.admit wire(string(get wire "capture")"snapshot")));
      add("wire-reordered-"^name)true(fun()->let wire=reorder wire in
        ignore(Guard.admit wire(string(get wire "capture")"snapshot")));
      if List.mem name["int3";"ud2";"ud1"]then begin
        let check changed=let changed=seal changed in
          ignore(Guard.admit changed(string(get changed "capture")"snapshot"))in
        add("wire-missing-terminal-"^name)false(fun()->check(without_terminal wire));
        let locations=get(get wire "normalized")"locations"in
        add("wire-terminal-must-effect-"^name)false(fun()->check(first_instruction "must_defs"
          (`List[List.hd(list locations)])wire));
        add("wire-terminal-narrowed-uses-"^name)false(fun()->check(first_instruction "uses"(`List[])wire));
        add("wire-terminal-narrowed-may-"^name)false(fun()->check(first_instruction "may_defs"(`List[])wire));
        add("wire-terminal-incomplete-"^name)false(fun()->check(first_instruction "targets_complete"(`Bool false)wire))
      end)
    ["int3";"ud2";"ud1";"movaps-load-aligned";"movaps-load-misaligned";"movaps-load-unknown"]);
  let selected=if Array.length Sys.argv=3 && Sys.argv.(1)="--case"then Some Sys.argv.(2)else None in
  let rows=List.filter_map(fun(name,expected,action)->if selected<>None && selected<>Some name then None else
    let accepted,error=try action();true,`Null with
      Invalid error->false,`String error|Yojson.Json_error error->false,`String error in
    Some(`Assoc["case",`String name;"expected",`Bool expected;"accepted",`Bool accepted;
      "passed",`Bool(accepted=expected);"error",error])) !cases in
  require(rows<>[])"no selected native caller control";
  print_endline(Yojson.Safe.to_string(`List rows));
  if List.exists(fun row->get row "passed"<>`Bool true)rows then exit 1
