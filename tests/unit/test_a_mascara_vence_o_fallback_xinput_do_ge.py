"""A máscara vence o fallback XInput do GE: o lançamento nunca põe o fallback às cegas.

A-MASCARA-VENCE-O-FALLBACK-XINPUT-DO-GE-01. O script do GE põe o fallback com `setdefault`: a
lista por appid o desliga nos jogos em que ele dobra a vaga, e o resto fica com o `1`. Pôr a
variável no lançamento calaria os dois. Enquanto a rodada não mede o caso (a), o lançamento não
compõe o `PROTON_SONY_AUTO_XINPUT` em máscara, número de pads ou mesa mista nenhuma
(D-1610-O-AUTO-XINPUT-FICA-FORA-DA-ALLOWLIST).
O modelo do caso (b) executa as linhas do script do 11-12 sobre o ambiente do lançamento.

A MORDIDA: `compose_env` pondo `PROTON_SONY_AUTO_XINPUT=0` em toda máscara fora do Xbox tira o
controle do jogo só XInput com a máscara DualSense, e `test_o_jogo_so_xinput_ve_o_controle`
reprova; pondo `1`, cala a lista por appid, e `test_a_lista_por_appid_do_ge_continua_valendo`
reprova.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le

ENV = "PROTON_SONY_AUTO_XINPUT"
JOGO_DA_LISTA = "3564740"
JOGO_QUALQUER = "9931993"

SCRIPT_DO_11_12 = '''
class Session:
    def setup(self, appid):
        if appid in [
                "1580240",
                "3564740",
                ]:
            self.env.setdefault("PROTON_SONY_AUTO_XINPUT", "0")

    def init_session(self):
        self.env.setdefault("PROTON_SONY_AUTO_XINPUT", "1")
'''

MASCARAS = [("dualsense", "uhid"), ("dualsense", "uinput"), ("xbox", "uinput"),
            ("nintendo", "uinput")]


def _o_que_o_script_deixa(env: dict[str, str], appid: str) -> dict[str, str]:
    escopo: dict[str, Any] = {}
    exec(SCRIPT_DO_11_12, escopo)
    sessao = escopo["Session"].__new__(escopo["Session"])
    sessao.env = dict(env)
    sessao.setup(appid)
    sessao.init_session()
    return dict(sessao.env)


def _env(mascara: str, backends: list[str], fisicos: int) -> dict[str, str]:
    return le.compose_env(native_mode=False, emulation_enabled=True, flavor=mascara,
                          backends=backends, fisicos=fisicos)


def _mesas() -> list[tuple[str, list[str], int]]:
    mesas = []
    for (mascara, backend), pads in itertools.product(MASCARAS, (1, 4)):
        mesas.append((mascara, [backend] * pads, pads))
    mesas.append(("dualsense", ["uhid", "uinput", "uhid", "uinput"], 4))
    mesas.append(("dualsense", ["uhid", "uhid"], 1))
    return mesas


def _jogo_so_xinput_ve(mascara: str, backend: str, env: dict[str, str]) -> bool:
    """O pad Sony do uhid só chega ao jogo só XInput pelo fallback; o resto já é XInput."""
    if mascara == "dualsense" and backend == "uhid":
        return env.get(ENV) == "1"
    return True


@pytest.mark.parametrize(("mascara", "backends", "fisicos"), _mesas())
def test_o_lancamento_nunca_poe_o_fallback(mascara: str, backends: list[str], fisicos: int) -> None:
    assert ENV not in _env(mascara, backends, fisicos)
    assert ENV not in le.ENV_ALLOWLIST


@pytest.mark.parametrize(("mascara", "backends", "fisicos"), _mesas())
def test_o_jogo_so_xinput_ve_o_controle(mascara: str, backends: list[str], fisicos: int) -> None:
    depois = _o_que_o_script_deixa(_env(mascara, backends, fisicos), JOGO_QUALQUER)
    assert all(_jogo_so_xinput_ve(mascara, b, depois) for b in backends), depois.get(ENV)


@pytest.mark.parametrize(("mascara", "backends", "fisicos"), _mesas())
def test_a_lista_por_appid_do_ge_continua_valendo(
    mascara: str, backends: list[str], fisicos: int
) -> None:
    assert _o_que_o_script_deixa(_env(mascara, backends, fisicos), JOGO_DA_LISTA)[ENV] == "0"


def test_a_opcao_por_jogo_sobrepoe_o_padrao_do_ge() -> None:
    env = {**_env("dualsense", ["uhid"], 1), ENV: "0"}
    assert _o_que_o_script_deixa(env, JOGO_QUALQUER)[ENV] == "0"


CABECALHO_DO_RECIBO = "versão,sha256,ficha,rodada,veredito,prova,data,runtime\n"
LINHAS_DO_RECIBO = {
    "sem_rodada": "",
    "nao_medida": "GE-Proton11-12,a,passou,não medida: 24 de 24 pernas (x),não medida,,d,1\n",
    "ficha_antes": "GE-Proton11-12,a,reprovou: winebus,não rodou,reprovou,winebus,d,\n",
    "rodada_reprovou": "GE-Proton11-12,a,passou,1vpad-cabo-dualsense-x11: gatilho,reprovou,"
                       "1vpad-cabo-dualsense-x11: gatilho,d,1\n",
}


def _a_casa_do_atualizador(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recibo: str
) -> Path:
    from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
    from hefesto_dualsense4unix.integrations import proton_pin as pp
    from hefesto_dualsense4unix.integrations import qualificar_proton as qp
    from tests.unit.test_o_proton_se_atualiza_sozinho import VELHA, _proton_de_mentira

    monkeypatch.setattr(pp, "_steam_gate", lambda: None)
    monkeypatch.setattr(censo, "proton_em_uso",
                        lambda *a, **k: censo.ProtonEmUso(frozenset(), ()))
    monkeypatch.setattr(censo, "casas_do_heroic", lambda *a, **k: ((), ()))
    arquivo = tmp_path / "recibo.csv"
    arquivo.write_text(CABECALHO_DO_RECIBO + recibo, encoding="utf-8")
    monkeypatch.setattr(qp, "caminho_do_recibo", lambda *_a, **_k: arquivo)
    lar = tmp_path / "casa"
    _proton_de_mentira(lar / ".steam" / "steam" / "compatibilitytools.d" / VELHA)
    (lar / ".steam" / "steam" / "steamapps").mkdir()
    return lar


@pytest.mark.parametrize(
    ("recibo", "vale_a_nova"),
    [("sem_rodada", True), ("nao_medida", True), ("ficha_antes", True),
     ("rodada_reprovou", False)],
)
def test_so_a_rodada_que_rodou_e_reprovou_veta_a_subida(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recibo: str, vale_a_nova: bool
) -> None:
    """D-0811-A-RODADA-QUE-REPROVOU-VETA-A-VERSAO."""
    from hefesto_dualsense4unix.integrations import proton_pin as pp
    from tests.unit.test_o_proton_se_atualiza_sozinho import (
        CONF,
        NOVA,
        VELHA,
        _atualizar,
        _compat,
        _Rede,
        _rede,
        _tarball,
    )

    lar = _a_casa_do_atualizador(tmp_path, monkeypatch, LINHAS_DO_RECIBO[recibo])
    _baixada, instalada = _atualizar(lar, _Rede(_rede(_tarball(tmp_path))))
    if vale_a_nova:
        assert instalada.estado == "instalada", instalada
        assert pp.pino_que_vale(CONF, _compat(lar)) == NOVA
    else:
        assert instalada.estado == "reprovou" and "a rodada reprovou" in instalada.detalhe
        assert not (_compat(lar) / NOVA).exists()
        assert pp.pino_que_vale(CONF, _compat(lar)) == VELHA


def test_a_nova_instalada_a_mao_que_a_rodada_reprovou_nao_vira_o_pino(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.integrations import proton_pin as pp
    from tests.unit.test_o_proton_se_atualiza_sozinho import CONF, NOVA, VELHA, _compat

    lar = _a_casa_do_atualizador(tmp_path, monkeypatch, LINHAS_DO_RECIBO["rodada_reprovou"])
    from tests.unit.test_o_proton_novo_so_entra_se_passar import _proton_de_mentira

    _proton_de_mentira(_compat(lar) / NOVA)
    assert pp.pino_que_vale(CONF, _compat(lar)) == VELHA
