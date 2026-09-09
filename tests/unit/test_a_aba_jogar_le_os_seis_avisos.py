#!/usr/bin/env python3
"""OS SEIS AVISOS que a aba Jogar lia do daemon e parou de ler.

JOGAR-OS-SEIS-AVISOS-01, 06/09/2026. As seis linhas do CSV da paridade que esta
régua guarda têm todas a MESMA forma, e é o enunciado da sprint: **o daemon
publica a chave, ou `home_actions` já tem a função pura, e o pacote da aba não
lê.** Nenhuma delas pedia lógica nova — as seis pediam um LEITOR.

    12  o aviso do "Controlar o PC" sem mouse nem teclado
    17  o grab dobrado ("o jogo pode receber cada botão duas vezes")
    25  o RECIBO do "Reconectar Controles"
    26  a dica do "Reconectar Controles" com jogo aberto
    28  a divergência de máscara que o daemon já publicava
    35  a linha de origem ("quem ligou foi o perfil ativo")

O QUE ESTA RÉGUA MEDE, E O QUE ELA DELIBERADAMENTE NÃO MEDE
------------------------------------------------------------
Ela mede que **a coluna Atenção emite a frase do DONO** a partir de um `state`,
e que ela **cala** quando não há o que dizer. Ela NÃO reescreve as frases: toda
comparação é contra a constante do produto (`home_actions.AVISO_DE_GRAB_LINHA`,
`RECONCILIAR_JOGO_ABERTO_TEXT`, `TEXTO_DESKTOP_SEM_MOUSE`…). Uma régua que
digitasse o texto esperado seria a segunda cópia da palavra — o defeito que
onze réguas desta casa já tiveram, e que o `_do_exame` desta mesma aba pagou
quando digitou "RÁDIO" e "AVISO" por cima de um selo que o produto emitia.

A MORDIDA DE CADA UMA é a mesma: com o `state` que ACENDE, a linha aparece; com
o `state` vizinho — o que muda UM termo da condição —, ela some. Uma régua que
só sabe passar não é régua, e as seis têm as duas respostas aqui.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from pacotes import Contexto
from pacotes import a01_jogar as aba

UNIQ = "aa:bb:cc:00:00:01"


def _mesa(**extra: Any) -> dict[str, Any]:
    """Um `state` mínimo com UM controle primário conectado."""
    base: dict[str, Any] = {
        "connected": True,
        "native_mode": False,
        "paused": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "controllers": [
            {"uniq": UNIQ, "connected": True, "is_primary": True, "player_slot": 1}
        ],
    }
    base.update(extra)
    return base


def _textos(state: dict[str, Any]) -> list[str]:
    """As frases da coluna Atenção INTEIRA para este `state`.

    **É `a01_jogar._avisos` e não `painel.avisos_do_estado`, e a diferença é o
    ponto.** Onze das doze fontes vêm da tupla do painel; a divergência de
    máscara mora no pacote da aba, porque volta em markup do Pango e tirá-lo
    custa uma citação a `gui/` que `app/actions/` não pode fazer. Medir só uma
    das duas metades seria a régua olhando meia coluna.
    """
    ctx = Contexto(state=state, mesa=[], conectados=[], estados={})
    return [str(a["texto"]) for a in aba._avisos(ctx)]


# ---------------------------------------------------------------------------
# 0. AS SEIS TÊM CANAL — e o canal é UM SÓ
# ---------------------------------------------------------------------------
def test_as_cinco_de_coluna_entraram_em_avisos_da_tela() -> None:
    """O dono da coluna é `painel.AVISOS_DA_TELA`, e a sprint proíbe um segundo.

    *"Os avisos entram na coluna Atenção por `painel.AVISOS_DA_TELA` e
    `ORDEM_DA_GRAVIDADE` — não invente um segundo lugar."*

    A sexta linha (o recibo do "Reconectar Controles") não é aviso de coluna: é
    a resposta de um GESTO, e tem régua própria mais abaixo.
    """
    nomes = {a.nome for a in painel.AVISOS_DA_TELA}
    for esperado in (
        "home_actions.texto_do_desktop_sem_emulacao",
        "painel.aviso_do_grab_dobrado",
        "home_actions._reconciliar_gate_text",
        "painel.aviso_da_origem_do_modo",
    ):
        assert esperado in nomes, (
            f"{esperado} saiu de `AVISOS_DA_TELA` — a linha do CSV que ela fecha "
            f"voltou a ser FALTA_NO_HTML, e a coluna Atenção parou de dizer o "
            f"que o daemon publica.")
    assert callable(getattr(aba, "_aviso_da_divergencia_de_mascara", None)), (
        "a divergência de máscara saiu do pacote da aba — ela é a quinta, e "
        "mora aqui e não na tupla do painel porque volta em markup do Pango")


def test_a_divergencia_nao_aponta_de_app_para_a_janela() -> None:
    """O PORTÃO QUE MOVEU ESTA FONTE, e a régua guarda a razão de ela ter mudado.

    `scripts/check_nada_aponta_para_a_janela.py` congela o inventário de quem
    ainda cita a janela GTK e o faz **só diminuir** (`D-0609-GTK-LEVA-INTEIRA`).
    A primeira versão desta cura punha `sem_markup` dentro de
    `app/actions/jogar/painel.py`, e o portão reprovou nomeando arquivo e linha
    — medido em 06/09/2026. Se alguém devolver a citação para lá, esta régua
    reprova ANTES do portão, dizendo por quê.
    """
    fonte = pathlib.Path(painel.__file__).read_text(encoding="utf-8")
    assert "gui.aba_sistema" not in fonte, (
        "`app/actions/jogar/painel.py` voltou a apontar para a janela GTK. "
        "Quem precisa de `sem_markup` é o pacote da aba, por `_sem_markup` — "
        "que existe para a citação continuar sendo UMA.")


def test_a_porta_do_markup_e_uma_so() -> None:
    """O par (arquivo, alvo) do inventário tem contagem 1, e ela não pode subir.

    O portão reprova tanto citação NOVA quanto contagem que CRESCE. As duas
    fontes que voltam em markup — a ponte e a divergência — passam pela mesma
    porta de propósito.

    **O NOME COMPLETO DO MÓDULO NÃO SE ESCREVE NESTA RÉGUA**, e não é asseio: o
    portão varre o TEXTO dos arquivos, então uma régua que soletrasse a agulha
    viraria a citação que ela mede — foi o que aconteceu na primeira versão
    deste teste, reprovada pelo portão em 06/09/2026. Contar os `import` que
    nomeiam o módulo responde à mesma pergunta sem cravar o padrão.
    """
    linhas = pathlib.Path(aba.__file__).read_text(encoding="utf-8").splitlines()
    imports = [linha for linha in linhas
               if linha.lstrip().startswith("from") and "aba_sistema" in linha]
    assert len(imports) == 1, (
        f"este arquivo tem {len(imports)} `import` do módulo da janela que sabe "
        f"tirar markup, e o inventário declara UM. O portão reprova quando a "
        f"contagem de um par declarado sobe — use `_sem_markup`.")


def test_todo_selo_novo_esta_na_escada_da_gravidade() -> None:
    """Selo fora de `ORDEM_DA_GRAVIDADE` é selo que a máquina cheia esconde.

    `a01_jogar._coluna_de_avisos` põe o que não está na tupla DEPOIS DE TUDO, e
    a coluna mostra `AVISOS_NA_COLUNA` de cada vez. Um selo nomeado neste
    arquivo e ausente da escada nasce condenado ao `+N`.
    """
    selos = [a.selo for a in painel.AVISOS_DA_TELA]
    selos += [str(a["selo"]) for a in aba._avisos(
        Contexto(state=_com_divergencia(), mesa=[], conectados=[], estados={}))]
    fora = [s for s in selos if s not in aba.ORDEM_DA_GRAVIDADE and not s.startswith("+")]
    assert fora == [], (
        f"estes selos não estão em `ORDEM_DA_GRAVIDADE`: {sorted(set(fora))}. "
        f"Ou eles entram na escada, ou a máquina cheia os esconde atrás do +N.")


# ---------------------------------------------------------------------------
# 1. LINHA 12 — "Controlar o PC" que não controla nada
# ---------------------------------------------------------------------------
def test_o_desktop_sem_mouse_nem_teclado_fala() -> None:
    """O MODO-QUE-NAO-CONTROLA-01 chega à coluna. Frase do dono, verbatim."""
    state = _mesa(
        native_mode=False,
        gamepad_emulation={"enabled": False, "flavor": "dualsense"},
        mouse_emulation={"enabled": False},
        keyboard_emulation={"enabled": False},
    )
    assert home_actions.TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO in _textos(state)


def test_o_desktop_com_o_mouse_ligado_cala() -> None:
    """A MORDIDA: liga o mouse e o teclado, e a linha some.

    Só o ``False`` LITERAL acende, e é a disciplina do dono — bloco ausente
    (daemon antigo, payload incompleto) não vira aviso.
    """
    state = _mesa(
        gamepad_emulation={"enabled": False, "flavor": "dualsense"},
        mouse_emulation={"enabled": True},
        keyboard_emulation={"enabled": True},
    )
    for frase in (
        home_actions.TEXTO_DESKTOP_SEM_MOUSE,
        home_actions.TEXTO_DESKTOP_SEM_TECLADO,
        home_actions.TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO,
    ):
        assert frase not in _textos(state)


def test_fora_do_desktop_ninguem_avisa_sobre_o_mouse() -> None:
    """Em "Jogar pelo Hefesto" o mouse está desligado pela exclusão mútua do
    daemon — o desenho normal, e nada de errado nele."""
    state = _mesa(mouse_emulation={"enabled": False}, keyboard_emulation={"enabled": False})
    assert home_actions.TEXTO_DESKTOP_SEM_MOUSE_NEM_TECLADO not in _textos(state)


# ---------------------------------------------------------------------------
# 2. LINHA 17 — o grab dobrado
# ---------------------------------------------------------------------------
def test_o_grab_dobrado_diz_a_linha_e_o_porque() -> None:
    """As DUAS metades viajam, porque a coluna não tem `hover` por linha.

    `aviso_de_grab` devolve ``(linha, porquê)``: na janela antiga o segundo era
    o `tooltip`. Cortá-lo aqui deixaria o alarme mais confuso desta aba sem o
    que fazer a respeito.
    """
    state = _mesa(primary_grab_state="failed")
    frase = next(t for t in _textos(state) if home_actions.AVISO_DE_GRAB_LINHA in t)
    assert home_actions.AVISO_DE_GRAB_PORQUE in frase, (
        "o porquê do grab dobrado não chegou à tela — na coluna Atenção ele é "
        "a única explicação que existe, porque não há `hover` por linha")


@pytest.mark.parametrize(
    ("extra", "porque"),
    [
        ({"primary_grab_state": "off"}, "só `failed` acende"),
        ({"primary_grab_state": "pending"}, "`pending` é quem ainda não abriu o dispositivo"),
        ({"primary_grab_state": "failed",
          "gamepad_emulation": {"enabled": False, "flavor": "dualsense"}},
         "sem gamepad do Hefesto não há segundo dispositivo para dobrar"),
        ({"primary_grab_state": "failed",
          "controllers": [{"uniq": UNIQ, "connected": False, "is_primary": True}]},
         "controle que saiu da sala não dobra botão de jogo nenhum"),
        ({"primary_grab_state": "failed",
          "controllers": [{"uniq": UNIQ, "connected": True, "is_primary": False}]},
         "o aviso é do PRIMÁRIO"),
    ],
)
def test_o_grab_dobrado_cala_quando_um_termo_muda(extra: dict[str, Any], porque: str) -> None:
    """A MORDIDA, em cinco vizinhos: cada um muda UM termo e a linha some."""
    state = _mesa(**extra)
    assert not any(home_actions.AVISO_DE_GRAB_LINHA in t for t in _textos(state)), porque


# ---------------------------------------------------------------------------
# 3. LINHA 26 — a dica do "Reconectar Controles" com jogo aberto
# ---------------------------------------------------------------------------
def test_com_jogo_em_cena_a_dica_do_reconectar_aparece() -> None:
    """`jogo_com_autoridade` é a fonte ÚNICA, e é a mesma do gate R-04."""
    state = _mesa(game_signal={"authority": "game"})
    assert home_actions.RECONCILIAR_JOGO_ABERTO_TEXT in _textos(state)


@pytest.mark.parametrize(
    "sinal",
    [None, {}, {"authority": "desktop"}, {"authority": None}, "nada"],
)
def test_sem_jogo_em_cena_a_dica_cala(sinal: Any) -> None:
    """A MORDIDA: sinal ausente ou de outra autoridade não vira alarme falso."""
    state = _mesa(game_signal=sinal)
    assert home_actions.RECONCILIAR_JOGO_ABERTO_TEXT not in _textos(state)


# ---------------------------------------------------------------------------
# 4. LINHA 28 — a divergência de máscara que o daemon já publicava
# ---------------------------------------------------------------------------
def _com_divergencia(**extra: Any) -> dict[str, Any]:
    alarme = {
        "appid": "424242",
        "profile": "Pragmata",
        "mascara_perfil": "xbox",
        "mascara_viva": "dualsense",
        "motivo": "jogo_aberto",
        "em_cena": True,
    }
    alarme.update(extra)
    return _mesa(gamepad_emulation={"enabled": True, "flavor": "dualsense",
                                    "mascara_divergente": alarme})


def test_a_divergencia_de_mascara_chega_a_coluna() -> None:
    """A chave que o daemon publica desde a MASCARA-01, lida pela primeira vez.

    A frase é a do dono e nomeia o PERFIL, nunca um gesto dela — quem pediu
    aquela máscara foi o perfil, que entra sozinho pelo autoswitch (I3).
    """
    state = _com_divergencia()
    frase = next(
        (t for t in _textos(state)
         if t.startswith(home_actions.DIVERGENCIA_DO_PERFIL_PREFIXO)), "")
    assert frase, "a divergência de máscara não chegou à coluna Atenção"
    assert "Pragmata" in frase, "a frase não nomeou o perfil que pediu a máscara"
    assert "você escolheu" not in frase, (
        "a frase acusou um gesto dela sobre uma máscara que o PERFIL pediu — "
        "é o defeito que a I3 tirou da tela")


def test_o_markup_do_pango_nao_chega_a_tela() -> None:
    """`texto_da_divergencia` devolve markup; o piloto escreve `textContent`.

    Sem `sem_markup`, o ``<span foreground="…">`` iria LITERAL para a tela.
    """
    for texto in _textos(_com_divergencia()):
        assert "<span" not in texto and "</span>" not in texto


@pytest.mark.parametrize(
    ("extra", "porque"),
    [
        ({"mascara_viva": "xbox"}, "as duas máscaras iguais não é divergência"),
        ({"mascara_perfil": None}, "sem uma das pontas não se afirma divergência"),
        ({"mascara_viva": ""}, "sem uma das pontas não se afirma divergência"),
    ],
)
def test_a_divergencia_cala_sem_as_duas_pontas(extra: dict[str, Any], porque: str) -> None:
    """A MORDIDA: afirmar divergência sem saber as duas máscaras é alarme falso."""
    textos = _textos(_com_divergencia(**extra))
    assert not any(
        t.startswith(home_actions.DIVERGENCIA_DO_PERFIL_PREFIXO) for t in textos), porque


def test_sem_alarme_do_daemon_a_coluna_cala() -> None:
    """`mascara_divergente: null` é o estado normal — e é o da máquina dela."""
    state = _mesa(gamepad_emulation={"enabled": True, "flavor": "dualsense",
                                     "mascara_divergente": None,
                                     "mascara_divergencias": []})
    assert not any(
        t.startswith(home_actions.DIVERGENCIA_DO_PERFIL_PREFIXO) for t in _textos(state))


def test_a_lista_irma_nao_acende_nada() -> None:
    """`mascara_divergencias` é antecipação de jogo FECHADO, e fica de fora.

    Mostrar divergência de jogo que não está em cena seria aviso sobre coisa
    que não está em uso — está escrito no dono, e esta régua o guarda.
    """
    state = _mesa(gamepad_emulation={
        "enabled": True, "flavor": "dualsense", "mascara_divergente": None,
        "mascara_divergencias": [{"appid": "1", "profile": "P", "mascara_perfil": "xbox",
                                  "mascara_viva": "dualsense", "motivo": "x",
                                  "em_cena": False}]})
    assert not any(
        t.startswith(home_actions.DIVERGENCIA_DO_PERFIL_PREFIXO) for t in _textos(state))


# ---------------------------------------------------------------------------
# 5. LINHA 35 — a linha de origem
# ---------------------------------------------------------------------------
def test_o_nativo_ligado_pelo_perfil_se_declara() -> None:
    state = _mesa(native_mode=True, native_mode_origin="profile",
                  gamepad_emulation={"enabled": False, "flavor": "dualsense"})
    frase = next(t for t in _textos(state) if t.startswith("Quem ligou"))
    assert painel._ROTULO_DO_MODO["native"] in frase, (
        "a linha de origem usou a palavra da casa em vez do rótulo da tela")


def test_o_gamepad_ligado_pelo_perfil_se_declara() -> None:
    state = _mesa(mode_from_profile="gamepad")
    frase = next(t for t in _textos(state) if t.startswith("Quem ligou"))
    assert painel._ROTULO_DO_MODO["gamepad"] in frase


def test_as_duas_origens_cabem_na_mesma_linha() -> None:
    """O ``" · "`` é o da janela antiga: dois fatos, não uma frase composta."""
    state = _mesa(native_mode=True, native_mode_origin="profile",
                  mode_from_profile="gamepad")
    frase = next(t for t in _textos(state) if t.startswith("Quem ligou"))
    assert painel.SEPARADOR_DA_ORIGEM in frase


@pytest.mark.parametrize(
    ("extra", "porque"),
    [
        ({}, "o estado normal não tem origem de perfil nenhuma"),
        ({"native_mode": True, "native_mode_origin": "manual"},
         "origem manual é ELA ligando, e a tela não pode chamar isso de perfil"),
        ({"native_mode": False, "native_mode_origin": "profile"},
         "a origem sobrevive ao modo no store; sem o modo de pé não há o que dizer"),
        ({"mode_from_profile": "native"},
         "o ramo do nativo já responde por isso — dois avisos do mesmo fato"),
    ],
)
def test_a_origem_cala_quando_o_perfil_nao_ligou(extra: dict[str, Any], porque: str) -> None:
    """A MORDIDA: só os literais ``"profile"`` e ``"gamepad"`` acendem."""
    state = _mesa(**extra)
    assert not any(t.startswith("Quem ligou") for t in _textos(state)), porque


# ---------------------------------------------------------------------------
# 6. LINHA 25 — o RECIBO do "Reconectar Controles"
# ---------------------------------------------------------------------------
class _PonteQueResponde:
    """Um dublê que sabe RESPONDER e sabe RECUSAR — as duas, ou não é régua."""

    def __init__(self, respostas: dict[str, Any]) -> None:
        self.respostas = respostas
        self.chamadas: list[str] = []

    def resultado(self, metodo: str, **_: Any) -> Any:
        self.chamadas.append(metodo)
        valor = self.respostas.get(metodo)
        if isinstance(valor, Exception):
            raise valor
        return valor


def _ctx() -> Contexto:
    return Contexto(state=_mesa(), mesa=[], conectados=[], estados={})


def test_o_recibo_diz_quantos_voltaram_e_o_que_a_numeracao_fez() -> None:
    """Os dois passos respondem, e a frase é a de `reconciliar_toast`."""
    p = _PonteQueResponde({
        "coop.sync": {"status": "ok", "players": 3, "active": True},
        "identity.renumber": {"ok": True, "renumbered": {UNIQ: 1, "bb": 2}},
    })
    fora = aba.reconectar(_ctx(), {}, p)
    assert p.chamadas == ["coop.sync", "identity.renumber"], (
        "a ORDEM é a entrega: renumerar antes de reconciliar compactaria uma "
        "lista que ainda não está completa")
    #: **A FRASE MUDOU DE DONO E DE LÍNGUA — JOGAR-02, 09/09/2026.** Era
    #: `home_actions.reconciliar_toast`, a frase da JANELA GTK, e ela dizia
    #: *"Jogadores reconciliados — 3 jogador(es). Numeração compactada em 2
    #: controle(s)."* — a língua de dentro (`CoopManager.sync`,
    #: `identity.compact`) escrita na tela dela, e o número de CONTROLES sem
    #: dizer QUAIS.
    #:
    #: Agora a frase nomeia o assento, que é a palavra que esta tela já usa, e
    #: a régua a lê do dono novo (`painel._RENUMEROU`) em vez de digitá-la.
    assert fora["recado"] == painel._RENUMEROU.format(quais="P1, P2"), (
        "o recibo deixou de ser a frase do dono e virou texto deste arquivo")
    assert "P1" in fora["recado"] and "P2" in fora["recado"], (
        "o recibo não disse QUAIS controles foram renumerados — um número "
        "sozinho obriga ela a descobrir quais")


def test_a_recusa_por_jogo_aberto_nao_e_falha_nem_recado() -> None:
    """Com os jogadores já de pé, um recado de erro seria a interface mentindo.

    **E DEIXOU DE SER RECADO NENHUM — JOGAR-02, 09/09/2026.** A recusa do
    passo 2 com o jogo aberto não é falha E não é notícia: o passo 1 fez o que
    o botão promete. O gesto sai sem `recado`, e a tela responde com a piscada
    verde no botão — que é como esta casa diz "deu certo" desde a 03-Q4.

    **A MORDIDA:** tire `sessao_de_jogo_aberta` de `painel._sem_noticia` e o
    gesto volta a pousar uma caixa verde em cima da identidade do cartão.
    """
    p = _PonteQueResponde({
        "coop.sync": {"players": 2},
        "identity.renumber": {"ok": False, "reason": "sessao_de_jogo_aberta"},
    })
    assert aba.reconectar(_ctx(), {}, p) is None


def test_a_numeracao_ja_compacta_nao_vira_recado() -> None:
    """"Já estava compacta" é a AUSÊNCIA de notícia — o caso do print dela.

    A frase que ela mandou remover era exatamente esta::

        Jogadores reconciliados — 2 jogador(es). A numeração já estava compacta.

    **A MORDIDA:** faça `_sem_noticia` devolver `False` para o `renumbered`
    vazio e a frase volta, em cima do cartão do P1.
    """
    p = _PonteQueResponde({
        "coop.sync": {"players": 2},
        "identity.renumber": {"ok": True, "renumbered": {}},
    })
    assert aba.reconectar(_ctx(), {}, p) is None


def test_o_acabamento_mudo_nao_derruba_o_gesto() -> None:
    """`identity.renumber` sem resposta vira "não consegui conferir", não erro."""
    p = _PonteQueResponde({
        "coop.sync": {"players": 1},
        "identity.renumber": RuntimeError("o daemon não respondeu"),
    })
    fora = aba.reconectar(_ctx(), {}, p)
    #: **CONTINUA SENDO NOTÍCIA:** "não consegui conferir" é o produto dizendo
    #: que não fez, e silêncio sobre isso é a mentira que esta casa persegue.
    assert fora is not None and fora["recado"] == painel._NAO_CONFERIU


def test_sem_o_primeiro_passo_o_botao_recusa_dizendo() -> None:
    """A MORDIDA do recibo, e é o defeito inteiro: o botão que respondia calado.

    Clicar com o serviço fora do ar e clicar com ele vivo produziam exatamente
    a mesma tela. Agora o primeiro levanta `RuntimeError`, que é o canal da
    recusa laranja no cartão.
    """
    p = _PonteQueResponde({"coop.sync": RuntimeError("o daemon não respondeu")})
    with pytest.raises(RuntimeError) as erro:
        aba.reconectar(_ctx(), {}, p)
    assert str(erro.value) == painel.RECONECTAR_SEM_SERVICO
    assert "identity.renumber" not in p.chamadas, (
        "o acabamento correu com a reconciliação caída — a numeração mudaria "
        "sobre uma lista que ninguém reconciliou")


def test_a_recusa_nao_afirma_que_nada_aconteceu() -> None:
    """Um teto de tempo estourado é trabalho POSSIVELMENTE feito sem resposta.

    É a cicatriz que a `a09_sistema.SEM_RESPOSTA_DO_SERVICO` escreve por
    extenso, e a frase daqui não pode desfazê-la afirmando o contrário.
    """
    frase = painel.RECONECTAR_SEM_SERVICO
    assert "não reconectei" not in frase.lower()
    assert "nada" not in frase.lower(), (
        "a recusa afirmou que nada aconteceu — ninguém mediu isso")


def test_a_prova_declarada_pede_o_corpo_e_nao_o_bool() -> None:
    """`PROVAS` é o contrato do clique, e ele mudou junto com o gesto.

    Se alguém devolver `chamar` para o "Reconectar Controles", o recibo volta a
    ser impossível — `chamar` devolve `bool` e joga o corpo fora.
    """
    prova = next(p for p in aba.PROVAS if p["gesto"] == "reconectar")
    assert [c[0] for c in prova["chama"]] == ["resultado", "resultado"]
    assert "resultado" in aba.PONTE
