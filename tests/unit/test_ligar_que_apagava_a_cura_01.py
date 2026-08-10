"""LIGAR-QUE-APAGAVA-A-CURA-01 — o botão "Ligar" desarmava a cura de 08/08.

MEDIDO no código, em 10/08/2026, seguindo a cadeia inteira de ponta a ponta:

    gui/main.glade:3121            <signal handler="on_emulation_mic_on"/>
    emulation_actions.py:930-945   -> _run_mic("--enable-mic", ...)
    fix_wireplumber_default_source.sh (enable_mic_dualsense)
                                   -> rm -f nos TRÊS drop-ins, o 51 junto

O 51 **era** supressão: até MONITOR-QUE-VENCE-01 (commit 6c428cd, 08/08) ele
rebaixava a entrada do controle para ``priority.session = 50``, e removê-lo ao
ligar o mic era coerente com o nome da operação. Naquele commit ele virou o
CONTRÁRIO — a entrada passou a **1500**, a faixa medida que fica acima de
qualquer monitor (1109) e abaixo de qualquer captura real (2009). O 51 é o
PROMOTOR desde então.

O ``rm -f`` que ficou no ``--enable-mic`` desarmava, portanto, a cura de 08/08
no gesto de LIGAR o microfone: sem o arquivo, a entrada volta ao 50 de fábrica,
o monitor da saída vence o microfone por vinte e duas vezes, e o que qualquer
aplicativo grava é o eco do que sai. É o defeito que a sprint
``2026-08-08-MONITOR-QUE-VENCE-01`` mediu e provou ao vivo, reintroduzido pelo
único botão que existe para o caso contrário.

E a tela afirmava o oposto do que tinha acontecido: ``_mic_is_on()`` perguntava
só pelo 52/53, então logo depois de apagar o promotor o rótulo escrevia
**"Ligado"** em verde.

O QUE ESTE ARQUIVO TRAVA
========================
1. ``--enable-mic`` não apaga o promotor, e o GARANTE quando ele falta;
2. ``--enable-mic`` continua removendo a supressão de verdade (52/53) — sem este
   contrapeso, "curar" viraria não fazer nada;
3. a promoção EXPLÍCITA (``--promote-source``) continua removendo o 51, porque
   ``doctor.sh:_prefere_mic_do_dualsense`` lê a ausência dele como a escolha a
   dedo da usuária;
4. a tela só chama de "Ligado" o que está ligado de verdade.

Nada aqui toca o áudio da máquina: as funções de shell exercitadas são as que
só mexem em ARQUIVO, num ``HOME`` de mentira, e ainda assim com um ``systemctl``
dublê na frente do PATH — cinto e suspensório, porque o preço de um engano seria
o WirePlumber da sessão dela.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# Reusa o andaime de stubs de `gi` do portão irmão (o import dele instala os
# stubs quando não há PyGObject real) em vez de duplicar quarenta linhas.
from tests.unit.test_emulation_mic_quirk import Mixin

RAIZ = Path(__file__).resolve().parents[2]
WP_FIX = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"

PROMOTOR = "51-hefesto-dualsense-no-default-source.conf"
DISABLE_SRC = "52-hefesto-dualsense-disable-source.conf"
DISABLE_OUT = "53-hefesto-dualsense-disable-output.conf"

ASSET_PROMOTOR = RAIZ / "assets" / "wireplumber" / PROMOTOR


# ---------------------------------------------------------------------------
# Andaime do lado shell — HOME de mentira e `systemctl` que não faz nada
# ---------------------------------------------------------------------------


def _ambiente(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Devolve ``(dir_dos_dropins, env)`` para rodar o wp-fix com segurança.

    O script monta ``DROPIN_DIR`` a partir do ``HOME`` já no carregamento (e as
    variáveis são ``readonly``), então o ``HOME`` precisa ser falso ANTES do
    ``source``. Os dublês de ``systemctl``/``wpctl``/``pactl`` existem para o
    caso de alguém, um dia, acrescentar uma chamada dessas na função sob teste:
    o portão avisaria por outro caminho, mas a sessão dela não pagaria a conta.
    """
    casa = tmp_path / "casa"
    dropins = casa / ".config" / "wireplumber" / "wireplumber.conf.d"
    dropins.mkdir(parents=True)
    binario = tmp_path / "bin"
    binario.mkdir()
    for nome in ("systemctl", "wpctl", "pactl"):
        alvo = binario / nome
        alvo.write_text(
            f'#!/bin/bash\nprintf "DUBLE {nome} %s\\n" "$*" >&2\nexit 0\n',
            encoding="utf-8",
        )
        alvo.chmod(0o755)
    env = {
        "PATH": f"{binario}:/usr/bin:/bin",
        "HOME": str(casa),
        "WP_FIX": str(WP_FIX),
    }
    return dropins, env


