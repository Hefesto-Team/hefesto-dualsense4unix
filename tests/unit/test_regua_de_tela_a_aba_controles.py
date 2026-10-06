"""A PRIMEIRA RÉGUA DE TELA: a aba Controles, dirigida por dentro."""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("RÉGUA-DE-TELA-01 — a aba Controles dirigida por dentro")

from hefesto_dualsense4unix.interface import janela as ponte_da_tela

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
    pytest.skip(
        "RÉGUA-DE-TELA-01: sem servidor gráfico. `Gtk.OffscreenWindow` ainda "
        "precisa de um GDK display — sem ele não há WebView para dirigir.",
        allow_module_level=True,
    )

try:
    regua_de_tela = importlib.import_module("regua_de_tela")
except (ImportError, ValueError) as _erro:  # pragma: no cover — ambiente sem WebKit
    pytest.skip(
        f"RÉGUA-DE-TELA-01: o instrumento não importou ({_erro}). Falta "
        "gir1.2-webkit2-4.1?",
        allow_module_level=True,
    )

try:
    PAGINA = regua_de_tela.achar_a_aba("02")
except regua_de_tela.MockupAusente as _erro:
    pytest.skip(f"RÉGUA-DE-TELA-01: {_erro}", allow_module_level=True)

def _ferramentas_da_pagina(pagina: pathlib.Path) -> pathlib.Path:
    for base in pagina.parents:
        alvo = base / "src" / "hefesto_dualsense4unix" / "interface"
        if alvo.is_dir():
            return alvo
    return pagina.parent


FERRAMENTAS = _ferramentas_da_pagina(PAGINA)
sys.path.insert(0, str(FERRAMENTAS))
try:
    mesa_viva = importlib.import_module("mesa_viva")
    aba02 = importlib.import_module("aba02")
    controles_vivos = importlib.import_module("controles_vivos")
except ImportError as _erro:  # pragma: no cover — árvore sem o piloto
    pytest.skip(
        f"RÉGUA-DE-TELA-01: o piloto da aba não importou de {FERRAMENTAS} "
        f"({type(_erro).__name__}: {_erro})",
        allow_module_level=True,
    )
except Exception as _erro:
    raise AssertionError(
        f"RÉGUA-DE-TELA-01: o gerador da aba 02 quebrou ao ser importado de "
        f"{FERRAMENTAS} — {type(_erro).__name__}: {_erro}. Isto não é ambiente "
        "sem WebKit: é código desta casa, e vira vermelho de propósito."
    ) from _erro

UNIQ = ("aabbcc000001", "aabbcc000002")

CENTRO, MINIMO, MAXIMO = 128, 0, 255

DESLOCAMENTO_NO_FIM = 48.0
FOLGA = 0.6


def _entrada(
    indice: int,
    *,
    lx: int = CENTRO,
    ly: int = CENTRO,
    rx: int = CENTRO,
    ry: int = CENTRO,
    transporte: str = "usb",
    posse_do_mudo: bool = False,
) -> dict[str, Any]:
    """Um controle do `state_full`, com só o que esta aba lê.

    `mic_mudo_desejado` é a POSSE: `None` significa que quem manda no mudo é o
    kernel (`hid_playstation`), e é por isso que o "Liberar" nasce travado —
    sem posse não há o que devolver.
    """
    return {
        "index": indice,
        "connected": True,
        "transport": transporte,
        "is_primary": indice == 0,
        "uniq": UNIQ[indice],
        "battery_pct": 85 - indice * 10,
        "player": indice + 1,
        "player_slot": indice + 1,
        "lightbar_rgb": [255, 0, 0] if indice == 0 else [0, 0, 255],
        "lightbar_on": True,
        "inputs": {
            "lx": lx,
            "ly": ly,
            "rx": rx,
            "ry": ry,
            "l2_raw": 0,
            "r2_raw": 0,
            "buttons": [],
            "gyro": {"x": 0.0, "y": 0.0, "z": 0.0},
            "touchpad": {"touching": False, "x": 0, "y": 0, "width": 1920, "height": 1080},
        },
        "audio": {
            "fone_plugado": False,
            "mic_externo": False,
            "mic_mudo": False,
            "mic_mudo_desejado": False if posse_do_mudo else None,
        },
        "speaker": {"volume": 101, "muted": False},
    }


