"""O `title` do "Virtual" MENTIA, e a medição da leva anterior o provou.

Ele prometia três coisas, e as três descreviam OUTRO botão ou coisa nenhuma:

1. *"cria uma fonte de áudio própria"* — só no RÁDIO. No cabo o filtro de
   `integrations/dualsense_bt_audio.nos_dualsense_bluetooth` exige
   ``bus == BLUETOOTH`` e descarta o nó, então `bt_mic.alvos()` não o vê e o
   clique só grava uma chave no `maquina.json`;
2. *"entrega o microfone do controle ao PC por ela"* — o gesto `mic-modo` faz
   UM `machine.declare` e mais nada. Quem chama `mic.canal.set`, elege o canal,
   escreve no firmware e manda o `0x32` é o 🎙, pelo gesto `mudo`;
3. a promessa de que o microfone soa IGUAL nos dois transportes — contradita
   pela linha `audio.microfone.mudo@dualsense` do mapa, `radio_aciona=parcial`,
   com a assimetria declarada desde 03/08/2026.

**SÃO DOIS BOTÕES, DOIS CAMINHOS**, e o `title` tem de dizer o que ESTE faz.

E O PREÇO DAQUELA FRASE JÁ FOI PAGO UMA VEZ: em 04/09/2026 ela foi usada como
PROVA para mudar o comportamento do gesto — *a frase da tela virou o
argumento*. O gesto ficou de pé por outros dois motivos; o argumento caiu.

A REGRA DELA QUE ESTE ARQUIVO TAMBÉM TRAVA (07/09/2026): **a tela nunca
confessa dívida nossa.** O texto novo diz o que o botão FAZ; o que falta mora
em `docs/data/mapa-controles.csv`.

NENHUM TESTE DESTE ARQUIVO FALA COM O DAEMON DELA. Tudo aqui é o texto do
gerador, a página publicada e o gesto com uma ponte de mentira.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PUBLICADA = (
    RAIZ / "src/hefesto_dualsense4unix/interface/paginas/02-controles.html"
)

#: A promessa que caiu, montada em PEDAÇOS de propósito. Escrevê-la inteira
#: aqui criaria a primeira ocorrência dela no repositório — é a ARMADILHA DA
#: PROSA, que esta casa já pagou cinco vezes: *um comentário que cita o padrão
#: proibido VIRA a primeira ocorrência dele*.
_SIMETRIA = "soar igual " + "no cabo e no rádio"

#: E a outra metade, pela mesma razão.
_FONTE_PROPRIA = "cria uma fonte de " + "áudio própria"


def _titulo_do_virtual(html: str) -> str:
    """O `title` do botão Virtual, lido da PÁGINA e não da constante.

    Ler a constante mediria o gerador; a pessoa lê a página. São dois lugares,
    e o defeito de 08/09 nasceu exatamente da diferença entre eles noutro
    arquivo (a afirmação valia na chamada direta e não no caminho rodado).
    """
    achado = re.search(
        r'data-mic-modo="virtual"[^>]*?\n?\s*title="([^"]*)"', html, re.S
    )
    assert achado, "não achei o botão Virtual com `title` na página publicada"
    return achado.group(1)


def test_o_tooltip_nao_promete_mais_a_simetria_entre_os_transportes() -> None:
    """A promessa que o mapa contradiz não pode voltar à tela.

    Devolva a frase ao `title` do Virtual e esta régua REPROVA.
    """
    html = PUBLICADA.read_text(encoding="utf-8")
    assert _SIMETRIA not in html, (
        "a promessa de que o microfone soa igual nos dois transportes voltou à "
        "tela — o mapa diz `radio_aciona=parcial` para `audio.microfone.mudo`"
    )
    assert _FONTE_PROPRIA not in html, (
        "a tela voltou a dizer que ESTE botão cria a fonte de áudio — quem a "
        "cria é a ponte do rádio, e só lá"
    )


def test_o_tooltip_manda_para_o_botao_que_poe_o_microfone_no_ar() -> None:
    """Dois botões, dois caminhos — e o texto diz qual é qual.

    Sem esta linha a pessoa lê "Virtual", clica, e nada vai ao ar: ela não tem
    como saber que o ato é do 🎙. Tire a menção ao 🎙 e a régua REPROVA.
    """
    titulo = _titulo_do_virtual(PUBLICADA.read_text(encoding="utf-8"))
    assert "🎙" in titulo, (
        f"o `title` do Virtual não diz quem põe o microfone no ar: {titulo!r}"
    )
    assert "no ar" in titulo, (
        f"o `title` não diz o que o 🎙 faz, só que ele existe: {titulo!r}"
    )


def test_o_tooltip_nao_confessa_divida() -> None:
    """Regra dela, 07/09/2026: a tela nunca confessa dívida NOSSA.

    Um texto que dissesse *"ainda não funciona no cabo"* seria honesto e
    proibido: o que falta mora no mapa. Ponha uma dessas palavras no `title` e
    a régua REPROVA.
    """
    titulo = _titulo_do_virtual(PUBLICADA.read_text(encoding="utf-8")).lower()
    for confissao in ("ainda não", "por enquanto", "não funciona", "falta ",
                      "em breve", "não suportado", "limitação"):
        assert confissao not in titulo, (
            f"o `title` do Virtual confessa dívida nossa ({confissao!r}): {titulo!r}"
        )


def test_o_gesto_do_modo_nao_faz_o_ato_do_microfone() -> None:
    """O FATO que o texto descreve, medido no gesto — e é a trava de verdade.

    Se alguém fizer o `mic-modo` eleger canal ou mandar `0x32`, o texto novo
    passa a ser incompleto — e esta régua avisa antes de a tela mentir de
    novo. Ela é o par da de cima: uma mede a FRASE, a outra mede o ATO.

    ARRANQUE a cura ao contrário (faça o gesto chamar `mic_canal_set_detalhado`)
    e esta régua REPROVA.
    """
    import pacotes
    import pacotes.a02_controles as a02

    class _Ponte:
        def __init__(self) -> None:
            self.chamadas: list[str] = []

        def __getattr__(self, nome: str) -> Any:
            def _chamar(*a: Any, **k: Any) -> dict[str, Any]:
                del a, k
                self.chamadas.append(nome)
                return {"status": "ok"}

            return _chamar

    uniq = "aa:bb:cc:00:00:01"
    entrada = {"uniq": uniq, "transport": "usb", "connected": True}
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[entrada], estados={})
    p = _Ponte()
    a02._controles_declarados = lambda **_: {}  # type: ignore[attr-defined]
    fn = pacotes.gesto_da_pagina("02-controles.html", "mic-modo")
    assert fn is not None, "02-controles.html:mic-modo não tem dono"
    fn(ctx, {"uniq": uniq, "micModo": "virtual"}, p)
    assert p.chamadas == ["machine_declare"], (
        "o gesto do MODO passou a fazer mais que declarar — o `title` do "
        f"Virtual deixou de descrevê-lo: {p.chamadas}"
    )
    for proibida in ("mic_canal_set_detalhado", "mic_set", "mic_volume_set"):
        assert proibida not in p.chamadas, (
            f"o gesto do modo chamou {proibida} — esse é o ato do 🎙"
        )


def test_a_pagina_publicada_e_a_que_o_gerador_emite() -> None:
    """O texto novo está nos QUATRO cartões, e veio do gerador.

    A incoerência entre o HTML commitado e o gerador commitado já custou uma
    leva inteira nesta casa: os portões passam porque ninguém regerou.
    """
    import aba02

    html = PUBLICADA.read_text(encoding="utf-8")
    assert html.count(aba02.DICA_MIC_VIRTUAL) == 4, (
        "o `title` do gerador não é o da página publicada nos quatro cartões — "
        "a árvore ficou internamente incoerente"
    )
    assert html.count(aba02.DICA_MIC_NATIVO) == 4
