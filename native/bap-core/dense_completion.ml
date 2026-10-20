(* Independent completion-only representation. No Rust results are inputs.
   Membership words use 62 bits to stay in the pinned OCaml immediate integer. *)
open Recovery
module Ready=Set.Make(struct type t=int * int let compare=compare end)
type t={universe:D.elt array;addresses:string array;indices:(string,int) Hashtbl.t;
  successors:int list array;rank:int array;values:int array array;
  outgoing:int array array;kills:(int*int) list array;mutable ready:Ready.t}
let bits_per_word=62
let full=(1 lsl 62)-1
let word_count n=(n+61)/62
let set row n=row.(n/62)<-row.(n/62) lor (1 lsl (n mod 62))
let union dest source =
  let changed=ref false in
  for n=0 to Array.length dest-1 do
    let value=dest.(n) lor source.(n) in
    if value<>dest.(n) then (changed:=true;dest.(n)<-value)
  done; !changed
let initialize (i:Recovery.input) (s:Recovery.state) =
  require(s.phase="dataflow" && s.compact_reaching=None) "dense completion phase";
  let addresses=Array.of_list(S.elements s.decoded) in
  let all=S.fold(fun a defs ->
    let defs=D.union defs (generated a "instruction" (M.find a i.instructions).may) in
    let defs=if S.mem a i.roots then D.union defs (generated a "entry" i.locations) else defs in
    require(D.cardinal defs<=1000000) "completion definition universe budget";defs) s.decoded D.empty in
  let universe=Array.of_list(D.elements all) in
  require(Array.fold_left(fun n (loc,_,_)->n+String.length loc)0 universe<=67108864)
    "completion definition bytes budget";
  let count=Array.length universe and nodes=Array.length addresses in
  require (nodes=0 || (count+63)/64<=33554432/nodes) "completion bitmap budget";
  let ids=Hashtbl.create count and indices=Hashtbl.create nodes in
  Array.iteri(fun n d->Hashtbl.add ids d n)universe;
  Array.iteri(fun n a->Hashtbl.add indices a n)addresses;
  let successors=Array.make nodes [] in
  E.iter(fun(src,dst,kind)->if kind<>"call" then
    match Hashtbl.find_opt indices src,Hashtbl.find_opt indices dst with
    |Some a,Some b->successors.(a)<-b::successors.(a)|_->())s.edges;
  Array.iteri(fun n row->successors.(n)<-List.sort_uniq compare row)successors;
  let seen=Array.make nodes false and post=ref [] in
  for root=0 to nodes-1 do
    let stack=ref [root,false] in
    while !stack<>[] do match !stack with
      |(a,exit)::rest->stack:=rest;
        if exit then post:=a:: !post
        else if not seen.(a) then begin seen.(a)<-true;
          stack:=(a,true):: !stack;
          List.iter(fun b->if not seen.(b) then stack:=(b,false):: !stack)(List.rev successors.(a))
        end
      |[]->()
    done
  done;
  let rank=Array.make nodes 0 in List.iteri(fun n a->rank.(a)<-n)!post;
  let words=word_count count in
  let values=Array.init nodes(fun _->Array.make words 0) in
  let outgoing=Array.init nodes(fun _->Array.make words 0) in
  let kills=Array.make nodes [] in
  let locations=Hashtbl.create(S.cardinal i.locations) in
  Array.iteri(fun n (loc,_,_)->let first,_=Option.value ~default:(n,n+1)(Hashtbl.find_opt locations loc) in Hashtbl.replace locations loc(first,n+1))universe;
  Array.iteri(fun a va->
    D.iter(fun d->set values.(a)(Hashtbl.find ids d))(M.find va s.reaching);
    Array.blit values.(a) 0 outgoing.(a) 0 words;
    S.iter(fun loc->match Hashtbl.find_opt locations loc with None->()|Some(first,last)->
      for word=first/62 to (last-1)/62 do
        let low=max 0 (first-word*62) and high=min 62 (last-word*62) in
        let mask=(full lsl low) land (full lsr (62-high)) in
        kills.(a)<-(word,mask)::kills.(a);outgoing.(a).(word)<-outgoing.(a).(word) land (lnot mask)
      done)(M.find va i.instructions).must;
    S.iter(fun loc->set outgoing.(a)(Hashtbl.find ids(loc,va,"instruction")))(M.find va i.instructions).may)addresses;
  Array.iteri(fun a va->
    if S.mem va i.roots then S.iter(fun loc->set values.(a)(Hashtbl.find ids(loc,va,"entry")))i.locations;
    List.iter(fun b->ignore(union values.(b) outgoing.(a)))successors.(a))addresses;
  let ready=ref Ready.empty in
  Array.iteri(fun a va->
    let previous=Array.make words 0 in D.iter(fun d->set previous(Hashtbl.find ids d))(M.find va s.reaching);
    if previous<>values.(a) then ready:=Ready.add(rank.(a),a)!ready)addresses;
  {universe;addresses;indices;successors;rank;values;outgoing;kills;ready= !ready}
