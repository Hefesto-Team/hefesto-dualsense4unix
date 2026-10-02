"""`alto` quer dizer a MESMA coisa nas duas pontas — medido em 05/09/2026."""

from __future__ import annotations

import pathlib

from hefesto_dualsense4unix.app.widgets import calibrar_entradas as cal

RAIZ = pathlib.Path(__file__).resolve().parents[2]
ARRANJO = RAIZ / "src/hefesto_dualsense4unix/integrations/arranjo_da_mesa.py"


def test_o_alto_e_o_hub_e_nao_a_escrivaninha() -> None:
    """A face "alta" é a do hub — a escrivaninha é o oposto dela no produto."""
    assert cal.FACE_QUE_E_ALTO == cal.FACE_HUB, (
        f"`FACE_QUE_E_ALTO` aponta para {cal.FACE_QUE_E_ALTO!r}. O produto "
        f"define `alto` como *acima da linha das cabeças* "
        f"(`maquina.FaceDeclarada`) e contrapõe a escrivaninha ao alto do rack "
        f"(`arranjo_da_mesa`): a resposta dela seria lida ao contrário, e o "
        f"conselho do arranjo sairia invertido.")
    assert cal.FACE_QUE_E_ALTO != cal.FACE_MESA


def test_o_perto_continua_sendo_a_frente() -> None:
    """A cura de um não pode mexer no vizinho — a guarda de vacuidade."""
    assert cal.FACE_QUE_E_PERTO == cal.FACE_FRENTE


def test_as_duas_faces_marcadas_sao_diferentes() -> None:
    """Uma face não pode ser a mais perto E a mais alta ao mesmo tempo."""
    assert cal.FACE_QUE_E_PERTO != cal.FACE_QUE_E_ALTO


def test_as_duas_estao_entre_as_faces_oferecidas() -> None:
    """Régua que não acha nada passa sempre: as duas têm de existir na lista."""
    assert cal.FACE_QUE_E_PERTO in cal.FACES
    assert cal.FACE_QUE_E_ALTO in cal.FACES


def test_o_arranjo_continua_dizendo_que_o_alto_e_o_hub() -> None:
    """A outra ponta da definição, LIDA e não digitada."""
    fonte = ARRANJO.read_text(encoding="utf-8")
    assert 'no_alto = sum(1 for e in bts if e.onde == "hub")' in fonte, (
        "o motor do arranjo deixou de contar o `alto` pelo hub — se a "
        "definição mudou, `calibrar_entradas.FACE_QUE_E_ALTO` muda junto")
    assert "na altura da escrivaninha, não no alto do rack" in fonte, (
        "sumiu a frase que contrapõe a escrivaninha ao alto do rack — era ela "
        "que provava que as duas são coisas OPOSTAS no produto")
