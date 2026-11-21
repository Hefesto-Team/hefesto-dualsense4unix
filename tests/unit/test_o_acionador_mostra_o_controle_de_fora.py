"""O-ACIONADOR-ENTREGA-A-UM-CONTROLE-DE-FORA-02 — a janela do acionador mostra o controle de fora.

A lista «Usar como botões de» oferece todo controle da mesa que recebe as teclas (DualSense, Pro
Controller e 8BitDo); o desenho e o nome de cada botão seguem o modelo escolhido (B, A e ZL no Pro
onde o DualSense diz Cruz, Círculo e L2); o `maquina.json` continua guardando o nome do DualSense,
e o desenho se lê pelo mapa posicional que o leitor do físico já tem.

A régua nunca abre o ``/sys`` nem o ``/dev/input``; os controles são dicionários de mentira, com
a faixa forjada ``aa:bb:cc`` e os octetos 4 e 5 zerados.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.linhagem_nintendo import OUIS_CLONE

RAIZ = Path(__file__).resolve().parents[2]
ENSAIO = RAIZ / "mockup" / "08-conexoes.html"
ARTE = RAIZ / "assets" / "control-svg"
DS = "aabbcc000001"
PRO = "aabbcc000003"
XBOX = "aabbcc000005"
SEM_ENDERECO = "aabbcc000006"
OITO = f"{sorted(OUIS_CLONE)[0]}000004"


def _mac(chave: str) -> str:
    return ":".join(chave[i:i + 2] for i in range(0, 12, 2))


def _externos() -> list[dict[str, Any]]:
    return [
        {"vid": "057e", "pid": "2009", "uniq": _mac(PRO), "player_slot": 3},
        {"vid": "2dc8", "pid": "3106", "uniq": _mac(OITO), "player_slot": 4},
        {"vid": "045e", "pid": "0b12", "uniq": _mac(XBOX), "player_slot": 5},
        {"vid": "057e", "pid": "2009", "uniq": "", "player_slot": 6},
        {"vid": "057e", "pid": "2009", "uniq": _mac("aabbcc000007"), "player_slot": None},
    ]


def _ctx() -> Any:
    return SimpleNamespace(
        mesa=[{"uniq": _mac(DS), "nome": "Cosmic Red", "cor": "cosmic-red"}],
        externos=_externos())


@pytest.fixture
def a08() -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    a08_conexoes._RASCUNHO = None
    yield a08_conexoes
    a08_conexoes._RASCUNHO = None


def _cena(a08: Any, monkeypatch: pytest.MonkeyPatch, controle: str,
          teclas: list[list[Any]]) -> dict[str, Any]:
    ctx = _ctx()
    cena = {"aparelhos": [{"id": "A1", "chave": "1234:abcd:00000000", "tipo": "entrada",
                           "lugar": "L1", "nome": "Pedal", "rotulo": "Acionador USB",
                           "controle": controle, "fixo": True, "esperando": False,
                           "teclas": [tuple(t) for t in teclas]}],
            "lugares": [{"id": "L1"}],
            "quem_recebe": a08._quem_recebe_da_mesa(ctx, SimpleNamespace(acionadores={})),
            "colorway_de": a08._colorways_da_mesa(ctx),
            "modelo_de": a08._modelos_da_mesa(ctx)}
    monkeypatch.setattr(a08, "_CENA_NA_TELA", cena)
    return cena


TECLAS = [[256, "Tecla 1", "cross"], [257, "Tecla 2", "circle"], [258, "Pedal", "l2"]]


def test_a_lista_oferece_todo_controle_que_recebe_e_so_ele(a08: Any) -> None:
    """D-2011-O-ACIONADOR-DESENHA-O-CONTROLE-DE-FORA-PELO-MODELO: DualSense, Pro e 8BitDo entram.

    O Xbox (sem controle virtual), o sem endereço e o sem número de jogador ficam de fora.

    MORDIDA: tire de ``_quem_recebe_da_mesa`` o laço de ``_os_externos_que_recebem``.
    """
    ctx = _ctx()
    assert a08._quem_recebe_da_mesa(ctx, SimpleNamespace(acionadores={})) == [
        (DS, "Cosmic Red"), (PRO, "Pro Controller"), (OITO, "8BitDo")]
    assert a08._modelos_da_mesa(ctx) == {PRO: "pro", OITO: "8bitdo"}


def _nomes(html: str, sufixo: str) -> list[str]:
    return re.findall(rf'ac-n ac-n-{sufixo}">([^<]+)<', html)


def test_o_nome_do_botao_e_o_do_controle_escolhido_e_o_desenho_acende_a_peca_dele(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-O-ACIONADOR-DESENHA-O-CONTROLE-DE-FORA-PELO-MODELO: B, A e ZL no Pro.

    A janela traz o nome e o brilho de cada desenho, e o CSS mostra o do controle escolhido no
    seletor. No 8BitDo, sem as quatro direções, a direção acende o contorno do ``dpad`` inteiro.

    MORDIDA: faça ``nome_do_botao`` ou ``peca_do_botao`` ignorarem o modelo.
    """
    cena = _cena(a08, monkeypatch, PRO, [*TECLAS, [259, "Tecla 4", "dpad_up"],
                                                [260, "Tecla 5", "l3"]])
    campos = a08.campos_do_acionador(cena)
    teclas, brilho = campos["acionador-teclas"], campos["acionador-brilho"]
    de_fora = campos["acionador-brilho-de-fora"]
    assert _nomes(teclas, "ds") == ["Cruz", "Círculo", "L2", "Cima", "L3"]
    assert _nomes(teclas, "pro") == ["B", "A", "ZL", "D-pad cima", "L3"]
    assert _nomes(teclas, "8bitdo") == ["B", "A", "ZL", "Cima", "L3"]
    assert brilho.startswith(
        "#acionador #ac-cross,#acionador #ac-circle,#acionador #ac-l2,#acionador #ac-dpad_up,")
    assert "#ac-pro-" not in brilho
    assert ("#acionador #ac-pro-b,#acionador #ac-pro-a,#acionador #ac-pro-zl,"
            "#acionador #ac-pro-dpad_up,#acionador #ac-pro-stick_l{") in de_fora
    assert ("#acionador #ac-8bitdo-b,#acionador #ac-8bitdo-a,#acionador #ac-8bitdo-zl,"
            "#acionador #ac-8bitdo-dpad,#acionador #ac-8bitdo-stick_l{") in de_fora
    assert campos["acionador-desenho"] == ""
    assert f'<option value="{PRO}" data-modelo="pro" selected>' in campos["acionador-quem"]
    assert f'<option value="{OITO}" data-modelo="8bitdo">8BitDo' in campos["acionador-quem"]
    assert f'<option value="{DS}">' in campos["acionador-quem"]


