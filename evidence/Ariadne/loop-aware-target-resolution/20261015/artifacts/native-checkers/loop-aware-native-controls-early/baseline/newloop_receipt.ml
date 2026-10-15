(* Checker controls over source-bound reports exported by the Rust fixture test.
   These call the independent checker directly; production paired admission is
   qualified separately and is never bypassed by the application. *)
open Recovery
let read path=Yojson.Safe.from_file path
let replace=Guard.replace_field
let address_value value=match value with
  | `String text when String.length text=18 && String.sub text 0 2="0x"->address text
  | _->Capture.hx(Capture.uint value)
let graph path =
  fields(read path) |> List.fold_left(fun map(key,row)->
    let site=if String.length key>=2 && String.sub key 0 2="0x" then address key
      else Capture.hx(Capture.uint(`Intlit key)) in
    let addresses name=List.fold_left(fun seen value->S.add(address_value value)seen)
      S.empty(list(get row name)) in
    let instruction={kind=String.lowercase_ascii(string row "kind");
      fall=addresses "fall";targets=addresses "targets";complete=boolean(get row "complete");
      uses=set(get row "uses");may=set(get row "may_defs");must=set(get row "must_defs")} in
    M.add site instruction map) M.empty
let row report=List.hd(list(get report "resolutions"))
let receipt report=get(get(row report)"coverage")"receipt"
let with_row report transform=
  match list(get report "resolutions")with
  | first::rest->replace report "resolutions"(`List(transform first::rest))
  | _->raise(Invalid "unit report lacks resolution")
let with_receipt report transform=with_row report(fun row->
  replace row "coverage"(replace(get row "coverage")"receipt"(transform(receipt report))))
let first transform=function first::rest->transform first::rest|_->raise(Invalid "unit empty list")
let check ?(roots=S.empty) report instructions =
  let addresses=M.fold(fun site _ seen->S.add site seen)instructions S.empty in
  let input={snapshot=string report "snapshot";addresses;roots;locations=S.empty;
    seeds=S.empty;captured=addresses;files=S.empty;trusted=S.empty;decodable=addresses;
    binary=false;instructions} in
  let transfers=List.fold_left(fun map source->M.add(string source "site")source map)
    M.empty(list(get report "transfers")) in
  let sites=M.map(fun source->`Assoc["bytes",get source "bytes_hex";
    "ast_sha256",get source "ast_sha256"])transfers in
  let reads=List.fold_left(fun map source->M.add(string source "address"^":"^
    string_of_int(Capture.integer(get source "requested")))source map)
    M.empty(list(get report "data_reads")) in
  Loop_closure.validate input sites transfers reads report(row report)
let mutate_receipt name report=with_receipt report(fun proof->match name with
  | "entrance"->replace proof "entrances"(`List [])
  | "internal"->replace proof "internal_edges"(`List(List.tl(list(get proof "internal_edges"))))
  | "exit"->replace proof "exits"(`List(List.tl(list(get proof "exits"))))
  | "corridor"->replace proof "corridors"(`List(first(fun corridor->replace corridor "sites"
      (`List(List.tl(list(get corridor "sites")))))(list(get proof "corridors"))))
  | "base"->replace proof "table"(replace(get proof "table")"base"
      (`String(Capture.hx(Int64.add(Capture.uaddress(get(get proof "table")"base"))4L))))
  | "selector"->
    let table=get proof "table" in
    replace proof "assertions"(`List(List.map(fun assertion->
      if get assertion "site"=get table "load_site" then replace assertion "domains"
        (replace(get assertion "domains")(string table "selector_bank")
          (`Assoc["width",`Int 64;"kind",`Assoc["kind",`String "constant";
            "value",`String(Capture.hx 3L)]]))else assertion)(list(get proof "assertions"))))
  | "flags"->replace proof "assertions"(`List(List.map(fun assertion->
      replace assertion "flags"(`Assoc []))(list(get proof "assertions"))))
  | "bytes"->replace proof "source_refs"(`List(first(fun source->replace source "bytes_hex"
      (`String "90"))(list(get proof "source_refs"))))
  | "table"->replace proof "table"(replace(get proof "table")"entries"
      (`List(List.tl(list(get(get proof "table")"entries")))))
  | "snapshot"->replace proof "snapshot"(`String(string proof "snapshot"^"x"))
  | "model"->replace proof "model_sha256"(`String(String.make 64 '0'))
  | "engine"->replace proof "engine_sha256"(`String(String.make 64 '0'))
  | "graph"->replace proof "graph_sha256"(`String(String.make 64 '0'))
  | _->raise(Invalid "unknown receipt mutation"))
let mutate_assertion report select change=with_receipt report(fun proof->
  replace proof "assertions"(`List(List.map(fun assertion->
    if select proof assertion then change proof assertion else assertion)
      (list(get proof "assertions")))))
