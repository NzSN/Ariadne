(* Diagnose real LOCALv2 infeasible receipts with the compiled native kernel.
   Input is the full combined native input envelope, optionally under input. *)
open Recovery
open Capture
let () =
  require (Array.length Sys.argv=2) "expected captured combined input JSON";
  let parsed=Yojson.Safe.from_file Sys.argv.(1) in
  let wire=match List.assoc_opt "input" (fields parsed) with Some input -> input | None -> parsed in
  let report,candidate_json,snapshot=match List.assoc_opt "target" (fields wire) with
    | Some report -> report,get wire "candidate",string wire "snapshot"
    | None -> let composition=get wire "composition" in
      get wire "target_resolution",get composition "candidate",string composition "snapshot" in
  let candidate=Recovery.admit candidate_json snapshot in
  let transfers=List.fold_left (fun map row -> M.add (string row "site") row map)
    M.empty (list(get report "transfers")) in
  let cap=uint(get(get report "limits")"max_values") in
  let cap=if Int64.unsigned_compare cap (Int64.of_int max_int)>0 then max_int else Int64.to_int cap in
  let rows=List.concat_map (fun row -> List.filter_map (fun path ->
    if string path "form"<>"infeasible" then None else
    let site=string row "site" in
    let cursor=ref site and expression=ref(get(M.find site transfers)"jump") and guards=ref [] in
    let chain=list(get path "reverse_path") |> List.map str in
    let edges=list(get path "reverse_edges") |> List.map boolean in
    List.iter2 (fun parent taken ->
      let instruction=M.find parent candidate.instructions in
      let transfer=M.find_opt parent transfers in
      let outputs=match transfer with Some transfer -> get transfer "outputs" | None -> `Assoc [] in
      let condition=match transfer with Some transfer -> get transfer "condition" | None -> `Null in
      let next,next_guards=reverse_step (ref 1000000) outputs instruction.may
        instruction.kind condition taken !expression !guards in
      expression:=next;guards:=next_guards;cursor:=parent) chain edges;
    let word=List.combine chain edges in
    let semantic=term_same !expression (get path "expression") && term_same (`List !guards) (get path "guards") in
    let guard=guards_infeasible cap !guards in
    let stable=not(has_repeat word) || stable_cycle word candidate.instructions transfers !expression !guards in
    Some(`Assoc ["site",`String site;"cursor",`String !cursor;
      "path_length",`Int(List.length chain);"semantic_replay",`Bool semantic;
      "guard_infeasible",`Bool guard;"cycle_stable",`Bool stable;
      "reported_guard_infeasible",`Bool(guards_infeasible cap (list(get path "guards")))])
  ) (list(get row "paths"))) (list(get report "resolutions")) in
  print_endline(Yojson.Safe.to_string(`List rows));
  require (List.for_all (fun row -> boolean(get row "semantic_replay") &&
    boolean(get row "guard_infeasible") && boolean(get row "cycle_stable")) rows)
    "real infeasible receipt replay disagreement"
