"""A-MIRA-POR-MOVIMENTO-NA-TELA-02 — as três respostas dela sobre a Mira Virtual.

Ela respondeu na página da sessão dos desenhos, em 24/09/2026 às 03h14
(`D-2409-*` no `docs/data/decisoes-dela.csv`):

1. **a dica do Giroscópio muda com a Mira acesa** — «Com a Mira Virtual acesa,
   o giro deste controle vai ao jogo pelo analógico direito.»; apagada, a de
   hoje. Por controle;
2. **no Modo Nativo o chip fica cinza e não grava** — *"A exceção do nativo
   todo o resto deve ter mira Virtual"*. A guarda mora no daemon (`mira.set`
   recusa), não só na tela; e em todo outro modo e caminho a Mira funciona,
   no cabo e no BT, do P1 ao P4;  <!-- noqa-acento: citação literal dela -->
3. **«Só enquanto eu segurar» e «Inverter» entram na tela**, no bloco da Mira
   da Calibrar, por controle, nascendo desligados.

Cada seção abaixo é uma resposta, e cada régua diz a MORDIDA: o que arrancar
para vê-la reprovar.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``), nunca um OUI real.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)
from tests.unit.test_a_mira_por_movimento_na_tela import (
    _P2,
    _P3,
    _P4,
    _servidor_com_perfil,
)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    """O `REGISTRO` dos sensores é do processo: nada desta régua vaza dele."""
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o mesmo molde da régua da A-MIRA-01."""
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


def _mira_set(servidor: IpcServer, **params: Any) -> dict[str, Any]:
    return asyncio.run(servidor._handlers["mira.set"](params))


# ---------------------------------------------------------------------------
# 2. O NATIVO — o chip não grava, e a guarda mora no daemon
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ligada", [True, False])
def test_no_nativo_o_mira_set_recusa_o_chip_sem_escrever_nada(
    perfis: Path, tmp_path: Path, ligada: bool
) -> None:
    """`D-2409-NO-NATIVO-A-MIRA-FICA-CINZA`: o chip não grava no Nativo — nem
    para acender, nem para apagar —, e a recusa não deixa rastro no disco nem
    no vivo.

    MORDIDA: tire a guarda `if nativo and "ligada" in params` do
    `_handle_mira_set` e este teste reprova — o chip voltaria a gravar e
    avisar, que é a opção que ela recusou.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    servidor.daemon._native_mode = True
    corpo = _mira_set(servidor, uniq=_P3, ligada=ligada)
    assert corpo["status"] == "nativo", corpo
    assert corpo["uniq"] == _P3 and corpo["motivo"]
    assert not load_profile("Bancada").controllers, "a recusa gravou no perfil"
    assert not rot.por_peca(servidor.store), "a recusa mexeu no vivo"
    assert not REGISTRO.roteado(_P3)


def test_no_nativo_a_recusa_leva_o_pedido_inteiro(perfis: Path, tmp_path: Path) -> None:
    """Chip e ajuste no mesmo pedido: nada grava. Uma resposta que diz
    «recusei» com metade escrita seria a tela mentindo pela metade.

    MORDIDA: mova a guarda para depois do `save_profile` e este teste reprova.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    servidor.daemon._native_mode = True
    corpo = _mira_set(servidor, uniq=_P2, ligada=True, sensibilidade=9)
    assert corpo["status"] == "nativo"
    assert not load_profile("Bancada").controllers


