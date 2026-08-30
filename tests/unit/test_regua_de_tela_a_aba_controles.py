"""A PRIMEIRA RÉGUA DE TELA: a aba Controles, dirigida por dentro.

Pedido dela, 29/08/2026: *"temos que ter no nosso hook do novo dev algo que
induza a construção de validações via interface pra ver se tal problema foi
resolvido ou se tal coisa traz regressão"*. Este módulo é o primeiro exemplar do
gênero, e o instrumento que ele usa é ``scripts/regua_de_tela.py``.

**Régua se prova contra defeito conhecido.** Os quatro que este arquivo cobre
foram achados nesta casa em 29/08/2026, e cada um está preso a uma medição:

(a) O ``or 128``. ``mesa_viva._eixo_do_analogico`` era
    ``int(inputs.get(nome) or 128)``, e ``0 or 128`` é ``128``: o zero — que num
    analógico é o EXTREMO — virava o CENTRO. Erro de 128 unidades, o máximo
    possível. Curado; :func:`test_o_extremo_do_analogico_nao_e_o_centro` reprova
    se voltar, e reprova **pela tela**: o que ele mede é onde o ponto está
    desenhado, não o que a função devolve.

(b) A geometria dos analógicos. Sem o ``transform:translate(-50%,-50%)`` do
    ``.stick .p`` o ponto era posicionado pelo CANTO: cru 0 e cru 255 davam
    -43,5 px e +52,5 px — 7 px vazando para fora de um lado e 9 px sobrando do
    outro. Com a cura os dois lados dão ±48 px.

(c) Os três botões de som. O 🎙, o ♪ e o "Liberar" tinham ``cursor:pointer``,
    eram pintados, e **não tinham ouvinte**: dois cliques sintéticos produziram
    ZERO gestos enquanto os botões de rota, ao lado, ecoavam. A régua de então
    dava VERDE sobre dois botões mortos porque nunca os tocava. E o "Liberar"
    tem de nascer TRAVADO: sem posse do mudo não há o que devolver ao kernel.

(d) A mordida, nas duas metades que o piloto já tinha: sem a ponte a tela fica
    na cena FIXA do mockup (quatro controles, "Mortal Kombat"); e com os
    ``data-*`` arrancados a pintura DESABA. Se qualquer uma das duas não
    acontecer, o dado não estava vindo do Python.

COMO MORDER ESTE ARQUIVO (e é assim que ele foi provado, numa cópia da árvore):

    (a) ``mesa_viva._eixo_do_analogico``  → ``return int(inputs.get(nome) or 128)``
    (b) ``aba02``, no ``.stick .p``       → tire o ``transform:translate(-50%,-50%)``
    (c) ``controles_vivos.BOOTSTRAP``     → apague o laço ``for(const b of qa('[data-mudo]'))``
    (d) ``controles_vivos.BOOTSTRAP``     → faça ``txt``/``est`` devolverem 1 sempre

O QUE ESTE MÓDULO NÃO PROVA: nada de pixel (ver ``O_QUE_ELE_NAO_FAZ`` no
instrumento), nada de ``:hover`` e nada das outras nove abas. Ele também **pula**
onde não há servidor gráfico, WebKit2 4.1 ou o ``novo-layout/`` (que é
``.gitignore:108``) — e um pulo não é um verde: o resumo do pytest o nomeia.
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.gui import ponte_da_tela
from tests.conftest import exigir_gi_real

exigir_gi_real("RÉGUA-DE-TELA-01 — a aba Controles dirigida por dentro")

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

#: O piloto e o gerador da aba moram ao lado do mockup, e são usados como
#: BIBLIOTECA. Reusar é a regra desta casa: copiar o `_pacote_do_card` para cá
#: criaria uma segunda verdade sobre o que a tela recebe, e a régua deixaria de
#: sentir quem quebrasse o original.
FERRAMENTAS = PAGINA.parent / "_ferramentas"
sys.path.insert(0, str(FERRAMENTAS))
try:
    mesa_viva = importlib.import_module("mesa_viva")
    aba02 = importlib.import_module("aba02")
    controles_vivos = importlib.import_module("controles_vivos")
except Exception as _erro:  # pragma: no cover — árvore sem o piloto
    pytest.skip(
        f"RÉGUA-DE-TELA-01: o piloto da aba não importou de {FERRAMENTAS} "
        f"({type(_erro).__name__}: {_erro})",
        allow_module_level=True,
    )

#: A faixa sintética da casa (`scripts/check_faixa_sintetica.py`). Nenhum
#: endereço real entra em arquivo versionado, e a mesa deste teste é inventada.
UNIQ = ("aabbcc000001", "aabbcc000002")

#: O centro do curso de um analógico. `0` e `255` são os EXTREMOS.
CENTRO, MINIMO, MAXIMO = 128, 0, 255

#: O deslocamento do ponto no fim do curso, MEDIDO em 29/08/2026 na aba de hoje:
#: o círculo tem 100 px de caixa e 2 px de borda, então o ponto — centrado pelo
#: `translate(-50%,-50%)` — vai de 257 px a 353 px num círculo cujo centro é
#: 305 px. Os dois lados dão 48. A tolerância é de meio pixel.
DESLOCAMENTO_NO_FIM = 48.0
FOLGA = 0.6


# ---------------------------------------------------------------------------
# A mesa de mentira
# ---------------------------------------------------------------------------
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
    """A ponte DE PRODUÇÃO com o transporte trocado.

    Desde 29/08/2026 a janela, as duas pontes e a guarda de carga saíram do
    piloto para `gui/ponte_da_tela.py`, e o `_remontar`/`_pintar` do piloto
    falam por ela. Esta subclasse troca SÓ o `rodar` — o WebView próprio pelo
    `executar` da régua — e herda tudo o mais: a serialização em JSON, uma
    chamada por pacote e a recusa do gesto malformado. **Reescrever `dizer`
    aqui criaria a segunda verdade** sobre o que a tela recebe, que é o defeito
    que a extração existe para não cometer.
    """

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
    """O lado Python do piloto, sem a janela dele.

    Herda de :class:`controles_vivos.Janela` de propósito e **não** chama o
    ``__init__`` — aquele abre uma janela GTK própria e fala com o daemon dela.
    O que se herda é o que interessa: ``_remontar``, ``_pintar``,
    ``_pacote_do_card`` e ``_gesto``, verbatim. Assim a régua mede o MESMO
    código que a interface roda, e quem quebrar qualquer um dos quatro é pego
    aqui em vez de na tela dela.
    """

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

    # -- o que a régua acrescenta -----------------------------------------
    def pintar(self, state: dict[str, Any], *, remontar: bool = True) -> int:
        """Remonta e pinta a mesa daquele `state`. Devolve os valores escritos.

        O `__hefN` volta a -1 antes de cada pintura porque o bootstrap só
        relata quando a conta MUDA — sem isso, a segunda pintura de um mesmo
        desenho passaria calada e a régua leria "nenhum valor escrito".

        ``remontar=False`` PINTA SEM RECONSTRUIR O HTML, e não é conforto: a
        remontagem troca o `innerHTML` do corpo pelo que o gerador emite, ou
        seja, ela DEVOLVE todo `data-*` que se tenha arrancado. Foi assim que a
        primeira versão da mordida do endereço deu 121 → 121 e mediu a si
        mesma. O piloto tem a mesma disciplina: só remonta quando a chave da
        mesa muda, e no resto do tempo faz diff.
        """
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
        """Entrega à cabeça o que a tela mandou — e o eco volta para a tela.

        É o outro sentido da ponte, e sem ele a prova pararia na metade: o
        "Liberar" só destrava porque o 🎙 assumiu a posse **no Python** e o eco
        voltou. Quem faz a conta é o `_da_tela` do piloto, sem cópia.
        """
        for recado in recados:
            self.ponte.receber_texto(recado.bruto)
        self.tela.avancar(0.2)


def _cartao(indice: int = 0) -> str:
    return f'.ctl[data-controle="{UNIQ[indice]}"]'


def _desvio_do_ponto(tela: Any, lado: str, indice: int = 0) -> float:
    """Quantos pixels o ponto está à direita do centro do círculo.

    Negativo é para a esquerda. É a medida que interessa: a posição ABSOLUTA
    muda com o layout, a relativa ao próprio círculo é a promessa do desenho.
    """
    circulo = tela.medir(f'{_cartao(indice)} .stick[data-stick="{lado}"]')
    ponto = tela.medir(f'{_cartao(indice)} .stick[data-stick="{lado}"] .p')
    return ponto.centro[0] - circulo.centro[0]


def _desvio_vertical(tela: Any, lado: str, indice: int = 0) -> float:
    circulo = tela.medir(f'{_cartao(indice)} .stick[data-stick="{lado}"]')
    ponto = tela.medir(f'{_cartao(indice)} .stick[data-stick="{lado}"] .p')
    return ponto.centro[1] - circulo.centro[1]


# ---------------------------------------------------------------------------
# A bancada
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def bancada():
    """Uma aba aberta e a ponte instalada — uma vez para o módulo inteiro.

    Abrir um WebView por teste custa ~1,5 s cada; a mesa é repintada entre os
    testes, que é o que a interface faz de verdade dez vezes por segundo.
    """
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


# ---------------------------------------------------------------------------
# (a) O `or 128` — o extremo não pode aparecer como centro
# ---------------------------------------------------------------------------
def test_o_extremo_do_analogico_nao_e_o_centro(mesa):
    """Cru 0 nos dois eixos: a tela tem de mostrar 0 e desenhar no canto.

    A DIFERENÇA ENTRE ESTA RÉGUA E UM TESTE DE UNIDADE: se
    `_eixo_do_analogico` voltar a ser `or 128`, um teste de unidade da função
    pega; um teste do desenho também tem de pegar, porque o caminho inteiro —
    IPC, `estado_do_card`, `_pacote_do_card`, `HEF.pinta`, CSS — é onde ela
    olha. Aqui o zero é lido de volta DA TELA.
    """
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
    """A outra metade da mesma régua: 128 tem de ficar no meio, e fica.

    Sem este par, apagar a cura do `or 128` e pôr um `or 0` no lugar passaria:
    o extremo iria para o canto e o centro iria junto.
    """
    tela, cabeca = mesa
    cabeca.pintar(_estado(lx=CENTRO, ly=CENTRO))
    assert abs(_desvio_do_ponto(tela, "l")) < 1.0
    assert abs(_desvio_vertical(tela, "l")) < 1.0


# ---------------------------------------------------------------------------
# (b) A geometria: os dois extremos têm de ser simétricos
# ---------------------------------------------------------------------------
def test_os_dois_extremos_do_analogico_sao_simetricos(mesa):
    """Cru 0 e cru 255 têm de dar o MESMO deslocamento, com sinais trocados.

    Antes da cura o ponto era posicionado pelo canto e não pelo centro:
    -43,5 px de um lado e +52,5 px do outro — 7 px vazando para fora do círculo
    num extremo e 9 px sobrando no outro. A assimetria é o defeito; o ±48 é o
    valor medido depois da cura.
    """
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
    """A consequência visível da assimetria, dita como ela aparece na tela.

    O ponto tem 9 px e a borda do círculo tem 2 px, então no fim do curso ele
    SEMPRE sobra um pouco para fora — 2,5 px de cada lado, e isso é o desenho,
    não defeito. O defeito era a sobra ser DIFERENTE nas duas pontas: com o
    ponto posicionado pelo canto, num extremo ele entrava 2 px e no outro saía
    7 px. Exigir "sobra zero" reprovaria a tela curada; o que se exige é
    simetria.

    Esta primeira versão do teste EXIGIA sobra zero e reprovou a árvore sã. Fica
    escrito: uma régua que reprova a cura em vez do defeito é o modo de falha
    mais caro desta casa, e ela se pega comparando com a medida real.
    """
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


# ---------------------------------------------------------------------------
# (c) Os três botões de som — e o "Liberar" que nasce travado
# ---------------------------------------------------------------------------
def test_os_tres_botoes_de_som_existem_na_tela(mesa):
    """Antes de perguntar se respondem, perguntar se estão lá.

    Um seletor que não casa é ERRO nesta régua, nunca silêncio — foi o silêncio
    que deixou o `--prova-gesto` dar verde sobre dois botões mortos.
    """
    tela, _ = mesa
    for bloco in ("microfone", "alto-falante", "mic-liberar"):
        assert tela.existe(f'{_cartao()} [data-mudo="{bloco}"]'), (
            f'o botão [data-mudo="{bloco}"] sumiu do cartão. Sem ele a régua '
            "não teria como reprovar quem o quebrasse."
        )


def test_o_liberar_nasce_travado_sem_posse(mesa):
    """Sem posse do mudo não há o que devolver — e o botão diz isso.

    `mic.set {muted: null}` devolve a posse ao kernel; sem tê-la assumido antes,
    a chamada não tem sentido. O produto já nasce com o botão insensível
    (`TEXTO_BOTAO_MIC_DEVOLVER`), e a tela nova tem de fazer o mesmo.
    """
    tela, _ = mesa
    assert tela.travado(f'{_cartao()} [data-mudo="mic-liberar"]'), (
        "o Liberar nasceu CLICÁVEL sem posse do mudo — a tela está oferecendo "
        "uma chamada que o daemon não tem o que atender."
    )


def test_o_liberar_travado_nao_responde_ao_clique(mesa):
    """Travado tem de ser MUDO. E provar silêncio custa o prazo inteiro.

    Não se prova ausência olhando por um instante: `esperados=0` faz a régua
    cumprir o prazo antes de concluir.
    """
    tela, _ = mesa
    tela.clicar_e_ouvir(
        f'{_cartao()} [data-mudo="mic-liberar"]', esperados=0, prazo=0.8
    )


def test_o_microfone_e_o_alto_falante_respondem_ao_clique(mesa):
    """O defeito de 29/08, direto: dois botões pintados e sem ouvinte.

    `clicar` só prova que o clique SAIU. O que prova que alguém o ouviu é o
    recado voltando pela ponte — e é o que esta régua exige.
    """
    tela, _ = mesa
    for bloco in ("microfone", "alto-falante"):
        recados = tela.clicar_e_ouvir(f'{_cartao()} [data-mudo="{bloco}"]')
        gesto = recados[0].objeto
        assert gesto["gesto"] == "mudo", gesto
        assert gesto["bloco"] == bloco, gesto
        assert gesto["controle"] == UNIQ[0], gesto


def test_o_microfone_da_posse_e_o_liberar_destrava(mesa):
    """O caminho inteiro: tela → Python → eco → tela, e de volta ao travado.

    É a ordem que morde. Clicar os três em qualquer ordem não distinguiria
    "travado" de "sem ouvinte" — que é exatamente o defeito de origem.
    """
    tela, cabeca = mesa
    liberar = f'{_cartao()} [data-mudo="mic-liberar"]'

    assert tela.travado(liberar), "o Liberar tinha de nascer travado"

    cabeca.ouvir(tela.clicar_e_ouvir(f'{_cartao()} [data-mudo="microfone"]'))
    assert not tela.travado(liberar), (
        "o 🎙 assumiu a posse do mudo e o Liberar continuou travado — o eco não "
        "voltou do Python para a tela."
    )

    cabeca.ouvir(tela.clicar_e_ouvir(liberar))
    assert tela.travado(liberar), (
        "o Liberar devolveu a posse ao kernel e continuou clicável — a tela "
        "está oferecendo devolver o que já foi devolvido."
    )


def test_o_gesto_do_som_tem_dono_declarado(mesa):
    """Todo gesto que chega ao Python tem de saber QUEM o aplicaria.

    `DONOS_DOS_GESTOS` é a tabela num lugar só. Um gesto sem linha nela é um
    endereço que o gerador não escreve, e a régua tem de dizer isso em vez de
    engolir — foi um `KeyError` cru que já derrubou a janela inteira.
    """
    tela, _cabeca = mesa
    recados = tela.clicar_e_ouvir(f'{_cartao()} [data-mudo="alto-falante"]')
    chave = f'mudo:{recados[0].objeto["bloco"]}'
    dono = controles_vivos.DONOS_DOS_GESTOS.get(chave)
    assert dono, f"{chave} chegou à ponte sem linha em DONOS_DOS_GESTOS"
    assert "speaker.set" in dono, dono


# ---------------------------------------------------------------------------
# (d) A mordida: sem ponte, e sem endereços
# ---------------------------------------------------------------------------
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

    Quatro controles e "Mortal Kombat" são a cena literal do mockup aprovado. Se
    esta tela mostrasse a mesa dela, o dado não estaria vindo da ponte — estaria
    vindo de algum lugar que ninguém declarou.
    """
    with regua_de_tela.Tela(PAGINA, titulo_esperado="Hefesto") as tela:
        assert tela.contar(".ctl") == 4, (
            "sem ponte a aba tinha de mostrar os quatro controles do desenho"
        )
        assert tela.ler(".pa-nome") == "Mortal Kombat"
        assert not tela.existe(_cartao(0)), (
            "sem ponte a tela mostrou um cartão da mesa de mentira: alguém "
            "pintou sem passar pela ponte."
        )
        assert tela.recados() == [], (
            f"sem ponte a página mandou recado sozinha: {tela.recados()}"
        )


