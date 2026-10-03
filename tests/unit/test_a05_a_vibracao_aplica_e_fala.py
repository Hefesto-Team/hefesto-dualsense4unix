#!/usr/bin/env python3
"""A RÉGUA DOS QUATRO SILÊNCIOS DA ABA VIBRAÇÃO — 04/09/2026.

O ENUNCIADO É DELA, e são quatro palavras — <!-- noqa-acento: literal dela -->
*"vibração nem funciona tambem"*.  <!-- noqa-acento: citação dela -->
Citação não se corrige: o que ela escreveu é o que ela escreveu.

O que estava calado, medido nesta árvore com o daemon dela vivo e dois
DualSense no cabo:

1. **A MIRA NÃO ERA CONFERIDA.** `a05_vibracao._mirar` mandava
   `controller.target.set` e jogava fora o `bool` de volta. Com o daemon mudo —
   ou só mais lento que os 250 ms do `_safe_call` — a mira falhava e o gesto
   seguia para o `rumble.set`, **que sem alvo escolhido é BROADCAST**
   (`daemon/ipc_handlers.py:3135`). O "Testar" da coluna do P2 sacudia os
   quatro controles, e a tela não dizia uma palavra. É pior que não fazer nada:
   faz na mesa inteira.
2. **AS DUAS RECUSAS DO "Testar"/"Parar" ERAM `ValueError`.** O contrato do
   piloto é explícito — `hefesto_vivo._recusou_dizendo` leva `RuntimeError` ao
   CARTÃO daquele controle e deixa `ValueError` no `stderr` de quem lançou a
   janela. As frases existiam desde 02/09 e **nunca chegaram aos olhos dela**.
3. **O `forca` GRAVAVA E VOLTAVA CALADO nos casos em que a escolha não fica.**
   `draft_config.with_controller_rumble` LIMPA o override em três casos (igual
   ao global do perfil, `policy=None`, `auto`), e a coluna sem override cai no
   `rumble_policy` da MESA: clicar "Auto" no P2 apagava o `max` dele e acendia
   "Balanceado" um tique depois — **o botão que ela clicou não é o que fica
   aceso**. A janela estável conta esse mesmo desfecho desde 25/08 (RUM-3).
4. **A MESA EM `Auto` ENGOLIA A ESCOLHA, sem uma palavra.**
   `profiles/manager._controllers_to_rumble_scales` PULA toda peça com opinião
   quando o global do perfil é `auto` (denominador móvel, com log), e o
   `a05_vibracao.SEM_DONO["forca:global-em-auto"]` dizia, desde 03/09, *"o que
   falta é a tela AVISAR"*.

O QUE ESTA RÉGUA COBRA — e cada caso traz a mordida no docstring:

* a mira recusada NÃO vira vibração, e a recusa é `RuntimeError`;
* a mira aceita chega ao par `rumble_set_checked(weak, strong)` — a prova de
  que a força chega ao motor pela porta certa;
* o `Auto` fala, com a frase que tem dono no produto;
* a mesa em `Auto` fala, no clique **e** no tempo (a linha de estado);
* a escolha que VIRA escala é silenciosa — porque uma frase por clique bem
  sucedido é ruído crônico, e ruído crônico é como um aviso deixa de ser lido.

**A PONTE É DUBLÊ, SEMPRE.** `perfil.gravar_e_reaplicar` chama
`p.profile_reaplicar(...)`, e uma ponte real mandaria isso ao daemon DELA. Todo
`uniq` daqui vem da faixa sintética `aa:bb:cc:00:00:0N` — há dois portões de
anonimato nesta árvore e eles não perdoam.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"


class PonteDeMentira:
    """Guarda o que foi pedido, na ordem. NUNCA fala com o daemon de verdade.

    `mira` decide o que `chamar("controller.target.set", …)` responde — é o
    interruptor da mordida do caso 1: com ela em `False`, o gesto tem de PARAR
    ali, e o `rumble.set` não pode aparecer nas chamadas.

    `recusas` É O DUBLÊ SABENDO RECUSAR, e ele existe porque **todo dublê tem de
    saber dizer não**: um que só responde `(True, None)` nunca exercita o
    caminho de erro, e a régua fica verde sobre a frase que ninguém leu. Ele
    mapeia o NOME da função da ponte para o par `(ok, motivo)` que ela devolve —
    e o par importa: as `*_checked` do `ipc_bridge` devolvem `(ok, motivo)`, com
    o motivo já traduzido em frase de tela. Um dublê que respondesse `False`
    seco faria a régua medir o normalizador em vez da frase.
    """

    def __init__(self, *, mira: bool = True,
                 recusas: dict[str, tuple[bool, str | None]] | None = None) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.mira = mira
        self.recusas = dict(recusas or {})

    @property
    def nomes(self) -> list[str]:
        return [n for n, _a, _k in self.chamadas]

    def chamar(self, metodo: str, **kw: Any) -> bool:
        self.chamadas.append(("chamar", (metodo,), kw))
        return self.mira if metodo == "controller.target.set" else True

    def __getattr__(self, nome: str):
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, a, k))
            if nome in self.recusas:
                return self.recusas[nome]
            return (True, None) if nome.endswith("_checked") else True
        return registrar


def _perfil_de_verdade(nome: str = "Bancada", **campos: Any) -> Any:
    """Um `Profile` DE VERDADE — o esquema é metade do que esta régua mede."""
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria"}, **campos})


@pytest.fixture
def a05():
    from pacotes import a05_vibracao

    return a05_vibracao


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira: guarda o que o gesto mandou gravar."""
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles import manager as _manager  # noqa: F401
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    # O `manager` copia `load_profile` pelo nome ao ser importado: o primeiro
    # import sob o dublê prendia o dublê nele para o resto do processo e
    # derrubava os testes seguintes (a_04). Importa-se ANTES de trocar.
    gravados: list[Any] = []
    estado: dict[str, Any] = {}

    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(
        loader, "save_profile", lambda prof, **_: gravados.append(prof),
        raising=False)

    def _pelo_gesto(_cartao, nome, muda, **_k):
        novo = muda(estado[nome])
        if novo is not None:
            estado[nome] = novo
            loader.save_profile(novo)
        return opc.JOGO, novo

    monkeypatch.setattr(opc, "gravar_pelo_gesto", _pelo_gesto)
    return estado, gravados