def _rodar(func: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Executa uma função REAL do wp-fix por ``source``, sem despachar o main."""
    return subprocess.run(
        ["bash", "-c", f'set --; source "$WP_FIX"; {func}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**env},
    )


def _planta(dropins: Path, *nomes: str) -> None:
    for nome in nomes:
        if nome == PROMOTOR:
            dropins.joinpath(nome).write_text(
                ASSET_PROMOTOR.read_text(encoding="utf-8"), encoding="utf-8"
            )
        else:
            dropins.joinpath(nome).write_text("# dublê\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. O promotor sobrevive ao botão "Ligar"
# ---------------------------------------------------------------------------


def test_ligar_o_mic_nao_apaga_o_promotor(tmp_path: Path) -> None:
    """O defeito, em uma asserção.

    ARRANQUE A CURA: devolva ``"${DROPIN_DST}"`` ao ``for`` de
    ``_arma_dropins_do_mic`` (era o primeiro da lista) e este teste REPROVA — é
    o estado exato que a máquina dela ficava depois de um clique em "Ligar":
    entrada de volta ao 50, monitor a 1109 vencendo.
    """
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, PROMOTOR, DISABLE_SRC, DISABLE_OUT)

    res = _rodar("_arma_dropins_do_mic", env)

    assert res.returncode == 0, res.stderr
    assert (dropins / PROMOTOR).is_file(), (
        "o `--enable-mic` apagou o drop-in 51 — que desde MONITOR-QUE-VENCE-01 "
        "é o PROMOTOR (priority.session = 1500), não uma supressão. Sem ele o "
        "monitor da saída (1109) vence o microfone (50) e o que se grava é o "
        f"eco do que sai.\n{res.stdout}"
    )
    # E o conteúdo continua sendo o do repositório: apagar-e-reescrever-errado
    # seria o mesmo defeito com outra roupa.
    assert "priority.session = 1500" in (dropins / PROMOTOR).read_text(encoding="utf-8")


def test_ligar_o_mic_instala_o_promotor_quando_ele_falta(tmp_path: Path) -> None:
    """Ligar o mic é ARMAR a cura, não só deixar de desarmá-la.

    É o estado de quem desligou o mic (``--disable-source`` instala 52/53 e não
    toca no 51) numa máquina onde o 51 já não estava — exatamente o que a versão
    anterior deste script deixava para trás.

    ARRANQUE A CURA: troque o ramo ``elif install_dropin`` por um ``:`` e este
    teste REPROVA, porque o mic volta livre, porém no 50 de fábrica.
    """
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, DISABLE_SRC, DISABLE_OUT)

    res = _rodar("_arma_dropins_do_mic", env)

    assert res.returncode == 0, res.stderr
    assert (dropins / PROMOTOR).is_file(), (
        f"o promotor não foi instalado; o mic ficaria livre e sem prioridade.\n{res.stdout}"
    )
    assert "priority.session = 1500" in (dropins / PROMOTOR).read_text(encoding="utf-8")


def test_ligar_o_mic_e_idempotente(tmp_path: Path) -> None:
    """Dois cliques seguidos em "Ligar" terminam no mesmo lugar.

    Contrapeso da cura acima: garantir o promotor não pode virar reinstalar em
    cima do que já está certo com erro no segundo passe.
    """
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, DISABLE_SRC, DISABLE_OUT)

    primeiro = _rodar("_arma_dropins_do_mic", env)
    segundo = _rodar("_arma_dropins_do_mic", env)

    assert primeiro.returncode == 0, primeiro.stderr
    assert segundo.returncode == 0, segundo.stderr
    assert (dropins / PROMOTOR).is_file()
    assert "promotor mantido" in segundo.stdout, segundo.stdout


# ---------------------------------------------------------------------------
# 2. O contrapeso: a supressão de verdade continua saindo
# ---------------------------------------------------------------------------


def test_ligar_o_mic_continua_removendo_a_supressao_de_verdade(tmp_path: Path) -> None:
    """Sem isto, "curar" viraria não fazer nada.

    O 52 e o 53 são ``node.disabled = true``: são eles que impedem o nó de
    existir. Se a cura os poupasse junto com o 51, o botão "Ligar" deixaria de
    ligar o microfone.

    ARRANQUE A CURA: tire ``"${DROPIN_DISABLE_DST}"``/``"${DROPIN_OUTPUT_DST}"``
    do ``for`` e este teste REPROVA.
    """
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, PROMOTOR, DISABLE_SRC, DISABLE_OUT)

    res = _rodar("_arma_dropins_do_mic", env)

    assert res.returncode == 0, res.stderr
    assert not (dropins / DISABLE_SRC).exists(), (
        f"o 52 (node.disabled do mic) ficou — o mic continua sumido.\n{res.stdout}"
    )
    assert not (dropins / DISABLE_OUT).exists(), (
        f"o 53 (node.disabled da saída) ficou — o fone do controle segue mudo.\n{res.stdout}"
    )


# ---------------------------------------------------------------------------
# 3. A promoção explícita não pode mudar de significado
# ---------------------------------------------------------------------------


def test_a_promocao_explicita_continua_removendo_o_51(tmp_path: Path) -> None:
    """A ausência do 51 é um SINAL que outro programa lê.

    ``doctor.sh:_prefere_mic_do_dualsense`` (linha 821) usa a presença do 51
    como "a política default é rebaixar" e a ausência como "a usuária promoveu o
    controle a dedo". Fazer a promoção manter o arquivo apagaria a escolha dela
    no próximo ``doctor --fix``.

    ARRANQUE A CURA: faça o ramo ``sem-promotor`` cair no ramo padrão e este
    teste REPROVA.
    """
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, PROMOTOR, DISABLE_SRC)

    res = _rodar('_arma_dropins_do_mic "sem-promotor"', env)

    assert res.returncode == 0, res.stderr
    assert not (dropins / PROMOTOR).exists(), (
        f"a promoção explícita deixou o 51 no lugar.\n{res.stdout}"
    )
    assert not (dropins / DISABLE_SRC).exists(), res.stdout


def test_a_promocao_pede_sem_promotor_ao_enable_mic() -> None:
    """A fiação: quem promove tem de pedir o modo, senão herda o novo padrão.

    Contrato de texto porque ``promote_source_dualsense`` fala com ``wpctl`` e
    com o ``doctor.sh`` — rodá-la de verdade é mexer no áudio da máquina.

    ARRANQUE A CURA: tire o argumento da chamada e este teste REPROVA.
    """
    texto = WP_FIX.read_text(encoding="utf-8")
    inicio = texto.index("promote_source_dualsense() {")
    corpo = texto[inicio : texto.index("\n}\n", inicio)]
    assert 'enable_mic_dualsense "sem-promotor"' in corpo, (
        "a promoção explícita voltou a herdar o padrão do `--enable-mic`, que "
        "MANTÉM o 51 — e a ausência do 51 é o sinal que o doctor lê como "
        "promoção a dedo da usuária."
    )


def test_o_enable_mic_do_despacho_nao_pede_sem_promotor() -> None:
    """O caminho do botão "Ligar" usa o padrão, e o padrão guarda o promotor.

    ARRANQUE A CURA: escreva ``enable_mic_dualsense "sem-promotor"`` no ramo
    ``enable-mic)`` do ``case`` e este teste REPROVA — seria o defeito de volta
    pela porta do despacho.
    """
    texto = WP_FIX.read_text(encoding="utf-8")
    inicio = texto.index("    enable-mic)")
    bloco = texto[inicio : texto.index("    unmute-routes)", inicio)]
    assert "enable_mic_dualsense" in bloco
    assert "sem-promotor" not in bloco, (
        "o `--enable-mic` (o que o botão “Ligar” da aba Emulação roda) voltou a "
        "apagar o promotor"
    )


# ---------------------------------------------------------------------------
# 4. A tela para de afirmar o contrário do que aconteceu
# ---------------------------------------------------------------------------


class _RotuloFalso:
    """Um GtkLabel de mentira que só guarda o que lhe mandam escrever."""

    def __init__(self) -> None:
        self.markup = ""
        self.tooltip = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto

    def set_tooltip_text(self, texto: str) -> None:
        self.tooltip = texto


def _tela(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[object, _RotuloFalso]:
    dropins = tmp_path / "wireplumber.conf.d"
    dropins.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Mixin, "_wp_dropin_dir", staticmethod(lambda: dropins))
    obj = Mixin()
    rotulo = _RotuloFalso()
    monkeypatch.setattr(obj, "_get", lambda _id: rotulo, raising=False)
    return obj, rotulo


def test_a_tela_nao_diz_ligado_sem_o_promotor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O rótulo verde era a segunda metade do defeito.

    Sem o 51, a captura padrão pode cair no monitor da saída — e a aba escrevia
    "Ligado" em verde, no mesmo segundo em que o botão tinha desarmado a cura.

    ARRANQUE A CURA: devolva o ``_mic_is_on`` que só olhava o 52/53 e este teste
    REPROVA nas duas asserções.
    """
    obj, rotulo = _tela(tmp_path, monkeypatch)  # diretório vazio: nem 52/53 nem 51

    assert obj._mic_is_on() is False, (
        "a janela considerou o mic ligado sem o promotor no lugar — é a leitura "
        "que fazia a tela afirmar o contrário do que o botão tinha feito"
    )
    obj._refresh_mic_status()
    assert "#50fa7b" not in rotulo.markup, f"verde de tudo certo: {rotulo.markup}"
    assert "sem prioridade" in rotulo.markup, rotulo.markup
    # E não pode mentir para o outro lado: nada foi suprimido aqui.
    assert "suprimido" not in rotulo.markup, rotulo.markup


