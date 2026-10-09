#[cfg(unix)]
mod unix {
    use ariadne::bap::{Backend, Config};
    use ariadne::{
        InstructionKind,
        effects::{Catalogue, EffectQuality, PreparationOptions},
        llvm_mc::DecoderTarget,
    };
    use std::{os::unix::fs::PermissionsExt, path::PathBuf};
    #[test]
    #[ignore = "requires pinned runtime and LLVM decoded-fact reference"]
    fn decode_length_control_and_operand_binding_disagreements_stop_without_fallback() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let runtime = std::env::var_os("BAP_RUNTIME_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.join("tmp/bap-setup/stable"));
        let decoder = std::env::var_os("ARIADNE_LLVM_MC")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.join("target/ariadne-llvm-mc"));
        let folder =
            std::env::temp_dir().join(format!("ariadne-bap-disagreement-{}", std::process::id()));
        std::fs::create_dir_all(&folder).unwrap();
        let corpus: serde_json::Value =
            serde_json::from_str(include_str!("fixtures/corpus.json")).unwrap();
        for mode in [
            "length",
            "control",
            "effect",
            "malformed",
            "opaque",
            "hidden-jump",
            "path-budget",
        ] {
            let name = if mode == "control" { "jne" } else { "mov64" };
            let row = corpus["rows"]
                .as_array()
                .unwrap()
                .iter()
                .find(|r| r["name"] == name)
                .unwrap();
            let fixture = folder.join(format!("{mode}.json"));
            std::fs::write(&fixture, serde_json::to_vec(&row["lift"]).unwrap()).unwrap();
            let program = r#"#!/usr/bin/env python3
import sys,json
mode='MODE';value=json.load(open('FIXTURE'))
h=sys.stdin.readline().split();print(json.dumps(dict(schema='ariadne.bap-ready/v1',snapshot=h[3],target=h[2],version='2.5.0-alpha',lifter='legacy')),flush=True)
b=sys.stdin.readline().split();r=sys.stdin.readline().split();value.update(snapshot=h[3],batch=int(b[1]),va=r[0],bytes=r[1])
if mode=='length':value['length']=2;value['bytes']=value['bytes'][:4]
if mode=='control':value['properties']['conditional']=False
if mode=='effect':value['bil'][0]['value']=dict(kind='int',value='0:64u')
if mode=='malformed':value['bil'][0]['value']=dict(kind='int',value='0:32u')
if mode=='opaque':value['bil'][0]['value']=dict(kind='unsupported')
if mode=='hidden-jump':value['bil'].append(dict(kind='jump',target=dict(kind='int',value=str(int(r[0],16)+3)+':64u')))
if mode=='path-budget':
 condition=dict(kind='var',var={'name':'CF','index':0,'virtual':False,'width':1,'type':'imm'})
 value['bil'] += [dict(kind='if',condition=condition,yes=[],no=[]) for _ in range(6)]
print(json.dumps(value),flush=True);print(json.dumps(dict(schema='ariadne.bap-batch/v1',batch=int(b[1]),count=1)),flush=True)
for _ in sys.stdin:pass
"#;
            let helper = folder.join(format!("{mode}.py"));
            std::fs::write(
                &helper,
                program
                    .replace("MODE", mode)
                    .replace("FIXTURE", fixture.to_str().unwrap()),
            )
            .unwrap();
            std::fs::set_permissions(&helper, std::fs::Permissions::from_mode(0o700)).unwrap();
            let mut backend = Backend::new(Config::new(helper, runtime.clone()), &decoder).unwrap();
            let hex = row["prefix"].as_str().unwrap();
            let va = u64::from_str_radix(&row["lift"]["va"].as_str().unwrap()[2..], 16).unwrap();
            let bytes = (0..hex.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap())
                .collect();
            let batch = backend.prepare(
                "fixture",
                &[(va, Some(bytes))].into(),
                &PreparationOptions::default(),
                DecoderTarget::LinuxAmd64,
            );
            if ["malformed", "path-budget"].contains(&mode) {
                assert!(
                    batch.is_err(),
                    "invalid type/resource failure was published"
                );
                let error = batch.err().unwrap();
                assert!(error.to_string().contains(if mode == "malformed" {
                    "width"
                } else {
                    "limit"
                }));
                backend.finish().unwrap();
                continue;
            }
            let batch = batch.unwrap();
            let site = &batch.sites[&va];
            let semantic = site.evidence.semantic.as_ref().unwrap();
            assert_ne!(semantic.status, "projected", "{mode}");
            if mode == "opaque" {
                assert_eq!(semantic.status, "opaque-ordinary");
                assert!(site.decodable);
                assert_eq!(site.instruction.kind, InstructionKind::Ordinary);
                assert_eq!(site.instruction.fall, [va + 3].into());
                assert_eq!(site.instruction.uses, Catalogue.locations());
                assert_eq!(site.instruction.may_defs, Catalogue.locations());
                assert!(site.instruction.must_defs.is_empty());
                assert!(
                    semantic
                        .gaps
                        .iter()
                        .any(|g| g == "unsupported-data-effects")
                );
                assert!(semantic.fallback.is_none());
            } else if mode == "length" {
                assert_eq!(semantic.status, "decode-disagreement");
                assert_eq!(site.instruction.kind, InstructionKind::Stop);
                assert!(!site.decodable);
                assert!(site.instruction.fall.is_empty());
                assert_eq!(site.instruction.uses, Catalogue.locations());
                assert_eq!(site.evidence.quality, EffectQuality::Opaque);
                assert!(site.instruction.must_defs.is_empty());
            } else {
                assert!(semantic.status.ends_with("disagreement"));
                assert!(semantic.gaps.iter().any(|g| g.contains("disagreement")));
                assert_eq!(site.evidence.quality, EffectQuality::Opaque);
                assert!(!site.decodable);
                assert_eq!(site.instruction.uses, Catalogue.locations());
                assert!(semantic.fallback.is_none());
            }
            backend.finish().unwrap();
        }
        std::fs::remove_dir_all(folder).unwrap();
    }
}