def _ctx(pac, *, policy_da_mesa: str = "balanceado", ativo: str = "Bancada"):
    """A mesa com UM controle, e o `rumble_policy` que o daemon publica."""
    return pac.Contexto(
        state={"active_profile": ativo, "rumble_policy": policy_da_mesa,
               "rumble_ff": {}},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
               "via": "USB", "cor": "starlight-blue"}],
        conectados=[{"uniq": UNIQ, "connected": True, "transport": "usb",
                     "index": 0, "player": 1}],
        estados={})


def _gesto(pac, nome: str):
    fn = pac.gesto_da_pagina("05-vibracao.html", nome)
    assert fn is not None, f"05-vibracao.html:{nome} perdeu o dono"
    return fn


def test_a_mira_recusada_nao_vira_vibracao_na_mesa_inteira(pac) -> None:
    """Mira que não foi = nada é mandado, e a frase diz por quê.

    É O DEFEITO MAIS CARO QUE ESTA ABA GUARDAVA. `rumble.set` e `rumble.stop`
    **não levam endereço**: quem escolhe o controle é o alvo de output, e sem
    alvo escolhido o daemon faz BROADCAST (`ipc_handlers.py:3135`). Com o
    retorno da mira jogado fora, um daemon lento fazia o "Testar" de UMA coluna
    sacudir as quatro — e o desenho promete o contrário, com todas as letras:
    *"Testar faz aquele controle tremer meio segundo"*.

    MORDIDA: em `a05_vibracao._mirar`, troque
    `if not p.chamar("controller.target.set", …)` de volta por
    `p.chamar("controller.target.set", …)` sem o `if` — este caso reprova
    porque `rumble_set_checked` volta a aparecer nas chamadas, que é o
    broadcast acontecendo.
    """
    p = PonteDeMentira(mira=False)
    with pytest.raises(RuntimeError, match="mirar"):
        _gesto(pac, "testar")(_ctx(pac), {"uniq": UNIQ, "controle": "p1"}, p)

    assert p.nomes == ["chamar"], (
        f"com a mira recusada o gesto foi adiante e chamou {p.nomes} — sem "
        f"alvo, `rumble.set` é BROADCAST e a mesa inteira treme")


