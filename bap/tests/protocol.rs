#[cfg(unix)]
mod unix {
    use ariadne_bap::{Config, Session};
    use std::os::unix::fs::PermissionsExt;
    use std::path::PathBuf;
    fn root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .to_path_buf()
    }
    #[test]
    #[ignore = "requires pinned BAP runtime"]
    fn malformed_wrong_version_and_missing_helper_fail_before_a_session_is_admitted() {
        let runtime = root().join("tmp/bap-setup/stable");
        assert!(runtime.is_dir(), "pinned BAP runtime required");
        let folder = root().join("tmp/bap-protocol-tests");
        std::fs::create_dir_all(&folder).unwrap();
        let bodies = [
            "print('{')",
            "print('{\"schema\":\"ariadne.bap-ready/v1\",\"snapshot\":\"wrong\",\"target\":\"linux-amd64\",\"version\":\"wrong\",\"lifter\":\"legacy\"}')",
            "print('{\"schema\":\"x\",\"schema\":\"y\"}')",
        ];
        for (i, body) in bodies.iter().enumerate() {
            let path = folder.join(format!("bad-{i}.py"));
            std::fs::write(
                &path,
                format!("#!/usr/bin/env python3\nimport sys\nsys.stdin.readline()\n{body}\n"),
            )
            .unwrap();
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
            let config = Config::new(path.clone(), runtime.clone());
            assert!(Session::start(&config, "fixture", "linux-amd64").is_err());
            std::fs::remove_file(path).unwrap();
        }
        assert!(
            Session::start(
                &Config::new(folder.join("absent"), runtime),
                "fixture",
                "linux-amd64"
            )
            .is_err()
        );
    }
}
