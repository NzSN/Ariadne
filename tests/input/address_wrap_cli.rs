//! Twelve frozen W4 CLI controls; native/process prerequisites stay explicit.
use ariadne::investigation::AddressWrapAssessment;
use ariadne::reports::{decode_address_wrap, sha256};
use serde_json::{Value, json};
use std::collections::BTreeSet;
use std::fs::{self, File};
#[cfg(target_os = "linux")]
use std::os::unix::fs::MetadataExt;
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

const SITE: &str = "0x0000000000401000";
const CONTROLS: [&str; 12] = [
    "with-zero-address",
    "with-zero-base-offset",
    "with-explanation",
    "with-stateflow",
    "out-of-query-site",
    "invalid-access-index",
    "site-remains-seed-not-root",
    "default-native-ownership",
    "explicit-rust-rollback",
    "transactional-render-failure",
    "transactional-native-failure",
    "unknown-assessment-render-order",
];

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}
fn decoder() -> PathBuf {
    std::env::var_os("ARIADNE_LLVM_MC")
        .map(PathBuf::from)
        .unwrap_or_else(|| root().join("target/ariadne-llvm-mc"))
}
fn core() -> PathBuf {
    std::env::var_os("ARIADNE_BAP_CORE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| root().join("target/qualification-native"))
}
fn read(path: &Path) -> Value {
    serde_json::from_slice(&fs::read(path).unwrap()).unwrap()
}
fn write(path: &Path, value: &Value) {
    fs::write(
        path,
        format!("{}\n", serde_json::to_string_pretty(value).unwrap()),
    )
    .unwrap();
}
fn artifact(path: &Path) -> Value {
    json!({"path":path,"bytes":fs::metadata(path).unwrap().len(),"sha256":sha256(&fs::read(path).unwrap())})
}
fn frozen_row(name: &str) -> Value {
    let manifest: Value =
        serde_json::from_slice(include_bytes!("fixtures/i5c/manifest.json")).unwrap();
    manifest["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|row| row["name"] == name)
        .unwrap()
        .clone()
}
fn assert_answer(value: &AddressWrapAssessment, name: &str) {
    let row = frozen_row(name);
    let expected = &row["expected"];
    assert_eq!(
        serde_json::to_value(value.conclusion).unwrap(),
        expected["conclusion"]
    );
    assert_eq!(
        value.input_evidence_count,
        expected["input_evidence_count"].as_u64().unwrap() as usize
    );
    assert_eq!(
        value.evidence.len(),
        expected["retained_evidence_count"].as_u64().unwrap() as usize
    );
    assert_eq!(
        value.claims.len(),
        expected["retained_claims"].as_u64().unwrap() as usize
    );
    if let Some(arithmetic) = &value.arithmetic {
        assert_eq!(
            arithmetic.sum_before_reduction,
            expected["arithmetic"]["sum_before_reduction"]
                .as_str()
                .unwrap()
        );
        assert_eq!(
            serde_json::to_value(arithmetic.wrap_kind).unwrap(),
            expected["arithmetic"]["wrap_kind"]
        );
    } else {
        assert!(expected["arithmetic"].is_null());
    }
    value.validate().unwrap();
}

struct Case {
    name: &'static str,
    directory: PathBuf,
}
impl Case {
    fn new(name: &'static str) -> Self {
        let matrix: Value =
            serde_json::from_slice(include_bytes!("fixtures/i5c/qualification-matrix.json"))
                .unwrap();
        let names: BTreeSet<_> = matrix["cli_cases"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap())
            .collect();
        assert_eq!(names, CONTROLS.into_iter().collect::<BTreeSet<_>>());
        assert!(names.contains(name));
        let base = std::env::var_os("ARIADNE_CLI_TEST_OUTPUT_ROOT")
            .map(PathBuf::from)
            .unwrap_or_else(std::env::temp_dir);
        fs::create_dir_all(&base).unwrap();
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let directory = base.join(format!("i5c-cli-{name}-{}-{nonce}", std::process::id()));
        fs::create_dir(&directory).unwrap();
        println!("I5C_W4_CLI {}", json!({"case":name,"directory":directory}));
        Self { name, directory }
    }
    fn command(&self, dump: &Path, entry: &str, site: &str, access: &str) -> Command {
        let mut command = Command::new(env!("CARGO_BIN_EXE_ariadne-minidump"));
        command
            .arg(dump)
            .args(["--decoder-reference"])
            .arg(decoder())
            .args([
                "--entry",
                entry,
                "--assess-address-wrap",
                site,
                "--memory-access",
                access,
            ]);
        command
    }
    fn upper(&self) -> Command {
        self.command(
            &root().join("tests/input/fixtures/i5c/dumps/mov32mi-upper.dmp"),
            SITE,
            SITE,
            "0",
        )
    }
    fn no_publication(&self, target: &Path) {
        assert!(
            !target.exists(),
            "{}: finished output unexpectedly exists",
            self.name
        );
        let prefix = format!(
            ".{}.ariadne-tmp-",
            target.file_name().unwrap().to_string_lossy()
        );
        assert!(
            !fs::read_dir(target.parent().unwrap())
                .unwrap()
                .any(|row| row
                    .unwrap()
                    .file_name()
                    .to_string_lossy()
                    .starts_with(&prefix)),
            "staging directory leaked"
        );
    }
    fn run(&self, command: Command, label: &str) -> Outcome {
        Running::spawn(self, command, label).finish(Duration::from_secs(90))
    }
}

#[cfg(unix)]
fn signal(target: &str, which: &str) -> bool {
    Command::new("/bin/kill")
        .args([which, "--", target])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .unwrap()
        .success()
}
#[cfg(unix)]
fn group_absent(group: u32) -> bool {
    let output = Command::new("/bin/kill")
        .env("LC_ALL", "C")
        .args(["-0", "--", &format!("-{group}")])
        .output()
        .unwrap();
    if output.status.success() {
        return false;
    }
    assert!(
        String::from_utf8_lossy(&output.stderr).contains("No such process"),
        "group absence was not established: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    true
}

struct Running {
    child: Child,
    group: u32,
    stdout: PathBuf,
    stderr: PathBuf,
    receipt: PathBuf,
    command: Vec<String>,
    started: Instant,
}
struct Outcome {
    status: ExitStatus,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
}
impl Running {
    fn spawn(case: &Case, mut command: Command, label: &str) -> Self {
        #[cfg(unix)]
        command.process_group(0);
        let argv: Vec<String> = std::iter::once(command.get_program())
            .chain(command.get_args())
            .map(|value| value.to_string_lossy().into_owned())
            .collect();
        let stdout = case.directory.join(format!("{label}.stdout"));
        let stderr = case.directory.join(format!("{label}.stderr"));
        let out = File::create_new(&stdout).unwrap();
        let err = File::create_new(&stderr).unwrap();
        let child = command.stdout(out).stderr(err).spawn().unwrap();
        let group = child.id();
        Self {
            child,
            group,
            stdout,
            stderr,
            receipt: case.directory.join(format!("{label}.json")),
            command: argv,
            started: Instant::now(),
        }
    }
    fn cleanup(&mut self) -> bool {
        #[cfg(unix)]
        {
            let target = format!("-{}", self.group);
            if !group_absent(self.group) {
                signal(&target, "-TERM");
            }
            let deadline = Instant::now() + Duration::from_secs(2);
            while !group_absent(self.group) && Instant::now() < deadline {
                let _ = self.child.try_wait();
                std::thread::sleep(Duration::from_millis(5));
            }
            if !group_absent(self.group) {
                signal(&target, "-KILL");
            }
            let _ = self.child.wait();
            let deadline = Instant::now() + Duration::from_secs(2);
            while !group_absent(self.group) && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(5));
            }
            group_absent(self.group)
        }
        #[cfg(not(unix))]
        {
            let _ = self.child.kill();
            let _ = self.child.wait();
            true
        }
    }
    fn finish(mut self, timeout: Duration) -> Outcome {
        let (status, timed_out) = loop {
            if let Some(status) = self.child.try_wait().unwrap() {
                break (status, false);
            }
            if self.started.elapsed() >= timeout {
                self.cleanup();
                break (self.child.wait().unwrap(), true);
            }
            std::thread::sleep(Duration::from_millis(5));
        };
        let clean = self.cleanup();
        write(
            &self.receipt,
            &json!({"command":self.command,"exit":status.code(),"timed_out":timed_out,
            "group":self.group,"group_absent":clean,"seconds":self.started.elapsed().as_secs_f64(),
            "stdout":artifact(&self.stdout),"stderr":artifact(&self.stderr)}),
        );
        assert!(!timed_out, "CLI timed out; no control credit");
        assert!(clean, "CLI process group remains; no control credit");
        Outcome {
            status,
            stdout: fs::read(&self.stdout).unwrap(),
            stderr: fs::read(&self.stderr).unwrap(),
        }
    }
}
impl Drop for Running {
    fn drop(&mut self) {
        self.cleanup();
    }
}
fn expect_failure(outcome: &Outcome, diagnostic: &str) {
    assert_eq!(outcome.status.code(), Some(1));
    assert!(outcome.stdout.is_empty());
    assert!(
        String::from_utf8_lossy(&outcome.stderr).contains(diagnostic),
        "{}",
        String::from_utf8_lossy(&outcome.stderr)
    );
}
#[cfg(target_os = "linux")]
fn native_prerequisites() -> Value {
    assert!(decoder().is_file(), "pinned decoder missing");
    let helper = core().join("ariadne-bap-core");
    let manifest = read(&core().join("manifest.json"));
    assert_eq!(manifest["schema"], "ariadne.bap-core-build/v1");
    assert_eq!(
        manifest["helper_sha256"],
        sha256(&fs::read(&helper).unwrap())
    );
    manifest
}
#[cfg(not(target_os = "linux"))]
fn native_prerequisites() -> Value {
    panic!("native W4 controls require the authorized Linux/WSL environment");
}
fn bundle(case: &Case, label: &str, backend: Option<&str>) -> (Value, AddressWrapAssessment) {
    let target = case.directory.join(label);
    let mut command = case.upper();
    command
        .args(["--bap-core-dir"])
        .arg(core())
        .arg("--output-dir")
        .arg(&target);
    if let Some(backend) = backend {
        command.args(["--analysis-backend", backend]);
    }
    let outcome = case.run(command, label);
    assert!(
        outcome.status.success(),
        "{}",
        String::from_utf8_lossy(&outcome.stderr)
    );
    let expected: BTreeSet<_> = [
        "report.txt",
        "report.json",
        "report.dot",
        "address-wrap-assessment.txt",
        "address-wrap-assessment.json",
        "address-wrap-assessment.dot",
    ]
    .into_iter()
    .map(str::to_owned)
    .collect();
    assert_eq!(
        fs::read_dir(&target)
            .unwrap()
            .map(|row| row.unwrap().file_name().into_string().unwrap())
            .collect::<BTreeSet<_>>(),
        expected
    );
    let report = read(&target.join("report.json"));
    let assessment =
        decode_address_wrap(&fs::read(target.join("address-wrap-assessment.json")).unwrap())
            .unwrap();
    assert_answer(&assessment, "mov32mi-upper");
    let dot = fs::read_to_string(target.join("address-wrap-assessment.dot")).unwrap();
    let retained = dot
        .lines()
        .next()
        .unwrap()
        .strip_prefix("// address_wrap_assessment: ")
        .unwrap();
    assert_eq!(
        decode_address_wrap(retained.as_bytes()).unwrap(),
        assessment
    );
    assert_eq!(
        assessment.identity.query_id,
        report["identity"]["query_id"].as_str().unwrap()
    );
    (report, assessment)
}
fn conflict(name: &'static str, extra: &[&str], diagnostic: &str) {
    let case = Case::new(name);
    let target = case.directory.join("bundle");
    let mut command = case.upper();
    command.arg("--output-dir").arg(&target).args(extra);
    expect_failure(&case.run(command, "reject"), diagnostic);
    case.no_publication(&target);
}
#[test]
fn with_zero_address() {
    conflict(
        "with-zero-address",
        &["--assess-zero-address", SITE],
        "choose one explanation or assessment question",
    );
}
#[test]
fn with_zero_base_offset() {
    conflict(
        "with-zero-base-offset",
        &["--assess-zero-base-offset", SITE],
        "choose one explanation or assessment question",
    );
}
#[test]
fn with_explanation() {
    conflict(
        "with-explanation",
        &["--explain-fault-address", SITE],
        "choose one explanation or assessment question",
    );
}
#[test]
fn with_stateflow() {
    conflict(
        "with-stateflow",
        &["--stateflow-input", "intentionally-not-read.json"],
        "assessment requires",
    );
}

#[test]
#[ignore = "requires pinned BAP/LLVM/native core runtime"]
fn out_of_query_site() {
    use ariadne::bap::core_adapter::NativeAnalyzer;
    use ariadne::bap::core_session::CoreConfig;
    use ariadne::effects::PreparationOptions;
    use ariadne::input::{AnalysisQuery, FileSnapshot, OpenLimits, PrepareLimits};
    use ariadne::investigation::{
        AddressWrapLimits, FaultAddressQuestion, ZeroAddressConclusion, assess_address_wrap,
    };

    let native_manifest = native_prerequisites();
    let case = Case::new("out-of-query-site");
    let dump = root().join("tests/input/fixtures/i5c/dumps/mov32mi-upper.dmp");
    let target = case.directory.join("bundle");
    let mut command = case.command(&dump, SITE, "0x401001", "0");
    command
        .arg("--bap-core-dir")
        .arg(core())
        .arg("--output-dir")
        .arg(&target);
    // A CLI question is a slice seed, so this address belongs to its query even
    // though it is not reachable from the original instruction entry.
    let outcome = case.run(command, "unreached-seed");
    assert!(
        outcome.status.success(),
        "{}",
        String::from_utf8_lossy(&outcome.stderr)
    );
    let report_path = target.join("report.json");
    let assessment_path = target.join("address-wrap-assessment.json");
    let report = read(&report_path);
    let assessment = decode_address_wrap(&fs::read(&assessment_path).unwrap()).unwrap();
    assert_eq!(report["query"]["entries"], json!([SITE]));
    assert_eq!(report["query"]["seeds"], json!(["0x0000000000401001"]));
    assert_eq!(assessment.question.site, 0x401001);
    assert_eq!(assessment.conclusion, ZeroAddressConclusion::Unknown);
    assert!(assessment.gaps.iter().any(|gap| gap == "site-not-reached"));
    assert!(assessment.arithmetic.is_none());

    // Exercise actual outside-query rejection through the public owned binder:
    // freshly prepare and complete a separate native query whose only entry and
    // seed are SITE. No post-seal edit or artificial bound constructor is used.
    let site = 0x401000u64;
    let snapshot = FileSnapshot::open_minidump(&dump, OpenLimits::default()).unwrap();
    let raw_manifest: Value =
        serde_json::from_slice(include_bytes!("fixtures/i5c/raw-corpus.json")).unwrap();
    let frozen = raw_manifest["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|row| row["name"] == "mov32mi-upper")
        .unwrap();
    assert_eq!(
        snapshot.metadata().artifact_sha256,
        frozen["sha256"].as_str().unwrap()
    );
    assert_eq!(
        snapshot.metadata().artifact_bytes as u64,
        frozen["bytes"].as_u64().unwrap()
    );
    let prepared = snapshot
        .prepare(
            &AnalysisQuery {
                entry_points: [site].into(),
                slice_seeds: [site].into(),
            },
            &decoder(),
            &PreparationOptions::default(),
            PrepareLimits::default(),
        )
        .unwrap();
    assert_eq!(
        prepared.prepared.request.entry_points,
        BTreeSet::from([site])
    );
    assert_eq!(
        prepared.prepared.request.slice_seeds,
        BTreeSet::from([site])
    );
    assert!(!prepared.prepared.request.addresses.contains(&(site + 1)));
    let completed = NativeAnalyzer::from_capture(
        &CoreConfig::from_directory(core()),
        "minidump-analysis",
        &prepared,
    )
    .unwrap()
    .complete()
    .unwrap();
    let mut rejections = Vec::new();
    for limits in [
        AddressWrapLimits::default(),
        AddressWrapLimits {
            max_evidence: 0,
            max_claims: 0,
        },
    ] {
        let original = ariadne::input::bind_address_wrap(
            &prepared,
            &completed,
            FaultAddressQuestion {
                site,
                memory_access: 0,
            },
        )
        .unwrap();
        assess_address_wrap(&original, limits).unwrap();
        let mut assessor_invoked = false;
        let result = ariadne::input::bind_address_wrap(
            &prepared,
            &completed,
            FaultAddressQuestion {
                site: site + 1,
                memory_access: 0,
            },
        )
        .and_then(|bound| {
            assessor_invoked = true;
            assess_address_wrap(&bound, limits)
        });
        assert!(
            result.is_err(),
            "outside-query binding must fail before budgets"
        );
        assert!(!assessor_invoked, "outside-query binding reached assessor");
        let error = result.err().unwrap().to_string();
        assert!(error.contains("question site is outside this query"));
        rejections.push(
            json!({"max_evidence":limits.max_evidence,"max_claims":limits.max_claims,
            "result":"Err before budgets","assessor_invoked":false,"error":error,
            "positive_binding_identity":original.identity()}),
        );
    }
    write(
        &case.directory.join("outside-query-binding.json"),
        &json!({"schema":"ariadne.i5c-w4-outside-query-binding/v1","passed":true,
            "frozen_control":"out-of-query-site","native_preparation":true,
            "native_completed_analysis":true,"helper_manifest":native_manifest,
            "dump":artifact(&dump),"artifact_sha256":snapshot.metadata().artifact_sha256,
            "query_identity":prepared.materialization.query_identity,
            "query":{"entries":[SITE],"seeds":[SITE],"question":"0x0000000000401001",
                "question_in_domain":false},"binding_rejections":rejections,
            "cli_unreached_seed":{"exit_code":outcome.status.code(),"conclusion":"unknown",
                "required_gap":"site-not-reached","arithmetic":null,
                "entries":[SITE],"seeds":["0x0000000000401001"],
                "report":artifact(&report_path),"assessment":artifact(&assessment_path)}}),
    );
}
#[test]
#[ignore = "requires pinned BAP/LLVM/native core runtime"]
fn invalid_access_index() {
    native_prerequisites();
    let case = Case::new("invalid-access-index");
    let target = case.directory.join("bundle");
    let mut command = case.command(
        &root().join("tests/input/fixtures/i5c/dumps/mov32mi-upper.dmp"),
        SITE,
        SITE,
        "1",
    );
    command
        .arg("--bap-core-dir")
        .arg(core())
        .arg("--output-dir")
        .arg(&target);
    expect_failure(
        &case.run(command, "reject"),
        "memory-access index does not exist",
    );
    case.no_publication(&target);
}
#[test]
#[ignore = "requires pinned BAP/LLVM/native core runtime"]
fn site_remains_seed_not_root() {
    native_prerequisites();
    let case = Case::new("site-remains-seed-not-root");
    let target = case.directory.join("bundle");
    let mut command = case.command(
        &root().join("tests/input/fixtures/i5b/upstream-call.dmp"),
        SITE,
        "0x401005",
        "0",
    );
    command
        .arg("--bap-core-dir")
        .arg(core())
        .arg("--output-dir")
        .arg(&target);
    let outcome = case.run(command, "seed");
    assert!(
        outcome.status.success(),
        "{}",
        String::from_utf8_lossy(&outcome.stderr)
    );
    let report = read(&target.join("report.json"));
    assert_eq!(report["query"]["entries"], json!([SITE]));
    assert_eq!(report["query"]["seeds"], json!(["0x0000000000401005"]));
}
#[test]
#[ignore = "requires pinned BAP/LLVM/native core runtime"]
fn default_native_ownership() {
    let manifest = native_prerequisites();
    let case = Case::new("default-native-ownership");
    let (report, _) = bundle(&case, "bundle", None);
    let receipt = &report["analysis_backend"];
    assert_eq!(receipt["schema"], "ariadne.analysis-backend/v1");
    assert_eq!(receipt["backend"], "bap");
    assert_eq!(receipt["family"], "recovery");
    assert_eq!(receipt["profile"], "captured-fixed-input/v1");
    assert_eq!(receipt["build"], manifest);
    assert_eq!(receipt["snapshot"], report["identity"]["snapshot_id"]);
    assert_eq!(report["analysis"]["phase"], "done");
    for format in ["text", "json", "dot"] {
        let mut command = case.upper();
        command
            .arg("--bap-core-dir")
            .arg(core())
            .args(["--assessment-only", "--format", format]);
        let outcome = case.run(command, &format!("only-{format}"));
        assert!(outcome.status.success());
        if format == "json" {
            assert_answer(
                &decode_address_wrap(&outcome.stdout).unwrap(),
                "mov32mi-upper",
            );
        }
        if format == "text" {
            assert!(
                String::from_utf8_lossy(&outcome.stdout)
                    .contains("wide sum before reduction: 18446744073709551624")
            );
        }
        if format == "dot" {
            assert!(
                String::from_utf8_lossy(&outcome.stdout)
                    .starts_with("// address_wrap_assessment: ")
            );
        }
    }
}
#[test]
#[ignore = "requires pinned BAP/LLVM/native preparation; explicit Rust completed analysis"]
fn explicit_rust_rollback() {
    native_prerequisites();
    let case = Case::new("explicit-rust-rollback");
    let (report, assessment) = bundle(&case, "bundle", Some("rust"));
    assert!(report.get("analysis_backend").is_none());
    assert!(
        assessment
            .identity
            .semantic_profile
            .contains("bap-bit-provenance-")
    );
    let semantics: Vec<_> = report["preparation"]["sites"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|site| site.get("semantic"))
        .collect();
    assert!(!semantics.is_empty());
    assert!(
        semantics
            .iter()
            .all(|semantic| semantic["backend"] == "bap-x86-legacy")
    );
}
#[test]
#[ignore = "requires Cargo-JSON-selected CLI unit-test executable and its pinned hash"]
fn transactional_render_failure() {
    let case = Case::new("transactional-render-failure");
    let binary = PathBuf::from(
        std::env::var_os("ARIADNE_CLI_UNIT_TEST_BINARY")
            .expect("select the current Cargo compiler-artifact CLI unit executable"),
    );
    let expected = std::env::var("ARIADNE_CLI_UNIT_TEST_SHA256")
        .expect("pin the selected unit executable hash");
    assert_eq!(sha256(&fs::read(&binary).unwrap()), expected);
    let mut command = Command::new(&binary);
    command.args([
        "--exact",
        "address_wrap_cli_tests::transactional_render_failure_uses_real_renderer",
        "--nocapture",
    ]);
    let outcome = case.run(command, "render-unit");
    assert!(
        outcome.status.success(),
        "{}",
        String::from_utf8_lossy(&outcome.stderr)
    );
    let stdout = String::from_utf8(outcome.stdout).unwrap();
    assert!(stdout.lines().any(|line| line
        == "test address_wrap_cli_tests::transactional_render_failure_uses_real_renderer ... ok"));
    assert_eq!(
        stdout
            .lines()
            .filter(|line| line.starts_with("test result: ok. 1 passed; 0 failed; 0 ignored;"))
            .count(),
        1
    );
    write(
        &case.directory.join("unit-artifact.json"),
        &json!({"binary":artifact(&binary),"exact_test":"address_wrap_cli_tests::transactional_render_failure_uses_real_renderer","passed":true}),
    );
}

#[cfg(target_os = "linux")]
#[derive(Clone, Debug, serde::Serialize, PartialEq, Eq)]
struct ProcessIdentity {
    pid: u32,
    parent: u32,
    start_time: u64,
    device: u64,
    inode: u64,
    state: String,
}
#[cfg(target_os = "linux")]
fn process_identity(pid: u32) -> Option<ProcessIdentity> {
    fn stat(pid: u32) -> Option<(u32, u64, String)> {
        let text = fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
        let fields: Vec<_> = text.rsplit_once(") ")?.1.split_whitespace().collect();
        Some((
            fields.get(1)?.parse().ok()?,
            fields.get(19)?.parse().ok()?,
            fields.first()?.to_string(),
        ))
    }
    let first = stat(pid)?;
    let metadata = fs::metadata(format!("/proc/{pid}/exe")).ok()?;
    let second = stat(pid)?;
    if first.0 != second.0 || first.1 != second.1 {
        return None;
    }
    Some(ProcessIdentity {
        pid,
        parent: second.0,
        start_time: second.1,
        device: metadata.dev(),
        inode: metadata.ino(),
        state: second.2,
    })
}
#[cfg(target_os = "linux")]
fn descendants(pid: u32) -> BTreeSet<u32> {
    let mut found = BTreeSet::new();
    let mut todo = vec![pid];
    while let Some(parent) = todo.pop() {
        if let Ok(tasks) = fs::read_dir(format!("/proc/{parent}/task")) {
            for task in tasks.flatten() {
                if let Ok(text) = fs::read_to_string(task.path().join("children")) {
                    for child in text
                        .split_whitespace()
                        .filter_map(|s| s.parse::<u32>().ok())
                    {
                        if child > 1 && child != pid && found.insert(child) {
                            todo.push(child);
                        }
                    }
                }
            }
        }
    }
    found
}
#[test]
#[ignore = "requires actual pinned native helper, Linux /proc and controlled descendant signal injection"]
fn transactional_native_failure() {
    native_prerequisites();
    let case = Case::new("transactional-native-failure");
    inject_actual_native_failure(&case);
}
#[cfg(not(target_os = "linux"))]
fn inject_actual_native_failure(_case: &Case) {
    panic!("Linux process identity observation required");
}
#[cfg(target_os = "linux")]
fn inject_actual_native_failure(case: &Case) {
    let helper = core().join("ariadne-bap-core");
    let metadata = fs::metadata(&helper).unwrap();
    let target = case.directory.join("bundle");
    let mut command = case.upper();
    command
        .arg("--bap-core-dir")
        .arg(core())
        .arg("--output-dir")
        .arg(&target);
    let mut running = Running::spawn(case, command, "native-failure");
    let cli_metadata = fs::metadata(env!("CARGO_BIN_EXE_ariadne-minidump")).unwrap();
    let cli_deadline = Instant::now() + Duration::from_secs(2);
    let cli = loop {
        if let Some(identity) = process_identity(running.child.id()) {
            if identity.device == cli_metadata.dev() && identity.inode == cli_metadata.ino() {
                break identity;
            }
        }
        assert!(
            Instant::now() < cli_deadline,
            "launched CLI executable identity was not observed"
        );
        std::thread::sleep(Duration::from_micros(100));
    };
    let mut witness = json!({"passed":false,"phase":"awaiting-helper","cli":cli,"matching_helper":artifact(&helper)});
    write(
        &case.directory.join("native-fault-observation.json"),
        &witness,
    );
    let deadline = Instant::now() + Duration::from_secs(60);
    let mut observed = None;
    while Instant::now() < deadline {
        assert!(
            running.child.try_wait().unwrap().is_none(),
            "CLI completed before real native helper was observed; no failure-control credit"
        );
        let current = process_identity(cli.pid).expect("CLI disappeared before injection");
        assert_eq!(current.start_time, cli.start_time);
        observed = descendants(cli.pid)
            .into_iter()
            .filter_map(process_identity)
            .find(|child| child.device == metadata.dev() && child.inode == metadata.ino());
        if observed.is_some() {
            break;
        }
        std::thread::sleep(Duration::from_micros(100));
    }
    let observed = observed.expect("real matching descendant helper not observed; no credit");
    assert!(descendants(cli.pid).contains(&observed.pid));
    let before_stop = process_identity(observed.pid).expect("helper disappeared before STOP");
    let active_cli = process_identity(cli.pid).expect("launched CLI disappeared before STOP");
    assert_eq!(active_cli.start_time, cli.start_time);
    assert_eq!(
        (active_cli.device, active_cli.inode),
        (cli.device, cli.inode)
    );
    assert_eq!(before_stop.start_time, observed.start_time);
    assert_eq!(
        (before_stop.device, before_stop.inode),
        (metadata.dev(), metadata.ino())
    );
    witness["observed"] = json!(observed);
    witness["before_stop"] = json!(before_stop);
    witness["phase"] = json!("before-stop");
    write(
        &case.directory.join("native-fault-observation.json"),
        &witness,
    );
    let stop_sent = signal(&observed.pid.to_string(), "-STOP");
    witness["stop_sent"] = json!(stop_sent);
    write(
        &case.directory.join("native-fault-observation.json"),
        &witness,
    );
    assert!(stop_sent, "SIGSTOP failed; no credit");
    let stop_deadline = Instant::now() + Duration::from_secs(1);
    let stopped = loop {
        let current = process_identity(observed.pid)
            .expect("helper disappeared before stopped state was observed");
        assert_eq!(current.start_time, observed.start_time);
        assert_eq!(
            (current.device, current.inode),
            (metadata.dev(), metadata.ino())
        );
        if current.state == "T" || current.state == "t" {
            break current;
        }
        assert!(
            Instant::now() < stop_deadline,
            "matching helper did not stop; no credit"
        );
        std::thread::sleep(Duration::from_micros(100));
    };
    assert!(descendants(cli.pid).contains(&stopped.pid));
    assert_eq!(
        process_identity(cli.pid).unwrap().start_time,
        cli.start_time
    );
    witness["stopped"] = json!(stopped);
    witness["phase"] = json!("stopped-real-helper");
    write(
        &case.directory.join("native-fault-observation.json"),
        &witness,
    );
    let before_kill =
        process_identity(stopped.pid).expect("stopped helper disappeared before KILL");
    assert_eq!(before_kill.start_time, stopped.start_time);
    assert_eq!(
        (before_kill.device, before_kill.inode),
        (metadata.dev(), metadata.ino())
    );
    assert!(before_kill.state == "T" || before_kill.state == "t");
    assert!(descendants(cli.pid).contains(&before_kill.pid));
    witness["before_kill"] = json!(before_kill);
    let kill_sent = signal(&stopped.pid.to_string(), "-KILL");
    witness["kill_sent"] = json!(kill_sent);
    write(
        &case.directory.join("native-fault-observation.json"),
        &witness,
    );
    assert!(kill_sent, "SIGKILL failed; no credit");
    let outcome = running.finish(Duration::from_secs(90));
    expect_failure(&outcome, "core");
    case.no_publication(&target);
    witness["passed"] = json!(true);
    witness["phase"] = json!("actual-helper-failure-cleaned-no-publication");
    write(
        &case.directory.join("native-fault-observation.json"),
        &witness,
    );
}
#[test]
#[ignore = "requires pinned BAP/LLVM/native core runtime"]
fn unknown_assessment_render_order() {
    native_prerequisites();
    let case = Case::new("unknown-assessment-render-order");
    let mut command = case.command(
        &root().join("tests/input/fixtures/i5c/dumps/mov32mi-underflow.dmp"),
        SITE,
        SITE,
        "0",
    );
    let target = case.directory.join("bundle");
    command
        .arg("--bap-core-dir")
        .arg(core())
        .arg("--output-dir")
        .arg(&target);
    let outcome = case.run(command, "unknown");
    assert!(outcome.status.success());
    let value =
        decode_address_wrap(&fs::read(target.join("address-wrap-assessment.json")).unwrap())
            .unwrap();
    assert_answer(&value, "mov32mi-underflow");
    let text = fs::read_to_string(target.join("address-wrap-assessment.txt")).unwrap();
    let conclusion = text.find("conclusion: Unknown").unwrap();
    let arithmetic = text
        .find("conditional arithmetic under the declared premises:")
        .unwrap();
    for gap in &value.gaps {
        let at = text.find(&format!("gap: {gap}\n")).unwrap();
        assert!(conclusion < at && at < arithmetic);
    }
    for requirement in &value.evidence_requirements {
        let at = text.find(&format!("requires: {requirement}\n")).unwrap();
        assert!(conclusion < at && at < arithmetic);
    }
    assert!(text.contains("wide sum before reduction: -8"));
}
