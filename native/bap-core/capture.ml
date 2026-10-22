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
        require (List.mem (get row "projection") [`String "bap-bit-provenance-v3"; `String "bap-bit-provenance-v4"; `String "bap-bit-provenance-v5"; `String "bap-bit-provenance-v6"; `String "bap-bit-provenance-v7"; `String "bap-bit-provenance-v8"; `String "bap-bit-provenance-v9"]
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
(* JSON object declaration order is transport formatting, not term identity.
   Replayed constructors and untouched parsed transfers can coexist. *)
let rec term_same a b = match a,b with
  | `Assoc a,`Assoc b ->
    let sort=List.sort (fun (a,_) (b,_) -> compare a b) in
    let a=sort a and b=sort b in
    List.length a=List.length b && List.for_all2
      (fun (ka,va) (kb,vb) -> ka=kb && term_same va vb) a b
  | `List a,`List b -> List.length a=List.length b && List.for_all2 term_same a b
  | _ -> a=b
let rec eval depth index value t =
  require (depth<=32) "resolver expression depth";
  if term_same t index then Some value else match tconstant t with Some v -> Some v | None ->
  let k=kind t and w=width t in
  match opname t with
  | "binary" -> begin match eval (depth+1) index value (get k "left"),eval (depth+1) index value (get k "right") with
    | Some l,Some r -> Some (binary (integer (get k "op")) (width (get k "left")) w l r) | _ -> None end
  | "cast" -> let arg=get k "arg" in Option.map (cast (integer (get k "op")) w (width arg)) (eval (depth+1) index value arg)
  | "unary" -> Option.map (fun v -> Int64.logand (mask w) (if integer (get k "op")=0 then Int64.lognot v else Int64.neg v)) (eval (depth+1) index value (get k "arg"))
  | _ -> None
(* v2 replays scalar expressions from immutable original BIL. The constructors
   are independent OCaml implementations of the reviewed modular term algebra. *)
let term w tag rest = `Assoc ["width",`Int w;
  "kind",`Assoc (("kind",`String tag)::rest)]
let tunknown w = term w "unknown" []
let tconst w n = term w "constant" ["value",`String(hx(Int64.logand n (mask w)))]
let tinput w key = term w "input" ["key",`String key]
let rec tcast op w arg =
  let aw=width arg in
  if w=aw && List.mem op [0;2;3] then arg
  else if op=0 && opname arg="cast" && integer(get(kind arg)"op")=3 &&
      width(get(kind arg)"arg")=w then get(kind arg)"arg"
  else if op=3 && opname arg="cast" && integer(get(kind arg)"op")=3 && w>=aw then
    tcast 3 w (get(kind arg)"arg")
  else match tconstant arg with
  | Some n -> (try tconst w (cast op w aw n) with Invalid _ -> tunknown w)
  | None -> term w "cast" ["op",`Int op;"arg",arg]
let tunary op arg =
  let w=width arg in match tconstant arg with
  | Some n -> tconst w (if op=0 then Int64.lognot n else Int64.neg n)
  | None -> term w "unary" ["op",`Int op;"arg",arg]
let rec tbinary op left right =
  let aw=width left and rw=width right in
  let w=if op<=5 then 1 else aw in
  if aw<>rw then tunknown w else
  match tconstant left,tconstant right with
  | Some l,Some r -> (try tconst w (binary op aw w l r)
      with Invalid _ -> tunknown w)
  | _ ->
    let sub=if op=5 && tconstant left=Some 0L then right
      else if op=5 && tconstant right=Some 0L then left else tunknown 1 in
    if opname sub="binary" && integer(get(kind sub)"op")=17 then
      tbinary 5 (get(kind sub)"left") (get(kind sub)"right")
    else term w "binary" ["op",`Int op;"left",left;"right",right]
let ast_signed = function
  | `Int n when n>= -2147483648 && n<=2147483647 -> n
  | _ -> raise(Invalid "resolver signed BIL integer")
let ast_var var =
  exact var ["name";"index";"virtual";"width";"type"];
  ignore(str(get var "name"));ignore(ast_signed(get var "index"));
  ignore(boolean(get var "virtual"));ignore(uint(get var "width"));
  ignore(str(get var "type"))
let rec ast_expr depth expr =
  require (depth<=64) "resolver BIL depth";
  let child=ast_expr (depth+1) in
  let child_field key=child(get expr key) in
  match string expr "kind" with
  | "var" -> exact expr ["kind";"var"];ast_var(get expr "var")
  | "int" -> exact expr ["kind";"value"];ignore(str(get expr "value"))
  | "unknown" -> exact expr ["kind";"reason"];ignore(str(get expr "reason"))
  | "load" -> exact expr ["kind";"width";"mem";"addr"];
    ignore(uint(get expr "width"));child_field "mem";child_field "addr"
  | "store" -> exact expr ["kind";"width";"mem";"addr";"value"];
    ignore(uint(get expr "width"));child_field "mem";child_field "addr";child_field "value"
  | "binop" -> exact expr ["kind";"op";"lhs";"rhs"];
    ignore(ast_signed(get expr "op"));child_field "lhs";child_field "rhs"
  | "unop" -> exact expr ["kind";"op";"arg"];
    ignore(ast_signed(get expr "op"));child_field "arg"
  | "cast" -> exact expr ["kind";"op";"width";"arg"];
    ignore(ast_signed(get expr "op"));ignore(uint(get expr "width"));child_field "arg"
  | "extract" -> exact expr ["kind";"hi";"lo";"arg"];
    ignore(uint(get expr "hi"));ignore(uint(get expr "lo"));child_field "arg"
  | "concat" -> exact expr ["kind";"lhs";"rhs"];child_field "lhs";child_field "rhs"
  | "ite" -> exact expr ["kind";"condition";"yes";"no"];
    child_field "condition";child_field "yes";child_field "no"
  | "let" -> exact expr ["kind";"var";"value";"body"];
    ast_var(get expr "var");child_field "value";child_field "body"
  | "unsupported" -> exact expr ["kind"]
  | _ -> raise(Invalid "resolver BIL expression variant")
let rec ast_statements depth statements =
  require (depth<=64) "resolver BIL statement depth";
  List.iter (fun stmt -> match string stmt "kind" with
    | "move" -> exact stmt ["kind";"var";"value"];
      ast_var(get stmt "var");ast_expr (depth+1) (get stmt "value")
    | "jump" -> exact stmt ["kind";"target"];ast_expr (depth+1) (get stmt "target")
    | "if" -> exact stmt ["kind";"condition";"yes";"no"];
      ast_expr (depth+1) (get stmt "condition");
      ast_statements (depth+1) (list(get stmt "yes"));
      ast_statements (depth+1) (list(get stmt "no"))
    | "while" -> exact stmt ["kind";"condition";"body"];
      ast_expr (depth+1) (get stmt "condition");
      ast_statements (depth+1) (list(get stmt "body"))
    | "exception" -> exact stmt ["kind";"number"];ignore(ast_signed(get stmt "number"))
    | "special" | "unsupported" -> exact stmt ["kind"]
    | _ -> raise(Invalid "resolver BIL statement variant")) statements
let validate_bil_ast ast = ast_statements 0 (list ast)

let tkey var = string var "name" ^ ":" ^
  (match get var "index" with `Int n -> string_of_int n | _ -> raise(Invalid "resolver variable index")) ^ ":" ^
  string_of_bool(boolean(get var "virtual"))
let rec tlift depth env site expr =
  if depth>32 then tunknown 64 else
  let child=tlift (depth+1) env site in
  match string expr "kind" with
  | "var" ->
    let var=get expr "var" in
    (match M.find_opt (tkey var) env with Some value -> value | None ->
      let w=integer(get var "width") in
      if not(boolean(get var "virtual")) && string var "name"="RIP" then
        tconst 64 (Int64.of_string site)
      else if not(boolean(get var "virtual")) && string var "type"="imm" &&
          w>=1 && w<=64 then tinput w (tkey var)
      else tunknown (max 1 (min 64 w)))
  | "int" ->
    (try match String.split_on_char ':' (string expr "value") with
    | [n;typed] when String.length typed>1 ->
      let w=int_of_string(String.sub typed 0 (String.length typed-1)) in
      if w>=1 && w<=64 then tconst w (Int64.of_string n) else tunknown 64
    | _ -> tunknown 64 with Failure _ -> tunknown 64)
  | "cast" -> let w=integer(get expr "width") in
    if w>=1 && w<=64 then tcast (ast_signed(get expr "op")) w (child(get expr "arg"))
    else tunknown 64
  | "extract" -> let hi=integer(get expr "hi") and lo=integer(get expr "lo") in
    if lo=0 && hi<64 then tcast 0 (hi+1) (child(get expr "arg")) else tunknown 64
  | "binop" -> let op=ast_signed(get expr "op") in
    if ((op>=0 && op<=11) || (op>=16 && op<=18)) then
      tbinary op (child(get expr "lhs")) (child(get expr "rhs")) else tunknown 64
  | "unop" -> let op=ast_signed(get expr "op") in
    if op=0 || op=1 then tunary op (child(get expr "arg")) else tunknown 64
  | "load" -> let w=integer(get expr "width") in
    if List.mem w [8;16;32;64] then term w "load" ["site",`String site;
      "address",child(get expr "addr")] else tunknown 64
  | "let" ->
    let local=M.add (tkey(get expr "var")) (child(get expr "value")) env in
    tlift (depth+1) local site (get expr "body")
  | _ -> tunknown 64
let banks=["RAX";"RCX";"RDX";"RBX";"RSP";"RBP";"RSI";"RDI";
  "R8";"R9";"R10";"R11";"R12";"R13";"R14";"R15"]
let transfer_from_bil site ast =
  let env=ref M.empty and outputs=ref S.empty and jump=ref `Null and condition=ref `Null in
  List.iter (fun stmt -> match string stmt "kind" with
    | "move" -> let var=get stmt "var" in
      let value=tlift 0 !env site (get stmt "value") in
      let w=integer(get var "width") in
      if string var "type"="imm" && w>=1 && w<=64 then begin
        let value=if width value=w then value else tunknown w in
        let key=tkey var in env:=M.add key value !env;
        if not(boolean(get var "virtual")) &&
          (List.mem (string var "name") banks || List.mem (string var "name") ["CF";"ZF"])
        then outputs:=S.add key !outputs
      end
    | "jump" -> jump:=tlift 0 !env site (get stmt "target")
    | "if" -> let yes=list(get stmt "yes") in
      if list(get stmt "no")=[] && List.length yes=1 &&
        string(List.hd yes)"kind"="jump" then
        condition:=tlift 0 !env site (get stmt "condition")
    | _ -> ()) (list ast);
  `Assoc(S.elements !outputs |> List.map (fun key -> key,M.find key !env)),!jump,!condition
let clobbered key killed =
  let name=List.hd(String.split_on_char ':' key) in
  if List.mem name banks then
    List.init 8 (fun byte -> "gpr:" ^ String.lowercase_ascii name ^ ":" ^ string_of_int byte)
      |> List.exists (fun location -> S.mem location killed)
  else S.mem ("flag:" ^ String.lowercase_ascii name) killed
let rec trewrite work outputs killed t =
  require (!work>0) "resolver proof work limit";decr work;
  let w=width t and k=kind t in
  match opname t with
  | "input" -> let key=string k "key" in
    (match List.assoc_opt key (fields outputs) with Some value -> value | None ->
      if clobbered key killed then tunknown w else t)
  | "binary" -> tbinary (integer(get k "op"))
    (trewrite work outputs killed (get k "left"))
    (trewrite work outputs killed (get k "right"))
  | "unary" -> tunary (integer(get k "op")) (trewrite work outputs killed (get k "arg"))
  | "cast" -> tcast (integer(get k "op")) w (trewrite work outputs killed (get k "arg"))
  | "load" -> term w "load" ["site",get k "site";
    "address",trewrite work outputs killed (get k "address")]
  | _ -> t

(* The extractor has already expanded the current predicate to pre-state.
   Rewrite only downstream expressions through this instruction's outputs. *)
let reverse_step work outputs killed instruction_kind condition taken term guards =
  let term=trewrite work outputs killed term in
  let guards=List.map (fun guard -> `Assoc [
    "expression",trewrite work outputs killed (get guard "expression");
    "taken",get guard "taken"]) guards in
  let guards=if instruction_kind="conditional" && condition<>`Null then
    guards @ [`Assoc ["expression",condition;"taken",`Bool taken]] else guards in
  term,guards

let unique_unsigned xs = List.sort_uniq Int64.unsigned_compare xs
let rec values depth cap t =
  require (depth<=32) "resolver value depth";
  if cap=0 then None else match tconstant t with Some v -> Some [v] | None ->
  let k=kind t and w=width t in match opname t with
  | "load" when w<=16 && 1 lsl w<=cap -> Some(List.init (1 lsl w) Int64.of_int)
  | "cast" -> let arg=get k "arg" in Option.map (fun xs -> List.map (cast (integer (get k "op")) w (width arg)) xs |> unique_unsigned) (values (depth+1) cap arg)
  | "unary" -> Option.map (fun xs -> List.map (fun v -> Int64.logand (mask w) (if integer (get k "op")=0 then Int64.lognot v else Int64.neg v)) xs |> unique_unsigned) (values (depth+1) cap (get k "arg"))
  | "binary" ->
    let op=integer (get k "op") and left=get k "left" and right=get k "right" in
    let bound=match tconstant left with Some n -> Some n | None -> tconstant right in
    if op=8 && Option.fold ~none:false ~some:(fun n -> Int64.unsigned_compare n (Int64.of_int cap)<0) bound then
      let m=Option.get bound in Some (List.init (Int64.to_int m+1) Int64.of_int |> List.filter (fun v -> Int64.logand v (Int64.lognot m)=0L))
    else begin match values (depth+1) cap left,values (depth+1) cap right with
      | Some ls,Some rs when rs=[] || List.length ls<=cap / List.length rs -> Some (List.concat_map (fun l -> List.map (binary op (width left) w l) rs) ls |> unique_unsigned)
      | _ -> None end
  | _ -> None
let umin a b = if Int64.unsigned_compare a b<=0 then a else b
let umax a b = if Int64.unsigned_compare a b>=0 then a else b
let rec same_unsigned_index t index = term_same t index ||
  (opname t="cast" && integer(get(kind t)"op")=3 &&
   width t>=width(get(kind t)"arg") && same_unsigned_index(get(kind t)"arg") index)
let rec range depth t taken index =
  require (depth<=32) "resolver guard depth";
  let full=0L,mask (width index) in let k=kind t in match opname t with
  | "unary" when integer (get k "op")=0 && width t=1 -> range (depth+1) (get k "arg") (not taken) index
  | "binary" ->
    let op=integer (get k "op") and left=get k "left" and right=get k "right" in
    if (op=7 || op=8) && width t=1 then
      let al,ah=range (depth+1) left taken index and bl,bh=range (depth+1) right taken index in
      if (op=7 && not taken)||(op=8 && taken) then umax al bl,umin ah bh else umin al bl,umax ah bh
    else if same_unsigned_index left index && tconstant right<>None then
      let v=Option.get (tconstant right) and maximum=mask (width index) in begin match op,taken with
      | 2,true -> 0L,v | 3,true when v<>0L -> 0L,Int64.sub v 1L
      | 2,false when v<>maximum -> Int64.add v 1L,maximum | 3,false -> v,maximum
      | 5,true | 4,false -> v,v
      | 5,false | 4,true when v=0L -> 1L,maximum | _ -> full end
    else if op=5 && same_unsigned_index right index && tconstant left<>None then
      let v=Option.get (tconstant left) in if taken then v,v else if v=0L then 1L,mask (width index) else full
    else full
  | _ -> full
let rec term_has_unknown t = match opname t with
  | "unknown" -> true
  | "binary" -> term_has_unknown(get(kind t)"left") || term_has_unknown(get(kind t)"right")
  | "cast" | "unary" -> term_has_unknown(get(kind t)"arg")
  | "load" -> term_has_unknown(get(kind t)"address")
  | _ -> false
let rec guard_subjects depth t subjects =
  if depth>32 then subjects else match opname t with
  | "binary" ->
    let left=get(kind t)"left" and right=get(kind t)"right" in
    let subjects=if integer(get(kind t)"op")<=5 then
      List.fold_left (fun subjects subject ->
        if tconstant subject=None && not(term_has_unknown subject) &&
          not(List.exists (term_same subject) subjects) then subject::subjects else subjects)
        subjects [left;right] else subjects in
    guard_subjects (depth+1) right (guard_subjects (depth+1) left subjects)
  | "unary" | "cast" -> guard_subjects (depth+1) (get(kind t)"arg") subjects
  | "load" -> guard_subjects (depth+1) (get(kind t)"address") subjects
  | _ -> subjects
let guards_infeasible cap guards =
  let subjects=List.fold_left (fun subjects guard ->
    guard_subjects 0 (get guard "expression") subjects) [] guards in
  List.exists (fun subject ->
    let low,high=List.fold_left (fun (low,high) guard ->
      let a,b=range 0 (get guard "expression") (boolean(get guard "taken")) subject in
      umax low a,umin high b) (0L,mask(width subject)) guards in
    if Int64.unsigned_compare low high>0 then true else
    let distance=Int64.sub high low in
    if Int64.unsigned_compare distance (Int64.of_int cap)>=0 then false else
    let rec excluded offset =
      if Int64.unsigned_compare offset distance>0 then true else
      let value=Int64.add low offset in
      List.exists (fun guard -> match eval 0 subject value (get guard "expression") with
        | Some n -> (n<>0L)<>boolean(get guard "taken") | None -> false) guards &&
      excluded(Int64.add offset 1L) in excluded 0L) subjects
let rec memory_write_expr expr = match string expr "kind" with
  | "store" -> true
  | "load" -> memory_write_expr(get expr "mem") || memory_write_expr(get expr "addr")
  | "binop" | "concat" -> memory_write_expr(get expr "lhs") || memory_write_expr(get expr "rhs")
  | "unop" | "cast" | "extract" -> memory_write_expr(get expr "arg")
  | "ite" -> memory_write_expr(get expr "condition") || memory_write_expr(get expr "yes") || memory_write_expr(get expr "no")
  | "let" -> memory_write_expr(get expr "value") || memory_write_expr(get expr "body")
  | _ -> false
let rec memory_write_bil statements = List.exists (fun stmt -> match string stmt "kind" with
  | "move" -> string(get stmt "var")"type"="mem" || memory_write_expr(get stmt "value")
  | "jump" -> memory_write_expr(get stmt "target")
  | "if" -> memory_write_expr(get stmt "condition") || memory_write_bil(list(get stmt "yes")) || memory_write_bil(list(get stmt "no"))
  | _ -> true) statements
let rec writes_address_bil keys statements = List.exists (fun stmt -> match string stmt "kind" with
  | "move" -> let var=get stmt "var" in not(boolean(get var "virtual")) && S.mem(tkey var) keys
  | "if" -> writes_address_bil keys (list(get stmt "yes")) || writes_address_bil keys (list(get stmt "no"))
  | _ -> false) statements
let rec address_inputs inside t keys = match opname t with
  | "input" when inside -> S.add(string(kind t)"key") keys
  | "load" -> address_inputs true (get(kind t)"address") keys
  | "binary" -> address_inputs inside (get(kind t)"right") (address_inputs inside (get(kind t)"left") keys)
  | "cast" | "unary" -> address_inputs inside (get(kind t)"arg") keys
  | _ -> keys
let has_repeat word =
  let _,repeated=List.fold_left (fun (seen,repeated) (site,_) ->
    S.add site seen,repeated || S.mem site seen) (S.empty,false) word in repeated
let cycle_window word =
  let word=Array.of_list word in
  let seen=ref M.empty and cycle=ref None and valid=ref true in
  Array.iteri (fun at (site,taken) -> match !cycle with
    | Some(first,repeated) -> let relative=at-repeated in
      if relative>=repeated-first || fst word.(first+relative)<>site ||
        (relative>0 && snd word.(first+relative)<>taken) then valid:=false
    | None -> (match M.find_opt site !seen with
      | Some first -> cycle:=Some(first,at)
      | None -> seen:=M.add site at !seen)) word;
  if !valid then !cycle else None
let stable_cycle word instructions transfers term guards = match cycle_window word with
  | None -> false
  | Some(first,repeated) ->
    let keys=List.fold_left (fun keys guard -> address_inputs false (get guard "expression") keys)
        (address_inputs false term S.empty) guards in
    let word=Array.of_list word in
    let stable=ref true in
    for at=first to repeated-1 do
      let site=fst word.(at) in
      match M.find_opt site transfers with
      | None -> stable:=false
      | Some transfer ->
        let instruction=M.find site instructions in
        let bil=list(Yojson.Safe.from_string(string transfer "ast")) in
        if instruction.kind="call" || S.mem "memory:any" instruction.may ||
          memory_write_bil bil || writes_address_bil keys bil ||
          S.exists (fun key -> clobbered key instruction.may) keys then stable:=false
    done; !stable

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
  let index=get s "left" in let index=if opname index="cast" && integer (get (kind index) "op")=3 then get (kind index) "arg" else index in
  require (not(term_has_unknown index)) "resolver unknown table index";base,index
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
  mutable frontier: bool;
  children: ((string * bool), path_context) Hashtbl.t;
}
let path_context () = {terminal=false; frontier=false; children=Hashtbl.create 2}
let require_path_coverage roots incoming max_values site context =
  (* Match the producer: push ascending predecessors, then pop the last one.
     The budget includes siblings retained from earlier branching contexts. *)
  let pending=ref [site,context] and pending_count=ref 1 in
  require (max_values>0) "resolver frontier budget";
  while !pending<>[] do
    let cursor,context=List.hd !pending in
    pending:=List.tl !pending;decr pending_count;
    require (not context.frontier || context.terminal) "resolver invalid terminal frontier";
    require (context.frontier || context.terminal=S.mem cursor roots)
      "resolver uncovered root context";
    let parents=if context.frontier then [] else match M.find_opt cursor incoming with Some xs -> List.sort compare xs | None -> [] in
    require (Hashtbl.length context.children=List.length parents)
      "resolver uncovered incoming path";
    List.iter (fun ((parent,_) as edge) ->
      match Hashtbl.find_opt context.children edge with
      | Some child ->
        require (!pending_count<max_values) "resolver frontier budget";
        pending:=(parent,child)::!pending;incr pending_count
      | None -> raise (Invalid "resolver uncovered incoming path")) parents
  done
let admit_resolved_current ~loop_checker j snapshot =
  exact j ["normalized";"capture";"target_resolution"];
  let i,sites=admit (`Assoc ["normalized",get j "normalized";"capture",get j "capture"]) snapshot in
  let report=get j "target_resolution" and capture=get j "capture" in
  exact report ["schema";"profile";"memory_premise";"snapshot";"artifact_sha256";"graph_sha256";"limits";"resolutions";"data_reads";"transfers";"stop"];
  let local=string report "schema"="ariadne.indirect-target-resolution/v3" &&
    string report "profile"="captured-local-indirect-targets/v2" in
  require (local &&
    string report "memory_premise"="FrozenCapturedControlData" && string report "snapshot"=snapshot
    && get report "artifact_sha256"=get capture "artifact_sha256") "resolver identity/premise";
  digest (string report "graph_sha256");
  let limits=get report "limits" in
  let keys=["max_entries";"max_targets";"max_read_bytes";"max_evidence_bytes";
    "max_values";"max_steps";"max_path_steps";"max_rounds";"max_elapsed_ms"] in
  exact limits keys;List.iter (fun key -> ignore(uint(get limits key))) keys;
  let budget key=uint(get limits key) in
  let within key count=Int64.unsigned_compare (Int64.of_int count) (budget key)<=0 in
  (* Clamp only host representations used by replay loops, never policy budgets. *)
  let limit key=let n=budget key in
    if Int64.unsigned_compare n (Int64.of_int max_int)>0 then max_int else Int64.to_int n in
  let empty_evidence_stop=get report "stop"=`String "resolution-evidence-limit"
    && get report "resolutions"=`List [] && get report "data_reads"=`List []
    && get report "transfers"=`List [] in
  require (within "max_evidence_bytes" (String.length (Yojson.Safe.to_string report))
    || empty_evidence_stop) "resolver evidence budget";
  if List.exists (fun key -> budget key=0L)
      ["max_values";"max_steps";"max_rounds";"max_elapsed_ms"] then
    require (get report "data_reads"=`List [] && List.for_all (fun row ->
      get row "paths"=`List [] && get row "targets"=`List []) (list (get report "resolutions")))
      "resolver zero work budget";
  let transfers=List.fold_left (fun map t ->
    exact t ["site";"bytes_hex";"ast";"ast_sha256";"outputs";"jump";"condition"];
    let a=address (string t "site") in require (not (M.mem a map) && M.mem a sites) "resolver transfer domain";
    let source=M.find a sites in require (get source "bytes"=get t "bytes_hex" && get source "ast_sha256"=get t "ast_sha256") "resolver semantic source binding";
    digest (string t "ast_sha256");let ast=Yojson.Safe.from_string (string t "ast") in json_shape 0 ast;ignore (list ast);
    if local then begin
      validate_bil_ast ast;
      let outputs,jump,condition=transfer_from_bil a ast in
      require (term_same outputs (get t "outputs") && term_same jump (get t "jump") &&
        term_same condition (get t "condition")) "resolver transfer BIL replay"
    end;
    M.add a t map) M.empty (list (get report "transfers")) in
  let read_bytes=ref 0 in
  let reads=List.fold_left (fun map r ->
    exact r ["address";"requested";"bytes_hex";"spans";"conflict_sources";"stop"];
    let a=address (string r "address") and requested=integer (get r "requested") in
    require (requested=4 || requested=8) "resolver read width";
    let key=a^":"^string_of_int requested in require (not (M.mem key map)) "resolver duplicate read";
    read_bytes := !read_bytes+requested;
    require (within "max_read_bytes" !read_bytes) "resolver read budget";
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
    exact row ["site";"targets";"complete";"paths";"unresolved";"coverage"];
    let site=address (string row "site") in require (M.mem site i.instructions && not (S.mem site !seen)) "resolver resolution domain";seen:=S.add site !seen;
    let instruction=M.find site i.instructions and complete=boolean (get row "complete") in
    require (instruction.kind="indirect" && instruction.complete=complete && S.equal instruction.targets (set ~addr:true (get row "targets"))) "resolver normalized targets";
    retained_targets:=S.union !retained_targets instruction.targets;
    require (within "max_targets" (S.cardinal !retained_targets)) "resolver target budget";
    let coverage=get row "coverage" in
    let inductive=match string coverage "kind" with
      | "existing_prefix_tree" ->
        exact coverage ["kind";"path_receipt_refs"];
        require (get coverage "path_receipt_refs"=`List(List.mapi
          (fun n _ -> `Int n) (list(get row "paths"))))
          "resolver prefix receipt references";
        false
      | "inductive_dispatch" ->
        exact coverage ["kind";"receipt"];
        (match loop_checker with
        | Some check -> check i sites transfers reads report row
        | None -> raise(Invalid "loop closure checker unavailable"));
        true
      | _ -> raise(Invalid "resolver coverage kind") in
    if complete then require (list (get row "unresolved")=[] && get report "stop"=`Null && list (get row "paths")<>[]) "resolver residual alternatives";
    let witnessed=ref S.empty and context=path_context () in
    List.iter (fun path ->
      let path_keys=["root";"reverse_path";"reverse_edges";"form";"base";"indices";"entries";"expression";"guards"] in
      let frontier=match List.assoc_opt "frontier" (fields path) with
        | None -> exact path path_keys;false
        | Some value -> require local "resolver legacy frontier";
          exact path ("frontier"::path_keys);boolean value in
      let chain=list (get path "reverse_path") |> List.map (fun a -> address (str a)) and edges=list (get path "reverse_edges") |> List.map boolean in
      require (List.length chain=List.length edges && List.length chain<limit "max_path_steps"
        && within "max_steps" (List.length chain+1)) "resolver edge word/work budget";
      require (within "max_entries" (List.length (list (get path "indices")))
        && within "max_entries" (List.length (list (get path "entries")))) "resolver entry budget";
      let cursor=ref site and path_seen=ref S.empty and prefix=ref context in
      let term=ref (match M.find_opt site transfers with
        | Some transfer -> get transfer "jump" | None -> `Null) in
      let guards=ref [] and work=ref(limit "max_steps") in
      List.iter2 (fun parent taken ->
        require (parent<>site && M.mem parent i.instructions &&
          (not(S.mem parent !path_seen) || (local && frontier && string path "form"="infeasible")))
          "resolver cyclic/absent predecessor";
        path_seen:=S.add parent !path_seen;
        require (List.mem (!cursor,taken) (local_edges (M.find parent i.instructions))) "resolver missing predecessor edge";
        let child=match Hashtbl.find_opt (!prefix).children (parent,taken) with
          | Some child -> child
          | None -> let child=path_context () in Hashtbl.add (!prefix).children (parent,taken) child; child in
        prefix:=child;
        if local then begin
          let instruction=M.find parent i.instructions in
          let transfer=M.find_opt parent transfers in
          let outputs=match transfer with Some t -> get t "outputs" | None -> `Assoc [] in
          let condition=match transfer with Some t -> get t "condition" | None -> `Null in
          require (!term<>`Null) "resolver jump evidence missing";
          let next,next_guards=reverse_step work outputs instruction.may
              instruction.kind condition taken !term !guards in
          term:=next;guards:=next_guards
        end;
        cursor:=parent
      ) chain edges;
      require (!cursor=string path "root" && (frontier || S.mem !cursor i.roots) &&
        not(frontier && S.mem !cursor i.roots)) "resolver root witness";
      if local then require (term_same !term (get path "expression") &&
        term_same (`List !guards) (get path "guards")) "resolver path semantic replay";
      require (not (!prefix).terminal) "resolver duplicate path";
      (!prefix).terminal<-true;(!prefix).frontier<-frontier;
      require (M.mem site transfers && get (M.find site transfers) "jump"<>`Null) "resolver jump semantic source";
      let expression=get path "expression" and form=string path "form" in
      let word=List.combine chain edges in
      if form="infeasible" then begin
        require (local && frontier && string path "base"=hx 0L &&
          list(get path "indices")=[] && list(get path "entries")=[])
          "resolver infeasible receipt shape";
        require (guards_infeasible (limit "max_values") !guards)
          "resolver infeasible guard domain";
        require (not(has_repeat word) || stable_cycle word i.instructions transfers !term !guards)
          "resolver infeasible cycle stability"
      end else begin
      let base,index,bytes=if form="relative32" then let b,x=relative expression in b,Some x,4
        else begin require (form="pointer64" && opname expression="load" && width expression=64) "resolver pointer form";
          match tconstant (get (kind expression) "address") with Some b -> b,None,8 | None -> raise (Invalid "resolver pointer address") end in
      require (hx base=string path "base") "resolver base binding";
      let indices=match index with None -> [0L] | Some index ->
        let guards=list (get path "guards") in
        let lo,hi=List.fold_left (fun (lo,hi) guard -> exact guard ["expression";"taken"];
          let a,b=range 0 (get guard "expression") (boolean (get guard "taken")) index in umax lo a,umin hi b) (0L,mask (width index)) guards in
        let possible=match values 0 (limit "max_values") index with Some v -> v | None ->
          let delta=Int64.sub hi lo in require (Int64.unsigned_compare lo hi<=0 && Int64.unsigned_compare delta (budget "max_entries")<0 &&
            Int64.unsigned_compare delta (Int64.of_int max_int)<0) "resolver unbounded index";
          List.init (Int64.to_int delta+1) (fun n -> Int64.add lo (Int64.of_int n)) in
        List.filter (fun value -> Int64.unsigned_compare value lo>=0 && Int64.unsigned_compare value hi<=0 && List.for_all (fun g ->
          match eval 0 index value (get g "expression") with None -> true | Some n -> (n<>0L)=boolean (get g "taken")) guards) possible |> unique_unsigned in
      require (within "max_entries" (List.length indices) && List.map hx indices=List.map str (list (get path "indices"))) "resolver index coverage";
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
      end
    ) (list (get row "paths"));
    require (S.equal !witnessed instruction.targets) "resolver unproved target";
    if complete && not inductive then
      require_path_coverage i.roots incoming (limit "max_values") site context
  ) (list (get report "resolutions"));
  M.iter (fun site insn -> if insn.kind="indirect" && not (S.mem site !seen) then require (not insn.complete && S.is_empty insn.targets && get report "stop"<>`Null) "resolver missing site certificate") i.instructions;
  i,sites

(* v1/v2 receipts keep their frozen admission algorithm. The new coverage sum
   is not retroactively accepted by a legacy profile. *)
let admit_resolved ?loop_checker j snapshot =
  require (List.for_all (fun row -> get row "projection" <> `String "bap-bit-provenance-v9")
      (list (get (get j "capture") "sites")))
    "source flag extension does not admit target resolution";
  let report=get j "target_resolution" in
  if string report "schema"="ariadne.indirect-target-resolution/v3" then
    admit_resolved_current ~loop_checker j snapshot
  else Legacy_capture.admit_resolved j snapshot
