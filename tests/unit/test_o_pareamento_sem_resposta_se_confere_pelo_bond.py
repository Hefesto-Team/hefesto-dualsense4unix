"""O ``Pair`` sem resposta se confere pelo bond — O-PAREAMENTO-SEM-RESPOSTA-SE-CONFERE-PELO-BOND-01.

O bluetoothd 5.86 às vezes não responde ao ``Device1.Pair`` depois de o bond
estar feito (``device_browse_sdp`` devolve ``-EBUSY`` e o pedido fica sem
resposta; o upstream curou na 5.87, ``622a46ebc``). O silêncio não é veredito:
a resposta está no ``Paired`` e no ``Bonded`` do nó. As réguas cobrem os três
donos do ``Pair`` — o vivo (Gio), o do ``busctl`` e a ponte root.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from tests.unit import barramento_de_mentira as bp
from tests.unit import bluez_de_mentira as bm

NO = bm.no_de(bm.CONTROLE)
SEM_RESPOSTA_GIO = "Timeout was reached"


class _PairQueNaoResponde(bm.BarramentoDeMentira):
    """O ``Pair`` volta sem resposta (ou com ``erro``); o bond nasce se ``bond``."""

    def __init__(self, *, erro: str = "", bond: bool = True, bond_velho: bool = False) -> None:
        super().__init__()
        self.erro = erro
        self.bond = bond
        if bond_velho:
            self.mesa[NO][bd.APARELHO].update(Paired=True, Bonded=True)

    def _parear(self, caminho: str) -> bd.Escrita:
        if self.bond:
            self.mesa[caminho][bd.APARELHO].update(Paired=True, Bonded=True)
            self.emitir(bd.Sinal("mudou", caminho=caminho, interface=bd.APARELHO,
                                 mudadas={"Paired": True, "Bonded": True}))
        return bd.Escrita(False, self.erro, SEM_RESPOSTA_GIO if not self.erro else "recusado")


def _trusted(barramento: bm.BarramentoDeMentira) -> list[Any]:
    return [valor for caminho, _i, nome, valor in barramento.escritas
            if caminho == NO and nome == "Trusted"]


@pytest.fixture(autouse=True)
def _trava_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.integrations import diario_do_radio

    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))


@pytest.mark.parametrize("erro", ["", "org.freedesktop.DBus.Error.NoReply"])
def test_o_pair_sem_resposta_com_bond_feito_pareou_e_confia(erro: str) -> None:
    """MORDIDA: sem a pergunta posterior em ``bluez_dbus``, ``feita`` cai para ``False``."""
    barramento = _PairQueNaoResponde(erro=erro)
    vivo = bd.DonoVivo(barramento)
    assert vivo.ligar()

    escrita = vivo.parear(NO, espera=0.1)

    assert escrita.feita, escrita
    assert _trusted(barramento) == [True]


def test_o_pair_sem_resposta_sem_bond_nao_pareou() -> None:
    barramento = _PairQueNaoResponde(bond=False)
    vivo = bd.DonoVivo(barramento)
    assert vivo.ligar()

    escrita = vivo.parear(NO, espera=0.1)

    assert not escrita.feita
    assert _trusted(barramento) == []


@pytest.mark.parametrize("erro", [
    "org.bluez.Error.AuthenticationFailed",
    "org.bluez.Error.AuthenticationCanceled",
    "org.bluez.Error.AuthenticationRejected",
    "org.bluez.Error.Canceled",
    "org.bluez.Error.Rejected",
])
def test_a_recusa_de_verdade_continua_recusa_mesmo_com_o_bond(erro: str) -> None:
    """O nome do erro manda: a recusa do BlueZ não se lê pelo bond."""
    barramento = _PairQueNaoResponde(erro=erro)
    vivo = bd.DonoVivo(barramento)
    assert vivo.ligar()

    escrita = vivo.parear(NO, espera=0.1)

    assert not escrita.feita
    assert escrita.erro == erro
    assert _trusted(barramento) == []


def test_o_bond_velho_nao_vira_pareamento_deste_pair() -> None:
    """O bond que JÁ estava lá antes do ``Pair`` não responde por ele."""
    barramento = _PairQueNaoResponde(bond_velho=True)
    vivo = bd.DonoVivo(barramento)
    assert vivo.ligar()

    escrita = vivo.parear(NO, espera=0.1)

    assert not escrita.feita
    assert _trusted(barramento) == []


class _BusctlDeMentira:
    """Um executor no formato ``busctl``: o ``Pair`` falha calado e faz o bond se ``bond``."""

    def __init__(self, *, bond: bool, bond_velho: bool = False) -> None:
        self.bond = bond
        self.props = {"Paired": bond_velho, "Bonded": bond_velho}
        self.chamadas: list[list[str]] = []

    def __call__(self, argumentos: Any) -> str | None:
        argumentos = list(argumentos)
        self.chamadas.append(argumentos)
        if argumentos[0] == "get-property":
            valor = self.props.get(argumentos[-1])
            return None if valor is None else f"b {'true' if valor else 'false'}"
        if argumentos[0] == "call" and argumentos[4] == "Pair":
            if self.bond:
                self.props.update(Paired=True, Bonded=True)
            return None
        return ""

    def trusted(self) -> list[list[str]]:
        return [c for c in self.chamadas if c[0] == "set-property" and c[4] == "Trusted"]


def test_pelo_busctl_o_pair_sem_resposta_com_bond_pareou() -> None:
    executor = _BusctlDeMentira(bond=True)
    escrita = bd.pelo_executor(executor).parear(NO)
    assert escrita.feita, escrita
    assert len(executor.trusted()) == 1


def test_pelo_busctl_o_pair_sem_resposta_sem_bond_nao_pareou() -> None:
    executor = _BusctlDeMentira(bond=False)
    assert not bd.pelo_executor(executor).parear(NO).feita
    assert executor.trusted() == []


def test_pelo_busctl_o_bond_velho_nao_responde_pelo_pair() -> None:
    """O ``busctl`` não diz o nome do erro: o bond de antes é o que separa a recusa."""
    executor = _BusctlDeMentira(bond=False, bond_velho=True)
    assert not bd.pelo_executor(executor).parear(NO).feita
    assert executor.trusted() == []


class _BluezQueNaoResponde(bm.BluezParticular):
    """O 5.86 do defeito: o bond fica feito e o ``Pair`` nunca recebe resposta."""

    erro = ""

    def _parear(self, remetente: str, caminho: str, invocacao: Any) -> None:
        self._mudou(caminho, bd.APARELHO, "Paired", True)
        self._mudou(caminho, bd.APARELHO, "Bonded", True)
        if self.erro:
            invocacao.return_dbus_error(self.erro, "recusado")
        self.sem_resposta = invocacao


@pytest.mark.skipif(not bm.ha_dbus_daemon(), reason="sem dbus-daemon ou sem Gio nesta máquina")
@pytest.mark.parametrize("erro", ["", "org.bluez.Error.AuthenticationFailed"])
def test_pelo_gio_o_silencio_do_pair_se_confere_pelo_bond(tmp_path: Path, erro: str) -> None:
    """O erro que o Gio dá ao tempo estourado é o que a cura lê — medido, não suposto."""
    classe = type("Bluez", (_BluezQueNaoResponde,), {"erro": erro})
    with classe(tmp_path) as bluez:
        barramento = bd.BarramentoGio(bluez.endereco)
        assert barramento.abrir(), barramento.erro
        vivo = bd.DonoVivo(barramento)
        try:
            assert vivo.ligar()
            escrita = vivo.parear(NO, espera=0.5)
            if erro:
                assert not escrita.feita and escrita.erro == erro
                assert bluez.mesa[NO][bd.APARELHO]["Trusted"] is False
            else:
                assert escrita.feita, escrita
                assert bluez.mesa[NO][bd.APARELHO]["Trusted"] is True
        finally:
            vivo.fechar()


_BUSCTL_DA_PONTE = """#!/usr/bin/env bash
set -u
raiz="${BUSCTL_FALSO_RAIZ}"
case "${1:-}" in
    tree) cat "${raiz}/tree"; exit 0 ;;
    get-property)
        arquivo="${raiz}/props/${3//\\//__}.${5:-}"
        [[ -f "${arquivo}" ]] || exit 1
        cat "${arquivo}"; exit 0 ;;
    call|set-property)
        printf '%s\\n' "$*" >>"${raiz}/chamadas"
        if [[ "${1}" == call && "${5:-}" == Pair ]]; then
            if [[ -e "${raiz}/pair-faz-bond" ]]; then
                printf 'b true\\n' >"${raiz}/props/${3//\\//__}.Paired"
                printf 'b true\\n' >"${raiz}/props/${3//\\//__}.Bonded"
            fi
            exit 1
        fi
        exit 0 ;;
