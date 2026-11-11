"""A escolha da tela não se queima sem monitor (11/11/2026).

Medido no diário de 11/11: o projetor (a única tela) reiniciou às 16h58, o portal respondeu
``No output`` e o ``PermissionStore`` passou a dizer ``No entry`` para a ficha guardada. O portal
consome a ficha no ``SelectSources`` e só grava outra quando o ``Start`` dá certo; a reabertura
feita sem monitor a queimava, e o diálogo voltava. Aqui o portal de mentira FAZ ISSO (consome a
ficha do armazém de mentira a cada ``SelectSources`` que a leva), o ``/sys/class/drm`` é uma pasta
do teste e o relógio é o da ``Cena``: nenhuma prova chama o portal de verdade nem abre diálogo.

MORDIDA: arrancar a conferência da saída (o ``_conferir_a_tela`` e a guarda de antes do barramento),
trocar a saída da ficha por «qualquer saída ligada», tirar o ``_esquecer`` da ficha perdida ou
o aviso próprio da ``Captura``, e a régua reprova.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import structlog.testing

from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
from tests.unit.test_a_captura_nao_acorda_o_portal_antes_da_sessao import (
    _PRECISA_DO_PORTAL,
    Atendente,
    Barramento,
    Cena,
    PortalDeTeste,
    barramento,  # noqa: F401
)

_DESLIGADA = "a tela escolhida está desligada"
_PERDIDA = "a escolha da tela se perdeu no portal"


@pytest.fixture(autouse=True)
def _sessao_do_cosmic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "COSMIC")


class Drm:
    """Um ``/sys/class/drm`` de mentira: uma pasta ``card0-<saída>/status`` por saída."""

    def __init__(self, raiz: Path, monkeypatch: pytest.MonkeyPatch, **estados: str) -> None:
        self.raiz = raiz
        raiz.mkdir()
        for nome, estado in estados.items():
            self.poe(nome.replace("_", "-"), estado)
        monkeypatch.setattr(tj, "RAIZ_DRM", raiz)

    def poe(self, nome: str, estado: str) -> None:
        pasta = self.raiz / f"card0-{nome}"
        pasta.mkdir(exist_ok=True)
        (pasta / "status").write_text(f"{estado}\n", encoding="utf-8")


def _drm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **estados: str) -> Drm:
    return Drm(tmp_path / "drm-de-mentira", monkeypatch, **estados)


def _dados_da_ficha(saida: str) -> tuple[str, tuple[Any, ...]]:
    """Os dados que o armazém devolve: o compositor guarda o que quiser dentro do ``v``."""
    detalhes = {"output": ("s", saida), "tamanho": ("(uu)", (1920, 1080))}
    return "(suv)", ("COSMIC", 1, ("a(ua{sv})", [(1, detalhes)]))


class ArmazemDeMentira(Atendente):
    """O ``PermissionStore``: o ``Lookup`` lê sem tirar nada, e ``No entry`` se a entrada falta."""

    def __init__(self, endereco: str, entradas: dict[str, tuple[str, Any]]) -> None:
        self.entradas = entradas
        super().__init__(endereco, tj._ARMAZEM)

    def responder(self, mensagem: Any) -> None:
        from jeepney import HeaderFields, new_error, new_method_return

        campos = mensagem.header.fields
        if campos.get(HeaderFields.member) != "Lookup":
            self._conexao.send(new_error(mensagem, tj._FICHA_PERDIDA, "s", ("só Lookup",)))
            return
        tabela, ficha = mensagem.body
        if tabela != tj._TABELA_DA_TELA or ficha not in self.entradas:
            self._conexao.send(
                new_error(mensagem, tj._FICHA_PERDIDA, "s", (f"No entry for {ficha}",)))
            return
        self._conexao.send(new_method_return(mensagem, "a{sas}v", ({}, self.entradas[ficha])))


class PortalQueConsome(PortalDeTeste):
    """O portal de verdade: o ``SelectSources`` que leva uma ficha a consome do armazém."""

    def __init__(self, endereco: str, armazem: ArmazemDeMentira, **jeitos: Any) -> None:
        self.armazem = armazem
        super().__init__(endereco, **jeitos)

    def responder(self, mensagem: Any) -> None:
        from jeepney import HeaderFields

        if mensagem.header.fields.get(HeaderFields.member) == "SelectSources":
            ficha = dict(mensagem.body[-1]).get("restore_token")
            if ficha is not None:
                self.armazem.entradas.pop(ficha[1], None)
        super().responder(mensagem)


def _escolhas(portal: PortalDeTeste) -> list[dict[str, object]]:
    return [o for m, o in portal.levados if m == "SelectSources"]


def _ausentes(diario: Sequence[Mapping[str, Any]]) -> list[str]:
    return [r["motivo"] for r in diario if r["event"] == "tela_do_jogo_ausente"]


@_PRECISA_DO_PORTAL
def test_com_a_saida_escolhida_desligada_nada_sai_ao_portal_e_a_ficha_fica_no_armazem(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """HDMI-A-1 é a tela da ficha e está desligada; DP-1 está ligada e não basta."""
    drm = _drm(tmp_path, monkeypatch, HDMI_A_1="disconnected", DP_1="connected")
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-boa", encoding="utf-8")
    armazem = ArmazemDeMentira(barramento.endereco, {"ficha-boa": _dados_da_ficha("HDMI-A-1")})
    portal = PortalQueConsome(barramento.endereco, armazem)
    try:
        cena = Cena(tj.FonteDoPortal(ficha))
        with structlog.testing.capture_logs() as diario:
            cena.correr(10.0)
        assert portal.pedidos == [], portal.pedidos
        assert "ficha-boa" in armazem.entradas
        assert ficha.read_text(encoding="utf-8") == "ficha-boa"
        assert _ausentes(diario) == [_DESLIGADA]
        assert len(cena.publicados) == 1
        drm.poe("HDMI-A-1", "connected")
        cena.correr(6.0)
        escolhas = _escolhas(portal)
        assert escolhas, portal.pedidos
        assert escolhas[0]["restore_token"] == ("s", "ficha-boa")
    finally:
        portal.fechar()
        armazem.fechar()


@_PRECISA_DO_PORTAL
def test_sem_nenhuma_saida_ligada_a_fonte_nem_acorda_o_portal(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    _drm(tmp_path, monkeypatch, HDMI_A_1="disconnected", DP_1="disconnected")
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-boa", encoding="utf-8")
    from jeepney.io import blocking

    abertas: list[object] = []
    abrir_de_verdade = blocking.open_dbus_connection

    def contar(*args: Any, **kwargs: Any) -> Any:
        abertas.append(args)
        return abrir_de_verdade(*args, **kwargs)

    monkeypatch.setattr(blocking, "open_dbus_connection", contar)
    cena = Cena(tj.FonteDoPortal(ficha))
    with structlog.testing.capture_logs() as diario:
        cena.correr(10.0)
    assert abertas == []
    assert barramento.ativacoes() == 0
    assert barramento.ativacoes_do_gerente() == 0
    assert ficha.read_text(encoding="utf-8") == "ficha-boa"
    assert _ausentes(diario) == [_DESLIGADA]


@_PRECISA_DO_PORTAL
def test_sem_dado_legivel_na_ficha_vale_qualquer_saida_ligada(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    _drm(tmp_path, monkeypatch, HDMI_A_1="disconnected", DP_1="connected")
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-boa", encoding="utf-8")
    armazem = ArmazemDeMentira(barramento.endereco, {"ficha-boa": ("s", "sem nome de saída")})
    portal = PortalQueConsome(barramento.endereco, armazem)
    try:
        Cena(tj.FonteDoPortal(ficha)).correr(4.0)
        assert _escolhas(portal)[0]["restore_token"] == ("s", "ficha-boa")
    finally:
        portal.fechar()
        armazem.fechar()


@_PRECISA_DO_PORTAL
def test_o_armazem_fora_do_ar_deixa_a_ficha_valer(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    _drm(tmp_path, monkeypatch, HDMI_A_1="connected")
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-boa", encoding="utf-8")
    portal = PortalDeTeste(barramento.endereco)
    try:
        Cena(tj.FonteDoPortal(ficha)).correr(4.0)
        assert _escolhas(portal)[0]["restore_token"] == ("s", "ficha-boa")
    finally:
        portal.fechar()


@_PRECISA_DO_PORTAL
def test_a_ficha_que_o_portal_perdeu_sai_do_disco_e_o_pedido_volta_uma_vez(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    monkeypatch.setattr(tj, "PRAZO_DA_ESCOLHA_S", 0.2)
    _drm(tmp_path, monkeypatch, HDMI_A_1="connected")
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-queimada", encoding="utf-8")
    armazem = ArmazemDeMentira(barramento.endereco, {})
    portal = PortalQueConsome(barramento.endereco, armazem, respostas={"Start": None})
    try:
        cena = Cena(tj.FonteDoPortal(ficha))
        with structlog.testing.capture_logs() as diario:
            cena.correr(10.0)
        escolhas = _escolhas(portal)
        assert len(escolhas) == 1, portal.pedidos
        assert "restore_token" not in escolhas[0]
        assert not ficha.exists()
        assert [r["motivo"] for r in diario if r["event"] == "tela_do_jogo_escolha_perdida"] == [
            _PERDIDA]
    finally:
        portal.fechar()
        armazem.fechar()


def test_os_conectores_contam_o_desconhecido_como_ligado_e_juntam_as_placas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drm = _drm(tmp_path, monkeypatch, HDMI_A_1="disconnected", DP_2="unknown", eDP_1="connected")
    (drm.raiz / "card1-HDMI-A-1").mkdir()
    (drm.raiz / "card1-HDMI-A-1" / "status").write_text("connected\n", encoding="utf-8")
    (drm.raiz / "card0").mkdir()
    (drm.raiz / "card1-DP-3").mkdir()
    assert tj.conectores() == {
        "DP-2": True, "HDMI-A-1": True, "eDP-1": True}


def test_sem_drm_legivel_a_pergunta_nao_trava_a_captura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tj, "RAIZ_DRM", tmp_path / "nao-existe")
    assert tj.conectores() == {}


@_PRECISA_DO_PORTAL
def test_o_install_sem_tela_ligada_nao_pergunta_e_deixa_para_o_primeiro_jogo(
    barramento: Barramento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    _drm(tmp_path, monkeypatch, HDMI_A_1="disconnected")
    ficha = tmp_path / "ficha"
    ficha.write_text("ficha-boa", encoding="utf-8")
    assert tj.escolher_a_tela(tj.FonteDoPortal(ficha), tentativas=2, dormir=lambda _s: None) == 2
    assert _DESLIGADA in capsys.readouterr().out
    assert barramento.ativacoes() == 0
    assert ficha.read_text(encoding="utf-8") == "ficha-boa"


class _FonteDoProjetor:
    """A fonte que cai com a tela, fica desligada e volta: cada ``abrir`` faz o próximo da fila."""

    def __init__(self, *jeitos: bool | BaseException) -> None:
        self.jeitos = list(jeitos)
        self.quadros = 0

    def abrir(self) -> bool:
        jeito = self.jeitos.pop(0)
        if isinstance(jeito, BaseException):
            raise jeito
        return jeito

    def quadro(self) -> tj.Quadro | None:
        self.quadros += 1
        return None if self.quadros == 2 else tj.Quadro(2, 2, 8, "BGRx", bytes(16))

    def fechar(self) -> None:
        return None

    def interromper(self) -> None:
        return None


def test_a_captura_diz_a_tela_desligada_mesmo_depois_de_dizer_que_a_fonte_parou() -> None:
    """O diário de 16h58: a fonte parou de entregar quadro, e o resto da espera ficava mudo."""
    fonte = _FonteDoProjetor(True, tj.TelaDesligadaError(_DESLIGADA),
                             tj.TelaDesligadaError(_DESLIGADA), True)
    cena = Cena(fonte)
    with structlog.testing.capture_logs() as diario:
        cena.correr(20.0)
    assert _ausentes(diario) == ["a fonte parou de entregar quadro", _DESLIGADA]
    ausentes = [p for p in cena.publicados if p["dano"] is None]
    assert len(ausentes) == 1
    assert cena.publicados[-1]["dano"] is not None
