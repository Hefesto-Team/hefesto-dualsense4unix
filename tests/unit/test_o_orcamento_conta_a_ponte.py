"""O orçamento de ar conta PONTES, não soma entrada — AR-MEDIDO-01, R10 dela.

A entrada do controle é elástica; o que transborda um adaptador são as saídas
de ritmo fixo (a ponte de som 0x35 e a de vibração 0x32). As três palavras de
sempre passam a ler as pontes contra ``N_MAX_PONTES``, e os Hz que viajam são
os MEDIDOS. Nada aqui lê ``/sys`` de verdade: o ``HID_PHYS`` é dublê.

AS MORDIDAS, feitas em 23/09/2026 e devolvidas com md5 conferido:

* ``palavra_das_pontes`` com ``<=`` no lugar de ``<`` faz o adaptador com
  duas pontes dizer «Folgada» — ``test_as_tres_palavras_leem_as_pontes``
  reprova;
* ``HZ_DA_PONTE`` trocado sem tocar o CSV faz
  ``test_o_csv_e_as_constantes_sao_o_mesmo_numero`` reprovar nas duas
  linhas de ponte.
"""

from __future__ import annotations

import csv
import importlib
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import radio_da_mesa as rm
from hefesto_dualsense4unix.integrations.ar_do_adaptador import ArDoAdaptador

RAIZ = Path(__file__).resolve().parents[2]
CSV = RAIZ / "docs" / "data" / "orcamento-de-ar.csv"

ADAPTADOR_A = "aa:bb:cc:00:00:01"
ADAPTADOR_B = "aa:bb:cc:00:00:02"


def _controle(n: int, **extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "uniq": f"aabbcc0000{n:02x}",
        "transport": "bt",
        "connected": True,
    }
    base.update(extra)
    return base


def _sem_sysfs(_raiz: str) -> list[str]:
    raise AssertionError("o orçamento leu o sysfs com o adaptador já publicado")


# ---------------------------------------------------------------- pontes


def test_quatro_controles_com_ponte_num_adaptador_sao_4_de_2() -> None:
    controles = [
        _controle(n, adaptador=ADAPTADOR_A, ponte_do_radio=modo)
        for n, modo in ((1, "som"), (2, "som"), (3, "haptica"), (4, "som"))
    ]
    orcamento = rm.orcamento_por_adaptador(controles, listar=_sem_sysfs)
    a = orcamento[ADAPTADOR_A]
    assert len(a.pontes) == 4
    assert a.n_max == rm.N_MAX_PONTES == 2
    assert a.rotulo == rm.PALAVRA_CHEIA
    publicado = a.publicar()
    assert len(publicado["pontes"]) == 4 and publicado["n_max"] == 2
    assert {p["modo"] for p in publicado["pontes"]} == {"som", "haptica"}


@pytest.mark.parametrize(
    ("pontes", "palavra"),
    [(0, rm.PALAVRA_FOLGADA), (1, rm.PALAVRA_FOLGADA), (2, rm.PALAVRA_APERTADA),
     (3, rm.PALAVRA_CHEIA), (4, rm.PALAVRA_CHEIA)],
)
def test_as_tres_palavras_leem_as_pontes(pontes: int, palavra: str) -> None:
    assert rm.palavra_das_pontes(pontes) == palavra


def test_a_palavra_nao_soma_entrada() -> None:
    """Quatro controles SEM ponte no mesmo adaptador: Folgada, por mais Hz que tenham."""
    controles = [
        _controle(n, adaptador=ADAPTADOR_A, hz_movimento=150.0, hz_voz=100.0)
        for n in range(1, 5)
    ]
    a = rm.orcamento_por_adaptador(controles, listar=_sem_sysfs)[ADAPTADOR_A]
    assert a.pontes == ()
    assert a.rotulo == rm.PALAVRA_FOLGADA


def test_controle_desconectado_nao_ocupa_ponte() -> None:
    controles = [
        _controle(1, adaptador=ADAPTADOR_A, ponte_do_radio="som"),
        _controle(2, adaptador=ADAPTADOR_A, ponte_do_radio="som", connected=False),
    ]
    a = rm.orcamento_por_adaptador(controles, listar=_sem_sysfs)[ADAPTADOR_A]
    assert [c.uniq for c in a.controles] == ["aabbcc000001"]
    assert len(a.pontes) == 1 and a.rotulo == rm.PALAVRA_FOLGADA


