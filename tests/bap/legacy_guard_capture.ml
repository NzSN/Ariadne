(* Full legacy guard admission over conservative widening of an actual retained
   source-bound fixture. Source instruction bytes/BIL remain unchanged. *)
open Recovery
let replace=Legacy_guard.replace_field
let map_rows field select change value=replace value field(`List(List.map(fun row->
  if select row then change row else row)(list(get value field))))
let fixture()=
  let root=Sys.getenv "ARIADNE_CALLER_SOURCE_ROOT"in
  Yojson.Safe.from_file(root^"/evidence/Ariadne/loop-aware-target-resolution/20261015/artifacts/validation-20261015T050857/passing-combined-wire.json")
let derive projection=
  let original=fixture()in let report=get original "guard_admission"and capture=get original "capture"in
  let input=get report "input"and normalized=get original "normalized"in
  let source=List.find(fun row->string(get row "control")"kind"="ordinary" &&
    Legacy_guard.recognized row=None)(list(get input "sites"))in
  let site=string source "site"in
  let is_source row=string row "site"=site and is_address row=string row "address"=site in
  let input=map_rows "sites"is_source(fun row->replace row "opaque"(`Bool true))input in
  let top=`List(List.init 16(fun _->`Int Legacy_guard.top))in
  let transfers=List.map(fun row->if is_source row then
    let rule=`String "opaque-rsp-havoc/v1"in
    replace(replace(replace row "rule"rule)"relation"top)"relation_sha256"
      (`String(Legacy_guard.digest_array[rule;top]))else row)(list(get report "transfers"))in
  let facts=List.map(fun row->replace row "residues"(`Int Legacy_guard.top))(list(get report "facts"))in
  let locations=get normalized "locations"in
  let normalized=map_rows "instructions"is_address(fun row->
    replace(replace(replace row "uses"locations)"may_defs"locations)"must_defs"(`List[]))normalized in
  let capture=map_rows "sites"is_address(fun row->replace(replace(replace row "status"
    (`String "opaque-ordinary"))"quality"(`String "opaque"))"projection"(`String projection))capture in
  let normalized,capture,guards=List.fold_left(fun(normalized,capture,guards)decision->
    let guarded=string decision "site"in
    let normalized=map_rows "instructions"(fun row->string row "address"=guarded)(fun row->
      replace(replace(replace(replace(replace(replace(replace row "kind"(`String "stop"))
        "fall"(`List[]))"targets"(`List[]))"targets_complete"(`Bool false))"uses"locations)
        "may_defs"locations)"must_defs"(`List[]))normalized in
    let normalized=replace normalized "decodable"(`List(List.filter(fun at->str at<>guarded)
      (list(get normalized "decodable"))))in
    let capture=map_rows "sites"(fun row->string row "address"=guarded)(fun row->
      replace(replace row "status"(`String "guard-not-admitted"))"quality"(`String "opaque"))capture in
    let decision=replace(replace(replace(replace(replace(replace(replace decision "verdict"(`String "unknown"))
      "input_residues"(`Int Legacy_guard.top))"address_residues"(`Int Legacy_guard.top))
      "normal_ast"`Null)"normal_ast_sha256"`Null)"removed_statement_paths"(`List[]))
      "residual"(`String "normal-or-alignment-fault-unresolved")in
    normalized,capture,guards@[decision]) (normalized,capture,[])(list(get report "guards"))in
  let normalized=Guard.canonical_value normalized in
  let edges=List.concat_map(fun row->let c=get row "control"and src=get row "site"in
    let kind=string c "kind"in let edge kind dst=`Assoc["src",src;"dst",dst;"kind",`String kind]in
    List.map(edge(if kind="call"then "summary"else if kind="conditional"then "fallthrough"else "next"))
      (list(get c "fall"))@(if List.mem kind["conditional";"jump";"indirect"]then
      List.map(edge(if kind="conditional"then "taken"else if kind="jump"then "jump"else "indirect"))
      (list(get c "targets"))else []))(list(get input "sites"))in
  let graph=Legacy_guard.digest_array[`String "ariadne-guard-candidate/v1";
    Legacy_guard.ordered_list Legacy_guard.ordered_root(get input "roots");get input "candidate_epoch";
    get input "closure_complete";get input "barriers";
    Legacy_guard.ordered_list Legacy_guard.ordered_site(get input "sites");`List edges]in
  let report=replace(replace(replace(replace(replace(replace report "input"input)
    "candidate_graph_sha256"(`String graph))"transfers"(`List transfers))"facts"(`List facts))
    "guards"(`List guards))"final_request_sha256"(`String(Legacy_guard.hash_json normalized))in
  let guards=List.map(fun decision->let without=replace decision "receipt_sha256"(`String "")in
    let receipt=Legacy_guard.digest_array[`String "ariadne-guard-receipt/v1";get report "checker_sha256";
      get report "intent_id";get report "candidate_graph_sha256";get input "candidate_epoch";
      get input "model_version";get input "model_sha256";
      Legacy_guard.ordered_list Legacy_guard.ordered_premise(get input "premises");
      Legacy_guard.ordered_limits(get input "limits");
      Legacy_guard.ordered_list Legacy_guard.ordered_transfer(get report "transfers");
      Legacy_guard.ordered_list Legacy_guard.ordered_fact(get report "facts");get report "stop";
      get report "final_request_sha256";Legacy_guard.ordered_decision without]in
    replace decision "receipt_sha256"(`String receipt))guards in
  let report=replace report "guards"(`List guards)in
  let query=Legacy_guard.digest_array[`String "ariadne-guard-analysis/v1";get report "intent_id";
    get report "final_request_sha256";`List(List.map(fun d->get d "receipt_sha256")guards|>List.sort compare)]in
  let capture=replace(replace capture "query_id"(`String query))"semantic_profile"
    (`String("legacy-opaque-capture-regression:bap-guard-admission-v1:"^
      Legacy_guard.hash_json(Legacy_guard.ordered_report report)))in
  `Assoc["normalized",normalized;"capture",capture;"guard_admission",report]
let ()=
  let selected=if Array.length Sys.argv=3 && Sys.argv.(1)="--case"then Some Sys.argv.(2)else None in
  let rows=List.filter_map(fun(name,projection,expected)->if selected<>None&&selected<>Some name then None else
    let wire=derive projection in
    let accepted,error=try ignore(Legacy_guard.admit wire(string(get wire "capture")"snapshot"));true,`Null
      with Invalid message->false,`String message in
    Some(`Assoc["case",`String name;"accepted",`Bool accepted;"expected",`Bool expected;
      "passed",`Bool(accepted=expected);"error",error]))
    ["legacy-opaque-v7","bap-bit-provenance-v7",true;"legacy-opaque-v8","bap-bit-provenance-v8",false]in
  require(rows<>[])"no legacy capture regression selected";
  print_endline(Yojson.Safe.to_string(`List rows));
  if List.exists(fun row->get row "passed"<>`Bool true)rows then exit 1
