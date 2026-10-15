(* Finite relational stateflow, directly implementing AriadneMachineState.tla.
   Catalogue identities are strings; equal valuations never merge IDs. *)
open Recovery
module Steps = Set.Make(struct type t = string * string * string * string * string let compare=compare end)
module Terminals = Set.Make(struct type t = string * string * string * string let compare=compare end)
type input = {snapshot:string; nodes:S.t; initial:S.t M.t; structural:E.t;
              steps:Steps.t; terminals:Terminals.t; complete:S.t; obligations:O.t}
type state = {phase:string; states:S.t M.t}
let local_kind k = require (List.mem k ["next";"taken";"fallthrough";"jump";"indirect";"summary"]) "nonlocal edge kind"
let rows j = let xs=list j in require (List.length xs<=65536) "relation budget"; xs
let total j key value domain parse =
  let xs=rows j in require (List.length xs=S.cardinal domain) "map must be total";
  List.fold_left (fun acc row ->
      exact row [key;value]; let k=string row key in
      require (S.mem k domain && not (M.mem k acc)) "map key duplicate/outside domain";
      M.add k (parse k (get row value)) acc) M.empty xs
let admit j expected_snapshot =
  exact j ["snapshot";"nodes";"entry_points";"locations";"value_domain";"state_ids";
           "valuation";"state_status";"initial_states";"structural_edges";"uses";
           "may_defs";"must_defs";"state_steps";"terminal_transitions";"complete_sites";
           "adapter_obligations"];
  let snapshot=string j "snapshot" in
  require (snapshot<>"" && snapshot=expected_snapshot) "snapshot mismatch";
  let nodes=set ~addr:true (get j "nodes") and locations=set (get j "locations")
  and ids=set (get j "state_ids") in
  require (not (S.is_empty nodes) && not (S.is_empty locations) && not (S.is_empty ids)) "empty finite domain";
  let roots=set ~addr:true (get j "entry_points") in subset roots nodes;
  let value_domain=total (get j "value_domain") "location" "values" locations (fun _ value ->
      let s=set value in require (not (S.is_empty s)) "empty value domain"; s) in
  let valuation=total (get j "valuation") "state" "values" ids (fun _ value ->
      total value "location" "values" locations (fun loc value ->
          let s=set value in require (not (S.is_empty s)) "empty valuation";
          subset s (M.find loc value_domain); s)) in
  let status=total (get j "state_status") "state" "status" ids (fun _ value ->
      let s=str value in require (List.mem s ["running";"faulted";"returned";"stopped"]) "state status"; s) in
  let initial=total (get j "initial_states") "address" "states" nodes (fun a value ->
      let states=set value in subset states ids;
      require (S.is_empty states = not (S.mem a roots)) "initial states/roots mismatch";
      S.iter (fun id -> require (M.find id status="running") "nonrunning initial state") states;
      states) in
  let effects name = total (get j name) "address" "locations" nodes (fun _ value ->
      let s=set value in subset s locations;s) in
  ignore (effects "uses");
  let may=effects "may_defs" and must=effects "must_defs" in
  M.iter (fun a s -> subset s (M.find a may)) must;
  let structural=List.fold_left (fun acc row ->
      exact row ["src";"dst";"kind"];
      let src=address (string row "src") and dst=address (string row "dst") and kind=string row "kind" in
      require (S.mem src nodes && S.mem dst nodes) "edge endpoints";local_kind kind;
      let edge=src,dst,kind in require (not (E.mem edge acc)) "duplicate structural edge";
      E.add edge acc) E.empty (rows (get j "structural_edges")) in
  let frame site before after =
    require (S.mem site nodes && S.mem before ids && S.mem after ids) "transition domain";
    S.iter (fun loc -> require (S.equal (M.find loc (M.find before valuation))
                                 (M.find loc (M.find after valuation))) "may-write frame violation")
      (S.diff locations (M.find site may)) in
  let steps=List.fold_left (fun acc row ->
      exact row ["src";"before";"dst";"after";"kind"];
      let src=address (string row "src") and dst=address (string row "dst")
      and before=string row "before" and after=string row "after" and kind=string row "kind" in
      require (E.mem (src,dst,kind) structural) "step outside structural graph";
      frame src before after;
      require (M.find before status="running" && M.find after status="running") "nonrunning step state";
      let step=src,before,dst,after,kind in require (not (Steps.mem step acc)) "duplicate step";
      Steps.add step acc) Steps.empty (rows (get j "state_steps")) in
  let terminals=List.fold_left (fun acc row ->
      exact row ["site";"before";"after";"outcome"];
      let site=address (string row "site") and before=string row "before"
      and after=string row "after" and outcome=string row "outcome" in
      frame site before after;
      require (List.mem outcome ["faulted";"returned";"stopped"] && M.find before status="running"
               && M.find after status=outcome) "terminal status/outcome mismatch";
      let term=site,before,after,outcome in require (not (Terminals.mem term acc)) "duplicate terminal";
      Terminals.add term acc) Terminals.empty (rows (get j "terminal_transitions")) in
  let complete=set ~addr:true (get j "complete_sites") in subset complete nodes;
  let obligations=List.fold_left (fun acc row ->
      exact row ["site";"reason"];
      let site=address (string row "site") and reason=string row "reason" in
      require (S.mem site nodes && List.mem reason ["unknown-memory";"unmodeled-exception";
                  "unmodeled-system-call";"unmodeled-concurrency"]) "adapter obligation";
      require (not (O.mem (site,reason) acc)) "duplicate adapter obligation";
      O.add (site,reason) acc) O.empty (rows (get j "adapter_obligations")) in
  let obligations=S.fold (fun a -> O.add (a,"incomplete-semantics")) (S.diff nodes complete) obligations in
  {snapshot;nodes;initial;structural;steps;terminals;complete;obligations}
