(* Independent LOOP-style pre/post-state control; this is a semantic replay
   probe, not captured-byte or whole-ISA qualification. *)
open Recovery
open Capture
let variable name = `Assoc ["name",`String name;"index",`Int 0;
  "virtual",`Bool false;"width",`Int 64;"type",`String "imm"]
let var name = `Assoc ["kind",`String "var";"var",variable name]
let number n = `Assoc ["kind",`String "int";"value",`String(string_of_int n ^ ":64u")]
let binary op lhs rhs = `Assoc ["kind",`String "binop";"op",`Int op;"lhs",lhs;"rhs",rhs]
let () =
  let bil=`List [
    `Assoc ["kind",`String "move";"var",variable "RCX";
      "value",binary 17 (var "RCX") (number 1)];
    `Assoc ["kind",`String "if";
      "condition",binary 4 (var "RCX") (number 0);
      "yes",`List [`Assoc ["kind",`String "jump";"target",number 3]];
      "no",`List []]] in
  validate_bil_ast bil;
  let outputs,_,condition=transfer_from_bil "0x0000000000000002" bil in
  let index=tinput 64 "RCX:0:false" in
  let bounds=[`Assoc ["expression",tbinary 2 index (tconst 64 3L);"taken",`Bool true]] in
  let killed=S.of_list(List.init 8 (fun n -> "gpr:rcx:" ^ string_of_int n)) in
  let after_index,guards=reverse_step (ref 1000) outputs killed
      "conditional" condition true index bounds in
  let indices guards = List.init 4 Int64.of_int |> List.filter (fun value ->
    List.for_all (fun guard -> match eval 0 after_index value (get guard "expression") with
      | Some n -> (n<>0L)=boolean(get guard "taken") | None -> true) guards) in
  assert (List.map Int64.to_int (indices guards)=[1;2;3]);
  let doubled=trewrite (ref 1000) outputs killed condition in
  let wrong=[List.hd guards;`Assoc ["expression",doubled;"taken",`Bool true]] in
  assert (List.map Int64.to_int (indices wrong)=[0;2;3]);
  assert (not(term_same condition doubled));
  print_endline "Native conditional-write checks PASS: three pre-state/predicate controls."