let first_assertion proof assertion=
  get assertion "site"=get(List.hd(list(get proof "assertions")))"site"
let malformed_domain report width=mutate_assertion report first_assertion(fun proof assertion->
  let bank=string(get proof "table")"base_bank" in
  replace assertion "domains"(replace(get assertion "domains")bank
    (replace(get(get assertion "domains")bank)"width"(`Int width))))
let malformed_flag report term=mutate_assertion report first_assertion(fun _ assertion->
  replace assertion "flags"(`Assoc["CF:0:false",term]))
let entrance_state report=with_receipt report(fun proof->
  let entrance=List.hd(list(get proof "entrances")) in
  let selector=string(get proof "table")"selector_bank" in
  let greatest=List.fold_left(fun high target->Capture.umax high(Capture.uaddress target))0L
    (list(get(row report)"targets")) in
  replace proof "assertions"(`List(List.map(fun assertion->
    if get assertion "site"=get entrance "to" then replace assertion "domains"
      (replace(get assertion "domains")selector(`Assoc["width",`Int 64;
        "kind",`Assoc["kind",`String "unsigned_interval";"lower",`String(Capture.hx 0L);
          "upper",`String(Capture.hx greatest)]]))else assertion)
    (list(get proof "assertions")))))
let preservation_state report instructions=with_receipt report(fun proof->
  let table=get proof "table" and load=string(get proof "table")"load_site" in
  let after=S.choose(M.find load instructions).fall in
  let bytes=string(List.hd(list(get table "entries")))"bytes_hex" in
  let offset=Capture.signed(Capture.data_value bytes 4)32 in
  replace proof "assertions"(`List(List.map(fun assertion->
    if string assertion "site"=after then replace assertion "domains"
      (replace(get assertion "domains")(string table "selector_bank")
        (`Assoc["width",`Int 64;"kind",`Assoc["kind",`String "constant";
          "value",`String(Capture.hx offset)]]))else assertion)
    (list(get proof "assertions")))))
let ()=
  try
    let directory=match Sys.getenv_opt "ARIADNE_LOOP_RECEIPT_DIR" with
      Some value->value|None->raise(Invalid "ARIADNE_LOOP_RECEIPT_DIR required") in
    let selected=if Array.length Sys.argv=3 && Sys.argv.(1)="--case"
      then Some Sys.argv.(2) else None in
    let results=ref [] in
    let run ?(roots=S.empty) name expect report instructions=
      if selected=None || selected=Some name then begin
        let accepted,error=try check ~roots report instructions;true,`Null with
          | Invalid why->false,`String why
          | Not_found->false,`String "missing checker field"
          | Failure why->false,`String why in
        results:= !results@[`Assoc["case",`String name;"expected_acceptance",`Bool expect;
          "accepted",`Bool accepted;"passed",`Bool(accepted=expect);"error",error]]
      end in
    List.iter(fun name->let prefix=Filename.concat directory name in
      run(name^"-original")true(read(prefix^"-target-report.json"))(graph(prefix^"-instructions.json")))
      ["da09";"dadd"];
    let original=read(Filename.concat directory "da09-target-report.json") and
        instructions=graph(Filename.concat directory "da09-instructions.json") in
    List.iter(fun name->run name false(mutate_receipt name original)instructions)
      ["entrance";"internal";"exit";"corridor";"base";"selector";"flags";"bytes";
       "table";"snapshot";"model";"engine";"graph"];
    run "zero-width" false(malformed_domain original 0)instructions;
    run "oversized-width" false(malformed_domain original 65)instructions;
    run "narrow-physical-input" false(malformed_flag original(Capture.tinput 1 "R8:0:false"))instructions;
    run "unknown-flag" false(malformed_flag original(Capture.tunknown 1))instructions;
    run "mismatched-binary-width" false(malformed_flag original
      (Capture.term 1 "binary"["op",`Int 3;"left",Capture.tinput 1 "R8:0:false";
        "right",Capture.tconst 64 9L]))instructions;
    List.iter(fun key->run("zero-"^key)false
      (replace original "limits"(replace(get original "limits")key(`Int 0)))instructions)
      ["max_steps";"max_values";"max_rounds";"max_elapsed_ms"];
    run "entrance-state" false(entrance_state original)instructions;
    run "preservation-state" false(preservation_state original instructions)instructions;
    let proof=receipt original in
    let region=set ~addr:true(get proof "region") in
    let first=address(str(List.hd(list(get proof "region")))) in
    let instruction=M.find first instructions in
    run "memory-effect" false original(M.add first
      {instruction with may=S.add "memory:any" instruction.may}instructions);
    run "base-clobber" false original(M.add first
      {instruction with may=S.add "gpr:rdx:0" instruction.may}instructions);
    run "call-effect" false original(M.add first {instruction with kind="call"}instructions);
    run ~roots:(S.singleton first) "root-bypass" false original instructions;
    let branch destination={kind="ordinary";fall=S.singleton destination;targets=S.empty;
      complete=true;uses=S.empty;may=S.empty;must=S.empty} in
    let entrance=List.hd(list(get proof "entrances")) in
    run "hidden-entrance" false original(M.add "0x0000000000000100"
      (branch(string entrance "to"))instructions);
    let corridor=List.hd(list(get proof "corridors")) in
    let middle=address(str(List.nth(list(get corridor "sites"))1)) in
    run "hidden-corridor-entrance" false original(M.add "0x0000000000000101"
      (branch middle)instructions);
    let missing=with_row original(fun row->replace row "paths"(`List(List.map(fun path->
      replace path "entries"(`List(List.filter(fun entry->
        Capture.uaddress(get entry "index")<>3L)(list(get path "entries")))))
      (list(get row "paths"))))) in
    run "missing-old-witness" false missing instructions;
    let partial=with_row original(fun row->replace(replace row "complete"(`Bool false))
      "unresolved"(`List[`String "candidate-epoch-changed"])) in
    require(get(row partial)"targets"=get(row original)"targets")"partial lost known targets";
    run "partial-retains-targets" true partial instructions;
    let from,to_,taken=List.find(fun(from,to_,_)->S.mem from region && not(S.mem to_ region) &&
      (M.find from instructions).kind="conditional")
      (List.map Loop_closure.parse_edge(list(get proof "exits"))) in
    let changed=Capture.hx(Int64.add(Int64.of_string to_)1L) in
    let control=M.find from instructions in
    let altered_graph=M.add from {control with targets=S.singleton changed}instructions in
    let altered_report=with_receipt original(fun proof->replace proof "exits"(`List(List.map(fun edge->
      if Loop_closure.parse_edge edge=(from,to_,taken) then replace edge "to"(`String changed)
      else edge)(list(get proof "exits"))))) in
    run "original-conditional" false altered_report altered_graph;
    require(!results<>[])"unknown loop checker case";
    print_endline(Yojson.Safe.to_string(`List !results));
    if List.exists(fun row->not(boolean(get row "passed")))!results then exit 1
  with Invalid why->prerr_endline why;exit 2
