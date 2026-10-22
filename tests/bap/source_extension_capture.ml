(* Direct control over the actual native target-profile dispatcher. This checks
   the reason separately because rejected non-guarded initialization closes the
   production transport without a structured error envelope. *)
let request projection schema = `Assoc [
    "capture", `Assoc ["sites", `List [`Assoc ["projection", `String projection]]];
    "target_resolution", `Assoc ["schema", `String schema]]

let reason projection schema =
  try ignore (Capture.admit_resolved (request projection schema) "snapshot");
    failwith "unexpected target admission"
  with Recovery.Invalid message -> message

let () =
  List.iter (fun schema ->
      assert (reason "bap-bit-provenance-v9" schema =
              "source flag extension does not admit target resolution");
      assert (reason "bap-bit-provenance-v8" schema <>
              "source flag extension does not admit target resolution"))
    ["ariadne.indirect-target-resolution/v3";
     "ariadne.indirect-target-resolution/v2"];
  print_endline "source-v9 target dispatch refusal: current and legacy controls pass"
