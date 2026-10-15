# Every directory under src/claws/baps with a bap.nix is a bap. Each bap.nix
# mirrors the BAP declared in that bap's bap.py; the manifest-sync check
# fails if they drift. Directory names use underscores (Python packages must);
# bap names use hyphens, so dangerous_commands/ is the bap "dangerous-commands".
let
  dir = ../src/claws/baps;
  isBap =
    name:
    (builtins.readDir dir).${name} == "directory" && builtins.pathExists (dir + "/${name}/bap.nix");
  dirs = builtins.filter isBap (builtins.attrNames (builtins.readDir dir));
in
builtins.listToAttrs (
  map (d: {
    name = builtins.replaceStrings [ "_" ] [ "-" ] d;
    value = import (dir + "/${d}/bap.nix");
  }) dirs
)
