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
* quem EDITA passa a ser só a aba Jogar, pelo dono compartilhado
  (`interface/pacotes/perfil.secao_do_modo` e `gravar_o_modo_no_ativo`), que
  nunca foi da aba 10 e continua de pé.

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

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.app.actions.profiles_actions import _MODE_KIND_ITEMS
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis, perfil
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.profiles.simple_match import (
    PROCEDENCIA_DE_QUALQUER_JOGO,
)

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

#: A MESA — endereços MASCARADOS (octetos 4 e 5 zerados), a máscara da casa.
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
        # O RENOMEAR APAGA O ANTIGO, e o dublê tem de saber disso: sem esta
        # metade o gesto mais perigoso para um dado INVISÍVEL — o que reescreve
        # o perfil inteiro com nome novo — não chegaria a rodar, e a régua
        # ficaria verde por não ter medido.
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


# --------------------------------------------------------------------------
# 1. O GESTO SAIU, E SAIU INTEIRO
# --------------------------------------------------------------------------

def test_a_aba_perfis_nao_tem_mais_gesto_de_modo() -> None:
    """Ordem dela, 11/09/2026 — e a queda se mede nos DOIS lugares.

    O nome da função e o REGISTRO são coisas diferentes: `@gesto` inscreve o par
    `(página, nome)` numa tabela que o piloto consulta. Apagar a função e
    esquecer a inscrição deixaria a tabela apontando para o vazio; inscrever sem
    função é o inverso. As duas metades caem juntas ou a retirada é pela metade.
    """
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
    """O dono do DADO continua publicando; a tela é que deixou de ter onde pôr.

    `perfis_web._pacote_do_editor` emite `modo` porque o perfil continua
    guardando `Profile.mode` — e `perfis_web` serve mais de uma tela. O que a
    aba 10 faz é DECLARAR que não tem endereço para ele. Declarar é o que deixa
    a queda visível: sem a linha, a chave cairia no vazio calada, que é o
    defeito que `SEM_ENDERECO` existe para nomear.
    """
    assert "editor.modo" in a10_perfis.SEM_ENDERECO, (
        "`editor.modo` deixou de ser declarado em `SEM_ENDERECO` — ou ele "
        "voltou a ter endereço (e aí a decisão dela mudou), ou a chave passou a "
        "cair no vazio sem ninguém saber")
    razao = a10_perfis.SEM_ENDERECO["editor.modo"]
    assert "Jogar" in razao and "11/09" in razao, (
        f"a razão declarada não diz para onde o quadro foi nem quando: {razao!r}")


# --------------------------------------------------------------------------
# 2. O DADO FICOU — e é aqui que uma retirada de tela costuma matar
# --------------------------------------------------------------------------

def _renomear(ctx: Contexto, ponte: Any) -> None:
    a10_perfis.editor_nome(ctx, {"valor": "Sackboy", "evento": "change"}, ponte)


def _prioridade(ctx: Contexto, ponte: Any) -> None:
    a10_perfis.editor_prioridade(ctx, {"valor": "137", "evento": "change"}, ponte)


def _ambiente(ctx: Contexto, ponte: Any) -> None:
    # «QUALQUER JOGO» E NÃO UM LANÇADOR: um lançador exige o jogo no campo ao
    # lado (`simple_match.MSG_ESCOLHA_O_JOGO`), e o perfil deste dublê não o
    # tem. A recusa seria do casamento, não do funil de gravação que esta régua
    # mede.
    #
    # O RÓTULO SAI DA CONSTANTE, e não é mais a palavra "Todos": em 11/09/2026
    # o campo passou a dizer DE ONDE O JOGO VEM (C4-FUNCIONA-EM), por ordem
    # dela. Digitar a palavra aqui faria esta régua medir um rótulo que a tela
    # não oferece mais — e ela não é sobre o rótulo, é sobre o funil.
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
    """O campo ficou INVISÍVEL nesta aba — e invisível é onde o dado morre calado.

    Cada um destes gestos lê UM campo, muda UM campo e grava o perfil INTEIRO.
    Enquanto o quadro existia, um deles que perdesse a seção `mode` apareceria
    na tela no tique seguinte: os quatro botões apagariam. Sem o quadro, não há
    nada que mostre — ela só descobriria no dia em que o perfil deixasse de
    ligar o modo que ela pediu.

    MORDIDA: ponha `prof.mode = None` dentro de `a10_perfis._gravar` e os quatro
    casos reprovam nomeando o gesto.
    """
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
    """"Copia o perfil inteiro" é literal, e o modo é parte do inteiro.

    MORDIDA: troque o `model_copy` de `a10_perfis.duplicar` por um `Profile(...)`
    montado à mão com nome, regra e prioridade, e isto reprova — a cópia nasceria
    sem opinião de modo enquanto a dica na tela promete o perfil inteiro.
    """
    disco["perfil"] = disco["perfil"].model_copy(
        update={"mode": ProfileModeConfig(kind="native")})
    a10_perfis.duplicar(_ctx(), {}, PonteDeMentira())
    copia = disco["perfil"]
    assert copia.name != "Pragmata", "a cópia não nasceu"
    assert copia.mode is not None and copia.mode.kind == "native", (
        "a cópia perdeu o modo do original — a dica da tela promete o perfil "
        "INTEIRO, e o modo é parte dele")


