"""Met a jour les fichiers de langue a partir du code.

Cherche tous les _("...") et N_("...") de fm_speedtool/*.py, puis :
- ecrit fm_speedtool/lang/template.json (toutes les chaines, traductions vides) ;
- ajoute les chaines manquantes (vides) a chaque fm_speedtool/lang/<code>.json,
  sans toucher aux traductions existantes, et retire celles qui ne servent plus.

python tools/make_lang.py
"""

import ast
import glob
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "fm_speedtool")
LANG = os.path.join(SRC, "lang")


def extract():
    keys = []
    for path in sorted(glob.glob(os.path.join(SRC, "*.py"))):
        if os.path.basename(path) == "i18n.py":
            continue
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("_", "N_") and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                keys.append((node.lineno, path, node.args[0].value))
    seen, out = set(), []
    for _line, _path, k in sorted(keys, key=lambda t: (t[1], t[0])):
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def write(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main():
    keys = extract()
    os.makedirs(LANG, exist_ok=True)
    write(os.path.join(LANG, "template.json"),
          {"language": "Name of the language (e.g. Deutsch)", "author": "", "strings": {k: "" for k in keys}})
    for path in glob.glob(os.path.join(LANG, "*.json")):
        if os.path.basename(path) == "template.json":
            continue
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
        old = data.get("strings", {})
        data["strings"] = {k: old.get(k, "") for k in keys}
        missing = [k for k in keys if not old.get(k)]
        write(path, data)
        print(f"{os.path.basename(path)} : {len(keys) - len(missing)}/{len(keys)} traduites")
        for k in missing:
            print("   manque :", k)
    print(len(keys), "chaines")


if __name__ == "__main__":
    main()