def test_modo_de_ponte_desconhecido_nao_e_ponte() -> None:
    controles = [_controle(1, adaptador=ADAPTADOR_A, ponte_do_radio="mic")]
    a = rm.orcamento_por_adaptador(controles, listar=_sem_sysfs)[ADAPTADOR_A]
    assert a.pontes == ()
    assert a.controles[0].ponte is None


# ---------------------------------------------------------------- quem é de quem


def test_o_adaptador_ausente_sai_do_hid_phys() -> None:
    uevents = {
        "/sys/class/hidraw/hidraw3/device/uevent":
            f"HID_UNIQ=aa:bb:cc:00:00:01\nHID_PHYS={ADAPTADOR_B.upper()}\n",
    }
    orcamento = rm.orcamento_por_adaptador(
        [_controle(1, ponte_do_radio="som")],
        listar=lambda _raiz: ["hidraw3"],
        ler=lambda caminho: uevents.get(caminho, ""),
    )
    assert list(orcamento) == [ADAPTADOR_B]
    assert orcamento[ADAPTADOR_B].pontes == (("aabbcc000001", "som"),)


def test_cabo_fica_fora_e_radio_sem_endereco_e_nao_sei() -> None:
    controles = [
        _controle(1, transport="usb", adaptador=ADAPTADOR_A, ponte_do_radio="som"),
        _controle(2),
    ]
    orcamento = rm.orcamento_por_adaptador(
        controles, listar=lambda _raiz: [], ler=lambda _c: "")
    assert list(orcamento) == [rm.SEM_ADAPTADOR]
    assert [c.uniq for c in orcamento[rm.SEM_ADAPTADOR].controles] == ["aabbcc000002"]


def test_os_hz_viajam_como_vieram_e_o_torto_vira_nao_sei() -> None:
    controles = [
        _controle(1, adaptador=ADAPTADOR_A, hz_movimento=412.5, hz_voz=0.0),
        _controle(2, adaptador=ADAPTADOR_A, hz_movimento=True, hz_voz="100"),
    ]
    um, dois = rm.orcamento_por_adaptador(controles, listar=_sem_sysfs)[
        ADAPTADOR_A].controles
    assert (um.hz_movimento, um.hz_voz) == (412.5, 0.0)
    assert (dois.hz_movimento, dois.hz_voz) == (None, None)


# ---------------------------------------------------------------- o medidor


def test_o_adaptador_vazio_do_medidor_aparece_com_zero_pontes() -> None:
    ar = {ADAPTADOR_B: ArDoAdaptador(hci=1, endereco=ADAPTADOR_B, entrada_por_s=0.0,
                                     saida_por_s=0.0, conexoes=())}
    orcamento = rm.orcamento_por_adaptador([], ar=ar, listar=_sem_sysfs)
    b = orcamento[ADAPTADOR_B]
    assert b.controles == () and b.pontes == ()
    assert b.entrada_por_s == 0.0
    assert b.rotulo == rm.PALAVRA_FOLGADA


def test_o_nao_sei_do_medidor_passa_adiante() -> None:
    ar = {ADAPTADOR_A: ArDoAdaptador(hci=0, endereco=ADAPTADOR_A,
                                     motivo="o contador não andou com conexão de pé")}
    a = rm.orcamento_por_adaptador(
        [_controle(1, adaptador=ADAPTADOR_A)], ar=ar, listar=_sem_sysfs)[ADAPTADOR_A]
    assert a.entrada_por_s is None
    assert a.motivo_do_ar == "o contador não andou com conexão de pé"
    assert a.publicar()["entrada_por_s"] is None


def test_adaptador_que_o_medidor_nao_leu_diz_por_que() -> None:
    a = rm.orcamento_por_adaptador(
        [_controle(1, adaptador=ADAPTADOR_A)], ar={}, listar=_sem_sysfs)[ADAPTADOR_A]
    assert a.entrada_por_s is None and a.motivo_do_ar


def test_o_afh_do_adaptador_viaja_na_publicacao() -> None:
    orcamento = rm.orcamento_por_adaptador(
        [_controle(1, adaptador=ADAPTADOR_A)],
        canais_evitados={ADAPTADOR_A: (20, 21), ADAPTADOR_B: None},
        listar=_sem_sysfs,
    )
    assert orcamento[ADAPTADOR_A].publicar()["canais_evitados"] == [20, 21]
    assert orcamento[ADAPTADOR_B].publicar()["canais_evitados"] is None


