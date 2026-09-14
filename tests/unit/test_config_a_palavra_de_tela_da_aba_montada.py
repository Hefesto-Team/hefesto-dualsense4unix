"""O portão de redação da aba Configurações — sobre a aba MONTADA, não o XML.

`scripts/validar-palavra-de-tela.py` é o portão de redação desta casa, e ele
varre um arquivo só: o `main.glade` (`:60`, e o docstring declara o alcance
estreito de propósito). Isso bastou enquanto todo texto de tela morava no XML.

A aba Configurações não mora no XML. Ela é montada em código, um módulo por
seção, e a decisão é anterior a este arquivo: o Glade reserva só o container.
Consequência medida em 22/08/2026, com o andaime pronto e as seções ainda
vazias: **cem por cento do texto desta aba nasceria fora do alcance do portão
de redação** — cinco seções, mais de cem rótulos, nenhum conferido.

Portão que não alcança o texto novo é portão que envelhece sozinho. Este
arquivo é o alcance que faltava: monta a aba de verdade, anda a árvore de
widgets e aplica as MESMAS regras do validador — as do módulo, importadas dele,
nunca copiadas. Copiar as regras criaria duas listas de jargão que divergem na
primeira edição, que é o defeito que a casa já pagou.

O QUE ELE COBRA

1. **Maiúscula inicial** em todo rótulo, opção e título — inclusive dentro de
   botão segmentado, que era onde a inconsistência morava.
2. **Jargão banido** — a lista viva de `validar-palavra-de-tela.py`, que
   recusa "daemon", "uinput" e companhia.
3. **Acentuação** — texto de tela em português do Brasil, escrito certo.

A MORDIDA (verificada em 22/08/2026): pus `TITULO = "orçamento"` em
`secao_orcamento.py` e o primeiro teste reprovou pela minúscula; troquei a dica
da mesa por uma frase com "daemon" e o segundo reprovou pelo jargão.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`, como no portão
# irmão. "Pulei porque não tenho GTK" é reprovação no job `gtk-real`.
exigir_gi_real("palavra de tela da aba configurações")

import importlib.util
import sys
import unicodedata
from pathlib import Path
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from tests.unit.aba_config_sem_a_janela import (
    FOLGA_DO_AMBIENTE,
    FRASES_DO_ESPELHO,
    PISO_DA_COLHEITA,
    PISO_POR_SECAO,
    SECOES_NO_GLADE,
    HospedeiroDaAbaConfig,
    aba_config_montada,
    textos_da_arvore,
)

RAIZ = Path(__file__).resolve().parents[2]


def _validador() -> Any:
    """O `validar-palavra-de-tela.py` importado como módulo.

    Ele mora em `scripts/` e tem hífen no nome, então não é importável pelo
    caminho normal. A alternativa — copiar `JARGAO_BANIDO` para cá — criaria
    duas listas de jargão para divergirem na primeira edição.
    """
    caminho = RAIZ / "scripts" / "validar-palavra-de-tela.py"
    spec = importlib.util.spec_from_file_location("_validador_de_tela", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_validador_de_tela"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _aba_montada() -> Any:
    """Monta a aba em CÓDIGO e devolve a caixa — o berço saiu do glade.

    06/09/2026 (`GTK-3`): esta função abria o `gui/main.glade` só para pegar a
    caixa vazia `tab_config_box`; as cinco seções sempre nasceram em código. Com
    o XML apagado, o berço é `tests/unit/aba_config_sem_a_janela.py`, e ele
    entrega os DOIS widgets que as seções pedem — a caixa e o
    `daemon_autostart_switch`. A colheita foi conferida contra o glade
    restaurado do git — os dois lados deram o mesmo número —, e
    `test_o_berco_nao_e_mais_frouxo_que_o_glade` reprova se ela encolher.

    O NÚMERO SAIU DAQUI EM 08/09/2026, e o de lá também caducou. Era "199 textos
    dos dois lados"; virou 189 solto e 186 sob a suíte, pelo censo do gabinete.
    Desde 13/09/2026 o berço monta sobre uma bancada FIXA e são 190 em todo
    ambiente medido — ver `aba_config_sem_a_janela.FOLGA_DO_AMBIENTE`.

    A RAZÃO QUE ESTAVA ESCRITA AQUI TAMBÉM CAIU: dizia que a colheita cresce
    com os controles ligados, porque "Os controles" monta um card por controle.
    Medido em 08/09/2026 com QUATRO DualSense adotados, a seção montou os
    mesmos 8 textos do estado vazio — este berço não tem `_controles_leitor` e
    o pedido que sobrava era assíncrono. Desde 13/09 ele nem sai.
    """
    return aba_config_montada()


def _textos_da_arvore(raiz: Any) -> list[tuple[str, str]]:
    """Todo texto visível da árvore, como `(origem, texto)`.

    Origem é o nome do tipo do widget mais o papel do texto (rótulo, dica),
    para a mensagem de falha dizer ONDE consertar sem obrigar a caçar.
    """
    achados: list[tuple[str, str]] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        nome = type(widget).__name__
        if isinstance(widget, Gtk.Label):
            texto = widget.get_text()
            if texto:
                achados.append((f"{nome} (rótulo)", texto))
        obter_rotulo = getattr(widget, "get_label", None)
        if obter_rotulo is not None and not isinstance(widget, Gtk.Label):
            texto = obter_rotulo()
            if texto:
                achados.append((f"{nome} (rótulo)", texto))
        dica = widget.get_tooltip_text()
        if dica:
            achados.append((f"{nome} (dica)", dica))
        if isinstance(widget, Gtk.Frame):
            rotulo = widget.get_label_widget()
            if rotulo is not None:
                pilha.append(rotulo)
        obter_filhos = getattr(widget, "get_children", None)
        if obter_filhos is not None:
            pilha.extend(obter_filhos())
    return achados


def test_o_berco_nao_e_mais_frouxo_que_o_glade() -> None:
    """O berço em código entrega a MESMA aba que o `main.glade` entregava.

    06/09/2026 (`GTK-3`), e a régua nasceu de um defeito real: a primeira versão
    do berço devolvia SÓ a caixa e a aba saiu com **193 textos contra os 196**
    do XML montado no mesmo processo — `secao_janela._linha_do_espelho` devolve
    `None` sem o `daemon_autostart_switch` e a linha inteira some sem levantar.
    Três frases a menos, em silêncio, numa régua de REDAÇÃO: ela passaria com a
    frase errada dentro.

    A régua cobra as FRASES, cada MOLDURA e o TOTAL, nesta ordem — a mais
    específica primeiro, para a mensagem apontar a causa. Uma seção que sobe oca
    é também uma colheita abaixo do piso, e o total sozinho diria só "sumiu
    texto"; a moldura diz qual seção.

    O PISO É O DA BANCADA FIXA (13/09/2026). Até ali ele valia 186 e contava o
    barramento USB da máquina de quem roda, e foi assim que a suíte
    reprovou 172 contra 186 sobre o mesmo código que tinha fechado verde de
    manhã. E ele valeu 175 até 08/09, deixando passar uma seção cortada a menos
    da metade — que é o que `test_a_folga_do_piso_tem_tamanho_medido` reprova.
    Ver `aba_config_sem_a_janela.PISO_DA_COLHEITA`.
    """
    caixa = _aba_montada()
    assert len(caixa.get_children()) == SECOES_NO_GLADE, (
        f"a aba montou {len(caixa.get_children())} seções e o glade dava "
        f"{SECOES_NO_GLADE} — o berço perdeu uma seção"
    )
    colhidos = textos_da_arvore(caixa)
    for frase in FRASES_DO_ESPELHO:
        assert frase in colhidos, (
            f"a linha do espelho sumiu da aba: {frase!r} não foi colhida. É o "
            "sintoma exato de `BercoDaAbaConfig` não entregar o widget que a "
            "seção pede — a linha some sem levantar, e as três réguas desta "
            "aba passam a medir menos sem nada acusar."
        )

    # CADA MOLDURA DE PÉ TEM DE TER CONTEÚDO — 08/09/2026. O modo de falha real
    # do berço é uma seção que monta OCA: o `montar` levanta, o mixin engole, e
    # a moldura fica na tela só com o título.
    for moldura in caixa.get_children():
        rotulo = getattr(moldura, "get_label", lambda: None)() or "?"
        quantos = len(textos_da_arvore(moldura))
        assert quantos >= PISO_POR_SECAO, (
            f"a seção {rotulo!r} montou com {quantos} textos — ela subiu oca, "
            "e o total das outras quatro esconderia a causa"
        )

    assert len(colhidos) >= PISO_DA_COLHEITA, (
        f"o berço colheu {len(colhidos)} textos, abaixo do piso de "
        f"{PISO_DA_COLHEITA}: uma seção perdeu conteúdo sem esvaziar. Dê ao "
        "`BercoDaAbaConfig` o widget que ela pede, ou confira se a bancada do "
        "berço continua sendo a que o piso mediu."
    )


def test_a_folga_do_piso_tem_tamanho_medido() -> None:
    """A folga entre a colheita e o piso é a do AMBIENTE, e nada além.

    ESTA RÉGUA NASCE DE UM PISO COMPRADO, e o preço dele foi medido — 08/09/2026.
    `PISO_DA_COLHEITA` valia 175 contra uma colheita de 186 sob a suíte: onze de
    folga sem fonte declarada. Cortada a seção "Está tudo certo?" de 20 textos
    para 9, a aba caiu a exatos 175 e o arquivo inteiro deu `4 passed`, `rc=0` —
    uma seção perdendo 55% do conteúdo passava pelos DOIS pisos, porque 9 ainda
    é folgadamente maior que `PISO_POR_SECAO`.

    O que se cobra aqui é o TAMANHO da folga, e a fonte dela acabou em
    13/09/2026. Até ali eram as três frases do censo do gabinete, que só
    apareciam com o `HOME` de verdade; o berço agora fixa o gabinete e a
    bancada, e a colheita deu 190 num processo solto sob um lar vazio, 190 sob
    um lar com o produto instalado e declarado, e 190 sob a suíte. A folga é
    `FOLGA_DO_AMBIENTE`, zero.

    Por isso o piso é também o teto: texto novo na aba reprova aqui, e quem o
    pôs sobe o `PISO_DA_COLHEITA` e diz na nota dele o que entrou.
    """
    colhidos = len(textos_da_arvore(_aba_montada()))
    folga = colhidos - PISO_DA_COLHEITA

    assert folga >= 0, (
        f"a aba colheu {colhidos} textos e o piso é {PISO_DA_COLHEITA}: "
        f"faltam {-folga}. Ou sumiu texto da tela, ou o piso subiu sem a "
        "colheita subir junto."
    )
    assert folga <= FOLGA_DO_AMBIENTE, (
        f"a aba colheu {colhidos} textos contra um piso de {PISO_DA_COLHEITA}: "
        f"{folga} de folga, e o ambiente explica {FOLGA_DO_AMBIENTE} desde que o "
        "berço fixa a bancada. Folga sem fonte é piso comprado — uma seção pode "
        "perder metade do conteúdo e atravessar. Se a aba ganhou texto, suba o "
        "`PISO_DA_COLHEITA` junto e diga na nota dele o que entrou."
    )


def test_a_colheita_nao_le_o_sys_nem_pergunta_ao_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A régua mede a ABA, e não a máquina de quem roda — BERCO-SEM-A-BANCADA-01.

    A suíte de 13/09/2026 reprovou este arquivo com 172 textos contra 186 sobre
    o mesmo código que tinha fechado verde de manhã. "Conexões" lia o barramento
    USB DESTA máquina: o berço não injetava leitor nenhum, e
    `secao_mesa._PainelDaMesa` cai em `ler_a_mesa()`, `ler_o_barramento()` e
    `listar_entradas()` quando o hospedeiro não traz os seus — e em
    `ler_do_disco()` para o gabinete, sob o `HOME` de quem roda.

    Os dublês LEVANTAM, e quem acusa é a lista: `_reler_a_mesa` engole a própria
    exceção (uma leitura de `/sys` que falha não pode derrubar a troca de aba), e
    sem a lista a régua passaria com a seção vazia. O pedido ao daemon entra
    junto, porque é o mesmo desvio que o cala. E a colheita tem de continuar no
    piso com os dublês de pé: a bancada do berço não passa por nenhum deles.

    MORDIDA: tirar do `HospedeiroDaAbaConfig` os leitores da bancada — reprova
    nomeando `ler_a_mesa` e os dois `call_async`.
    """
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.app.actions.config import secao_controles, secao_mesa

    chamadas: list[str] = []

    def _que_levanta(nome: str) -> Any:
        def _duble(*_args: Any, **_kwargs: Any) -> Any:
            chamadas.append(nome)
            raise AssertionError(f"a colheita chamou {nome}")

        return _duble

    for nome in ("ler_a_mesa", "ler_o_barramento", "listar_entradas", "ler_do_disco"):
        monkeypatch.setattr(secao_mesa, nome, _que_levanta(nome))
    # `secao_controles` importa `call_async` no topo; `secao_mesa` e
    # `secao_orcamento` o buscam em `ipc_bridge` na hora da chamada.
    monkeypatch.setattr(secao_controles, "call_async", _que_levanta("call_async"))
    monkeypatch.setattr(ipc_bridge, "call_async", _que_levanta("call_async"))

    colhidos = textos_da_arvore(_aba_montada())

    assert not chamadas, (
        f"a colheita da aba passou por {chamadas}: ela está lendo a máquina de "
        "quem roda a suíte, e o piso volta a medir a bancada. Injete o leitor "
        "que falta em `HospedeiroDaAbaConfig`, no molde dos que já estão lá."
    )
    assert len(colhidos) >= PISO_DA_COLHEITA, (
        f"com os leitores vivos proibidos a aba colheu {len(colhidos)} textos, "
        f"abaixo do piso de {PISO_DA_COLHEITA}. Se as duas réguas de piso acima "
        "também reprovaram, a aba perdeu texto; se só esta, a bancada do berço "
        "passa por uma leitura que ela não devia fazer."
    )


