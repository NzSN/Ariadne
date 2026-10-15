(* Finite semantic controls for LOCALv2 byte domains and one stable cycle.
   Captured BIL/helper qualification is separate from this source probe. *)
open Recovery
open Capture
let at n = hx(Int64.of_int n)
let instruction kind may = {kind; fall=S.empty; targets=S.empty; complete=true;
  uses=S.empty; may; must=S.empty}
let rec reordered = function
  | `Assoc rows -> `Assoc(List.map (fun (key,value) -> key,reordered value) rows
      |> List.sort (fun (a,_) (b,_) -> compare a b))
  | `List rows -> `List(List.map reordered rows)
  | value -> value
let () =
  let load=term 8 "load" ["site",`String(at 6);"address",
    tbinary 18 (tinput 64 "RCX:0:false") (tconst 64 120L)] in
  let index=tcast 3 64 (tcast 3 32 load) in
  assert (term_same index (tcast 3 64 load));
  assert (List.length(Option.get(values 0 256 load))=256);
  let greater=tunary 0 (tbinary 7 (tbinary 3 index (tconst 64 9L))
    (tbinary 5 index (tconst 64 9L))) in
  let guards=[`Assoc ["expression",greater;"taken",`Bool false];
    `Assoc ["expression",greater;"taken",`Bool true]] in
  assert (guards_infeasible 256 guards);
  (* Transport maps are lex-sorted; replay also creates terms in constructor
     order. A symbolic subject is identical in both representations. *)
  let mixed=[reordered(List.hd guards);List.nth guards 1] in
  assert (guards_infeasible 256 mixed);
  assert (eval 0 (reordered index) 9L index=Some 9L);
  let word=List.map (fun (site,taken) -> at site,taken)
    [8,true;7,false;6,false;3,false;8,false;7,false;6,false] in
  let nodes=List.fold_left (fun map site -> M.add (at site) (instruction "ordinary" S.empty) map)
    M.empty [3;6;7;8] in
  let transfers=List.fold_left (fun map site -> M.add (at site) (`Assoc ["ast",`String "[]"]) map)
    M.empty [3;6;7;8] in
  assert (stable_cycle word nodes transfers index guards);
  let stores=M.add (at 3) (`Assoc ["ast",`String
    "[{\"kind\":\"move\",\"var\":{\"name\":\"mem\",\"index\":0,\"virtual\":false,\"width\":0,\"type\":\"mem\"},\"value\":{\"kind\":\"var\",\"var\":{\"name\":\"mem\",\"index\":0,\"virtual\":false,\"width\":0,\"type\":\"mem\"}}}]"]) transfers in
  assert (not(stable_cycle word nodes stores index guards));
  let writes=M.add (at 3) (instruction "ordinary" (S.singleton "gpr:rcx:0")) nodes in
  assert (not(stable_cycle word writes transfers index guards));
  let unknown=M.add (at 3) (instruction "ordinary" (S.singleton "memory:any")) nodes in
  assert (not(stable_cycle word unknown transfers index guards));
  let call=M.add (at 3) (instruction "call" S.empty) nodes in
  assert (not(stable_cycle word call transfers index guards));
  assert (cycle_window (word @ [at 3,false;at 8,false])=None);
  let unsupported=tunknown 64 in
  let unknown_guards=[`Assoc ["expression",tbinary 2 unsupported (tconst 64 9L);"taken",`Bool true];
    `Assoc ["expression",tbinary 2 unsupported (tconst 64 9L);"taken",`Bool false]] in
  assert (not(guards_infeasible 256 unknown_guards));
  print_endline "Native infeasible-loop checks PASS: twelve byte-domain/cycle/uncertainty/map-order controls."
