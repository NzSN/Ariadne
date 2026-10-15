(* Independent admission for joint captured target/guard preparation.
   The candidate is a proof graph, never the committed ordinary effect graph. *)
open Recovery
let profile = "captured-guarded-targets/v3"
let version = "ariadne.guarded-target-resolution/v3"
let rec canonical = function
  | `Assoc rows -> `Assoc (List.map (fun (key,value) -> key,canonical value) rows
      |> List.sort (fun (a,_) (b,_) -> compare a b))
  | `List rows -> `List (List.map canonical rows)
  | value -> value
let hash_json value = Guard.hash_json (canonical value)
let transport_query_current snapshot input =
  let bytes=Buffer.create 512 in
  Buffer.add_string bytes "ariadne.bap-core-query/v1\000";
  List.iter (fun text ->
    let length=Int64.of_int(String.length text) in
    for byte=7 downto 0 do
      Buffer.add_char bytes (Char.chr(Int64.to_int(Int64.logand
        (Int64.shift_right_logical length (byte*8)) 255L)))
    done;
    Buffer.add_string bytes text)
    [snapshot;"recovery";profile;Guard.encoded(canonical input)];
  Guard.Sha256.digest(Buffer.contents bytes)
let same = Guard.same_shape
let ends text suffix = let n=String.length text and m=String.length suffix in
  n>=m && String.sub text (n-m) m=suffix
let control_of_instruction row = `Assoc [
  "kind",get row "kind";"fall",get row "fall";
  "targets",get row "targets";"complete",get row "targets_complete"]
let unsigned_json value =
  if Int64.unsigned_compare value (Int64.of_int max_int)<=0 then
    `Int(Int64.to_int value) else `Intlit(Printf.sprintf "%Lu" value)
let resolver_graph_hash candidate =
  let roots=List.map (fun value -> unsigned_json(Int64.of_string(address(str value))))
      (list(get candidate "entry_points")) in
  let rows=List.map (fun row ->
    let kind=String.capitalize_ascii(string row "kind") in
    `List [get row "address";`String kind;get row "fall";get row "targets";
      get row "uses";get row "may_defs";get row "must_defs"])
      (list(get candidate "instructions")) in
  let legacy=hash_json (`List [`List roots;`List rows]) in
  let completeness=List.map(fun row->`List[get row "address";get row "targets_complete"])
    (list(get candidate "instructions")) in
  hash_json(`List[`String legacy;`List completeness])
(* Reconstruct only source control targets. Effects and call/return ABI remain
   under their existing producer trust contracts; a projected register jump
   cannot be renamed as a direct edge by resealing caller metadata. *)
let rec original_targets site depth env statements =
  require (depth<=64) "composition source control depth";
  List.fold_left (fun (env,targets) stmt ->
    match string stmt "kind" with
    | "move" ->
      let var=get stmt "var" and value=get stmt "value" in
      let width=Capture.integer(get var "width") in
      if string var "type"="imm" && width>=1 && width<=64 then
        let term=Capture.tlift 0 env site value in
        let term=if Capture.width term=width then term else Capture.tunknown width in
        M.add (Capture.tkey var) term env,targets
      else env,targets
    | "jump" -> env,targets @ [Capture.tconstant(Capture.tlift 0 env site (get stmt "target"))]
    | "if" ->
      let branch body=original_targets site (depth+1) env (list(get stmt body)) in
      (match Capture.tconstant(Capture.tlift 0 env site (get stmt "condition")) with
       | Some condition -> let next,added=branch (if condition=0L then "no" else "yes") in
         next,targets @ added
       | None ->
         let left,ls=branch "yes" and right,rs=branch "no" in
         let joined=M.merge (fun _ left right -> match left,right with
           | Some a,Some b when same a b -> Some a
           | Some a,_ | _,Some a -> Some(Capture.tunknown(Capture.width a))
           | _ -> None) left right in
         joined,targets @ ls @ rs)
    | _ -> raise(Invalid "composition unreviewed projected source control")) (env,[]) statements