esac
exit 1
"""


def _ponte(tmp_path: Path, *, bond: bool, bond_velho: bool = False) -> tuple[int, str, Path]:
    raiz = bp.montar(tmp_path)
    busctl = raiz / "bin" / "busctl"
    busctl.write_text(_BUSCTL_DA_PONTE, encoding="utf-8")
    busctl.chmod(0o755)
    caminho = bp.caminho_do(bp.CONTROLE).replace("/", "__")
    estado = "true" if bond_velho else "false"
    (raiz / "props" / f"{caminho}.Paired").write_text(f"b {estado}\n", encoding="utf-8")
    (raiz / "props" / f"{caminho}.Bonded").write_text(f"b {estado}\n", encoding="utf-8")
    if bond:
        (raiz / "pair-faz-bond").write_text("", encoding="utf-8")
    resultado = subprocess.run(
        ["bash", str(bp.PONTE), "parear"],
        input=f"{bp.ADAPTADOR}\n{bp.CONTROLE}\n",
        capture_output=True, text=True, env=bp.ambiente(raiz), timeout=60, check=False,
    )
    chamadas = raiz / "chamadas"
    texto = chamadas.read_text(encoding="utf-8") if chamadas.exists() else ""
    return resultado.returncode, texto, raiz


def _trusted_da_ponte(chamadas: str) -> list[str]:
    return [linha for linha in chamadas.splitlines() if "Trusted b true" in linha]


def test_a_ponte_confere_o_bond_quando_o_pair_nao_responde(tmp_path: Path) -> None:
    """MORDIDA: sem a pergunta posterior na ponte, sai ``rc=1`` sem ``Trusted``."""
    rc, chamadas, _ = _ponte(tmp_path, bond=True)
    assert rc == 0
    assert len(_trusted_da_ponte(chamadas)) == 1


def test_a_ponte_sem_bond_continua_falhando(tmp_path: Path) -> None:
    rc, chamadas, _ = _ponte(tmp_path, bond=False)
    assert rc == 1
    assert _trusted_da_ponte(chamadas) == []


def test_a_ponte_nao_toma_o_bond_velho_pelo_pair(tmp_path: Path) -> None:
    rc, chamadas, _ = _ponte(tmp_path, bond=False, bond_velho=True)
    assert rc == 1
    assert _trusted_da_ponte(chamadas) == []

