"""O quadro "Modo" saiu da aba Perfis — e o que o perfil guarda ficou.

**ESTA RÉGUA INVERTEU EM 11/09/2026, por ordem dela:**

    "em perfis ainda aparece modo. Isso deve aparecer só na aba jogar."

O QUE ELA COBRAVA ANTES, e cobrava certo: o gesto `a10_perfis.editor_modo`
nasceu em 06/09 (`PERFIL-MODO-01`) porque a linha 384 do CSV da paridade tinha o
veredito mais duro da aba — *"NÃO EXISTE — nem na página, nem no pacote"* —, e
esta régua provava que os quatro botões gravavam o que prometiam.

**A ORDEM DELA REVOGA A EXIGÊNCIA, NÃO O DADO**, e essa distinção é o assunto
inteiro deste arquivo:

* o QUADRO sai da tela, o GESTO sai do pacote — nada na página o alcançava mais,
  e gesto sem clique é o "campo morto com nome de promessa";
* `Profile.mode` **fica**: no esquema, no disco e no `ativar`. Um perfil que já
  diz «Jogar pelo Hefesto» continua dizendo;
* quem EDITA passa a ser só a aba Jogar, e quem GRAVA o que ela escolhe lá é
  o daemon, depois do aparelho (`Daemon.gravar_o_modo_escolhido`, desde a
  O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01, 29/09/2026), pela regra do dono
  (`manager.secao_do_modo_com_o_caminho`), que nunca foi da aba 10.

**O RISCO REAL DE UMA RETIRADA DE TELA É O DADO MORRER JUNTO**, em silêncio: os
gestos que sobraram no editor gravam o perfil **INTEIRO**, e um deles que
reconstruísse o `Profile` sem a seção apagaria o modo dela na primeira vez que
ela renomeasse um perfil. Não haveria tela para mostrar isso — o campo é
invisível nesta aba agora. É o que a §2 mede, gesto por gesto.

**E O PERFIL NOVO PRECISAVA DE UMA DECISÃO**, porque a tela deixou de ter onde
perguntar: ele nasce **sem a seção** — «Não mexer no modo», o perfil sem opinião
—, que é o único valor que preserva o comportamento de antes do quadro. A §3
amarra essa decisão.

A IRMÃ DESTA RÉGUA é
`tests/unit/test_o_quadro_do_modo_nao_descreve_o_que_perde.py`, e a divisão é de
assunto: lá a TELA (as quatro marcas do quadro não estão nas duas páginas); aqui
o DADO.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.perfis_web`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import secao_do_modo_com_o_caminho
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    PROCEDENCIA_DE_QUALQUER_JOGO,
)

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True},
]


class PonteDeMentira:
    """Anota, e não fala com o daemon dela. Sabe RECUSAR (ver `falha`)."""

    def __init__(self, falha: bool = False) -> None:
        self.chamadas: list[str] = []
        self.falha = falha

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
        return not self.falha

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"chamar:{metodo}")
        return not self.falha

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"resultado:{metodo}")
        if self.falha:
            raise RuntimeError("o dublê recusou")
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de MÓDULO herdado de outro teste não é prova de nada."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_CARONA_PENDENTE", "", raising=False)


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Um perfil na "pasta". O que o gesto gravar fica AQUI, não em `~/.config`."""
    guardado: dict[str, Any] = {
        "perfil": Profile(name="Pragmata", match=MatchAny(), priority=40),
        "salvos": [],
        "apagados": [],
    }

    def _load_all(*a: Any, **kw: Any) -> list[Profile]:
        return [guardado["perfil"]]

    def _load(nome: str, *a: Any, **kw: Any) -> Profile:
        if nome != guardado["perfil"].name:
            raise FileNotFoundError(nome)
        return guardado["perfil"].model_copy(deep=True)

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


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": None}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


