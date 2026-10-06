"""CONTA-DO-TOPO-01 — o transporte vazio não aparece, e os DOIS escritores concordam.

**Decisão, 17/09/2026**, com um controle só no rádio na mesa:

    "só tem 1 controle conectado ainda assim aparece no canto superior direito
     0 usb  1 bt deveria mostrar só o que tá conectado que é 1 bt nesse caso"

Ela REFINA a decisão de 06/09 e não a contradiz. Aquela escolheu a PALAVRA —
``USB``/``BT`` em vez de ``cabo``/``rádio``, porque *"2 cabo · 0 rádio"* não é
português, e é a única exceção declarada em ``docs/A-LINGUA-DESTA-CASA``. Esta
escolhe o que se OMITE. A palavra continua a mesma, e a régua de 06/09
(``test_a_palavra_do_transporte_tem_um_dono_so``) continua medindo a pergunta
de produto sem uma vírgula de mudança.

**A METADE QUE IMPORTA MAIS É A SEGUNDA.** A frase tem DOIS escritores:

* ``mesa_viva.texto_da_contagem`` — o que o piloto pinta a cada tique;
* ``interface/monta.py`` — o que fica gravado no esqueleto das dez páginas, e
  que é o que ela vê no PRIMEIRO QUADRO, antes do primeiro tique chegar.

Enquanto cada um formatava por conta própria, uma mudança num deles deixava o
outro dizendo outra coisa — e o defeito aparece no lugar mais visível possível:
a fração de segundo em que a janela abre. É a forma desta casa de fabricar
divergência, e o ``monta.py`` já carrega a cicatriz de duas: a contagem
digitada no esqueleto que divergia da fita, e o ``0 USB · 0 BT`` que a tela
mostrava antes de o daemon responder.

Por isso a mordida daqui é dupla: arrancar a cura tem de reprovar no VIVO **e**
no ESQUELETO.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_conta_do_topo_01_o_transporte_vazio_nao_aparece: importa código da janela GTK")

import re

import pytest

from hefesto_dualsense4unix.interface import mesa_viva


@pytest.mark.parametrize(
    ("usb", "bt", "esperado"),
    [
        (0, 1, "1 BT"),
        (0, 2, "2 BT"),
        (0, 4, "4 BT"),
        (1, 0, "1 USB"),
        (2, 0, "2 USB"),
        (1, 1, "1 USB · 1 BT"),
        (2, 1, "2 USB · 1 BT"),
        (2, 2, "2 USB · 2 BT"),
        (0, 0, ""),
    ],
)
def test_o_transporte_vazio_nao_aparece(usb: int, bt: int, esperado: str) -> None:
    """O zero não se escreve. O que está lá, sim."""
    assert mesa_viva.frase_dos_transportes(usb, bt) == esperado


def test_a_mesa_dela_do_dia_da_decisao() -> None:
    """A cena exata da queixa: um controle, no rádio, e mais nada."""
    prefixo, conta = mesa_viva.texto_da_contagem([{"transporte": "bt"}])
    assert prefixo == "● 1 controle: "
    assert conta == "1 BT"
    assert "0 USB" not in conta, (
        "o `0 USB ·` voltou ao cabeçalho — é a queixa dela de 17/09/2026"
    )


def test_a_palavra_nao_mudou() -> None:
    """A exceção de língua de 06/09 continua de pé."""
    assert mesa_viva.frase_dos_transportes(2, 1) == "2 USB · 1 BT"
    for proibida in ("cabo", "rádio", "radio"):
        assert proibida not in mesa_viva.frase_dos_transportes(2, 1).lower()


def _fonte_do_monta() -> str:
    """O texto do `interface/monta.py`, LIDO DO DISCO e nunca importado."""
    import pathlib

    from hefesto_dualsense4unix import interface

    arq = pathlib.Path(interface.__file__).parent / "monta.py"
    assert arq.is_file(), f"o `monta.py` não está em {arq} — ele mudou de lugar"
    return arq.read_text(encoding="utf-8")


def test_o_esqueleto_usa_o_mesmo_dono_da_frase() -> None:
    """O `monta.py` não pode ter uma segunda cópia da formatação."""
    fonte = _fonte_do_monta()

    assert "frase_dos_transportes" in fonte, (
        "o `monta.py` parou de chamar `mesa_viva.frase_dos_transportes` — ele "
        "voltou a formatar a contagem por conta própria, e o esqueleto vai "
        "divergir do que o piloto pinta"
    )

    literal = re.compile(r"\{usb\}\s*USB\s*·\s*\{bt\}\s*BT")
    assert not literal.search(fonte), (
        "a interpolação literal `{usb} USB · {bt} BT` voltou ao `monta.py`. "
        "São dois escritores da mesma frase: a formatação mora em "
        "`mesa_viva.frase_dos_transportes`, e só lá"
    )


def test_o_esqueleto_e_o_vivo_dizem_a_mesma_coisa_para_a_mesa_dela() -> None:
    """Fim a fim, no formato: o que o esqueleto grava é o que o piloto pinta."""
    _, vivo = mesa_viva.texto_da_contagem([{"transporte": "bt"}])

    fonte = _fonte_do_monta()
    assert "frase_dos_transportes(usb, bt)" in fonte, (
        "o `monta.py` chama o dono com outros argumentos que não a contagem "
        "de `CONECTADOS` — confira se ele não passou a contar outra coisa"
    )
    do_esqueleto = mesa_viva.frase_dos_transportes(0, 1)

    assert vivo == do_esqueleto == "1 BT"


def test_a_regua_sabe_reprovar() -> None:
    """Régua que só sabe passar não é régua."""
    def formula_antiga(usb: int, bt: int) -> str:
        return f"{usb} USB · {bt} BT"

    assert formula_antiga(0, 1) == "0 USB · 1 BT"
    assert formula_antiga(0, 1) != mesa_viva.frase_dos_transportes(0, 1)

    assert formula_antiga(2, 1) == mesa_viva.frase_dos_transportes(2, 1), (
        "com os dois transportes presentes as duas fórmulas dizem o mesmo; "
        "uma régua que medisse SÓ este caso passaria verde sobre o defeito"
    )
