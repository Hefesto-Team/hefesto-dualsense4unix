"""As DUAS frases que NÃO nascem, e a TERCEIRA linha, que era a dívida de verdade.

**O NOME DESTE ARQUIVO É O DA SPRINT, E ELE MEDE O CONTRÁRIO DO QUE PROMETE** —
de propósito, e a razão é uma decisão dela. A `PERFIS-O-PRECO-E-O-RADIO-01`
nasceu de três linhas do CSV da paridade, e as duas do título **caíram antes de
esta régua existir**:

* **linha 385**, *"O preço da máscara (o que o Xbox custa)"*;
* **linha 386**, *"O aviso de rádio frágil quando ela escolhe o Modo Nativo"*.

DECISÃO DELA, 05/09/2026 (10-Q6), na própria célula das duas::

    "É pra tudo funcionar independente do modo, mascarou forma de conexão.
     Essas frases devem sumir."

A dívida trocou de natureza — de TEXTO para MECANISMO: o Hefesto **constrói** o
mecanismo em vez de descrever a limitação. Construir a etiqueta do preço e o
rótulo laranja do rádio nesta aba seria executar um enunciado que ela revogou,
e por isso a §1 desta régua prova a AUSÊNCIA das duas em vez da presença.

A guarda que as barra já vive em ``interface/aba10.py`` (a metade barata, que
reprova na geração) e em
``tests/unit/test_o_quadro_do_modo_nao_descreve_o_que_perde.py`` (a completa,
que lê as constantes do dono). **Esta régua não as repete**: ela mede que a
página PUBLICADA continua sem as duas frases, que é o degrau que nenhuma das
outras duas cobre — a geração pode passar e o arquivo no disco ser de ontem.

--------------------------------------------------------------------------
A LINHA QUE SOBROU, e ela é o item 13 dela outra vez — §2 em diante
--------------------------------------------------------------------------
A **linha 370** do CSV pedia uma conferência de DADO, e a conferência achou o
defeito que ela descrevia::

    "o que está VALENDO no aparelho e ainda não foi ao disco (a cor clicada,
     por exemplo) é perdido por um gesto desta aba que grave"

MEDIDO nesta árvore em 06/09/2026, antes da cura — perfil "Pragmata" valendo,
``[0,255,128]`` no ``.json``, ``[255,0,255]`` publicado pelo daemon (a cor que
ela acabou de clicar na aba 04), e o gesto de RENOMEAR::

    no disco                (0, 255, 128)
    viva (o daemon publica) (255, 0, 255)
    gravado por editor.nome (0, 255, 128)   ← a cor dela morreu no renomear

E o estrago passa do disco: ``_gravar`` reaplica o arquivo logo em seguida
(``perfil.gravar_e_reaplicar`` → ``profile.switch``), então o gesto não só
perdia a escolha dela no ``.json`` — ele a **desfazia no controle**.

A cura é ``a10_perfis._com_o_que_esta_valendo``, que lê do DONO da sobreposição
(``rodape._draft_do_ativo``, o mesmo que o «Salvar Perfil» usa desde 01/09) em
vez de escrever uma segunda cópia dela aqui.

**A ARMADILHA QUE ESTA RÉGUA GUARDA, e ela quase virou o conserto que
reintroduz o defeito que cura:** ``DraftConfig.to_profile`` tem um portão
``mesmo_perfil`` por slug e, com um nome NOVO, zera ``match``, ``mode`` e
``suppress_desktop_emulation`` de propósito (R-11). Medido no mesmo dia::

    to_profile("Pragmata")  → difere do original em NADA
    to_profile("Sackboy")   → perde match, mode e suppress_desktop_emulation

Curar a cor pela rota ingênua teria apagado a regra que faz o perfil dela entrar
no jogo. A §3 é a régua que impede a volta disso.

**O QUE ESTA RÉGUA NÃO MEDE:** o clique chegando pela ponte JS, e o aparelho.
Ela mede o Python dos gestos com dublê de ponte e o disco desviado para memória.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig, LedsDraft
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.profiles.simple_match import PROCEDENCIA_DA_NAVEGACAO

PAGINA = "10-perfis.html"

#: A COR QUE ESTÁ NO `.json` — a de ontem.
NO_DISCO = (0, 255, 128)
#: A COR QUE O DAEMON PUBLICA — a que ela acabou de clicar na aba 04, e que
#: ainda não foi ao disco. É esta que todo gesto desta aba apagava.
VIVA = (255, 0, 255)

#: UM CONTROLE NA MESA, com endereço MASCARADO (octetos 4 e 5 zerados).
#: `lightbar_source` e `lightbar_on` não são enfeite: `rotulo_lightbar` devolve
#: a cor base como `None` sem os dois, e a sobreposição não teria o que pôr.
UNIQ = "aabbcc000001"
MESA: list[dict[str, Any]] = [
    {"pref": "p1", "uniq": UNIQ, "jogador": 1, "via": "USB",
     "transporte": "usb", "alvo": True,
     "lightbar_rgb": list(VIVA), "lightbar_on": True,
     "lightbar_source": "sysfs"},
]


class PonteDeMentira:
    """E ELA SABE RECUSAR: `profile_switch` devolve `False` quando o daemon não
    está lá, que é o caminho que o `gravar_e_reaplicar` tem de aguentar sem
    derrubar o gesto. Régua cujo dublê só sabe dizer sim não mede o caminho de
    erro — e foi um dublê assim que deixou passar um conserto que
    reintroduzia o defeito que curava."""

    def __init__(self, *, daemon_vivo: bool = True) -> None:
        self.chamadas: list[str] = []
        self._vivo = daemon_vivo

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
        return self._vivo

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"chamar:{metodo}")
        return self._vivo

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"resultado:{metodo}")
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de MÓDULO herdado de outro teste não é prova de nada — a mesma
    cicatriz de `test_aba10_o_slider_e_o_estilo_gravam`, que ficava verde
    sozinha e vermelha em lote."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO_REBAIXAR", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)


def _perfil_rico(nome: str) -> Profile:
    """Um perfil com a COR DE ONTEM no disco — e com regra e modo de verdade.

    Os três campos ricos (`match`, `mode`, `suppress_desktop_emulation`) são a
    §3: são exatamente os que o portão `mesmo_perfil` de `to_profile` zera com
    nome novo. Um perfil de `MatchAny()` não os revelaria — a régua ficaria
    verde sobre a perda.
    """
    base = Profile(
        name=nome,
        priority=40,
        match=MatchCriteria(window_title_regex="Pragmata",
                            process_name=["pragmata.exe"]),
        mode={"kind": "gamepad", "gamepad_flavor": "xbox"},  # type: ignore[arg-type]
        suppress_desktop_emulation=True,
    )
    draft = DraftConfig.from_profile(base)
    draft = draft.with_controller_leds(UNIQ, LedsDraft(
        lightbar_rgb=NO_DISCO,
        lightbar_brightness=1.0,
        player_leds=(False, False, False, False, False),
        auto_player_colors=False,
    ))
    return draft.to_profile(nome, priority=40)


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A "pasta" de perfis em memória. NADA toca `~/.config`."""
    guardado: dict[str, Any] = {
        "perfil": _perfil_rico("Pragmata"),
        "salvos": [],
        "apagados": [],
    }

    def _load_all(*a: Any, **kw: Any) -> list[Profile]:
        return [guardado["perfil"]]

    def _load(nome: str, *a: Any, **kw: Any) -> Profile:
        if nome != guardado["perfil"].name:
            raise FileNotFoundError(nome)
        return guardado["perfil"]

    def _save(prof: Profile, *a: Any, **kw: Any) -> None:
        guardado["perfil"] = prof
        guardado["salvos"].append(prof)

    def _delete(nome: str, *a: Any, **kw: Any) -> None:
        guardado["apagados"].append(nome)

    monkeypatch.setattr(loader, "load_all_profiles", _load_all)
    monkeypatch.setattr(loader, "load_profile", _load)
    monkeypatch.setattr(loader, "save_profile", _save)
    monkeypatch.setattr(loader, "delete_profile", _delete)
    a10_perfis._ESCOLHIDO = "Pragmata"
    return guardado