def test_no_nativo_os_ajustes_da_calibrar_continuam_gravando(
    perfis: Path, tmp_path: Path
) -> None:
    """Os ajustes não acendem mira nenhuma: gravam, e valem quando o modo
    voltar. Escolha pelo padrão dela (a que custa menos a quem joga): ela
    pode deixar a Calibrar pronta no Nativo.

    MORDIDA: recuse qualquer campo no Nativo e este teste reprova.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    servidor.daemon._native_mode = True
    corpo = _mira_set(servidor, uniq=_P2, zona_morta_graus_s=24.0,
                      inverter_vertical=True, gatilho="l2")
    assert corpo["status"] == "ok" and corpo["ligada"] is False, corpo
    assert corpo["alcance"] == {"tique": "nao_se_aplica"}
    dele = load_profile("Bancada").controllers["aabbcc000002"].movimento
    assert (dele.zona_morta_graus_s, dele.inverter_vertical, dele.gatilho) == (
        24.0, True, "l2")
    assert "destino" not in dele.model_fields_set, (
        "o ajuste no Nativo escreveu o destino — a peça deixaria de seguir o perfil")


def test_fora_do_nativo_o_chip_grava(perfis: Path, tmp_path: Path) -> None:
    """O controle da guarda: o MESMO pedido, sem o Nativo, grava. Sem este
    caso a régua de cima passaria com um `mira.set` que recusa sempre."""
    servidor = _servidor_com_perfil(tmp_path)
    corpo = _mira_set(servidor, uniq=_P3, ligada=True)
    assert corpo["status"] == "ok" and corpo["ligada"] is True
    assert corpo["alcance"] == {"tique": "aplicado"} and corpo["ressalva"] is None


# ---------------------------------------------------------------------------
# 3. «SÓ ENQUANTO EU SEGURAR» E «INVERTER» — o IPC abre a porta que a tela tem
# ---------------------------------------------------------------------------


def test_o_gatilho_e_o_inverter_chegam_ao_disco_e_ao_vivo(
    perfis: Path, tmp_path: Path
) -> None:
    """Os três campos novos gravam NA PEÇA, só o que ela mexeu, e valem no
    próximo tique.

    MORDIDA: tire `gatilho` de `_CAMPOS_DA_MIRA` e este teste reprova com a
    recusa de chave desconhecida.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    _mira_set(servidor, uniq=_P4, ligada=True)
    corpo = _mira_set(servidor, uniq=_P4, gatilho="l2")
    assert corpo["status"] == "ok" and corpo["gatilho"] == "l2"
    corpo = _mira_set(servidor, uniq=_P4, inverter_horizontal=True)
    assert corpo["inverter_horizontal"] is True and corpo["inverter_vertical"] is False
    dele = load_profile("Bancada").controllers["aabbcc000004"].movimento
    assert dele.model_fields_set == {"destino", "gatilho", "inverter_horizontal"}
    vivo = rot.da_peca(servidor.store, _P4, rot.ativo(servidor.store))
    assert vivo is not None and (vivo.gatilho, vivo.inverter_horizontal) == ("l2", True)


def test_sempre_devolve_a_mira_sem_botao(perfis: Path, tmp_path: Path) -> None:
    """A opção «Sempre» manda `null` (a lista manda `""`): a peça volta a mirar
    sem botão, COM opinião — o gatilho do perfil não volta por baixo.

    MORDIDA: trate o `""` como campo omitido e este teste reprova.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    perfil = Profile(
        name="Bancada", match=MatchAny(type="any"),
        movimento=ProfileMovimentoConfig(destino="analogico_direito", gatilho="r1"),
    )
    servidor = _servidor_com_perfil(tmp_path, perfil)
    for vazio in ("", None):
        corpo = _mira_set(servidor, uniq=_P2, gatilho=vazio)
        assert corpo["status"] == "ok" and corpo["gatilho"] is None, (vazio, corpo)
        vivo = rot.da_peca(servidor.store, _P2, rot.ativo(servidor.store))
        assert vivo is not None and vivo.gatilho is None


@pytest.mark.parametrize("torto", ["ps", "touchpad", "l3_direcao", 7])
def test_o_ps_e_o_que_nao_e_botao_sao_recusados(
    perfis: Path, tmp_path: Path, torto: Any
) -> None:
    """O PS é a saída de emergência dela e nunca vira gatilho; o que não chega
    ao jogo como botão também não. Nada grava.

    MORDIDA: tire o validador de `ProfileMovimentoConfig.gatilho` e o caso
    `ps` reprova.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    with pytest.raises(ValueError, match="gatilho"):
        _mira_set(servidor, uniq=_P3, gatilho=torto)
    assert not load_profile("Bancada").controllers, "a recusa gravou alguma coisa"


@pytest.mark.parametrize("torto", ["sim", 1, None])
def test_o_inverter_e_boolean(perfis: Path, tmp_path: Path, torto: Any) -> None:
    """Um `1` ou um `"sim"` não viram `True` calados."""
    servidor = _servidor_com_perfil(tmp_path)
    with pytest.raises(ValueError, match="inverter_vertical"):
        _mira_set(servidor, uniq=_P3, inverter_vertical=torto)


def test_a_leitura_de_volta_traz_os_tres(perfis: Path, tmp_path: Path) -> None:
    """O `state_full` publica o gatilho e os dois inverter de cada peça — é
    deles que o bloco da Calibrar pinta, e com a mira APAGADA também.

    MORDIDA: tire `gatilho` do `_merge_mira` e este teste reprova.
    """
    servidor = _servidor_com_perfil(tmp_path)
    _mira_set(servidor, uniq=_P3, gatilho="square", inverter_vertical=True)
    entradas: list[dict[str, Any]] = [{"uniq": _P2}, {"uniq": _P3}]
    servidor._merge_mira(entradas)
    assert entradas[0]["mira"]["gatilho"] is None
    assert entradas[0]["mira"]["inverter_horizontal"] is False
    assert entradas[1]["mira"]["ligada"] is False
    assert entradas[1]["mira"]["gatilho"] == "square"
    assert entradas[1]["mira"]["inverter_vertical"] is True
