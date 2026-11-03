"""Assemble chaque vidéo : en-tête commun + scènes + script, avec la durée indiquée."""
import re, sys
from pathlib import Path
D = Path(__file__).parent
head, tail = (D / "_head.html").read_text(), (D / "_tail.html").read_text()
for src in sys.argv[1:]:
    body = (D / src).read_text()
    total = re.search(r"TOTAL=(\d+)", body).group(1)
    (D / src.replace("v_", "out_")).write_text(head + body + tail.replace("__TOTAL__", total))
    print(src, total)
