{ lib }:
let
  manifest = import ./baps.nix;

  # Mirrors adapters/<harness>.py `matchers`.
  matchers = {
    claude = {
      shell = "Bash";
      edit = "Edit|Write|MultiEdit|NotebookEdit";
    };
    codex = {
      shell = "Bash|exec_command|functions.exec_command|shell|local_shell";
      edit = "apply_patch|Edit|Write|MultiEdit";
    };
  };

  harnesses = builtins.attrNames matchers;

  # Render a set of baps into the {event = [entries]} hooks block a harness wants.
  #   bapSet { harness = "claude"; baps = [ "paws" ]; bin = "/nix/store/..-claws/bin/claws-bap"; configFile = null; }
  bapSet =
    {
      harness,
      baps ? builtins.attrNames manifest,
      bin,
      configFile ? null,
    }:
    let
      entry =
        name:
        let
          bap = manifest.${name};
          command =
            "${bin} ${name} --harness ${harness}"
            + lib.optionalString (configFile != null) " --config ${configFile}";
        in
        {
          inherit (bap) event;
          value =
            lib.optionalAttrs (bap.tools != [ ]) {
              matcher = lib.concatMapStringsSep "|" (t: matchers.${harness}.${t}) bap.tools;
            }
            // {
              hooks = [
                {
                  type = "command";
                  inherit command;
                  inherit (bap) timeout;
                }
              ];
            };
        };
      entries = map entry baps;
    in
    lib.mapAttrs (_: map (e: e.value)) (lib.groupBy (e: e.event) entries);
in
{
  baps = manifest;
  inherit matchers harnesses bapSet;
}
