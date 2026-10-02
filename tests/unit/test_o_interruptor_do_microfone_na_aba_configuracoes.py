"""QUATRO-MICROFONES-01 (E1) — o interruptor de microfone existe, num card só."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o interruptor de microfone da seção Os controles")

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_controles
from hefesto_dualsense4unix.app.actions.config.secao_controles import (
    DICA_MIC_NO_CABO,
    DICA_MIC_NO_RADIO,
    DICA_MIC_SEM_CANAL,
    DICA_MIC_SEM_ENDERECO,
    TEXTO_DO_MIC,
    _BlocoDoMicrofone,
    _PainelDosControles,
    dica_do_microfone,
    frase_da_capacidade_do_mic,
    pode_ligar_o_mic,
    tem_canal_de_captura,
)
from hefesto_dualsense4unix.app.widgets.external_card import (
    DadosDoControle,
    ExternalCard,
)
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    PALAVRAS_DE_CULPA,
    SLOTS_POR_SEGUNDO,
)

UM = "aabbcc000001"
DOIS = "aabbcc000002"
OITO_BITDO = "e8473a000007"


def _dados(**over: Any) -> DadosDoControle:
    base: dict[str, Any] = dict(
        chave=UM,
        titulo="Jogador 1",
        subtitulo="Sony · Bluetooth",
        uniq=UM,
        slot=1,
        adotado=True,
        no_cabo=False,
        endereco=UM,
    )
    base.update(over)
    return DadosDoControle(**base)


def _assentar() -> None:
    for _ in range(200):
        if not Gtk.events_pending():
            break
        Gtk.main_iteration()


def _card_com_o_bloco(dados: DadosDoControle, *, ligado: bool = False) -> tuple[
    Any, _BlocoDoMicrofone, list[tuple[str, bool]]
]:
    """Um card de produção com o bloco encaixado, numa janela offscreen."""
    cliques: list[tuple[str, bool]] = []
    card = ExternalCard(dados)
    bloco = _BlocoDoMicrofone(
        dados,
        ligado=ligado,
        ao_alternar=lambda chave, valor: cliques.append((chave, valor)),
    )
    bloco.encaixar(card)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.show_all()
    _assentar()
    return card, bloco, cliques


def _rotulos(widget: Any, achados: list[str] | None = None) -> list[str]:
    """Todo texto visível na árvore — é assim que se pergunta "está na tela?"."""
    achados = [] if achados is None else achados
    with_label = getattr(widget, "get_label", None)
    if callable(with_label):
        texto = with_label()
        if texto:
            achados.append(str(texto))
    filhos = getattr(widget, "get_children", None)
    if callable(filhos):
        for filho in filhos():
            _rotulos(filho, achados)
    return achados


class TestOInterruptorEstaNaTela:
    def test_o_dualsense_no_radio_ganha_o_interruptor_e_ele_e_clicavel(self) -> None:
        card, bloco, _ = _card_com_o_bloco(_dados())

        assert TEXTO_DO_MIC in _rotulos(card), (
            "o interruptor de microfone não aparece no card: a ponte volta a "
            "só subir por variável de ambiente"
        )
        assert bloco.botao.get_sensitive() is True

    def test_no_cabo_o_interruptor_esta_aceso_e_a_dica_so_informa(self) -> None:
        """A queixa 15 dela, em forma de régua — 04/09/2026."""
        card, bloco, _ = _card_com_o_bloco(_dados(no_cabo=True))

        assert TEXTO_DO_MIC in _rotulos(card), "o interruptor SUMIU no cabo"
        assert bloco.botao.get_sensitive() is True, (
            "o interruptor de microfone nasceu APAGADO no cabo — é a frase "
            "invertida da queixa 15 dela de volta, e o CSV desta casa diz o "
            "contrário: audio.microfone tem cabo_aciona=sim"
        )
        assert bloco.botao.get_tooltip_text() == DICA_MIC_NO_CABO

    def test_a_dica_do_cabo_informa_e_nao_recusa(self) -> None:
        """A frase do cabo é CAPACIDADE, não advertência — e ela dizia o inverso."""
        for proibida in ("só vale", "não passa", "sem ela"):
            assert proibida not in DICA_MIC_NO_CABO.lower(), (
                f"{proibida!r} voltou à dica do cabo: ela é informação sobre "
                "por onde o canal vem, nunca recusa (D-12)"
            )
        assert "já existe" in DICA_MIC_NO_CABO

    def test_sem_endereco_a_dica_diz_o_outro_motivo(self) -> None:
        """Os dois motivos de estar apagado pedem frases diferentes."""
        dados = _dados(endereco="")
        assert pode_ligar_o_mic(dados) is False
        assert dica_do_microfone(dados) == DICA_MIC_SEM_ENDERECO

    def test_sem_canal_de_captura_a_dica_nao_fala_de_endereco(self) -> None:
        """Sem canal, o endereço não interessa — e a frase não pode mentir.

        `dica_do_microfone` respondia a TODA recusa com a frase do endereço, e
        isso aparecia como um controle com doze hexa sendo recusado por não ter
        endereço. As duas perguntas agora são feitas na ordem em que mandam.
        """
        dados = _dados(adotado=False)
        assert tem_canal_de_captura(dados) is False
        assert dica_do_microfone(dados) == DICA_MIC_SEM_CANAL

    def test_no_radio_a_dica_diz_que_a_escolha_e_dela_e_e_de_um_so(self) -> None:
        assert dica_do_microfone(_dados()) == DICA_MIC_NO_RADIO
        assert "este controle" in DICA_MIC_NO_RADIO
        assert "desligado" in DICA_MIC_NO_RADIO

    def test_o_valor_inicial_nao_declara_nada_sozinho(self) -> None:
        """`set_active` EMITE "toggled". Com o handler já ligado, abrir a janela"""
        _card, _bloco, cliques = _card_com_o_bloco(_dados(), ligado=True)
        assert cliques == []

    def test_um_card_ligado_nasce_marcado(self) -> None:
        _card, bloco, _ = _card_com_o_bloco(_dados(), ligado=True)
        assert bloco.botao.get_active() is True


class _HostFalso:
    """O `HefestoApp` reduzido ao que a seção lê — sem GTK e sem daemon."""

    def __init__(self, controles: list[dict[str, Any]]) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self._edit_target_uniq: str | None = None
        self._controles_leitor = lambda: {"controllers": controles, "external": []}
        self._cor_do_plastico_leitor = lambda _u: None
        self._mesa_limpa_leitor = lambda: False


def _painel_montado(
    monkeypatch: pytest.MonkeyPatch, controles: list[dict[str, Any]],
    declarado: dict[str, Any] | None = None,
) -> tuple[_PainelDosControles, _HostFalso, Any]:
    """A seção montada pelo MÉTODO DE PRODUÇÃO, com o disco fora do caminho."""
    from hefesto_dualsense4unix.utils.maquina import ControleDeclarado, MaquinaConfig

    monkeypatch.setattr(
        secao_controles,
        "carregar_maquina",
        lambda: MaquinaConfig(
            controles={
                chave: ControleDeclarado(**campos)
                for chave, campos in (declarado or {}).items()
            }
        ),
    )
    monkeypatch.setattr(secao_controles, "run_in_thread", lambda *a, **k: None)

    host = _HostFalso(controles)
    painel = _PainelDosControles(host)
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    janela = Gtk.OffscreenWindow()
    janela.add(caixa)
    painel.montar(caixa)
    janela.show_all()
    _assentar()
    return painel, host, caixa


def _entrada(uniq: str, *, transporte: str = "bt") -> dict[str, Any]:
    return {
        "uniq": uniq,
        "transport": transporte,
        "connected": True,
        "player_slot": 1 if uniq == UM else 2,
        "name": "Sony Interactive Entertainment Wireless Controller",
        "vid": "054c",
        "pid": "0ce6",
    }


class TestOGesto:
    def test_ligar_escreve_no_rascunho_e_nao_no_disco(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O clique acumula; quem grava é o "Aplicar" do rodapé (`D-A4`)."""
        painel, host, _caixa = _painel_montado(monkeypatch, [_entrada(UM)])
        bloco = painel._microfones[UM]

        bloco.botao.set_active(True)

        assert host._maquina_pendente == {"controles": {UM: {"microfone": True}}}

    def test_desligar_volta_para_nao_sei_e_nao_grava_um_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida que mais importa deste arquivo."""
        painel, host, _caixa = _painel_montado(
            monkeypatch, [_entrada(UM)], declarado={UM: {"microfone": True}}
        )
        bloco = painel._microfones[UM]
        assert bloco.botao.get_active() is True, "o card não leu o que estava no disco"

        bloco.botao.set_active(False)

        assert host._maquina_pendente == {"controles": {UM: {"microfone": None}}}

    def test_ligar_um_nao_liga_o_outro(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A decisão dela, do lado da tela: quatro independentes."""
        painel, host, _caixa = _painel_montado(
            monkeypatch, [_entrada(UM), _entrada(DOIS)]
        )
        assert set(painel._microfones) == {UM, DOIS}

        painel._microfones[DOIS].botao.set_active(True)

        assert host._maquina_pendente == {"controles": {DOIS: {"microfone": True}}}
        assert painel._microfones[UM].botao.get_active() is False

    def test_a_secao_nao_manda_ipc_nenhum_no_clique(self) -> None:
        """Nenhum `machine.declare` e nenhuma chamada a `dualsense_bt_audio`."""
        fonte = Path(inspect.getfile(secao_controles)).read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        chamadas = {
            no.func.attr
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
        }
        assert "machine_declare" not in chamadas
        importados = {
            alvo
            for no in ast.walk(arvore)
            if isinstance(no, ast.ImportFrom) and no.module
            for alvo in (no.module,)
        } | {
            nome.name
            for no in ast.walk(arvore)
            if isinstance(no, ast.Import)
            for nome in no.names
        }
        assert not any("dualsense_bt_audio" in mod for mod in importados), (
            "a seção importou o módulo da ponte de áudio: o processo da janela "
            "não pode subir um microfone a um clique de distância enquanto a "
            "posse do hidraw não for arbitrada"
        )

    def test_o_interruptor_so_aparece_em_dualsense_adotado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ponte é Opus tunelado num report HID da Sony (`0x31`/`0x32`)."""
        painel, _host, _caixa = _painel_montado(monkeypatch, [_entrada(UM)])
        painel._aplicar(
            {
                "controllers": [],
                "external": [
                    {
                        "uniq": "e8:47:3a:00:00:07",
                        "name": "Nintendo Co., Ltd. Pro Controller",
                        "vid": "057e",
                        "pid": "2009",
                        "bus": "bluetooth",
                        "driver": "nintendo",
                        "identity": OITO_BITDO,
                    }
                ],
            }
        )
        assert painel._microfones == {}


class TestAFraseDeCapacidade:
    def test_a_frase_de_capacidade_e_derivada_do_medidor(self) -> None:
        """Nenhum número digitado: os quatro saem das constantes de `radio_da_mesa`."""
        frase = frase_da_capacidade_do_mic()

        for valor in (HZ_INPUT_SEM_MIC, HZ_INPUT_COM_MIC, HZ_AUDIO_COM_MIC):
            esperado = f"{valor:.1f}".replace(".", ",")
            assert esperado in frase, f"{esperado} não está na frase: {frase!r}"
        assert str(SLOTS_POR_SEGUNDO) in frase

        fonte = Path(inspect.getfile(secao_controles)).read_text(encoding="utf-8")
        corpo = fonte.split("def frase_da_capacidade_do_mic")[1].split("\ndef ")[0]
        for literal in ("260,4", "170,5", "106,2", "276,7"):
            assert literal not in corpo, (
                f"{literal!r} está digitado na frase de capacidade. Ele tem de "
                "sair das constantes de `integrations/radio_da_mesa`, senão a "
                "tela e a barra do medidor podem discordar sobre o mesmo fato."
            )

    def test_a_frase_nao_culpa_o_controle(self) -> None:
        """A mesma lista que o medidor de rádio varre, pela mesma razão."""
        minuscula = frase_da_capacidade_do_mic().lower()
        for palavra in PALAVRAS_DE_CULPA:
            assert palavra not in minuscula, (
                f"a frase de capacidade contém {palavra!r} — ela é informação "
                "de capacidade, não advertência (decisão dela, 22/08/2026)"
            )

    def test_a_frase_nao_ressuscita_o_preco_contra_o_giroscopio(self) -> None:
        """O trade-off contra giroscópio foi DERRUBADO em 22/08/2026."""
        textos = " ".join(
            (frase_da_capacidade_do_mic(), DICA_MIC_NO_RADIO, DICA_MIC_NO_CABO)
        ).lower()
        for proibida in ("girosc", "mira", "250"):
            assert proibida not in textos, (
                f"{proibida!r} voltou ao texto do interruptor: a comparação "
                "entre a taxa do rádio e a taxa NATIVA DO CABO é a armadilha "
                "nº 1 desta casa, e ela já foi derrubada uma vez"
            )

    def test_a_frase_aparece_uma_unica_vez_na_secao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """São 208px de largura por card: a mesma frase cinco vezes vira ruído."""
        _painel, _host, caixa = _painel_montado(
            monkeypatch, [_entrada(UM), _entrada(DOIS)]
        )
        frase = frase_da_capacidade_do_mic()
        assert _rotulos(caixa).count(frase) == 1