def test_a_mira_aceita_leva_o_par_ao_motor(pac) -> None:
    """A prova do outro lado: mirou, o par `weak`/`strong` sai pela porta certa.

    O PAR VIAJA JUNTO, e é o contrato do daemon: `rumble.set` recebe
    `('weak', 'strong')` numa chamada só. E é a `_checked`, não a crua — a
    recusa do Modo Nativo vem no CORPO da resposta, não como erro JSON-RPC
    (NATIVO-RUMBLE-01), e foi por não a ler que a aba anunciou "vibração
    travada" com o motor parado.

    A ORDEM É O GESTO INTEIRO: mirar, vibrar, calar, devolver. Invertida, o
    passthrough soltaria antes de o silêncio ir, e o jogo ficaria mudo depois
    de um teste (SPRINT-GAME-RUMBLE-01).

    O "PARAR" GANHOU DUAS CHAMADAS EM 07/09/2026, e este caso as perdeu. O
    `rumble_stop` e o `rumble_passthrough` eram o fim do PULSO de meio segundo;
    o pulso saiu a pedido dela — *"o botão Testar tem que ficar em estado de
    ligado (…) e se eu clicar em Parar ele para de testar"* — e os dois passos
    mudaram de dono, não sumiram do produto. A queixa de origem (*"testei os
    motores e o jogo não vibra mais"*) continua coberta: quem devolve a mão ao
    jogo é o "Parar", e é o `test_o_testar_fica_ligado_e_so_o_parar_desliga`
    que o cobra.

    MORDIDA: apague o `_EM_TESTE[0] = uniq` do fim de `a05_vibracao.testar` — o
    último `assert` reprova, e o botão volta a ser um pulso mudo.
    """
    from pacotes import a05_vibracao as a05

    a05.parar_o_teste()
    p = PonteDeMentira()
    _gesto(pac, "testar")(_ctx(pac), {"uniq": UNIQ, "controle": "p1"}, p)

    assert p.nomes == ["chamar", "rumble_set_checked"], f"a ordem saiu {p.nomes}"
    _, args, _kw = p.chamadas[1]
    assert args == (160, 220), (
        f"o par que foi ao motor é {args}, e o par de teste da casa é o mesmo "
        f"da janela estável (`rumble_actions.py:817`, weak=160/strong=220)")
    assert p.chamadas[0][2] == {"index": 0}, (
        f"a mira foi para {p.chamadas[0][2]} — `controller.target.set` recebe "
        f"`index`, e o 0 é a posição deste controle na lista do daemon")
    assert a05.em_teste() == UNIQ, "o Testar não ficou ligado neste controle"
    a05.parar_o_teste()


def test_o_controle_que_saiu_da_mesa_fala_sem_dizer_o_endereco(pac) -> None:
    """Coluna cujo controle caiu: recusa que CHEGA à tela, e sem MAC na frase."""
    ctx = _ctx(pac)
    fora = {"controle": "p2"}
    with pytest.raises(RuntimeError) as recusa:
        _gesto(pac, "parar")(ctx, fora, PonteDeMentira())

    frase = str(recusa.value)
    assert "se desligou" in frase, f"a frase não diz o que houve: {frase}"
    assert "aa:bb:cc" not in frase and "aabbcc" not in frase, (
        f"a recusa publicou o endereço de rádio do aparelho: {frase}")


CLIQUE_DE_CADA_GESTO = {
    "testar": {},
    "parar": {},
    "forca": {"forca": "max"},
    "intensidade": {"valor": "120"},
    "motor": {"lado": "e", "valor": "80"},
}


