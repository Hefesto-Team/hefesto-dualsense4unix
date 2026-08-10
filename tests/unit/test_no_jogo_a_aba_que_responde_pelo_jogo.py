"""A aba "No jogo" — o que atravessa para o jogo, e nos TRÊS modos.

O pedido dela, literal (09/08/2026), depois de perguntar como validar
giroscópio e touchpad:

    *"eu sei que a aba status é uma coisa, mas isso converter em input seja via
    xbox ou dualsense ou nativo é outra"*

A aba Status responde pelo controle FÍSICO. Esta bancada cobra a aba que
responde pelo JOGO — e cobra, acima de tudo, que ela não invente regra nova:
quem decide se um recurso está chegando, parou ou nunca foi pedido continua
sendo `controller_card.estado_do_recurso`, dona única dessa decisão desde a
PAINEL-DA-VERDADE-01. Um segundo dono aqui divergiria do card na primeira
mudança, e a mesma janela passaria a dizer duas coisas sobre o mesmo controle.

O que estes testes travam, em ordem de importância:

1. **as três palavras** — "no jogo agora", "parou" e "sem pedido ainda" — e a
   distinção entre as duas últimas, que mandam agir em lugares opostos;
2. **os três modos** — máscara DualSense, máscara Xbox 360 e Conexão Nativa —,
   que é a pergunta que a aba existe para fechar;
3. **o caso sem gamepad virtual**, em que a tela não pode ficar vazia nem
   mentir;
4. **o vocabulário** — nenhuma frase pode afirmar que o JOGO consumiu o dado.
   Essa medição é de fora e depende de qual biblioteca o jogo carregou (01/08:
   a `libSDL2` do Ubuntu não enumerava o gamepad virtual; a SDL3 da Steam
   enumerava). É a regra que mais custou nesta casa;
5. **o gate de aba à vista**, que é o que impede o poller de trabalhar para
   ninguém.

Sem GTK de propósito: tudo aqui é função pura ou dublê, e o arquivo roda no
`lint-test` do CI, que não tem PyGObject (CI-GUI-PULAVA-CALADO-01).
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.widgets.controller_card import (
    resumo_do_que_chega_ao_jogo,
)
from hefesto_dualsense4unix.app.widgets.painel_no_jogo import (
    NOME_DO_RECURSO,
    PALAVRA_DA_SITUACAO,
    RECURSOS,
    TEXTO_DESKTOP,
    TEXTO_NATIVO,
    TEXTO_OFFLINE,
    TEXTO_SEM_VPAD,
    linhas_do_controle,
    recado_do_controle,
    recado_global,
    tem_controle_no_jogo,
    texto_do_contexto,
    titulo_do_painel,
)

#: O controle primário, sem número de jogador — o caso de mesa de um controle.
_PRIMARIO: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "player": 1,
    "player_slot": 1,
}


def _estado(
    vpad: dict[str, Any] | None = None,
    *,
    flavor: str = "dualsense",
    native: bool = False,
    gamepad: bool = True,
) -> dict[str, Any]:
    """Um `state_full` mínimo com (ou sem) o vpad do jogador 1."""
    return {
        "connected": True,
        "native_mode": native,
        "gamepad_emulation": {"enabled": gamepad, "flavor": flavor},
        "controllers": [dict(_PRIMARIO)],
        "rumble_ff": {"per_vpad": [vpad] if vpad else []},
    }


def _vpad(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"player": 1, "visto_ha_s": {}}
    base.update(extra)
    return base


def _por_recurso(estado: dict[str, Any]) -> dict[str, Any]:
    return {
        linha.recurso: linha for linha in linhas_do_controle(_PRIMARIO, estado)
    }


# ---------------------------------------------------------------------------
# As três palavras, e a distinção que elas carregam
# ---------------------------------------------------------------------------


def test_o_que_atravessa_agora_aparece_como_no_jogo_agora() -> None:
    """Giroscópio e vibração fluindo: a linha diz "no jogo agora" com o número.

    Mordida: trocar `PALAVRA_DA_SITUACAO[SITUACAO_CHEGANDO]` por qualquer outra
    coisa derruba as duas primeiras asserções; tirar o `_detalhe` do texto
    derruba as duas últimas, que são o número que ela lê na tela.
    """
    estado = _estado(
        _vpad(
            motion_streaming=True,
            motion_hz=158.3,
            motion_forwards=48210,
            rumble_no_fisico=[30, 120],
            rumble_no_fisico_ha_s=0.4,
            visto_ha_s={"rumble": 0.4},
        )
    )
    linhas = _por_recurso(estado)

    assert linhas["giroscopio"].texto.startswith("no jogo agora")
    assert linhas["vibracao"].texto.startswith("no jogo agora")
    assert "158 Hz" in linhas["giroscopio"].texto
    assert "30/120" in linhas["vibracao"].texto


def test_parou_e_sem_pedido_ainda_sao_frases_diferentes() -> None:
    """As duas situações que mandam agir em lugares opostos.

    "Nunca começou" é fiação; "parou" é o espelho/o rádio que caiu. Quem as
    separa é `motion_forwards`, o contador cumulativo de janelas que o vpad de
    fato escreveu — e a regra é do card, não daqui.

    Mordida: apagar `motion_forwards` do vpad "parado" faz as duas linhas
    saírem iguais, e a primeira asserção reprova.
    """
    parado = _por_recurso(
        _estado(_vpad(motion_streaming=False, motion_forwards=12904))
    )
    nunca = _por_recurso(
        _estado(_vpad(motion_streaming=False, motion_forwards=0))
    )

    assert parado["giroscopio"].texto != nunca["giroscopio"].texto
    assert parado["giroscopio"].texto == "parou"
    assert nunca["giroscopio"].texto == "sem pedido ainda"


def test_o_carimbo_velho_vira_parou_e_o_fresco_vira_no_jogo_agora() -> None:
    """A recência é lida do `visto_ha_s`, e o teto é o do card (3,0 s).

    Mordida: fixar a idade em algo abaixo do teto nos dois casos faz a segunda
    asserção reprovar — que é exatamente o defeito de uma tela que diz "está
    chegando" olhando um contador cumulativo.
    """
    fresco = _por_recurso(_estado(_vpad(visto_ha_s={"lightbar": 1.0})))
    velho = _por_recurso(_estado(_vpad(visto_ha_s={"lightbar": 73.0})))

    assert fresco["lightbar"].texto == "no jogo agora"
    assert velho["lightbar"].texto == "parou"


#: A palavra desta aba -> o rótulo de GRUPO que a linha do card usa para a
#: mesma situação. Só uma difere, e só em número: o card enumera vários
#: recursos de uma vez ("pararam: gatilho, luz") e aqui cada linha fala de um
#: ("parou"). Nenhuma outra palavra entrou.
_MESMA_COISA_NO_CARD = {
    "no jogo agora": "No jogo agora",
    "parou": "pararam",
    "sem pedido ainda": "sem pedido ainda",
}


def test_as_tres_palavras_sao_as_do_card_no_singular() -> None:
    """O vocabulário não é novo: ele é o da linha do card, sem o plural.

    Palavra nova nesta tela seria conceito novo, e a regra da casa é que nome
    que não deriva do que já está na tela é sinal de erro de conceito.

    Mordida: inventar uma quarta palavra em `PALAVRA_DA_SITUACAO` (ou trocar
    "sem pedido ainda" por "nunca chegou") derruba a primeira asserção, porque
    a palavra nova não tem par no card.
    """
    assert set(PALAVRA_DA_SITUACAO.values()) == set(_MESMA_COISA_NO_CARD), (
        "esta aba ganhou (ou perdeu) uma palavra de situação. Ela tem de vir "
        "da linha do card — e o par correspondente tem de entrar no mapa acima"
    )
    # Uma mesa em que as TRÊS situações aparecem de uma vez: giroscópio
    # fluindo, luz vista há muito tempo, e o resto sem pedido nenhum.
    estado = _estado(
        _vpad(
            motion_streaming=True,
            motion_hz=158.3,
            visto_ha_s={"lightbar": 73.0},
        )
    )
    do_card = resumo_do_que_chega_ao_jogo(_PRIMARIO, estado) or ""

    for palavra, no_card in _MESMA_COISA_NO_CARD.items():
        assert no_card in do_card, (
            f"a situação que esta aba chama de {palavra!r} não aparece na "
            f"linha do card como {no_card!r} — as duas telas passaram a ter "
            "vocabulários diferentes para a mesma coisa"
        )


def test_os_nomes_dos_recursos_sao_os_mesmos_do_card() -> None:
    """Os seis nomes têm de aparecer, iguais, na linha do card.

    É o teste que impede as duas telas de divergirem: se alguém renomear
    "clique do touchpad" aqui, o card continua com o nome antigo e a mesma
    janela passa a ter dois nomes para o mesmo recurso.

    Mordida: escrever `NOME_DO_RECURSO` à mão neste módulo (em vez de importar
    a lista-dona) e mudar um nome faz o `in` reprovar.
    """
    estado = _estado(_vpad())  # tudo em "sem pedido ainda": a linha cita os 6
    do_card = resumo_do_que_chega_ao_jogo(_PRIMARIO, estado) or ""

    for recurso in RECURSOS:
        assert NOME_DO_RECURSO[recurso] in do_card, (
            f"{recurso!r} aparece como {NOME_DO_RECURSO[recurso]!r} nesta aba "
            "e com outro nome no card"
        )


# ---------------------------------------------------------------------------
# Os três modos — a pergunta que a aba existe para fechar
# ---------------------------------------------------------------------------


def test_mascara_xbox_explica_em_vez_de_acusar() -> None:
    """Giroscópio e touchpad não chegam, e o motivo não é defeito nosso.

    A API do controle de Xbox declara 8 eixos e 11 botões: não há onde pôr IMU
    nem dedo. A linha EXPLICA isso; a vibração e a luz continuam medidas.

    Mordida: fazer a aba tratar `SITUACAO_IMPOSSIVEL` como as outras três (isto
    é, colar a palavra "sem pedido ainda" na frente da explicação) faz a
    primeira asserção reprovar.
    """
    estado = _estado(
        _vpad(visto_ha_s={"rumble": 0.3}, motion_forwards=0), flavor="xbox"
    )
    linhas = _por_recurso(estado)

    assert linhas["giroscopio"].texto == "a máscara Xbox 360 não tem giroscópio"
    assert linhas["touchpad"].texto == "a máscara Xbox 360 não tem touchpad"
    assert linhas["vibracao"].texto == "no jogo agora"
    for recurso in ("giroscopio", "touchpad"):
        for palavra in PALAVRA_DA_SITUACAO.values():
            assert palavra not in linhas[recurso].texto


def test_conexao_nativa_diz_o_que_acontece_em_vez_de_ficar_vazia() -> None:
    """No Nativo não há gamepad virtual — e a tela tem de DIZER isso.

    Ficar vazia seria pior que mentir: ela olharia uma aba morta e concluiria
    que quebrou. E dizer "não chega nada" seria falso — no Nativo chega TUDO,
    justamente porque não há nada nosso no meio.

    Mordida: devolver `None` em `recado_global` para o Nativo faz a aba cair no
    caminho dos painéis, e a primeira asserção reprova com a aba vazia.
    """
    estado = _estado(native=True, gamepad=False)

    assert recado_global(estado) == TEXTO_NATIVO
    assert not tem_controle_no_jogo(_PRIMARIO, estado)
    assert "direto" in TEXTO_NATIVO
    assert texto_do_contexto(estado) == "Conexão Nativa (Sony)"


def test_controlar_o_pc_afirma_so_o_que_o_daemon_sabe() -> None:
    """A frase fala do que NÓS entregamos, nunca do que o jogo faz.

    "Nenhum jogo recebe nada" seria uma afirmação sobre o mundo inteiro tirada
    de um campo do nosso payload. "O Hefesto não entrega controle nenhum ao
    jogo" é o que o daemon de fato sabe.

    Mordida: trocar a frase por uma que comece com "o jogo" faz a última
    asserção reprovar.
    """
    estado = _estado(gamepad=False)

    assert recado_global(estado) == TEXTO_DESKTOP
    assert texto_do_contexto(estado) == "Controlar o PC"
    assert "o Hefesto não entrega" in TEXTO_DESKTOP


def test_a_linha_de_contexto_nomeia_o_modo_e_a_mascara() -> None:
    """É o que faz a foto da tela dizer de QUAL dos três modos ela é.

    Os rótulos são os da aba Início, importados de lá — a mesma coisa não pode
    ter dois nomes em duas abas (é a regra que o
    `test_vocabulario_das_quatro_superficies` cobra entre as quatro
    superfícies).

    Mordida: escrever "Xbox"/"DualSense" à mão neste módulo faz as duas
    primeiras asserções reprovarem no dia em que a aba Início renomear.
    """
    assert (
        texto_do_contexto(_estado(_vpad(), flavor="xbox"))
        == "Jogar pelo Hefesto · O jogo vê o controle como: Xbox 360"
    )
    assert texto_do_contexto(_estado(_vpad())) == (
        "Jogar pelo Hefesto · O jogo vê o controle como: "
        "DualSense (botões PlayStation)"
    )
    assert texto_do_contexto(None) == TEXTO_OFFLINE


def test_mascara_desconhecida_diz_o_modo_e_cala_sobre_o_resto() -> None:
    """Payload incompleto não autoriza inventar nome de máscara.

    Mesma família de erro que esta casa já removeu do
    `texto_do_custo_da_mascara` (o `or "xbox"` que afirmava por omissão).

    Mordida: cair num `str(flavor)` cru faz a asserção ver "arco-iris" no
    texto.
    """
    estado = _estado(_vpad(), flavor="arco-iris")

    assert texto_do_contexto(estado) == "Jogar pelo Hefesto"


# ---------------------------------------------------------------------------
# O caso sem gamepad virtual — nem vazio, nem mentira
# ---------------------------------------------------------------------------


def test_sem_vpad_no_modo_jogo_a_aba_diz_o_que_observa_e_o_que_fazer() -> None:
    """"Jogar pelo Hefesto" e mesmo assim nenhum controle virtual casado.

    É o único dos três casos sem vpad que pode ser transitório, e por isso o
    único com conselho: a frase diz o que se observa, que costuma resolver
    sozinho, e aponta o gesto que já existe na aba Início.

    Mordida: fazer `recado_do_controle` devolver `None` (ou a frase do Nativo)
    aqui faz a aba ficar com um painel vazio — a primeira asserção reprova.
    """
    estado = _estado()  # modo gamepad, `per_vpad` vazio

    assert recado_do_controle(_PRIMARIO, estado) == TEXTO_SEM_VPAD
    assert recado_global(estado) is None, (
        "sem vpad no modo jogo é fato de UM controle: pode valer para um e não "
        "para o outro na mesma mesa, então não pode virar recado da janela"
    )
    assert "Reconciliar jogadores" in TEXTO_SEM_VPAD


def test_o_secundario_sem_reader_nao_ganha_linha_inventada() -> None:
    """Fora do co-op todos vêm como jogador 1, e só o primário tem espelho.

    O casamento controle->vpad é do card (`_item_do_vpad`), com essa regra
    sutil dentro. Esta aba não a repete — ela deriva de `estado_do_recurso`.

    Mordida: casar por `player` aqui, ignorando o `is_primary`, faz o
    secundário herdar as linhas do vpad do primário e a asserção reprova.
    """
    secundario = {**_PRIMARIO, "index": 1, "is_primary": False}
    estado = _estado(_vpad(motion_streaming=True, motion_hz=200.0))

    assert not tem_controle_no_jogo(secundario, estado)
    assert recado_do_controle(secundario, estado) == TEXTO_SEM_VPAD


def test_o_titulo_do_painel_e_o_mesmo_do_card_do_status() -> None:
    """Ela olha uma aba, olha a outra, e o nome do aparelho bate.

    Mordida: montar o título aqui ("Jogador 1", "vpad 1"...) em vez de chamar
    `titulo_do_card` faz a asserção reprovar.
    """
    assert titulo_do_painel(_PRIMARIO) == "Controle 1 — USB · Jogador 1"


# ---------------------------------------------------------------------------
# O vocabulário — a regra que mais custou nesta casa
# ---------------------------------------------------------------------------

#: Frases proibidas: todas afirmam que o JOGO consumiu o dado. O daemon não
#: sabe disso, e o erro é fácil — em 01/08 uma medição contra a biblioteca
#: errada produziu um diagnóstico convincente e falso.
_PROIBIDAS = (
    "o jogo recebeu",
    "o jogo está recebendo",
    "o jogo recebe",
    "funcionando no jogo",
    "confirmado pelo jogo",
)


def test_nenhuma_frase_afirma_que_o_jogo_consumiu_o_dado() -> None:
    """Varre TODOS os textos que a aba consegue produzir.

    Mordida: trocar "no jogo agora" por "o jogo está recebendo" — que é
    literalmente a pergunta dela, e por isso a tentação — faz este teste
    reprovar na hora.
    """
    estados = [
        _estado(_vpad(motion_streaming=True, motion_hz=158.0)),
        _estado(_vpad(visto_ha_s={"rumble": 90.0}), flavor="xbox"),
        _estado(native=True, gamepad=False),
        _estado(gamepad=False),
        _estado(),
    ]
    textos: list[str] = [TEXTO_NATIVO, TEXTO_DESKTOP, TEXTO_SEM_VPAD]
    for estado in estados:
        textos.append(texto_do_contexto(estado))
        textos.append(recado_global(estado) or "")
        textos.append(recado_do_controle(_PRIMARIO, estado) or "")
        textos.extend(
            linha.texto for linha in linhas_do_controle(_PRIMARIO, estado)
        )

    for texto in textos:
        for proibida in _PROIBIDAS:
            assert proibida not in texto.lower(), (
                f"{texto!r} afirma que o JOGO consumiu o dado. O daemon sabe "
                "que o dado saiu daqui e que alguém escreveu de volta — não "
                "sabe o que o jogo fez com ele."
            )


# ---------------------------------------------------------------------------
# O gate de aba à vista — o poller que não trabalha para ninguém
# ---------------------------------------------------------------------------


class _Rotulo:
    """Dublê de `Gtk.Label` com o mínimo que o sync toca."""

    def __init__(self) -> None:
        self.texto = ""
        self.visivel = False

    def set_text(self, texto: str) -> None:
        self.texto = texto

    def set_visible(self, visivel: bool) -> None:
        self.visivel = bool(visivel)


class _Slot:
    def get_children(self) -> list[Any]:
        return []

    def pack_start(self, *_a: Any, **_k: Any) -> None:
        return None

    def show_all(self) -> None:
        return None


class _Painel:
    def __init__(self) -> None:
        self.chamadas: list[dict[str, Any]] = []

    def atualizar(self, entry: dict[str, Any], _estado: dict[str, Any]) -> None:
        self.chamadas.append(entry)


class _Janela:
    """Só o que `_sync_paineis_no_jogo` usa da mixin, com o método REAL."""

    def __init__(self, aba_a_vista: str | None) -> None:
        from hefesto_dualsense4unix.app.actions import status_actions as sa

        self.aba_a_vista = aba_a_vista
        self._no_jogo_slot = _Slot()
        self._no_jogo_contexto = _Rotulo()
        self._no_jogo_recado = _Rotulo()
        self._no_jogo_vazio = _Rotulo()
        self._no_jogo_paineis: dict[Any, _Painel] = {}
        self._no_jogo_keys: list[Any] = []
        self.reconstrucoes = 0
        self._sync = sa.StatusActionsMixin._sync_paineis_no_jogo.__get__(self)
        self._status_card_keys_for = sa.StatusActionsMixin._status_card_keys_for
        self._connected_controllers = sa.StatusActionsMixin._connected_controllers

    def _get(self, widget_id: str) -> Any:
        return object() if widget_id == "main_notebook" else None

    def _rebuild_paineis_no_jogo(self, _slot: Any, keys: list[Any]) -> None:
        self.reconstrucoes += 1
        self._no_jogo_keys = list(keys)
        self._no_jogo_paineis = {chave: _Painel() for chave in keys}


@pytest.fixture
def sem_notebook_real(monkeypatch: pytest.MonkeyPatch) -> None:
    """`id_da_pagina_corrente` responde o que a janela dublada disser."""
    from hefesto_dualsense4unix.app.actions import status_actions as sa

    monkeypatch.setattr(
        sa, "id_da_pagina_corrente", lambda _nb: _JANELA_ATUAL.aba_a_vista
    )


_JANELA_ATUAL: Any = None


def _sincronizar(aba_a_vista: str | None, estado: Any) -> _Janela:
    global _JANELA_ATUAL
    janela = _Janela(aba_a_vista)
    _JANELA_ATUAL = janela
    janela._sync(estado)
    return janela


def test_com_outra_aba_a_vista_o_tique_nao_pinta_nada(
    sem_notebook_real: None,
) -> None:
    """O mesmo gate do tique de 10 Hz da Status, pelo mesmo motivo medido.

    Pintar com outra aba na frente é CPU que ninguém vê — e um poller cego já
    custou 104% de um núcleo nesta casa (BUG-GUI-IDLE-ADD-BUSY-LOOP-01).

    MORDIDA: tirar o `return` do gate faz a primeira asserção reprovar.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_STATUS

    janela = _sincronizar(ABA_STATUS, _estado(_vpad(motion_streaming=True)))

    assert janela._no_jogo_contexto.texto == ""
    assert janela.reconstrucoes == 0


