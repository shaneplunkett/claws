# Adding a bap

A bap is one claws hook, a directory under `src/claws/baps/`. Nothing central lists baps; the Python registry and the Nix side both discover directories.

1. Create `src/claws/baps/<name>/` with:
   - `__init__.py` exporting `BAP` from `bap.py`. The directory uses underscores, the bap `name` uses hyphens: `dangerous_commands/` declares `name="dangerous-commands"`.
   - `bap.py` with a `run(event, options) -> Decision` and a module-level `BAP = Bap(name=..., event=..., tools=..., timeout=..., fail_closed=..., defaults=..., run=run)`. The `name` must match the directory.
   - `bap.nix` mirroring `event`, `tools` and `timeout`. The `manifest-sync` check fails if it drifts from `BAP`.
   - `README.md` describing what it does and its options, with a Nix example.
   - `tests/__init__.py` and `tests/test_<name>.py`. Build events with `claws.testing.shell_event` and `edit_event`, and run the real CLI with `claws.testing.run_cli` for at least one end-to-end case.
2. Baps never read a raw payload. They get an `Event` from the adapter and return a `Decision`. If you need a field the `Event` lacks, add it to `Event` and to both adapters, with a fixture-backed test.
3. Options arrive as a `JsonObject` already merged across layers. Validate them with the helpers in `claws.core.jsontypes` and raise `ValueError` on bad input. A `fail_closed` bap turns that into a deny with the message in the reason.
4. Choose `fail_closed` deliberately. A guard should be `True`. Something cosmetic that runs after an edit should be `False`.
5. Run `scripts/check.sh`. That covers ruff, strict mypy, pytest, nixfmt, statix and deadnix, then `nix flake check` for the manifest-sync check and the home-manager module eval.