@pytest.mark.parametrize("nome", sorted(CLIQUE_DE_CADA_GESTO))
def test_os_cinco_gestos_dizem_a_causa_certa(pac, nome) -> None:
    """Os CINCO donos desta aba, e nenhum deles acusa o clique dela."""
    clique = {"controle": "p2", **CLIQUE_DE_CADA_GESTO[nome]}
    p = PonteDeMentira()
    with pytest.raises(RuntimeError) as recusa:
        _gesto(pac, nome)(_ctx(pac), clique, p)

    frase = str(recusa.value)
    assert "se desligou" in frase, (
        f"{nome} recusou com {frase!r} — e o fato é que o controle daquela "
        f"coluna caiu entre o clique e agora")
    assert "não disse em qual controle" not in frase, (
        f"{nome} culpa o clique dela: {frase!r}. O clique DISSE — veio com "
        f"`controle=p2`, e a coluna existe na tela")
    assert p.chamadas == [], (
        f"{nome} recusou e falou com o daemon assim mesmo ({p.nomes}) — sem "
        f"alvo, `rumble.set` é BROADCAST")


@pytest.mark.parametrize("nome", sorted(CLIQUE_DE_CADA_GESTO))
def test_o_clique_sem_coluna_continua_dizendo_que_nao_tem_alvo(pac, nome) -> None:
    """O PAR da régua acima: sem coluna, a frase de sempre, inteira."""
    clique = {"controle": "", "uniq": "", **CLIQUE_DE_CADA_GESTO[nome]}
    p = PonteDeMentira()
    with pytest.raises(RuntimeError) as recusa:
        _gesto(pac, nome)(_ctx(pac), clique, p)

    frase = str(recusa.value)
    assert "dentro da coluna" in frase, (
        f"{nome} perdeu a instrução do clique solto — sem ela a recusa não diz "
        f"o que fazer: {frase!r}")
    assert "se desligou" not in frase, (
        f"{nome} diz que um controle caiu, e o clique não nomeou nenhum: "
        f"{frase!r}")
    assert p.chamadas == [], (
        f"{nome} recusou e falou com o daemon assim mesmo ({p.nomes})")


def test_mirar_lugar_vazio_nunca_vira_broadcast(pac, a05) -> None:
    """A guarda de `_indice` FICA, mesmo sendo inalcançável pelo piloto.

    O PILOTO NÃO CHEGA AQUI, e está medido: um `uniq` não vazio veio de
    `ctx.mesa`, e `ctx.mesa` está contida em `ctx.conectados` — então
    `Contexto.por_uniq` sempre acha. Este caso monta o clique que o piloto NÃO
    monta, de propósito e dizendo que é isso: é a guarda contra o broadcast para
    qualquer outro chamador.

    MIRAR UM LUGAR VAZIO É PIOR QUE NÃO MIRAR: o alvo de output ANTERIOR fica de
    pé, e o tremor sai na coluna errada, calado.

    MORDIDA: troque o `raise` do fim de `a05_vibracao._indice` por `return 0` —
    este caso reprova, porque a mira sai (para o controle errado) em vez de o
    gesto parar.
    """
    p = PonteDeMentira()
    with pytest.raises(RuntimeError, match="se desligou"):
        a05._mirar(_ctx(pac), {"uniq": "aa:bb:cc:00:00:09", "controle": "p9"}, p)

    assert p.chamadas == [], (
        f"a mira saiu assim mesmo ({p.nomes}) — para um `uniq` fora da mesa "
        f"isso aponta o controle ERRADO, e o tremor sai na coluna errada")


def test_o_parar_diz_o_motivo_do_daemon_e_nao_um_palpite(pac) -> None:
    """O "Parar" recusado: sobe o motivo do daemon, não a causa mais barata."""
    recusa_do_daemon = ("o Modo Nativo está no comando: o jogo fala com o motor "
                        "por fora do Hefesto")
    p = PonteDeMentira(recusas={"rumble_stop_checked": (False, recusa_do_daemon)})
    with pytest.raises(RuntimeError) as erro:
        _gesto(pac, "parar")(_ctx(pac), {"uniq": UNIQ, "controle": "p1"}, p)

    frase = str(erro.value)
    assert frase == recusa_do_daemon, (
        f"a tela disse {frase!r} e o daemon disse {recusa_do_daemon!r} — a "
        f"segunda é medida, a primeira é palpite")
    assert "rumble_stop_checked" in p.nomes, (
        f"o gesto nem chegou a pedir a parada ({p.nomes})")