def _estado(**kwargs: Any) -> dict[str, Any]:
    """Um `daemon.state_full` com DOIS controles — o primeiro é o que se mexe."""
    return {
        "active_profile": "Régua de Tela",
        "gamepad_emulation": {"flavor": "dualsense"},
        "controllers": [_entrada(0, **kwargs), _entrada(1)],
    }


class _PonteNaRegua(ponte_da_tela.PonteDaTela):
    """A ponte DE PRODUÇÃO com o transporte trocado."""

    def __init__(self, tela: Any, ao_receber: Any) -> None:
        self.canal = ponte_da_tela.CANAL_PADRAO
        self._ao_receber = ao_receber
        self._ao_recusar = None
        self.recusas = []
        self.chamadas = 0
        self.tela = tela

    def rodar(self, script: str) -> None:
        self.chamadas += 1
        self.tela.executar(script)


class CabecaDeMentira(controles_vivos.Janela):
    """O lado Python do piloto, sem a janela dele."""

    def __init__(self, tela: Any) -> None:
        self.tela = tela
        self.ponte = _PonteNaRegua(tela, ao_receber=self._gesto)
        self.ondas = {}
        self.eco_sensor = {}
        self.eco_rota = {}
        self.eco_mudo = {}
        self.gestos = []
        self.valores = []
        self.remontagens = 0
        self.alvo = None
        self.lento = {}
        self.mic = None

    def pintar(self, state: dict[str, Any], *, remontar: bool = True) -> int:
        """Remonta e pinta a mesa daquele `state`. Devolve os valores escritos."""
        conectados = mesa_viva.controles_conectados(state)
        mesa = mesa_viva.mesa_do_estado(state, {})
        estados = {
            c["uniq"]: mesa_viva.estado_do_card(
                next(e for e in conectados if str(e.get("uniq") or "") == c["uniq"])
            )
            for c in mesa
        }
        if remontar:
            self._remontar(mesa, estados)
        self.tela.executar("window.__hefN = -1")
        antes = len(self.tela.recados())
        self._pintar(state, mesa, conectados, estados)
        self.tela.esperar_ate(
            lambda: any(
                r.gesto == "pintou" for r in self.tela.recados()[antes:]
            ),
            prazo=3.0,
            motivo="a página relatar quantos valores a pintura escreveu",
        )
        pintou = [r for r in self.tela.recados()[antes:] if r.gesto == "pintou"][-1]
        return int(pintou.objeto["valores"])

    def ouvir(self, recados: list[Any]) -> None:
        """Entrega à cabeça o que a tela mandou — e o eco volta para a tela."""
        for recado in recados:
            self.ponte.receber_texto(recado.bruto)
        self.tela.avancar(0.2)


def _cartao(indice: int = 0) -> str:
    return f'.ctl[data-controle="{UNIQ[indice]}"]'


def _desvio_do_ponto(tela: Any, lado: str, indice: int = 0) -> float:
    """Quantos pixels o ponto está à direita do centro do círculo."""
    circulo = tela.medir(f'{_cartao(indice)} .stick[data-stick="{lado}"]')
    ponto = tela.medir(f'{_cartao(indice)} .stick[data-stick="{lado}"] .p')
    return ponto.centro[0] - circulo.centro[0]


def _desvio_vertical(tela: Any, lado: str, indice: int = 0) -> float:
    circulo = tela.medir(f'{_cartao(indice)} .stick[data-stick="{lado}"]')
    ponto = tela.medir(f'{_cartao(indice)} .stick[data-stick="{lado}"] .p')
    return ponto.centro[1] - circulo.centro[1]


