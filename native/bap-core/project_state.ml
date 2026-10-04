(* Reader-scoped BAP ownership for the normalized-input bootstrap. These terms
   attribute supplied summaries; they do not claim to be newly lifted BIR. *)
open Bap.Std
let snapshot_tag = Value.Tag.register ~name:"snapshot" ~package:"ariadne-core"
    ~uuid:"16fa79b4-21cf-44bf-a58a-eb8d597db8e2" (module Core_kernel.String)
let input_tag = Value.Tag.register ~name:"normalized-input" ~package:"ariadne-core"
    ~uuid:"1c95c260-76c8-41ab-a26d-67e1a18864442" (module Core_kernel.String)
let evidence_tag = Value.Tag.register ~name:"capture-evidence" ~package:"ariadne-core"
    ~uuid:"d1c103c2-0eac-42a6-ab93-7ec92d224fb5" (module Core_kernel.String)
type t = {sites:Yojson.Safe.t Recovery.M.t; project:project; blocks:blk term list; attribution:Yojson.Safe.t list}
let create ?(sites=Recovery.M.empty) snapshot input =
  let target = Bap_core_theory.Theory.Target.declare ~bits:64
      ~package:"ariadne-core" "normalized-amd64" in
  let project = Project.empty target in
  let project = Project.set project snapshot_tag snapshot in
  let project = Project.set project input_tag (Yojson.Safe.to_string input) in
  {sites; project; blocks=[]; attribution=[]}
let add t snapshot va =
  let word = Word.of_string (va ^ ":64") in
  let block = Term.set_attr (Blk.create ()) address word in
  let block = Term.set_attr block snapshot_tag snapshot in
  let block = match Recovery.M.find_opt va t.sites with
    | None -> block | Some e -> Term.set_attr block evidence_tag (Yojson.Safe.to_string e) in
  let sub = Sub.create ~blks:[block] () |> fun s -> Term.set_attr s address word in
  let sub = Term.set_attr sub snapshot_tag snapshot in
  let sub = match Recovery.M.find_opt va t.sites with
    | None -> sub | Some e -> Term.set_attr sub evidence_tag (Yojson.Safe.to_string e) in
  let tid term = Tid.to_string (Term.tid term) in
  let row term cls =
    let stored_va = Option.get (Term.get_attr term address) |> Word.to_int64_exn in
    let stored_snapshot = Option.get (Term.get_attr term snapshot_tag) in
    `Assoc ["term",`String (tid term); "class",`String cls;
      "origin",`String "machine"; "snapshot",`String stored_snapshot;
      "va",`String (Printf.sprintf "0x%016Lx" stored_va); "parents",`List [];
      "evidence",(match Term.get_attr term evidence_tag with None -> `Null | Some e -> Yojson.Safe.from_string e)] in
  let program = Term.append sub_t (Project.program t.project) sub in
  let project = Project.with_program t.project program in
  {sites=t.sites; project; blocks=block::t.blocks;
   attribution=t.attribution @ [row block "blk"; row sub "sub"]}
let attribution t snapshot =
  if t.attribution = [] then `List [] else
    let program = Project.program t.project in
    let parents = List.map (fun row -> Recovery.get row "term") t.attribution in
    `List (t.attribution @ [`Assoc ["term",`String (Tid.to_string (Term.tid program));
       "class",`String "program"; "origin",`String "synthetic";
       "snapshot",`String snapshot; "va",`Null; "parents",`List parents; "evidence",`Null]])
