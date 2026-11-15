{
  description = "A devShell example";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    crane.url = "github:ipetkov/crane";

    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    flake-utils.url = "github:numtide/flake-utils";
    # TODO: can we do this with a buildRustPackage instead? This pulls in an extra
    # rust toolchain and stuff...
    selfci = {
      url = "git+https://radicle.dpc.pw/z2tDzYbAXxTQEKTGFVwiJPajkbeDU.git";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, rust-overlay, flake-utils, crane, selfci, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        overlays = [ rust-overlay.overlays.default ];
        pkgs = import nixpkgs {
          inherit system overlays;
        };
        craneLib = (crane.mkLib pkgs).overrideToolchain (p: p.rust-bin.stable.latest.default);
        kompari = pkgs.callPackage ./nix/kompari.nix { };
        gungraun-runner = pkgs.callPackage ./nix/gungraun-runner.nix { };

        commonArgs = {
          strictDeps = true;
          src = pkgs.lib.fileset.toSource {
            root = ./.;
            fileset = pkgs.lib.fileset.unions [
              (craneLib.fileset.commonCargoSources ./.)
              (pkgs.lib.fileset.fileFilter (f: f.hasExt "snap") ./.)
              (pkgs.lib.fileset.fileFilter (f: f.hasExt "svg") ./.)
              (pkgs.lib.fileset.fileFilter (f: f.hasExt "png") ./.)
              ./README.md
            ];
          };
        };

        mkArtifacts = extraArgs: craneLib.buildDepsOnly (commonArgs // extraArgs);

        linesweeperArgs = extraArgs: craneLib.buildPackage (
          commonArgs // {
            cargoArtifacts = (mkArtifacts extraArgs);
          } // extraArgs
        );

        linesweeper = linesweeperArgs {};

        clippy = craneLib.cargoClippy (
          commonArgs // {
            cargoArtifacts = mkArtifacts {};
            cargoClippyExtraArgs = "--all-targets -- --deny warnings";
          }
        );
      in
      with pkgs;
      {
        packages.default = linesweeper;

        checks = {
          inherit linesweeper clippy;
          slowAsserts = linesweeperArgs { cargoExtraArgs = "--features slow-asserts"; };
        };

        devShells.default = mkShell {
          packages = [
            cargo-insta
            cargo-flamegraph
            cargo-fuzz
            cargo-nextest
            cargo-outdated
            cargo-show-asm
            gungraun-runner
            kompari
            rust-analyzer
            selfci.packages.${system}.default
            taplo
            typst
            tinymist
            valgrind
          ];

          nativeBuildInputs = [
            # Provide nightly in the dev-shell for fuzzing support
            # TODO: maybe make fuzzing a separate thing
            rust-bin.nightly.latest.default
          ];
        };
      }
    );
}