def test_com_a_aba_a_vista_o_tique_pinta_contexto_e_paineis(
    sem_notebook_real: None,
) -> None:
    """E do outro lado do gate ele trabalha — senão o teste acima passaria com
    uma aba que nunca pinta nada."""
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_NO_JOGO

    janela = _sincronizar(ABA_NO_JOGO, _estado(_vpad(motion_streaming=True)))

    assert janela._no_jogo_contexto.texto.startswith("Jogar pelo Hefesto")
    assert janela.reconstrucoes == 1
    assert [p.chamadas for p in janela._no_jogo_paineis.values()] != [[]]


def test_daemon_desligado_esvazia_a_aba_em_vez_de_congelar(
    sem_notebook_real: None,
) -> None:
    """Sem daemon, o último estado bom não pode ficar na tela como se fosse de
    agora — é a mentira confortável que esta aba existe para não contar.

    MORDIDA: fazer `_render_offline` deixar de chamar o sync (ou o sync tratar
    `None` como "não mexe") faz a segunda asserção reprovar.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_NO_JOGO

    janela = _sincronizar(ABA_NO_JOGO, None)

    assert janela._no_jogo_contexto.texto == TEXTO_OFFLINE
    assert janela._no_jogo_paineis == {}
    assert janela._no_jogo_vazio.visivel is False, (
        '"Nenhum controle conectado." com o daemon desligado seria uma '
        "afirmação sobre uma mesa que ninguém conseguiu olhar"
    )


def test_no_nativo_o_recado_substitui_os_paineis(sem_notebook_real: None) -> None:
    """A explicação é UMA, e não uma cópia dela dentro de cada painel.

    MORDIDA: deixar `recado_global` fora do sync faz a segunda asserção
    reprovar com um painel por controle repetindo a mesma frase.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_NO_JOGO

    janela = _sincronizar(ABA_NO_JOGO, _estado(native=True, gamepad=False))

    assert janela._no_jogo_recado.texto == TEXTO_NATIVO
    assert janela._no_jogo_paineis == {}
    assert janela._no_jogo_vazio.visivel is False
