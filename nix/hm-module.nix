# home-manager module. Usage:
#
#   imports = [ inputs.claws.homeManagerModules.default ];
#   programs.claws = {
#     enable = true;
#     harnesses = [ "claude" "codex" ];
#     bap.paws = { enable = true; level = "high"; ask = true; };
#   };
#
# Bap options other than `enable` are passed through to the bap as its
# config. `programs.claws.rendered.<harness>` holds the hooks block for each
# harness; by default it is wired into programs.claude-code.settings.hooks and
# programs.codex.settings.hooks when those options exist. Set
# programs.claws.wire.<harness> = false to wire it yourself.
{ claws, clawsLib }:
{
  config,
  lib,
  pkgs,
  options,
  ...
}:
let
  cfg = config.programs.claws;
  json = pkgs.formats.json { };

  bapModule =
    { name, ... }:
    {
      freeformType = json.type;
      options.enable = lib.mkEnableOption "the ${name} bap";
    };

  enabled = lib.filterAttrs (_: b: b.enable) cfg.bap;
  bapNames = builtins.attrNames enabled;
  settings = lib.mapAttrs (_: h: builtins.removeAttrs h [ "enable" ]) enabled;
  configFile = json.generate "claws.json" { baps = settings; };

  rendered = lib.genAttrs cfg.harnesses (
    harness:
    clawsLib.bapSet {
      inherit harness;
      baps = bapNames;
      bin = "${cfg.package}/bin/claws-bap";
      configFile = toString configFile;
    }
  );

  wired = harness: cfg.enable && cfg.wire.${harness} && builtins.elem harness cfg.harnesses;
in
{
  options.programs.claws = {
    enable = lib.mkEnableOption "claws baps (agent hooks)";
    package = lib.mkOption {
      type = lib.types.package;
      default = claws;
      description = "The claws package providing claws-bap.";
    };
    harnesses = lib.mkOption {
      type = lib.types.listOf (lib.types.enum clawsLib.harnesses);
      default = clawsLib.harnesses;
      description = "Which harnesses to render hook config for.";
    };
    bap = lib.mkOption {
      type = lib.types.attrsOf (lib.types.submodule bapModule);
      default = { };
      description = "Baps to enable, with their options.";
    };
    wire = lib.genAttrs clawsLib.harnesses (
      harness:
      lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Set programs.${
          if harness == "claude" then "claude-code" else harness
        }.settings.hooks from the rendered block.";
      }
    );
    rendered = lib.mkOption {
      type = lib.types.attrsOf json.type;
      readOnly = true;
      description = "Rendered hook config per harness.";
    };
    configFile = lib.mkOption {
      type = lib.types.path;
      readOnly = true;
      description = "The generated claws.json passed to every bap.";
    };
  };

  config = lib.mkMerge [
    {
      programs.claws.rendered = rendered;
      programs.claws.configFile = configFile;
      assertions = [
        {
          assertion = !cfg.enable || lib.all (n: clawsLib.baps ? ${n}) bapNames;
          message = "programs.claws.bap: unknown bap(s) ${
            toString (lib.filter (n: !(clawsLib.baps ? ${n})) bapNames)
          }; known: ${toString (builtins.attrNames clawsLib.baps)}";
        }
      ];
    }
    (lib.optionalAttrs (options.programs ? claude-code) {
      programs.claude-code.settings.hooks = lib.mkIf (wired "claude") rendered.claude;
    })
    (lib.optionalAttrs (options.programs ? codex) {
      programs.codex.settings.hooks = lib.mkIf (wired "codex") rendered.codex;
    })
  ];
}
