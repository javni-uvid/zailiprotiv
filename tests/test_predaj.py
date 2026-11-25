"""tools/predaj.sh, the one way the workflows send their commits, and each workflow's own commit steps run with it: a run
that lost its commit ends red and starts nothing (24 Nov 2026: an hour's reading lost in a green run)."""
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
FLOWS = ROOT / ".github" / "workflows"
TOOL = (ROOT / "tools" / "predaj.sh").read_text(encoding="utf-8")


def _bash():
    """On Windows Git's own: the `bash` first on the PATH may be WSL's."""
    if os.name != "nt":
        return shutil.which("bash")
    git = shutil.which("git")
    found = [p / "bin" / "bash.exe" for p in Path(git).parents if (p / "bin" / "bash.exe").exists()] if git else []
    return str(found[0]) if found else None


BASH = _bash()
pytestmark = pytest.mark.skipif(not BASH, reason="bash and git are needed")
FILES = ["data/14/index.json", "data/14/votes/1.json", "data/15/transcripts/1.json", "data/15/uzivo/d.json",
         "data/15/prepis/d/1.json", "data/15/arhiva.json", "data/15/snimak/d.json", "data/notes_manifest.json", "data/mp_years.json", "data/batches.json",
         "tests/fixtures/a.txt"]


def sh(script, cwd, ok=True, **env):
    r = subprocess.run([BASH, "-e", "-c", script], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PREDAJ_SLEEP": "0", "PREDAJ_TRIES": "2", "GIT_CONFIG_GLOBAL": os.devnull, **env})
    assert not ok or r.returncode == 0, r.stdout + r.stderr
    return r


@pytest.fixture
def repo(tmp_path):
    """A server's repository, a run's shallow checkout of it ("w") and another writer's ("z")."""
    sh("git init -q --bare -b main o.git; git clone -q o.git z; cd z; git checkout -q -b main", tmp_path)
    for f in FILES:
        (tmp_path / "z" / f).parent.mkdir(parents=True, exist_ok=True)
        write(tmp_path / "z", "a", f)
    (tmp_path / "z" / "tools").mkdir()
    (tmp_path / "z" / "tools" / "predaj.sh").write_text(TOOL, encoding="utf-8", newline="\n")
    sh("git config user.name z; git config user.email z@z; git add .; git commit -qm one; git push -q -u origin main",
       tmp_path / "z")
    sh('git clone -q --depth 1 "file://$PWD/o.git" w', tmp_path)
    return tmp_path


def write(folder, text, *files):
    for f in files:
        (folder / f).write_text(text + "\n", encoding="utf-8", newline="\n")


def other(repo, *files, text="other"):
    """Another writer's commit, on the server before the run sends its own."""
    write(repo / "z", text, *files)
    sh("git pull -q --rebase --autostash; git commit -qam other; git push -q", repo / "z")


def send(repo, message="", ok=True):
    return sh(f'sh tools/predaj.sh "{message}"', repo / "w", ok=ok)


def main_log(repo):
    return sh("git log --format=%s main", repo / "o.git").stdout.split("\n")[:-1]


def test_a_commit_is_sent(repo):
    write(repo / "w", "b", FILES[0])
    sh("git add data", repo / "w")
    assert "is on main" in send(repo, "new").stdout and main_log(repo) == ["new", "one"]
    assert send(repo, "nothing staged").stdout == "" and main_log(repo) == ["new", "one"]


def test_beside_another_writer_and_with_changes_left_alone(repo):
    other(repo, FILES[1])
    other(repo, FILES[2])
    write(repo / "w", "b", FILES[0], FILES[3])
    sh(f"git add {FILES[3]}", repo / "w")
    send(repo, "new")
    assert main_log(repo) == ["new", "other", "other", "one"]
    assert (repo / "w" / FILES[0]).read_text() == "b\n"
    assert sh("git status --porcelain", repo / "w").stdout.strip() == "M " + FILES[0]


def test_a_commit_made_before_is_sent_with_no_message(repo):
    write(repo / "w", "b", FILES[0])
    sh("git -c user.name=x -c user.email=x@x commit -qam earlier", repo / "w")
    send(repo)
    assert main_log(repo) == ["earlier", "one"]


def test_a_conflict_is_red_and_leaves_the_branch_whole(repo):
    other(repo, FILES[0])
    write(repo / "w", "b", FILES[0])
    sh("git add data", repo / "w")
    r = send(repo, "new", ok=False)
    assert r.returncode == 1 and FILES[0] in r.stdout and "::error::predaj: NOT on main" in r.stdout
    assert main_log(repo) == ["other", "one"]
    assert sh("git symbolic-ref --short HEAD", repo / "w").stdout.strip() == "main"


def test_a_refused_push_and_no_branch_are_red(repo):
    hook = repo / "o.git" / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n", newline="\n")
    hook.chmod(0o755)
    write(repo / "w", "b", FILES[0])
    sh("git add data", repo / "w")
    assert send(repo, "new", ok=False).returncode == 1 and main_log(repo) == ["one"]
    sh("git checkout -q --detach", repo / "w")
    assert send(repo, ok=False).returncode == 1


def steps():
    out = []
    for f in sorted(FLOWS.glob("*.yml")):
        for part in f.read_text(encoding="utf-8").split("\n      - ")[1:]:
            if "sh tools/predaj.sh" in part:
                run = part.split("run: |\n", 1)[1].split("\n      #")[0]
                out.append((f.name, part.split("\n")[0].removeprefix("name: "), textwrap.dedent(run)))
    return out


def test_every_workflow_that_commits_sends_with_the_tool():
    for f in sorted(FLOWS.glob("*.yml")):
        if f.name == "osnova.yml":  # the copy of the shared rules: one push under `set -e`, red when refused
            continue
        lines = [x for x in f.read_text(encoding="utf-8").split("\n") if not x.strip().startswith("#")]
        for x in lines:
            assert not any(w in x for w in ("git push", "git pull", "git commit")), (f.name, x)
            assert not re.search(r"predaj\.sh[^;]*\|\|", x), (f.name, x)  # its 1 is never swallowed


# The first of votes leaves what it could not send to the run's last step.
LAST = [s for s in steps() if s[1] != "The newest convocation's sittings first"]


@pytest.mark.parametrize("name,step,run", LAST, ids=[f"{n}: {s}" for n, s, _ in LAST])
def test_a_run_that_lost_its_commit_ends_red(repo, name, step, run):
    (repo / "bin").mkdir()
    for tool, body in (("gh", f'echo "$*" >> "{(repo / "gh.log").as_posix()}"'), ("uv", "echo 15")):
        (repo / "bin" / tool).write_text(f"#!/bin/sh\n{body}\n", newline="\n")
        (repo / "bin" / tool).chmod(0o755)
    env = {"GITHUB_ENV": (repo / "env").as_posix(), "GITHUB_OUTPUT": (repo / "out").as_posix(), "CONV": "14",
           "CURRENT": "14", "BESIDE": "15", "ROLLS": "", "CTX_EVENT_NAME": "workflow_dispatch", "IN_SCHEDULED": "true",
           "IN_CONVOCATION": "14", "IN_ALL": "false", "IN_MODEL": "m", "IN_DAY": "d", "GH_TOKEN": "x",
           "GITHUB_REPOSITORY": "x/x"}
    # prepis gives the token in the address: here that address is the test's server
    run = run.replace("https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git",
                      (repo / "o.git").as_posix())
    run = 'export PATH="$(cd ../bin && pwd):$PATH"\n' + run
    write(repo / "w", "b", *FILES)
    other(repo, *FILES)
    r = sh(run, repo / "w", ok=False, **env)
    assert r.returncode == 1 and "NOT on main" in r.stdout, r.stdout + r.stderr
    assert main_log(repo) == ["other", "one"]
    started = (repo / "gh.log").read_text() if (repo / "gh.log").exists() else ""
    assert "pages.yml" not in started and "summaries.yml" not in started
    # and with another's commit that is in nobody's way it ends green, its own on main
    sh("git fetch -q; git reset -q --hard origin/main", repo / "w")
    write(repo / "w", "c", *FILES)
    other(repo, "tools/predaj.sh", text=TOOL + "# later")
    sh(run, repo / "w", **env)
    assert len(main_log(repo)) == 4 and main_log(repo)[1:] == ["other", "other", "one"]
