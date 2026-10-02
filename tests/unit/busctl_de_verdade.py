"""Como o `busctl` de verdade imprime uma string — para os dublês dele."""

from __future__ import annotations

import inspect
import json
from pathlib import Path


def impressao_do_busctl(texto: str, json_curto: bool) -> str:
    """A linha que o `busctl get-property` imprime para uma propriedade `s`."""
    if json_curto:
        return json.dumps({"type": "s", "data": texto}, ensure_ascii=False, separators=(",", ":"))
    especiais = {7: "a", 8: "b", 12: "f", 10: "n", 13: "r", 9: "t", 11: "v"}
    especiais.update({92: "\\", 34: '"', 39: "'"})
    saida = []
    for byte in texto.encode("utf-8"):
        if byte in especiais:
            saida.append("\\" + especiais[byte])
        elif byte < 32 or byte >= 127:
            saida.append(f"\\{byte:03o}")
        else:
            saida.append(chr(byte))
    return 's "' + "".join(saida) + '"'


def escrever_impressor(pasta: Path) -> Path:
    """Grava `pasta/impressao_do_busctl.py` para os dublês em shell."""
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / "impressao_do_busctl.py"
    alvo.write_text(
        "import json\nimport sys\n\n\n"
        + inspect.getsource(impressao_do_busctl)
        + "\n\nprint(impressao_do_busctl(sys.argv[1], '--json=short' in sys.argv[2:]))\n",
        encoding="utf-8",
    )
    return alvo
