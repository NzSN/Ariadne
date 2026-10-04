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