@pytest.fixture(scope="module")
def bancada():
    """Uma aba aberta e a ponte instalada — uma vez para o módulo inteiro."""
    with regua_de_tela.Tela(PAGINA, titulo_esperado="Hefesto") as tela:
        tela.executar(controles_vivos.BOOTSTRAP)
        yield tela, CabecaDeMentira(tela)


@pytest.fixture()
def mesa(bancada):
    """Cada teste começa com a mesa no centro e o rodapé limpo."""
    tela, cabeca = bancada
    cabeca.eco_mudo.clear()
    cabeca.eco_rota.clear()
    cabeca.eco_sensor.clear()
    cabeca.pintar(_estado())
    tela.limpar_recados()
    return tela, cabeca


def test_o_extremo_do_analogico_nao_e_o_centro(mesa):
    """Cru 0 nos dois eixos: a tela tem de mostrar 0 e desenhar no canto."""
    tela, cabeca = mesa
    cabeca.pintar(_estado(lx=MINIMO, ly=MINIMO))

    texto = tela.ler(f'{_cartao()} .xy[data-xy="l"]')
    assert "X:   0" in texto, f"a tela não escreveu o zero: {texto!r}"
    assert "Y:   0" in texto, f"a tela não escreveu o zero: {texto!r}"

    dx = _desvio_do_ponto(tela, "l")
    dy = _desvio_vertical(tela, "l")
    assert dx < -40, (
        f"cru 0 desenhou o ponto a {dx:+.2f} px do centro — o extremo apareceu "
        "como centro. É o `or 128` de volta (mesa_viva._eixo_do_analogico)."
    )
    assert dy < -40, f"cru 0 no eixo Y desenhou a {dy:+.2f} px do centro"


def test_o_analogico_no_centro_fica_no_centro(mesa):
    """A outra metade da mesma régua: 128 tem de ficar no meio, e fica."""
    tela, cabeca = mesa
    cabeca.pintar(_estado(lx=CENTRO, ly=CENTRO))
    assert abs(_desvio_do_ponto(tela, "l")) < 1.0
    assert abs(_desvio_vertical(tela, "l")) < 1.0


def test_os_dois_extremos_do_analogico_sao_simetricos(mesa):
    """Cru 0 e cru 255 têm de dar o MESMO deslocamento, com sinais trocados."""
    tela, cabeca = mesa
    cabeca.pintar(_estado(lx=MINIMO, ly=CENTRO, rx=MAXIMO, ry=CENTRO))

    esquerda = _desvio_do_ponto(tela, "l")
    direita = _desvio_do_ponto(tela, "r")

    assert abs(abs(esquerda) - abs(direita)) < FOLGA, (
        f"os extremos ficaram ASSIMÉTRICOS: cru 0 deu {esquerda:+.2f} px e cru "
        f"255 deu {direita:+.2f} px. São DOIS defeitos possíveis, e o número "
        "separa: -43,5/+52,5 é o ponto posicionado pelo canto (falta o "
        "`transform:translate(-50%,-50%)` do `.stick .p`); ~0/+48 é o cru 0 "
        "chegando como 128 (o `or 128` de `mesa_viva._eixo_do_analogico`)."
    )
    assert abs(esquerda + DESLOCAMENTO_NO_FIM) < FOLGA, (
        f"cru 0 deu {esquerda:+.2f} px, e o medido em 29/08 é "
        f"-{DESLOCAMENTO_NO_FIM:g} px"
    )
    assert abs(direita - DESLOCAMENTO_NO_FIM) < FOLGA, (
        f"cru 255 deu {direita:+.2f} px, e o medido em 29/08 é "
        f"+{DESLOCAMENTO_NO_FIM:g} px"
    )


