#!/usr/bin/env python3
"""A RÉGUA DA D2 NOS GATILHOS: o que ela aplicou no clique VAI PARA O DISCO.

Ela pediu, com estas palavras, em 05/09/2026:

    *"ao pular e sair configurando de aba em aba o perfil vai se lembrando de
    cada config de cada aba pra cada controle. aí aplicar aplica todas as
    configs naquele perfil e salvar se lembra disso quando eu for jogar o jogo e
    no dia seguinte e por diante."*

A decisão que a atende é a **D2** —
`docs/process/2026-09-05-AS-TRES-DECISOES-DO-PERFIL-medidas-e-decididas.md`:
*"persistência no clique em toda parte, com o rodapé como rede de segurança"*.

O DEFEITO, MEDIDO ANTES DA CURA
--------------------------------
`controllers[uniq].triggers` não persistia por clique nenhum. O `_RASCUNHO`
desta aba guardava o gatilho aplicado NESTA SESSÃO e o rodapé não o alcançava —
`pacotes/rodape.py` não importa `a03_gatilhos`. Clicar `Rígido` no L2 e depois
"Salvar Perfil" gravava o gatilho DE ONTEM, porque o rodapé monta o rascunho a
partir do PERFIL NO DISCO. A própria aba já dizia isso pela outra ponta, na
docstring do `reenviar`: *"o Aplicar do rodapé não é substituto — ele manda o
rascunho montado a partir do PERFIL NO DISCO"*.

AS SETE COISAS QUE ESTA RÉGUA COBRA
------------------------------------
1. **O clique grava.** `modo`, `pronto` e `ajuste` põem o gatilho no override
   daquele controle, no perfil ativo — sem passar pelo "Guardar esse efeito".
2. **SÓ O LADO QUE ELA TOCOU.** Clicar no L2 não pode escrever opinião sobre o
   R2: `profiles/manager._controllers_to_specs` lê `model_fields_set` lado a
   lado, e um `Off` implícito virado explícito SILENCIA o gatilho direito que a
   seção global do perfil dava àquele controle.
3. **O `reenviar` NÃO grava.** Ele reenvia o que está na tela, e a tela pode
   estar mostrando o global — persistir criaria uma opinião por-controle que
   ela nunca deu.
4. **Nada mudou, nada grava.** Regravar o perfil idêntico troca a data do
   arquivo e faz o daemon reaplicá-lo.
5. **O aparelho recusou, o disco não guarda.** A guarda é a mesma do rascunho.
6. **Sem perfil ativo não grava e NÃO levanta** — o efeito foi para o aparelho e
   o rascunho o segura; dizer "não deu" sobre um efeito que ela sente na mão
   seria a tela mentindo do lado caro.
7. **QUANDO MEIO ATO DEU CERTO, A FRASE DIZ AS DUAS METADES** — 06/09/2026, a
   decisão **D-17** dela (*"as duas abas falam"*),
   `docs/process/sprints/2026-09-05-AS-DUAS-ABAS-FALAM-01-*.md`. Perfil NOMEADO
   que não abre não cala mais: o recibo sai *«… aplicado · o efeito FOI para o
   aparelho, mas não consegui ABRIR o perfil …»*, pelo canal do `recado` verde
   e nunca pelo `RuntimeError` laranja — um gesto que fez o que prometeu no
   aparelho não é recusa.

A MORDIDA: apague o `_guardar_no_perfil(...)` de `_aplicar` (ou troque o
`guardar` para `False`) — o caso 1 reprova dizendo que o clique não chegou ao
disco. Densifique os dois lados em `_com_os_gatilhos` (o que o código fazia até
05/09) — o caso 2 reprova dizendo que o R2 ganhou dono sem ela pedir. Devolva o
`except Exception: return` de `_guardar_no_perfil` (o que o código fazia até
06/09) — o caso 7 reprova nos QUATRO lugares em que ele fala.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"
PERFIL = "Mortal Kombat"


class PonteDeMentira:
    """O daemon que aceita tudo e anota o que lhe pediram.

    Devolve `True` PELADO de propósito: é a forma da ponte antiga, e
    `_desfecho` a traduz para `(True, "", None)` — corpo `None`, que é
    "não há o que ler sobre destino". É a montagem em que `_chegou_ao_aparelho`
    responde pelo `ok`, e é a que separa esta régua da conversa sobre destinos.
    """

    def __init__(self, aceita: bool = True) -> None:
        self.aceita = aceita
        self.enviados: list[tuple[str, str, list[int]]] = []
        self.chamadas: list[str] = []

    def trigger_set_detalhado(self, lado: str, modo: str, params: list[int],
                              uniq: str = "") -> Any:
        self.enviados.append((lado, modo, list(params)))
        return self.aceita if self.aceita else (False, "o daemon recusou", None)

    def trigger_reset_detalhado(self, lado: str, uniq: str = "") -> Any:
        self.enviados.append((lado, "Off", []))
        return self.aceita if self.aceita else (False, "o daemon recusou", None)

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(metodo)
        return True


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture(autouse=True)
def rascunho_limpo():
    """O `_RASCUNHO` é estado de MÓDULO, e ele atravessa testes.

    Sem esta limpeza, o `ajuste` do caso 4 leria o que o caso 1 aplicou e sairia
    pela porta do "já está assim" — verde sobre uma gravação que nunca
    aconteceu.
    """
    from pacotes.a03_gatilhos import esquecer_o_rascunho

    esquecer_o_rascunho()
    yield
    esquecer_o_rascunho()


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira com um `Profile` DE VERDADE dentro.

    O esquema é o do produto porque é ele que esta régua mede: um dublê
    aceitaria um `ControllerOverrides` malformado e o teste ficaria verde sobre
    um perfil que o disco recusaria.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    estado = {PERFIL: Profile(name=PERFIL, match={"type": "any"})}
    gravados: list[Any] = []

    def _grava(prof: Any, **_: Any) -> None:
        gravados.append(prof)
        # O DISCO DE MENTIRA GUARDA O QUE RECEBEU. Sem isto, o segundo clique
        # releria o perfil de antes e a régua do "nada mudou" mediria outra
        # coisa — é a mesma montagem que o teste do `guardar` monta à mão.
        estado[prof.name] = prof

    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile", _grava, raising=False)
    return estado, gravados


#: O NOME QUE O DAEMON PUBLICA E ESTE LEITOR NÃO ACHA. É o caso da §2 da D-17:
#: perfil apagado, renomeado ou noutra pasta — e é dele que a frase das duas
#: metades tem de falar, com o nome dentro.
SUMIU = "perfil que sumiu"


@pytest.fixture
def perfil_que_nao_abre(monkeypatch):
    """O disco em que `load_profile` LEVANTA — o ramo que calava até 06/09.

    Devolve a lista de gravações, que tem de continuar vazia: não abriu, não
    grava. O que mudou na D-17 é só que ele passou a DIZER.
    """
    from hefesto_dualsense4unix.profiles import loader

    def _sem_perfil(nome: str) -> Any:
        raise FileNotFoundError(f"perfil não encontrado: {nome}")

    gravados: list[Any] = []
    monkeypatch.setattr(loader, "load_profile", _sem_perfil, raising=False)
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof), raising=False)
    return gravados


def _ctx(pac, ativo: str = PERFIL):
    dele = {"uniq": UNIQ, "transport": "usb", "connected": True}
    return pac.Contexto(state={"active_profile": ativo, "controllers": [dele]},
                        mesa=[], conectados=[dele], estados={})


def _gesto(pac, nome: str):
    fn = pac.gesto_da_pagina("03-gatilhos.html", nome)
    assert fn is not None, f"03-gatilhos.html:{nome} perdeu o dono"
    return fn


def _triggers_gravados(prof: Any) -> Any:
    override = (prof.controllers or {}).get(CHAVE)
    assert override is not None, (
        f"o clique não criou o override deste controle; "
        f"controllers={prof.controllers!r}")
    return override.triggers


# ---------------------------------------------------------------------------
# 1. O CLIQUE GRAVA — os três gestos que são escolha dela
# ---------------------------------------------------------------------------


def test_escolher_um_modo_grava_no_perfil(pac, disco) -> None:
    """A queixa dela, no caso mais simples: escolher `Rígido` no L2 e ir jogar."""
    _, gravados = disco
    _gesto(pac, "modo")(_ctx(pac),
                        {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                        PonteDeMentira())

    assert len(gravados) == 1, (
        f"o clique gravou {len(gravados)} vez(es) no perfil. Sem isto, o "
        f"'Salvar Perfil' do rodapé grava o gatilho DE ONTEM — ele monta o "
        f"rascunho a partir do PERFIL NO DISCO, e o `_RASCUNHO` desta aba não "
        f"chega lá.")
    assert _triggers_gravados(gravados[0]).left.mode == "Rigid"


def test_um_efeito_pronto_grava_a_curva(pac, disco) -> None:
    """A curva escolhida é a que fica no disco, com o modo da TABELA dela."""
    from pacotes.a03_gatilhos import _curva

    _, gravados = disco
    curva, modo_da_curva = _curva("stop_hard")
    _gesto(pac, "pronto")(_ctx(pac),
                          {"uniq": UNIQ, "lado": "d", "valor": "stop_hard"},
                          PonteDeMentira())

    assert len(gravados) == 1, "o efeito pronto não chegou ao disco"
    direito = _triggers_gravados(gravados[0]).right
    assert direito.mode == modo_da_curva, (
        f"gravou o modo {direito.mode!r} para uma curva que mora em "
        f"{modo_da_curva!r} — número certo no efeito errado")
    assert list(direito.params)[-len(curva):] == list(curva)


def test_arrastar_uma_barra_grava_o_ajuste(pac, disco) -> None:
    """O `ajuste` é o terceiro caminho de escolha, e o mais fácil de esquecer."""
    _, gravados = disco
    _gesto(pac, "ajuste")(
        _ctx(pac),
        {"uniq": UNIQ, "lado": "e", "i": "0", "valor": "7",
         "forma": {"modo-chave-e": "Rigid"}},
        PonteDeMentira())

    assert len(gravados) == 1, "arrastar a barra não chegou ao disco"
    primeiro = next(iter(_triggers_gravados(gravados[0]).left.params))
    assert primeiro == 7, f"a barra 0 foi ao disco como {primeiro}"


# ---------------------------------------------------------------------------
# 2. SÓ O LADO QUE ELA TOCOU
# ---------------------------------------------------------------------------


def test_o_clique_num_lado_nao_da_dono_ao_outro(pac, disco) -> None:
    """O R2 continua herdando a seção GLOBAL do perfil.

    `profiles/manager._controllers_to_specs` lê `model_fields_set` LADO A LADO:
    um `right` escrito no override vence o global daquele controle. Densificar o
    lado que ela não tocou apaga, só ali, o gatilho direito do perfil.
    """
    _, gravados = disco
    _gesto(pac, "modo")(_ctx(pac),
                        {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                        PonteDeMentira())

    lados = _triggers_gravados(gravados[0]).model_fields_set
    assert lados == {"left"}, (
        f"o clique no L2 escreveu {sorted(lados)} no override. O lado que ela "
        f"não tocou tem de continuar SEM OPINIÃO — escrito, ele vence a seção "
        f"global do perfil e silencia o gatilho direito só neste controle.")


def test_o_segundo_lado_soma_e_nao_substitui(pac, disco) -> None:
    """Clicar nos dois lados deixa os DOIS no disco — a soma é o que ela espera."""
    _, gravados = disco
    ctx = _ctx(pac)
    _gesto(pac, "modo")(ctx, {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                        PonteDeMentira())
    _gesto(pac, "modo")(ctx, {"uniq": UNIQ, "lado": "d", "valor": "Off"},
                        PonteDeMentira())

    trig = _triggers_gravados(gravados[-1])
    assert trig.model_fields_set == {"left", "right"}, (
        f"depois dos dois cliques o override tem {sorted(trig.model_fields_set)}")
    assert (trig.left.mode, trig.right.mode) == ("Rigid", "Off"), (
        "o segundo clique apagou a escolha do primeiro lado")


def test_a_secao_global_do_perfil_fica_intacta(pac, disco) -> None:
    """A aba tem uma coluna POR CONTROLE: gravar no global mudaria o vizinho."""
    _, gravados = disco
    _gesto(pac, "modo")(_ctx(pac),
                        {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                        PonteDeMentira())

    assert gravados[0].triggers.left.mode == "Off", (
        "o clique mexeu na seção GLOBAL do perfil — o gatilho do P1 mudaria "
        "quando ela clicasse na coluna do P2")


# ---------------------------------------------------------------------------
# 3. O REENVIAR NÃO GRAVA
# ---------------------------------------------------------------------------


def test_reenviar_nao_grava(pac, disco) -> None:
    """A medição que sustenta a isenção em `test_todo_gesto_que_grava_esta_protegido`.

    A coluna pode estar mostrando o gatilho da seção GLOBAL, sem override
    nenhum: persistir aqui criaria uma opinião por-controle que ela nunca deu, e
    a partir dali mudar o global deixaria de alcançar este aparelho.
    """
    _, gravados = disco
    p = PonteDeMentira()
    _gesto(pac, "reenviar")(
        _ctx(pac),
        {"uniq": UNIQ, "forma": {"modo-chave-e": "Rigid", "modo-chave-d": "Off"}},
        p)

    assert len(p.enviados) == 2, (
        f"o reenviar mandou {len(p.enviados)} gatilho(s) ao aparelho — ele "
        f"manda os DOIS da coluna")
    assert gravados == [], (
        f"o reenviar gravou {len(gravados)} vez(es) no perfil dela. Ele reenvia "
        f"o que está na TELA, e a tela pode estar mostrando o global.")


# ---------------------------------------------------------------------------
# 4, 5 e 6. AS TRÊS GUARDAS
# ---------------------------------------------------------------------------


def test_nada_mudou_nada_grava(pac, disco) -> None:
    """Regravar idêntico troca a data do arquivo e faz o daemon reaplicar."""
    from pacotes.a03_gatilhos import esquecer_o_rascunho

    _, gravados = disco
    ctx = _ctx(pac)
    _gesto(pac, "modo")(ctx, {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                        PonteDeMentira())
    assert len(gravados) == 1
    # O RASCUNHO É ARRANCADO DE PROPÓSITO: com ele, o segundo clique poderia
    # nem chegar ao disco por outro caminho, e a régua mediria a memória de
    # sessão em vez da guarda de gravação.
    esquecer_o_rascunho()

    p2 = PonteDeMentira()
    _gesto(pac, "modo")(ctx, {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                        p2)
    assert len(gravados) == 1, (
        "regravou um perfil idêntico — um `profile.switch` no meio de uma "
        "partida não é de graça")
    assert p2.chamadas == [], (
        f"pediu {p2.chamadas} ao daemon sem ter o que gravar — o "
        f"`launch_env.refresh` só faz sentido depois de uma gravação")


def test_o_aparelho_recusou_o_disco_nao_guarda(pac, disco) -> None:
    """Guardar o que o aparelho recusou seria prometer amanhã o que não fez hoje."""
    _, gravados = disco
    with pytest.raises(RuntimeError):
        _gesto(pac, "modo")(_ctx(pac),
                            {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                            PonteDeMentira(aceita=False))
    assert gravados == [], (
        "gravou no perfil um efeito que o daemon recusou — a guarda é a mesma "
        "do rascunho (`ok and _chegou_ao_aparelho`)")


def test_sem_perfil_ativo_aplica_e_nao_levanta(pac, disco) -> None:
    """O efeito FOI para o aparelho; dizer "não deu" seria mentir do lado caro."""
    _, gravados = disco
    p = PonteDeMentira()
    saida = _gesto(pac, "modo")(_ctx(pac, ativo=""),
                                {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                                p)

    assert p.enviados, "o gatilho não chegou ao aparelho"
    assert gravados == [], "gravou sem perfil ativo"
    assert saida and "recado" in saida, (
        "o gesto deixou de devolver o recibo por causa da gravação que não "
        "havia onde fazer")


def test_perfil_que_nao_abre_aplica_grava_nada_e_nao_levanta(
        pac, perfil_que_nao_abre) -> None:
    """O NOME PUBLICADO PODE NÃO EXISTIR PARA ESTE LEITOR — achado em 05/09/2026.

    Não é hipótese: quatro réguas desta aba rodam com `active_profile="régua"`,
    um nome que não está em disco, e a primeira versão desta cura LEVANTOU nas
    quatro — transformando um gatilho que FOI para o aparelho num erro na tela.
    Na máquina dela o mesmo caminho existe (perfil apagado, renomeado, outra
    pasta), e o preço seria pior: o clique deixaria de funcionar.

    **AS TRÊS ASSERÇÕES CONTINUAM VALENDO DEPOIS DA D-17** (06/09/2026), e o
    nome deste caso mudou porque prometia menos do que ele mede: o gatilho
    chega ao aparelho, o disco não recebe nada, e o gesto **não levanta**. O que
    caducou aqui não é nenhuma das três — é o SILÊNCIO que o docstring antigo
    desta função defendia. A metade que sobrevive é *"não levanta"*, que é a
    escolha do CANAL; a que morreu é *"não fala"*.

    Quem cobra a FRASE é `test_a_falha_de_abrir_o_perfil_diz_as_duas_metades`,
    logo abaixo. Aqui a asserção é só a de que ela existe — este caso é sobre o
    clique continuar funcionando.

    Abrir e não conseguir gravar é outra coisa, e essa também fala, por outro
    canal — ver `test_a_falha_de_disco_diz_as_duas_metades`. A diferença é entre
    "não há onde guardar" e "havia onde e não guardei".
    """
    gravados = perfil_que_nao_abre
    p = PonteDeMentira()
    saida = _gesto(pac, "modo")(_ctx(pac, ativo=SUMIU),
                                {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                                p)
    assert p.enviados, "o gatilho não chegou ao aparelho"
    assert gravados == [], "gravou num perfil que não abriu"
    assert saida and "recado" in saida, (
        "o gesto virou erro porque o perfil ativo não abriu — o efeito FOI "
        "para o aparelho e ela está sentindo na mão")


# ---------------------------------------------------------------------------
# 7. AS DUAS METADES — a D-17, 06/09/2026
# ---------------------------------------------------------------------------


def test_a_falha_de_abrir_o_perfil_diz_as_duas_metades(
        pac, perfil_que_nao_abre) -> None:
    """O ramo que CALAVA passou a falar — e a frase tem forma, não só palavras.

    Ela decidiu em 05/09, sobre a divergência entre as abas 02 e 03: **as duas
    abas falam**. O que este caso mede é o *como*:

    1. **as duas metades** — `aparelho` e `perfil` na mesma frase. Só a primeira
       esconderia o defeito; só a segunda mandaria ela procurar no aparelho um
       efeito que ESTÁ lá;
    2. **o nome do perfil** — sem ele a frase não diz o que consertar, e é
       justamente o nome que separa "apagado" de "renomeado" na mesa dela;
    3. **o recibo vem PRIMEIRO** — a frase abre pelo que ela FEZ. Invertida, o
       cartão começa por uma queixa sobre um gesto que funcionou;
    4. **o canal é o verde** — `{"recado": …}`, nunca um `RuntimeError`. O
       laranja de 30 s é o da RECUSA, e este gesto não recusou nada.

    A MORDIDA: devolva o `except Exception: return` de `_guardar_no_perfil` e o
    item 1 reprova com o recibo curto, sem a segunda metade.

    O RECIBO É O CURTO DE PROPÓSITO: o `PonteDeMentira` devolve `True` pelado,
    `_fala_de_destino` responde `False` e o recibo sai como `"<assunto>
    aplicado"`. Contar com o traduzido faria esta régua medir
    `textos_de_aplicacao.frase_do_desfecho` em vez da soma que a D-17 acrescenta.
    """
    from pacotes.a03_gatilhos import _E_TAMBEM, _assunto

    gravados = perfil_que_nao_abre
    saida = _gesto(pac, "modo")(_ctx(pac, ativo=SUMIU),
                                {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                                PonteDeMentira())

    assert gravados == [], "gravou num perfil que não abriu"
    assert isinstance(saida, dict), (
        f"o gesto devolveu {saida!r} — a falha de ABRIR o perfil virou recusa, "
        f"e o cartão pintaria laranja sobre um efeito que ela sente na mão")
    frase = str(saida["recado"])

    baixo = frase.lower()
    assert "aparelho" in baixo and "perfil" in baixo, (
        f"a frase não diz as DUAS metades — «o aparelho recebeu · o perfil não "
        f"guardou» é o contrato da D-17, e esta diz: {frase!r}")
    assert SUMIU in frase, (
        f"a frase não nomeia o perfil que não abriu, e sem o nome ela não diz o "
        f"que consertar: {frase!r}")
    assert frase.startswith(_assunto("left", "Rigid")), (
        f"a frase não abre pelo que ela FEZ — a segunda metade vem DEPOIS do "
        f"recibo, nunca antes: {frase!r}")
    assert _E_TAMBEM in frase, (
        f"as duas metades vieram coladas sem o separador desta aba: {frase!r}")


@pytest.mark.parametrize(
    ("gesto_", "clique"),
    [("modo", {"lado": "e", "valor": "Rigid"}),
     ("pronto", {"lado": "d", "valor": "stop_hard"}),
     ("ajuste", {"lado": "e", "i": "0", "valor": "7",
                 "forma": {"modo-chave-e": "Rigid"}})])
def test_os_tres_gestos_que_gravam_carregam_a_frase(
        pac, perfil_que_nao_abre, gesto_, clique) -> None:
    """**É ESTA QUE PROVA O PASSO 2:** a soma mora no `_aplicar`, não no gesto.

    Uma cura escrita dentro de um gesto passa em UM TERÇO desta régua — e é
    exatamente o defeito que esta casa pagou duas vezes em 05/09: *"quando a
    cura conhece a causa, ela cobre TODOS os chamadores"*. A espera pela página
    nasceu aplicada a um dos quatro chamadores do piloto, e a frente da aba 10
    teve de escrever um driver próprio por causa disso.

    Os três são os que GRAVAM (a D2, 05/09): `modo`, `pronto` e `ajuste`. O
    quarto chamador do `_aplicar` — o `reenviar` — passa `guardar=False`, e o
    caso seguinte prova que ele continua sem frase de disco.

    A MORDIDA: arranque a soma do `_aplicar` (devolva só o recibo) e as três
    reprovam de uma vez. Se só UMA reprovar, a cura entrou no gesto.
    """
    gravados = perfil_que_nao_abre
    saida = _gesto(pac, gesto_)(_ctx(pac, ativo=SUMIU),
                                {"uniq": UNIQ, **clique}, PonteDeMentira())

    assert gravados == [], f"o gesto {gesto_!r} gravou num perfil que não abriu"
    assert isinstance(saida, dict), (
        f"o gesto {gesto_!r} devolveu {saida!r} em vez do recado com as duas "
        f"metades")
    baixo = str(saida["recado"]).lower()
    assert "aparelho" in baixo and "perfil" in baixo, (
        f"o gesto {gesto_!r} calou a segunda metade: {saida['recado']!r}. A soma "
        f"é do `_aplicar` — se ela vive dentro de um gesto, os outros dois "
        f"continuam mudos.")
    assert SUMIU in str(saida["recado"]), (
        f"o gesto {gesto_!r} não nomeou o perfil: {saida['recado']!r}")


def test_o_reenviar_nao_ganhou_frase_de_disco(pac, perfil_que_nao_abre) -> None:
    """O contrato do `reenviar` diz *"ELE NÃO GRAVA NADA NO DISCO DELA"*.

    Ele passa `guardar=False`, então `_guardar_no_perfil` nem é chamado e a
    frase é sempre `""`. **Isto não é sorte, e sem esta régua o Passo 2 da D-17
    poderia somar uma queixa de disco num gesto que por contrato não toca o
    disco** — e ninguém veria: o recibo dele já é uma soma de duas metades pelo
    mesmo separador.

    A razão do `guardar=False` é de PRODUTO: a coluna pode estar mostrando o
    gatilho da seção GLOBAL do perfil. Persistir aqui criaria uma opinião
    por-controle que ela nunca deu.

    A MORDIDA: troque o `guardar=False` da chamada em `reenviar` por `True` e
    esta régua reprova com a frase do perfil dentro do recibo do reenvio — e
    `test_reenviar_nao_grava` reprova junto, pelo disco.
    """
    gravados = perfil_que_nao_abre
    p = PonteDeMentira()
    saida = _gesto(pac, "reenviar")(
        _ctx(pac, ativo=SUMIU),
        {"uniq": UNIQ, "forma": {"modo-chave-e": "Rigid", "modo-chave-d": "Off"}},
        p)

    assert len(p.enviados) == 2, (
        f"o reenviar mandou {len(p.enviados)} gatilho(s) — ele manda os DOIS")
    assert gravados == [], "o reenviar gravou no perfil dela"
    frase = str((saida or {}).get("recado") or "")
    assert "perfil" not in frase.lower() and SUMIU not in frase, (
        f"o reenviar ganhou uma frase de disco: {frase!r}. Ele reenvia o que "
        f"está na TELA e não guarda nada — queixar-se do perfil aqui seria a "
        f"tela falando de um disco que este gesto não tocou.")


def test_a_falha_de_disco_diz_as_duas_metades(pac, monkeypatch) -> None:
    """Silêncio aqui é a promessa de amanhã que não se cumpre.

    A frase tem de dizer as DUAS coisas: o aparelho recebeu, o perfil não
    guardou. Só a primeira metade esconderia o defeito; só a segunda faria ela
    procurar no aparelho um efeito que está lá.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    monkeypatch.setattr(loader, "load_profile",
                        lambda n: Profile(name=n, match={"type": "any"}),
                        raising=False)

    def _explode(prof: Any, **_: Any) -> None:
        raise OSError("disco cheio")

    monkeypatch.setattr(loader, "save_profile", _explode, raising=False)

    with pytest.raises(RuntimeError) as erro:
        _gesto(pac, "modo")(_ctx(pac),
                            {"uniq": UNIQ, "lado": "e", "valor": "Rigid"},
                            PonteDeMentira())
    frase = str(erro.value).lower()
    assert "aparelho" in frase and "perfil" in frase, frase
    assert "disco cheio" in frase, (
        f"a razão de baixo sumiu da frase — quem lê fica sem o que consertar: "
        f"{frase}")
