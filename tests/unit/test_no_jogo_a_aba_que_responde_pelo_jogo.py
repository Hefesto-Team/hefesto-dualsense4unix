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

from tests.conftest import exigir_gi_real

exigir_gi_real("test_no_jogo_a_aba_que_responde_pelo_jogo: importa código da janela GTK")

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


def _pedido_de_vibracao(ha_s: float = 0.2) -> list[dict[str, Any]]:
    """Um anel de vibração com um PEDIDO de verdade: motor não-nulo e fresco.

    NO-JOGO-SEM-FALSO-VERDE-01/T1 (25/08/2026). Desde esta leva a linha
    "vibração" só fica verde com PROVA de pedido: o carimbo `rumble` sozinho
    sai também da PARADA do SDL, que chega sem jogo nenhum na mesa — medido na
    bancada dela em 23/08, com zero DualSense e nenhum jogo aberto
    (`ff_parada_sdl_count: 1`, `ff_nao_nulo_count: 0`), e a linha ficou verde
    por três segundos. Todo teste que quer dizer "o jogo está vibrando" passa a
    dizê-lo pelo anel, que é onde o payload guarda a diferença — e sempre
    guardou.
    """
    return [
        {
            "ha_s": ha_s,
            "flag0": 4,
            "flag1": 0,
            "flag2": 0,
            "weak": 40,
            "strong": 90,
            "ramo": "v1",
        }
    ]


def _por_recurso(estado: dict[str, Any]) -> dict[str, Any]:
    return {
        linha.recurso: linha for linha in linhas_do_controle(_PRIMARIO, estado)
    }


def test_o_que_atravessa_agora_aparece_como_no_jogo_agora() -> None:
    """Giroscópio e vibração fluindo: a linha diz "no jogo agora" com o número."""
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
    """As duas situações que mandam agir em lugares opostos."""
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
    """A recência é lida do `visto_ha_s`, e o teto é o do card (3,0 s)."""
    fresco = _por_recurso(_estado(_vpad(visto_ha_s={"lightbar": 1.0})))
    velho = _por_recurso(_estado(_vpad(visto_ha_s={"lightbar": 73.0})))

    assert fresco["lightbar"].texto == "no jogo agora"
    assert velho["lightbar"].texto == "parou"


_MESMA_COISA_NO_CARD = {
    "no jogo agora": "No jogo agora",
    "parou": "pararam",
    "sem pedido ainda": "sem pedido ainda",
}


def test_as_tres_palavras_sao_as_do_card_no_singular() -> None:
    """O vocabulário não é novo: ele é o da linha do card, sem o plural."""
    assert set(PALAVRA_DA_SITUACAO.values()) == set(_MESMA_COISA_NO_CARD), (
        "esta aba ganhou (ou perdeu) uma palavra de situação. Ela tem de vir "
        "da linha do card — e o par correspondente tem de entrar no mapa acima"
    )
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
    """Os seis nomes têm de aparecer, iguais, na linha do card."""
    estado = _estado(_vpad())
    do_card = resumo_do_que_chega_ao_jogo(_PRIMARIO, estado) or ""

    for recurso in RECURSOS:
        assert NOME_DO_RECURSO[recurso] in do_card, (
            f"{recurso!r} aparece como {NOME_DO_RECURSO[recurso]!r} nesta aba "
            "e com outro nome no card"
        )


