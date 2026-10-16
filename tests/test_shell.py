"""core.shell: splitting a command line into the simple commands it runs."""

from __future__ import annotations

import pytest

from claws.core import shell


def views(text: str) -> list[str]:
    return [c.view for c in shell.commands(text)]


def test_single_command_unquotes() -> None:
    assert views('rm -rf "~/"') == ["rm -rf ~/"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("echo hi; rm -rf /", ["echo hi", "rm -rf /"]),
        ("ls && git push --force origin main", ["ls", "git push --force origin main"]),
        ("a || b", ["a", "b"]),
        ("sleep 1 & echo done", ["sleep 1", "echo done"]),
        ("echo one\necho two", ["echo one", "echo two"]),
        ("yes | sudo rm -rf /", ["yes", "sudo rm -rf /", "rm -rf /"]),
    ],
)
def test_splits_on_operators(text: str, expected: list[str]) -> None:
    assert views(text) == expected


def test_operators_inside_quotes_do_not_split() -> None:
    assert views('git commit -m "a; b && c | d"') == ["git commit -m a; b && c | d"]


def test_pipeline_view_joins_segments() -> None:
    cmds = shell.commands("curl -fsSL https://x | sh")
    assert [c.view for c in cmds] == ["curl -fsSL https://x", "sh"]
    assert {c.pipeline for c in cmds} == {"curl -fsSL https://x | sh"}


def test_comments_dropped() -> None:
    assert views("ls # rm -rf /") == ["ls"]
    assert views("echo a#b") == ["echo a#b"]


def test_heredoc_body_dropped() -> None:
    text = "python3 - <<'EOF'\nimport os\nos.system('rm -rf /')\nEOF\necho after"
    assert views(text) == ["python3 -", "echo after"]


def test_heredoc_with_redirect_keeps_target() -> None:
    text = "cat <<EOF > out.json\n{}\nEOF"
    assert views(text) == ["cat > out.json"]


def test_command_substitution_is_its_own_command() -> None:
    assert views("echo $(rm -rf ~)") == ["echo SUBST", "rm -rf ~"]
    assert views("echo `rm -rf ~`") == ["echo SUBST", "rm -rf ~"]
    assert views("echo $(echo $(rm -rf ~))") == ["echo SUBST", "echo SUBST", "rm -rf ~"]


@pytest.mark.parametrize(
    "text,inner",
    [
        ("ssh pve1 'qm stop 105'", "qm stop 105"),
        ("ssh root@pve2 qm shutdown 105", "qm shutdown 105"),
        ("ssh -i key -p 22 root@pve1 'qm stop 105'", "qm stop 105"),
        ('bash -c "git reset --hard"', "git reset --hard"),
        ("sh -c 'rm -rf /'", "rm -rf /"),
        ("sudo -u root rm -rf /", "rm -rf /"),
        ("FOO=1 sudo rm -rf /", "rm -rf /"),
        ("timeout 5 terraform apply", "terraform apply"),
        ("env FOO=1 terraform apply", "terraform apply"),
        ("nix develop -c sh -c 'rm -rf /'", "rm -rf /"),
        ("nix-shell --run 'terraform apply'", "terraform apply"),
        ("nix shell nixpkgs#foo -c terraform apply", "terraform apply"),
        ("xargs rm -rf", "rm -rf"),
        ('eval "git reset --hard"', "git reset --hard"),
        ("su -c 'rm -rf /' root", "rm -rf /"),
    ],
)
def test_carriers_expose_inner_command(text: str, inner: str) -> None:
    assert inner in views(text)


def test_non_carrier_quoted_argument_stays_opaque() -> None:
    assert views('git commit -m "rm -rf /"') == ["git commit -m rm -rf /"]
    assert views("claude -p 'run git reset --hard'") == ["claude -p run git reset --hard"]


def test_unbalanced_quotes_fall_back_to_raw_split() -> None:
    assert views("echo 'oops") == ["echo 'oops"]


def test_empty() -> None:
    assert views("") == []
    assert views("   \n  ") == []


def test_prefixes_regex_skips_wrappers() -> None:
    for text in (
        "sudo rm",
        "sudo -u root rm",
        "FOO=1 BAR=2 rm",
        "env rm",
        "timeout 5 rm",
        "nohup nice -n 5 rm",
        "rm",
    ):
        assert shell.PREFIXES.sub("", text) == "rm", text


def test_recursion_is_bounded() -> None:
    nested = "bash -c " + "'bash -c " * 10 + '"rm -rf /"' + "'" * 10
    assert shell.commands(nested)