def test_o_ponto_vaza_o_mesmo_tanto_nos_dois_extremos(mesa):
    """A consequência visível da assimetria, dita como ela aparece na tela."""
    tela, cabeca = mesa
    cabeca.pintar(_estado(lx=MINIMO, ly=CENTRO, rx=MAXIMO, ry=CENTRO))

    esq_circulo = tela.medir(f'{_cartao()} .stick[data-stick="l"]')
    esq_ponto = tela.medir(f'{_cartao()} .stick[data-stick="l"] .p')
    dir_circulo = tela.medir(f'{_cartao()} .stick[data-stick="r"]')
    dir_ponto = tela.medir(f'{_cartao()} .stick[data-stick="r"] .p')

    sobra_esquerda = esq_circulo.x - esq_ponto.x
    sobra_direita = (dir_ponto.x + dir_ponto.largura) - (
        dir_circulo.x + dir_circulo.largura
    )
    assert abs(sobra_esquerda - sobra_direita) < FOLGA, (
        f"no cru 0 o ponto sobra {sobra_esquerda:.2f} px para fora e no cru 255 "
        f"sobra {sobra_direita:.2f} px. As duas pontas têm de sobrar igual. "
        "-2/+7 é o ponto posicionado pelo canto (falta o "
        "`transform:translate(-50%,-50%)`); uma sobra muito negativa de um lado "
        "é o cru 0 chegando como 128 (o `or 128`), e aí o ponto nem saiu do meio."
    )
    assert 0 < sobra_esquerda < 4, (
        f"a sobra virou {sobra_esquerda:.2f} px; o medido em 29/08 é 2,5 px "
        "(metade dos 9 px do ponto, menos os 2 px da borda do círculo)"
    )


def test_os_tres_botoes_de_som_existem_na_tela(mesa):
    """Antes de perguntar se respondem, perguntar se estão lá."""
    tela, _ = mesa
    for botao, quem in (('[data-gesto="mic-retorno"]', "🎙"),
                        ('[data-mudo="alto-falante"]', "♪")):
        assert tela.existe(f'{_cartao()} {botao}'), (
            f"o botão {quem} ({botao}) sumiu do cartão. Sem ele a régua "
            "não teria como reprovar quem o quebrasse."
        )


def test_o_gesto_do_som_tem_dono_declarado(mesa):
    """Todo gesto que chega ao Python tem de saber QUEM o aplicaria."""
    tela, _cabeca = mesa
    recados = tela.clicar_e_ouvir(f'{_cartao()} [data-mudo="alto-falante"]')
    chave = f'mudo:{recados[0].objeto["bloco"]}'
    dono = controles_vivos.DONOS_DOS_GESTOS.get(chave)
    assert dono, f"{chave} chegou à ponte sem linha em DONOS_DOS_GESTOS"
    assert "speaker.set" in dono, dono


def test_com_a_ponte_a_tela_mostra_a_mesa_e_nao_a_cena_fixa(mesa):
    """A metade positiva da mordida — sem ela, a negativa não prova nada."""
    tela, _ = mesa
    assert tela.contar(".ctl") == 2, (
        "a ponte pintou e a tela continuou com quatro cartões: o dado não veio "
        "do Python."
    )
    assert tela.ler(".pa-nome") == "Régua de Tela"
    assert tela.existe(_cartao(0)) and tela.existe(_cartao(1))


def test_sem_a_ponte_a_tela_fica_na_cena_fixa_do_mockup():
    """A MORDIDA: uma aba aberta e nunca tocada tem de ser o desenho.

    Quatro controles e o chip «Perfil ativo» sem nome são a cena literal do
    mockup aprovado. Se esta tela mostrasse a bancada, o dado não estaria vindo
    da ponte — estaria vindo de algum lugar que ninguém declarou.

    O CHIP NASCE COM O QUE O PINTOR ESCREVE SEM PERFIL ATIVO — 13/09/2026
    (VAO-DO-ESQUELETO-01). Até então o desenho trazia o nome de um perfil de
    exemplo, e ele ficava na tela do usuário sempre que a pintura não chegava. A
    régua pergunta o valor ao dono (`pacotes.topo`) em vez de digitá-lo.
    """
    from hefesto_dualsense4unix.interface import pacotes

    class _SemPerfil:
        def __init__(self) -> None:
            self.state: dict[str, Any] = {"active_profile": ""}
            self.mesa: list[dict[str, Any]] = []

    with regua_de_tela.Tela(PAGINA, titulo_esperado="Hefesto") as tela:
        assert tela.contar(".ctl") == 4, (
            "sem ponte a aba tinha de mostrar os quatro controles do desenho"
        )
        assert tela.ler(".pa-nome") == pacotes.topo(_SemPerfil())["perfil"]
        assert not tela.existe(_cartao(0)), (
            "sem ponte a tela mostrou um cartão da mesa de mentira: alguém "
            "pintou sem passar pela ponte."
        )
        assert tela.recados() == [], (
            f"sem ponte a página mandou recado sozinha: {tela.recados()}"
        )


