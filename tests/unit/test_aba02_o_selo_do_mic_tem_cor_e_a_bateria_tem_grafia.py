#!/usr/bin/env python3
"""AS DUAS DECISÕES DE 03/09/2026 na aba Controles.

**1. O SELO DO MICROFONE GANHA COR + ÍCONE.** *"Cor + ícone. Redundante de
propósito — quem lê rápido pega pela cor, quem não distingue cor pega pelo
risco."*

O DEFEITO, medido no DOM VIVO com o daemon ligado
(`scripts/ensaios/o_selo_do_mic_muda_de_cor.py`, na página PUBLICADA): a palavra
mudava e a cor não. Injetando os três valores do selo, o fundo de cada card
ficava congelado no que o gerador desenhou —

    P1  MUDO -> rgb(80, 250, 123)   ATIVO -> rgb(80, 250, 123)   — -> rgb(80, 250, 123)
    P2  MUDO -> rgb(68, 71, 90)     ATIVO -> rgb(68, 71, 90)     — -> rgb(68, 71, 90)

— o P1 dizia MUDO em VERDE e o P2 dizia ATIVO em CINZA. A causa é estrutural:
`escrever()` do piloto tem **UM alvo por elemento**, o padrão é o texto, e o
`<span>` carregava a palavra e a classe ao mesmo tempo.

**2. A BATERIA DESCONHECIDA VOLTA A `— %`.** *"— %, como a janela antiga"* —
paridade literal com a GTK, contra a harmonia interna do card. É do usuário.

AS MORDIDAS que estas réguas pegam, e as três foram feitas:

* junte os três `<span>` do selo num só — `test_o_selo_tem_tres_alvos` reprova;
* troque `data-hef-quando` por um literal digitado que divirja do dono —
  `test_o_quando_do_selo_vem_do_dono` reprova;
* faça `texto_da_bateria` redigitar a `f-string` da GTK —
  `test_a_bateria_pergunta_a_grafia_a_gtk` reprova.

O QUE ESTAS RÉGUAS **NÃO** MEDEM, de propósito: a cor em pixel e o risco
desenhado. Isso é `getComputedStyle` num motor de verdade, e quem faz é o ensaio
acima — este arquivo lê o HTML no disco, e HTML no disco não tem cor computada.
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.mesa_viva`, que carrega o GTK")

from hefesto_dualsense4unix.interface import mesa_viva, onde

PAGINA = "02-controles.html"  # (noqa-acento) nome de arquivo

UNIQ = "aa:bb:cc:00:00:02"
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]


def _card(mod, contexto, entrada: dict) -> dict:
    """O ÚNICO card que o pacote monta para esta entrada."""
    cards = mod.pacote(contexto(state={"controllers": [entrada]},
                                mesa=MESA, conectados=[entrada]))["cards"]
    assert len(cards) == 1, f"esperava um card, vieram {len(cards)}"
    return next(iter(cards.values()))


def _bancada() -> str:
    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def _selos(doc: str) -> list[str]:
    """Cada `<span class="selo-ativo…">` inteiro, até o `</span>` que o fecha."""
    fora = []
    for abre in re.finditer(r'<span class="selo-ativo[^"]*"', doc):
        i, nivel = abre.start(), 0
        for marca in re.finditer(r"<span\b|</span>", doc[abre.start():]):
            nivel += 1 if marca.group(0) == "<span" else -1
            if nivel == 0:
                fora.append(doc[i:abre.start() + marca.end()])
                break
    return fora


def test_o_selo_tem_tres_alvos() -> None:
    """A cor, o risco e a palavra são TRÊS alvos, e um elemento aceita UM."""
    selos = _selos(_bancada())
    assert selos, "não achei um `.selo-ativo` na bancada da aba Controles"

    for selo in selos:
        campo = re.search(r'data-campo="([^"]+)"', selo)
        assert campo, f"selo sem endereço nenhum: {selo[:160]}"
        enderecos = selo.count(f'data-campo="{campo.group(1)}"')
        assert enderecos == 3, (
            f"o selo de `{campo.group(1)}` tem {enderecos} endereço(s) e precisa "
            f"de 3 — a cor, o risco e a palavra. Achado: {selo[:160]}"
        )
        assert 'data-hef-alvo="classe" data-hef-classe="on"' in selo, (
            "o selo perdeu o alvo da COR. Sem ele o tique só troca a palavra, "
            "e o fundo fica no que o gerador desenhou — o defeito de 03/09."
        )
        assert 'data-hef-alvo="classe" data-hef-classe="cortado"' in selo, (
            "o selo perdeu o alvo do RISCO. Ela escolheu 'Cor + ícone' de "
            "propósito, para quem não distingue cor."
        )
        palavra = re.search(r'<span class="selo-palavra"([^>]*)>', selo)
        assert palavra is not None, "o selo perdeu o `<span>` da palavra"
        alvo = re.search(r'data-hef-alvo="([^"]*)"', palavra.group(1))
        nome_do_alvo = alvo.group(1) if alvo else ""
        assert alvo is None or alvo.group(1) == "html", (
            f"o `<span>` da palavra caiu no alvo `{nome_do_alvo}`, "
            "que não escreve texto — ele tem de ficar no alvo "
            "PADRÃO (o texto), senão a palavra para de ser escrita."
        )


def test_o_quando_do_selo_vem_do_dono() -> None:
    """O valor que acende cada classe é o que `mesa_viva.selo_do_mic` devolve."""
    doc = _bancada()
    for selo in _selos(doc):
        for classe, esperado in (("on", mesa_viva.selo_do_mic(False, True)),
                                 ("cortado", mesa_viva.selo_do_mic(True, True))):
            achado = re.search(
                rf'data-hef-classe="{classe}" data-hef-quando="([^"]*)"', selo)
            assert achado is not None, f"o selo não declara quando `{classe}` acende"
            assert achado.group(1) == esperado, (
                f"`{classe}` acende em {achado.group(1)!r} e o dono do selo diz "
                f"{esperado!r} — a régua e o produto discordam, e quem pinta é o "
                "produto"
            )


def test_o_verde_quer_dizer_uma_coisa_so() -> None:
    """Só ATIVO acende. MUDO e o travessão ficam apagados."""
    import aba02

    aceso = aba02.selo_do_microfone(False)
    apagado = aba02.selo_do_microfone(True)

    assert 'class="selo-ativo on"' in aceso, "o selo ATIVO não acende"
    assert 'class="selo-ativo"' in apagado and ' on"' not in apagado, (
        "o selo MUDO ficou aceso — verde tem de querer dizer UMA coisa só"
    )
    assert "cortado" in apagado, "o MUDO perdeu o risco sobre o microfone"
    assert "cortado" not in aceso.split("data-hef-classe")[1], (
        "o ATIVO nasceu com o risco aceso"
    )
    assert f'data-hef-classe="on" data-hef-quando="{mesa_viva.selo_do_mic(False, True)}"' \
        in aceso


def test_a_folha_pinta_as_duas_classes() -> None:
    """As classes que o produto acende existem no CSS da página."""
    doc = _bancada()
    assert ".selo-ativo.on{" in doc, (
        "a regra que ACENDE o selo sumiu — a classe seria escrita e o fundo "
        "ficaria apagado nos três estados"
    )
    assert ".mic-glifo.cortado::after{" in doc, (
        "a regra do RISCO sumiu — o glifo ganharia a classe e nada cruzaria o "
        "microfone, que é a metade da escolha dela para quem não distingue cor"
    )
    assert ".mic-glifo{" in doc and "position:relative" in doc, (
        "o glifo perdeu o `position:relative` — o `::after` do risco é absoluto "
        "e passaria a se posicionar contra outro ancestral"
    )


def test_o_selo_nao_e_escrito_a_mao_em_dois_lugares() -> None:
    """Um dono só para o selo no gerador — `aba02.selo_do_microfone`."""
    import aba02

    for alvo, nome in ((aba02.resumo_fechado, "resumo_fechado"),
                       (aba02.bloco, "bloco")):
        codigo = alvo.__code__
        assert "selo_do_microfone" in codigo.co_names, (
            f"`{nome}` não chama o dono do selo"
        )
        literais = {c for c in codigo.co_consts if isinstance(c, str)}
        literais.discard(alvo.__doc__)
        assert not any("selo-ativo" in c for c in literais), (
            f"`{nome}` voltou a montar o selo por conta própria — duas versões "
            "vivas do mesmo desenho é como a cor congelou"
        )


def test_a_bateria_pergunta_a_grafia_a_gtk() -> None:
    """As duas frases da carga saem da GTK, não de uma cópia daqui.

    O comentário que morava nesta linha afirmava *"NÃO HÁ FUNÇÃO DONA PARA
    IMPORTAR"*. É falso, e o fato foi substituído:
    `StatusActionsMixin._bateria_da_mesa` é `@staticmethod`, devolve
    `(fração, texto)` e não toca em widget nenhum.

    MORDE: faça `texto_da_bateria` redigitar a `f-string` em vez de chamar o
    dono — esta régua reprova no dia em que a GTK mudar a grafia, que é
    exatamente quando ela tem de reprovar.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
    from pacotes.a02_controles import texto_da_bateria

    assert texto_da_bateria(None) == StatusActionsMixin._bateria_da_mesa({})[1]
    for pct in (0, 1, 42, 85, 100):
        assert texto_da_bateria(pct) == StatusActionsMixin._bateria_da_mesa(
            {"battery_pct": pct})[1], f"a carga {pct} saiu fora da grafia da GTK"


