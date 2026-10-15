(* SDK qualification only: no image loading or instruction discovery. *)
open Bap.Std

let snapshot = Value.Tag.register
    ~name:"snapshot" ~package:"ariadne-sdk-smoke"
    ~uuid:"8f6b0cb8-d9ec-4ca8-91ed-72fcd838a063"
    (module Core_kernel.String)

let () =
  let target = Bap_core_theory.Theory.Target.declare
      ~bits:64 ~package:"ariadne-sdk-smoke" "normalized-amd64" in
  let project = Project.empty target in
  assert (Term.length sub_t (Project.program project) = 0);
  let project = Project.set project snapshot "snapshot-smoke" in
  assert (Project.get project snapshot = Some "snapshot-smoke");
  let va = Word.of_string "0xfedcba9876543210:64" in
  let block = Term.set_attr (Blk.create ()) address va in
  assert (Term.get_attr block address = Some va);
  let sub = Sub.create ~blks:[block] () in
  let project = Project.with_program project (Program.create ~subs:[sub] ()) in
  assert (Term.length sub_t (Project.program project) = 1);
  print_endline "isolated-sdk-project-term-storage-ok"