@pytest.fixture
def disco_de_steam(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A mesma pasta, com um perfil de JOGO DA STEAM.

    `editor.jogo` e `editor.ambiente` recusam sobre a regra rica da outra
    fixture (`ambiente_travado`, e a recusa é do produto, não da régua). Com
    `steam_game` o seletor está destravado e os dois chegam a gravar — que é o
    degrau que esta régua precisa medir neles.
    """
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    base = Profile(name="Pragmata", priority=40,
                   match=from_simple_choice("steam_game", "1599660"))
    draft = DraftConfig.from_profile(base)
    draft = draft.with_controller_leds(UNIQ, LedsDraft(
        lightbar_rgb=NO_DISCO,
        lightbar_brightness=1.0,
        player_leds=(False, False, False, False, False),
        auto_player_colors=False,
    ))
    guardado: dict[str, Any] = {
        "perfil": draft.to_profile("Pragmata", priority=40),
        "salvos": [],
        "apagados": [],
    }

    def _load_all(*a: Any, **kw: Any) -> list[Profile]:
        return [guardado["perfil"]]

    def _load(nome: str, *a: Any, **kw: Any) -> Profile:
        if nome != guardado["perfil"].name:
            raise FileNotFoundError(nome)
        return guardado["perfil"]

    def _save(prof: Profile, *a: Any, **kw: Any) -> None:
        guardado["perfil"] = prof
        guardado["salvos"].append(prof)

    monkeypatch.setattr(loader, "load_all_profiles", _load_all)
    monkeypatch.setattr(loader, "load_profile", _load)
    monkeypatch.setattr(loader, "save_profile", _save)
    a10_perfis._ESCOLHIDO = "Pragmata"
    return guardado


def _ctx(valendo: str | None = "Pragmata") -> Contexto:
    return Contexto(state={"active_profile": valendo}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


def _cor_gravada(prof: Profile) -> tuple[int, ...]:
    return tuple(DraftConfig.from_profile(prof).effective_leds_for(UNIQ)
                 .lightbar_rgb)


# --------------------------------------------------------------------------
# 1. AS DUAS FRASES NÃO NASCEM — decisão 10-Q6 dela
# --------------------------------------------------------------------------

@pytest.mark.parametrize("publicado", [False, True])
def test_o_preco_da_mascara_nao_entra_na_aba_10(publicado: bool) -> None:
    """A linha 385 do CSV, e ela fecha por AUSÊNCIA.

    A frase que a sprint mandava construir é a de
    `profiles_actions.texto_do_preco_da_mascara`. A régua PERGUNTA AO DONO qual
    é a frase de hoje em vez de digitar um pedaço dela — digitar seria a régua
    medindo o texto de ontem no dia em que a frase mudar.

    MORDIDA: cole a frase do dono no quadro Modo do `aba10.py`, gere a página, e
    isto reprova.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        texto_do_preco_da_mascara,
    )

    html = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    for sabor in ("dualsense", "xbox"):
        frase = str(texto_do_preco_da_mascara(sabor) or "").strip()
        if not frase:
            continue
        assert frase not in html, (
            f"a aba 10 voltou a escrever o preço da máscara ({sabor}) — a "
            f"decisão 10-Q6 dela tirou a frase: “Essas frases devem sumir.”")


