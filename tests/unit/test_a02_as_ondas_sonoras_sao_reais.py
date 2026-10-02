"""As ondas sonoras da aba 02 mostram ÁUDIO, e não o desenho."""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import ondas_de_som
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import (
    ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE,
)
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

PAGINA = "02-controles.html"


class _FluxoDeMentira:
    """Um `parec` de mentira: um par de fds em que o teste escreve os picos."""

    def __init__(self) -> None:
        import os

        self._r, self._w = os.pipe()
        self.parado = False

    @property
    def fd(self) -> int:
        return self._r

    def vivo(self) -> bool:
        return not self.parado

    def parar(self) -> None:
        import contextlib
        import os

        self.parado = True
        for fd in (self._r, self._w):
            with contextlib.suppress(OSError):
                os.close(fd)

    def manda(self, *picos: float) -> None:
        import os

        os.write(self._w, b"".join(struct.pack("<f", p) for p in picos))


@pytest.fixture
def medidor() -> Any:
    """Um medidor com relógio e fluxo nas mãos do teste — zero `parec`."""
    fluxos: dict[str, _FluxoDeMentira] = {}
    relogio = [1000.0]

    def abrir(no: str, uniq: str) -> _FluxoDeMentira:
        fluxos[no] = _FluxoDeMentira()
        return fluxos[no]

    m = ondas_de_som.OndasDeSom(
        abrir=abrir, agora=lambda: relogio[0], automatico=False
    )
    ondas_de_som.ligar(True)
    try:
        yield m, fluxos, relogio
    finally:
        m.parar()
        ondas_de_som.ligar(False)


def test_o_medidor_traduz_o_pico_em_altura(medidor: Any) -> None:
    """Um pico medido vira uma barra mais alta que o piso."""
    m, fluxos, _ = medidor
    m.seguir({"no": "uniq"})
    m.bombear(timeout_s=0)
    fluxos["no"].manda(*([0.0] * 14))
    m.bombear(timeout_s=0.2)
    silencio = m.alturas("no")
    assert silencio == tuple([ondas_de_som.PISO_PCT] * 14), silencio

    fluxos["no"].manda(*([ondas_de_som.PICO_CHEIO] * 14))
    m.bombear(timeout_s=0.2)
    cheio = m.alturas("no")
    assert cheio == tuple([100] * 14), cheio

    fluxos["no"].manda(*([ondas_de_som.PICO_CHEIO / 2] * 14))
    m.bombear(timeout_s=0.2)
    meio = m.alturas("no")
    assert meio is not None
    assert ondas_de_som.PISO_PCT < meio[0] < 100, meio


def test_o_medidor_desligado_nao_abre_nada() -> None:
    """Com o módulo desligado nenhum fluxo nasce — é a trava da suíte."""
    abriu: list[str] = []

    def abrir(no: str, uniq: str) -> None:
        abriu.append(no)
        return None

    ondas_de_som.ligar(False)
    m = ondas_de_som.OndasDeSom(abrir=abrir, automatico=False)
    m.seguir({"no": "uniq"})
    m.bombear(timeout_s=0)
    assert abriu == [], abriu
    assert m.alturas("no") is None


def test_sem_leitura_nunca_vira_silencio(medidor: Any) -> None:
    """Nó pedido e sem amostra responde ``None`` — nunca uma fila de zeros."""
    m, fluxos, relogio = medidor
    m.seguir({"no": "uniq"})
    m.bombear(timeout_s=0)
    assert m.alturas("no") is None, "fluxo recém-aberto ainda não mediu nada"

    fluxos["no"].manda(*([0.3] * 14))
    m.bombear(timeout_s=0.2)
    assert m.alturas("no") is not None

    relogio[0] += ondas_de_som.MUDEZ_S + 1.0
    assert m.alturas("no") is None


def test_o_que_sai_da_lista_e_fechado(medidor: Any) -> None:
    """`seguir` sem um nó fecha o fluxo dele no mesmo instante."""
    m, fluxos, _ = medidor
    m.seguir({"a": "u", "b": "u"})
    m.bombear(timeout_s=0)
    assert not fluxos["a"].parado and not fluxos["b"].parado
    m.seguir({"a": "u"})
    m.bombear(timeout_s=0)
    assert fluxos["b"].parado, "o nó que saiu da lista continuou aberto"
    assert not fluxos["a"].parado


def _publicado() -> str:
    return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")


def test_cada_barrinha_tem_endereco_e_o_alvo_altura() -> None:
    """As catorze barras de cada medidor são endereçáveis, com o alvo certo."""
    doc = _publicado()
    for lado in (a02.LADO_MIC, a02.LADO_ALTO):
        for i in range(ondas_de_som.BARRAS):
            alvo = f'data-campo="{lado}-onda-{i}" data-hef-alvo="altura"'
            assert alvo in doc, f"a página publicada não tem {alvo}"
        assert f'data-campo="{lado}-onda-lida"' in doc


