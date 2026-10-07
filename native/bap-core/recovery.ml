(* The fixed-input recovery bootstrap. Canonical fixed-width hex keys compare
   in unsigned address order without conversion to OCaml's signed int. *)
module S = Set.Make(String)
module M = Map.Make(String)
type json = Yojson.Safe.t
exception Invalid of string
let require b why = if not b then raise (Invalid why)
let str = function `String s -> s | _ -> raise (Invalid "string required")
let fields = function `Assoc xs -> xs | _ -> raise (Invalid "object required")
let get j k = try List.assoc k (fields j) with Not_found -> raise (Invalid ("missing " ^ k))
let exact j keys =
  let actual = List.map fst (fields j) |> List.sort String.compare in
  require (actual = List.sort String.compare keys) "unexpected/missing/duplicate fields"
let list = function `List xs -> xs | _ -> raise (Invalid "array required")
let boolean = function `Bool b -> b | _ -> raise (Invalid "boolean required")
let string j k = str (get j k)
let string_all f s =
  let ok = ref true in String.iter (fun c -> if not (f c) then ok := false) s; !ok
let address s =
  require (String.length s = 18 && String.sub s 0 2 = "0x" &&
    string_all (fun c -> (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))
      (String.sub s 2 16)) "noncanonical address"; s
let set ?(addr=false) j =
  let xs = list j in
  require (List.length xs <= 65536) "set budget";
  List.fold_left (fun acc x ->
      let s = str x in
      if addr then ignore (address s);
      require (not (S.mem s acc)) "duplicate set entry";
      S.add s acc) S.empty xs
let subset s domain = require (S.subset s domain) "element outside domain"
let rec json_shape depth = function
  | _ when depth > 64 -> raise (Invalid "JSON depth budget")
  | `Assoc xs ->
    ignore (List.fold_left (fun seen (k,v) ->
        require (not (S.mem k seen)) "duplicate JSON key";
        json_shape (depth+1) v; S.add k seen) S.empty xs)
  | `List xs -> List.iter (json_shape (depth+1)) xs
  | `Float f -> require (Float.is_finite f) "nonfinite JSON number"
  | _ -> ()
type instruction = {kind:string; fall:S.t; targets:S.t; complete:bool;
                    uses:S.t; may:S.t; must:S.t}
type input = { snapshot:string; addresses:S.t; roots:S.t; locations:S.t; seeds:S.t; captured:S.t;
               files:S.t; trusted:S.t; decodable:S.t; binary:bool;
               instructions:instruction M.t }
let admit j expected_snapshot =
  exact j ["snapshot";"addresses";"locations";"entry_points";"slice_seeds";
           "input_kind";"captured";"file_backed";"trusted_fallback";
           "decodable";"instructions"];
  let snapshot = string j "snapshot" in
  require (snapshot <> "" && snapshot = expected_snapshot) "snapshot mismatch";
  let addresses = set ~addr:true (get j "addresses") in
  require (not (S.is_empty addresses)) "empty address domain";
  let locations = set (get j "locations") in
  let aset k = let s = set ~addr:true (get j k) in subset s addresses; s in
  let roots = aset "entry_points" in
  require (not (S.is_empty roots)) "empty roots";
  let seeds = aset "slice_seeds" in
  let captured = aset "captured" and files = aset "file_backed" in
  let trusted = aset "trusted_fallback" and decodable = aset "decodable" in
  subset trusted files;
  let kind = string j "input_kind" in
  require (kind = "binary" || kind = "dump") "input kind";
  let rows = list (get j "instructions") in
  require (List.length rows = S.cardinal addresses) "instruction map not total";
  let edge_budget = ref 0 in
  let instructions = List.fold_left (fun acc row ->
      exact row ["address";"kind";"fall";"targets";"targets_complete";
                 "uses";"may_defs";"must_defs"];
      let a = address (string row "address") in
      require (S.mem a addresses && not (M.mem a acc)) "instruction map key";
      let kind = string row "kind" in
      require (List.mem kind ["ordinary";"conditional";"jump";"indirect";
                             "call";"return";"stop"]) "instruction kind";
      let fall = set ~addr:true (get row "fall") in
      let targets = set ~addr:true (get row "targets") in
      subset fall addresses; subset targets addresses;
      edge_budget := !edge_budget + S.cardinal fall + S.cardinal targets;
      require (!edge_budget <= 65536) "edge budget";
      require (S.cardinal fall = if List.mem kind ["ordinary";"conditional";"call"]
               then 1 else 0) "continuation cardinality";
      if List.mem kind ["ordinary";"return";"stop"] then
        require (S.is_empty targets) "unexpected targets";
      if List.mem kind ["conditional";"jump"] then
        require (S.cardinal targets = 1) "target cardinality";
      let uses = set (get row "uses") and may = set (get row "may_defs") in
      let must = set (get row "must_defs") in
      subset uses locations; subset may locations; subset must may;
      let complete = boolean (get row "targets_complete") in
      M.add a {kind; fall; targets; complete; uses; may; must} acc) M.empty rows in
  {snapshot; addresses; roots; locations; seeds; captured; files; trusted; decodable;
   binary = kind = "binary"; instructions}

module E = Set.Make(struct type t = string * string * string let compare = compare end)
module O = Set.Make(struct type t = string * string let compare = compare end)
module D = Set.Make(struct type t = string * string * string let compare = compare end)
type state = { phase:string; pending:S.t; visited:S.t; decoded:S.t; provenance:string M.t;
               edges:E.t; obligations:O.t; reaching:D.t M.t; slice:S.t;
               (* Derived per-state flow facts; never part of the observation. *)
               flow_out:D.t M.t; flow_in:S.t M.t; entry_defs:D.t M.t; flow_values:D.t M.t; flow_enabled:S.t }
let generated a origin locations =
  S.fold (fun loc -> D.add (loc,a,origin)) locations D.empty
let init input = {phase="recover"; pending=input.roots; visited=S.empty; decoded=S.empty;
                  provenance=S.fold (fun a -> M.add a "unavailable") input.addresses M.empty;
                  edges=E.empty; obligations=O.empty; slice=S.empty;
                  reaching=S.fold (fun a -> M.add a D.empty) input.addresses M.empty;
                  flow_out=M.empty;
                  flow_in=M.empty; flow_values=M.empty; flow_enabled=S.empty;
                  entry_defs=M.empty}
let source i a =
  if i.binary then (if S.mem a i.files then "file" else "unavailable")
  else if S.mem a i.captured then "captured"
  else if S.mem a i.trusted then "file" else "unavailable"
let visit i s a =
  require (s.phase = "recover" && not (S.is_empty s.pending) && S.min_elt s.pending = a) "Visit guard/schedule";
  let visited = S.add a s.visited in
  let provenance = source i a in
  if provenance = "unavailable" || not (S.mem a i.decodable) then
    {s with visited; pending=S.remove a s.pending;
            obligations=O.add (a, if provenance = "unavailable" then "unavailable"
                                 else "decode-failed") s.obligations}
  else
    let ins = M.find a i.instructions in
    let add kind destinations edges = S.fold (fun b -> E.add (a,b,kind)) destinations edges in
    let edges = match ins.kind with
      | "ordinary" -> add "next" ins.fall E.empty
      | "conditional" -> add "taken" ins.targets (add "fallthrough" ins.fall E.empty)
      | "jump" -> add "jump" ins.targets E.empty
      | "indirect" -> add "indirect" ins.targets E.empty
      | "call" -> add "call" ins.targets (add "summary" ins.fall E.empty)
      | _ -> E.empty in
    let successors = E.fold (fun (_,b,k) acc -> if k = "call" then acc else S.add b acc)
        edges S.empty in
    let obligations = if not ins.complete && List.mem ins.kind ["indirect";"call"]
      then O.add (a, ins.kind ^ "-targets") s.obligations else s.obligations in
    {s with pending=S.diff (S.union s.pending successors) visited; visited;
     decoded=S.add a s.decoded; provenance=M.add a provenance s.provenance;
     edges=E.union s.edges edges; obligations}

let outgoing _i s a = M.find a s.flow_out
let compute_incoming _i s a =
  let entry = match M.find_opt a s.entry_defs with Some defs -> defs | None -> D.empty in
  let sources = match M.find_opt a s.flow_in with Some srcs -> srcs | None -> S.empty in
  S.fold (fun src defs -> D.union defs (outgoing _i s src)) sources entry
let flow_index s =
  E.fold (fun (src,dst,kind) index ->
      if kind = "call" || not (S.mem src s.decoded) then index else
      let old = match M.find_opt dst index with Some srcs -> srcs | None -> S.empty in
      M.add dst (S.add src old) index) s.edges M.empty
let incoming _i s a = M.find a s.flow_values
let enabled_at s a = not (D.subset (M.find a s.flow_values) (M.find a s.reaching))
let initialize_flow i s =
  let next = {s with flow_in=flow_index s;
      flow_out=S.fold (fun a -> M.add a (generated a "instruction" (M.find a i.instructions).may)) s.decoded M.empty;
      entry_defs=S.fold (fun a -> M.add a (generated a "entry" i.locations)) (S.inter i.roots s.decoded) M.empty} in
  let next = {next with flow_values=S.fold (fun a -> M.add a (compute_incoming i next a)) s.decoded M.empty} in
  {next with flow_enabled=S.filter (enabled_at next) next.decoded}
let refresh_flow i s changed =
  let destinations = E.fold (fun (src,dst,kind) acc ->
      if src = changed && kind <> "call" && S.mem dst s.decoded then S.add dst acc else acc) s.edges S.empty in
  let next = {s with flow_values=S.fold (fun dst -> M.add dst (compute_incoming i s dst)) destinations s.flow_values} in
  let enabled = S.fold (fun a enabled ->
      if S.mem a next.decoded && enabled_at next a then S.add a enabled else S.remove a enabled)
      (S.add changed destinations) next.flow_enabled in
  {next with flow_enabled=enabled}
let enabled_propagation _i s = S.min_elt_opt s.flow_enabled
let predecessors i s =
  S.fold (fun a sites ->
      let uses = (M.find a i.instructions).uses in
      D.fold (fun (loc,site,origin) sites ->
          if origin = "instruction" && S.mem loc uses then S.add site sites else sites)
        (M.find a s.reaching) sites) s.slice S.empty
type action = Visit of string | FinishRecovery | Propagate of string
            | FinishDataflow | ExpandSlice | FinishSlice
let action_name = function
  | Visit _ -> "Visit" | FinishRecovery -> "FinishRecovery" | Propagate _ -> "Propagate"
  | FinishDataflow -> "FinishDataflow" | ExpandSlice -> "ExpandSlice" | FinishSlice -> "FinishSlice"
let next_action i s = match s.phase with
  | "recover" -> Some (if S.is_empty s.pending then FinishRecovery else Visit (S.min_elt s.pending))
  | "dataflow" -> Some (match enabled_propagation i s with Some a -> Propagate a | None -> FinishDataflow)
  | "slice" -> Some (if S.subset (predecessors i s) s.slice then FinishSlice else ExpandSlice)
  | "done" -> None
  | _ -> raise (Invalid "internal phase")
let advance i s action =
  require (next_action i s = Some action) "action phase/guard/schedule";
  match action with
  | Visit a -> visit i s a
  | FinishRecovery ->
    let next = {s with phase="dataflow"} in initialize_flow i next
  | Propagate a ->
    let next = {s with reaching=M.add a (D.union (M.find a s.reaching) (incoming i s a)) s.reaching} in
    let ins = M.find a i.instructions in
    let defs = D.union (D.filter (fun (loc,_,_) -> not (S.mem loc ins.must)) (M.find a next.reaching))
        (generated a "instruction" ins.may) in
    refresh_flow i {next with flow_out=M.add a defs s.flow_out} a
  | FinishDataflow -> {s with phase="slice"; slice=S.inter i.seeds s.decoded}
  | ExpandSlice -> {s with slice=S.union s.slice (predecessors i s)}
  | FinishSlice -> {s with phase="done"}
let parse_action payload =
  let name = string payload "action" in
  if name = "Visit" || name = "Propagate" then begin
    exact payload ["action";"address"];
    let a = address (string payload "address") in
    if name = "Visit" then Visit a else Propagate a
  end else begin
    exact payload ["action"];
    match name with
    | "FinishRecovery" -> FinishRecovery | "FinishDataflow" -> FinishDataflow
    | "ExpandSlice" -> ExpandSlice | "FinishSlice" -> FinishSlice
    | _ -> raise (Invalid "unsupported recovery action")
  end
let js s = `String s
let jsset s = `List (List.map js (S.elements s))
let observe i s = `Assoc [
    "phase", js s.phase; "pending",jsset s.pending; "visited",jsset s.visited;
    "decoded",jsset s.decoded;
    "provenance", `List (List.map (fun (a,p) -> `Assoc ["address",js a;"source",js p])
                           (M.bindings s.provenance));
    "edges", `List (List.map (fun (a,b,k) -> `Assoc ["src",js a;"dst",js b;"kind",js k])
                     (E.elements s.edges));
    "obligations", `List (List.map (fun (a,r) -> `Assoc ["site",js a;"reason",js r])
                           (O.elements s.obligations));
    "reaching", `List (List.map (fun a -> `Assoc ["address",js a;"definitions",
        `List (List.map (fun (loc,site,origin) -> `Assoc ["loc",js loc;"site",js site;"origin",js origin])
                 (D.elements (M.find a s.reaching)))]) (S.elements i.addresses));
    "slice", jsset s.slice]

