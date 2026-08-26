"""O selo de saúde da aba Configurações — GTK real, e três coisas que não podem.

Este arquivo mede a SEÇÃO MONTADA, com widgets de verdade. O que ele trava:

1. **A montagem não examina.** O exame lê `/sys` e chama `busctl`, e a montagem
   roda no arranque da janela — que é o caminho por onde o
   `scripts/gui-captura/retratar_abas.py` passa ao gerar os PNGs que entram em
   `docs/usage/assets/` sem revisão humana. Nenhum portão de anonimato varre
   imagem, então a defesa tem de ser esta: a montagem não dispara leitura viva.
2. **Selo verde nunca convive com linha vermelha.** A cicatriz está em
   `scripts/doctor.sh:1586-1590` e a casa pagou por ela duas vezes em agosto
   (`6c86e295`, `c3d3518f`).
3. **Nenhum texto da seção carrega `sudo`, `JSON` ou `systemd`** — nem na
   montagem, nem depois do exame. O `scripts/validar-palavra-de-tela.py` declara
   alcance estreito (só o `main.glade`, `:12-17`), e esta seção é montada em
   Python: sem este arquivo, o texto dela não tem portão nenhum.

Por que não há id de Glade aqui: a aba Configurações reserva só o container no
XML (F1 da leva) e cada seção monta os próprios widgets. Cobrar id de Glade
seria cobrar um desenho que a leva descartou.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`. `importorskip("gi")`
# aceita o stub que outro arquivo planta em `sys.modules`; esta guarda não.
exigir_gi_real("selo de saúde")

import time
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import ABA_CONFIG, ConfigActionsMixin
from hefesto_dualsense4unix.app.actions.config import secao_exame as secao
from hefesto_dualsense4unix.app.constants import MAIN_GLADE
from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_ATENCAO,
    ESTADO_CERTO,
    ESTADO_NAO_SEI,
    ESTADO_PROBLEMA,
    Item,
    veredito,
)

#: As palavras que não podem chegar à tela desta seção. As três primeiras estão
#: na lista de `tests/unit/test_glade_vocabulario_leigo.py:41-60`, que só olha o
#: XML; `bluetoothctl` e `modprobe` entram porque são as duas curas que o doctor
#: imprime nesta área e que a doutrina sudo-zero não deixa repetir.
PROIBIDAS = ("sudo", "json", "systemd", "systemctl", "bluetoothctl", "modprobe")


class _Host(ConfigActionsMixin):
    def __init__(self, builder: Gtk.Builder) -> None:
        self.builder = builder


def _montar_a_aba() -> tuple[_Host, Gtk.Widget]:
    """Carrega o Glade, roda o mixin e devolve `(host, moldura da seção 0)`."""
    builder = Gtk.Builder()
    builder.add_from_file(str(MAIN_GLADE))
    host = _Host(builder)
    host.install_config_tab()
    caixa = builder.get_object(ABA_CONFIG)
    for filho in caixa.get_children():
        rotulo = filho.get_label_widget()
        if rotulo is not None and rotulo.get_text() == secao.TITULO:
            return host, filho
    raise AssertionError(f"a moldura {secao.TITULO!r} não foi montada")


def _textos(raiz: Any) -> list[str]:
    """Todo texto visível da árvore — rótulo, rótulo de botão e dica."""
    achados: list[str] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        if isinstance(widget, Gtk.Label):
            if widget.get_text():
                achados.append(widget.get_text())
        else:
            obter = getattr(widget, "get_label", None)
            if obter is not None and obter():
                achados.append(obter())
        dica = widget.get_tooltip_text()
        if dica:
            achados.append(dica)
        if isinstance(widget, Gtk.Frame) and widget.get_label_widget() is not None:
            pilha.append(widget.get_label_widget())
        filhos = getattr(widget, "get_children", None)
        if filhos is not None:
            pilha.extend(filhos())
    return achados


def _itens(estado_da_ultima: str) -> list[Item]:
    """As cinco linhas, quatro certas e a última no estado pedido."""
    linhas = secao.PainelDoExame._linhas_do_desenho()
    return [
        Item(
            chave=chave,
            rotulo=rotulo,
            estado=ESTADO_CERTO if i < len(linhas) - 1 else estado_da_ultima,
            porque="Conferido agora.",
            cura=None if i < len(linhas) - 1 else "Mude o adaptador de porta.",
        )
        for i, (chave, rotulo) in enumerate(linhas)
    ]


# --- 1. a montagem não examina ---------------------------------------------


class _ExecutorSincrono:
    """Um executor que roda o worker NA HORA, para o teste ser determinístico.

    O executor de verdade é uma thread (`ipc_bridge._get_executor`), e um teste
    que só espera "o worker provavelmente ainda não rodou" mede o escalonador,
    não o produto — é a armadilha nº 1 desta casa, o instrumento que dá alarme
    convincente e falso.
    """

    def __init__(self) -> None:
        self.submetidos: list[object] = []

    def submit(self, funcao: Any, *args: Any, **kwargs: Any) -> None:
        self.submetidos.append(funcao)
        funcao(*args, **kwargs)


def _espionar_o_exame(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Instrumenta o caminho inteiro: o executor e a função de exame.

    O executor síncrono é o que fecha as duas portas de uma vez: uma chamada
    direta a `exame()` na montagem é anotada na hora, e uma chamada de dentro
    de um worker também, porque o worker roda antes de `submit` voltar.

    O que a espiã NÃO faz é vigiar quem submete: o executor é compartilhado com
    as outras seções da aba, e reprovar por trabalho alheio seria um portão
    acusando o vizinho.
    """
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.integrations import exame_da_mesa

    chamadas: list[str] = []
    monkeypatch.setattr(ipc_bridge, "_get_executor", _ExecutorSincrono)
    monkeypatch.setattr(
        exame_da_mesa,
        "exame",
        lambda **_k: (chamadas.append("exame"), [])[1],
    )
    return chamadas