def test_o_testar_diz_o_motivo_do_daemon_e_nao_um_palpite(pac) -> None:
    """A IRMÃ, e ela estava CERTA e SEM RÉGUA — medido em 05/09/2026."""
    recusa_do_daemon = ("o Modo Nativo está no comando: o jogo fala com o motor "
                        "por fora do Hefesto")
    p = PonteDeMentira(recusas={"rumble_set_checked": (False, recusa_do_daemon)})
    with pytest.raises(RuntimeError) as erro:
        _gesto(pac, "testar")(_ctx(pac), {"uniq": UNIQ, "controle": "p1"}, p)

    assert str(erro.value) == recusa_do_daemon, (
        f"a tela disse {str(erro.value)!r} e o daemon disse "
        f"{recusa_do_daemon!r} — a segunda é medida, a primeira é palpite")
    assert "rumble_stop" not in p.nomes, (
        f"o `testar` recusado seguiu adiante ({p.nomes}) — o par nunca foi ao "
        f"motor, e parar o que não começou é falar no alvo do clique seguinte")


def test_o_palpite_sobra_para_quando_o_daemon_nao_diz_nada(pac) -> None:
    """O par do caso acima: sem motivo, a frase de recurso continua inteira."""
    p = PonteDeMentira(recusas={"rumble_stop_checked": (False, None)})
    with pytest.raises(RuntimeError, match="ligue na aba Sistema"):
        _gesto(pac, "parar")(_ctx(pac), {"uniq": UNIQ, "controle": "p1"}, p)


def test_a_recusa_do_degrau_nao_oferece_botao_que_nao_existe(pac) -> None:
    """A frase do `forca` sem degrau cita os botões que EXISTEM, e só eles.

    ELA MEDIA O MUNDO DE ONTEM: mandava tentar *"em cima de um dos quatro
    botões (Economia, Balanceado, Máximo ou Auto)"*, e desde 05/09 são três — o
    `Auto` saiu da tela pela palavra dela. A tela mandando ela procurar o que
    não está lá é a mesma família de defeito que esta régua inteira persegue.

    OS NOMES NÃO SE DIGITAM AQUI, e é o ponto: eles são perguntados ao produto
    (`RUMBLE_POLICY_MULT`, que o gerador do desenho confere contra os botões da
    tela) e a `rumble_actions.ROTULOS_DO_ORCAMENTO`. Uma lista escrita neste
    arquivo seria a quarta cópia, e a quarta é a que envelhece.

    MORDIDA: devolva o `Auto` à frase de `a05_vibracao.forca` — este caso
    reprova, porque a recusa volta a oferecer um botão que não está na tela.
    """
    from hefesto_dualsense4unix.app.actions.rumble_actions import (
        ROTULOS_DO_ORCAMENTO,
    )
    from hefesto_dualsense4unix.daemon.subsystems.rumble import (
        RUMBLE_POLICY_MULT,
    )

    with pytest.raises(RuntimeError) as recusa:
        _gesto(pac, "forca")(_ctx(pac), {"uniq": UNIQ, "controle": "p1"},
                             PonteDeMentira())

    frase = str(recusa.value)
    for chave, rotulo in ROTULOS_DO_ORCAMENTO.items():
        if chave in RUMBLE_POLICY_MULT:
            assert rotulo in frase, (
                f"{rotulo!r} é um botão desta tela e a recusa não o oferece: "
                f"{frase!r}")
        else:
            assert rotulo not in frase, (
                f"a recusa manda clicar em {rotulo!r}, que não é botão desta "
                f"tela — `RUMBLE_POLICY_MULT` tem {sorted(RUMBLE_POLICY_MULT)}: "
                f"{frase!r}")
    assert "quatro" not in frase, (
        f"a frase conta os botões, e o numeral é o que envelheceu da última "
        f"vez: {frase!r}")