let init i = {phase="stateflow"; states=i.initial}
let incoming i s a =
  Steps.fold (fun (src,before,dst,after,_) states ->
      if dst=a && S.mem before (M.find src s.states) then S.add after states else states)
    i.steps (M.find a i.initial)
type action = Propagate of string | FinishStateflow
let action_name = function Propagate _ -> "Propagate" | FinishStateflow -> "FinishStateflow"
let next_action i s =
  if s.phase="done" then None else
    Some (match List.find_opt (fun a -> not (S.subset (incoming i s a) (M.find a s.states))) (S.elements i.nodes) with
        | Some a -> Propagate a | None -> FinishStateflow)
let advance i s action =
  require (next_action i s=Some action) "stateflow phase/guard/schedule";
  match action with
  | Propagate a -> {s with states=M.add a (S.union (M.find a s.states) (incoming i s a)) s.states}
  | FinishStateflow -> {s with phase="done"}
let parse_action payload =
  match string payload "action" with
  | "Propagate" -> exact payload ["action";"address"]; Propagate (address (string payload "address"))
  | "FinishStateflow" -> exact payload ["action"]; FinishStateflow
  | _ -> raise (Invalid "unsupported stateflow action")
let json_edges edges = `List (List.map (fun (src,dst,kind) ->
    `Assoc ["src",js src;"dst",js dst;"kind",js kind]) (E.elements edges))
let observe i s =
  let feasible=Steps.fold (fun (src,before,dst,_,kind) edges ->
      if S.mem before (M.find src s.states) then E.add (src,dst,kind) edges else edges) i.steps E.empty in
  let reached=M.fold (fun a states result -> if S.is_empty states then result else S.add a result) s.states S.empty in
  let infeasible=if s.phase<>"done" then E.empty else
      E.filter (fun (src,_,_) -> S.mem src i.complete && S.mem src reached) (E.diff i.structural feasible) in
  let unknown=E.diff (E.diff i.structural feasible) infeasible in
  let terminals=Terminals.filter (fun (site,before,_,_) -> S.mem before (M.find site s.states)) i.terminals in
  `Assoc ["phase",js s.phase;
          "states_at",`List (List.map (fun (a,ids) -> `Assoc ["address",js a;"states",jsset ids]) (M.bindings s.states));
          "structural_edges",json_edges i.structural;"feasible_edges",json_edges feasible;
          "provably_infeasible_edges",json_edges infeasible;"unknown_feasibility_edges",json_edges unknown;
          "reached_terminal_transitions",`List (List.map (fun (site,before,after,outcome) ->
              `Assoc ["site",js site;"before",js before;"after",js after;"outcome",js outcome]) (Terminals.elements terminals));
          "not_reached_nodes",jsset (if s.phase="done" then S.diff i.nodes reached else S.empty);
          "obligations",`List (List.map (fun (site,reason) -> `Assoc ["site",js site;"reason",js reason]) (O.elements i.obligations))]
