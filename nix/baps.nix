# Every directory under src/claws/baps with a bap.nix is a bap. Each bap.nix
# mirrors the BAP declared in that bap's bap.py; the manifest-sync check
# fails if they drift.
let
  dir = ../src/claws/baps;
  isBap =
    name:
    (builtins.readDir dir).${name} == "directory" && builtins.pathExists (dir + "/${name}/bap.nix");
  names = builtins.filter isBap (builtins.attrNames (builtins.readDir dir));
in
builtins.listToAttrs (
  map (name: {
    inherit name;
    value = import (dir + "/${name}/bap.nix");
  }) names
)