def test_a_bateria_desconhecida_e_travessao_com_porcento() -> None:
    """Decisão de produto: `— %`, como a janela antiga. Paridade literal."""
    from pacotes.a02_controles import texto_da_bateria

    seco = str(mesa_viva.SEM_LEITOR)
    assert texto_da_bateria(None) != seco, (
        "a bateria desconhecida voltou ao travessão seco — ela pediu `— %`"
    )
    assert texto_da_bateria(None).startswith(seco), (
        "a frase do desconhecido deixou de começar pelo travessão"
    )
    assert texto_da_bateria(None).endswith("%")


def test_o_card_emite_a_carga_desconhecida_com_porcento() -> None:
    """E ela chega ao CARD, não só à função — o valor que o tique pinta."""
    from pacotes import Contexto
    from pacotes import a02_controles as mod

    sem_carga = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
                 "battery_pct": None, "is_primary": True, "inputs": {},
                 "audio": {}, "speaker": {}}
    com_carga = dict(sem_carga, battery_pct=85)

    for entrada, esperado in ((sem_carga, "— %"), (com_carga, "85 %")):
        assert _card(mod, Contexto, entrada)["bateria"] == esperado, (
            f"o card emitiu {_card(mod, Contexto, entrada)['bateria']!r} e a "
            f"janela antiga escreve {esperado!r}"
        )


@pytest.mark.parametrize("mudo", [True, False])
def test_o_selo_do_card_continua_saindo_do_dono(mudo: bool) -> None:
    """A palavra que o tique pinta é a do dono — a cura não mexeu nisso."""
    from pacotes import Contexto
    from pacotes import a02_controles as mod

    entrada = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
               "battery_pct": 50, "is_primary": True, "inputs": {},
               "audio": {"mic_mudo": mudo, "canal_ativo": True,
                         "canal_mudo": False},
               "speaker": {}}
    assert _card(mod, Contexto, entrada)["mic-selo"] == mesa_viva.selo_do_mic(
        mudo, True)
