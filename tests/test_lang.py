"""Fichiers de langue."""

import glob
import json
import os
import re

LANG = os.path.join(os.path.dirname(__file__), "..", "fm_speedtool", "lang")


def test_lang_files_placeholders():
    """Chaque traduction garde les memes {noms} que le texte source."""
    for path in glob.glob(os.path.join(LANG, "*.json")):
        data = json.load(open(path, encoding="utf-8-sig"))
        for k, v in data["strings"].items():
            if v:
                assert sorted(re.findall(r"{(\w+)}", k)) == sorted(re.findall(r"{(\w+)}", v)), (path, k)
