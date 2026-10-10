import ast
import collections
import subprocess
import sys


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def check(name, raw, old=b""):
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        return [f"{name}:1:invalid UTF-8: {exc}"]
    errors = []
    try:
        ast.parse(source, filename=name)
    except SyntaxError as exc:
        errors.append(f"{name}:{exc.lineno}:syntax: {exc.msg}")
    try:
        previous = old.decode("utf-8-sig")
    except UnicodeError:
        previous = ""
    delta = collections.Counter(c for c in source if ord(c) > 127) - collections.Counter(
        c for c in previous if ord(c) > 127
    )
    if delta:
        errors.append(
            f"{name}:1:new non-ASCII: "
            + ",".join(f"U+{ord(c):04X}" for c in sorted(delta))
        )
    return errors


def main():
    args = sys.argv[1:]
    if "--all" in args and "--base-ref" in args:
        print("[FAIL] --all and --base-ref are mutually exclusive")
        return 2
    if "--base-ref" in args:
        index = args.index("--base-ref")
        if index + 1 >= len(args) or not args[index + 1].strip():
            print("[FAIL] --base-ref requires a commit SHA or ref")
            return 2
        base = args[index + 1]
        try:
            git("rev-parse", "--verify", base + "^{commit}")
            raw = git("diff", "--name-only", "-z", "--diff-filter=ACMR", base, "HEAD", "--", "*.py")
        except subprocess.CalledProcessError as exc:
            print(f"[FAIL] unable to compare base ref {base}: {exc}")
            return 2
        mode = "base"
    elif "--all" in args:
        raw = git("ls-files", "-z", "--", "*.py")
        mode = "all"
    else:
        raw = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
        mode = "staged"
    names = [name.decode("utf-8", "replace") for name in raw.split(b"\0")
             if name and name.lower().endswith(b".py")]
    errors = []
    for name in names:
        try:
            source = git("show", ("HEAD:" if mode == "base" else ":") + name)
        except subprocess.CalledProcessError:
            errors.append(f"{name}:1:missing {mode} source")
            continue
        if mode == "all":
            try:
                ast.parse(source.decode("utf-8-sig"), filename=name)
            except (SyntaxError, UnicodeError) as exc:
                errors.append(f"{name}:1:{exc}")
        else:
            try:
                old = git("show", (base if mode == "base" else "HEAD") + ":" + name)
            except subprocess.CalledProcessError:
                old = b""
            errors.extend(check(name, source, old))
    for error in errors:
        print("[FAIL]", error)
    print(f"[{'FAIL' if errors else 'PASS'}] mode={mode} files={len(names)} errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
