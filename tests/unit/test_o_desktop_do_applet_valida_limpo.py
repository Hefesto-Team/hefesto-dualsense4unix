"""Todo `.desktop` que esta casa empacota valida SEM SAÍDA — nem erro, nem aviso.

`DESKTOP-CATEGORIA-01` — 19/09/2026.

**A ASSERÇÃO É SOBRE A SAÍDA, NUNCA SOBRE O `rc`, e a diferença tem número.**
Medido nos três valores que passaram por esta mesa:

    Categories=COSMIC;                      rc=1  error + hint
    Categories=X-COSMIC;Utility;Settings;   rc=0  hint: more than one main category
    Categories=X-COSMIC;Settings;HardwareSettings;   rc=0  (vazia)

O do meio é o valor que a própria sprint propunha. Uma régua escrita com
`assert rc == 0` passaria VERDE sobre ele — e o `doctor` fazia exatamente isso
(`>/dev/null 2>&1` e decisão pelo `rc`), que é por que o aviso vivia há meses
dizendo *"emitiu avisos"* sem nunca dizer qual.

*Régua verde sobre defeito vivo* é a assinatura que esta casa persegue. Esta
função existe para não repeti-la.

**E O `Categories` NÃO É O QUE DESCOBRE O APPLET:** quem faz isso é a chave
`X-CosmicApplet`, lida pelo `cosmic-settings`. Trocar a categoria é higiene de
validador, não mudança de comportamento — está escrito no rodapé do próprio
`.desktop` para a próxima pessoa não "corrigir de volta".
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
VALIDADOR = shutil.which("desktop-file-validate")

#: Os `.desktop` que esta casa EMPACOTA. `packaging/` é a pasta de quem monta o
#: pacote; o que o `install.sh` escreve em `~/.local/share` é gerado, e valida
#: sozinho (medido em 19/09: `rc=0`, saída vazia).
ALVOS = sorted(RAIZ.glob("packaging/**/*.desktop"))

pytestmark = pytest.mark.skipif(
    VALIDADOR is None,
    reason="sem `desktop-file-validate` — a régua não tem motor")


def test_ha_desktop_para_medir() -> None:
    """Conjunto vazio não é verde — é a régua medindo o nada.

    Se `packaging/` mudar de nome, esta função reprova antes de as outras
    passarem sobre zero arquivos.
    """
    assert ALVOS, (
        "nenhum `.desktop` em `packaging/**` — ou a pasta mudou de nome, ou "
        "esta régua deixou de medir o que promete")


@pytest.mark.parametrize("alvo", ALVOS, ids=lambda p: p.name)
def test_o_desktop_nao_emite_uma_linha_sequer(alvo: pathlib.Path) -> None:
    """Saída vazia, e só isso passa."""
    # O BINÁRIO VEM DE `shutil.which`, não de entrada livre.
    r = subprocess.run(
        [str(VALIDADOR), str(alvo)],
        capture_output=True, text=True, check=False)
    saida = (r.stdout + r.stderr).strip()
    assert not saida, (
        f"`{alvo.relative_to(RAIZ)}` não valida limpo:\n"
        + "\n".join("    " + linha.replace(str(alvo) + ": ", "")
                    for linha in saida.splitlines())
        + "\n\n  O `rc` foi "
        + str(r.returncode)
        + " — repare que um `hint` sai com `rc=0`. Se o achado for aceitável, "
        "a saída continua tendo de ser vazia: cure o arquivo, não a régua.")