def test_a_aba_perfis_nao_tem_mais_gesto_de_modo() -> None:
    """Ordem dela, 11/09/2026 — e a queda se mede nos DOIS lugares."""
    assert not hasattr(a10_perfis, "editor_modo"), (
        "`a10_perfis.editor_modo` voltou — o quadro «Modo» saiu do editor de "
        "Perfis por ordem dela em 11/09/2026, e um gesto que nenhum clique "
        "alcança é o campo morto com nome de promessa")
    inscritos = {nome for (pagina, nome) in pacotes.GESTOS if pagina == PAGINA}
    assert "editor.modo" not in inscritos, (
        f"`editor.modo` continua inscrito na tabela de gestos de {PAGINA} — o "
        f"piloto o ofereceria a um botão que a página não tem mais")
    assert len(inscritos) == a10_perfis.PISO_DA_ABA, (
        f"o piso da aba diz {a10_perfis.PISO_DA_ABA} e há {len(inscritos)} "
        f"gestos inscritos — o número é o que pega uma queda SEM dono, e uma "
        f"folga nele apaga exatamente isso")


def test_a_chave_do_modo_esta_declarada_sem_endereco() -> None:
    """O dono do DADO continua publicando; a tela é que deixou de ter onde pôr."""
    assert "editor.modo" in a10_perfis.SEM_ENDERECO, (
        "`editor.modo` deixou de ser declarado em `SEM_ENDERECO` — ou ele "
        "voltou a ter endereço (e aí a decisão dela mudou), ou a chave passou a "
        "cair no vazio sem ninguém saber")
    razao = a10_perfis.SEM_ENDERECO["editor.modo"]
    assert "Jogar" in razao and "11/09" in razao, (
        f"a razão declarada não diz para onde o quadro foi nem quando: {razao!r}")


def _renomear(ctx: Contexto, ponte: Any) -> None:
    a10_perfis.editor_nome(ctx, {"valor": "Sackboy", "evento": "change"}, ponte)


def _prioridade(ctx: Contexto, ponte: Any) -> None:
    a10_perfis.editor_prioridade(ctx, {"valor": "137", "evento": "change"}, ponte)


def _ambiente(ctx: Contexto, ponte: Any) -> None:
    a10_perfis.editor_ambiente(
        ctx, {"valor": PROCEDENCIA_DE_QUALQUER_JOGO, "evento": "change"}, ponte)


def _jogo(ctx: Contexto, ponte: Any) -> None:
    a10_perfis.editor_jogo(ctx, {"valor": "1245620", "evento": "change"}, ponte)


