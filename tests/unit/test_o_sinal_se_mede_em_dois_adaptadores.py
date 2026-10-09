"""O-SINAL-SE-MEDE-EM-DOIS-ADAPTADORES-01: o enlace e a varredura, lado a lado, em dois adaptadores.

O ensaio ``scripts/ensaios/o_sinal_em_dois_adaptadores.py`` grava, por segundo, o RSSI da
varredura em A e em B e o do enlace em A, sem endereço, e recusa com o daemon no ar. A conta lê
as sessões gravadas (``tests/fixtures/o_sinal_em_dois_adaptadores/``, sintéticas até a bancada
rodar) e diz se as constantes do sinal valem: a faixa ideal, a conversão entre as réguas e a margem
do Equilibrar. As constantes não mudam nesta sprint; a régua cobra quando a sessão gravada chegar.

MORDIDAS (arrancar, ver reprovar, devolver):

1. Tirar a recusa do daemon no ar (``recusas``) reprova o ``test_1``.
2. Gravar o endereço no lugar do rótulo (``Rotulos.de`` devolvendo a chave) reprova o ``test_2``.
3. Tirar do ``conferir`` a pergunta da faixa ideal reprova o ``test_4``.
4. Tirar do ``conferir`` a conta da margem reprova o ``test_6``.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from hefesto_dualsense4unix.integrations import plano_de_radio as pr
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ / "tests" / "fixtures" / "o_sinal_em_dois_adaptadores"

CONTROLE_1 = "aa:bb:cc:00:00:01"
CONTROLE_2 = "aa:bb:cc:00:00:02"


def _carregar() -> ModuleType:
    caminho = RAIZ / "scripts" / "ensaios" / "o_sinal_em_dois_adaptadores.py"
    spec = importlib.util.spec_from_file_location("_o_sinal_em_dois_adaptadores", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


sinal = _carregar()


class _Mundo:
    """As portas em dublê: duas varreduras e um enlace que mudam a cada segundo."""

    def __init__(self, *, daemon: bool = False, enlace: bool = True) -> None:
        self.daemon = daemon
        self.com_enlace = enlace
        self.abertos: list[tuple[str, str, int]] = []
        self.fechou = False
        self.segundo = 0

    def portas(self) -> object:
        return sinal.Portas(
            daemon_no_ar=lambda: self.daemon,
            modelo=lambda hci: {"hci0": "usb 0a12:0001", "hci1": "usb 8087:0029"}[hci],
            abrir=lambda a, b, fase: self.abertos.append((a, b, fase)),
            ler=self.ler, fechar=self.fechar, dormir=lambda _s: None, hora=lambda: "10:00:00",
        )

    def ler(self) -> object:
        self.segundo += 1
        enlace = ({CONTROLE_1.upper(): -40 - self.segundo, CONTROLE_2: -30}
                  if self.com_enlace else {})
        return sinal.Leitura(
            varredura={"A": {CONTROLE_1: -41}, "B": {CONTROLE_1: -39 - self.segundo}},
            enlace=enlace)

    def fechar(self) -> None:
        self.fechou = True


# --------------------------------------------------------------- as recusas


def test_1_recusa_com_o_daemon_no_ar_sem_medir_e_sem_enlace(tmp_path: Path) -> None:
    saida = tmp_path / "s.jsonl"
    mundo = _Mundo(daemon=True)
    pedido = sinal.Pedido(medir=True, fase=1, a="hci0", b="hci1")
    assert sinal.gravar(mundo.portas(), pedido, distancia="1 m", segundos=3, saida=saida) == 2
    assert not saida.exists() and not mundo.abertos, "com o daemon no ar, nada abre"
    assert sinal.RECUSA_DAEMON in sinal.recusas(pedido, daemon_no_ar=lambda: True)
    assert sinal.RECUSA_SEM_MEDIR in sinal.recusas(
        sinal.Pedido(medir=False, fase=1, a="hci0", b="hci1"), daemon_no_ar=lambda: False)
    assert sinal.RECUSA_MESMO_ADAPTADOR in sinal.recusas(
        sinal.Pedido(medir=True, fase=1, a="hci0", b="hci0"), daemon_no_ar=lambda: False)
    no_cabo = _Mundo(enlace=False)
    assert sinal.gravar(no_cabo.portas(), sinal.Pedido(True, 2, "hci0", "hci1"),
                        distancia="1 m", segundos=3, saida=saida) == 2
    assert no_cabo.fechou and not saida.exists(), "no cabo o ensaio nem arma, e fecha a busca"


def test_1b_sem_medir_a_linha_de_comando_nao_abre_nada(capsys: pytest.CaptureFixture[str],
                                                        tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    def _proibido(_nome: str) -> object:
        raise AssertionError("abriu as portas sem --medir")

    monkeypatch.setattr(sinal, "portas_de_verdade", _proibido)
    rc = sinal.main(["gravar", "--fase", "1", "--distancia", "1 m", "--saida",
                     str(tmp_path / "s.jsonl")])
    assert rc == 2 and sinal.RECUSA_SEM_MEDIR in capsys.readouterr().out


# --------------------------------------------------------------- o que se grava


def _formas(endereco: str) -> list[str]:
    hexa = endereco.replace(":", "").lower()
    return [endereco.lower(), endereco.upper(), hexa, hexa.upper(),
            endereco.replace(":", "_").upper()]


def test_2_grava_por_segundo_sem_endereco(tmp_path: Path) -> None:
    saida = tmp_path / "s.jsonl"
    mundo = _Mundo()
    rc = sinal.gravar(mundo.portas(), sinal.Pedido(True, 3, "hci0", "hci1"),
                      distancia="3 m com obstáculo", segundos=4, saida=saida)
    assert rc == 0 and mundo.fechou and mundo.abertos == [("hci0", "hci1", 3)]
    texto = saida.read_text(encoding="utf-8")
    for endereco in (CONTROLE_1, CONTROLE_2):
        for forma in _formas(endereco):
            assert forma not in texto, f"o endereço vazou na forma {forma}"
    assert not re.search(r"([0-9a-f]{2}[:_-]){5}[0-9a-f]{2}", texto, re.I)
    linhas = [json.loads(li) for li in texto.splitlines()]
    assert len(linhas) == 8, "um par por controle por segundo"
    p1 = [li for li in linhas if li["controle"] == "P1"]
    assert [li["segundo"] for li in p1] == [0, 1, 2, 3]
    assert p1[0]["enlace_a"] == -41, "o endereço em caixa alta é o mesmo controle"
    assert p1[0]["varredura_b"] == -40
    assert p1[0]["vizinhos"] == 1 and p1[0]["modelo_a"] == "usb 0a12:0001"
    assert {li["controle"] for li in linhas} == {"P1", "P2"}


def test_2b_o_modelo_do_adaptador_vem_do_modalias_sem_endereco(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pasta = tmp_path / "sys" / "class" / "bluetooth" / "hci0" / "device"
    pasta.mkdir(parents=True)
    (pasta / "modalias").write_text("usb:v0A12p0001d8891dcE0dsc01dp01icE0isc01ip01in00\n")
    original = Path.read_text

    def ler(self: Path, *a: object, **k: object) -> str:
        if str(self).startswith("/sys/class/bluetooth/"):
            return original(tmp_path / str(self).lstrip("/"))
        return original(self, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", ler)
    assert sinal.modelo_do_adaptador("hci0") == "usb 0a12:0001"
    assert sinal.modelo_do_adaptador("hci9") == "não sei"


# --------------------------------------------------------------- a conta, sobre as sessões gravadas


def _sessao(nome: str) -> list[object]:
    return list(sinal.ler_pares(FIXTURES / f"{nome}.json"))


def test_3_a_mesma_regua_confere_e_a_conta_bate() -> None:
    pares = _sessao("mesma-regua")
    assert sinal.conferir(pares) == []
    distancias = sinal.por_distancia(pares)
    assert [d.distancia for d in distancias] == list(sinal.DISTANCIAS)
    for d in distancias:
        assert d.entre_adaptadores == pytest.approx(2.0)
        assert d.conversao == pytest.approx(1.0)
    assert sinal.ouvidos_na_fase_3(pares) == {"usb 8087:0029": pytest.approx(0.3)}
    assert len(sinal.linhas_curtas(pares)) == len(sinal.DISTANCIAS) + 1


def test_4_o_enlace_que_le_zero_de_perto_reprova_os_limiares() -> None:
    problemas = sinal.conferir(_sessao("faixa-ideal"))
    assert any("faixa ideal" in p for p in problemas), problemas
    assert str(rm.SINAL_QUE_ATRASA_DBM) in problemas[0]


def test_5_enlace_e_varredura_em_reguas_diferentes_reprovam() -> None:
    problemas = sinal.conferir(_sessao("escala-diferente"))
    assert any("15,0 dB" in p and "conversão" in p for p in problemas), problemas
    assert sinal.conferir(_sessao("escala-diferente"), folga=16) == [], "a folga é o interruptor"


def test_6_a_margem_tem_de_cobrir_a_diferenca_entre_os_adaptadores() -> None:
    problemas = sinal.conferir(_sessao("adaptadores-longe"))
    assert len(problemas) == len(sinal.DISTANCIAS), problemas
    assert all("margem de 8" in p for p in problemas)
    assert sinal.conferir(_sessao("adaptadores-longe"), margem=13) == []


def test_7_as_constantes_seguem_a_sessao_gravada() -> None:
    """Gravada a bancada (``bancada.json``), as constantes do produto têm de conferir com ela."""
    assert rm.SINAL_QUE_ATRASA_DBM == -48 and rm.SINAL_QUE_PERDE_APERTO_DBM == -52
    assert pr.MARGEM_DO_SINAL_QUE_COMPENSA_DBM == 8
    gravada = sinal.gravada()
    if gravada is None:
        return
    assert sinal.conferir(gravada) == []


def test_8_o_roteiro_e_o_da_sprint() -> None:
    passos = sinal.roteiro("hci0", "hci1")
    texto = "\n".join(passos)
    assert texto.count("--fase 1") == texto.count("--fase 2") == 3 * len(sinal.DISTANCIAS)
    assert texto.count("--fase 3") == 3
    assert "A = hci1, B = hci0" in texto, "a repetição com A e B trocados"
    assert "P2" in texto
    assert all("--medir" in p for p in passos if "gravar" in p)