def test_mascara_xbox_explica_em_vez_de_acusar() -> None:
    """Giroscópio e touchpad não chegam, e o motivo não é defeito nosso."""
    estado = _estado(
        _vpad(
            visto_ha_s={"rumble": 0.3},
            ff_ultimos_reports=_pedido_de_vibracao(0.3),
            motion_forwards=0,
        ),
        flavor="xbox",
    )
    linhas = _por_recurso(estado)

    for recurso in ("giroscopio", "touchpad"):
        texto = linhas[recurso].texto
        assert "o jogo vê este controle como Xbox 360" in texto, (
            f"a frase de `{recurso}` perdeu o sujeito — ela volta a afirmar "
            f"sobre o aparelho o que só vale para o canal: {texto!r}")
        assert recurso.replace("giroscopio", "giroscópio") in texto
        assert "no Hefesto ele segue ativo" in texto, (
            f"a frase de `{recurso}` deixou de dizer que o recurso continua "
            f"vivo no produto — sem isso ela lê-se como «você não tem»")
    assert linhas["vibracao"].texto == "no jogo agora"
    for recurso in ("giroscopio", "touchpad"):
        for palavra in PALAVRA_DA_SITUACAO.values():
            assert palavra not in linhas[recurso].texto


def test_conexao_nativa_diz_o_que_acontece_em_vez_de_ficar_vazia() -> None:
    """No Nativo não há gamepad virtual — e a tela tem de DIZER isso."""
    estado = _estado(native=True, gamepad=False)

    assert recado_global(estado) == TEXTO_NATIVO
    assert not tem_controle_no_jogo(_PRIMARIO, estado)
    assert "direto" in TEXTO_NATIVO
    assert texto_do_contexto(estado) == "Conexão Nativa (Sony)"


def test_controlar_o_pc_afirma_so_o_que_o_daemon_sabe() -> None:
    """A frase fala do que NÓS entregamos, nunca do que o jogo faz."""
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
    """Payload incompleto não autoriza inventar nome de máscara."""
    estado = _estado(_vpad(), flavor="arco-iris")

    assert texto_do_contexto(estado) == "Jogar pelo Hefesto"


def test_sem_vpad_no_modo_jogo_a_aba_diz_o_que_observa_e_o_que_fazer() -> None:
    """"Jogar pelo Hefesto" e mesmo assim nenhum controle virtual casado."""
    estado = _estado()

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
    """Ela olha uma aba, olha a outra, e o nome do aparelho bate."""
    assert titulo_do_painel(_PRIMARIO) == "Controle 1 — USB · Jogador 1"


_PROIBIDAS = (
    "o jogo recebeu",
    "o jogo está recebendo",
    "o jogo recebe",
    "funcionando no jogo",
    "confirmado pelo jogo",
)


def test_nenhuma_frase_afirma_que_o_jogo_consumiu_o_dado() -> None:
    """Varre TODOS os textos que a aba consegue produzir."""
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


class _Rotulo:
    """Dublê de `Gtk.Label` com o mínimo que o sync toca."""

    def __init__(self) -> None:
        self.texto = ""
        self.markup = ""
        self.visivel = False

    def set_text(self, texto: str) -> None:
        self.texto = texto
        self.markup = ""

    def set_markup(self, markup: str) -> None:
        self.markup = markup
        self.texto = markup

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
        self._no_jogo_perfil = _Rotulo()
        self._no_jogo_vazio = _Rotulo()
        self._no_jogo_paineis: dict[Any, _Painel] = {}
        self._no_jogo_keys: list[Any] = []
        self.reconstrucoes = 0
        self._sync = sa.StatusActionsMixin._sync_paineis_no_jogo.__get__(self)
        self._status_card_keys_for = sa.StatusActionsMixin._status_card_keys_for
        self._connected_controllers = sa.StatusActionsMixin._connected_controllers
        self._sync_visibilidade_no_jogo = (
            sa.StatusActionsMixin._sync_visibilidade_no_jogo.__get__(self)
        )
        self._pagina_do_notebook = (
            sa.StatusActionsMixin._pagina_do_notebook.__get__(self)
        )

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
    """O mesmo gate do tique de 10 Hz da Status, pelo mesmo motivo medido."""
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_STATUS

    janela = _sincronizar(ABA_STATUS, _estado(_vpad(motion_streaming=True)))

    assert janela._no_jogo_contexto.texto == ""
    assert janela.reconstrucoes == 0