def test_a_forca_que_vira_escala_chega_ao_motor_e_nao_fala(
        pac, a05, disco) -> None:
    """O caso comum: a escolha vira fator, e o silêncio é o certo.

    O CAMINHO INTEIRO, e nenhum passo é novo: o override vai para
    `controllers[chave].rumble` no perfil, `_controllers_to_rumble_scales` o
    converte no fator RELATIVO ao global do perfil, `ProfileManager.apply` o
    publica com `set_rumble_scales`, e `_escalar_rumble` multiplica o que vai
    ao motor daquele handle.

    A CONTA É CONFERIDA CONTRA O PRODUTO, e não digitada aqui: `max` sobre um
    perfil sem opinião global (que o daemon lê como `balanceado`) é
    1,5 / 1,0 = 1,5 — e quem responde isso é a mesma
    `profiles/manager.fator_da_unidade` que o mapa das escalas usa.

    E ELE NÃO FALA, que é metade do valor: uma frase por clique bem sucedido é
    ruído crônico, e ruído crônico é como um aviso deixa de ser lido.

    MORDIDA: em `a05_vibracao._aplicar_a_forca`, troque o
    `if mostra != policy:` por `if True:` — este caso reprova, porque o clique
    que funcionou passa a gritar.
    """
    from hefesto_dualsense4unix.profiles.manager import (
        _controllers_to_rumble_scales,
    )

    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade()
    p = PonteDeMentira()

    _gesto(pac, "forca")(_ctx(pac), {"uniq": UNIQ, "forca": "max"}, p)

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    prof = gravados[0]
    escalas = _controllers_to_rumble_scales(prof.controllers, prof.rumble)
    assert escalas == {CHAVE: 1.5}, (
        f"o que chega ao motor é {escalas}, e devia ser o fator 1,5 do `max` "
        f"sobre o `balanceado` que o daemon assume sem opinião global. Um mapa "
        f"vazio aqui é a escolha dela guardada e ignorada — o defeito que esta "
        f"aba inteira persegue")
    assert "profile_reaplicar" in p.nomes, (
        f"gravou e não mandou reaplicar ({p.nomes}) — o perfil novo só chegaria "
        f"ao motor na próxima troca de perfil")


def test_a_mesa_em_auto_confessa_no_clique(pac, disco) -> None:
    """A escolha fica no disco e NÃO chega ao motor — e agora a tela conta.

    O MECANISMO É DO PRODUTO: com o global do PERFIL em `auto`,
    `_controllers_to_rumble_scales` pula a peça com
    `escala_de_vibracao_pulada_base_movel`, porque o denominador muda com a
    bateria a cada tique. Era o `a05_vibracao.SEM_DONO["forca:global-em-auto"]`,
    que dizia *"o que falta é a tela AVISAR"*.

    E A PROVA TEM DOIS LADOS: a escolha é gravada (ela não se perde) **e** a
    escala sai vazia (ela não chega ao motor). Sem os dois, o caso seria
    indistinguível de "não gravou".

    **E ELE DEIXOU DE SER UMA RECUSA — 04/09/2026, decisão [04] dela (D-01):**
    o gesto devolve `{"recado": …}`, porque a gravação ACONTECEU. Ver a nota em
    `_aplicar_a_forca`.

    MORDIDA: em `a05_vibracao._aplicar_a_forca`, apague as duas linhas do
    `if _fator_no_motor(...) is None:` — este caso reprova, porque o clique
    volta a ser silencioso sobre uma escolha que o motor nunca vê.
    """
    from hefesto_dualsense4unix.profiles.manager import (
        _controllers_to_rumble_scales,
    )

    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade(rumble={"policy": "auto"})

    volta = _gesto(pac, "forca")(_ctx(pac, policy_da_mesa="economia"),
                                 {"uniq": UNIQ, "forca": "economia"},
                                 PonteDeMentira())
    assert isinstance(volta, dict) and "Auto" in str(volta.get("recado") or ""), (
        f"o clique voltou a ser silencioso sobre uma escolha que o motor nunca "
        f"vê: {volta!r}")

    assert gravados, "a escolha não foi gravada — ela se perderia de vez"
    prof = gravados[0]
    assert (prof.controllers or {}).get(CHAVE) is not None, (
        "o override não ficou no perfil: com a mesa fora do Auto ele tem de "
        "voltar a valer sozinho")
    assert _controllers_to_rumble_scales(prof.controllers, prof.rumble) == {}, (
        "o produto passou a mandar escala com o global em `auto` — se isso "
        "mudou, a frase desta aba virou mentira e tem de sair")