@pytest.mark.parametrize("publicado", [False, True])
def test_o_aviso_do_radio_fragil_nao_entra_na_aba_10(publicado: bool) -> None:
    """A linha 386 do CSV, e ela fecha pela mesma ausência.

    O dono é `profiles_actions.frase_do_radio_fragil_no_modo`. Como ele devolve
    frase só sob um estado de rádio ruim, a régua o interroga com um estado que
    a produz e confere que ela não está na página.

    MORDIDA: escreva o rótulo laranja no quadro Modo e isto reprova.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        frase_do_radio_fragil_no_modo,
    )

    html = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    # `native_bt_fragil` é a chave que o daemon publica e que
    # `home_actions.texto_do_radio_fragil` lê — o gatilho do aviso genérico.
    frase = str(frase_do_radio_fragil_no_modo(
        "native", {"native_bt_fragil": True}) or "").strip()
    # A AUSÊNCIA DE FRASE NO DONO NÃO PODE VIRAR VERDE POR VACUIDADE: sem texto
    # para comparar, esta régua não mediu nada e tem de dizer.
    assert frase, (
        "`frase_do_radio_fragil_no_modo` não produziu frase para o Modo Nativo "
        "com rádio frágil — a régua passaria sem comparar nada")
    assert frase not in html, (
        "a aba 10 voltou a avisar do rádio no quadro Modo — 10-Q6: “Essas "
        "frases devem sumir.”")


# --------------------------------------------------------------------------
# 2. A LINHA 370 — o que está VALENDO sobrevive ao gesto que grava
# --------------------------------------------------------------------------

def _renomear(ctx: Contexto, ponte: Any) -> None:
    a10_perfis.editor_nome(ctx, {"valor": "Sackboy", "evento": "change"}, ponte)


def _prioridade(ctx: Contexto, ponte: Any) -> None:
    a10_perfis.editor_prioridade(ctx, {"valor": "137", "evento": "change"},
                                 ponte)


# O `_modo` SAIU DAQUI — 11/09/2026. Ordem dela: *"em perfis ainda aparece
# modo. Isso deve aparecer só na aba jogar."* O quadro «Modo» saiu do editor de
# Perfis e o gesto `a10_perfis.editor_modo` saiu com ele, porque clique nenhum
# o alcançava mais.
#
# O QUE ESTE CASO PROVAVA CONTINUA PROVADO pelos outros quatro: a linha 370 é
# sobre `_com_o_que_esta_valendo` — *todo* gesto que grava o perfil INTEIRO lê o
# que está valendo em vez do `.json`. O funil é o mesmo (`_gravar`), e quatro
# gestos o exercem. Um quinto que não existe não acrescenta cobertura; ele só
# faria a régua morrer com um `AttributeError` que não é sobre o defeito.


def _jogo(ctx: Contexto, ponte: Any) -> None:
    a10_perfis.editor_jogo(ctx, {"valor": "1245620", "evento": "change"}, ponte)


def _ambiente(ctx: Contexto, ponte: Any) -> None:
    # «NAVEGAÇÃO» E NÃO "Jogo" — C4-FUNCIONA-EM, 11/09/2026: o campo passou a
    # dizer DE ONDE O JOGO VEM, e "Jogo" era o jargão que ela mandou tirar.
    #
    # **E TEM DE SER UMA PROCEDÊNCIA DIFERENTE DA QUE O PERFIL JÁ TEM**: o
    # dublê desta régua é um perfil da Steam (`disco_de_steam`), e escolher
    # «Steam» nele não grava nada — é a guarda que impede um gesto que não
    # mudou nada na tela de reescrever a forma no disco. «Navegação» é uma
    # troca de verdade, e não passa pela pergunta do rebaixamento (ela só
    # existe para o catch-all). O que se mede aqui continua sendo o funil de
    # gravação, não o rótulo.
    a10_perfis.editor_ambiente(
        ctx, {"valor": PROCEDENCIA_DA_NAVEGACAO, "evento": "change"}, ponte)


@pytest.mark.parametrize("gesto,nome_do_gesto", [
    (_renomear, "editor.nome"),
    (_prioridade, "editor.prioridade"),
])
def test_o_gesto_que_grava_nao_apaga_a_cor_viva(
    disco: dict[str, Any], gesto: Any, nome_do_gesto: str
) -> None:
    """O item 13 dela, medido em quatro gestos.

    Cada um lê UM campo, muda UM campo e grava o perfil INTEIRO — e o inteiro
    vinha do `.json`. A cor que ela clicou na aba 04 e ainda não foi ao disco
    morria aí, e o `profile.switch` do `_gravar` a desfazia no controle logo em
    seguida.

    MORDIDA: troque `_com_o_que_esta_valendo(...)` por `load_profile(...)` no
    gesto e isto reprova com a cor de ontem — foi assim que a medição de
    06/09/2026 achou o defeito.
    """
    gesto(_ctx(), PonteDeMentira())

    assert disco["salvos"], f"{nome_do_gesto} não gravou nada"
    cor = _cor_gravada(disco["salvos"][-1])
    assert cor == VIVA, (
        f"{nome_do_gesto} gravou {cor} e a cor que está VALENDO é {VIVA} — o "
        f"gesto regrediu o perfil ao disco e apagou o clique dela na aba 04")


@pytest.mark.parametrize("gesto,nome_do_gesto", [
    (_jogo, "editor.jogo"),
    (_ambiente, "editor.ambiente"),
])
def test_os_dois_gestos_do_ambiente_tambem_nao_apagam_a_cor(
    disco_de_steam: dict[str, Any], gesto: Any, nome_do_gesto: str
) -> None:
    """Os DOIS gestos que a régua acima não alcança, e o motivo é do produto.

    `editor.jogo` e `editor.ambiente` recusam antes de gravar quando a regra do
    perfil é uma que a tela não sabe mostrar (`ambiente_travado`) — e a regra
    rica da outra fixture é exatamente uma dessas. Medir os dois num perfil de
    Steam não é afrouxar a régua: é o único perfil em que eles chegam a gravar,
    e ficar sem eles deixaria dois dos sete gestos do funil sem prova.

    MORDIDA: a mesma da régua acima, nestes dois gestos.
    """
    gesto(_ctx(), PonteDeMentira())

    assert disco_de_steam["salvos"], f"{nome_do_gesto} não gravou nada"
    cor = _cor_gravada(disco_de_steam["salvos"][-1])
    assert cor == VIVA, (
        f"{nome_do_gesto} gravou {cor} e a cor que está VALENDO é {VIVA}")


def test_a_sobreposicao_so_vale_para_o_perfil_que_esta_valendo(
    disco: dict[str, Any],
) -> None:
    """Sem perfil valendo, o disco é a verdade — e tem de continuar sendo.

    O que o daemon publica é o estado dos controles SOB o perfil ativo. Despejá-
    lo num perfil que ela edita sem ele estar valendo escreveria o estado de um
    perfil dentro do arquivo de outro: uma perda de dado NOVA no lugar da que se
    cura. É o mesmo cuidado que o `duplicar` cobra, e é por isso que a guarda é
    por slug (R-10) e não por `==`.

    MORDIDA: tire a guarda `mesmo_slug` de `_com_o_que_esta_valendo` e isto
    reprova — a cor viva vaza para um perfil que não está valendo.
    """
    _prioridade(_ctx(valendo=None), PonteDeMentira())

    assert disco["salvos"]
    cor = _cor_gravada(disco["salvos"][-1])
    assert cor == NO_DISCO, (
        f"gravou {cor} sem perfil valendo — o estado vivo de NINGUÉM entrou no "
        f"arquivo dela")


def test_o_gesto_grava_mesmo_quando_a_sobreposicao_falha(
    disco: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sobreposição é um GANHO, nunca uma condição para ela salvar.

    Se o dono não souber montar o rascunho — o daemon publicando um estado que o
    esquema recusa, que já aconteceu com o par `policy`/`custom_mult` —, a
    resposta certa é o perfil do disco, que é o comportamento de ontem. Um gesto
    dela não pode deixar de gravar o campo que ela mexeu por causa disso.

    MORDIDA: tire o `try/except` de `_com_o_que_esta_valendo` e isto vira o
    `RuntimeError` do dublê subindo pelo gesto — a tela recusaria um renomear
    por causa de um campo do daemon.
    """
    from hefesto_dualsense4unix.interface.pacotes import rodape

    def _explode(*a: Any, **kw: Any) -> Any:
        raise RuntimeError("o daemon publicou um estado que o esquema recusa")

    monkeypatch.setattr(rodape, "_draft_do_ativo", _explode)
    _prioridade(_ctx(), PonteDeMentira())

    assert disco["salvos"], "o gesto deixou de gravar porque o vivo falhou"
    assert disco["salvos"][-1].priority == 137
    assert _cor_gravada(disco["salvos"][-1]) == NO_DISCO