@pytest.mark.parametrize("gesto,nome_do_gesto", [
    (_renomear, "editor.nome"),
    (_prioridade, "editor.prioridade"),
    (_ambiente, "editor.ambiente"),
    (_jogo, "editor.jogo"),
])
def test_o_modo_do_disco_sobrevive_aos_gestos_que_ficaram(
    disco: dict[str, Any], gesto: Any, nome_do_gesto: str
) -> None:
    """O campo ficou INVISÍVEL nesta aba — e invisível é onde o dado morre calado."""
    disco["perfil"] = disco["perfil"].model_copy(update={
        "mode": ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")})
    gesto(_ctx(), PonteDeMentira())
    guardado = disco["perfil"]
    assert guardado.mode is not None, (
        f"`{nome_do_gesto}` apagou a seção `mode` do perfil — a tela não mostra "
        f"mais esse campo, então a perda seria silenciosa até o perfil entrar")
    assert guardado.mode.kind == "gamepad", (
        f"`{nome_do_gesto}` trocou o modo do perfil para "
        f"{guardado.mode.kind!r}")
    assert guardado.mode.gamepad_flavor == "xbox", (
        f"`{nome_do_gesto}` perdeu a máscara do modo jogo — é a cicatriz de "
        f"ESCOLHA-DELA-VENCE-01/E1 pelo avesso")


def test_duplicar_leva_o_modo_junto(disco: dict[str, Any]) -> None:
    """"Copia o perfil inteiro" é literal, e o modo é parte do inteiro."""
    disco["perfil"] = disco["perfil"].model_copy(
        update={"mode": ProfileModeConfig(kind="native")})
    a10_perfis.duplicar(_ctx(), {}, PonteDeMentira())
    copia = disco["perfil"]
    assert copia.name != "Pragmata", "a cópia não nasceu"
    assert copia.mode is not None and copia.mode.kind == "native", (
        "a cópia perdeu o modo do original — a dica da tela promete o perfil "
        "INTEIRO, e o modo é parte dele")


def test_o_pacote_continua_publicando_o_modo_como_id(disco: dict[str, Any]) -> None:
    """O dono do dado não mudou, e é ele quem a aba Jogar vai ler."""
    disco["perfil"] = disco["perfil"].model_copy(
        update={"mode": ProfileModeConfig(kind="gamepad")})
    editor = perfis_web._pacote_do_editor(disco["perfil"])
    assert editor["modo"] == "gamepad"
    sem_secao = Profile(name="x", match=MatchAny())
    assert perfis_web._pacote_do_editor(sem_secao)["modo"] == "none", (
        "perfil SEM a seção `mode` deixou de sair como «Não mexer no modo» — é "
        "o caso mais comum, e é o que a aba Jogar precisa ler para acender o "
        "estado certo")


def test_o_perfil_novo_nasce_sem_opiniao_de_modo(disco: dict[str, Any]) -> None:
    """Decisão desta sprint, 11/09/2026, registrada em `a10_perfis.novo`."""
    a10_perfis.novo(_ctx(), {}, PonteDeMentira())
    criado = disco["perfil"]
    assert criado.name != "Pragmata", "o perfil novo não nasceu"
    assert criado.mode is None, (
        f"o perfil novo nasceu com modo {criado.mode!r} — sem o quadro na tela, "
        f"ela não teria como ver nem desfazer isso")


def test_a_regra_do_modo_ficou_no_dono_compartilhado() -> None:
    """`manager.secao_do_modo_com_o_caminho` é quem aplica, e nunca foi da aba 10.

    É o dono da seção `mode` que o daemon grava quando ela escolhe o modo
    (`Daemon.gravar_o_modo_escolhido`, O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01,
    29/09/2026). Até ali quem a aplicava pela janela era
    `interface/pacotes/perfil.secao_do_modo`, que saiu com o escritor da
    janela; as duas regras que ela cobrava passam a ser cobradas do dono: a
    máscara não é do modo, e nada de máscara inventada
    (ESCOLHA-DELA-VENCE-01/E1).

    AJUSTADA À REGRA DELA — MODO-DE-CONEXAO-01, 13/09/2026 (na validação). ANTES
    a segunda asserção cobrava a poda: fora do modo jogo o `gamepad_flavor` era
    zerado. AGORA cobra que ele FICA — o item 2 da regra dela na sprint: «A
    MÁSCARA vem por cima, independente do modo». Com o PS + R3 gravando a cada aperto, a volta
    pela Navegação apagava a máscara padrão do perfil em silêncio, medido.

    MORDIDA: devolva a poda (`campos["gamepad_flavor"] = None` no ramo que não é
    gamepad de `manager.secao_do_modo_com_o_caminho`) e a primeira asserção
    reprova.
    """
    atual = ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")
    virou = secao_do_modo_com_o_caminho(atual, kind="native")
    assert virou.kind == "native"
    assert virou.gamepad_flavor == "dualsense", (
        "o modo apagou a máscara padrão do perfil — a máscara não é do modo, e "
        "a volta do PS + R3 pela Navegação a perdia a cada ciclo")
    do_zero = secao_do_modo_com_o_caminho(None, kind="gamepad")
    assert do_zero.gamepad_flavor is None, (
        "a regra inventou uma máscara — `None` quer dizer «mantém a atual»")
