# Declarative set of baps for a repo flake. Mirrors the home-manager module's
# shape but produces a shellHook and an app instead of touching user config.
#
#   clawsCfg = claws.lib.project {
#     inherit pkgs;
#     harnesses = [ "claude" "codex" ];
#     bap.dangerous-commands = { level = "high"; ask = true; };
#   };
#   devShells.default = pkgs.mkShell { shellHook = clawsCfg.shellHook; };
#   apps.claws = clawsCfg.app;
{
  lib,
  clawsLib,
  mkClaws,
}:
{
  pkgs,
  bap,
  harnesses ? clawsLib.harnesses,
  package ? mkClaws pkgs,
}:
let
  # bap.<name> = { enable = false; ... } switches one off without deleting its options.
  enabled = lib.filterAttrs (_: b: b.enable or true) bap;
  settings = lib.mapAttrs (_: b: builtins.removeAttrs b [ "enable" ]) enabled;
  unknown = lib.filter (n: !(clawsLib.baps ? ${n})) (builtins.attrNames bap);
  badHarness = lib.filter (h: !(builtins.elem h clawsLib.harnesses)) harnesses;
  checked =
    assert lib.assertMsg (unknown == [ ])
      "claws.lib.project: unknown bap(s) ${toString unknown}; known: ${toString (builtins.attrNames clawsLib.baps)}";
    assert lib.assertMsg (badHarness == [ ])
      "claws.lib.project: unknown harness(es) ${toString badHarness}; known: ${toString clawsLib.harnesses}";
    true;

  configFile = (pkgs.formats.json { }).generate "claws.json" {
    inherit harnesses;
    baps = settings;
  };

  installer = pkgs.writeShellApplication {
    name = "claws-install-project";
    runtimeInputs = [ package ];
    text = ''exec claws-install --from ${configFile} "$@"'';
  };

  rendered = lib.genAttrs harnesses (
    harness:
    clawsLib.bapSet {
      inherit harness;
      baps = builtins.attrNames settings;
      bin = "${package}/bin/claws-bap";
      configFile = toString configFile;
    }
  );
in
assert checked;
{
  inherit configFile rendered package;
  shellHook = ''
    if [ -z "''${CLAWS_SKIP_INSTALL:-}" ]; then
      ${lib.getExe installer} --quiet || echo "claws: install failed" >&2
    fi
  '';
  app = {
    type = "app";
    program = lib.getExe installer;
    meta.description = "Sync claws baps into this repo";
  };
}
