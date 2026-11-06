"""A tela mostra e não diz: nenhuma frase explica API, protocolo ou o que o jogo vê.

A-TELA-NAO-EXPLICA-O-QUE-O-CHIP-JA-MOSTRA-01 (31/10/2026). Com a máscara Xbox 360, o cabeçalho do
controle dizia «Giroscópio: o jogo vê este controle como Xbox 360, e essa API não leva giroscópio —
no Hefesto ele segue ativo», e a mesma frase como dica, ao lado dos chips que já dizem o que está
ligado. As réguas olham as três portas por onde uma frase dessas chega à tela: o pacote vivo do
cartão, as constantes de texto dos geradores e dos pacotes, e o HTML gerado das abas.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
from html.parser import HTMLParser
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09
from hefesto_dualsense4unix.interface.pacotes import camada

EXPLICACAO = re.compile(
    r"\bAPI\b|segue ativo|não leva (o )?(giroscópio|touchpad)"
    r"|o jogo vê (este|deste) controle|como Xbox 360|Xbox 360[,.:;—]"
    r"|o jogo lê este controle|o jogo ainda vê|sem o Hefesto no meio|pelo rádio, é assim"
    r"|não há som nem vibração"
    r"|o jogo vê (um|o próprio) controle|enumera este aparelho"
    r"|chega tudo o que o jogo usa|menos que pelo USB|os gatilhos não chegam"
    r"|a borda é a cor do plástico que|uma borda colorida aqui|assumir o registrador"
    r"|modelo do controle virtual",
    re.IGNORECASE,
)

FRASES_QUE_SAIRAM = {
    "DO_DESLIGADO": r"como ele é, sem Steam|A Steam traduz o controle|Vira mouse e teclado;",
    "FRASE_DO_MODO_NATIVO": r"quem conta os\s+jogadores",
    "o resumo dos impedimentos": r"não recebem? gatilhos e vibração",
    "nintendo_bt_warning": r"modo Switch pode travar|driver do kernel",
    "a dica da extensão": r"Foi você quem disse|leitura do sistema distingue",
    "DICA_DOS_HUBS": r"não enxerga hubs",
    "a cauda do ap_botao": r"O objeto:",
    "a dica da borda": r"A borda é a cor lida|^A borda é a cor|title=\"A borda é a cor",
    "BOTAO_DICA": r"botão físico do microfone",
    "DICA_MIC_SEM_LEITURA": r"ainda não leu o estado do microfone|seria chute",
}


def _frases_que_voltaram(texto: str) -> list[str]:
    return [nome for nome, frase in FRASES_QUE_SAIRAM.items() if re.search(frase, texto, re.I)]

UNIQ = "aa:bb:cc:00:00:01"

XBOX = {
    "rumble_ff": {"per_vpad": [{"player": 1, "uniq": UNIQ, "motion_streaming": True,
                                "motion_hz": 250.0}]},
    "gamepad_emulation": {"enabled": True, "flavor": "xbox",
                          "por_aparelho": {UNIQ: "xbox"}},
}


def _cartao(estado: dict[str, Any], **entrada: Any) -> dict[str, Any]:
    dele = {"uniq": UNIQ, "transport": "usb", "connected": True, "is_primary": True,
            "inputs": {}, "audio": {}, "speaker": {}, **entrada}
    ctx = Contexto(state=estado, mesa=[], conectados=[dele], estados={})
    return dict(a02.pacote(ctx)["cards"][UNIQ])


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("estado", [
    XBOX,
    {**XBOX, "native_mode": True},
    {"rumble_ff": XBOX["rumble_ff"]},
], ids=["xbox", "nativo-com-xbox", "dualsense"])
def test_o_cartao_com_o_giroscopio_ligado_nao_explica_nada(
    estado: dict[str, Any], transporte: str,
) -> None:
    """Nenhum campo do cartão, linha ou dica, fala de API, de «Xbox 360» numa frase ou de «segue
    ativo».

    MORDE: devolva o `_FRASE_MASCARA_XBOX` e o `texto_motion` ao cartão e o campo dele ao pacote, e
    a máscara Xbox volta a emitir a frase.
    """
    card = _cartao(estado, transport=transporte,
                   sensores={"giroscopio_ligado": True, "acelerometro_ligado": True})
    falam = {k: v for k, v in card.items() if isinstance(v, str) and EXPLICACAO.search(v)}
    assert not falam, f"o cartão explicou o que o chip já mostra: {falam}"


def _constantes_de_texto(arquivo: pathlib.Path) -> list[tuple[int, str]]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if (isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and corpo and isinstance(corpo[0], ast.Expr)
                and isinstance(corpo[0].value, ast.Constant)):
            docstrings.add(id(corpo[0].value))
    return [(no.lineno, no.value) for no in ast.walk(arvore)
            if isinstance(no, ast.Constant) and isinstance(no.value, str)
            and id(no) not in docstrings]


GERADORES_E_PACOTES = sorted([
    INTERFACE / "cartao_do_controle.py",
    INTERFACE / "conexoes.py",
    INTERFACE / "desenho_da_experimental.py",
    INTERFACE / "logica_do_mapa.py",
    RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "impedimentos_da_steam.py",
    RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "external_controllers.py",
    RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "jogar" / "painel.py",
    *INTERFACE.glob("aba[01][0-9].py"),
    *(INTERFACE / "pacotes").glob("*.py"),
])


def test_ha_geradores_e_pacotes_para_varrer() -> None:
    nomes = {p.name for p in GERADORES_E_PACOTES}
    assert {"cartao_do_controle.py", "aba01.py", "aba02.py", "a02_controles.py",
            "a09_sistema.py"} <= nomes, nomes


@pytest.mark.parametrize("arquivo", GERADORES_E_PACOTES, ids=lambda p: p.name)
def test_nenhum_texto_dos_geradores_e_dos_pacotes_explica_a_api(arquivo: pathlib.Path) -> None:
    """A frase que sai da tela sai do código: nenhuma constante de texto a guarda para voltar.

    MORDE: devolva o `_FRASE_MASCARA_XBOX` a `cartao_do_controle.py`, mesmo sem chamador, e reprova.
    """
    achados = [f"{arquivo.name}:{n}: {t[:90]!r}"
               for n, t in _constantes_de_texto(arquivo) if EXPLICACAO.search(t)]
    assert not achados, "\n".join(achados)


@pytest.mark.parametrize("arquivo", GERADORES_E_PACOTES, ids=lambda p: p.name)
def test_as_frases_que_sairam_nao_voltam_aos_geradores(arquivo: pathlib.Path) -> None:
    """Inclui o pedaço de um `title=` montado em f-string, que também é constante de texto.

    MORDE: devolva o texto antigo do `DICA_MIC_SEM_LEITURA` e reprova com o nome da constante.
    """
    achados = [f"{nome}: {arquivo.name}:{n}: {t[:90]!r}"
               for n, t in _constantes_de_texto(arquivo) for nome in _frases_que_voltaram(t)]
    assert not achados, "\n".join(achados)


class _TextoDaTela(HTMLParser):
    ATRIBUTOS = ("title", "data-dica", "aria-label", "alt", "placeholder")

    def __init__(self) -> None:
        super().__init__()
        self.dentro_de_codigo = 0
        self.textos: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self.dentro_de_codigo += 1
        for nome, valor in attrs:
            if nome in self.ATRIBUTOS and valor:
                self.textos.append((self.getpos()[0], valor))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.dentro_de_codigo = max(0, self.dentro_de_codigo - 1)

    def handle_data(self, data: str) -> None:
        if not self.dentro_de_codigo and data.strip():
            self.textos.append((self.getpos()[0], data.strip()))


PAGINAS = sorted(p for p in (RAIZ / "mockup").glob("[01][0-9]-*.html"))


def test_ha_as_paginas_das_abas() -> None:
    assert len(PAGINAS) >= 9, PAGINAS


@pytest.mark.parametrize("desenho", PAGINAS, ids=lambda p: p.name)
def test_o_html_gerado_das_abas_nao_explica_a_api(desenho: pathlib.Path) -> None:
    """Prova da D-3110-A-TELA-MOSTRA-E-NAO-DIZ: o texto e as dicas de cada aba, sem explicação.

    MORDE: devolva o `title` «O que o jogo vê deste controle» à máscara do `aba02.py`, regere a 02,
    e reprova.
    """
    leitor = _TextoDaTela()
    leitor.feed(desenho.read_text(encoding="utf-8"))
    achados = [f"{desenho.name}:{n}: {t[:90]!r}" for n, t in leitor.textos if EXPLICACAO.search(t)]
    assert not achados, "\n".join(achados)


def _publicadas_sem_declaracao() -> list[pathlib.Path]:
    corpo = (onde.ENSAIO / "DIVERGENCIAS.md").read_text(encoding="utf-8").partition("\n---\n")[2]
    em_trabalho = set(re.findall(r"^##\s+(\S+\.html)\s*$", corpo, re.M))
    return sorted(p for p in onde.PUBLICADO.glob("[01][0-9]-*.html") if p.name not in em_trabalho)


@pytest.mark.parametrize("desenho", [*PAGINAS, *_publicadas_sem_declaracao()],
                         ids=lambda p: f"{p.parent.name}/{p.name}")
def test_as_frases_que_sairam_nao_voltam_as_paginas(desenho: pathlib.Path) -> None:
    """O `title` e o `data-dica` de cada aba; a publicada entra quando sai da DIVERGENCIAS.md.

    MORDE: devolva o `title` da borda em `aba08.py`, regere a 08, e reprova com o nome dele.
    """
    leitor = _TextoDaTela()
    leitor.feed(desenho.read_text(encoding="utf-8"))
    achados = [f"{nome}: {desenho.name}:{n}: {t[:90]!r}"
               for n, t in leitor.textos for nome in _frases_que_voltaram(t)]
    assert not achados, "\n".join(achados)


MAPA_DO_RADIO = (*sorted(INTERFACE.glob("*/mapa-do-radio.html")),
                 RAIZ / "mockup" / "mapa-do-radio.html")


@pytest.mark.parametrize("arquivo", MAPA_DO_RADIO, ids=lambda p: p.parent.name)
def test_as_dicas_que_o_script_do_mapa_do_radio_escreve_nao_explicam(arquivo: pathlib.Path) -> None:
    """O mapa do rádio monta o `title` do sinal no script, que o leitor de HTML pula.

    MORDE: devolva «chega tudo o que o jogo usa» ao `DICA_DO_MOVIMENTO` da página e reprova.
    """
    assert len(MAPA_DO_RADIO) == 2, MAPA_DO_RADIO
    achados = [f"{arquivo.name}:{n}: {linha.strip()[:90]!r}"
               for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1)
               if EXPLICACAO.search(linha)]
    assert not achados, "\n".join(achados)


@pytest.mark.parametrize("arquivo", MAPA_DO_RADIO, ids=lambda p: p.parent.name)
def test_a_dica_do_movimento_do_mapa_do_radio_e_a_mesma_da_08(arquivo: pathlib.Path) -> None:
    """O `DICA_DO_MOVIMENTO` do script do mapa e o gêmeo da 08 dizem a mesma palavra por nível.

    MORDE: troque o «reduzido» só do script da página e reprova.
    """
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

    bloco = re.search(r"const DICA_DO_MOVIMENTO = \{(.*?)\};", arquivo.read_text(encoding="utf-8"),
                      re.S)
    assert bloco, f"{arquivo.name} perdeu o `DICA_DO_MOVIMENTO`"
    do_script = {chave.strip("'"): texto
                 for chave, texto in re.findall(r"(\w+|''):\s*'([^']*)'", bloco.group(1))}
    assert do_script == a08.DICA_DO_MOVIMENTO, (do_script, a08.DICA_DO_MOVIMENTO)


def _estado_do_sistema(**extra: Any) -> dict[str, Any]:
    return {"controllers": [{"uniq": UNIQ, "connected": True}],
            "rumble_ff": {"vpads": 0}, "gamepad_emulation": {"enabled": True}, **extra}


@pytest.mark.parametrize("estado", [
    _estado_do_sistema(native_mode=True),
    _estado_do_sistema(gamepad_emulation={"enabled": False}),
    _estado_do_sistema(),
], ids=["nativo", "emulacao-desligada", "nenhum-subiu"])
def test_a_linha_do_gamepad_no_sistema_nao_explica_o_que_o_jogo_ve(estado: dict[str, Any]) -> None:
    """A linha diz o estado; a dica não acrescenta o que o jogo vê.

    MORDE: devolva a dica «No Modo Nativo não há gamepad virtual: o jogo usa o controle.» e reprova.
    """
    linha = a09.linha_do_gamepad_por_jogador(estado)
    assert linha["dica"] == linha["txt"], linha
    assert "o jogo" not in linha["dica"].lower(), linha


def test_a_recusa_no_modo_nativo_diz_o_modo_e_nao_o_que_o_jogo_le() -> None:
    """O clique recusado no Modo Nativo diz o modo e o que não grava, sem explicar o jogo.

    MORDE: devolva «Em modo nativo o jogo lê este controle direto, …» a `pacotes/camada.py` e
    reprova.
    """
    frases = {camada.FRASE_NO_NATIVO, *camada.FRASES_NO_NATIVO.values()}
    assert frases, "a camada parou de ter frase de recusa"
    for frase in frases:
        assert frase.startswith("Modo Nativo:"), frase
        assert not EXPLICACAO.search(frase) and "o jogo" not in frase.lower(), frase