def test_arrancar_os_enderecos_faz_a_pintura_desabar(mesa):
    """A MORDIDA DO ENDEREÇO: sem os `data-*` a conta da pintura tem de cair.

    Um endereço a menos não levanta erro nenhum no WebKit — o `querySelector`
    devolve `null` e o valor simplesmente não é escrito. Por isso a régua é a
    CONTA: `HEF.pinta` devolve quantos valores escreveu, e se a conta não cair
    ao arrancar os endereços é porque eles não estavam sendo usados.

    `data-controle` fica de fora de propósito — arrancá-lo derruba a pintura
    inteira de uma vez, e a queda deixaria de dizer QUAL endereço morreu.
    """
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

    # O TETO É 20% E FOI CALIBRADO CONTRA A MORDIDA, não escolhido no olho. Com
    # a árvore sã a conta cai 121 → 17 (14%). Com as escritas do bootstrap
    # contando CEGO — o `n++` de 27/08, que devolve 1 mesmo sem elemento — ela
    # cai só até 39 (32%), porque os laços de glifo e de eixo continuam caindo
    # sozinhos. O primeiro teto que escrevi era `inteiro/3` (33%) e deixou a
    # conta cega passar por 1,3 ponto: uma régua frouxa aprova exatamente o
    # defeito que ela existe para pegar.
    assert depois <= inteiro * 0.20, (
        f"arranquei os endereços e a pintura ainda escreveu {depois} de "
        f"{inteiro} valores ({depois / inteiro:.0%}); o medido na árvore sã é "
        "121 → 17 (14%). Ou os `data-*` não estavam sendo usados, ou as "
        "escritas do bootstrap voltaram a contar cego (`return 1` sem elemento, "
        "em vez do `return 0` de txt/est/cls/trava)."
    )
    print(f"[mordida] pintura {inteiro} → {depois} valores com os data-* fora")


def test_o_seletor_que_nao_casa_e_erro_e_nao_silencio(mesa):
    """A régua da régua. Se o instrumento mentir, tudo acima é enfeite.

    É o portão do próprio vocabulário: `ler`, `medir`, `travado` e `clicar` têm
    de REPROVAR em endereço que não existe, e é isso que separa este instrumento
    do `--prova-gesto` que dava verde sobre dois botões mortos.
    """
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
    recados = tela.clicar_e_ouvir(f'{_cartao()} [data-mudo="microfone"]')
    assert isinstance(recados[0].objeto, dict), recados[0].bruto
    assert json.loads(recados[0].bruto) == recados[0].objeto
    assert recados[0].aos > 0, "o recado chegou sem hora"