(* Query-owned serialization cache. Every response still carries the complete
   observation; only unchanged immutable definition rows avoid re-encoding. *)
type observation_cache = (D.t * string) M.t ref
let observation_cache () = ref M.empty
let observe_chunks cache i s =
  let rows = S.elements i.addresses |> List.map (fun a ->
      let defs = M.find a s.reaching in
      match M.find_opt a !cache with
      | Some (old,text) when old == defs -> text
      | _ ->
        let row = `Assoc ["address",js a;"definitions",`List
            (List.map (fun (loc,site,origin) -> `Assoc
                 ["loc",js loc;"site",js site;"origin",js origin]) (D.elements defs))] in
        let text = Yojson.Safe.to_string row in
        cache := M.add a (defs,text) !cache; text) in
  (* The other fields are small. Avoid constructing the uncached reaching rows. *)
  let fields = [
    "phase",js s.phase; "pending",jsset s.pending; "visited",jsset s.visited;
    "decoded",jsset s.decoded;
    "provenance",`List (List.map (fun (a,p) -> `Assoc ["address",js a;"source",js p]) (M.bindings s.provenance));
    "edges",`List (List.map (fun (a,b,k) -> `Assoc ["src",js a;"dst",js b;"kind",js k]) (E.elements s.edges));
    "obligations",`List (List.map (fun (a,r) -> `Assoc ["site",js a;"reason",js r]) (O.elements s.obligations))] in
  let encoded = List.map (fun (k,v) -> Yojson.Safe.to_string (js k) ^ ":" ^ Yojson.Safe.to_string v) fields in
  let separated = List.fold_right (fun row chunks ->
      if chunks = [] then [row] else row :: "," :: chunks) rows [] in
  ["{" ^ String.concat "," encoded ^ ",\"reaching\":["] @ separated @
    ["],\"slice\":" ^ Yojson.Safe.to_string (jsset s.slice) ^ "}"]
