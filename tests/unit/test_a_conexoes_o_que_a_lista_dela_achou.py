"""A seção Rádio e Adaptadores faz o que diz — A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit.radio_de_mentira import AZUL, ROXO, VERDE, VERMELHO

QUATRO = (VERMELHO, AZUL, VERDE, ROXO)
TECLADO = "aa:bb:cc:00:00:7e"


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os dela, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


def _plano(controles: list[dict[str, Any]], adaptadores: tuple[str, ...]) -> Any:
    from hefesto_dualsense4unix.integrations import plano_de_radio

    planos = plano_de_radio.plano_por_adaptador(
        controles, adaptadores=adaptadores, listar=lambda _p: [], raiz="/nao/existe")
    return plano_de_radio.ordem_de_redistribuicao(planos)


PCI = "0000:00:14.0"
ADAPTADORES_DA_TELA = ("aa:bb:cc:00:00:09", "aa:bb:cc:00:00:15", "aa:bb:cc:00:00:21")
LUGARES_DA_TELA = (f"pci-{PCI}-usb-0:1.2", f"pci-{PCI}-usb-0:4.1.4", f"pci-{PCI}-usb-0:4.1.3")
NOMES_DA_TELA = ("Esquerda", "Direita", "Centro")


def _id(endereco: str) -> str:
    """O id da tela: 12 hex em maiúsculas, a forma do `_mac` do pacote."""
    return endereco.replace(":", "").upper()


def _objeto(adaptador: int, aparelho: str, **kw: Any) -> Any:
    from hefesto_dualsense4unix.integrations.bluez_dbus import AparelhoDoBluez

    no = f"/org/bluez/hci{adaptador}/dev_{aparelho.upper().replace(':', '_')}"
    return AparelhoDoBluez(no, f"/org/bluez/hci{adaptador}", aparelho.upper(), **kw)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    monkeypatch.setattr(a08_conexoes, "LER_NA_HORA", True)
    monkeypatch.setattr(a08_conexoes, "_FUNDO", {})
    monkeypatch.setattr(a08_conexoes, "_ABERTO", {})
    monkeypatch.setattr(a08_conexoes, "_CENA_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_SALA_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_CHEGADAS", {})
    monkeypatch.setattr(a08_conexoes, "_mesa_do_radio", lambda recarregar=False: Mesa())
    monkeypatch.setattr(a08_conexoes, "_ler_o_historico", lambda: {})
    return a08_conexoes


def _montar(a08: Any, monkeypatch: pytest.MonkeyPatch, *, adaptadores: int = 3,
            aparelhos: tuple[Any, ...] = ()) -> None:
    """O BlueZ e o `maquina.json` da mesa declarada, com ``adaptadores`` deles."""
    from hefesto_dualsense4unix.integrations.bluez_dbus import AdaptadorDoBluez
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    lidos = tuple(
        AdaptadorDoBluez(f"/org/bluez/hci{i}", f"hci{i}", ADAPTADORES_DA_TELA[i].upper(),
                         lugar=LUGARES_DA_TELA[i], varrendo=False)
        for i in range(adaptadores))
    monkeypatch.setattr(a08, "_FUNDO", {})
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: (lidos, aparelhos))
    maquina = MaquinaConfig(adaptadores={_id(ADAPTADORES_DA_TELA[i]).lower():
                                         {"nome": NOMES_DA_TELA[i]}
                                         for i in range(adaptadores)})
    monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (maquina, {3: PCI}))


def _linha(a08: Any, cena: dict[str, Any], quem: str) -> str:
    ap = next(a for a in cena["aparelhos"] if a["id"].replace(":", "").lower()
              == quem.replace(":", "").lower())
    return str(a08.html_da_linha(ap, cena))


def _esperando(aparelho: str, destino: int, **kw: Any) -> dict[str, Any]:
    return {"aparelho": aparelho, "destino": ADAPTADORES_DA_TELA[destino],
            "estado": "esperando", "passo": "gesto", "motivo": "", "origens": [],
            "quando": time.time(), **kw}


@pytest.mark.parametrize(("modalias", "gesto"), [
    ("bluetooth:v054Cp0CE6d0100", "Segure PS + Create"),   # DualSense
    ("bluetooth:v054Cp0DF2d0100", "Segure PS + Create"),   # DualSense Edge
    ("bluetooth:v054Cp09CCd0100", "Segure PS + Share"),
    ("bluetooth:v2DC8p6002d0100", ""),
    ("", "Segure PS + Create"),
])
def test_cada_controle_diz_o_gesto_do_modelo_dele(a08: Any, modalias: str, gesto: str) -> None:
    ap = {"tipo": "controle", "modalias": modalias}
    assert a08.gesto_de_parear(ap) == gesto
    fala = a08._como_se_pareia(ap)
    if gesto:
        assert gesto.removeprefix("Segure ") in fala
    else:
        assert "PS" not in fala and "ponha o controle para parear" in fala


def test_o_outro_aparelho_nao_vira_o_outro(a08: Any) -> None:
    """«Depois, ponha o outro para parear» era a frase do tipo «outro»."""
    assert a08._como_se_pareia({"tipo": "outro"}) == "Depois, ponha o aparelho para parear."
    assert a08._como_se_pareia({"tipo": "caixa"}) == "Depois, ponha a caixa de som para parear."


def test_o_vizinho_que_o_sistema_reconhece_mostra_o_desenho_dele(a08: Any) -> None:
    """O selo do rádio vizinho: declarado, o tipo dele; sugerido pelo kernel, o"""
    cena = {"espectro": [], "vizinhos": [
        {"id": "046d:c52b", "tipo": "", "nome": "", "sugestao": "Teclado",
         "sugestao_tipo": "teclado"},
        {"id": "0bda:8179", "tipo": "wifi", "nome": "Wi-Fi", "sugestao": "",
         "sugestao_tipo": ""},
        {"id": "1234:5678", "tipo": "", "nome": "", "sugestao": "", "sugestao_tipo": ""},
    ]}
    selos = a08.html_fora_da_faixa(cena).split("</button>")
    assert "#rd-teclado" in selos[0] and "sem-nome" in selos[0]
    assert "#rd-wifi" in selos[1]
    assert "#rd-ajuda" in selos[2]


class _PonteDaCentralOcupada:
    """O `radio.mover` com a central ocupada: o que o tratador real responde"""

    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        assert metodo == "radio.mover"
        self.pedidos.append(dict(params))
        return {"status": "ocupado", "movimento": {"estado": "nao_chegou", "motivo": "ocupado"}}


# O QUE O CONFERENTE ACHOU (25/09/2026) — a cura que só valia para o DualSense
# O rádio de mentira respondia o `HID_PHYS` só pelo DualSense e dava movimento a
# que o daemon (ele só mede o movimento do DualSense). Com ele fiel, três curas
# desta sprint caíam fora do DualSense de classe publicada.

TECLADO_LE = "aa:bb:cc:00:00:7d"
OUTRO_CONTROLE = "aa:bb:cc:00:00:8b"


