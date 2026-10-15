open Recovery
type owned = Core of Recovery.input * Recovery.state * Project_state.t
           | Flow of Stateflow.input * Stateflow.state * Project_state.t
let observe_owned snapshot = function
  | Core (i,s,p) -> Recovery.observe i s, Project_state.attribution p snapshot
  | Flow (i,s,_) -> Stateflow.observe i s, `List []
let finish_owned snapshot = function
  | Core (i,s,_) ->
    require (s.phase="done") "finish requires done";
    `Assoc ["snapshot",js snapshot;"missing_slice_seeds",jsset (S.diff i.seeds s.decoded)]
  | Flow (_,s,_) ->
    require (s.phase="done") "finish requires done";
    `Assoc ["snapshot",js snapshot]
let advance_owned operation payload snapshot = function
  | Core (i,s,p) ->
    let action = if operation="advance" then Recovery.parse_action payload else begin
        let a = match Recovery.next_action i s with Some a -> a | None -> raise (Invalid "no action at done") in
        if fields payload=[] then exact payload [] else begin
          exact payload ["action"]; require (string payload "action"=Recovery.action_name a) "requested action is not selected"
        end; a
      end in
    let next=Recovery.advance i s action in
    let p=match action with
      | Visit a when S.mem a next.decoded -> Project_state.add p snapshot a
      | _ -> p in
    Core (i,next,p)
  | Flow (i,s,p) ->
    let action = if operation="advance" then Stateflow.parse_action payload else begin
        let a = match Stateflow.next_action i s with Some a -> a | None -> raise (Invalid "no action at done") in
        if fields payload=[] then exact payload [] else begin
          exact payload ["action"]; require (string payload "action"=Stateflow.action_name a) "requested action is not selected"
        end; a
      end in
    Flow (i,Stateflow.advance i s action,p)
let max_frame = 8 * 1024 * 1024
let read_frame max_request_bytes =
  let buf = Buffer.create 4096 in
  let max_content_bytes = Int64.sub max_request_bytes 1L in
  let rec loop () =
    let c = input_char stdin in
    if c = '\n' then Buffer.contents buf else begin
      (* The limit includes the final newline. Keep the budget unsigned so
         a caller's finite uint64 limit never becomes a signed OCaml ceiling. *)
      require (Int64.unsigned_compare (Int64.of_int (Buffer.length buf))
                 max_content_bytes < 0) "frame budget";
      Buffer.add_char buf c; loop ()
    end in loop ()
let send_chunks chunks =
  let size = List.fold_left (fun size chunk -> size + String.length chunk) 0 chunks in
  require (size < max_frame) "response budget";
  List.iter (output_string stdout) chunks; output_char stdout '\n'; flush stdout
let send j = send_chunks [Yojson.Safe.to_string j]
let max_result = 256 * 1024 * 1024
let page_bytes = 256 * 1024
let checksum text =
  (* The pinned AMD64 SDK has 63-bit machine integers. Two 32-bit halves
     implement exactly the same FNV-1a modulo 2^64 without boxed Int64
     allocation for each byte of a large completion envelope. *)
  require (Sys.word_size=64) "checksum requires the pinned 64-bit SDK";
  let low=ref 0x84222325 and high=ref 0xcbf29ce4 in
  String.iter (fun c ->
    let x= !low lxor Char.code c in
    let product=x * 435 in
    high := (!high * 435 + x * 256 + (product lsr 32)) land 0xffffffff;
    low := product land 0xffffffff) text;
  Printf.sprintf "%08x%08x" !high !low
let hex_bytes text offset length =
  let digits="0123456789abcdef" in
  String.init (length * 2) (fun n ->
      let byte=Char.code text.[offset + n / 2] in
      digits.[if n mod 2 = 0 then byte lsr 4 else byte land 15])
let () =
  try
    require (Array.length Sys.argv = 5 || Array.length Sys.argv = 7)
      "expected session snapshot query family [--max-request-bytes decimal]";
    let session = Sys.argv.(1) and snapshot = Sys.argv.(2)
    and query = Sys.argv.(3) and family = Sys.argv.(4) in
    require (session <> "" && snapshot <> "" && List.mem family ["recovery";"stateflow"]) "identity/family";
    require (String.length query = 64 && string_all
               (fun c -> (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) query) "query digest";
    let handshake = Yojson.Safe.from_string Build_identity.handshake in
    let max_request_bytes =
      if Array.length Sys.argv = 5 then Capture.uint (get handshake "max_request_bytes")
      else begin
        require (Sys.argv.(5)="--max-request-bytes") "unsupported launch option";
        Capture.uint (`Intlit Sys.argv.(6))
      end in
    require (max_request_bytes<>0L) "positive request byte limit required";
    send (`Assoc (List.map (fun (key,value) ->
        if key="max_request_bytes" then key,`Intlit (Printf.sprintf "%Lu" max_request_bytes)
        else key,value) (fields handshake)));
    let sequence = ref 0 and action_index = ref 0 and owned = ref None in
    let completed = ref None and completion_mode = ref false and page_offset = ref 0 in
    let target_profile=ref false in
    let computation_cpu=ref 0. in
    let identity seq = ["schema",js "ariadne.bap-core/v1"; "session",js session;
      "snapshot",js snapshot; "query",js query; "family",js family; "sequence",`Int seq] in
    let observation_cache = Recovery.observation_cache () in
    let attribution_cache = ref None in
    let response seq changed error result =
      let observation, attribution = match !owned with
        | None -> ["null"], "[]"
        | Some (Core (i,s,p)) ->
          let attribution = match !attribution_cache with
            | Some (old,text) when old == p -> text
            | _ -> let text = Yojson.Safe.to_string (Project_state.attribution p snapshot) in
              attribution_cache := Some (p,text); text in
          (if !target_profile && !completion_mode && s.phase="done" then [Yojson.Safe.to_string (Recovery.observe_dictionary i s)] else Recovery.observe_chunks observation_cache i s), attribution
        | Some (Flow (i,s,_)) -> [Yojson.Safe.to_string (Stateflow.observe i s)], "[]" in
      let compact= !target_profile && !completion_mode && (match !owned with Some (Core (_,s,_)) -> s.phase="done" | _ -> false) in
      let fields = (List.map (fun (k,v) -> if k="schema" && compact then k,js "ariadne.bap-core-dictionary/v1" else k,v) (identity seq)) @ ["generation",`Int 1; "action_index",`Int !action_index;
        "changed",`Bool changed] in
      let encode (k,v) = Yojson.Safe.to_string (js k) ^ ":" ^ Yojson.Safe.to_string v in
      ["{" ^ String.concat "," (List.map encode fields) ^ ",\"observation\":"] @
      observation @ [",\"attribution\":"; attribution;
        "," ^ encode ("error",error) ^ "," ^ encode ("result",result) ^ "}"] in
    let rec loop () =
      let raw = read_frame max_request_bytes in
      let request = Yojson.Safe.from_string raw in
      json_shape 0 request;
      exact request ["schema";"session";"snapshot";"query";"family";"sequence";"operation";"payload"];
      List.iter (fun (k,v) -> require (get request k = v) ("identity/sequence mismatch: " ^ k))
        (identity !sequence);
      let operation = string request "operation" and payload = get request "payload" in
      let seq = !sequence in
      incr sequence;
      if !owned = None then begin
        require (seq = 0 && operation = "initialize") "initialize must be first";
        exact payload ["profile";"input"];
        let profile=string payload "profile" in
        target_profile := profile="captured-indirect-targets/v1" ||
          profile="captured-guarded-input/v1" || profile="captured-guarded-targets/v1" ||
          profile="captured-guarded-targets/v2" || profile="captured-guarded-input/v2" ||
          profile="captured-guarded-targets/v3";
        require (List.mem profile ["normalized-fixed-input/v1";"captured-fixed-input/v1";"captured-indirect-targets/v1";"captured-guarded-input/v1";"captured-guarded-targets/v1";"captured-guarded-targets/v2";"captured-guarded-input/v2";"captured-guarded-targets/v3"])
          "unsupported profile";
        require (family="recovery" || profile="normalized-fixed-input/v1") "stateflow profile";
        (* Large captured graphs allocate many short-lived persistent-tree nodes.
           This is a private target-profile allocation policy, not an analysis rule. *)
        if !target_profile then Gc.set {(Gc.get ()) with minor_heap_size=2097152};
        let input_json = get payload "input" in
        let state = try Some (if family="recovery" then begin
            let input,sites=if profile="captured-guarded-targets/v1" ||
                profile="captured-guarded-targets/v2" || profile="captured-guarded-targets/v3" then begin
                require(string(get input_json "composition")"profile"=profile)
                  "composition transport profile binding";
                require (Composition.transport_query snapshot input_json=query)
                  "composition session query identity";
                Composition.admit input_json snapshot
              end
              else if profile="captured-guarded-input/v1" then Legacy_guard.admit input_json snapshot
              else if profile="captured-guarded-input/v2" then begin
                require(string(get input_json "guard_admission")"schema"="ariadne.guard-admission/v2")
                  "guard transport profile binding";
                Guard.admit input_json snapshot
              end
              else if profile="captured-indirect-targets/v1" then Capture.admit_resolved input_json snapshot
              else if profile="captured-fixed-input/v1" then Capture.admit input_json snapshot
              else Recovery.admit input_json snapshot,M.empty in
            Core (input, Recovery.init input, Project_state.create ~sites snapshot input_json)
          end else begin
            let input=Stateflow.admit input_json snapshot in
            Flow (input, Stateflow.init input, Project_state.create snapshot input_json)
          end) with Invalid reason when profile="captured-guarded-input/v1" ||
              profile="captured-guarded-targets/v1" || profile="captured-guarded-targets/v2" ||
              profile="captured-guarded-input/v2" || profile="captured-guarded-targets/v3" ->
            if Sys.getenv_opt "ARIADNE_TARGET_DIAGNOSTICS"<>None then
              Printf.eprintf "guarded native admission rejected: %s\n%!" reason;
            let empty=`Assoc ["phase",js "recover";"pending",`List [];
              "visited",`List [];"decoded",`List [];"provenance",`List [];
              "edges",`List [];"obligations",`List [];"reaching",`List [];
              "slice",`List []] in
            send (`Assoc ((identity seq) @ ["generation",`Int 1;
              "action_index",`Int 0;"changed",`Bool false;
              "observation",empty;"attribution",`List [];
              "error",`Assoc ["kind",js "semantic";"message",js reason];
              "result",`Null]));
            None in
        (match state with
        | Some state -> owned := Some state;
          send_chunks (response seq false `Null `Null); loop ()
        | None -> ())
      end else if List.mem operation ["run-batch";"result-page";"result-close"] then begin
        require (family="recovery") "completion family";
        let advanced = ref 0 and closed = ref false in
        let offset = ref 0 and data = ref "" in
        let error = try
          begin match operation with
          | "run-batch" ->
            exact payload ["steps"];
            let steps = match get payload "steps" with `Int n -> n | _ -> raise (Invalid "batch steps") in
            require (steps > 0 && steps <= 64 && !completed=None) "batch guard";
            completion_mode := true;
            let rec advance n = if n > 0 then match Option.get !owned with
              | Core (i,s,_) when s.phase<>"done" ->
                require (!action_index < 1000000) "action budget";
                let next=advance_owned "step" (`Assoc []) snapshot (Option.get !owned) in
                owned := Some next; incr action_index; incr advanced; advance (n-1)
              | _ -> () in
            let before=Sys.time () in advance steps;computation_cpu := !computation_cpu +. Sys.time () -. before;
            begin match Option.get !owned with
            | Core (_,s,_) when s.phase="done" ->
              let before=Sys.time () in
              let chunks=response seq false `Null (finish_owned snapshot (Option.get !owned)) in
              let total=List.fold_left (fun n text -> n + String.length text) 0 chunks in
              require (total <= max_result) "completed result budget";
              let text=String.concat "" chunks in
              completed := Some (text,checksum text,seq);
              if Sys.getenv_opt "ARIADNE_TARGET_DIAGNOSTICS"<>None then
                Printf.eprintf "native kernel_cpu_s=%.3f serialization_cpu_s=%.3f actions=%d\n%!" !computation_cpu (Sys.time () -. before) !action_index
            | _ -> () end
          | "result-page" ->
            exact payload ["offset"];
            let requested=match get payload "offset" with `Int n -> n | _ -> raise (Invalid "page offset") in
            let text,_,_=match !completed with Some x -> x | None -> raise (Invalid "result not done") in
            require (requested = !page_offset && requested < String.length text) "page order";
            let length=min page_bytes (String.length text - requested) in
            offset := requested; data := hex_bytes text requested length;
            page_offset := requested + length
          | "result-close" ->
            exact payload [];
            let text,_,_=match !completed with Some x -> x | None -> raise (Invalid "result not done") in
            require (!page_offset = String.length text) "incomplete result transfer";
            ignore (finish_owned snapshot (Option.get !owned)); closed := true
          | _ -> assert false end;
          `Null
        with Invalid reason -> `Assoc ["kind",js "semantic";"message",js reason] in
        let total,digest,result_sequence=match !completed with
          | None -> 0,"",0 | Some (text,digest,seq) -> String.length text,digest,seq in
        send (`Assoc ["schema",js "ariadne.bap-core-completion/v1";
          "session",js session;"snapshot",js snapshot;"query",js query;"family",js family;
          "sequence",`Int seq;"generation",`Int 1;"action_index",`Int !action_index;
          "advanced",`Int !advanced;"done",`Bool (!completed<>None);"closed",`Bool !closed;
          "offset",`Int !offset;"total_bytes",`Int total;"checksum",js digest;
          "result_sequence",`Int result_sequence;"data_hex",js !data;"error",error]);
        if not !closed && error=`Null then loop ()
      end else begin
        require (not !completion_mode) "completion session cannot return to step mode";
        let reset = ref false in
        let result = ref `Null in
        let changed, error = try
          begin match operation with
          | "observe" -> exact payload []
          | "reset" -> exact payload []; reset := true
          | "finish" ->
            exact payload []; result := finish_owned snapshot (Option.get !owned)
          | "advance" | "step" ->
            let next=advance_owned operation payload snapshot (Option.get !owned) in
            owned := Some next; incr action_index
          | _ -> raise (Invalid "unsupported operation")
          end;
          (operation = "advance" || operation = "step"), `Null
        with Invalid reason -> false, `Assoc ["kind",js "semantic";"message",js reason] in
        send_chunks (response seq changed error !result);
        if not !reset then loop ()
      end in
    loop ()
  with
  | End_of_file -> prerr_endline "fatal: unexpected EOF"; exit 2
  | exn -> prerr_endline ("fatal: " ^ Printexc.to_string exn); exit 2