def test_a_barra_arrastada_grava_e_o_multiplicador_chega(pac, disco) -> None:
    """A barra "Personalizado": 0 a 200%, e o número vira fator.

    A DIVISÃO POR 100 É A ÚNICA CONTA, e ela é de unidade: a tela fala em
    pontos percentuais e o perfil guarda o multiplicador (`custom_mult`, 0 a 2).

    MORDIDA: em `a05_vibracao.intensidade`, mande `custom=pontos` em vez de
    `pontos / 100` — este caso reprova na borda do esquema, porque 150 passa do
    `RUMBLE_CUSTOM_MULT_MAX`.
    """
    from hefesto_dualsense4unix.profiles.manager import (
        _controllers_to_rumble_scales,
    )

    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade()

    _gesto(pac, "intensidade")(_ctx(pac), {"uniq": UNIQ, "valor": "150"},
                               PonteDeMentira())

    prof = gravados[0]
    dele = (prof.controllers or {}).get(CHAVE)
    assert dele is not None and dele.rumble is not None
    assert dele.rumble.policy == "custom" and dele.rumble.custom_mult == 1.5, (
        f"a barra gravou {dele.rumble!r}, e 150% é `custom` com 1,5")
    assert _controllers_to_rumble_scales(prof.controllers, prof.rumble) == {
        CHAVE: 1.5}, "o multiplicador arrastado não virou escala"


def test_a_linha_de_estado_confessa_a_mesa_em_auto(a05) -> None:
    """Quem abre a aba amanhã vê o aviso, sem ter clicado nada.

    AS DUAS METADES NÃO SE SUBSTITUEM. O recado do clique dura os segundos do
    depósito de recados do piloto e fala do gesto que ela acabou de fazer; esta
    linha fica **enquanto a condição existir**. Sem ela, quem abrisse a aba no
    dia seguinte veria quatro degraus acesos que o motor não obedece, e nada
    dizendo por quê.

    SÓ QUANDO HÁ O QUE PERDER: sem nenhuma peça com opinião, a mesa em `Auto`
    não está engolindo nada, e a linha viraria ruído crônico — a mesma
    disciplina do `rumble_actions.texto_de_onde_grava_e_onde_manda`, que
    devolve `None` quando não há divergência a confessar.

    MORDIDA: em `a05_vibracao._ressalva_da_mesa`, troque o
    `if not quantos: return ""` por `pass` — o terceiro caso deste teste
    reprova, porque a linha passa a aparecer sobre uma mesa sem nada a perder.
    """
    mesa = [{"pref": "p1", "uniq": UNIQ}]
    com_peca = {"rumble": {"policy": "auto"},
                "controllers": {CHAVE: {"rumble": {"policy": "max"}}}}

    frase = a05._ressalva_da_mesa(com_peca, mesa)
    assert "Auto" in frase and "1 controle" in frase, (
        f"a linha não conta o que está sendo engolido: {frase!r}")

    assert a05._ressalva_da_mesa(
        {**com_peca, "rumble": {"policy": "balanceado"}}, mesa) == ""
    assert a05._ressalva_da_mesa({"rumble": {"policy": "auto"}}, mesa) == ""
    assert a05._ressalva_da_mesa(com_peca, []) == ""


def test_a_ressalva_entra_na_linha_do_produto_e_nao_num_bloco_novo(
        pac, a05, monkeypatch) -> None:
    """A confissão sai pelo MESMO emissor da linha de estado — `#vib-estado`."""
    from pacotes import perfil as _perfil

    monkeypatch.setattr(
        _perfil, "ativo",
        lambda _nome: {"rumble": {"policy": "auto"},
                       "controllers": {CHAVE: {"rumble": {"policy": "max"}}}})

    r = a05.pacote(pac.Contexto(
        state={"active_profile": "Bancada", "rumble_policy": "auto"},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
               "via": "USB", "cor": "starlight-blue"}],
        conectados=[{"uniq": UNIQ, "connected": True, "transport": "usb",
                     "index": 0, "player": 1}],
        estados={}))

    estado = r["blocos"]["#vib-estado"]
    assert "Auto" in estado and "sem chegar ao motor" in estado, (
        f"a ressalva não chegou à linha de estado da aba:\n{estado}")
