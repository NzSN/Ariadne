(* Capture evidence is supplied by the trusted reader, never read from paths. *)
open Recovery
let hex s = string_all (fun c -> (c>='0' && c<='9') || (c>='a' && c<='f')) s
let digest s = require (String.length s=64 && hex s) "capture digest"
let integer = function `Int n when n>=0 -> n | _ -> raise (Invalid "capture nonnegative integer")
let admit j snapshot =
  exact j ["normalized";"capture"];
  let normalized=get j "normalized" in
  let i=Recovery.admit normalized snapshot in
  require (not i.binary && S.is_empty i.files && S.is_empty i.trusted) "capture-only profile";
  let capture=get j "capture" in
  exact capture ["snapshot";"artifact_sha256";"query_id";"semantic_profile";"sites"];
  require (string capture "snapshot"=snapshot && string capture "semantic_profile"<>"") "capture identity";
  digest (string capture "artifact_sha256"); digest (string capture "query_id");
  let sites=List.fold_left (fun sites row ->
      exact row ["address";"bytes";"captured";"quality";"status";"helper_sha256";
                 "runtime_sha256";"ast_sha256";"projection";"spans"];
      let a=address (string row "address") in
      require (S.mem a i.addresses && not (M.mem a sites)) "capture site domain";
      let bytes=string row "bytes" in
      require (String.length bytes<=30 && String.length bytes mod 2=0 && hex bytes) "capture bytes";
      let captured=boolean (get row "captured") in
      require (captured=S.mem a i.captured) "capture availability";
      List.iter (fun k -> match get row k with `Null -> () | v -> digest (str v))
        ["helper_sha256";"runtime_sha256";"ast_sha256"];
      if S.mem a i.decodable then begin
        require (captured && bytes<>"") "decoded bytes absent";
        require (get row "helper_sha256"<>`Null && get row "runtime_sha256"<>`Null
                 && get row "projection"<>`Null && get row "status"<>`Null) "decoded semantic identity absent"
      end;
      if get row "status"=`String "projected" then
        require (get row "ast_sha256"<>`Null && string row "quality"="external_lift") "projected AST identity";
      if get row "status"=`String "opaque-ordinary" then begin
        let instruction=M.find a i.instructions in
        let next=Printf.sprintf "0x%016Lx" (Int64.add (Int64.of_string a)
            (Int64.of_int (String.length bytes / 2))) in
        require (get row "projection"=`String "bap-bit-provenance-v3"
                 && get row "ast_sha256"<>`Null && string row "quality"="opaque"
                 && S.mem a i.decodable && instruction.kind="ordinary"
                 && S.equal instruction.fall (S.singleton next)
                 && S.is_empty instruction.targets && instruction.complete
                 && S.equal instruction.uses i.locations
                 && S.equal instruction.may i.locations && S.is_empty instruction.must)
          "opaque ordinary capture contract"
      end;
      let start=Int64.of_string a in
      let length=String.length bytes / 2 in
      let covered=ref 0 in
      List.iter (fun span ->
          exact span ["address";"length";"contributors"];
          let low=Int64.of_string (address (string span "address")) in
          let count=integer (get span "length") in
          require (count>0) "empty capture span";
          let contributors=list (get span "contributors") in
          require (contributors<>[]) "capture contributor missing";
          List.iter (fun c ->
              exact c ["stream";"entry";"file_offset"];
              ignore(integer (get c "stream")); ignore(integer (get c "entry"));
              let offset=string c "file_offset" in
              require (offset<>"" && string_all (fun c -> c>='0' && c<='9') offset) "capture file offset") contributors;
          if !covered<length then begin
            let current=Int64.add start (Int64.of_int !covered) in
            require (Int64.unsigned_compare low current<=0) "capture span hole";
            let delta=Int64.sub current low in
            if Int64.unsigned_compare delta (Int64.of_int count)<0 then
              covered := min length (!covered + count - Int64.to_int delta)
          end) (list (get row "spans"));
      if captured then require (!covered=length) "capture span coverage";
      M.add a row sites) M.empty (list (get capture "sites")) in
  require (M.cardinal sites=S.cardinal i.addresses) "capture sites not total";
  i,sites

(* The reader/BIL producer remains trusted. This profile additionally checks
   numeric entry evaluation, full table/index coverage, source bindings and
   every incoming path of a complete certificate against the admitted graph. *)
let uint j = match j with `Int n when n>=0 -> Int64.of_int n
  | `Intlit s ->
    require (s<>"" && String.length s<=20 && string_all (fun c -> c>='0' && c<='9') s) "unsigned integer required";
    let value=ref 0L in String.iter (fun c -> let digit=Int64.of_int (Char.code c-Char.code '0') in
      require (Int64.unsigned_compare !value (Int64.unsigned_div (Int64.sub Int64.minus_one digit) 10L)<=0) "unsigned overflow";
      value := Int64.add (Int64.mul !value 10L) digit) s; !value
  | _ -> raise (Invalid "unsigned integer required")
let uaddress j = Int64.of_string (address (str j))
let hx x = Printf.sprintf "0x%016Lx" x
let width t = let w=integer (get t "width") in require (w>0 && w<=64) "resolver width"; w
let kind t = get t "kind"
let opname t = string (kind t) "kind"
let tconstant t = if opname t="constant" then Some (uaddress (get (kind t) "value")) else None
let mask w = if w=64 then Int64.minus_one else Int64.sub (Int64.shift_left 1L w) 1L
let signed v w = Int64.shift_right (Int64.shift_left v (64-w)) (64-w)
let cast op w aw v = Int64.logand (mask w) (match op with
  | 0|3 -> v | 1 -> require (w<=aw) "resolver high cast"; Int64.shift_right_logical v (aw-w)
  | 2 -> require (w>=aw) "resolver signed cast"; signed v aw
  | _ -> raise (Invalid "resolver cast"))
let binary op aw w l r = Int64.logand (mask w) (match op with
  | 0 -> if signed l aw<=signed r aw then 1L else 0L
  | 1 -> if signed l aw<signed r aw then 1L else 0L
  | 2 -> if Int64.unsigned_compare l r<=0 then 1L else 0L
  | 3 -> if Int64.unsigned_compare l r<0 then 1L else 0L
  | 4 -> if l<>r then 1L else 0L | 5 -> if l=r then 1L else 0L
  | 6 -> Int64.logxor l r | 7 -> Int64.logor l r | 8 -> Int64.logand l r
  | 9 -> if Int64.unsigned_compare r (Int64.of_int aw)>=0 then (if signed l aw<0L then Int64.minus_one else 0L) else Int64.shift_right (signed l aw) (Int64.to_int r)
  | 10 -> if Int64.unsigned_compare r 64L>=0 then 0L else Int64.shift_right_logical l (Int64.to_int r)
  | 11 -> if Int64.unsigned_compare r 64L>=0 then 0L else Int64.shift_left l (Int64.to_int r)
  | 16 -> Int64.mul l r | 17 -> Int64.sub l r | 18 -> Int64.add l r
  | _ -> raise (Invalid "resolver unsupported arithmetic"))
let rec eval depth index value t =
  require (depth<=32) "resolver expression depth";
  if t=index then Some value else match tconstant t with Some v -> Some v | None ->
  let k=kind t and w=width t in
  match opname t with
  | "binary" -> begin match eval (depth+1) index value (get k "left"),eval (depth+1) index value (get k "right") with
    | Some l,Some r -> Some (binary (integer (get k "op")) (width (get k "left")) w l r) | _ -> None end
  | "cast" -> let arg=get k "arg" in Option.map (cast (integer (get k "op")) w (width arg)) (eval (depth+1) index value arg)
  | "unary" -> Option.map (fun v -> Int64.logand (mask w) (if integer (get k "op")=0 then Int64.lognot v else Int64.neg v)) (eval (depth+1) index value (get k "arg"))
  | _ -> None
let unique_unsigned xs = List.sort_uniq Int64.unsigned_compare xs
let rec values depth cap t =
  require (depth<=32) "resolver value depth";
  if cap=0 then None else match tconstant t with Some v -> Some [v] | None ->
  let k=kind t and w=width t in match opname t with
  | "cast" -> let arg=get k "arg" in Option.map (fun xs -> List.map (cast (integer (get k "op")) w (width arg)) xs |> unique_unsigned) (values (depth+1) cap arg)
  | "unary" -> Option.map (fun xs -> List.map (fun v -> Int64.logand (mask w) (if integer (get k "op")=0 then Int64.lognot v else Int64.neg v)) xs |> unique_unsigned) (values (depth+1) cap (get k "arg"))
  | "binary" ->
    let op=integer (get k "op") and left=get k "left" and right=get k "right" in
    let bound=match tconstant left with Some n -> Some n | None -> tconstant right in
    if op=8 && Option.fold ~none:false ~some:(fun n -> Int64.unsigned_compare n (Int64.of_int cap)<0) bound then
      let m=Option.get bound in Some (List.init (Int64.to_int m+1) Int64.of_int |> List.filter (fun v -> Int64.logand v (Int64.lognot m)=0L))
    else begin match values (depth+1) cap left,values (depth+1) cap right with
      | Some ls,Some rs when List.length ls*List.length rs<=cap -> Some (List.concat_map (fun l -> List.map (binary op (width left) w l) rs) ls |> unique_unsigned)
      | _ -> None end
  | _ -> None
let umin a b = if Int64.unsigned_compare a b<=0 then a else b
let umax a b = if Int64.unsigned_compare a b>=0 then a else b
let rec range depth t taken index =
  require (depth<=32) "resolver guard depth";
  let full=0L,mask (width index) in let k=kind t in match opname t with
  | "unary" when integer (get k "op")=0 && width t=1 -> range (depth+1) (get k "arg") (not taken) index
  | "binary" ->
    let op=integer (get k "op") and left=get k "left" and right=get k "right" in
    if (op=7 || op=8) && width t=1 then
      let al,ah=range (depth+1) left taken index and bl,bh=range (depth+1) right taken index in
      if (op=7 && not taken)||(op=8 && taken) then umax al bl,umin ah bh else umin al bl,umax ah bh
    else if left=index && tconstant right<>None then
      let v=Option.get (tconstant right) and maximum=mask (width index) in begin match op,taken with
      | 2,true -> 0L,v | 3,true when v<>0L -> 0L,Int64.sub v 1L
      | 2,false when v<>maximum -> Int64.add v 1L,maximum | 3,false -> v,maximum
      | 5,true | 4,false -> v,v
      | 5,false | 4,true when v=0L -> 1L,maximum | _ -> full end
    else if op=5 && right=index && tconstant left<>None then
      let v=Option.get (tconstant left) in if taken then v,v else if v=0L then 1L,mask (width index) else full
    else full
  | _ -> full
let relative t =
  let fail () = raise (Invalid "resolver relative expression") in
  let k=kind t in if opname t<>"binary" || integer (get k "op")<>18 then fail ();
  let l=get k "left" and r=get k "right" in
  let base,offset=match tconstant l,tconstant r with Some b,_ -> b,r | _,Some b -> b,l | _ -> fail () in
  let o=kind offset in if opname offset<>"cast" || integer (get o "op")<>2 || width offset<>64 then fail ();
  let load=get o "arg" in if opname load<>"load" || width load<>32 then fail ();
  let slot=get (kind load) "address" in let s=kind slot in
  if opname slot<>"binary" || integer (get s "op")<>18 then fail ();
  let l=get s "left" and r=get s "right" in
  let scaled=if tconstant l=Some base then r else if tconstant r=Some base then l else fail () in
  let s=kind scaled in if opname scaled<>"binary" then fail ();
  let op=integer (get s "op") and multiplier=tconstant (get s "right") in
  if not ((op=11 && multiplier=Some 2L)||(op=16 && multiplier=Some 4L)) then fail ();
  let index=get s "left" in let index=if opname index="cast" && integer (get (kind index) "op")=3 then get (kind index) "arg" else index in base,index
let local_edges i =
  let falls=if List.mem i.kind ["ordinary";"conditional";"call"] then S.elements i.fall |> List.map (fun a -> a,false) else [] in
  let targets=if List.mem i.kind ["conditional";"jump";"indirect"] then S.elements i.targets |> List.map (fun a -> a,true) else [] in falls@targets
let data_value text bytes =
  require (String.length text=bytes*2 && hex text) "resolver entry encoding";
  let value=ref 0L in for n=0 to bytes-1 do
    let byte=int_of_string ("0x" ^ String.sub text (n*2) 2) in
    value := Int64.logor !value (Int64.shift_left (Int64.of_int byte) (n*8)) done; !value
(* A node denotes a reverse-path prefix, not just an instruction. Merging
   contexts by address loses combinations across successive branch diamonds. *)
type path_context = {
  mutable terminal: bool;
  children: ((string * bool), path_context) Hashtbl.t;
}
let path_context () = {terminal=false; children=Hashtbl.create 2}
let require_path_coverage roots incoming max_values site context =
  (* Match the producer: push ascending predecessors, then pop the last one.
     The budget includes siblings retained from earlier branching contexts. *)
  let pending=ref [site,context] and pending_count=ref 1 in
  require (max_values>0) "resolver frontier budget";
  while !pending<>[] do
    let cursor,context=List.hd !pending in
    pending:=List.tl !pending;decr pending_count;
    require (context.terminal=S.mem cursor roots) "resolver uncovered root context";
    let parents=match M.find_opt cursor incoming with Some xs -> List.sort compare xs | None -> [] in
    require (Hashtbl.length context.children=List.length parents)
      "resolver uncovered incoming path";
    List.iter (fun ((parent,_) as edge) ->
      match Hashtbl.find_opt context.children edge with
      | Some child ->
        require (!pending_count<max_values) "resolver frontier budget";
        pending:=(parent,child)::!pending;incr pending_count
      | None -> raise (Invalid "resolver uncovered incoming path")) parents
  done
let admit_resolved j snapshot =
  exact j ["normalized";"capture";"target_resolution"];
  let i,sites=admit (`Assoc ["normalized",get j "normalized";"capture",get j "capture"]) snapshot in
  let report=get j "target_resolution" and capture=get j "capture" in
  exact report ["schema";"profile";"memory_premise";"snapshot";"artifact_sha256";"graph_sha256";"limits";"resolutions";"data_reads";"transfers";"stop"];
  require (string report "schema"="ariadne.indirect-target-resolution/v1" && string report "profile"="captured-indirect-targets/v1"
    && string report "memory_premise"="FrozenCapturedControlData" && string report "snapshot"=snapshot
    && get report "artifact_sha256"=get capture "artifact_sha256") "resolver identity/premise";
  digest (string report "graph_sha256");
  let limits=get report "limits" in
  let caps=["max_entries",4096;"max_targets",65536;"max_read_bytes",1048576;"max_evidence_bytes",4194304;
    "max_values",256;"max_steps",262144;"max_path_steps",256;"max_rounds",16;"max_elapsed_ms",1000] in
  exact limits (List.map fst caps);List.iter (fun (key,cap) -> require (integer (get limits key)<=cap) "resolver resource cap") caps;
  let empty_evidence_stop=get report "stop"=`String "resolution-evidence-limit"
    && get report "resolutions"=`List [] && get report "data_reads"=`List []
    && get report "transfers"=`List [] in
  require (String.length (Yojson.Safe.to_string report)<=integer (get limits "max_evidence_bytes")
    || empty_evidence_stop) "resolver evidence budget";
  if List.exists (fun key -> integer (get limits key)=0)
      ["max_values";"max_steps";"max_rounds";"max_elapsed_ms"] then
    require (get report "data_reads"=`List [] && List.for_all (fun row ->
      get row "paths"=`List [] && get row "targets"=`List []) (list (get report "resolutions")))
      "resolver zero work budget";
  let transfers=List.fold_left (fun map t ->
    exact t ["site";"bytes_hex";"ast";"ast_sha256";"outputs";"jump";"condition"];
    let a=address (string t "site") in require (not (M.mem a map) && M.mem a sites) "resolver transfer domain";
    let source=M.find a sites in require (get source "bytes"=get t "bytes_hex" && get source "ast_sha256"=get t "ast_sha256") "resolver semantic source binding";
    digest (string t "ast_sha256");let ast=Yojson.Safe.from_string (string t "ast") in json_shape 0 ast;ignore (list ast);
    M.add a t map) M.empty (list (get report "transfers")) in
  let read_bytes=ref 0 in
  let reads=List.fold_left (fun map r ->
    exact r ["address";"requested";"bytes_hex";"spans";"conflict_sources";"stop"];
    let a=address (string r "address") and requested=integer (get r "requested") in
    require (requested=4 || requested=8) "resolver read width";
    let key=a^":"^string_of_int requested in require (not (M.mem key map)) "resolver duplicate read";
    read_bytes := !read_bytes+requested;
    require (!read_bytes<=integer (get limits "max_read_bytes")) "resolver read budget";
    let bytes=string r "bytes_hex" in require (String.length bytes<=requested*2 && String.length bytes mod 2=0 && hex bytes) "resolver read bytes";
    if String.length bytes=requested*2 then begin
      require (get r "conflict_sources"=`List [] && string r "stop"="RequestedLength") "resolver ambiguous full read";
      let covered=ref 0 in List.iter (fun span ->
        exact span ["address";"length";"contributors"];let low=uaddress (get span "address") in let length=integer (get span "length") in
        require (length>0 && list (get span "contributors")<>[]) "resolver contributor coverage";
        List.iter (fun c -> exact c ["stream";"entry";"file_offset"];ignore (integer (get c "stream"));ignore (integer (get c "entry"));ignore (uint (get c "file_offset"))) (list (get span "contributors"));
        let current=Int64.add (Int64.of_string a) (Int64.of_int !covered) in
        require (Int64.unsigned_compare low current<=0) "resolver read hole";
        let delta=Int64.sub current low in if Int64.unsigned_compare delta (Int64.of_int length)<0 then covered := min requested (!covered+length-Int64.to_int delta)
      ) (list (get r "spans"));require (!covered=requested) "resolver partial read coverage"
    end;
    M.add key r map) M.empty (list (get report "data_reads")) in
  let incoming=M.fold (fun parent instruction incoming ->
    List.fold_left (fun incoming ((to_,taken)) ->
      let previous=match M.find_opt to_ incoming with Some xs -> xs | None -> [] in
      M.add to_ ((parent,taken)::previous) incoming) incoming (local_edges instruction)) i.instructions M.empty in
  let seen=ref S.empty and retained_targets=ref S.empty in
  List.iter (fun row ->
    exact row ["site";"targets";"complete";"paths";"unresolved"];
    let site=address (string row "site") in require (M.mem site i.instructions && not (S.mem site !seen)) "resolver resolution domain";seen:=S.add site !seen;
    let instruction=M.find site i.instructions and complete=boolean (get row "complete") in
    require (instruction.kind="indirect" && instruction.complete=complete && S.equal instruction.targets (set ~addr:true (get row "targets"))) "resolver normalized targets";
    retained_targets:=S.union !retained_targets instruction.targets;
    require (S.cardinal !retained_targets<=integer (get limits "max_targets")) "resolver target budget";
    if complete then require (list (get row "unresolved")=[] && get report "stop"=`Null && list (get row "paths")<>[]) "resolver residual alternatives";
    let witnessed=ref S.empty and context=path_context () in
    List.iter (fun path ->
      exact path ["root";"reverse_path";"reverse_edges";"form";"base";"indices";"entries";"expression";"guards"];
      let chain=list (get path "reverse_path") |> List.map (fun a -> address (str a)) and edges=list (get path "reverse_edges") |> List.map boolean in
      require (List.length chain=List.length edges && List.length chain<integer (get limits "max_path_steps")
        && List.length chain+1<=integer (get limits "max_steps")) "resolver edge word/work budget";
      require (List.length (list (get path "indices"))<=integer (get limits "max_entries")
        && List.length (list (get path "entries"))<=integer (get limits "max_entries")) "resolver entry budget";
      let cursor=ref site and path_seen=ref S.empty and prefix=ref context in
      List.iter2 (fun parent taken ->
        require (parent<>site && not (S.mem parent !path_seen) && M.mem parent i.instructions) "resolver cyclic/absent predecessor";
        path_seen:=S.add parent !path_seen;
        require (List.mem (!cursor,taken) (local_edges (M.find parent i.instructions))) "resolver missing predecessor edge";
        let child=match Hashtbl.find_opt (!prefix).children (parent,taken) with
          | Some child -> child
          | None -> let child=path_context () in Hashtbl.add (!prefix).children (parent,taken) child; child in
        prefix:=child;cursor:=parent
      ) chain edges;
      require (!cursor=string path "root" && S.mem !cursor i.roots) "resolver root witness";
      require (not (!prefix).terminal) "resolver duplicate path";
      (!prefix).terminal<-true;
      require (M.mem site transfers && get (M.find site transfers) "jump"<>`Null) "resolver jump semantic source";
      let expression=get path "expression" and form=string path "form" in
      let base,index,bytes=if form="relative32" then let b,x=relative expression in b,Some x,4
        else begin require (form="pointer64" && opname expression="load" && width expression=64) "resolver pointer form";
          match tconstant (get (kind expression) "address") with Some b -> b,None,8 | None -> raise (Invalid "resolver pointer address") end in
      require (hx base=string path "base") "resolver base binding";
      let indices=match index with None -> [0L] | Some index ->
        let guards=list (get path "guards") in
        let lo,hi=List.fold_left (fun (lo,hi) guard -> exact guard ["expression";"taken"];
          let a,b=range 0 (get guard "expression") (boolean (get guard "taken")) index in umax lo a,umin hi b) (0L,mask (width index)) guards in
        let possible=match values 0 (integer (get limits "max_values")) index with Some v -> v | None ->
          let delta=Int64.sub hi lo in require (Int64.unsigned_compare lo hi<=0 && Int64.unsigned_compare delta (Int64.of_int (integer (get limits "max_entries")))<0) "resolver unbounded index";
          List.init (Int64.to_int delta+1) (fun n -> Int64.add lo (Int64.of_int n)) in
        List.filter (fun value -> Int64.unsigned_compare value lo>=0 && Int64.unsigned_compare value hi<=0 && List.for_all (fun g ->
          match eval 0 index value (get g "expression") with None -> true | Some n -> (n<>0L)=boolean (get g "taken")) guards) possible |> unique_unsigned in
      require (List.length indices<=integer (get limits "max_entries") && List.map hx indices=List.map str (list (get path "indices"))) "resolver index coverage";
      let entry_indices=ref S.empty in
      List.iter (fun entry ->
        exact entry ["index";"slot";"bytes_hex";"target"];
        let index=uaddress (get entry "index") in let key=hx index in
        require (List.mem index indices && not (S.mem key !entry_indices)) "resolver entry index";entry_indices:=S.add key !entry_indices;
        let slot=if bytes=4 then Int64.add base (Int64.mul index 4L) else base in
        require (hx slot=string entry "slot") "resolver entry slot";
        let read=M.find (hx slot^":"^string_of_int bytes) reads in require (get read "bytes_hex"=get entry "bytes_hex") "resolver read/entry bytes";
        let raw=data_value (string entry "bytes_hex") bytes in let target=if bytes=4 then Int64.add base (signed raw 32) else raw in
        require (hx target=string entry "target") "resolver target arithmetic";
        witnessed:=S.add (hx target) !witnessed
      ) (list (get path "entries"));
      if complete then require (S.equal !entry_indices (List.fold_left (fun s v -> S.add (hx v) s) S.empty indices)) "resolver missing table entry"
    ) (list (get row "paths"));
    require (S.equal !witnessed instruction.targets) "resolver unproved target";
    if complete then require_path_coverage i.roots incoming (integer (get limits "max_values")) site context
  ) (list (get report "resolutions"));
  M.iter (fun site insn -> if insn.kind="indirect" && not (S.mem site !seen) then require (not insn.complete && S.is_empty insn.targets && get report "stop"<>`Null) "resolver missing site certificate") i.instructions;
  i,sites
