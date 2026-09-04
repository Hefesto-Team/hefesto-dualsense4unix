"""A queixa 15 dela, em forma de régua — e ela é sobre uma frase INVERTIDA.

<!-- noqa-acento: citação literal dela -->
*"esse aviso nao devia aparecer pq era pra funcionar em ambos ne"*

O aviso que ela leu na aba 02, disparado pelo botão "Virtual" do microfone:

    "Só vale no rádio. Pelo cabo o microfone deste controle é uma placa de som
     USB e não passa por esta ponte — ele já funciona sem ela."

**A FÍSICA ESTAVA CERTA E A CONCLUSÃO DE PRODUTO, ERRADA.** O
`docs/data/mapa-controles.csv` diz o contrário linha por linha:

    audio.microfone         cabo_aciona=sim   radio_aciona=parcial
    audio.microfone.mudo    cabo_aciona=sim   radio_aciona=parcial

Quem é PARCIAL no microfone é o RÁDIO. A frase promovia o transporte mais fraco
e recusava o mais forte — e o que "não vale no cabo" nunca foi a feature: é uma
IMPLEMENTAÇÃO dela, a `PonteMicBluetooth`. A frase deu à ponte o nome da
capacidade.

E A MESMA TELA JÁ PROMETIA A SIMETRIA QUE O GESTO RECUSAVA: o `title` do próprio
botão "Virtual" diz *"É o que faz o mic soar igual no cabo e no rádio"*.

A DECISÃO DELA (D-12), verbatim: *"tá errado o conceito da coisa. o botão é pra
ligar o microfone e ele ser ouvido no canal específico dele."* — **é um ato só**,
e a pergunta certa nunca foi o transporte.

AS TRÊS MORDIDAS QUE ESTE ARQUIVO EXERCE
-----------------------------------------

1. **devolver `and not bool(getattr(dados, "no_cabo", False))` a
   `pode_ligar_o_mic`** — reprova `test_o_virtual_grava_no_cabo` e
   `test_o_interruptor_acende_nos_dois_transportes`;
2. **fazer o gesto copiar as duas perguntas em vez de chamar
   `pode_ligar_o_mic`** — reprova `test_o_gesto_pergunta_ao_produto`, que é o
   caso que existe porque a primeira redação desta cura fez exatamente isso e a
   mordida (1) passou VERDE;
3. **devolver a palavra "Só vale no rádio" a `DICA_MIC_NO_CABO`** — reprova
   `test_a_dica_do_cabo_e_informacao_e_nao_recusa`.
"""
from __future__ import annotations

import csv
import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.actions.config.secao_controles import (
    DICA_MIC_NO_CABO,
    DICA_MIC_NO_RADIO,
    DICA_MIC_SEM_CANAL,
    DICA_MIC_SEM_ENDERECO,
    dica_do_microfone,
    pode_ligar_o_mic,
    tem_canal_de_captura,
)

#: MAC da faixa sintética desta casa — há DOIS portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"

#: O CSV é o dono do que cada transporte aciona, e ele é lido, nunca digitado:
#: cravar "sim"/"parcial" aqui faria esta régua envelhecer calada no dia em que
#: alguém remedisse o aparelho.
CSV = RAIZ / "docs/data/mapa-controles.csv"


def _dados(**over: Any) -> SimpleNamespace:
    base = {"adotado": True, "no_cabo": False, "uniq": UNIQ,
            "endereco": "aabbcc000001"}
    base.update(over)
    return SimpleNamespace(**base)


