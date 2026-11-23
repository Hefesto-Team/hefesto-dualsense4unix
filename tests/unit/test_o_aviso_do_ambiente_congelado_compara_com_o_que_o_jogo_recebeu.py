"""O aviso do ambiente congelado compara com o que o jogo recebeu.

O-AVISO-DO-AMBIENTE-CONGELADO-COMPARA-COM-O-QUE-O-JOGO-RECEBEU-01 (22/11/2026). O aviso
`launch_env_mudou_depois_do_exec` comparava a mesa de agora com o recibo da última materialização
do processo, e não com o que o arme entregou ao wrapper. Reiniciar o serviço com o jogo aberto dava
o alarme falso (o recibo era de antes de os controles voltarem), e a entrega sem cobertura passava
calada (a materialização do meio recompunha o recibo). Agora o arme guarda a entrega (no daemon e no
arquivo `entregue`), o aviso a compara com a mesa só quando o `fonte_do_ambiente` do wrapper diz que
o jogo nasceu da resposta do serviço, e a entrega sem cobertura com a mesa prometendo um vpad por
físico tem `warning` próprio.

O ENSAIO usa a pasta `launch_env` de mentira, o `last_run` de um PID vivo (o do próprio teste) e o
`ambiente_do_lancamento` de verdade; o serviço reiniciado é um daemon novo sobre a mesma pasta.

MORDIDAS (md5 conferido na volta):
* o registro trocado pelo recibo da última materialização reprova as duas noites (17h33 e 17h29);
* sem a guarda de `fisicos <= 0` reprova «não sei nunca vira tinha cobertura»;
* sem a conferência do `epoch` ou da fonte reprova os casos sem registro da sessão;
* sem a condição da promessa do co-op reprova o co-op desligado;
* sem o sossego que volta a perguntar enquanto a fonte não chega reprova a fonte que chega depois
  do sossego, e sem o prazo reprova o sossego que para de perguntar.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le

APPID = 9924420
MAX_FISICOS = 4


class _Espiao:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, Any]]] = []

    def _r(self, evento: str, **kw: Any) -> None:
        self.eventos.append((evento, kw))

    info = warning = debug = _r

    def nomes(self) -> list[str]:
        return [evento for evento, _ in self.eventos]

    def campos(self, evento: str) -> dict[str, Any]:
        return next(kw for nome, kw in self.eventos if nome == evento)


def _daemon(
    *, vpads: int, fisicos: int, flavor: str = "dualsense", coop: bool = True,
    transportes: tuple[str, ...] = ("usb", "bt", "usb", "bt"),
) -> Any:
    players = {
        f"mac{i}": SimpleNamespace(vpad=SimpleNamespace(backend="uhid"))
        for i in range(2, vpads + 1)
    }
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor=flavor, coop_enabled=coop
        ),
        _gamepad_device=SimpleNamespace(backend="uhid") if vpads >= 1 else None,
        _coop_manager=SimpleNamespace(_players=players),
        controller=SimpleNamespace(
            describe_controllers=lambda: [
                {"connected": True, "transport": transportes[i % len(transportes)]}
                for i in range(fisicos)
            ]
        ),
    )


def _mesa_de(daemon: Any, *, vpads: int, fisicos: int) -> None:
    daemon._coop_manager.players = None
    daemon._coop_manager._players = {
        f"mac{i}": SimpleNamespace(vpad=SimpleNamespace(backend="uhid"))
        for i in range(2, vpads + 1)
    }
    daemon._gamepad_device = SimpleNamespace(backend="uhid") if vpads >= 1 else None
    daemon.controller.describe_controllers = lambda: [{"connected": True}] * fisicos


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    return tmp_path


@pytest.fixture
def espiao(monkeypatch: pytest.MonkeyPatch) -> _Espiao:
    espiao = _Espiao()
    monkeypatch.setattr(le, "logger", espiao)
    return espiao


def _jogo_aberto(lar: Path, *, epoch: int | None = None, fonte: str | None = "daemon") -> int:
    quando = epoch if epoch is not None else int(time.time())
    (lar / "last_run").write_text(
        f"appid={APPID}\nepoch={quando}\npid={os.getpid()}\n", encoding="utf-8"
    )
    if fonte is None:
        (lar / "fonte_do_ambiente").unlink(missing_ok=True)
    else:
        (lar / "fonte_do_ambiente").write_text(
            f"appid={APPID}\nfonte={fonte}\narquivo=\nepoch={quando}\n", encoding="utf-8"
        )
    return quando


def _sossegar(daemon: Any) -> None:
    le.armar_rematerializacao(daemon, motivo="teste", agora=0.0)
    le.rematerializar_se_sossegou(daemon, agora=le.JANELA_DE_SOSSEGO_SEC)


def _avisos(espiao: _Espiao) -> list[dict[str, Any]]:
    return [kw for nome, kw in espiao.eventos if nome == "launch_env_mudou_depois_do_exec"]


def test_as_17h33_o_servico_reiniciado_nao_acusa_o_que_o_jogo_nao_recebeu(
    lar: Path, espiao: _Espiao
) -> None:
    """O arme entrega sem cobertura; o serviço novo materializa com 0 físicos e vê 2 de 1 vpad."""
    _jogo_aberto(lar)
    antigo = _daemon(vpads=1, fisicos=3)
    le.materialize_launch_env(antigo)
    le.ambiente_do_lancamento(antigo, APPID)
    assert "launch_ambiente_entregue_sem_cobertura" in espiao.nomes()
    campos = espiao.campos("launch_ambiente_entregue_sem_cobertura")
    assert (campos["appid"], campos["vpads"], campos["fisicos"]) == (APPID, 1, 3)

    novo = _daemon(vpads=1, fisicos=0)
    le.materialize_launch_env(novo)
    _mesa_de(novo, vpads=1, fisicos=2)
    _sossegar(novo)

    assert _avisos(espiao) == [], "o aviso saiu sobre um recibo de antes de os controles voltarem"


def test_as_17h29_a_entrega_sem_cobertura_nao_passa_calada_pela_materializacao_do_meio(
    lar: Path, espiao: _Espiao
) -> None:
    """A mesa se recompõe com 3 vpads: o jogo ficou com a env sem IGNORE, e o aviso diz."""
    _jogo_aberto(lar)
    mesa = _daemon(vpads=1, fisicos=3)
    le.materialize_launch_env(mesa)
    le.ambiente_do_lancamento(mesa, APPID)
    _mesa_de(mesa, vpads=3, fisicos=3)
    le.materialize_launch_env(mesa)

    _sossegar(mesa)

    avisos = _avisos(espiao)
    assert len(avisos) == 1 and avisos[0]["appid"] == APPID
    assert avisos[0]["cobertura_entregue"] is False
    assert avisos[0]["cobertura_agora"] is True


@pytest.mark.parametrize(
    "fonte_velha", [None, "arquivo"], ids=["sem fonte", "fonte do jogo de antes"]
)
def test_as_17h29_com_a_fonte_chegando_depois_do_sossego_o_aviso_ainda_sai(
    lar: Path, espiao: _Espiao, fonte_velha: str | None
) -> None:
    """O wrapper grava o `fonte_do_ambiente` depois da resposta, e a folha o relê a cada 1 s.

    Os pads em voo nascem logo depois do arme e o sossego corre antes de a fonte chegar: ele volta a
    perguntar, e o aviso sai quando a fonte chega. Passado o prazo sem fonte, o sossego não se
    rearma.
    """
    epoch = _jogo_aberto(lar, fonte=None)
    if fonte_velha is not None:
        (lar / "fonte_do_ambiente").write_text(
            f"appid={APPID}\nfonte={fonte_velha}\narquivo=\nepoch={epoch - 600}\n",
            encoding="utf-8",
        )
    mesa = _daemon(vpads=1, fisicos=3)
    le.materialize_launch_env(mesa)
    le.ambiente_do_lancamento(mesa, APPID)
    _mesa_de(mesa, vpads=3, fisicos=3)
    le.materialize_launch_env(mesa)

    _sossegar(mesa)
    assert _avisos(espiao) == []
    prazo = mesa._launch_env_sossego_em
    assert prazo is not None, "o sossego desistiu antes de o wrapper dizer de onde veio a env"

    _jogo_aberto(lar, epoch=epoch)
    le.rematerializar_se_sossegou(mesa, agora=prazo)

    avisos = _avisos(espiao)
    assert len(avisos) == 1
    assert (avisos[0]["cobertura_entregue"], avisos[0]["cobertura_agora"]) == (False, True)


def test_sem_fonte_no_prazo_o_sossego_para_de_perguntar(lar: Path, espiao: _Espiao) -> None:
    _jogo_aberto(lar, fonte=None)
    mesa = _daemon(vpads=1, fisicos=3)
    le.ambiente_do_lancamento(mesa, APPID)
    _mesa_de(mesa, vpads=3, fisicos=3)

    _sossegar(mesa)
    assert mesa._launch_env_sossego_em is not None
    depois = le.JANELA_DE_SOSSEGO_SEC + le.PRAZO_DA_FONTE_DO_AMBIENTE_SEC + 1.0
    le.rematerializar_se_sossegou(mesa, agora=depois)

    assert mesa._launch_env_sossego_em is None
    assert _avisos(espiao) == []


@pytest.mark.parametrize("reiniciado", [False, True], ids=["mesmo processo", "serviço reiniciado"])
def test_a_entrega_coberta_que_perde_a_cobertura_com_o_jogo_vivo_avisa(
    lar: Path, espiao: _Espiao, reiniciado: bool
) -> None:
    _jogo_aberto(lar)
    mesa = _daemon(vpads=3, fisicos=3)
    le.materialize_launch_env(mesa)
    le.ambiente_do_lancamento(mesa, APPID)
    assert "launch_ambiente_entregue_sem_cobertura" not in espiao.nomes()
    if reiniciado:
        mesa = _daemon(vpads=3, fisicos=3)
        le.materialize_launch_env(mesa)
    mesa.controller.describe_controllers = lambda: [{"connected": True}] * 4

    _sossegar(mesa)

    avisos = _avisos(espiao)
    assert len(avisos) == 1
    assert avisos[0]["cobertura_entregue"] is True
    assert avisos[0]["cobertura_agora"] is False
    assert avisos[0]["fisicos"] == 4


def test_o_aviso_sai_uma_vez_por_mudanca_e_a_volta_ao_acordo_rearma(
    lar: Path, espiao: _Espiao
) -> None:
    _jogo_aberto(lar)
    mesa = _daemon(vpads=3, fisicos=3)
    le.materialize_launch_env(mesa)
    le.ambiente_do_lancamento(mesa, APPID)
    mesa.controller.describe_controllers = lambda: [{"connected": True}] * 4

    _sossegar(mesa)
    _sossegar(mesa)
    assert len(_avisos(espiao)) == 1

    mesa.controller.describe_controllers = lambda: [{"connected": True}] * 3
    _sossegar(mesa)
    mesa.controller.describe_controllers = lambda: [{"connected": True}] * 4
    _sossegar(mesa)
    assert len(_avisos(espiao)) == 2


@pytest.mark.parametrize(
    "caso", ["sem_registro", "epoch_de_outro_lancamento", "fonte_arquivo", "fonte_nenhuma",
             "sem_fonte"],
)
def test_sem_registro_da_sessao_nao_ha_aviso(lar: Path, espiao: _Espiao, caso: str) -> None:
    """A base não é a entrega: nenhum aviso, e «não sei» não vira «tinha cobertura»."""
    epoch = _jogo_aberto(lar)
    mesa = _daemon(vpads=3, fisicos=3)
    le.materialize_launch_env(mesa)
    le.ambiente_do_lancamento(mesa, APPID)
    if caso == "sem_registro":
        (lar / "entregue").unlink()
        mesa._launch_env_entregue = None
    elif caso == "epoch_de_outro_lancamento":
        _jogo_aberto(lar, epoch=epoch + 5)
    elif caso == "fonte_arquivo":
        _jogo_aberto(lar, epoch=epoch, fonte="arquivo")
    elif caso == "fonte_nenhuma":
        _jogo_aberto(lar, epoch=epoch, fonte="nenhuma")
    else:
        _jogo_aberto(lar, epoch=epoch, fonte=None)
    mesa.controller.describe_controllers = lambda: [{"connected": True}] * 4

    _sossegar(mesa)

    assert _avisos(espiao) == []


@pytest.mark.parametrize("lado", ["entrega", "mesa"])
def test_fisicos_zero_em_um_dos_lados_e_nao_sei(lar: Path, espiao: _Espiao, lado: str) -> None:
    _jogo_aberto(lar)
    if lado == "entrega":
        mesa = _daemon(vpads=1, fisicos=0)
        le.ambiente_do_lancamento(mesa, APPID)
        _mesa_de(mesa, vpads=1, fisicos=3)
    else:
        mesa = _daemon(vpads=1, fisicos=3)
        le.ambiente_do_lancamento(mesa, APPID)
        _mesa_de(mesa, vpads=1, fisicos=0)

    _sossegar(mesa)

    assert _avisos(espiao) == []


def test_co_op_desligado_com_dois_fisicos_e_um_vpad_nao_avisa_nada(
    lar: Path, espiao: _Espiao
) -> None:
    """WRAPPER-EM-TODOS-01: sem o co-op todos alimentam o mesmo vpad, e isso é a doutrina."""
    _jogo_aberto(lar)
    mesa = _daemon(vpads=1, fisicos=2, coop=False)
    le.materialize_launch_env(mesa)

    le.ambiente_do_lancamento(mesa, APPID)
    _sossegar(mesa)

    assert "launch_ambiente_entregue_sem_cobertura" not in espiao.nomes()
    assert _avisos(espiao) == []


@pytest.mark.parametrize("flavor", ["dualsense", "xbox", "nintendo"])
@pytest.mark.parametrize("fisicos", [2, 3, MAX_FISICOS])
def test_vale_para_toda_mascara_e_para_dois_tres_e_quatro_controles_no_cabo_e_no_radio(
    lar: Path, espiao: _Espiao, flavor: str, fisicos: int
) -> None:
    """A régua conta físicos, e não o transporte nem a máscara: a mesa mista é a de sempre."""
    _jogo_aberto(lar)
    mesa = _daemon(vpads=1, fisicos=fisicos, flavor=flavor)
    le.materialize_launch_env(mesa)
    le.ambiente_do_lancamento(mesa, APPID)
    assert espiao.campos("launch_ambiente_entregue_sem_cobertura")["fisicos"] == fisicos
    _mesa_de(mesa, vpads=fisicos, fisicos=fisicos)
    le.materialize_launch_env(mesa)

    _sossegar(mesa)

    avisos = _avisos(espiao)
    assert len(avisos) == 1
    assert (avisos[0]["cobertura_entregue"], avisos[0]["cobertura_agora"]) == (False, True)


def test_a_entrega_vai_ao_arquivo_e_volta_igual(lar: Path, espiao: _Espiao) -> None:
    epoch = _jogo_aberto(lar)
    mesa = _daemon(vpads=2, fisicos=3)

    le.ambiente_do_lancamento(mesa, APPID)

    assert le.read_a_entrega(lar) == le.EntregaDoAmbiente(APPID, epoch, False, 2, 3)
    assert le.read_a_fonte(lar) == (APPID, "daemon", epoch)


def test_a_entrega_de_outro_jogo_nao_vira_registro(lar: Path, espiao: _Espiao) -> None:
    _jogo_aberto(lar)
    mesa = _daemon(vpads=1, fisicos=3)

    le.ambiente_do_lancamento(mesa, APPID + 1)

    assert not (lar / "entregue").exists()
    assert "launch_ambiente_entregue_sem_cobertura" not in espiao.nomes()