def test_a_cor_do_plastico_nao_e_perguntada_ao_aparelho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com controle na aba, a cor do plástico vem do berço, e não do `/sys`.

    `secao_controles._PainelDosControles._perguntar_as_cores` pergunta a cada
    controle novo, e sem `_cor_do_plastico_leitor` quem responde é
    `cor_do_plastico.ler_pelo_cabo`, que procura o controle em
    `/sys/class/hidraw`. `test_config_01_a_aba_nasce_vazia` monta este berço com
    dois controles, e é por ali que se chega aqui.

    O executor roda NA HORA, como no `test_config_selo_de_saude`: esperar que
    "a thread provavelmente já rodou" mediria o escalonador, não o produto. E a
    régua confere que o caminho foi percorrido — sem as duas perguntas, ela
    passaria sem ter olhado.

    MORDIDA: tirar o `_cor_do_plastico_leitor` do berço — reprova nomeando
    `ler_pelo_cabo` duas vezes.
    """
    from hefesto_dualsense4unix.app.actions.config import secao_controles

    chamadas: list[str] = []
    perguntas: list[str] = []

    def _ler_pelo_cabo_que_levanta(uniq: str) -> Any:
        chamadas.append("ler_pelo_cabo")
        raise AssertionError(f"a aba perguntou a cor de {uniq} ao aparelho")

    def _na_hora(fn: Any, ao_chegar: Any, ao_falhar: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as exc:
            if ao_falhar is not None:
                ao_falhar(exc)
            return
        ao_chegar(resultado)

    original = secao_controles._pergunta_de_cor

    def _pergunta_contada(uniq: str, ler: Any) -> Any:
        perguntas.append(uniq)
        return original(uniq, ler)

    monkeypatch.setattr(secao_controles, "ler_pelo_cabo", _ler_pelo_cabo_que_levanta)
    monkeypatch.setattr(secao_controles, "run_in_thread", _na_hora)
    monkeypatch.setattr(secao_controles, "_pergunta_de_cor", _pergunta_contada)

    class _ComControles(HospedeiroDaAbaConfig):
        def __init__(self) -> None:
            super().__init__()
            self._controles_leitor = lambda: {
                "controllers": [
                    {
                        "uniq": "aa:bb:cc:00:00:01",
                        "connected": True,
                        "transport": "usb",
                        "player_slot": 1,
                    },
                    {
                        "uniq": "aa:bb:cc:00:00:02",
                        "connected": True,
                        "transport": "bt",
                        "player_slot": 2,
                    },
                ]
            }

    _ComControles().install_config_tab()

    assert len(perguntas) == 2, (
        f"a seção perguntou a cor de {len(perguntas)} controles, e são dois: a "
        "régua não percorreu o caminho que ela vigia"
    )
    assert not chamadas, (
        f"a aba montada no berço perguntou a cor ao aparelho: {chamadas}. É "
        "leitura de `/sys/class/hidraw` da máquina de quem roda — o berço tem de "
        "trazer o `_cor_do_plastico_leitor`."
    )


def test_todo_rotulo_da_aba_comeca_em_maiuscula() -> None:
    """Rótulo, opção e título começam com maiúscula.

    A regra vale para dentro do segmentado, que é onde a inconsistência estava
    quando o desenho foi revisado: `teclado sem fio` ao lado de `Não sei`.
    """
    fora_da_regra = []
    for origem, texto in _textos_da_arvore(_aba_montada()):
        primeira = texto.strip()[:1]
        if not primeira or not primeira.isalpha():
            continue
        if primeira.islower():
            fora_da_regra.append(f"{origem}: {texto!r}")

    assert not fora_da_regra, (
        "texto de tela começando em minúscula na aba Configurações:\n  "
        + "\n  ".join(fora_da_regra)
    )


def test_nenhum_texto_da_aba_carrega_jargao_banido() -> None:
    """A lista de jargão é a do validador — importada, não copiada."""
    banido: dict[str, str] = _validador().JARGAO_BANIDO
    achados = []
    for origem, texto in _textos_da_arvore(_aba_montada()):
        for termo, troca in banido.items():
            if termo.lower() in texto.lower():
                achados.append(f"{origem}: {texto!r} contém {termo!r} — use {troca!r}")

    assert not achados, "jargão na aba Configurações:\n  " + "\n  ".join(achados)


#: Pares em que as DUAS grafias são palavras do português, e a diferença de
#: acento é a diferença entre singular e plural — não um deslize de digitação.
#:
#: MEDIDO EM 22/08/2026, e o portão estava REPROVANDO TEXTO CERTO: a seção "A
#: mesa" diz *"o rádio **tem** 1.600 fatias de tempo por segundo"* e a seção
#: "Orçamento" diz *"gatilhos, barra de luz e giroscópio ainda não **têm** por
#: onde ser limitados"*. As duas frases estão corretas, e a heurística de
#: "mesma palavra com e sem acento" não tem como saber disso sozinha.
#:
#: Um portão que acusa de erro quem escreveu certo é pior que portão nenhum:
#: ensina a próxima pessoa a não acreditar nele, que é a lição que esta casa já
#: pagou em 13/08 com o `portao_a_casa_sabe_e_o_produto_nao_faz`. A isenção é
#: por PAR e não por palavra — isentar "tem" sozinho deixaria passar um "tem"
#: onde o certo fosse "têm".
#:
#: A lista é curta de propósito. Ela cresce quando uma frase NOVA da aba precisa
#: dela, nunca por precaução: par isento é par que este portão deixa de vigiar.
PARES_LEGITIMOS: frozenset[tuple[str, str]] = frozenset(
    {
        ("tem", "têm"),
        ("vem", "vêm"),
        ("contem", "contêm"),
        ("mantem", "mantêm"),
    }
)


def test_o_texto_da_aba_esta_acentuado() -> None:
    """Português do Brasil escrito certo, na tela como no fonte.

    A checagem é a que cabe num portão de widget: uma palavra que aparece na
    aba SEM acento, quando a mesma palavra aparece COM acento em outro ponto da
    mesma aba, é erro de digitação e não escolha. Comparar contra um dicionário
    inteiro seria o trabalho do `validar-acentuacao.py`, que já roda no fonte.

    A exceção está em `PARES_LEGITIMOS`, e ela é medida — leia lá.
    """
    palavras_com_acento: dict[str, str] = {}
    todas: list[tuple[str, str, str]] = []
    for origem, texto in _textos_da_arvore(_aba_montada()):
        for palavra in texto.replace("\n", " ").split():
            limpa = palavra.strip(".,;:!?()[]{}\"'—·").lower()
            if not limpa.isalpha() or len(limpa) < 3:
                continue
            sem_acento = "".join(
                caractere
                for caractere in unicodedata.normalize("NFD", limpa)
                if unicodedata.category(caractere) != "Mn"
            )
            if sem_acento != limpa:
                palavras_com_acento[sem_acento] = limpa
            todas.append((origem, limpa, sem_acento))

    achados = [
        f"{origem}: {palavra!r} — a mesma aba escreve "
        f"{palavras_com_acento[palavra]!r}"
        for origem, palavra, sem_acento in todas
        if palavra == sem_acento
        and palavra in palavras_com_acento
        and (palavra, palavras_com_acento[palavra]) not in PARES_LEGITIMOS
    ]

    assert not achados, (
        "a mesma palavra aparece com e sem acento na aba Configurações:\n  "
        + "\n  ".join(sorted(set(achados)))
    )