def _linha_do_csv(chave: str) -> dict[str, str]:
    with CSV.open(newline="", encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            if linha["chave"] == chave and linha["controle"] == "dualsense":
                return linha
    raise AssertionError(f"{chave!r} sumiu do mapa-controles.csv")


# ===========================================================================
# 1. O CSV é a testemunha — e ele diz o contrário do que a frase dizia
# ===========================================================================


def test_o_csv_diz_que_quem_e_parcial_no_microfone_e_o_radio() -> None:
    """A medição que derruba a frase. Se ela mudar, esta régua muda junto."""
    for chave in ("audio.microfone", "audio.microfone.mudo"):
        linha = _linha_do_csv(chave)
        assert linha["cabo_aciona"] == "sim", (
            f"{chave}: o cabo deixou de acionar — a frase 'só vale no rádio' "
            f"voltaria a fazer sentido, e isso é notícia, não detalhe"
        )
        assert linha["radio_aciona"] == "parcial", (
            f"{chave}: o rádio deixou de ser parcial"
        )


def test_a_unica_assimetria_real_do_bloco_de_som_e_o_alto_falante() -> None:
    """A frase de transporte que SOBREVIVE, e por que ela sobrevive.

    Toda frase que condiciona o microfone ao transporte caiu nesta leva. Esta
    NÃO cai: o alto-falante por rádio é `radio_aciona=não`, com a assimetria
    declarada no próprio CSV (*"o descritor de cabo não tem report de saída de
    áudio"*, medido no aparelho dela em 11/08/2026).
    """
    linha = _linha_do_csv("audio.alto_falante")
    assert linha["radio_aciona"] == "não"
    assert linha["assimetria_declarada"].strip(), (
        "a assimetria do alto-falante perdeu a declaração — sem ela a frase de "
        "transporte que sobrou fica sem testemunha"
    )


# ===========================================================================
# 2. A regra do produto: o transporte SAIU dela
# ===========================================================================


class TestARegraDoProduto:
    def test_o_interruptor_acende_nos_dois_transportes(self) -> None:
        """MORDIDA 1: devolva `not no_cabo` a `pode_ligar_o_mic` e isto reprova."""
        assert pode_ligar_o_mic(_dados(no_cabo=False)) is True
        assert pode_ligar_o_mic(_dados(no_cabo=True)) is True, (
            "o microfone voltou a recusar no CABO, que é o transporte em que o "
            "CSV diz `cabo_aciona=sim` — é a queixa 15 dela de volta"
        )

    def test_a_pergunta_que_sobrou_e_sobre_o_canal_e_o_endereco(self) -> None:
        """As três condições, e nenhuma delas é o transporte."""
        assert tem_canal_de_captura(_dados()) is True
        assert tem_canal_de_captura(_dados(adotado=False)) is False
        assert tem_canal_de_captura(_dados(uniq="")) is False
        # O endereço não é sobre o canal: é sobre onde a escolha é GRAVADA.
        assert tem_canal_de_captura(_dados(endereco="")) is True
        assert pode_ligar_o_mic(_dados(endereco="")) is False

    def test_cada_recusa_tem_a_frase_dela(self) -> None:
        """Uma frase só para dois motivos manda a pessoa procurar a coisa errada."""
        assert dica_do_microfone(_dados(adotado=False)) == DICA_MIC_SEM_CANAL
        assert dica_do_microfone(_dados(endereco="")) == DICA_MIC_SEM_ENDERECO
        assert dica_do_microfone(_dados(no_cabo=True)) == DICA_MIC_NO_CABO
        assert dica_do_microfone(_dados(no_cabo=False)) == DICA_MIC_NO_RADIO

    def test_a_dica_do_cabo_e_informacao_e_nao_recusa(self) -> None:
        """MORDIDA 3: devolva "Só vale no rádio" e isto reprova.

        As três afirmações da frase antiga, e as três estavam erradas: a ordem
        dos transportes, o nome da capacidade (era a ponte) e o *"já funciona
        sem ela"* — pelo cabo o canal existe e nasce `SUSPENDED`, e existir não
        é ser ouvido.
        """
        baixa = DICA_MIC_NO_CABO.lower()
        for proibida in ("só vale", "não passa", "sem ela"):
            assert proibida not in baixa, (
                f"{proibida!r} voltou à dica do cabo — ela é informação sobre "
                f"por onde o canal vem, nunca recusa"
            )
        assert "já existe" in baixa


# ===========================================================================
# 3. O gesto da aba 02 — o botão que ela clicou
# ===========================================================================


class PonteDeMentira:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True
        return registrar


@pytest.fixture
def no_cabo():
    """O controle dela, NO CABO — que é onde o botão recusava."""
    import pacotes

    entrada = {"uniq": UNIQ, "transport": "usb", "connected": True,
               "inputs": {}, "audio": {}, "speaker": {}}
    return pacotes.Contexto(state={}, mesa=[], conectados=[entrada], estados={})


def _gesto(nome: str):
    import pacotes

    fn = pacotes.gesto_da_pagina("02-controles.html", nome)
    assert fn is not None, f"02-controles.html:{nome} não tem dono"
    return fn


def test_o_virtual_grava_no_cabo(no_cabo, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA 1, do lado do botão: o "Virtual" GRAVA com o controle no cabo.

    Era exatamente aqui que a frase dela aparecia. A declaração é DURÁVEL e não
    acende nada no cabo — `bt_mic.alvos()` só enxerga nós de Bluetooth —, então
    gravá-la não mente sobre som nenhum: ela vale quando o controle voltar ao
    rádio, que é a mesma natureza que o "Nativo" sempre teve.
    """
    import pacotes.a02_controles as a02

    monkeypatch.setattr(a02, "_controles_declarados", lambda **_: {})
    p = PonteDeMentira()
    _gesto("mic-modo")(no_cabo, {"uniq": UNIQ, "micModo": "virtual"}, p)

    assert p.chamadas == [
        ("machine_declare",
         ({"controles": {"aabbcc000001": {"microfone": True}}},), {})
    ], "o 'Virtual' no cabo não gravou — a recusa da queixa 15 voltou"


def test_o_gesto_pergunta_ao_produto(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA 2, e ela existe porque a primeira redação desta cura CAIU nela.

    O gesto tinha COPIADO as duas perguntas de `pode_ligar_o_mic` em vez de
    chamá-lo. Com a cópia, devolver o `not no_cabo` ao produto deixaria a janela
    ANTIGA recusando no cabo e esta ACEITANDO — duas verdades sobre o mesmo
    botão, e nenhuma régua desta casa veria. Medido: com a cópia, a mordida (1)
    passou verde.

    A régua não lê o texto do arquivo: ela troca a função do produto por uma que
    RECUSA e cobra que o gesto obedeça. Ler o fonte mediria a PALAVRA; isto mede
    o ATO.
    """
    import pacotes
    import pacotes.a02_controles as a02

    monkeypatch.setattr(a02, "_controles_declarados", lambda **_: {})
    monkeypatch.setattr(a02._mic_do_produto, "pode_ligar_o_mic", lambda _d: False)
    entrada = {"uniq": UNIQ, "transport": "usb", "connected": True}
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[entrada], estados={})

    with pytest.raises(RuntimeError):
        _gesto("mic-modo")(ctx, {"uniq": UNIQ, "micModo": "virtual"}, PonteDeMentira())


def test_o_nativo_tambem_pergunta_ao_produto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guarda vale para os DOIS botões, e antes valia só para o "Virtual".

    Declarar "Nativo" sem endereço também não tem onde pousar — a chave do
    `maquina.json` são doze hexa, e sem eles a gravação iria para um controle
    que não existe.

    O `uniq` sem um dígito hex é o caso em que `norm_mac` devolve `None`, e é o
    único em que a recusa é DAQUI. Um `uniq` com hex a menos (medido:
    `norm_mac("sem-mac")` = `"eac"`) passa por esta guarda e quem recusa é o
    DONO da chave — o validador do `maquina.py`, que exige doze hex minúsculos e
    ainda barra o endereço SINTETIZADO. Repetir aquelas duas regras aqui seria a
    segunda declaração do mesmo formato, e a que envelheceria calada.
    """
    import pacotes
    import pacotes.a02_controles as a02

    monkeypatch.setattr(a02, "_controles_declarados", lambda **_: {})
    entrada = {"uniq": "zzz", "transport": "usb", "connected": True}
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[entrada], estados={})

    with pytest.raises(RuntimeError) as erro:
        _gesto("mic-modo")(ctx, {"uniq": "zzz", "micModo": "nativo"},
                           PonteDeMentira())
    assert str(erro.value) == DICA_MIC_SEM_ENDERECO


def test_no_radio_o_virtual_continua_gravando(monkeypatch: pytest.MonkeyPatch) -> None:
    """O outro transporte não regrediu — é a metade "em ambos" da queixa dela.

    Com um controle no cabo e outro no rádio (a mesa dela em 04/09/2026), os
    DOIS botões fazem a MESMA coisa. Era essa simetria que a tela prometia no
    `title` e o gesto recusava.
    """
    import pacotes
    import pacotes.a02_controles as a02

    monkeypatch.setattr(a02, "_controles_declarados", lambda **_: {})
    entrada = {"uniq": UNIQ, "transport": "bt", "connected": True}
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[entrada], estados={})
    p = PonteDeMentira()
    _gesto("mic-modo")(ctx, {"uniq": UNIQ, "micModo": "virtual"}, p)

    assert p.chamadas == [
        ("machine_declare",
         ({"controles": {"aabbcc000001": {"microfone": True}}},), {})
    ]


def test_a_aba_02_nao_condiciona_mais_o_microfone_ao_transporte() -> None:
    """A varredura: nenhuma frase da aba recusa o microfone por transporte.

    Ela é sobre as CONSTANTES de texto do gerador e do pacote, que são o que vai
    para o `title` da tela. As frases que descrevem o que o transporte MUDA (a
    taxa do giroscópio, o perfil que o adaptador negociou) continuam — o que não
    pode voltar é a que diz que o microfone não vale num deles.
    """
    import aba02

    import pacotes.a02_controles as a02

    textos = " ".join(
        str(getattr(mod, nome))
        for mod in (aba02, a02)
        for nome in dir(mod)
        if nome.startswith(("DICA_", "ROTULO_", "TEXTO_", "SEM_"))
        and isinstance(getattr(mod, nome), str)
    ).lower()
    for proibida in ("só vale no rádio. pelo cabo o microfone",
                     "não passa por esta ponte"):
        assert proibida not in textos, (
            f"{proibida!r} voltou aos textos da aba 02 — é a frase invertida da "
            f"queixa 15 dela"
        )
