"""TELA-DELA-02 — nenhum instrumento de `scripts/` abre janela na tela dela.

O PAR do TELA-DELA-01. Aquele curou a SUÍTE; este cura a outra metade, que é a
que os agentes disparam à mão: **os scripts de `scripts/` que constroem
`Gtk.Window` de verdade**, um por execução, na sessão gráfica viva.

Ela pediu duas vezes em 04/09/2026: *"segue tudo abrindo na Meow ao invés da
OS"*. E a regra desta casa *"SE VOCÊ MEXEU NA TELA, VOCÊ ABRE A TELA E CLICA"*
garante que TODA onda de interface vai rodar esses instrumentos — sem guarda,
toda onda custa a tela dela.

A guarda é `hefesto_dualsense4unix.utils.tela_de_mentira`, chamada no topo de
cada instrumento. Ela redireciona (não recusa) de propósito: recusar deixaria
os instrumentos inúteis até alguém acrescentar bandeira em cada um — e "alguém
lembrar" é exatamente o que falhou.

ESTA RÉGUA É DE COBERTURA, e é o formato certo aqui: o defeito não era um
instrumento errado, era um instrumento ESQUECIDO. Um script novo que abra
janela e não chame a guarda reprova aqui no dia em que nascer.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "scripts"

#: O que caracteriza "este script abre uma janela de verdade".
#: A CHAMADA no nível do módulo. Import não basta — ver a mordida abaixo.
_CHAMA_A_GUARDA = re.compile(r"^garantir_tela_de_mentira\(", re.M)

#: Menção em prosa (docstring/comentário) não abre janela nenhuma. A régua tem
#: de LER o código, não o texto — é a família de defeito que esta casa já pagou
#: onze vezes em 26/08/2026, quando réguas digitavam o que deviam ler.
def _abre_janela_no_codigo(caminho: Path) -> bool:
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return False
    for no in ast.walk(arvore):
        if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant):
            continue  # docstring solta
        if isinstance(no, ast.Attribute):
            alvo = f"{getattr(no.value, 'id', '')}.{no.attr}"
            if alvo in {"Gtk.Window", "Gtk.main", "WebKit2.WebView"}:
                return True
    return False


def _instrumentos_que_abrem_janela() -> list[Path]:
    achados = []
    for p in sorted(SCRIPTS.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        if _abre_janela_no_codigo(p):
            achados.append(p)
    return achados


def test_a_regua_acha_instrumentos_para_medir() -> None:
    """Régua que não acha nada dá verde sobre o vazio."""
    achados = _instrumentos_que_abrem_janela()
    assert len(achados) >= 15, (
        f"só {len(achados)} instrumentos casaram — a busca quebrou, e uma "
        "régua que não acha ninguém passa sempre."
    )


def test_todo_instrumento_que_abre_janela_chama_a_guarda() -> None:
    """A METADE QUE IMPORTA — e ela cobre o script que ainda não existe."""
    # A CHAMADA, não o import. A primeira versão desta régua aceitava o
    # `from ... import garantir_tela_de_mentira` sozinho — e a mordida provou
    # na hora: arranquei a chamada de um instrumento e ela passou verde. Um
    # import sem chamada não desvia janela nenhuma.
    sem_guarda = [
        p.relative_to(RAIZ)
        for p in _instrumentos_que_abrem_janela()
        if not _CHAMA_A_GUARDA.search(p.read_text(encoding="utf-8"))
    ]
    assert not sem_guarda, (
        "estes instrumentos abrem `Gtk.Window` e não chamam a guarda — a "
        "janela deles nasce na tela dela:\n  "
        + "\n  ".join(str(p) for p in sem_guarda)
        + "\n\nPonha no topo, antes do `import gi`:\n"
        "    from hefesto_dualsense4unix.utils.tela_de_mentira import (\n"
        "        garantir_tela_de_mentira,\n    )\n"
        "    garantir_tela_de_mentira()"
    )


def test_a_guarda_desvia_e_se_anuncia() -> None:
    """Ela age, e DIZ que agiu — um 1x1 inexplicado vira diagnóstico errado."""
    from hefesto_dualsense4unix.utils import tela_de_mentira as tm

    fonte = Path(tm.__file__ or "").read_text(encoding="utf-8")
    assert "HEFESTO_NA_TELA" in fonte, "sem escape declarado, alguém força na marra"
    assert "file=sys.stderr" in fonte, "o desvio tem de se anunciar"
    assert "pkill" not in fonte, "matar por padrão é proibido nesta casa"
    assert "proc.terminate()" in fonte and "proc.kill()" in fonte


def test_a_guarda_e_idempotente_e_nao_mexe_em_sessao_ja_headless() -> None:
    """Chamar duas vezes não sobe duas telas; sem sessão viva, não faz nada."""
    from hefesto_dualsense4unix.utils import tela_de_mentira as tm

    antes_display = os.environ.get("DISPLAY")
    primeira = tm.garantir_tela_de_mentira(anunciar=False)
    segunda = tm.garantir_tela_de_mentira(anunciar=False)
    assert primeira == segunda
    # A suíte já corre sob a tela do TELA-DELA-01: a guarda não a troca.
    assert os.environ.get("DISPLAY") == antes_display
