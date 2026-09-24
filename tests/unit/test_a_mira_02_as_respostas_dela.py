"""A-MIRA-POR-MOVIMENTO-NA-TELA-02 — as três respostas dela sobre a Mira Virtual.

Ela respondeu na página da sessão dos desenhos, em 24/09/2026 às 03h14
(`D-2409-*` no `docs/data/decisoes-dela.csv`):

1. **a dica do Giroscópio muda com a Mira acesa** — «Com a Mira Virtual acesa,
   o giro deste controle vai ao jogo pelo analógico direito.»; apagada, a de
   hoje. Por controle;
2. **no Modo Nativo o chip fica cinza e não grava** — *"A exceção do nativo
   todo o resto deve ter mira Virtual"*. A guarda mora no daemon (`mira.set`
   recusa), não só na tela; e em todo outro modo e caminho a Mira funciona,
   no cabo e no BT, do P1 ao P4;
3. **«Só enquanto eu segurar» e «Inverter» entram na tela**, no bloco da Mira
   da Calibrar, por controle, nascendo desligados.

Cada seção abaixo é uma resposta, e cada régua diz a MORDIDA: o que arrancar
para vê-la reprovar.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``), nunca um OUI real.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)
from tests.unit.test_a_mira_por_movimento_na_tela import (
    _OK,
    _P2,
    _P3,
    _P4,
    _RAIZ,
    _o_gesto,
    _PonteDaMira,
    _servidor_com_perfil,
)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    """O `REGISTRO` dos sensores é do processo: nada desta régua vaza dele."""
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o mesmo molde da régua da A-MIRA-01."""
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


def _mira_set(servidor: IpcServer, **params: Any) -> dict[str, Any]:
    return asyncio.run(servidor._handlers["mira.set"](params))


# ---------------------------------------------------------------------------
# 2. O NATIVO — o chip não grava, e a guarda mora no daemon
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ligada", [True, False])
def test_no_nativo_o_mira_set_recusa_o_chip_sem_escrever_nada(
    perfis: Path, tmp_path: Path, ligada: bool
) -> None:
    """`D-2409-NO-NATIVO-A-MIRA-FICA-CINZA`: o chip não grava no Nativo — nem
    para acender, nem para apagar —, e a recusa não deixa rastro no disco nem
    no vivo.

    MORDIDA: tire a guarda `if nativo and "ligada" in params` do
    `_handle_mira_set` e este teste reprova — o chip voltaria a gravar e
    avisar, que é a opção que ela recusou.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    servidor.daemon._native_mode = True
    corpo = _mira_set(servidor, uniq=_P3, ligada=ligada)
    assert corpo["status"] == "nativo", corpo
    assert corpo["uniq"] == _P3 and corpo["motivo"]
    assert not load_profile("Bancada").controllers, "a recusa gravou no perfil"
    assert not rot.por_peca(servidor.store), "a recusa mexeu no vivo"
    assert not REGISTRO.roteado(_P3)


def test_no_nativo_a_recusa_leva_o_pedido_inteiro(perfis: Path, tmp_path: Path) -> None:
    """Chip e ajuste no mesmo pedido: nada grava. Uma resposta que diz
    «recusei» com metade escrita seria a tela mentindo pela metade.

    MORDIDA: mova a guarda para depois do `save_profile` e este teste reprova.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    servidor.daemon._native_mode = True
    corpo = _mira_set(servidor, uniq=_P2, ligada=True, sensibilidade=9)
    assert corpo["status"] == "nativo"
    assert not load_profile("Bancada").controllers


def test_no_nativo_os_ajustes_da_calibrar_continuam_gravando(
    perfis: Path, tmp_path: Path
) -> None:
    """Os ajustes não acendem mira nenhuma: gravam, e valem quando o modo
    voltar. Escolha pelo padrão dela (a que custa menos a quem joga): ela
    pode deixar a Calibrar pronta no Nativo.

    MORDIDA: recuse qualquer campo no Nativo e este teste reprova.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    servidor.daemon._native_mode = True
    corpo = _mira_set(servidor, uniq=_P2, zona_morta_graus_s=24.0,
                      inverter_vertical=True, gatilho="l2")
    assert corpo["status"] == "ok" and corpo["ligada"] is False, corpo
    assert corpo["alcance"] == {"tique": "nao_se_aplica"}
    dele = load_profile("Bancada").controllers["aabbcc000002"].movimento
    assert (dele.zona_morta_graus_s, dele.inverter_vertical, dele.gatilho) == (
        24.0, True, "l2")
    assert "destino" not in dele.model_fields_set, (
        "o ajuste no Nativo escreveu o destino — a peça deixaria de seguir o perfil")


def test_fora_do_nativo_o_chip_grava(perfis: Path, tmp_path: Path) -> None:
    """O controle da guarda: o MESMO pedido, sem o Nativo, grava. Sem este
    caso a régua de cima passaria com um `mira.set` que recusa sempre."""
    servidor = _servidor_com_perfil(tmp_path)
    corpo = _mira_set(servidor, uniq=_P3, ligada=True)
    assert corpo["status"] == "ok" and corpo["ligada"] is True
    assert corpo["alcance"] == {"tique": "aplicado"} and corpo["ressalva"] is None


# ---------------------------------------------------------------------------
# 3. «SÓ ENQUANTO EU SEGURAR» E «INVERTER» — o IPC abre a porta que a tela tem
# ---------------------------------------------------------------------------


def test_o_gatilho_e_o_inverter_chegam_ao_disco_e_ao_vivo(
    perfis: Path, tmp_path: Path
) -> None:
    """Os três campos novos gravam NA PEÇA, só o que ela mexeu, e valem no
    próximo tique.

    MORDIDA: tire `gatilho` de `_CAMPOS_DA_MIRA` e este teste reprova com a
    recusa de chave desconhecida.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    _mira_set(servidor, uniq=_P4, ligada=True)
    corpo = _mira_set(servidor, uniq=_P4, gatilho="l2")
    assert corpo["status"] == "ok" and corpo["gatilho"] == "l2"
    corpo = _mira_set(servidor, uniq=_P4, inverter_horizontal=True)
    assert corpo["inverter_horizontal"] is True and corpo["inverter_vertical"] is False
    dele = load_profile("Bancada").controllers["aabbcc000004"].movimento
    assert dele.model_fields_set == {"destino", "gatilho", "inverter_horizontal"}
    vivo = rot.da_peca(servidor.store, _P4, rot.ativo(servidor.store))
    assert vivo is not None and (vivo.gatilho, vivo.inverter_horizontal) == ("l2", True)