def test_arrancar_os_enderecos_faz_a_pintura_desabar(mesa):
    """A MORDIDA DO ENDEREÇO: sem os `data-*` a conta da pintura tem de cair."""
    tela, cabeca = mesa
    inteiro = cabeca.pintar(_estado())
    assert inteiro > 60, f"a pintura inteira escreveu só {inteiro} valores"

    tela.executar(
        "for(const e of document.querySelectorAll('[data-glifo],[data-eixo],"
        "[data-bloco],[data-gatilho],[data-stick],[data-xy],[data-campo],"
        "[data-mudo]')){for(const a of ['glifo','eixo','bloco','gatilho',"
        "'stick','xy','campo','mudo']) delete e.dataset[a];}"
    )
    depois = cabeca.pintar(_estado(), remontar=False)

    assert depois <= inteiro * 0.20, (
        f"arranquei os endereços e a pintura ainda escreveu {depois} de "
        f"{inteiro} valores ({depois / inteiro:.0%}); o medido na árvore sã é "
        "121 → 17 (14%). Ou os `data-*` não estavam sendo usados, ou as "
        "escritas do bootstrap voltaram a contar cego (`return 1` sem elemento, "
        "em vez do `return 0` de txt/est/cls/trava)."
    )
    print(f"[mordida] pintura {inteiro} → {depois} valores com os data-* fora")


def test_o_seletor_que_nao_casa_e_erro_e_nao_silencio(mesa):
    """A régua da régua. Se o instrumento mentir, tudo acima é enfeite."""
    tela, _ = mesa
    inexistente = '.ctl [data-mudo="botao-que-nunca-existiu"]'
    assert tela.contar(inexistente) == 0
    assert not tela.existe(inexistente)
    for chamada in (
        lambda: tela.ler(inexistente),
        lambda: tela.medir(inexistente),
        lambda: tela.travado(inexistente),
        lambda: tela.clicar(inexistente),
    ):
        with pytest.raises(regua_de_tela.SemElemento) as caiu:
            chamada()
        assert "casou 0 elemento" in str(caiu.value)


def test_a_espera_que_nao_acontece_reprova(mesa):
    """`esperar_ate` devolvendo `False` viraria verde esquecido. Ele levanta."""
    tela, _ = mesa
    with pytest.raises(regua_de_tela.Impaciencia):
        tela.esperar_ate("false", prazo=0.3, motivo="o que nunca acontece")


def test_o_instrumento_declara_o_que_nao_faz():
    """Um instrumento que promete demais é pior que um limitado e honesto."""
    limites = regua_de_tela.O_QUE_ELE_NAO_FAZ
    assert len(limites) >= 5
    junto = " ".join(limites)
    for palavra in ("hover", "pixels", "GTK", "gráfico", "gitignore"):
        assert palavra in junto, f"o instrumento não declara o limite de {palavra}"


def test_a_ponte_leva_json_nos_dois_sentidos(mesa):
    """O recado é JSON — e um recado ilegível não pode virar `None` calado."""
    tela, _ = mesa
    recados = tela.clicar_e_ouvir(f'{_cartao()} [data-mudo="alto-falante"]')
    assert isinstance(recados[0].objeto, dict), recados[0].bruto
    assert json.loads(recados[0].bruto) == recados[0].objeto
    assert recados[0].aos > 0, "o recado chegou sem hora"