def test_nada_publicado_carrega_palavra_de_culpa() -> None:
    controles = [_controle(n, adaptador=ADAPTADOR_A, ponte_do_radio="som")
                 for n in range(1, 4)]
    publicado = rm.orcamento_por_adaptador(controles, listar=_sem_sysfs)[
        ADAPTADOR_A].publicar()
    texto = f"{publicado['rotulo']} {publicado['motivo_do_ar']}".lower()
    assert not [p for p in rm.PALAVRAS_DE_CULPA if p in texto]


# ---------------------------------------------------------------- o CSV


def _linhas() -> list[dict[str, str]]:
    with CSV.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def test_o_csv_tem_uma_linha_por_consumidor_com_a_procedencia() -> None:
    linhas = _linhas()
    assert linhas, "o orçamento de ar sem nenhuma linha"
    for linha in linhas:
        assert linha["procedencia"].strip(), linha["consumidor"]
        assert linha["fonte"].strip(), linha["consumidor"]
        assert linha["o_que_nao_conta"].strip(), (
            f"{linha['consumidor']}: a coluna «o que NÃO conta» é o ponto do CSV")
    consumidores = {linha["consumidor"] for linha in linhas}
    assert {"ponte de som (0x35)", "ponte de vibração (0x32)",
            "pontes por adaptador (n_max)", "relatório de entrada (0x31)"} <= consumidores


def test_o_ritmo_da_ponte_e_o_que_a_bomba_manda() -> None:
    """``HZ_DA_PONTE`` pergunta ao DONO do ritmo, a bomba do rádio.

    A régua do CSV compara o CSV com a constante, que nasceram juntos: se a
    bomba passasse a mandar dois quadros por report (a camada do firmware do
    estudo de 23/09), as duas continuariam iguais entre si e erradas.
    """
    from hefesto_dualsense4unix.integrations import alto_falante_bt as bomba

    for arranjo in (bomba.ARRANJO_PADRAO, bomba.ARRANJO_HAPTICA_032):
        intervalo = arranjo.intervalo_de_envio_s
        assert intervalo is not None, arranjo.nome
        assert pytest.approx(1.0 / intervalo) == rm.HZ_DA_PONTE, arranjo.nome


def test_o_csv_e_as_constantes_sao_o_mesmo_numero() -> None:
    conferidas = 0
    for linha in _linhas():
        dono = linha["constante"].strip()
        if not dono:
            continue
        caminho, nome = dono.split("::")
        modulo = importlib.import_module(
            "hefesto_dualsense4unix." + caminho.removesuffix(".py").replace("/", "."))
        valor = getattr(modulo, nome)
        assert float(linha["numero"]) == float(valor), (
            f"{linha['consumidor']}: o CSV diz {linha['numero']} e {dono} diz {valor}")
        conferidas += 1
    assert conferidas >= 8


# ---------------------------------------------------------------- quem sabe das pontes


class _PonteDoSom:
    def __init__(self, de_pe: bool) -> None:
        self._de_pe = de_pe

    def esta_de_pe(self) -> bool:
        return self._de_pe


def test_as_pontes_de_pe_sao_o_efeito_e_nao_o_pedido() -> None:
    """A ponte sob demanda que desceu por silêncio não ocupa o ar."""
    from hefesto_dualsense4unix.daemon.subsystems.alto_falante import AltoFalanteSubsystem

    sub = AltoFalanteSubsystem()
    sub._pontes = {
        "aabbcc000001": _PonteDoSom(True),
        "aabbcc000002": _PonteDoSom(False),
        "aabbcc000003": _PonteDoSom(True),
        "aabbcc000004": _PonteDoSom(True),
    }
    sub._modo_da_ponte = {
        "aabbcc000001": "som",
        "aabbcc000002": "som",
        "aabbcc000003": "haptica",
        "aabbcc000004": "outro",
    }
    assert sub.pontes_de_pe() == {"aabbcc000001": "som", "aabbcc000003": "haptica"}


def test_ponte_que_levanta_ao_ser_perguntada_fica_de_fora() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.alto_falante import AltoFalanteSubsystem

    class _Quebrada:
        def esta_de_pe(self) -> bool:
            raise RuntimeError("fd sumiu")

    sub = AltoFalanteSubsystem()
    sub._pontes = {"aabbcc000001": _Quebrada()}
    sub._modo_da_ponte = {"aabbcc000001": "som"}
    assert sub.pontes_de_pe() == {}
