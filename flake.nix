{
  description = "claws: baps (agent hooks) for Claude Code and Codex";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      clawsLib = import ./nix/lib.nix { inherit (nixpkgs) lib; };

      mkClaws =
        pkgs:
        pkgs.python3Packages.buildPythonApplication {
          pname = "claws";
          version = "0.1.0";
          pyproject = true;
          src = self;
          build-system = [ pkgs.python3Packages.setuptools ];
          nativeCheckInputs = [ pkgs.python3Packages.pytestCheckHook ];
          # tests shell out to python -I; keep them hermetic
          preCheck = "export CLAWS_NO_LOG=1 HOME=$TMPDIR";
          meta.mainProgram = "claws-bap";
        };
    in
    {
      lib = clawsLib // {
        project = import ./nix/project.nix {
          inherit (nixpkgs) lib;
          inherit clawsLib mkClaws;
        };
      };

      packages = forAll (pkgs: rec {
        claws = mkClaws pkgs;
        default = claws;
      });

      apps = forAll (pkgs: {
        install = {
          type = "app";
          program = "${self.packages.${pkgs.stdenv.hostPlatform.system}.claws}/bin/claws-install";
        };
        default = self.apps.${pkgs.stdenv.hostPlatform.system}.install;
      });

      homeManagerModules = rec {
        claws =
          { pkgs, ... }@args:
          (import ./nix/hm-module.nix {
            claws = self.packages.${pkgs.stdenv.hostPlatform.system}.claws;
            inherit clawsLib;
          })
            args;
        default = claws;
      };

      checks = forAll (
        pkgs:
        let
          claws = self.packages.${pkgs.stdenv.hostPlatform.system}.claws;
          renderNix =
            harness:
            builtins.toJSON (
              clawsLib.bapSet {
                inherit harness;
                bin = "BIN";
                configFile = "CFG";
              }
            );
        in
        {
          inherit claws;

          lint =
            pkgs.runCommand "claws-lint"
              {
                nativeBuildInputs = [
                  pkgs.nixfmt
                  pkgs.statix
                  pkgs.deadnix
                  pkgs.ruff
                  (pkgs.python3.withPackages (p: [
                    p.mypy
                    p.pytest
                  ]))
                ];
              }
              ''
                cd ${self}
                nixfmt --check flake.nix nix/*.nix src/claws/baps/*/bap.nix
                statix check .
                deadnix --fail .
                export RUFF_CACHE_DIR=$TMPDIR/ruff
                ruff check src tests conftest.py
                ruff format --check src tests conftest.py
                export MYPY_CACHE_DIR=$TMPDIR/mypy
                mypy --strict src tests conftest.py
                touch $out
              '';

          # Each bap.nix and nix/lib.nix must render exactly what Python renders.
          manifest-sync =
            pkgs.runCommand "claws-manifest-sync"
              {
                nativeBuildInputs = [
                  claws
                  pkgs.jq
                ];
              }
              ''
                set -e
                ${pkgs.lib.concatMapStringsSep "\n" (harness: ''
                  echo ${pkgs.lib.escapeShellArg (renderNix harness)} | jq -S . > nix-${harness}.json
                  claws-manifest --render ${harness} --bin BIN --config CFG | jq -S . > py-${harness}.json
                  diff -u py-${harness}.json nix-${harness}.json
                '') clawsLib.harnesses}
                touch $out
              '';

          # lib.project renders, its installer builds, and a bad bap name fails at eval.
          project-eval =
            let
              cfg = self.lib.project {
                inherit pkgs;
                bap.paws = {
                  level = "medium";
                  ask = true;
                };
              };
              bad =
                builtins.tryEval
                  (self.lib.project {
                    inherit pkgs;
                    bap.nope = { };
                  }).configFile;
              claudeCmd = (builtins.head (builtins.head cfg.rendered.claude.PreToolUse).hooks).command;
              ok =
                pkgs.lib.hasInfix "claws-bap paws --harness claude --config /nix/store/" claudeCmd
                &&
                  builtins.attrNames cfg.rendered == [
                    "claude"
                    "codex"
                  ]
                && !bad.success;
            in
            assert ok;
            pkgs.runCommand "claws-project-eval" { nativeBuildInputs = [ pkgs.git ]; } ''
              cd $(mktemp -d)
              git init -q .
              ${cfg.app.program}
              grep -q "claws-bap paws --harness codex" .codex/hooks.json
              grep -q "claws-bap paws --harness claude" .claude/settings.local.json
              grep -q "settings.local.json" .git/info/exclude
              ${cfg.app.program} --quiet | tee out
              [ ! -s out ]
              touch $out
            '';

          # The home-manager module evaluates and wires into stub claude-code/codex options.
          hm-module-eval =
            let
              stub =
                name:
                { lib, ... }:
                {
                  options.programs.${name}.settings = lib.mkOption {
                    type = lib.types.attrsOf lib.types.anything;
                    default = { };
                  };
                };
              result = pkgs.lib.evalModules {
                modules = [
                  { _module.args.pkgs = pkgs; }
                  (stub "claude-code")
                  (stub "codex")
                  (
                    { lib, ... }:
                    {
                      options.assertions = lib.mkOption {
                        type = lib.types.listOf lib.types.anything;
                        default = [ ];
                      };
                    }
                  )
                  self.homeManagerModules.default
                  {
                    programs.claws = {
                      enable = true;
                      bap.paws = {
                        enable = true;
                        level = "high";
                        ask = true;
                      };
                      wire.codex = false;
                    };
                  }
                ];
              };
              c = result.config;
              claudeCmd =
                (builtins.head (builtins.head c.programs.claude-code.settings.hooks.PreToolUse).hooks).command;
              ok =
                pkgs.lib.hasInfix "claws-bap paws --harness claude --config /nix/store/" claudeCmd
                && !(c.programs.codex.settings ? hooks)
                &&
                  builtins.attrNames c.programs.claws.rendered == [
                    "claude"
                    "codex"
                  ]
                && pkgs.lib.all (a: a.assertion) c.assertions
                &&
                  builtins.fromJSON (builtins.readFile c.programs.claws.configFile) == {
                    baps.paws = {
                      level = "high";
                      ask = true;
                    };
                  };
            in
            assert ok;
            pkgs.runCommand "claws-hm-module-eval" { } "touch $out";
        }
      );

      devShells = forAll (
        pkgs:
        let
          own = self.lib.project {
            inherit pkgs;
            bap.paws = { };
          };
        in
        {
          default = pkgs.mkShell {
            packages = [
              (pkgs.python3.withPackages (p: [
                p.pytest
                p.ruff
                p.mypy
              ]))
              pkgs.nixfmt
              pkgs.statix
              pkgs.deadnix
              pkgs.jq
            ];
            shellHook = ''
              export PYTHONPATH=$PWD/src
              ${own.shellHook}
            '';
          };
        }
      );

      formatter = forAll (pkgs: pkgs.nixfmt);
    };
}
