(* Small source-level check; pinned SDK/helper qualification is separate. *)
open Recovery
open Capture

let incoming rows = List.fold_left (fun map (site, parents) ->
  M.add site (List.map (fun parent -> parent, false) parents) map) M.empty rows

let receipts paths =
  let root = path_context () in
  List.iter (fun chain ->
    let cursor = ref root in
    List.iter (fun parent ->
      let child = match Hashtbl.find_opt (!cursor).children (parent, false) with
        | Some child -> child
        | None -> let child = path_context () in
          Hashtbl.add (!cursor).children (parent, false) child; child in
      cursor := child) chain;
    (!cursor).terminal <- true) paths;
  root

let accepts roots graph cap paths =
  try require_path_coverage (S.of_list roots) graph cap "site" (receipts paths); true
  with Invalid _ -> false

let () =
  let graph = incoming ["site", ["d"; "c"]; "c", ["m"]; "d", ["m"];
    "m", ["b"; "a"]; "a", ["r"]; "b", ["r"]] in
  let full = [["c"; "m"; "a"; "r"]; ["c"; "m"; "b"; "r"];
    ["d"; "m"; "a"; "r"]; ["d"; "m"; "b"; "r"]] in
  assert (not (accepts ["r"] graph 2 full));
  assert (accepts ["r"] graph 3 full);
  assert (not (accepts ["r"] graph 3 [List.nth full 0; List.nth full 3]));
  assert (not (accepts ["r"; "m"] graph 3 full));
  assert (accepts ["r"; "m"] graph 3 (["c"; "m"] :: ["d"; "m"] :: full));
  (* Incoming-map order is reversed by M.fold. Ascending pushes visit b first,
     freeing its stack entry before the a branch needs its two slots. *)
  let asymmetric = incoming ["site", ["b"; "a"]; "a", ["y"; "x"]] in
  assert (accepts ["b"; "x"; "y"] asymmetric 2 [["b"]; ["a"; "x"]; ["a"; "y"]]);
  print_endline "Native source frontier checks PASS: six boundary/coverage/order cases."