def test_o_selo_da_leitura_acende_a_classe_sem_leitura() -> None:
    """O contêiner sabe dizer "não medi", e a folha sabe desenhar isso."""
    doc = _publicado()
    assert 'data-hef-classe="sem-leitura"' in doc
    assert 'data-hef-quando="nao"' in doc
    assert re.search(r"\.onda\.sem-leitura i\{[^}]*height:16% !important", doc), (
        "a folha não achata a onda sem leitura"
    )


def test_o_lugar_vazio_nao_mostra_onda_do_desenho() -> None:
    """Um assento sem controle não desenha onda sonora nenhuma.

    O molde do lugar vazio NÃO escreve nas barras (`altura` está em
    `ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE`), então quem apaga é a folha — a mesma
    cura, e a mesma regra, que a barra de bateria já usa.

    MORDE: apagar a regra `.ctl[data-conectado="nao"] .onda i` faz o P2 vazio
    exibir a onda cheia do desenho.
    """
    doc = _publicado()
    assert re.search(
        r'\.ctl\[data-conectado="nao"\] \.onda i\{[^}]*height:16% !important', doc
    ), "o lugar vazio continua com a onda do desenho"


def test_altura_esta_entre_os_alvos_que_o_travessao_nao_atende() -> None:
    """`altura` sofre a MESMA recusa do CSSOM que tirou `largura` do molde."""
    assert "altura" in ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE


def test_sem_leitura_emite_o_piso_e_nunca_o_vazio() -> None:
    """Sem medição as catorze saem no PISO, e o selo diz que não leu."""
    campos = a02.campos_da_onda(a02.LADO_MIC, None)
    assert campos["mic-onda-lida"] == "nao"  # (noqa-acento) valor de atributo
    for i in range(ondas_de_som.BARRAS):
        valor = campos[f"mic-onda-{i}"]
        assert valor == ondas_de_som.PISO_PCT, (
            f"mic-onda-{i} saiu {valor!r} — o vazio vira '—%', que o CSSOM "
            "descarta, e a altura do DESENHO fica no atributo"
        )


def test_com_leitura_o_selo_diz_sim_e_as_alturas_passam() -> None:
    """Medido é medido: as catorze alturas chegam como vieram."""
    lidas = tuple(range(16, 16 + ondas_de_som.BARRAS))
    campos = a02.campos_da_onda(a02.LADO_ALTO, lidas)
    assert campos["alto-onda-lida"] == "sim"
    assert tuple(campos[f"alto-onda-{i}"] for i in range(len(lidas))) == lidas


def test_o_alto_falante_mudo_achata_a_onda_sem_apagar_a_leitura() -> None:
    """Com o alto-falante mudo no firmware, a onda vai ao piso — e o selo fica."""
    lidas = tuple([90] * ondas_de_som.BARRAS)
    campos = a02.campos_da_onda(a02.LADO_ALTO, lidas, mudo=True)
    assert campos["alto-onda-lida"] == "sim"
    assert all(
        campos[f"alto-onda-{i}"] == ondas_de_som.PISO_PCT
        for i in range(ondas_de_som.BARRAS)
    ), campos


def test_o_no_de_saida_e_o_monitor_do_sink_do_controle(monkeypatch: Any) -> None:
    """"O que sai" mora no `.monitor` do sink — e o sink tem dono."""
    class _Lida:
        sink_do_controle = "alsa_output.um_sink"

    monkeypatch.setitem(a02._CAMADA_1, "uniq", _Lida())
    assert a02.no_do_alto_falante("uniq") == "alsa_output.um_sink.monitor"
    assert a02.no_do_alto_falante("outro") == "", "sem camada 1 lida, não se sabe"


def test_o_no_de_entrada_vem_do_daemon_e_nao_e_inventado() -> None:
    """O nó do microfone é o que o daemon publica — ou nada."""
    com = {"audio": {"canal_fonte": "alsa_input.um_mic"}}
    assert a02.no_do_microfone(com) == "alsa_input.um_mic"
    assert a02.no_do_microfone({"audio": {}}) == ""
    assert a02.no_do_microfone({}) == ""


def test_o_gerador_sem_lado_continua_sem_endereco() -> None:
    """A peça `onda()` sem `lado` é o desenho puro — nada de endereço."""
    import importlib.util

    caminho = (
        Path(__file__).resolve().parents[2]
        / "src/hefesto_dualsense4unix/interface/aba02.py"
    )
    spec = importlib.util.spec_from_file_location("_aba02_para_o_teste", caminho)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert "data-campo" not in mod.onda([50, 60])
    assert 'data-campo="mic-onda-0"' in mod.onda([50, 60], lado="mic")