let step work = match Ready.min_elt_opt work.ready with
  | None -> false
  | Some(priority,a)->
    work.ready<-Ready.remove(priority,a)work.ready;
    let delta=Array.copy work.values.(a) in
    List.iter(fun(word,mask)->delta.(word)<-delta.(word) land(lnot mask))work.kills.(a);
    for n=0 to Array.length delta-1 do
      delta.(n)<-delta.(n) land(lnot work.outgoing.(a).(n));
      work.outgoing.(a).(n)<-work.outgoing.(a).(n) lor delta.(n)
    done;
    List.iter(fun b->if union work.values.(b) delta then work.ready<-Ready.add(work.rank.(b),b)work.ready)work.successors.(a);
    true
let finish work (i:Recovery.input) (s:Recovery.state) =
  require(Ready.is_empty work.ready) "unfinished compact dataflow";
  let words=word_count(Array.length work.universe) in
  let rows=S.fold(fun a rows->M.add a (match Hashtbl.find_opt work.indices a with
    |Some n->work.values.(n)|None->Array.make words 0)rows)i.addresses M.empty in
  {s with phase="slice";slice=S.inter i.seeds s.decoded;
    compact_reaching=Some(work.universe,rows);reaching=M.empty;
    flow_out=M.empty;flow_in=M.empty;flow_next=M.empty;entry_defs=M.empty;
    flow_values=M.empty;flow_delta=M.empty;flow_enabled=S.empty}

let observe (i:Recovery.input) (s:Recovery.state) =
  let universe,rows=match s.compact_reaching with Some x->x|None->
    let work=initialize i {s with phase="dataflow"} in
    require(Ready.is_empty work.ready) "completed legacy state is not a fixed point";
    match (finish work i s).compact_reaching with Some x->x|None->assert false in
  let digits="0123456789abcdef" in
  (* Four low-to-high membership bits per hex character; the final nibble is
     zero-padded. Exact array equality decides interning after a full hash. *)
  let pool=Hashtbl.create(S.cardinal i.addresses) and sets=ref [] and count=ref 0 in
  let reference words=
    let hash=Array.fold_left(fun h n->((h*65599)lxor n)land max_int)0 words in
    let bucket=Option.value ~default:[](Hashtbl.find_opt pool hash) in
    match List.find_opt(fun(previous,_)->previous=words)bucket with
    |Some(_,n)->n
    |None->let n= !count in incr count;Hashtbl.replace pool hash((words,n)::bucket);
      let text=String.init((Array.length universe+3)/4)(fun nibble->
        let value=ref 0 in
        for bit=0 to 3 do let id=nibble*4+bit in
          if id<Array.length universe && words.(id/62)land(1 lsl(id mod 62))<>0 then value:= !value lor(1 lsl bit)
        done;digits.[!value]) in
      sets:=`String text:: !sets;n in
  let reaching=S.elements i.addresses |> List.map(fun a->`Assoc["address",js a;"definitions_ref",`Int(reference(M.find a rows))]) in
  let empty={s with reaching=M.empty;compact_reaching=None} in
  let fields=match Recovery.observe {i with addresses=S.empty} empty with `Assoc x->x|_->assert false in
  `Assoc(List.filter(fun(k,_)->k<>"reaching")fields @[
    "definition_dictionary",`List(Array.to_list universe |> List.map(fun(loc,site,origin)->`Assoc["loc",js loc;"site",js site;"origin",js origin]));
    "definition_bitmaps",`List(List.rev !sets);"reaching",`List reaching])
