"""O Hefesto sabe em qual vaga de pareamento o controle está.

O-HEFESTO-SABE-EM-QUAL-VAGA-DE-PAREAMENTO-O-CONTROLE-ESTA-01.

O DualSense guarda até quatro aparelhos e troca de vaga com o PS e um botão de
face segurados (3 s; 5 s para registrar). Para o PC, o controle que troca de
vaga some como um que caiu. A régua separa os dois pelo padrão de desconexão do
BlueZ (o ``Device1.Disconnected``, que chega antes do ``Connected`` falso) e
pelo gesto segurado antes dele, para cada um dos quatro controles.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from tests.unit import bluez_de_mentira as bm

NO = bm.no_de(bm.CONTROLE)
NO_OUTRO = bm.no_de(bm.OUTRO)


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _Mesa:
    """O dono vivo sobre o barramento de mentira, com dois controles pareados e ligados."""

    def __init__(self) -> None:
        self.relogio = _Relogio()
        self.vaga = bd.VigiaDaVaga(self.relogio)
        self.barramento = bm.BarramentoDeMentira()
        for no in (NO, NO_OUTRO):
            self.barramento.mesa[no][bd.APARELHO].update(Paired=True, Connected=True)
        self.vivo = bd.DonoVivo(self.barramento, vaga=self.vaga)
        assert self.vivo.ligar()
        self.avisos: list[tuple[str, dict[str, Any]]] = []
        self.vivo.ouvir(lambda aviso, dados: self.avisos.append((aviso, dict(dados))))

    def segurar(self, botoes: Iterable[str], segundos: float, *, quem: str = bm.CONTROLE) -> None:
        """Um tique a cada 0,25 s com ``botoes`` apertados, por ``segundos``."""
        fim = self.relogio.agora + segundos
        while True:
            self.vaga.observar({quem: frozenset(botoes), None: frozenset()})
            if self.relogio.agora >= fim:
                return
            self.relogio.agora = min(fim, self.relogio.agora + 0.25)

    def esperar(self, segundos: float) -> None:
        self.relogio.agora += segundos

    def cair(self, razao: str | None, *, no: str = NO) -> dict[str, Any]:
        """A sequência do bluetoothd: o ``Disconnected`` (se houver) e o ``Connected`` falso."""
        if razao is not None:
            self.barramento.emitir(bd.Sinal("desconectou", caminho=no, razao=razao))
        self.barramento.emitir(
            bd.Sinal("mudou", caminho=no, interface=bd.APARELHO, mudadas={"Connected": False})
        )
        desligou = [dados for aviso, dados in self.avisos if aviso == bd.AVISO_DESLIGOU]
        assert len(desligou) == 1, self.avisos
        self.avisos.clear()
        return desligou[0]


def test_a_troca_de_vaga_sai_com_a_frase_dela() -> None:
    """MORDIDA: tratar a troca como queda (sem o ramo do gesto em ``a_saida``) reprova."""
    mesa = _Mesa()
    mesa.segurar({"ps", "triangle"}, 3.0)

    dados = mesa.cair(bd.RAZAO_DO_CONTROLE)

    assert dados["saida"] == bd.SAIDA_OUTRO_APARELHO
    assert dados["frase"] == "O controle foi para outro aparelho"
    assert dados["razao"] == bd.RAZAO_DO_CONTROLE
    assert dados["aparelho"] == bm.CONTROLE
    assert mesa.vivo.como_saiu(bm.CONTROLE.upper()) == bd.SAIDA_OUTRO_APARELHO


@pytest.mark.parametrize("botao", sorted(bd.BOTOES_DA_VAGA))
def test_qualquer_das_quatro_vagas_vale(botao: str) -> None:
    mesa = _Mesa()
    mesa.segurar({"ps", botao}, 5.0)

    assert mesa.cair(bd.RAZAO_DO_CONTROLE)["saida"] == bd.SAIDA_OUTRO_APARELHO


def test_a_queda_do_radio_continua_queda() -> None:
    mesa = _Mesa()

    dados = mesa.cair(bd.RAZAO_TIMEOUT)

    assert dados["saida"] == bd.SAIDA_CAIU
    assert "frase" not in dados


def test_o_controle_que_encerrou_sem_o_gesto_nao_foi_para_outro_aparelho() -> None:
    """O PS segurado sozinho é o desligar do controle, não a troca de vaga."""
    mesa = _Mesa()
    mesa.segurar({"ps"}, 10.0)

    dados = mesa.cair(bd.RAZAO_DO_CONTROLE)

    assert dados["saida"] == bd.SAIDA_O_CONTROLE_ENCERROU
    assert "frase" not in dados


def test_o_aperto_curto_e_atalho_e_nao_troca_de_vaga() -> None:
    """MORDIDA: sem o tempo segurado em ``VigiaDaVaga.observar``, o toque vira troca."""
    mesa = _Mesa()
    mesa.segurar({"ps", "cross"}, 1.0)

    assert mesa.cair(bd.RAZAO_DO_CONTROLE)["saida"] == bd.SAIDA_O_CONTROLE_ENCERROU


def test_o_gesto_antigo_nao_responde_pela_queda_de_agora() -> None:
    """MORDIDA: sem a janela em ``VigiaDaVaga.tomar``, o gesto de minutos atrás decide."""
    mesa = _Mesa()
    mesa.segurar({"ps", "circle"}, 3.0)
    mesa.segurar(set(), 0.0)
    mesa.esperar(60.0)

    assert mesa.cair(bd.RAZAO_TIMEOUT)["saida"] == bd.SAIDA_CAIU


def test_dois_botoes_de_face_com_o_ps_nao_sao_o_gesto() -> None:
    mesa = _Mesa()
    mesa.segurar({"ps", "cross", "circle"}, 4.0)

    assert mesa.cair(bd.RAZAO_DO_CONTROLE)["saida"] == bd.SAIDA_O_CONTROLE_ENCERROU


def test_o_gesto_se_gasta_na_primeira_queda() -> None:
    mesa = _Mesa()
    mesa.segurar({"ps", "square"}, 3.0)
    assert mesa.cair(bd.RAZAO_DO_CONTROLE)["saida"] == bd.SAIDA_OUTRO_APARELHO

    mesa.barramento.emitir(
        bd.Sinal("mudou", caminho=NO, interface=bd.APARELHO, mudadas={"Connected": True})
    )
    assert mesa.cair(bd.RAZAO_TIMEOUT)["saida"] == bd.SAIDA_CAIU


def test_o_desligar_daqui_ganha_do_gesto() -> None:
    """O Hefesto (ou a suspensão) encerrou o enlace: o gesto não decide."""
    mesa = _Mesa()
    mesa.segurar({"ps", "triangle"}, 3.0)

    assert mesa.cair(bd.RAZAO_DAQUI)["saida"] == bd.SAIDA_DAQUI


def test_o_gesto_e_de_cada_controle() -> None:
    """O gesto num controle não muda a saída do outro: vale para os quatro, nos dois adaptadores."""
    mesa = _Mesa()
    mesa.segurar({"ps", "triangle"}, 3.0, quem=bm.OUTRO)

    assert mesa.cair(bd.RAZAO_DO_CONTROLE)["saida"] == bd.SAIDA_O_CONTROLE_ENCERROU
    assert mesa.cair(bd.RAZAO_DO_CONTROLE, no=NO_OUTRO)["saida"] == bd.SAIDA_OUTRO_APARELHO


def test_sem_o_sinal_do_bluez_o_gesto_ainda_decide() -> None:
    """Um bluetoothd sem o ``Disconnected``: o ``Connected`` falso chega sozinho."""
    mesa = _Mesa()
    assert mesa.cair(None)["saida"] == bd.SAIDA_SEM_RAZAO

    mesa.barramento.emitir(
        bd.Sinal("mudou", caminho=NO, interface=bd.APARELHO, mudadas={"Connected": True})
    )
    mesa.segurar({"ps", "triangle"}, 3.0)
    assert mesa.cair(None)["saida"] == bd.SAIDA_OUTRO_APARELHO


def test_o_laco_dos_atalhos_entrega_os_botoes_ao_vigia(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: sem a chamada em ``poll.observar_os_atalhos``, o vigia nunca vê o gesto."""
    from hefesto_dualsense4unix.daemon.subsystems import poll

    relogio = _Relogio()
    vigia = bd.VigiaDaVaga(relogio)
    monkeypatch.setattr(bd, "_VAGA", vigia)
    monkeypatch.setattr(
        poll,
        "botoes_de_cada_controle",
        lambda _daemon, _botoes: {bm.CONTROLE: frozenset({"ps", "triangle"})},
    )

    class _Gerente:
        def observe(self, *_a: Any, **_k: Any) -> None:
            return None

    class _Daemon:
        _hotkey_manager = _Gerente()

    for _ in range(13):
        poll.observar_os_atalhos(_Daemon(), frozenset(), now=relogio.agora)
        relogio.agora += 0.25

    assert vigia.tomar(bm.CONTROLE)