def test_sempre_devolve_a_mira_sem_botao(perfis: Path, tmp_path: Path) -> None:
    """A opção «Sempre» manda `null` (a lista manda `""`): a peça volta a mirar
    sem botão, COM opinião — o gatilho do perfil não volta por baixo.

    MORDIDA: trate o `""` como campo omitido e este teste reprova.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot

    perfil = Profile(
        name="Bancada", match=MatchAny(type="any"),
        movimento=ProfileMovimentoConfig(destino="analogico_direito", gatilho="r1"),
    )
    servidor = _servidor_com_perfil(tmp_path, perfil)
    for vazio in ("", None):
        corpo = _mira_set(servidor, uniq=_P2, gatilho=vazio)
        assert corpo["status"] == "ok" and corpo["gatilho"] is None, (vazio, corpo)
        vivo = rot.da_peca(servidor.store, _P2, rot.ativo(servidor.store))
        assert vivo is not None and vivo.gatilho is None


@pytest.mark.parametrize("torto", ["ps", "touchpad", "l3_direcao", 7])
def test_o_ps_e_o_que_nao_e_botao_sao_recusados(
    perfis: Path, tmp_path: Path, torto: Any
) -> None:
    """O PS é a saída de emergência dela e nunca vira gatilho; o que não chega
    ao jogo como botão também não. Nada grava.

    MORDIDA: tire o validador de `ProfileMovimentoConfig.gatilho` e o caso
    `ps` reprova.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor_com_perfil(tmp_path)
    with pytest.raises(ValueError, match="gatilho"):
        _mira_set(servidor, uniq=_P3, gatilho=torto)
    assert not load_profile("Bancada").controllers, "a recusa gravou alguma coisa"


@pytest.mark.parametrize("torto", ["sim", 1, None])
def test_o_inverter_e_boolean(perfis: Path, tmp_path: Path, torto: Any) -> None:
    """Um `1` ou um `"sim"` não viram `True` calados."""
    servidor = _servidor_com_perfil(tmp_path)
    with pytest.raises(ValueError, match="inverter_vertical"):
        _mira_set(servidor, uniq=_P3, inverter_vertical=torto)


def test_a_leitura_de_volta_traz_os_tres(perfis: Path, tmp_path: Path) -> None:
    """O `state_full` publica o gatilho e os dois inverter de cada peça — é
    deles que o bloco da Calibrar pinta, e com a mira APAGADA também.

    MORDIDA: tire `gatilho` do `_merge_mira` e este teste reprova.
    """
    servidor = _servidor_com_perfil(tmp_path)
    _mira_set(servidor, uniq=_P3, gatilho="square", inverter_vertical=True)
    entradas: list[dict[str, Any]] = [{"uniq": _P2}, {"uniq": _P3}]
    servidor._merge_mira(entradas)
    assert entradas[0]["mira"]["gatilho"] is None
    assert entradas[0]["mira"]["inverter_horizontal"] is False
    assert entradas[1]["mira"]["ligada"] is False
    assert entradas[1]["mira"]["gatilho"] == "square"
    assert entradas[1]["mira"]["inverter_vertical"] is True


# ---------------------------------------------------------------------------
# A TELA 02 — a dica do Giroscópio (resposta 1) e o chip cinza (resposta 2)
# ---------------------------------------------------------------------------
# O desenho mora na BANCADA (`mockup/02-controles.html`) e espera o OK dela; o
# pacote já sabe pintar, e só pinta no dia em que a página publicada tiver o
# endereço.

#: AS PALAVRAS DELA, escritas aqui POR EXTENSO e não lidas do pacote: a régua
#: confere o pacote contra a decisão dela, não contra ele mesmo.
_DICA_DE_HOJE = "Ligado: o jogo recebe o giro deste controle."
_DICA_COM_A_MIRA = ("Com a Mira Virtual acesa, o giro deste controle vai ao jogo "
                    "pelo analógico direito.")


