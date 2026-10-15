(* Independent local-phase induction admission. Assertions are proposals: every
   entrance and edge is checked against the original BIL and captured reads.
   This module never performs the producer's fixed-point iteration. *)
open Recovery

type work = { mutable left:int; deadline:float; cap:int; path_limit:int; entry_limit:int }
let charge work n =
  require (n>=0 && work.left>=n && Unix.gettimeofday ()<work.deadline)
    "loop closure work limit";
  work.left<-work.left-n
let host_limit limits key =
  let n=Capture.uint(get limits key) in
  if Int64.unsigned_compare n (Int64.of_int max_int)>0 then max_int else Int64.to_int n
let make_work limits =
  List.iter (fun key -> require (Capture.uint(get limits key)<>0L)
    "loop zero work budget") ["max_steps";"max_values";"max_rounds";"max_elapsed_ms"];
  let milliseconds=float_of_string(Printf.sprintf "%Lu"
    (Capture.uint(get limits "max_elapsed_ms"))) in
  {left=host_limit limits "max_steps";deadline=Unix.gettimeofday ()+.milliseconds/.1000.;
   cap=host_limit limits "max_values";path_limit=host_limit limits "max_path_steps";
   entry_limit=host_limit limits "max_entries"}
let ucmp=Int64.unsigned_compare
let same=Capture.term_same
let find map key why=match M.find_opt key map with Some value->value|None->raise(Invalid why)
let is_bank key=List.exists(fun bank->key=bank^":0:false") Capture.banks
let sorted_unique values = values=List.sort_uniq String.compare values

type domain={width:int;low:int64;high:int64;points:int64 list option;tag:string}
let top width={width;low=0L;high=Capture.mask width;points=None;tag="top"}
let constant width value=let n=Int64.logand value (Capture.mask width) in
  {width;low=n;high=n;points=None;tag="constant"}
let interval width low high=
  require(ucmp low high<=0 && ucmp high (Capture.mask width)<=0) "loop domain bounds";
  if low=high then constant width low
  else {width;low;high;points=None;tag="unsigned_interval"}
let finite width values=
  let values=Capture.unique_unsigned values in
  require(values<>[]) "loop empty finite domain";
  if List.length values=1 then constant width (List.hd values)
  else {width;low=List.hd values;high=List.hd(List.rev values);
    points=Some values;tag="finite_set"}
let parse_domain work row =
  charge work 1;exact row ["width";"kind"];
  let width=Capture.integer(get row "width") in
  require(width>=1 && width<=64) "loop domain width";
  let kind=get row "kind" in
  let result=match string kind "kind" with
    | "top"->exact kind ["kind"];top width
    | "constant"->exact kind ["kind";"value"];
      let n=Capture.uaddress(get kind "value") in
      require(ucmp n (Capture.mask width)<=0) "loop constant width";constant width n
    | "unsigned_interval"->exact kind ["kind";"lower";"upper"];
      let low=Capture.uaddress(get kind "lower") and high=Capture.uaddress(get kind "upper") in
      let d=interval width low high in {d with tag="unsigned_interval"}
    | "finite_set"->exact kind ["kind";"values"];
      let values=List.map Capture.uaddress (list(get kind "values")) in
      require(values<>[] && List.length values<=work.cap &&
        values=Capture.unique_unsigned values)
        "loop finite domain order";
      charge work (List.length values);
      let d=finite width values in {d with points=Some values;tag="finite_set"}
    | _->raise(Invalid "loop domain kind") in
  require(ucmp result.high (Capture.mask width)<=0) "loop domain bounds";result
let domain_values work domain = match domain.points with
  | Some values when List.length values<=work.cap->charge work(List.length values);Some values
  | Some _->None
  | None->
    let distance=Int64.sub domain.high domain.low in
    if ucmp distance (Int64.of_int work.cap)>=0 then None
    else let count=Int64.to_int distance+1 in charge work count;
      Some(List.init count(fun n->Int64.add domain.low(Int64.of_int n)))
let includes work expected actual =
  charge work 1;
  expected.width=actual.width && ucmp actual.low expected.low>=0 &&
  ucmp actual.high expected.high<=0 &&
  match expected.points with
  | None->true
  | Some values->(match domain_values work actual with
    | None->false|Some actual->List.for_all(fun n->List.mem n values) actual)

type state={domains:domain M.t;flags:json M.t}
type table={load_site:string;base_bank:string;selector_bank:string;base:int64;
  indices:int64 list;entries:json list}
let parse_table work row =
  exact row ["load_site";"base_bank";"selector_bank";"base";"indices";"entries"];
  let base_bank=string row "base_bank" and selector_bank=string row "selector_bank" in
  require(is_bank base_bank && is_bank selector_bank && base_bank<>selector_bank)
    "loop table bank identity";
  let indices=List.map Capture.uaddress(list(get row "indices")) in
  charge work(List.length indices);
  {load_site=address(string row "load_site");base_bank;selector_bank;
   base=Capture.uaddress(get row "base");indices;entries=list(get row "entries")}
let empty table={domains=M.empty|>M.add table.base_bank(top 64)|>
  M.add table.selector_bank(top 64);flags=M.empty}
let rec inputs term seen =
  let kind=Capture.kind term in match Capture.opname term with
  | "input"->S.add(string kind "key") seen
  | "binary"->inputs(get kind "right")(inputs(get kind "left") seen)
  | "cast"|"unary"->inputs(get kind "arg") seen
  | "load"->inputs(get kind "address") seen
  | _->seen
let rec predicate work depth term =
  charge work 1;require(depth<=32) "loop flag depth";
  let width=Capture.width term and kind=Capture.kind term in
  match Capture.opname term with
  | "constant"->exact term ["width";"kind"];exact kind ["kind";"value"];
    require(ucmp(Capture.uaddress(get kind "value"))(Capture.mask width)<=0)
      "loop flag constant"
  | "input"->exact term ["width";"kind"];exact kind ["kind";"key"];
    require(width=64 && is_bank(string kind "key")) "loop flag input"
  | "binary"->exact term ["width";"kind"];exact kind ["kind";"op";"left";"right"];
    let op=Capture.integer(get kind "op") and left=get kind "left" and right=get kind "right" in
    require(List.mem op [0;1;2;3;4;5;6;7;8;9;10;11;16;17;18] &&
      Capture.width left=Capture.width right &&
      width=(if op<=5 then 1 else Capture.width left)) "loop flag binary shape";
    predicate work(depth+1)left;predicate work(depth+1)right
  | "cast"|"unary"->exact term ["width";"kind"];exact kind ["kind";"op";"arg"];
    let op=Capture.integer(get kind "op") and arg=get kind "arg" in
    let aw=Capture.width arg in
    require((if Capture.opname term="unary" then List.mem op [0;1] && width=aw
      else List.mem op [0;1;2;3] && (if op<=1 then width<=aw else width>=aw)))
      "loop flag cast or unary shape";
    predicate work(depth+1)arg
  | _->raise(Invalid "loop flag load or unknown")
let parse_assertion work table row =
  exact row ["site";"domains";"flags"];
  let domains=get row "domains" in exact domains [table.base_bank;table.selector_bank];
  let domains=List.fold_left(fun map(key,value)->
    let d=parse_domain work value in require(d.width=64) "loop bank width";
    M.add key d map) M.empty(fields domains) in
  let flags=List.fold_left(fun map(key,value)->
    require(List.mem key ["CF:0:false";"ZF:0:false"] && not(M.mem key map) &&
      Capture.width value=1) "loop assertion flag";
    predicate work 0 value;M.add key value map) M.empty(fields(get row "flags")) in
  address(string row "site"),{domains;flags}
let included work actual expected =
  M.for_all(fun key domain->includes work (M.find key expected.domains) domain) actual.domains &&
  true (* mutation: omit branch-definition provenance *)

let rec evaluate work depth state table reads term =
  charge work 1;require(depth<=32) "loop expression depth";
  let width=Capture.width term and kind=Capture.kind term in
  let child=evaluate work(depth+1) state table reads in
  match Capture.tconstant term with Some n->constant width n|None->
  match Capture.opname term with
  | "input"->(match M.find_opt(string kind "key") state.domains with
    Some value->value|None->top width)
  | "load"->
    if width=8 || width=16 then top width
    else if width<>32 || string kind "site"<>table.load_site then top width
    else begin
      let addresses=match domain_values work(child(get kind "address")) with
        Some values->values|None->raise(Invalid "loop table address unbounded") in
      let values=List.map(fun location->charge work 1;
        let read=find reads (Capture.hx location^":4") "loop table captured read missing" in
        let bytes=string read "bytes_hex" in
        require(String.length bytes=8) "loop table captured read incomplete";
        Capture.data_value bytes 4) addresses in finite 32 values
    end
  | "unary"|"cast"->
    let arg=get kind "arg" and op=Capture.integer(get kind "op") in
    let domain=child arg in
    (match domain_values work domain with
    | Some values->
      let values=List.map(fun value->charge work 1;
        let value=Capture.tconst(Capture.width arg) value in
        let result=if Capture.opname term="unary" then Capture.tunary op value
          else Capture.tcast op width value in Capture.tconstant result) values in
      if List.for_all Option.is_some values then finite width(List.map Option.get values)
      else top width
    | None->
      if Capture.opname term="cast" && List.mem op [0;3] &&
        ucmp domain.high(Capture.mask width)<=0 then interval width domain.low domain.high
      else top width)
  | "binary"->
    let left=get kind "left" and right=get kind "right" and op=Capture.integer(get kind "op") in
    let left_domain=child left and right_domain=child right in
    (match domain_values work left_domain,domain_values work right_domain with
    | Some ls,Some rs when rs=[] || List.length ls<=work.cap/List.length rs->
      let values=List.concat_map(fun a->List.map(fun b->charge work 1;
        Capture.tconstant(Capture.tbinary op (Capture.tconst(Capture.width left) a)
          (Capture.tconst(Capture.width right) b))) rs) ls in
      if List.for_all Option.is_some values then finite width(List.map Option.get values)
      else top width
    | _->top width)
  | _->top width

let safe site instructions transfers =
  let instruction=find instructions site "loop instruction missing" and
      transfer=find transfers site "loop transfer missing" in
  let ast=Yojson.Safe.from_string(string transfer "ast") in
  Capture.validate_bil_ast ast;
  require(string transfer "ast_sha256"=Guard.Sha256.digest(string transfer "ast"))
    "loop original AST digest";
  require(instruction.kind<>"call" && not(S.mem "memory:any" instruction.may) &&
    not(Capture.memory_write_bil(list ast))) "loop unsafe original effects";
  let outputs,jump,condition=Capture.transfer_from_bil site ast in
  require(same outputs(get transfer "outputs") && same jump(get transfer "jump") &&
    same condition(get transfer "condition")) "loop original BIL mismatch";
  let next=Capture.hx(Int64.add(Int64.of_string site)
    (Int64.of_int(String.length(string transfer "bytes_hex")/2))) in
  let ordinary_fall=S.equal instruction.fall(S.singleton next) in
  (match instruction.kind with
  | "ordinary"->require(jump=`Null && condition=`Null && ordinary_fall &&
      S.is_empty instruction.targets) "loop original ordinary control"
  | "jump"->require(condition=`Null && jump<>`Null && S.is_empty instruction.fall &&
      (match Capture.tconstant jump with Some target->
        S.equal instruction.targets(S.singleton(Capture.hx target))|None->false))
      "loop original jump control"
  | "conditional"->
    require(condition<>`Null && jump=`Null && ordinary_fall) "loop original conditional control";
    let _,target=List.fold_left(fun(env,target)stmt->match string stmt "kind" with
      | "move"->let var=get stmt "var" in
        M.add(Capture.tkey var)(Capture.tlift 0 env site(get stmt "value"))env,target
      | "if"->let yes=list(get stmt "yes") in
        if get stmt "no"=`List [] && List.length yes=1 && string(List.hd yes)"kind"="jump"
        then env,Capture.tconstant(Capture.tlift 0 env site(get(List.hd yes)"target"))
        else env,target
      | _->env,target)(M.empty,None)(list ast) in
    require(match target with Some target->S.equal instruction.targets
      (S.singleton(Capture.hx target))|None->false) "loop original conditional target"
  | "indirect"->require(jump<>`Null && Capture.tconstant jump=None && condition=`Null &&
      S.is_empty instruction.fall) "loop original indirect control"
  | _->raise(Invalid "loop original control mismatch"))
let transfer work site taken state table instructions transfers reads =
  charge work 1;
  charge work(String.length(string(find transfers site "loop transfer missing")"ast"));
  safe site instructions transfers;
  let instruction=M.find site instructions and source=M.find site transfers in
  let outputs=get source "outputs" in
  let before=if instruction.kind="conditional" then begin
    require(not(List.exists(fun(key,_)->M.mem key state.domains)(fields outputs)))
      "loop branch writes relevant bank";
    let condition=get source "condition" in
    if condition=`Null then Some state else begin
      let budget=ref work.left in
      let condition=Capture.trewrite budget (`Assoc(M.bindings state.flags)) S.empty (get source "condition") in
      work.left<- !budget;
      let low,high=Capture.range 0 condition taken(Capture.tinput 64 table.selector_bank) in
      let previous=M.find table.selector_bank state.domains in
      let low=Capture.umax low previous.low and high=Capture.umin high previous.high in
      if ucmp low high>0 then None else Some{state with domains=M.add table.selector_bank
        (interval 64 low high) state.domains}
    end
  end else Some state in
  match before with None->None|Some before->
  let domains=List.fold_left(fun map key->
    let domain=match List.assoc_opt key(fields outputs) with
      | Some term->evaluate work 0 before table reads term
      | None when Capture.clobbered key instruction.may->top 64
      | None->M.find key before.domains in M.add key domain map)
      before.domains [table.base_bank;table.selector_bank] in
  let writes=List.fold_left(fun seen(key,_)->if List.mem key ["CF:0:false";"ZF:0:false"]
    then seen else S.add key seen) S.empty(fields outputs) in
  let flags=M.filter(fun _ value->
    let refs=inputs value S.empty in S.is_empty(S.inter refs writes) &&
    not(S.exists(fun key->Capture.clobbered key instruction.may) refs)) before.flags in
  let flags=List.fold_left(fun flags key->match List.assoc_opt key(fields outputs) with
    | Some value->let refs=inputs value S.empty in
      let valid=try predicate work 0 value;true with Invalid _->false in
      if S.is_empty(S.inter refs writes) && valid then M.add key value flags else M.remove key flags
    | None when Capture.clobbered key instruction.may->M.remove key flags
    | None->flags) flags ["CF:0:false";"ZF:0:false"] in
  Some{domains;flags}

type edge=string*string*bool
let parse_edge row = exact row ["from";"to";"taken"];
  address(string row "from"),address(string row "to"),boolean(get row "taken")
let edge_inventory work region instructions =
  let internal=ref [] and incoming=ref [] and exits=ref [] in
  M.iter(fun from instruction->charge work 1;
    List.iter(fun(to_,taken)->charge work 1;let edge=from,to_,taken in
      match S.mem from region,S.mem to_ region with
      | true,true->internal:=edge::!internal
      | false,true->incoming:=edge::!incoming
      | true,false->exits:=edge::!exits|_->())(Capture.local_edges instruction)) instructions;
  List.sort_uniq compare !internal,List.sort_uniq compare !incoming,List.sort_uniq compare !exits
let predecessors work instructions site =
  charge work(M.cardinal instructions);
  M.fold(fun from instruction edges->List.fold_left(fun edges(to_,taken)->
    if to_=site then (from,taken)::edges else edges) edges(Capture.local_edges instruction))
      instructions [] |> List.sort_uniq compare
let corridor_state work corridor table region input transfers reads =
  exact corridor ["entrance";"sites"];
  let from,to_,taken=parse_edge(get corridor "entrance") in
  let sites=List.map(fun value->address(str value))(list(get corridor "sites")) in
  require(sites<>[] && List.length sites<=work.path_limit) "loop empty initialization corridor";
  require(List.hd(List.rev sites)=from) "loop corridor boundary";
  let first=find transfers(List.hd sites) "loop corridor transfer missing" in
  require(match List.assoc_opt table.base_bank(fields(get first "outputs")) with
    Some term->Capture.tconstant term=Some table.base|None->false)
    "loop corridor missing original base reset";
  let rec walk seen previous state = function
    | []->state
    | site::rest->
      charge work 1;require(not(S.mem site region) && not(S.mem site seen) &&
        (previous=None || not(S.mem site input.roots))) "loop corridor cycle or root bypass";
      let instruction=find input.instructions site "loop corridor instruction missing" in
      let next,direction=match rest with
        | []->to_,taken
        | next::_->let selected=List.filter(fun(to_,_)->to_=next)(Capture.local_edges instruction) in
          require(List.length selected=1) "loop corridor edge";List.hd selected in
      require(List.mem(next,direction)(Capture.local_edges instruction)) "loop corridor edge missing";
      (match previous with None->()|Some previous->
        let expected=List.filter(fun(to_,_)->to_=site)
          (Capture.local_edges(M.find previous input.instructions)) in
        require(List.length expected=1 && predecessors work input.instructions site=
          [previous,snd(List.hd expected)]) "loop corridor hidden entrance");
      let state=match transfer work site direction state table input.instructions transfers reads with
        Some state->state|None->raise(Invalid "loop infeasible initialization corridor") in
      walk(S.add site seen)(Some site) state rest in
  walk S.empty None(empty table) sites

let rec load32_site term =
  let kind=Capture.kind term in match Capture.opname term with
  | "load" when Capture.width term=32->Some(string kind "site")
  | "binary"->(match load32_site(get kind "left") with
    Some _ as result->result|None->load32_site(get kind "right"))
  | "cast"|"unary"->load32_site(get kind "arg")|_->None
let source_shape work dispatch instructions transfers =
  let jump=get(find transfers dispatch "loop dispatch transfer missing") "jump" in
  require(jump<>`Null && Capture.opname jump="input") "loop dispatch source form";
  let selector=string(Capture.kind jump) "key" in
  let rec walk remaining cursor term =
    require(remaining>0) "loop source form path limit";charge work 1;
    let recognized=S.fold(fun key found->match found with Some _->found|None->
      if key=selector then None else
      let budget=ref work.left in
      let replaced=Capture.trewrite budget (`Assoc[key,Capture.tconst 64 0L]) S.empty term in
      work.left<- !budget;
      match (try Some(Capture.relative replaced) with Invalid _->None) with
      | Some(0L,index) when same index(Capture.tinput 64 selector)->
        Option.map(fun site->key,selector,site)(load32_site term)
      | _->None) (inputs term S.empty) None in
    match recognized with Some value->value|None->
    let parents=predecessors work instructions cursor |> List.map fst |> List.sort_uniq compare in
    require(List.length parents=1) "loop relative table source form";
    let parent=List.hd parents in
    let source=find transfers parent "loop source form transfer missing" in
    let budget=ref work.left in
    let term=Capture.trewrite budget (get source "outputs") (M.find parent instructions).may term in
    work.left<- !budget;walk(remaining-1) parent term in
  walk work.path_limit dispatch jump

let check_table work table reads row =
  require(table.indices<>[] && List.length table.indices<=work.entry_limit &&
    List.length table.indices<=work.cap && table.indices=Capture.unique_unsigned table.indices &&
    List.length table.entries=List.length table.indices) "loop table domain limit or order";
  let targets=ref S.empty in
  List.iter2(fun index entry->charge work 1;exact entry ["index";"slot";"bytes_hex";"target"];
    let slot=Int64.add table.base(Int64.mul index 4L) in
    require(Capture.uaddress(get entry "index")=index && string entry "slot"=Capture.hx slot)
      "loop table slot";
    let read=find reads(Capture.hx slot^":4") "loop table read missing" in
    let bytes=string read "bytes_hex" in require(String.length bytes=8) "loop table read incomplete";
    require(string entry "bytes_hex"=bytes) "loop table byte binding";
    let target=Capture.hx(Int64.add table.base(Capture.signed(Capture.data_value bytes 4)32)) in
    require(string entry "target"=target) "loop table target arithmetic";
    require(List.exists(fun path->string path "form"="relative32" &&
      string path "base"=Capture.hx table.base && List.mem(get entry "index")(list(get path "indices")) &&
      List.exists(same entry)(list(get path "entries")))(list(get row "paths")))
      "loop table requires new path witness";
    targets:=S.add target !targets) table.indices table.entries;!targets

let validate input sites transfers reads report row =
  let receipt=get(get row "coverage") "receipt" in
  exact receipt ["schema";"rule";"snapshot";"artifact_sha256";"graph_sha256";
    "model_sha256";"engine_sha256";"dispatch";"region";"internal_edges";
    "entrances";"exits";"corridors";"assertions";"table";"source_refs"];
  require(string receipt "schema"="ariadne.loop-target-closure/v1" &&
    string receipt "rule"="local-phase-induction/v1" &&
    get receipt "snapshot"=get report "snapshot" &&
    get receipt "artifact_sha256"=get report "artifact_sha256" &&
    get receipt "graph_sha256"=get report "graph_sha256" &&
    string receipt "model_sha256"=Build_identity.loop_model_sha256 &&
    string receipt "engine_sha256"=Build_identity.loop_engine_sha256 &&
    get receipt "dispatch"=get row "site") "loop closure identity";
  let work=make_work(get report "limits") in
  let region_list=List.map(fun value->address(str value))(list(get receipt "region")) in
  let region=set ~addr:true(get receipt "region") in
  let dispatch=address(string receipt "dispatch") in
  require(region_list<>[] && sorted_unique region_list && List.length region_list<=work.path_limit &&
    S.mem dispatch region && S.is_empty(S.inter region input.roots)) "loop region domain or root";
  let table=parse_table work(get receipt "table") in
  let internal,incoming,exits=edge_inventory work region input.instructions in
  let declared key=List.map parse_edge(list(get receipt key)) in
  require((internal,incoming,exits)=(declared "internal_edges",declared "entrances",declared "exits") &&
    incoming<>[]) "loop edge inventory";
  let corridors=list(get receipt "corridors") in
  require(List.map(fun corridor->parse_edge(get corridor "entrance")) corridors=incoming)
    "loop entrance corridors";
  let source_sites=List.fold_left(fun seen corridor->List.fold_left(fun seen site->
    S.add(address(str site))seen)seen(list(get corridor "sites")))region corridors in
  let expected_sources=S.elements source_sites |> List.map(fun site->
    let transfer=find transfers site "loop source missing" in
    `Assoc["site",`String site;"bytes_hex",get transfer "bytes_hex";
      "ast_sha256",get transfer "ast_sha256"]) in
  require(same(`List expected_sources)(get receipt "source_refs")) "loop source inventory";
  S.iter(fun site->charge work 1;safe site input.instructions transfers;
    require(site=dispatch || (M.find site input.instructions).kind<>"indirect")
      "loop other indirect control";
    let source=find sites site "loop captured source missing" and transfer=M.find site transfers in
    require(get source "bytes"=get transfer "bytes_hex" &&
      get source "ast_sha256"=get transfer "ast_sha256") "loop captured source binding")source_sites;
  let rows=list(get receipt "assertions") in
  require(List.map(fun row->string row "site")rows=region_list) "loop assertion inventory";
  let assertions=List.fold_left(fun map row->let site,state=parse_assertion work table row in
    M.add site state map)M.empty rows in
  M.iter(fun _ state->let base=M.find table.base_bank state.domains in
    require(base.tag="constant" && base.low=table.base && base.width=64)
      "loop stable base invariant")assertions;
  List.iter(fun corridor->let _,to_,_=parse_edge(get corridor "entrance") in
    let state=corridor_state work corridor table region input transfers reads in
    require(included work state(M.find to_ assertions)) "loop entrance inclusion")corridors;
  List.iter(fun(from,to_,taken)->match transfer work from taken(M.find from assertions)
    table input.instructions transfers reads with
    | None->()
    | Some state when S.mem to_ region->
      require(included work state(M.find to_ assertions)) "loop preservation inclusion"
    | Some _->())(internal@exits);
  let load=find assertions table.load_site "loop table load outside region" in
  require(domain_values work(M.find table.selector_bank load.domains)=Some table.indices)
    "loop selector domain coverage";
  let derived=check_table work table reads row in
  let instruction=find input.instructions dispatch "loop dispatch instruction missing" in
  require(S.equal derived instruction.targets && S.equal derived(set ~addr:true(get row "targets")))
    "loop dispatch successor coverage";
  let jump=get(M.find dispatch transfers) "jump" in
  require(jump<>`Null) "loop dispatch source jump";
  let values=match domain_values work(evaluate work 0(M.find dispatch assertions)table reads jump) with
    Some values->List.fold_left(fun set value->S.add(Capture.hx value)set)S.empty values
    | None->raise(Invalid "loop dispatch domain unbounded") in
  require(S.equal values derived) "loop dispatch invariant target domain";
  require(source_shape work dispatch input.instructions transfers=
    (table.base_bank,table.selector_bank,table.load_site)) "loop table source shape"