# --- de ponta a ponta, por um dbus-daemon particular --------------------------


@pytest.mark.skipif(not bm.ha_dbus_daemon(), reason="sem dbus-daemon ou sem Gio nesta máquina")
def test_pelo_gio_o_disconnected_do_bluez_chega_com_a_razao(tmp_path: Path) -> None:
    """MORDIDA: sem a assinatura do ``Disconnected`` no ``BarramentoGio``, a razão some."""
    relogio = _Relogio()
    vaga = bd.VigiaDaVaga(relogio)
    with bm.BluezParticular(tmp_path) as bluez:
        bluez.mesa[NO][bd.APARELHO].update(Paired=True, Connected=True)
        barramento = bd.BarramentoGio(bluez.endereco)
        assert barramento.abrir(), barramento.erro
        vivo = bd.DonoVivo(barramento, vaga=vaga)
        avisos: list[dict[str, Any]] = []

        def ouvinte(aviso: str, dados: Any) -> None:
            if aviso == bd.AVISO_DESLIGOU:
                avisos.append(dict(dados))

        vivo.ouvir(ouvinte)
        try:
            assert vivo.ligar()
            for _ in range(13):
                vaga.observar({bm.CONTROLE: frozenset({"ps", "triangle"})})
                relogio.agora += 0.25
            variante = bluez.bluez.GLib.Variant

            def desconectar() -> None:
                bluez.bluez.conexao.emit_signal(
                    None, NO, bd.APARELHO, "Disconnected",
                    variante("(ss)", (bd.RAZAO_DO_CONTROLE, "Connection terminated by remote")),
                )
                bluez._mudou(NO, bd.APARELHO, "Connected", False)

            bluez.bluez.no_fio(desconectar)
            assert bm.esperar(lambda: bool(avisos)), "o Connected falso não chegou"
            assert avisos[0]["razao"] == bd.RAZAO_DO_CONTROLE
            assert avisos[0]["saida"] == bd.SAIDA_OUTRO_APARELHO
        finally:
            vivo.fechar()