let validate_original_control site source original =
  let kind=string original "kind" in
  let start=Int64.of_string site in
  let length=String.length(string source "bytes_hex")/2 in
  let fall=set ~addr:true (get original "fall") and
      targets=set ~addr:true (get original "targets") in
  if List.mem kind ["ordinary";"conditional";"call"] then begin
    let next=Int64.add start (Int64.of_int length) in
    require (length>0 && Int64.unsigned_compare next start>0 &&
      S.equal fall (S.singleton(Capture.hx next))) "composition original structural fall"
  end else require (S.is_empty fall) "composition original unexpected fall";
  if kind="indirect" then require (S.is_empty targets &&
    get original "complete"=`Bool false) "composition raw indirect invented targets";
  let pending=Guard.recognized source<>None in
  if not pending && not(boolean(get source "opaque")) &&
      List.mem kind ["ordinary";"conditional";"jump";"indirect"] then begin
    let bil=list(Yojson.Safe.from_string(string source "ast")) in
    require (bil<>[] || (kind="ordinary" && string source "bytes_hex"="90"))
      "composition empty projected source control";
    let _,jumps=original_targets site 0 M.empty bil in
    let known=List.fold_left (fun set value -> match value with
      | Some target -> S.add (Capture.hx target) set | None -> set) S.empty jumps in
    let unknown=List.exists ((=) None) jumps in
    if kind="ordinary" then require (jumps=[] && S.is_empty targets)
      "composition ordinary source jumps"
    else if kind="indirect" then require (jumps<>[] && unknown)
      "composition indirect source lacks unknown jump"
    else require (jumps<>[] && not unknown &&
      S.subset known (S.union targets fall) && S.subset targets known)
      "composition direct source targets mismatch"
  end else if not pending && boolean(get source "opaque") &&
      not(List.mem kind ["stop";"call";"return"]) then begin
    require (kind="ordinary") "composition opaque original control";
    require (S.is_empty targets && get original "complete"=`Bool true &&
      not(Guard.unreviewed_control true 0
        (list(Yojson.Safe.from_string(string source "ast")))))
      "composition opaque ordinary control changed"
  end