def test_o_clique_no_desenho_do_pro_grava_o_nome_do_dualsense(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-O-ACIONADOR-DESENHA-O-CONTROLE-DE-FORA-PELO-MODELO: o «A» do Pro grava ``circle``.

    O desenho à vista é o do controle escolhido no seletor (a forma da janela o diz): o clique de
    uma peça de outro modelo é recusado, o 8BitDo não tem as direções para clicar, e escolher o
    DualSense devolve os nomes dele.

    MORDIDA: leia o ``botao_da_peca`` sem o modelo no ``acionador_botao``.
    """
    _cena(a08, monkeypatch, PRO, [[256, "Tecla 1", None], [257, "Tecla 2", None]])
    monkeypatch.setattr(a08, "_declaracao", lambda: SimpleNamespace(acionadores={}))
    a08.usar_como_botoes(None, {"alvo": "A1"}, None)

    def clica(entrada: str, quem: str, tecla: str = "256") -> None:
        a08.acionador_botao(
            None, {"entrada": entrada, "forma": {"tecla": tecla, "acionador-quem": quem}}, None)

    clica("a", PRO)
    clica("zl", PRO, "257")
    assert [t[2] for t in a08._RASCUNHO.teclas] == ["circle", "l2"]
    with pytest.raises(ValueError):
        clica("cross", PRO)
    assert a08._RASCUNHO.teclas[0][2] == "circle"
    with pytest.raises(ValueError):
        clica("dpad", OITO)
    clica("start", OITO)
    assert a08._RASCUNHO.teclas[0][2] == "options" and a08._RASCUNHO.controle == OITO
    clica("cross", DS)
    assert a08._RASCUNHO.teclas[0][2] == "cross" and a08._RASCUNHO.controle == DS


def _entradas_do_arquivo(arquivo: str) -> dict[str, str]:
    texto = (ARTE / arquivo).read_text(encoding="utf-8")
    return dict(re.findall(r'data-entrada="([^"]+)"(?:[^>]*?)data-evdev="([^"]+)"', texto))


@pytest.mark.parametrize(("modelo", "arquivo"), [("pro", "nintendo-pro.svg"),
                                                 ("8bitdo", "8bitdo-sn30-pro.svg")])
def test_as_tabelas_do_pacote_sao_as_do_arquivo_e_cobrem_todo_botao_que_troca(
        a08: Any, modelo: str, arquivo: str) -> None:
    """D-2011-O-ACIONADOR-DESENHA-O-CONTROLE-DE-FORA-PELO-MODELO: o dado do pacote é o do desenho.

    Cada entrada da tabela existe no arquivo com o mesmo ``BTN_*``, e todo botão que a troca
    conhece tem peça no modelo (o 8BitDo cai no ``dpad`` nas quatro direções). O ``BTN_*`` do
    botão vem do mapa do leitor do físico.
    """
    no_arquivo = _entradas_do_arquivo(arquivo)
    tabela = a08.ENTRADAS_DO_MODELO[modelo]
    for evdev, (entrada, _) in tabela.items():
        assert no_arquivo.get(entrada) == evdev, (modelo, entrada)
    assert a08._evdev_do_botao("circle") == "BTN_EAST"
    assert a08._evdev_do_botao("l2") == "BTN_TL2"
    for _, motor, _ in a08._botoes_do_desenho():
        peca = a08.peca_do_botao(motor, modelo)
        assert peca in no_arquivo, (modelo, motor, peca)
        if peca != a08.O_DPAD_INTEIRO.get(modelo):
            assert a08.botao_da_peca(peca, modelo) == motor


def test_a_janela_do_mockup_traz_os_tres_desenhos_e_o_seletor_escolhe_o_que_aparece(
        a08: Any) -> None:
    """D-2011-O-ACIONADOR-DESENHA-O-CONTROLE-DE-FORA-PELO-MODELO: os três desenhos na janela.

    O DualSense primeiro, os de fora depois, cada peça de troca com o gesto, e a opção do Pro leva
    o modelo que o CSS lê para mostrar o desenho e os nomes dele.
    """
    janela = ENSAIO.read_text().split('id="acionador">', 1)[1].split('<div class="tela-nova"')[0]
    svgs = re.findall(r'<svg class="(ac-svg[^"]*)"', janela)
    assert svgs == ["ac-svg", "ac-svg ac-pro", "ac-svg ac-8bitdo"]
    assert f'<option value="{"aabbcc0000e1"}" data-modelo="pro">Pro Controller</option>' in janela
    assert _nomes(janela, "ds") == ["Cruz", "Círculo", "L2"]
    assert _nomes(janela, "pro") == ["B", "A", "ZL"]
    css = ENSAIO.read_text()
    for modelo in ("pro", "8bitdo"):
        assert (f'#acionador:has(.ac-quem option[data-modelo="{modelo}"]:checked) '
                f'.ac-desenho>.ac-{modelo}') in css
        assert (f'#acionador:has(.ac-quem option[data-modelo="{modelo}"]:checked) '
                f'.ac-para>.ac-n-{modelo}') in css
    for modelo in ("pro", "8bitdo"):
        svg = re.search(rf'<svg class="ac-svg ac-{modelo}".*?</svg>', janela, re.S)
        assert svg is not None
        com_gesto = set(re.findall(r'data-entrada="([^"]+)" data-gesto="acionador-botao" '
                                   r'data-hef-forma="acionador"', svg.group(0)))
        assert com_gesto == {e for e, _ in a08.ENTRADAS_DO_MODELO[modelo].values()}
        ids = re.findall(r'\sid="([^"]+)"', svg.group(0))
        assert ids and all(i.startswith(a08.PREFIXO_DA_PECA[modelo]) for i in ids)
        assert "#acionador svg.ac-" + modelo in svg.group(0)
    por_desenho = [set(re.findall(r'\sid="([^"]+)"', m.group(0)))
                   for m in re.finditer(r'<svg class="ac-svg.*?</svg>', janela, re.S)]
    assert len(por_desenho) == 3 and not (
        (por_desenho[0] & por_desenho[1]) | (por_desenho[0] & por_desenho[2])
        | (por_desenho[1] & por_desenho[2]))


def test_o_mockup_nao_leva_os_comentarios_das_artes() -> None:
    """D-2011-O-ACIONADOR-DESENHA-O-CONTROLE-DE-FORA-PELO-MODELO: as artes entram sem comentário.

    O código e o mockup não têm comentário; os arquivos de arte têm, e o gerador os tira ao embutir.

    MORDIDA: tire de ``_desenho_do_modelo`` a remoção dos comentários e regenere o mockup.
    """
    for arte in ARTE.glob("*.svg"):
        if arte.name in {"nintendo-pro.svg", "8bitdo-sn30-pro.svg"}:
            assert "<!--" in arte.read_text(encoding="utf-8"), arte.name
    assert "<!--" not in ENSAIO.read_text(encoding="utf-8")
