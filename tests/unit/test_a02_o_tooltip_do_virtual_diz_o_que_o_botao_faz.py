"""O `title` do "Virtual" MENTIA, e a medição da leva anterior o provou."""

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

_SIMETRIA = "soar igual " + "no cabo e no rádio"

_FONTE_PROPRIA = "cria uma fonte de " + "áudio própria"


def _titulo_do_virtual(html: str) -> str:
    """O `title` do botão Virtual, lido da PÁGINA e não da constante."""
    achado = re.search(
        r'data-mic-modo="virtual"[^>]*?\n?\s*title="([^"]*)"', html, re.S
    )
    assert achado, "não achei o botão Virtual com `title` na página publicada"
    return achado.group(1)


def test_o_tooltip_nao_promete_mais_a_simetria_entre_os_transportes() -> None:
    """A promessa que o mapa contradiz não pode voltar à tela."""
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
    """Dois botões, dois caminhos — e o texto diz qual é qual."""
    titulo = _titulo_do_virtual(PUBLICADA.read_text(encoding="utf-8"))
    assert "🎙" in titulo, (
        f"o `title` do Virtual não diz quem põe o microfone no ar: {titulo!r}"
    )
    assert "no ar" in titulo, (
        f"o `title` não diz o que o 🎙 faz, só que ele existe: {titulo!r}"
    )


def test_o_tooltip_nao_confessa_divida() -> None:
    """Regra dela, 07/09/2026: a tela nunca confessa dívida NOSSA."""
    titulo = _titulo_do_virtual(PUBLICADA.read_text(encoding="utf-8")).lower()
    for confissao in ("ainda não", "por enquanto", "não funciona", "falta ",
                      "em breve", "não suportado", "limitação"):
        assert confissao not in titulo, (
            f"o `title` do Virtual confessa dívida nossa ({confissao!r}): {titulo!r}"
        )


def test_o_gesto_do_modo_nao_faz_o_ato_do_microfone(monkeypatch) -> None:
    """O FATO que o texto descreve, medido no gesto — e é a trava de verdade."""
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
    monkeypatch.setattr(a02, "_controles_declarados", lambda **_: {})
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
    """O texto novo está nos QUATRO cartões, e veio do gerador."""
    import aba02

    html = PUBLICADA.read_text(encoding="utf-8")
    assert html.count(aba02.DICA_MIC_VIRTUAL) == 4, (
        "o `title` do gerador não é o da página publicada nos quatro cartões — "
        "a árvore ficou internamente incoerente"
    )
    assert html.count(aba02.DICA_MIC_NATIVO) == 4
