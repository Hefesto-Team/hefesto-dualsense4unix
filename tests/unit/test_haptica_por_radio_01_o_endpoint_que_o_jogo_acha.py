"""HAPTICA-POR-RADIO-01 (P3) — o endpoint que o produto publica por APARELHO.

O nó é o que fez o PRAGMATA aceitar mandar a vibração pelo rádio, medido em
18/09/2026: com ele, o jogo abriu `HiFi__Speaker__sink (float32le 4ch)`; a
mesma passada, com o `sysfs.path` errado por UM NÍVEL da árvore do USB, não
abriu nada.

Nenhuma régua daqui toca o servidor de som: o `pactl` é dublê e o sysfs é de
mentira.

**POR APARELHO DESDE 02/10/2026** (A-HAPTICA-E-POR-APARELHO-01): até 28/09 o
nó era um por controle no rádio, com o nome pelo rabo do endereço; de 28/09 a
02/10, um por lugar (P1 a P4); agora é um por DualSense, com o nome pela marca
do aparelho, que não é o endereço. As agulhas, o formato, a âncora e as aspas
são os mesmos.
"""

from __future__ import annotations


import pytest

from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from tests.unit import porta_de_mentira as porta


def _rabo_hex(uniq: str) -> str:
    """Os seis hex do rabo do endereço: a forma que os nomes levavam antes de 02/10/2026."""
    digitos = "".join(ch for ch in uniq.lower() if ch in "0123456789abcdef")
    return digitos[-6:]


_UNIQ = "aa:bb:cc:00:00:03"
_QUATRO = tuple(f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))


def _runner_que_grava(saida: str = "42\n"):
    chamadas: list[list[str]] = []

    def correr(argv: list[str]) -> str | None:
        chamadas.append(argv)
        return saida

    return correr, chamadas


@pytest.fixture
def ancora() -> eh.Ancora:
    """A porta USB virtual do pad do ``_UNIQ`` (TODO-PAD-TEM-PORTA-PROPRIA-01)."""
    resposta = eh.ancora_da_interface(porta.dar_porta(_UNIQ, 4))
    assert resposta is not None
    return resposta


def test_o_nome_tem_as_tres_agulhas_que_o_ge_procura() -> None:
    nome = eh.nome_do_endpoint(_UNIQ)
    for agulha in eh.AGULHAS:
        assert agulha in nome, agulha


def test_o_nome_cabe_no_limite_do_servidor() -> None:
    """`PA_NAME_MAX` é 128 com o `\\0`; acima disso o servidor recusa o nó."""
    assert all(0 < len(eh.nome_do_endpoint(u)) <= eh.MAX_NOME for u in _QUATRO)


def test_dois_aparelhos_nao_dividem_o_mesmo_nome() -> None:
    """Nome igual vira UM endpoint só (patch 0186) e a háptica troca de dono."""
    assert len({eh.nome_do_endpoint(u) for u in _QUATRO}) == len(_QUATRO)


def test_o_que_nao_da_identidade_nao_vira_no_anonimo() -> None:
    """Sem identidade, dois nós disputariam o mesmo endpoint: um número de lugar não é uma."""
    for fora in (0, 5, -1, True, None, "1", "", "path:"):
        assert eh.nome_do_endpoint(fora) == "", fora  # type: ignore[arg-type]
    for fora in (1, "LUGAR1", "000003", _rabo_hex(_UNIQ)):
        assert eh.nome_da_marca(fora) == "", fora  # type: ignore[arg-type]


def test_as_propriedades_sao_as_que_o_ge_le(ancora: eh.Ancora) -> None:
    props = eh.propriedades_do_endpoint(_UNIQ, ancora)
    assert "device.bus=usb" in props
    assert f"device.vendor.id={eh.VID_SONY}" in props
    assert f"device.product.id={eh.PID_DUALSENSE}" in props
    assert f"sysfs.path={ancora.declarado}" in props


def test_as_propriedades_vao_entre_aspas_duplas(ancora: eh.Ancora) -> None:
    """Sem as aspas o parser corta no primeiro ESPAÇO e só a primeira chega."""
    props = eh.propriedades_do_endpoint(_UNIQ, ancora)
    assert props.startswith('sink_properties="')
    assert props.endswith('"')
    assert " " in props[len('sink_properties="') : -1], "há mais de uma propriedade"


def test_o_no_nao_vira_a_saida_padrao_da_maquina(ancora: eh.Ancora) -> None:
    props = eh.propriedades_do_endpoint(_UNIQ, ancora)
    assert f"priority.session={eh.PRIORIDADE_DA_SESSAO}" in props
    assert eh.PRIORIDADE_DA_SESSAO == 0


def test_o_sysfs_path_declarado_e_o_filho_nao_a_ancora(ancora: eh.Ancora) -> None:
    """O Wine sobe ao PAI do caminho: declarar a âncora nua dá o hub raiz."""
    props = eh.propriedades_do_endpoint(_UNIQ, ancora)
    assert f"sysfs.path={ancora.syspath}\"" not in props
    assert ancora.declarado.startswith(ancora.syspath + "/")


def _o_load(chamadas: list[list[str]]) -> list[str]:
    """O `load-module` entre as chamadas — a consulta ao servidor vem antes."""
    return next(a for a in chamadas if a[:2] == ["pactl", "load-module"])


def test_o_no_sobe_com_quatro_canais_em_float32(ancora: eh.Ancora) -> None:
    correr, chamadas = _runner_que_grava()
    no = eh.EndpointDeHaptica(uniq=_UNIQ, ancora=ancora, runner=correr)
    assert no.iniciar() is True
    argv = _o_load(chamadas)
    assert "channels=4" in argv
    assert "format=float32le" in argv
    assert "rate=48000" in argv
    assert no.module_id == "42"


def test_subir_duas_vezes_nao_publica_dois(ancora: eh.Ancora) -> None:
    correr, chamadas = _runner_que_grava()
    no = eh.EndpointDeHaptica(uniq=_UNIQ, ancora=ancora, runner=correr)
    no.iniciar()
    no.iniciar()
    cargas = [a for a in chamadas if a[:2] == ["pactl", "load-module"]]
    assert len(cargas) == 1


def test_o_no_desce_pelo_id_que_ele_subiu(ancora: eh.Ancora) -> None:
    correr, chamadas = _runner_que_grava()
    no = eh.EndpointDeHaptica(uniq=_UNIQ, ancora=ancora, runner=correr)
    no.iniciar()
    no.parar()
    assert chamadas[-1] == ["pactl", "unload-module", "42"]
    assert no.module_id is None


def test_servidor_que_nao_responde_nao_vira_no_de_mentira(ancora: eh.Ancora) -> None:
    no = eh.EndpointDeHaptica(uniq=_UNIQ, ancora=ancora, runner=lambda _a: None)
    assert no.iniciar() is False
    assert no.module_id is None


def test_o_monitor_e_de_onde_a_ponte_le(ancora: eh.Ancora) -> None:
    no = eh.EndpointDeHaptica(uniq=_UNIQ, ancora=ancora, runner=lambda _a: "1\n")
    assert no.monitor == no.nome + ".monitor"