def test_o_pacote_continua_publicando_o_modo_como_id(disco: dict[str, Any]) -> None:
    """O dono do dado não mudou, e é ele quem a aba Jogar vai ler.

    MORDIDA: troque `"modo": ...kind` por `dict(_MODE_KIND_ITEMS)[kind]` em
    `perfis_web._pacote_do_editor` e isto reprova — quem compara com um id
    passaria a comparar com a palavra dela, que muda.
    """
    disco["perfil"] = disco["perfil"].model_copy(
        update={"mode": ProfileModeConfig(kind="gamepad")})
    editor = perfis_web._pacote_do_editor(disco["perfil"])
    assert editor["modo"] == "gamepad"
    sem_secao = Profile(name="x", match=MatchAny())
    assert perfis_web._pacote_do_editor(sem_secao)["modo"] == "none", (
        "perfil SEM a seção `mode` deixou de sair como «Não mexer no modo» — é "
        "o caso mais comum, e é o que a aba Jogar precisa ler para acender o "
        "estado certo")


# --------------------------------------------------------------------------
# 3. O PERFIL NOVO — a decisão que a saída do quadro obrigou
# --------------------------------------------------------------------------

def test_o_perfil_novo_nasce_sem_opiniao_de_modo(disco: dict[str, Any]) -> None:
    """Decisão desta sprint, 11/09/2026, registrada em `a10_perfis.novo`.

    Com o quadro fora, a tela deixou de ter onde perguntar *"que modo?"* — e um
    padrão tinha de ser escolhido. É `None`: «Não mexer no modo», o perfil sem
    opinião. É o único valor que preserva o comportamento de antes do quadro,
    quando o campo não era alcançável por esta tela e todo perfil nascia assim.

    MORDIDA: ponha `mode=ProfileModeConfig(kind="gamepad")` no `Profile(...)` de
    `a10_perfis.novo` e isto reprova — um perfil recém-criado passaria a MEXER
    no modo da máquina dela sem ninguém ter pedido, que é a cicatriz do
    `or "xbox"` do Salvar da janela estável.
    """
    a10_perfis.novo(_ctx(), {}, PonteDeMentira())
    criado = disco["perfil"]
    assert criado.name != "Pragmata", "o perfil novo não nasceu"
    assert criado.mode is None, (
        f"o perfil novo nasceu com modo {criado.mode!r} — sem o quadro na tela, "
        f"ela não teria como ver nem desfazer isso")


# --------------------------------------------------------------------------
# 4. O DONO DA REGRA CONTINUA DE PÉ — é por ele que a aba Jogar escreve
# --------------------------------------------------------------------------

def test_o_perfil_sem_opiniao_e_o_primeiro_par_do_dono() -> None:
    """`MODO_SEM_OPINIAO` é o id que REMOVE a seção, e ele tem de casar com o dono.

    **ESTA RÉGUA MUDOU DE ALVO EM 11/09/2026, na conferência.** Ela perguntava a
    `perfis_web.MODO_DO_PERFIL` — uma cópia dos quatro rótulos que existia para
    o quadro «Modo» da aba Perfis. O quadro saiu por ordem dela, e a cópia ficou
    **sem um único leitor em `src/`**: os únicos que restavam eram estas
    asserções. Uma régua cujo alvo só existe para ela medir não mede o produto,
    então a cópia morreu e a pergunta passou ao DONO.

    O QUE ELA GUARDA é o que `interface/pacotes/perfil.secao_do_modo` depende:
    "none" é o primeiro par de `profiles_actions._MODE_KIND_ITEMS` — «Não mexer
    no modo» —, e é o valor com que a seção é REMOVIDA do perfil.

    MORDIDA: mova `("none", "Não mexer no modo")` para o fim de
    `_MODE_KIND_ITEMS` e isto reprova, com o id de remoção apontando para um
    modo que LIGA alguma coisa.
    """
    primeiro = next(iter(dict(_MODE_KIND_ITEMS)))
    assert primeiro == perfis_web.MODO_SEM_OPINIAO, (
        "«Não mexer no modo» deixou de ser o primeiro par do dono — é o que a "
        "MAIORIA dos perfis é, e é o id com que a seção `mode` é removida")
    assert perfil.secao_do_modo(None, primeiro) is None, (
        "o primeiro par do dono deixou de REMOVER a seção — o rótulo promete "
        "que ativar não mexe, e o arquivo diria o contrário")


def test_a_regra_do_modo_ficou_no_dono_compartilhado() -> None:
    """`pacotes/perfil.secao_do_modo` é quem aplica, e nunca foi da aba 10.

    Ela existe desde 06/09 justamente porque a seção tem UM dono e DUAS telas.
    Uma das duas saiu; a regra fica — e continua fazendo as três coisas que a
    janela estável faz: «none» remove, a máscara só vale no modo jogo, e nada de
    máscara inventada (ESCOLHA-DELA-VENCE-01/E1).

    MORDIDA: apague o `if kind != "gamepad": campos["gamepad_flavor"] = None` e
    a segunda asserção reprova, com a máscara sobrando num perfil que já não usa
    o gamepad virtual.
    """
    assert perfil.secao_do_modo(None, perfis_web.MODO_SEM_OPINIAO) is None, (
        "«Não mexer no modo» deixou de remover a seção — o rótulo promete que "
        "ativar não mexe, e o arquivo diria o contrário")
    atual = ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")
    virou = perfil.secao_do_modo(atual, "native")
    assert virou is not None and virou.kind == "native"
    assert virou.gamepad_flavor is None, (
        "o `gamepad_flavor` sobreviveu fora do modo jogo — é sobra no `.json`, "
        "e é justamente a sobra que fez a janela estável exigir Xbox")
    do_zero = perfil.secao_do_modo(None, "gamepad")
    assert do_zero is not None and do_zero.gamepad_flavor is None, (
        "a regra inventou uma máscara — `None` quer dizer «mantém a atual»")