def test_a_montagem_nao_dispara_o_exame(monkeypatch: pytest.MonkeyPatch) -> None:
    """E6 da leva, e é o que impede a foto de publicar a máquina dela.

    A montagem roda no arranque da janela, e o `retratar_abas.py` percorre
    exatamente esse caminho para gerar os PNGs de `docs/usage/assets/`.

    Mordida verificada em 22/08/2026: acrescentei `painel.reexaminar()` ao fim
    de `montar()` e este teste reprovou com
    `AssertionError: a montagem leu a máquina: ['exame']`.
    """
    chamadas = _espionar_o_exame(monkeypatch)

    _montar_a_aba()

    assert not chamadas, f"a montagem leu a máquina: {chamadas}"


def test_o_instrumento_deste_arquivo_de_fato_pega_o_exame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A régua contra si mesma: chamado o refresher, a espiã TEM de acusar.

    Sem esta, o teste acima passaria numa espiã quebrada — que é exatamente
    como um portão dá verde sem nunca ter medido nada.
    """
    host, _moldura = _montar_a_aba()
    chamadas = _espionar_o_exame(monkeypatch)

    getattr(host, secao.NOME_DO_REFRESH)()

    assert chamadas == ["exame"]


def test_a_secao_pendura_o_refresher_no_hospedeiro() -> None:
    """A costura da aba chama pelo nome; sem o atributo, ela não chama nada.

    O nome é a constante `NOME_DO_REFRESH`, e não um literal repetido nos dois
    lados — repetir é como um refresher nasce morto em silêncio nesta casa
    (BUG-GUI-EMULATION-HANDLERS-UNWIRED-01).
    """
    host, _moldura = _montar_a_aba()

    assert callable(getattr(host, secao.NOME_DO_REFRESH, None))


def test_o_selo_nasce_dizendo_que_ainda_nao_examinou() -> None:
    """Sem exame na montagem, o topo não pode afirmar nada."""
    _host, moldura = _montar_a_aba()

    assert any(secao.FRASE_ANTES_DO_EXAME in t for t in _textos(moldura))


def test_a_secao_tem_o_botao_e_as_cinco_linhas() -> None:
    _host, moldura = _montar_a_aba()
    textos = _textos(moldura)

    assert secao.ROTULO_DO_BOTAO in textos
    for _chave, rotulo in secao.PainelDoExame._linhas_do_desenho():
        assert any(rotulo in t for t in textos), f"a linha {rotulo!r} não foi montada"


# --- 2. o selo verde não convive com linha vermelha -------------------------


def test_um_problema_pinta_o_topo_de_vermelho() -> None:
    """A MORDIDA desta tela: o selo do topo segue o pior item, sempre.

    Mordida verificada em 22/08/2026: troquei o `selo` que `aplicar` recebe por
    `ESTADO_CERTO` fixo — que é a forma exata de a tela voltar a ensinar que
    verde e vermelho juntos são normais — e este teste reprovou com
    `assert '#ff5555' in '<span foreground="#50fa7b" weight="bold">●</span>
    <b>Pronto para jogar</b>'`, junto com os dois vizinhos.
    """
    host, _moldura = _montar_a_aba()
    painel = host._painel_do_exame
    itens = _itens(ESTADO_PROBLEMA)

    painel.aplicar(itens, veredito(itens), time.time())

    topo = painel.selo.get_label()
    assert secao.COR[ESTADO_PROBLEMA] in topo
    assert secao.COR[ESTADO_CERTO] not in topo
    assert secao.FRASE_DO_SELO[ESTADO_PROBLEMA] in painel.selo.get_text()
    # E a linha ruim está mesmo vermelha — sem isto o teste passaria numa tela
    # que pinta tudo de vermelho e não mede nada.
    ultima = painel.linhas["vizinhanca_das_portas"]
    assert secao.COR[ESTADO_PROBLEMA] in ultima.get_label()


def test_uma_atencao_pinta_o_topo_de_laranja_e_nao_de_verde() -> None:
    """F2 da leva: atenção é LARANJA `@orange`, o token de alerta da casa."""
    host, _moldura = _montar_a_aba()
    painel = host._painel_do_exame
    itens = _itens(ESTADO_ATENCAO)

    painel.aplicar(itens, veredito(itens), time.time())

    assert secao.COR[ESTADO_ATENCAO] in painel.selo.get_label()
    assert secao.COR[ESTADO_CERTO] not in painel.selo.get_label()


def test_tudo_certo_ganha_o_sinal_de_conferido_em_verde() -> None:
    """E2 da leva: o glifo U+2713 colorido, sem bola em volta."""
    host, _moldura = _montar_a_aba()
    painel = host._painel_do_exame
    itens = _itens(ESTADO_CERTO)

    painel.aplicar(itens, veredito(itens), time.time())

    assert secao.COR[ESTADO_CERTO] in painel.selo.get_label()
    assert painel.selo.get_text().startswith(secao.GLIFO[ESTADO_CERTO])

    # CORRIGIDO em 26/08/2026, e o que mudou foi o PRODUTO, não o teste.
    # Esta linha exigia a frase FIXA `FRASE_DO_SELO[ESTADO_CERTO]` ("Pronto
    # para jogar"). Com a ORDEM-DE-SERVICO-01 o selo passa a repetir o texto do
    # CABEÇALHO quando os dois concordam no estado — e o do cabeçalho CONTA
    # ("Nada a mudar. Conferi 5 coisas agora."), que diz mais do que a frase
    # fixa dizia. Exigir a fixa aqui travaria a contagem.
    texto = painel.selo.get_text()
    assert any(str(n) in texto for n in (len(itens),)), (
        f"o selo verde deixou de contar o que conferiu: {texto!r}"
    )


def test_uma_linha_nao_medida_impede_o_verde_do_topo() -> None:
    """Quatro verdes e um "não sei" não é "Pronto para jogar"."""
    host, _moldura = _montar_a_aba()
    painel = host._painel_do_exame
    itens = _itens(ESTADO_NAO_SEI)

    painel.aplicar(itens, veredito(itens), time.time())

    assert secao.FRASE_DO_SELO[ESTADO_CERTO] not in painel.selo.get_text()


# --- 3. o vocabulário da seção ---------------------------------------------


def test_nenhum_texto_da_secao_montada_carrega_jargao_de_terminal() -> None:
    _host, moldura = _montar_a_aba()

    achados = [
        f"{texto!r} contém {palavra!r}"
        for texto in _textos(moldura)
        for palavra in PROIBIDAS
        if palavra in texto.lower()
    ]

    assert not achados, "jargão de terminal na seção do exame:\n  " + "\n  ".join(
        achados
    )


def test_nem_depois_do_exame_com_todas_as_curas_na_tela() -> None:
    """O que o `validar-palavra-de-tela.py` não alcança: o texto de RUNTIME.

    As curas do doctor para estas mesmas cinco checagens são cheias de `sudo`
    (`scripts/doctor.sh:2259`, `:3227`). Este teste roda as cinco checagens de
    verdade, em bancada falsa forçada ao pior caso, e exige que o que chega à
    tela esteja limpo — dica, porquê e cura.
    """
    from hefesto_dualsense4unix.integrations import exame_da_mesa

    host, moldura = _montar_a_aba()
    itens = [
        exame_da_mesa.energia_do_radio(
            parametro=_arquivo_inexistente(), conf=_arquivo_inexistente()
        ),
        exame_da_mesa.energia_das_portas(raiz=_arquivo_inexistente()),
        exame_da_mesa.pareamentos(executar=lambda _a: None),
        exame_da_mesa.suporte_ao_controle(
            modulos=_arquivo_inexistente(),
            diretorio_do_modulo=_arquivo_inexistente(),
        ),
        exame_da_mesa.vizinhanca_das_portas(leitura=lambda: [("a", "b")]),
    ]

    host._painel_do_exame.aplicar(itens, veredito(itens), time.time())

    achados = [
        f"{texto!r} contém {palavra!r}"
        for texto in _textos(moldura)
        for palavra in PROIBIDAS
        if palavra in texto.lower()
    ]

    assert not achados, "jargão de terminal depois do exame:\n  " + "\n  ".join(achados)


def _arquivo_inexistente() -> Any:
    """Um caminho que não existe — força cada checagem ao ramo pessimista."""
    from pathlib import Path

    return Path("/nao-existe/hefesto/exame-da-mesa")


def test_o_carimbo_envelhece_com_o_exame() -> None:
    """"Agora mesmo" só vale agora; um exame de três minutos atrás diz isso."""
    assert secao.frase_de_quando(0.0) == "Agora mesmo"
    assert secao.frase_de_quando(60.0) == "Há 1 minuto"
    assert secao.frase_de_quando(190.0) == "Há 3 minutos"
    assert secao.frase_de_quando(7200.0) == "Há mais de uma hora"


def test_o_escopo_desta_tela_esta_escrito() -> None:
    """E5 da leva: duas telas de saúde na janela, cada uma dizendo a sua.

    A aba Sistema tem o cartão do daemon e do storm; esta responde se dá para
    jogar. Sem a frase, a pessoa tem de adivinhar qual das duas olhar.
    """
    _host, moldura = _montar_a_aba()

    assert any(secao.ESCOPO in texto for texto in _textos(moldura))