let admit_current j snapshot =
  exact j ["normalized";"capture";"guard_admission";"target_resolution";"composition"];
  let final=get j "normalized" and capture=get j "capture" and
      guards=get j "guard_admission" and targets=get j "target_resolution" and
      report=get j "composition" in
  exact report ["schema";"profile";"model_version";"model_sha256";
    "checker_sha256";"snapshot";"artifact_sha256";"query_scope_sha256";
    "candidate_epoch";"candidate";"original_controls";"candidate_sha256";
    "target_report_sha256";"guard_report_sha256";"final_request_sha256";
    "binding_sha256"];
  require (string report "schema"=version && string report "profile"=profile &&
    string report "model_version"=version &&
    string report "model_sha256"=Build_identity.composition_model_sha256 &&
    string report "checker_sha256"=Build_identity.composition_engine_sha256)
    "composition profile/model/checker identity";
  List.iter (fun key -> Capture.digest(string report key))
    ["model_sha256";"checker_sha256";"artifact_sha256";"query_scope_sha256";
      "candidate_sha256";"target_report_sha256";"guard_report_sha256";
      "final_request_sha256";"binding_sha256"];
  let candidate=get report "candidate" and input=get guards "input" in
  require (string report "snapshot"=snapshot && string candidate "snapshot"=snapshot &&
    string final "snapshot"=snapshot && string input "snapshot"=snapshot &&
    string capture "snapshot"=snapshot && string targets "snapshot"=snapshot &&
    get report "artifact_sha256"=get capture "artifact_sha256" &&
    get report "artifact_sha256"=get input "artifact_sha256" &&
    get report "artifact_sha256"=get targets "artifact_sha256" &&
    get report "query_scope_sha256"=get input "query_scope_sha256" &&
    get report "candidate_epoch"=get input "candidate_epoch")
    "composition scope/source/epoch binding";
  ignore(Capture.uint(get report "candidate_epoch"));
  require (string report "candidate_sha256"=hash_json candidate &&
    string report "target_report_sha256"=hash_json targets &&
    string report "guard_report_sha256"=hash_json guards &&
    string report "final_request_sha256"=hash_json final)
    "composition component digest";
  let originals=list(get report "original_controls") in
  require (originals=List.sort (fun a b -> compare (string a "site") (string b "site")) originals)
    "composition original control order";
  let binding=hash_json (`List [
    `String "ariadne-guarded-target-binding/v3";get report "snapshot";
    get report "artifact_sha256";get report "query_scope_sha256";
    get report "candidate_epoch";get report "model_version";
    get report "model_sha256";get report "checker_sha256";
    get report "candidate_sha256";get report "original_controls";
    get report "target_report_sha256";get report "guard_report_sha256";
    get report "final_request_sha256"]) in
  require (string report "binding_sha256"=binding) "composition binding digest";
  let query=hash_json (`List [`String "ariadne-guarded-target-analysis/v3";`String binding]) in
  require (string capture "query_id"=query) "composition analysis identity";
  require (ends (string capture "semantic_profile")
    (":" ^ profile ^ ":" ^ binding ^ ":" ^ string targets "profile" ^ ":" ^
      string targets "memory_premise")) "composition capture proof binding";
  require (string targets "schema"="ariadne.indirect-target-resolution/v3" &&
    string targets "profile"="captured-local-indirect-targets/v2")
    "composition requires local target replay";
  require (string targets "graph_sha256"=resolver_graph_hash candidate)
    "composition target graph digest";
  List.iter (fun row ->
    require (string row "ast_sha256"=Guard.Sha256.digest(string row "ast"))
      "composition target original AST digest") (list(get targets "transfers"));
  (* Capture proves table arithmetic, structural incoming coverage and scalar
     substitution against the sealed candidate, including pending normal edges. *)
  require (get candidate "input_kind"=`String "dump" &&
    get candidate "file_backed"=`List [] && get candidate "trusted_fallback"=`List [])
    "composition requires capture-only dump";
  let candidate_input,_=Capture.admit_resolved ~loop_checker:Loop_closure.validate (`Assoc [
    "normalized",candidate;"capture",capture;"target_resolution",targets]) snapshot in
  let site_rows=list(get input "sites") in
  let sources=List.fold_left (fun map row ->
    let site=address(string row "site") in
    require (not(M.mem site map)) "composition duplicate guard source";
    M.add site row map) M.empty site_rows in
  List.iter (fun transfer ->
    let site=address(string transfer "site") in
    let source=try M.find site sources with Not_found ->
      raise(Invalid "composition target transfer missing original guard source") in
    require (get transfer "bytes_hex"=get source "bytes_hex" &&
      get transfer "ast"=get source "ast" &&
      string transfer "ast_sha256"=Guard.Sha256.digest(string source "ast"))
      "composition target/guard original BIL mismatch") (list(get targets "transfers"));
  let controls=List.fold_left (fun map row ->
    exact row ["site";"control"];
    let site=address(string row "site") in
    require (not(M.mem site map) && M.mem site sources)
      "composition original control domain";
    let control=get row "control" in
    exact control ["kind";"fall";"targets";"complete"];
    ignore(boolean(get control "complete"));
    ignore(set ~addr:true (get control "fall"));
    ignore(set ~addr:true (get control "targets"));
    M.add site control map) M.empty originals in
  require (M.cardinal controls=M.cardinal sources) "composition original control totality";
  let resolutions=List.fold_left (fun map row ->
    M.add (address(string row "site")) row map) M.empty (list(get targets "resolutions")) in
  let candidate_rows=List.fold_left (fun map row ->
    M.add (address(string row "address")) row map) M.empty (list(get candidate "instructions")) in
  let pending=ref S.empty in
  M.iter (fun site source ->
    Capture.validate_bil_ast (Yojson.Safe.from_string(string source "ast"));
    let original=M.find site controls and effective=get source "control" in
    validate_original_control site source original;
    let row=try M.find site candidate_rows with Not_found ->
      raise(Invalid "composition source absent from candidate") in
    require (same effective (control_of_instruction row))
      "composition guard/candidate effective control mismatch";
    if string original "kind"="indirect" then begin
      require (string effective "kind"="indirect" &&
        same (get original "fall") (get effective "fall"))
        "composition original indirect control changed";
      let known=set ~addr:true (get original "targets") in
      (match M.find_opt site resolutions with
      | Some resolution ->
        let added=set ~addr:true (get resolution "targets") in
        require (S.is_empty known && S.equal (set ~addr:true (get effective "targets")) added &&
          get effective "complete"=get resolution "complete")
          "composition resolver control augmentation"
      | None -> require (S.is_empty known &&
          get effective "targets"=`List [] && get effective "complete"=`Bool false &&
          get targets "stop"<>`Null) "composition missing indirect receipt")
    end else require (same original effective) "composition unauthorized control change";
    if Guard.recognized source<>None then begin
      pending:=S.add site !pending;
      let next=Printf.sprintf "0x%016Lx" (Int64.add(Int64.of_string site)
        (Int64.of_int(String.length(string source "bytes_hex")/2))) in
      let instruction=M.find site candidate_input.instructions in
      require (S.mem site candidate_input.decodable && instruction.kind="ordinary" &&
        S.equal instruction.fall (S.singleton next) && S.is_empty instruction.targets &&
        instruction.complete && S.is_empty instruction.uses && S.is_empty instruction.may &&
        S.is_empty instruction.must) "composition pending continuation committed effects"
    end) sources;
  List.iter (fun key -> require (same (get candidate key) (get final key))
    "composition immutable request scope")
    ["snapshot";"addresses";"locations";"entry_points";"slice_seeds";
      "input_kind";"captured";"file_backed";"trusted_fallback"];
  let final_rows=List.fold_left (fun map row ->
    M.add (address(string row "address")) row map) M.empty (list(get final "instructions")) in
  require (M.cardinal final_rows=M.cardinal candidate_rows)
    "composition final instruction domain";
  let final_decodable=set ~addr:true (get final "decodable") in
  M.iter (fun site row ->
    let final_row=try M.find site final_rows with Not_found ->
      raise(Invalid "composition missing final instruction") in
    if not(S.mem site !pending) then require (same row final_row &&
      S.mem site candidate_input.decodable=S.mem site final_decodable)
      "composition unauthorized final transformation") candidate_rows;
  (* Guard independently checks all final selections and stopped summaries. Its
     internal query ID stays guard-specific; the public query is the pair seal. *)
  let receipts=List.map (fun row -> get row "receipt_sha256") (list(get guards "guards"))
    |> List.sort compare in
  require(string guards "schema"="ariadne.guard-admission/v2" &&
    string guards "profile"="bap-guard-admission-v2")"composition current guard policy";
  let guard_query=Guard.digest_array [`String "ariadne-guard-analysis/v2";
    get guards "intent_id";get guards "final_request_sha256";`List receipts] in
  let guard_capture=Guard.replace_field capture "query_id" (`String guard_query) in
  Guard.admit (`Assoc ["normalized",final;"capture",guard_capture;
    "guard_admission",guards]) snapshot

let generation input = match string(get input "composition")"profile" with
  | "captured-guarded-targets/v1"->1|"captured-guarded-targets/v2"->2|_->3
let transport_query snapshot input =
  match generation input with
  | 1->Legacy_composition.transport_query snapshot input
  | 2->Legacy_composition_v2.transport_query snapshot input
  | _->transport_query_current snapshot input
let admit input snapshot =
  match generation input with
  | 1->Legacy_composition.admit input snapshot
  | 2->Legacy_composition_v2.admit input snapshot
  | _->(try admit_current input snapshot with
    Yojson.Json_error _->raise(Invalid "composition malformed original BIL JSON"))