def test_o_daemon_calado_nao_derruba_o_gesto(disco: dict[str, Any]) -> None:
    """O dublê que sabe RECUSAR: `profile_switch` devolve `False`.

    É o caminho da máquina dela com o serviço parado, e o gesto tem de gravar
    assim mesmo — gravar é do processo da janela, reaplicar é do daemon.
    """
    _prioridade(_ctx(), PonteDeMentira(daemon_vivo=False))

    assert disco["salvos"]
    assert disco["salvos"][-1].priority == 137


# --------------------------------------------------------------------------
# 3. A ARMADILHA DO NOME NOVO — `match`, `mode` e a supressão sobrevivem
# --------------------------------------------------------------------------

def test_renomear_nao_perde_a_regra_nem_o_modo(disco: dict[str, Any]) -> None:
    """A rota ingênua da cura teria apagado a regra que faz o perfil entrar.

    `DraftConfig.to_profile` zera `match`, `mode` e `suppress_desktop_emulation`
    quando o nome pedido não é o da origem (portão `mesmo_perfil`, R-11) — e é
    deliberado lá. Por isso a sobreposição volta pelo nome ANTIGO e o renomear
    acontece DEPOIS, por `model_copy`.

    MEDIDO em 06/09/2026::

        to_profile("Pragmata")  → difere do original em NADA
        to_profile("Sackboy")   → perde match, mode e suppress

    MORDIDA: faça `_com_o_que_esta_valendo` devolver
    `draft.to_profile(nome_novo, ...)` e isto reprova em três campos de uma vez.
    """
    antes = disco["perfil"]
    _renomear(_ctx(), PonteDeMentira())

    assert disco["salvos"]
    gravado = disco["salvos"][-1]
    assert gravado.name == "Sackboy"
    assert gravado.match == antes.match, (
        f"o renomear perdeu a regra do perfil: {gravado.match!r} — o perfil "
        f"dela deixaria de entrar no jogo, calado")
    assert gravado.mode is not None and gravado.mode.kind == "gamepad", (
        f"o renomear perdeu o modo: {gravado.mode!r}")
    assert gravado.suppress_desktop_emulation is True, (
        "o renomear perdeu a supressão da emulação de desktop")
    assert gravado.priority == antes.priority, (
        f"o renomear trocou a prioridade: {gravado.priority}")
    # E A COR VIVA ENTROU JUNTO — as duas metades no mesmo gesto.
    assert _cor_gravada(gravado) == VIVA
