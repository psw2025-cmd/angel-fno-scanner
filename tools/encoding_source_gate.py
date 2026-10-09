import ast, collections, subprocess, sys
def git(*a): return subprocess.run(["git",*a],check=True,capture_output=True).stdout
def check(name, raw, old=b""):
    try: s=raw.decode("utf-8-sig")
    except UnicodeError as e: return [f"{name}:1:invalid UTF-8: {e}"]
    errors=[]
    try: ast.parse(s,filename=name)
    except SyntaxError as e: errors.append(f"{name}:{e.lineno}:syntax: {e.msg}")
    try: prev=old.decode("utf-8-sig")
    except UnicodeError: prev=""
    delta=collections.Counter(c for c in s if ord(c)>127)-collections.Counter(c for c in prev if ord(c)>127)
    if delta: errors.append(f"{name}:1:new non-ASCII: "+",".join(f"U+{ord(c):04X}" for c in sorted(delta)))
    return errors
def main():
    all_files="--all" in sys.argv
    raw=git("ls-files","-z","--","*.py") if all_files else git("diff","--cached","--name-only","-z","--diff-filter=ACMR")
    names=[x.decode("utf-8","replace") for x in raw.split(b"\0") if x and x.lower().endswith(b".py")]
    errors=[]
    for name in names:
        try: source=git("show",":"+name)
        except subprocess.CalledProcessError: errors.append(f"{name}:1:missing staged source");continue
        if all_files:
            try: ast.parse(source.decode("utf-8-sig"),filename=name)
            except (SyntaxError,UnicodeError) as e: errors.append(f"{name}:1:{e}")
        else:
            try: old=git("show","HEAD:"+name)
            except subprocess.CalledProcessError: old=b""
            errors+=check(name,source,old)
    for e in errors: print("[FAIL]",e)
    print(f"[{'FAIL' if errors else 'PASS'}] files={len(names)} errors={len(errors)}")
    return 1 if errors else 0
if __name__=="__main__": sys.exit(main())
