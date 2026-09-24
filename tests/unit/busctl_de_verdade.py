"""Como o `busctl` de verdade imprime uma string — para os dublês dele.

Conferência da INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026). Os dublês do
`busctl` desta casa devolviam o texto CRU (`printf 's "%s"'`), e o `busctl`
do systemd escapa em C todo byte fora do ASCII (o `cescape` do
`format_cmdline`): «Nintendo Sofá» sai `s "Nintendo Sof\\303\\241"`. Medido
num barramento privado (`dbus-run-session`) com o systemd 255 dela. Só o
`--json=short` entrega o texto como ele é: `{"type":"s","data":"Nintendo Sofá"}`.

Com o dublê cru, duas réguas que puseram acento DE PROPÓSITO nos nomes dela
passavam sobre dois defeitos vivos: o `bt_active_mode.sh` reescrevia um nome
com acento a cada tique do watchdog (comparava o escapado com o de verdade) e
costurava «Nintendo Sof\\303\\241» no adaptador; e o `uninstall.sh` não
devolvia o lugar com acento e gravava de volta o texto escapado.

**Este módulo não é um arquivo de teste** — é o impressor que os dublês usam.
Escrevê-lo em cada arquivo deixaria uma verdade por dublê sobre o mesmo
`busctl`.
"""

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
    """Grava `pasta/impressao_do_busctl.py` para os dublês em shell.

    Uso no dublê: `python3 <impressor> "<texto>" "$@"` — o `--json=short`
    em qualquer posição dos argumentos troca a forma, como no real.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / "impressao_do_busctl.py"
    alvo.write_text(
        "import json\nimport sys\n\n\n"
        + inspect.getsource(impressao_do_busctl)
        + "\n\nprint(impressao_do_busctl(sys.argv[1], '--json=short' in sys.argv[2:]))\n",
        encoding="utf-8",
    )
    return alvo