def test_a_dica_explica_a_consequencia_e_o_caminho(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um rótulo de 21 caracteres não cabe a explicação; a dica cabe.

    ARRANQUE A CURA: apague o ``set_tooltip_text`` e este teste REPROVA. Sem
    ela, "Ligado sem prioridade" é diagnóstico sem tradução — a tela deixaria de
    mentir e passaria a ser críptica, que é o defeito seguinte.
    """
    obj, rotulo = _tela(tmp_path, monkeypatch)
    obj._refresh_mic_status()
    assert "grav" in rotulo.tooltip, rotulo.tooltip  # o que acontece de errado
    assert "Ligar" in rotulo.tooltip, rotulo.tooltip  # e o que fazer a respeito


def test_ligado_de_verdade_continua_verde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O contrapeso: sem ele, "curar" viraria dizer Desligado para sempre."""
    obj, rotulo = _tela(tmp_path, monkeypatch)
    obj._wp_dropin_dir().joinpath(PROMOTOR).write_text("x", encoding="utf-8")

    assert obj._mic_is_on() is True
    obj._refresh_mic_status()
    assert rotulo.markup == '<span foreground="#50fa7b">Ligado</span>', rotulo.markup


@pytest.mark.parametrize("suprimido", [DISABLE_SRC, DISABLE_OUT])
def test_suprimido_continua_dizendo_suprimido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suprimido: str
) -> None:
    """O estado que já existia não podia mudar de nome no meio da cura.

    Vale com o promotor no lugar: o 52/53 vence, porque ``node.disabled`` tira o
    nó do mapa e prioridade nenhuma ressuscita o que não existe.
    """
    obj, rotulo = _tela(tmp_path, monkeypatch)
    obj._wp_dropin_dir().joinpath(PROMOTOR).write_text("x", encoding="utf-8")
    obj._wp_dropin_dir().joinpath(suprimido).write_text("x", encoding="utf-8")

    assert obj._mic_is_on() is False
    obj._refresh_mic_status()
    assert "Desligado (suprimido)" in rotulo.markup, rotulo.markup