def _bancada_02() -> str:
    return (_RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")


def _ctx(nativo: bool = False, **miras: Any) -> Any:
    """Um `Contexto` com um controle por jogador, no cabo e no rádio.

    `miras` é `{uniq: bloco mira ou None}`; `None` = o daemon não publicou.
    """
    import pacotes

    conectados = []
    for n, (uniq, mira) in enumerate(miras.items()):
        dele: dict[str, Any] = {
            "uniq": uniq, "transport": "usb" if n % 2 == 0 else "bluetooth",
            "connected": True, "inputs": {}, "audio": {}, "speaker": {}}
        if mira is not None:
            dele["mira"] = mira
        conectados.append(dele)
    estado = {"native_mode": True} if nativo else {}
    return pacotes.Contexto(state=estado, mesa=[], conectados=conectados, estados={})


def _cards(monkeypatch: pytest.MonkeyPatch, ctx: Any) -> dict[str, dict[str, Any]]:
    import pacotes.a02_controles as a02

    monkeypatch.setattr(a02, "_so_se_a_pagina_tiver", lambda campos: campos)
    cards = a02.pacote(ctx)["cards"]
    assert cards, "o pacote não montou card nenhum — régua cega"
    return cards


def test_a_dica_do_giroscopio_muda_so_com_a_mira_acesa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`D-2409-A-DICA-DO-GIROSCOPIO-MUDA-COM-A-MIRA`, POR CONTROLE: o P2 com a
    Mira acesa diz a frase nova; o P3 apagado e o P4 sem leitura dizem a de hoje.

    MORDIDA: devolva sempre `DICA_DO_GIRO` em `dica_do_giro` e o P2 reprova;
    devolva sempre a nova e o P3 reprova.
    """
    cards = _cards(monkeypatch, _ctx(**{
        "aa:bb:cc:00:00:02": {"ligada": True},
        "aa:bb:cc:00:00:03": {"ligada": False},
        "aa:bb:cc:00:00:04": None,
    }))
    dicas = {u[-1]: c["giro-dica"] for u, c in cards.items()}
    assert dicas == {"2": _DICA_COM_A_MIRA, "3": _DICA_DE_HOJE, "4": _DICA_DE_HOJE}, dicas


def test_no_nativo_a_dica_de_hoje_volta_mesmo_com_a_mira_acesa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Nativo o jogo lê o controle físico — o giro chega como giroscópio, e
    a frase da Mira afirmaria o que não acontece.

    MORDIDA: tire o `and not nativo` de `dica_do_giro` e este teste reprova.
    """
    cards = _cards(monkeypatch, _ctx(nativo=True, **{"aa:bb:cc:00:00:02": {"ligada": True}}))
    assert next(iter(cards.values()))["giro-dica"] == _DICA_DE_HOJE


def test_no_nativo_o_chip_da_mira_fica_cinza_nos_quatro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`D-2409-NO-NATIVO-A-MIRA-FICA-CINZA`: o cinza acende em todo controle no
    Nativo, e em nenhum fora dele. O valor é o que o desenho espera.

    MORDIDA: devolva sempre `""` em `mira_fora` e o caso Nativo reprova.
    """
    import re

    esperado = re.findall(r'data-campo="mira-fora" data-hef-alvo="classe" '
                          r'data-hef-classe="sem-mira" data-hef-quando="([^"]+)"',
                          _bancada_02())
    assert esperado and set(esperado) == {"NATIVO"}, esperado
    miras = {f"aa:bb:cc:00:00:0{n}": {"ligada": n % 2 == 0} for n in (1, 2, 3, 4)}
    for nativo, valor in ((True, "NATIVO"), (False, "")):
        cards = _cards(monkeypatch, _ctx(nativo=nativo, **miras))
        assert {c["mira-fora"] for c in cards.values()} == {valor}, (nativo, cards)
        assert len(cards) == 4


def test_no_nativo_o_clique_no_chip_nao_chega_ao_daemon() -> None:
    """O chip cinza não pede nada: recusa antes da ponte, e a frase vai ao
    diário (o botão pisca a recusa; recado na tela, nenhum).

    MORDIDA: tire o `if _nativo(ctx)` do gesto `mira` e este teste reprova —
    o clique voltaria a chegar ao daemon.
    """
    import pacotes.a02_controles as a02

    p = _PonteDaMira(_OK)
    with pytest.raises(RuntimeError) as erro:
        _o_gesto("02-controles.html", "mira")(
            _ctx(nativo=True, **{"aa:bb:cc:00:00:01": {"ligada": False}}),
            {"uniq": "aa:bb:cc:00:00:01"}, p)
    assert str(erro.value) == a02.MIRA_CINZA_NO_NATIVO
    assert p.chamadas == [], "o chip cinza pediu ao daemon"


def test_o_nativo_que_o_daemon_recusa_volta_pela_mesma_frase() -> None:
    """A tela leu o estado um tique atrás: se o Nativo ligou no meio, quem
    recusa é o daemon (`status: "nativo"`), e a frase é a mesma do cinza —
    não a do controle que sumiu.

    MORDIDA: apague o ramo `status == "nativo"` do gesto e a frase vira
    `MIRA_SEM_O_CONTROLE`.
    """
    import pacotes.a02_controles as a02

    p = _PonteDaMira({"status": "nativo", "uniq": "aa:bb:cc:00:00:01", "motivo": "x"})
    with pytest.raises(RuntimeError) as erro:
        _o_gesto("02-controles.html", "mira")(
            _ctx(**{"aa:bb:cc:00:00:01": {"ligada": False}}),
            {"uniq": "aa:bb:cc:00:00:01"}, p)
    assert str(erro.value) == a02.MIRA_CINZA_NO_NATIVO
    assert p.chamadas == [{"ligada": True, "uniq": "aa:bb:cc:00:00:01"}]


@pytest.mark.parametrize(("entrada", "jogador"), [
    ({"is_primary": True}, 1),        # o primário, fora do co-op
    ({"player": 3}, 3),               # um secundário do co-op
])
def test_com_a_mira_acesa_o_cartao_nao_diz_que_o_giroscopio_flui(
    entrada: dict[str, Any], jogador: int,
) -> None:
    """O MESMO FATO DA RESPOSTA 1, na linha de cima do cartão: com a Mira acesa
    o filtro do report tira o giroscópio da janela daquele controle
    (`virtual_motion.REGISTRO.filtrar`), e o `motion_streaming` do vpad segue
    ligado pelo acelerômetro. «Giroscópio: fluindo para o jogo» ao lado da dica
    nova seria a tela dizendo as duas coisas sobre o mesmo giro.

    O Nativo e a máscara Xbox continuam com a frase deles — as duas seguem
    verdadeiras com a Mira acesa.

    MORDIDA: tire a guarda `mira.ligada` do `controller_card.texto_motion` e
    este teste reprova, no P1 e no P3.
    """
    import pacotes.a02_controles as a02

    from hefesto_dualsense4unix.app.widgets.controller_card import texto_motion

    estado: dict[str, Any] = {"rumble_ff": {"per_vpad": [
        {"player": jogador, "motion_streaming": True, "motion_hz": 250.0}]}}
    apagada = {**entrada, "mira": {"ligada": False}}
    acesa = {**entrada, "mira": {"ligada": True}}
    assert texto_motion(apagada, estado) == "Giroscópio: fluindo para o jogo (~250 Hz)"
    assert texto_motion(acesa, estado) is None
    nativo = texto_motion(acesa, {**estado, "native_mode": True})
    assert nativo and "direto com o controle" in nativo, nativo
    # E pelo pacote da aba, que é quem leva a linha à tela: o vazio a esconde.
    dele = {"uniq": _P2, "transport": "usb", "connected": True, "inputs": {},
            "audio": {}, "speaker": {}, **acesa}
    import pacotes

    ctx = pacotes.Contexto(state=estado, mesa=[], conectados=[dele], estados={})
    cards = a02.pacote(ctx)["cards"]
    assert [c["giro-no-jogo"] for c in cards.values()] == [""], cards


def test_a_bancada_tem_a_dica_e_o_cinza_em_cada_controle() -> None:
    """O desenho: a dica do Giroscópio no invólucro sem caixa, o botão SEM
    `title` próprio (ele calaria a dica que muda), e o cinza do chip da Mira
    na folha, com o cursor que recusa.

    MORDIDA: devolva o `title` ao botão do Giroscópio no `aba02.py` e o gerador
    para; tire a regra `.sem-mira` da folha e este teste reprova.
    """
    import re

    doc = _bancada_02()
    invol = re.findall(r'<span class="dica-do-giro" data-campo="giro-dica" '
                       r'data-hef-alvo="atributo" data-hef-atributo="title"'
                       r'(?: title="([^"]*)")?><button ([^>]*)>', doc)
    assert len(invol) == 4, invol
    assert sorted(t for t, _ in invol if t) == [_DICA_DE_HOJE] * 2
    assert not any("title=" in b for _, b in invol)
    assert ".sensores-peca .dica-do-giro{display:contents}" in doc
    folha = re.search(r'\.sensores-peca\.sem-mira \.sw\[data-gesto="mira"\],\s*'
                      r'\.sensores-peca\.sem-mira \.sw\[data-gesto="mira"\]:hover\{([^}]*)\}',
                      doc)
    assert folha and "cursor:not-allowed" in folha.group(1), "o cinza sumiu da folha"
    assert "var(--red)" not in folha.group(1), "cinza, nunca vermelho"


def test_antes_do_ok_dela_o_produto_nao_pinta_o_desenho_novo() -> None:
    """A página PUBLICADA não tem os dois endereços, e o pacote não emite para
    o vazio: o desenho novo só chega à janela dela depois do `--publicar`.

    MORDIDA: tire `giro-dica` e `mira-fora` de dentro do
    `_so_se_a_pagina_tiver` e este teste reprova.
    """
    import pacotes.a02_controles as a02

    publicado = (_RAIZ / "src/hefesto_dualsense4unix/interface/paginas/"
                 "02-controles.html").read_text(encoding="utf-8")
    if 'data-campo="giro-dica"' in publicado:
        pytest.skip("a 02 já foi publicada com a dica — a guarda cumpriu o papel")
    cards = a02.pacote(_ctx(**{"aa:bb:cc:00:00:02": {"ligada": True}}))["cards"]
    campos = next(iter(cards.values()))
    assert "giro-dica" not in campos and "mira-fora" not in campos


# ---------------------------------------------------------------------------
# A CALIBRAR — «Só enquanto eu segurar» e «Inverter» (resposta 3)
# ---------------------------------------------------------------------------

#: OS BOTÕES QUE O ESQUEMA ACEITA, com os nomes que a troca de botões da aba
#: Navegação já mostra — escritos aqui por extenso, e não lidos do gerador.
_BOTOES_DA_LISTA = [
    ("cross", "Cruz"), ("circle", "Círculo"), ("square", "Quadrado"),
    ("triangle", "Triângulo"), ("l1", "L1"), ("r1", "R1"), ("l2", "L2"),
    ("r2", "R2"), ("l3", "L3"), ("r3", "R3"), ("dpad_up", "D-pad Cima"),
    ("dpad_down", "D-pad Baixo"), ("dpad_left", "D-pad Esquerda"),
    ("dpad_right", "D-pad Direita"), ("options", "Options"), ("create", "Share"),
]


def _bancada_calibrar() -> str:
    return (_RAIZ / "mockup/calibrar-sensores.html").read_text(encoding="utf-8")


def _colunas_da_mira() -> list[str]:
    import re

    doc = _bancada_calibrar()
    return re.findall(r'<div class="mira" data-controle="p\d">(.*?)\n          </div>',
                      doc, re.S)


def test_a_lista_do_segurar_e_a_do_esquema_e_nasce_sempre() -> None:
    """Cada coluna tem a lista: «Sempre» escolhido de nascença, e depois os
    dezesseis botões que o esquema aceita, na ordem dele — nenhum PS.

    MORDIDA: acrescente `"ps"` à lista do gerador, ou tire o `selected` do
    «Sempre», e este teste reprova.
    """
    import re

    from hefesto_dualsense4unix.core.remapeamento_de_botao import REMAPEAVEIS

    assert [b for b, _ in _BOTOES_DA_LISTA] == list(REMAPEAVEIS), (
        "o esquema mudou a lista — releia a decisão antes de corrigir a régua")
    colunas = _colunas_da_mira()
    assert len(colunas) == 2, "a bancada do desenho tem dois controles"
    for coluna in colunas:
        lista = re.findall(r'<label class="desl"><span class="r">Só enquanto eu segurar'
                           r'</span><select class="lista" data-gesto="mira-segurar" '
                           r'data-campo="mira-segurar" data-hef-alvo="valor"[^>]*>(.*?)</select>',
                           coluna)
        assert len(lista) == 1, coluna
        opcoes = re.findall(r'<option value="([^"]*)"( selected)?>([^<]*)</option>', lista[0])
        assert opcoes[0] == ("sempre", " selected", "Sempre")
        assert [(v, r) for v, _, r in opcoes[1:]] == _BOTOES_DA_LISTA
        assert not any(s for _, s, _ in opcoes[1:]), "outro botão nasceu escolhido"


def test_os_dois_inverter_nascem_apagados_e_dizem_o_ato() -> None:
    """Dois interruptores por coluna, cada lado por si, APAGADOS de nascença,
    e o nome acessível diz o ato inteiro («Inverter cima e baixo»).

    MORDIDA: tire o `off` do gerador e este teste reprova.
    """
    import re

    for coluna in _colunas_da_mira():
        botoes = re.findall(r'<button class="([^"]*)" data-gesto="mira-inverter" '
                            r'data-inverter="([^"]*)" data-campo="([^"]*)"[^>]*'
                            r'aria-label="([^"]*)"><span class="p"></span>([^<]*)</button>',
                            coluna)
        assert [(q, c, a, r) for _, q, c, a, r in botoes] == [
            ("lado", "mira-inverter-lado", "Inverter esquerda e direita",
             "Esquerda e direita"),
            ("cima-baixo", "mira-inverter-cima-baixo", "Inverter cima e baixo",
             "Cima e baixo"),
        ], botoes
        assert all("off" in classe.split() for classe, *_ in botoes)
        assert '<span class="r">Inverter</span>' in coluna


def test_o_bloco_nao_tem_vermelho_nem_recado() -> None:
    """Os dois ajustes não trazem frase nova nem cor de alarme — só o rótulo."""
    doc = _bancada_calibrar()
    folha = doc.split("<style>", 1)[1].split("</style>", 1)[0]
    trecho = folha.split("«SÓ ENQUANTO EU SEGURAR» E «INVERTER»", 1)[1]
    assert "--red" not in trecho and "--orange" not in trecho


def _ctx_calibrar(**mira: Any) -> Any:
    import pacotes

    mesa = [{"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "jogador": 1,
             "cor": "cosmic-red", "nome": "Cosmic Red", "via": "USB"}]
    dele = {"uniq": "aa:bb:cc:00:00:01", "transport": "usb", "connected": True,
            "inputs": {}, "mira": mira}
    return pacotes.Contexto(state={}, mesa=mesa, conectados=[dele], estados={})


def test_a_calibrar_pinta_o_segurar_e_o_inverter(monkeypatch: pytest.MonkeyPatch) -> None:
    """A lista recebe o botão da peça (`sempre` quando é `None`) e os dois
    interruptores as três respostas: aceso, apagado e o travessão.

    MORDIDA: pinte o `None` como vazio e a lista nunca volta a «Sempre».
    """
    import mesa_viva
    from pacotes import a11_calibrar_sensores as a11

    import pacotes.a02_controles as a02

    monkeypatch.setattr(a11, "_TEM_A_MIRA", True)
    campos = a11.pacote(_ctx_calibrar(gatilho=None, inverter_horizontal=True,
                                      inverter_vertical=False))["colunas"]["p1"]
    assert campos["mira-segurar"] == "sempre"
    assert campos["mira-inverter-lado"] == a02.SENSOR_LIGADO
    assert campos["mira-inverter-cima-baixo"] == a02.SENSOR_DESLIGADO
    campos = a11.pacote(_ctx_calibrar(gatilho="l2"))["colunas"]["p1"]
    assert campos["mira-segurar"] == "l2"
    assert campos["mira-inverter-lado"] == mesa_viva.SEM_LEITOR
    # Sem a chave, a lista fica onde está; um botão que ela não oferece, também.
    for mira in ({}, {"gatilho": "ps"}):
        assert "mira-segurar" not in a11.pacote(_ctx_calibrar(**mira))["colunas"]["p1"]


def test_a_calibrar_pinta_cada_controle_com_o_dele(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do P1 ao P4, no USB e no BT: cada coluna recebe o botão e os dois
    «Inverter» do SEU controle — nunca só o P1 (a regra dela de 23/09).

    MORDIDA: faça o `pacote` ler o bloco `mira` do primeiro controle para
    todas as colunas e este teste reprova.
    """
    import pacotes
    from pacotes import a11_calibrar_sensores as a11

    import pacotes.a02_controles as a02

    monkeypatch.setattr(a11, "_TEM_A_MIRA", True)
    gatilhos = {1: None, 2: "l2", 3: "square", 4: "r1"}
    mesa = [{"pref": f"p{n}", "uniq": f"aa:bb:cc:00:00:0{n}", "jogador": n,
             "cor": "cosmic-red", "nome": "Cosmic Red", "via": "USB" if n % 2 else "BT"}
            for n in gatilhos]
    conectados = [{"uniq": f"aa:bb:cc:00:00:0{n}",
                   "transport": "usb" if n % 2 else "bluetooth", "connected": True,
                   "inputs": {},
                   "mira": {"gatilho": g, "inverter_horizontal": n == 3,
                            "inverter_vertical": n == 4}}
                  for n, g in gatilhos.items()]
    ctx = pacotes.Contexto(state={}, mesa=mesa, conectados=conectados, estados={})
    colunas = a11.pacote(ctx)["colunas"]
    assert {p: c["mira-segurar"] for p, c in colunas.items()} == {
        "p1": "sempre", "p2": "l2", "p3": "square", "p4": "r1"}
    ligado = a02.SENSOR_LIGADO
    assert [p for p, c in colunas.items() if c["mira-inverter-lado"] == ligado] == ["p3"]
    assert [p for p, c in colunas.items()
            if c["mira-inverter-cima-baixo"] == ligado] == ["p4"]


def test_escolher_o_botao_manda_um_campo_so() -> None:
    """A escolha vai ao `mira.set` sozinha; «Sempre» manda o vazio (que a ponte
    leva como `null`); o `click` de abrir a lista não é escolha.

    MORDIDA: trate o `click` como escolha e a lista regrava o perfil a cada vez
    que ela a abre para olhar; devolva `None` no `click` e a lista pisca o
    verde de «aplicado» só por ter sido aberta (o `armou` é o pouso sem
    piscada, `hefesto_vivo.CHAVE_DO_CLIQUE_QUE_SO_ARMOU`).
    """
    gesto = _o_gesto("calibrar-sensores.html", "mira-segurar")
    for valor, esperado in (("l2", "l2"), ("sempre", "")):
        p = _PonteDaMira(_OK)
        assert gesto(_ctx_calibrar(), {"uniq": "aa:bb:cc:00:00:01", "valor": valor,
                                       "tipo": "select", "evento": "change"}, p) is None
        assert p.chamadas == [{"uniq": "aa:bb:cc:00:00:01", "gatilho": esperado}]
    p = _PonteDaMira(_OK)
    volta = gesto(_ctx_calibrar(), {"uniq": "aa:bb:cc:00:00:01", "valor": "l2",
                                    "tipo": "select", "evento": "click"}, p)
    assert p.chamadas == [], "abrir a lista virou escolha"
    import hefesto_vivo as hv

    assert volta == {hv.CHAVE_DO_CLIQUE_QUE_SO_ARMOU: True}, (
        "abrir a lista voltou sem o `armou` — o piloto pisca «aplicado» sobre "
        "um clique que não aplicou nada")


@pytest.mark.parametrize("torto", ["ps", "", "touchpad"])
def test_o_ps_nao_passa_pela_lista(torto: str) -> None:
    """O PS é a saída de emergência dela: nem chega ao daemon."""
    p = _PonteDaMira(_OK)
    with pytest.raises(ValueError):
        _o_gesto("calibrar-sensores.html", "mira-segurar")(
            _ctx_calibrar(), {"uniq": "aa:bb:cc:00:00:01", "valor": torto,
                              "evento": "change"}, p)
    assert p.chamadas == []


def test_inverter_alterna_um_lado_pelo_que_o_daemon_diz() -> None:
    """Cada botão alterna O SEU lado, pelo estado lido — e só ele vai ao daemon.

    MORDIDA: mande `True` fixo e o segundo caso reprova; troque as chaves dos
    dois lados e o primeiro reprova.
    """
    gesto = _o_gesto("calibrar-sensores.html", "mira-inverter")
    for qual, chave in (("lado", "inverter_horizontal"),
                        ("cima-baixo", "inverter_vertical")):
        for agora in (False, True):
            p = _PonteDaMira(_OK)
            gesto(_ctx_calibrar(**{chave: agora}),
                  {"uniq": "aa:bb:cc:00:00:01", "inverter": qual}, p)
            assert p.chamadas == [{"uniq": "aa:bb:cc:00:00:01", chave: not agora}]


def test_inverter_sem_leitura_recusa_sem_chutar() -> None:
    """Sem o bloco, alternar é chutar o oposto: recusa e não chama."""
    import pacotes.a02_controles as a02

    p = _PonteDaMira(_OK)
    with pytest.raises(RuntimeError) as erro:
        _o_gesto("calibrar-sensores.html", "mira-inverter")(
            _ctx_calibrar(), {"uniq": "aa:bb:cc:00:00:01", "inverter": "lado"}, p)
    assert str(erro.value) == a02.SEM_LEITURA_DA_MIRA
    assert p.chamadas == []


def test_no_nativo_a_calibrar_grava_calada() -> None:
    """O ajuste no Nativo grava (`alcance: nao_se_aplica`) e não vira recusa:
    o aviso «grava e avisa» saiu com a decisão dela.

    MORDIDA: devolva o ramo `nao_se_aplica` ao `_pedir_a_mira` e reprova.
    """
    p = _PonteDaMira({"status": "ok", "alcance": {"tique": "nao_se_aplica"},
                      "ressalva": "Modo Nativo"})
    _o_gesto("calibrar-sensores.html", "mira-tremor")(
        _ctx_calibrar(), {"uniq": "aa:bb:cc:00:00:01", "valor": "20"}, p)
    assert p.chamadas == [{"uniq": "aa:bb:cc:00:00:01", "zona_morta_graus_s": 20.0}]


def test_a_ponte_leva_o_sempre_como_null(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ponte da tela: `gatilho=""` sai como `null` no pedido, e `None` não sai.

    MORDIDA: trate o `""` como `None` na ponte e «Sempre» vira pedido vazio.
    """
    from hefesto_dualsense4unix.app import ipc_bridge

    enviados: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(ipc_bridge, "_corpo_do_daemon",
                        lambda metodo, params: enviados.append((metodo, params)) or {})
    ipc_bridge.mira_set_detalhado(gatilho="", uniq="aa:bb:cc:00:00:01")
    ipc_bridge.mira_set_detalhado(inverter_vertical=False, uniq="aa:bb:cc:00:00:01")
    assert ipc_bridge.mira_set_detalhado(gatilho=None) is None
    assert enviados == [
        ("mira.set", {"gatilho": None, "uniq": "aa:bb:cc:00:00:01"}),
        ("mira.set", {"inverter_vertical": False, "uniq": "aa:bb:cc:00:00:01"}),
    ]


# ---------------------------------------------------------------------------
# A MATRIZ DO ITEM 2 — fora do Nativo, a Mira do CHIP anda em todo caminho
# ---------------------------------------------------------------------------
# *"todas as decisões e funcionalidades nunca é pensada só em um modo, rota,
# forma de conexão se cabo ou se bt, ou só pro player 1."*  <!-- noqa-acento: dela -->
#
# OS MODOS QUE EXISTEM, medidos em 24/09/2026 (`mode_transition.MODES` e
# `ProfileModeConfig`): `gamepad` (o Hefesto ligado, com o CAMINHO `dualsense`
# — o vpad `uhid` — ou `xbox` — o vpad `uinput`), `native` (o Modo Nativo) e
# `desktop` (a Navegação). A matriz abaixo é a do `gamepad`: os dois caminhos,
# os dois transportes e os quatro jogadores, com a mira acesa PELO CHIP
# (`mira.set`), e o analógico direito lido na SAÍDA de cada vpad de verdade —
# o report `0x01` do `uhid` e o `ABS_RX` do `uinput`. O `desktop` não entra:
# nele não há gamepad virtual (o `dispatch_gamepad` volta no `device is None`)
# e o analógico direito vira a roda do mouse (`uinput_mouse.dispatch`); a
# decisão de o chip ficar ou não cinza ali é dela, e está no relatório.
#
# E O QUARTO CHIP DA FILEIRA, o «Steam Input», NÃO É UMA LINHA A MAIS — medido
# na conferência, em `a01_jogar.o_que_o_chip_faz`: ele é `gamepad` com o
# caminho `dualsense` e o jogo na lista da Steam. No daemon é a MESMA linha do
# `dualsense` acima (o vpad `uhid` recebe a mira igual), e o que a Steam faz
# depois com o analógico direito é configuração dela, que esta régua não mede.
# Uma linha `steam` aqui repetiria a do `dualsense` com outro nome — a matriz
# que finge cobrir o que não exercita.

_GIRO = (0.0, 150.0, 0.0)


class _GravadorDeEvdev:
    """O nó `uinput` de mentira: guarda o último valor de cada eixo escrito.

    Do tamanho do `evdev.UInput` para o que o `UinputGamepad.forward_analog`
    usa — `write(tipo, código, valor)` e `syn()` —, e nada a mais.
    """

    def __init__(self) -> None:
        self.eixos: dict[int, int] = {}
        self.syns = 0

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        from evdev import ecodes

        if tipo == ecodes.EV_ABS:
            self.eixos[codigo] = valor

    def syn(self) -> None:
        self.syns += 1


def _vpad_de_verdade(caminho: str, jogador: int, fds: list[int]) -> tuple[Any, Any]:
    """O vpad DO CAMINHO, com o codificador de verdade, e o leitor do analógico
    direito que o jogo receberia.

    `dualsense` é o `UhidDualSense`: o fd vai ao `/dev/null` (o `send_report`
    escreve de verdade) e o analógico sai do corpo do report `0x01`, byte 2.
    `xbox` é o `UinputGamepad`: o nó é o gravador acima, e o analógico sai do
    `ABS_RX` que o `forward_analog` escreveu.
    """
    import os

    if caminho == "dualsense":
        from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

        pad = UhidDualSense(player=jogador, blueprint=None)
        pad._fd = os.open(os.devnull, os.O_WRONLY)
        fds.append(pad._fd)
        return pad, lambda: pad._encode_body()[2]
    from evdev import ecodes

    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

    pad = UinputGamepad.for_flavor("xbox")
    gravador = _GravadorDeEvdev()
    pad._device = gravador
    pad._ecodes = ecodes
    return pad, lambda: gravador.eixos.get(ecodes.ABS_RX)


def _servidor_da_matriz(tmp_path: Path, transporte: str, hub: Any) -> Any:
    """O `Daemon` e o `IpcServer` reais, com um perfil ATIVO SEM mira: quem
    acende a mira aqui é o CHIP, e só ele."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from tests.unit.test_a_mira_por_movimento_na_tela import _mesa_de_verdade

    perfil = Profile(name="Bancada", match=MatchAny(type="any"))
    save_profile(perfil)
    daemon, servidor = _mesa_de_verdade(tmp_path, transporte, hub)
    servidor.profile_manager.apply_movimento(perfil)
    servidor.store.set_active_profile(perfil.name)
    return daemon, servidor


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("caminho", ["dualsense", "xbox"])
def test_fora_do_nativo_a_mira_do_chip_anda_do_p1_ao_p4(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    caminho: str, transporte: str,
) -> None:
    """Os dois caminhos, os dois transportes e os quatro jogadores: o chip
    acende a mira de cada um, e o analógico direito que o JOGO recebe anda.

    MORDIDAS, as três conferidas em 24/09/2026: faça o `mira.set` recusar
    `ligada` em todo modo (a guarda sem o `nativo`) e os quatro casos reprovam;
    arranque o `aplicar_o_movimento` do `coop.CoopManager.forward_all` e os
    quatro reprovam pelos P2 a P4; arranque-o do `gamepad.dispatch_gamepad` e
    os quatro reprovam pelo P1.
    """
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.subsystems import coop as co
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
    from tests.unit.test_a_mira_por_movimento_na_tela import _P1, _estado, _hub

    todos = (_P1, _P2, _P3, _P4)
    hub = _hub({u: _GIRO for u in todos})
    daemon, servidor = _servidor_da_matriz(tmp_path, transporte, hub)
    for uniq in todos:
        corpo = _mira_set(servidor, uniq=uniq, ligada=True)
        assert corpo["status"] == "ok" and corpo["ligada"] is True, (uniq, corpo)

    fds: list[int] = []
    try:
        # O P1 — o tique do primário, `dispatch_gamepad`.
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
        monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
        vpad1, ler1 = _vpad_de_verdade(caminho, 1, fds)
        daemon._gamepad_device = vpad1
        gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
        hub.reconciliar()
        gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
        lidos = {_P1: ler1()}

        # Os P2 a P4 — o laço dos secundários, `CoopManager.forward_all`.
        gerente = co.CoopManager(daemon)
        leitores = {}
        for n, uniq in enumerate(todos[1:], start=2):
            vpad, leitores[uniq] = _vpad_de_verdade(caminho, n, fds)
            gerente._players[uniq] = co._SecondaryPlayer(
                identity=uniq,
                evdev_path=f"/dev/input/event{n}",
                reader=SimpleNamespace(
                    snapshot=lambda: SimpleNamespace(
                        lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
                        buttons_pressed=frozenset()),
                    grab_state="held",
                ),
                player_index=n,
                vpad=vpad,
            )
        gerente.forward_all()
        hub.reconciliar()
        gerente.forward_all()
        lidos.update({u: ler() for u, ler in leitores.items()})
    finally:
        import os

        for fd in fds:
            os.close(fd)
    parados = {u: v for u, v in lidos.items() if v in (None, 128)}
    assert not parados, (
        f"{caminho}/{transporte}: o chip acendeu a mira e o analógico direito "
        f"que o jogo recebe ficou parado em {parados}")


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_no_nativo_o_chip_nao_acende_ninguem(
    perfis: Path, tmp_path: Path, transporte: str
) -> None:
    """A exceção dela, nos quatro jogadores e nos dois transportes: no Nativo
    o chip de ninguém acende, e o giro nativo de ninguém sai da janela."""
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from tests.unit.test_a_mira_por_movimento_na_tela import _P1, _hub

    todos = (_P1, _P2, _P3, _P4)
    _daemon, servidor = _servidor_da_matriz(tmp_path, transporte, _hub({}))
    servidor.daemon._native_mode = True
    for uniq in todos:
        assert _mira_set(servidor, uniq=uniq, ligada=True)["status"] == "nativo"
    assert not rot.por_peca(servidor.store)
    assert not any(REGISTRO.roteado(u) for u in todos)