def test_com_a_aba_a_vista_o_tique_pinta_contexto_e_paineis(
    sem_notebook_real: None,
) -> None:
    """E do outro lado do gate ele trabalha — senão o teste acima passaria com"""
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_NO_JOGO

    janela = _sincronizar(ABA_NO_JOGO, _estado(_vpad(motion_streaming=True)))

    assert janela._no_jogo_contexto.texto.startswith("Jogar pelo Hefesto")
    assert janela.reconstrucoes == 1
    assert [p.chamadas for p in janela._no_jogo_paineis.values()] != [[]]


def test_daemon_desligado_esvazia_a_aba_em_vez_de_congelar(
    sem_notebook_real: None,
) -> None:
    """Sem daemon, o último estado bom não pode ficar na tela como se fosse de"""
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_NO_JOGO

    janela = _sincronizar(ABA_NO_JOGO, None)

    assert janela._no_jogo_contexto.texto == TEXTO_OFFLINE
    assert janela._no_jogo_paineis == {}
    assert janela._no_jogo_vazio.visivel is False, (
        '"Nenhum controle conectado." com o daemon desligado seria uma '
        "afirmação sobre uma mesa que ninguém conseguiu olhar"
    )


def test_no_nativo_o_recado_substitui_os_paineis(sem_notebook_real: None) -> None:
    """A explicação é UMA, e não uma cópia dela dentro de cada painel."""
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_NO_JOGO

    janela = _sincronizar(ABA_NO_JOGO, _estado(native=True, gamepad=False))

    assert janela._no_jogo_recado.texto == TEXTO_NATIVO
    assert janela._no_jogo_paineis == {}
    assert janela._no_jogo_vazio.visivel is False


def test_o_aviso_do_perfil_sai_colorido_e_aparece_ate_no_nativo(
    sem_notebook_real: None,
) -> None:
    """PERFIL-MUDO-01, do estado até o pixel. Duas mordidas numa."""
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_NO_JOGO
    from hefesto_dualsense4unix.app.widgets.painel_no_jogo import (
        COR_DO_AVISO_DE_PERFIL,
    )

    estado = _estado(native=True, gamepad=False)
    estado["active_profile"] = "fallback"
    estado["perfil_do_jogo_que_nao_entrou"] = [
        {"nome": "Pragmata", "frase": 'O perfil "Pragmata" não entrou: X.'}
    ]
    janela = _sincronizar(ABA_NO_JOGO, estado)

    assert janela._no_jogo_perfil.visivel is True
    assert COR_DO_AVISO_DE_PERFIL in janela._no_jogo_perfil.markup
    assert "Pragmata" in janela._no_jogo_perfil.markup
    assert "não entrou" in janela._no_jogo_perfil.markup
    assert "fallback" in janela._no_jogo_perfil.markup
    assert janela._no_jogo_recado.texto == TEXTO_NATIVO


def test_nome_de_perfil_com_e_comercial_nao_quebra_o_markup(
    sem_notebook_real: None,
) -> None:
    """Terceira mordida: o escape do Pango."""
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_NO_JOGO

    estado = _estado()
    estado["active_profile"] = "fallback"
    estado["perfil_do_jogo_que_nao_entrou"] = [
        {"nome": "Rock & Roll", "frase": 'O perfil "Rock & Roll" <não> entrou.'}
    ]
    janela = _sincronizar(ABA_NO_JOGO, estado)

    markup = janela._no_jogo_perfil.markup
    assert "&amp;" in markup and "&lt;não&gt;" in markup
    assert markup.count("<") == markup.count("<span") + markup.count("</span")


def test_sem_aviso_de_perfil_a_linha_fica_escondida(sem_notebook_real: None) -> None:
    """O caso comum — nenhum perfil ficou de fora — não deixa rótulo em branco."""
    from hefesto_dualsense4unix.app.actions.status_actions import ABA_NO_JOGO

    janela = _sincronizar(ABA_NO_JOGO, _estado())

    assert janela._no_jogo_perfil.visivel is False
    assert janela._no_jogo_perfil.texto == ""
