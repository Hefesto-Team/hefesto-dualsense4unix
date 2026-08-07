"""O ícone SIMBÓLICO do painel — APPLET-MONOCROMÁTICO-01 (07/08/2026).

Pedido dela, olhando a própria barra: *"o applet do hefesto deve ficar em preto
e branco, talvez só o círculo com borda preta e a borda do martelo ao centro. no
cosmic todos os applet são assim"*.

Cada asserção daqui nasceu de uma MEDIÇÃO, não de gosto. As três que mais
importam, porque as três já quebraram o ícone de verdade:

1. **`currentColor` some.** Renderizado sem contexto de cor (rsvg-convert,
   resvg) ele resolve para PRETO: `srgb(0,0,0)`, 1,59:1 sobre o `#2F2F3A` do
   painel escuro dela. É o mecanismo reproduzido do "parecia sumir" de 27/06,
   que trocou o simbólico pelo PNG colorido e deixou o Hefesto como o único
   ícone cromático da barra;
2. **`stroke` + `fill="none"` vira DISCO CHAPADO.** O GTK recolore símbolo
   injetando CSS `rect,circle,path {fill: <cor> !important;}` — o `!important`
   atropela `fill="none"`. Reproduzido em 07/08: o mesmo aro feito com stroke
   saiu um disco liso, com o desenho todo sumido dentro. Contorno aqui é
   sempre `fill-rule="evenodd"` com dois subcaminhos;
3. **PNG nunca é recolorido.** Por isso o nome pedido pelo código TEM de
   terminar em `-symbolic` e o arquivo TEM de ser SVG.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[2]

SIMBOLICO = RAIZ / "assets" / "simbolico" / "hefesto-dualsense4unix-symbolic.svg"
SIMBOLICO_APPLET = (
    RAIZ
    / "packaging"
    / "cosmic-applet"
    / "data"
    / "icons"
    / "hicolor"
    / "symbolic"
    / "apps"
    / "com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg"
)
TRAY_PY = RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "tray.py"
APPLET_RS = RAIZ / "packaging" / "cosmic-applet" / "src" / "app.rs"
APPLET_DESKTOP = (
    RAIZ
    / "packaging"
    / "cosmic-applet"
    / "data"
    / "com.vitoriamaria.HefestoDualsense4Unix.desktop"
)
INSTALL_SH = RAIZ / "install.sh"
UNINSTALL_SH = RAIZ / "uninstall.sh"


def _corpo(svg: str) -> str:
    """O SVG sem os comentários — o cabeçalho fala de `currentColor` e de
    `stroke` para EXPLICAR por que eles não podem aparecer no desenho."""
    return re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)


@pytest.fixture(scope="module")
def svg() -> str:
    return SIMBOLICO.read_text(encoding="utf-8")


def test_o_simbolico_existe():
    assert SIMBOLICO.is_file(), (
        f"{SIMBOLICO} sumiu — sem ele a bandeja cai no ícone colorido e, se nem "
        "ele existir, num joystick genérico"
    )


def test_o_simbolico_e_xml_valido():
    """Aconteceu de verdade, em 07/08/2026, escrevendo este arquivo.

    O cabeçalho ganhou uma linha de traços de separação, e `--` dentro de
    comentário fecha o comentário em XML: o `rsvg-convert` passou a recusar o
    arquivo inteiro ("Comment must not contain double-hyphen"). O painel ainda
    desenhava (o renderizador dele é mais tolerante), então o defeito era
    INVISÍVEL na tela e só apareceria em quem usa librsvg — que é a pilha da
    bandeja GTK. Nenhum dos outros testes daqui pegava: todos leem o SVG como
    TEXTO.
    """
    import xml.etree.ElementTree as ET

    for arq in (SIMBOLICO, SIMBOLICO_APPLET):
        try:
            ET.parse(arq)
        except ET.ParseError as erro:  # pragma: no cover - só quando quebra
            pytest.fail(f"{arq.name} não é XML válido: {erro}")


def test_grade_simbolica_16x16(svg: str):
    assert 'viewBox="0 0 16 16"' in svg
    assert 'width="16"' in svg and 'height="16"' in svg


def test_sem_currentcolor(svg: str):
    assert "currentColor" not in _corpo(svg), (
        "`currentColor` sem contexto de cor resolve para PRETO (medido: "
        "srgb(0,0,0)) e some no painel escuro dela"
    )


def test_uma_cor_so_acromatica_e_clara(svg: str):
    cores = set(re.findall(r"#[0-9a-fA-F]{6}", _corpo(svg)))
    assert len(cores) == 1, f"ícone simbólico é monocromático; achei {sorted(cores)}"
    (cor,) = cores
    r, g, b = (int(cor[i : i + 2], 16) for i in (1, 3, 5))
    assert r == g == b, f"{cor} não é acromático — 'preto e branco' quer dizer R=G=B"
    assert r >= 0x90, (
        f"{cor} é escuro demais: fora de quem recolore, um glifo escuro fica "
        "abaixo de 2:1 no painel escuro dela e some"
    )


def test_contorno_e_preenchimento_nunca_stroke(svg: str):
    corpo = _corpo(svg)
    assert "stroke" not in corpo, (
        "contorno feito com `stroke` + `fill=\"none\"` vira DISCO CHAPADO quando "
        "o GTK recolore (CSS `fill: ... !important`) — reproduzido em 07/08"
    )
    assert 'fill="none"' not in corpo
    assert 'fill-rule="evenodd"' in corpo, (
        "o furo do aro e o vazado da cabeça do martelo são feitos com evenodd"
    )


def test_sem_fundo_opaco_e_sem_transform(svg: str):
    corpo = _corpo(svg)
    assert "transform" not in corpo, (
        "o librsvg ignora `transform-origin` e joga a forma para fora do viewBox"
    )
    assert "<rect" not in corpo, (
        "nada de retângulo de fundo: a recoloração preserva o alfa, e um fundo "
        "opaco viraria mancha da cor do tema"
    )


def test_bandeja_e_applet_servem_o_mesmo_desenho():
    assert SIMBOLICO_APPLET.is_file()
    assert SIMBOLICO.read_bytes() == SIMBOLICO_APPLET.read_bytes(), (
        "dois nomes, um desenho só — se divergirem, a mesma aplicação aparece "
        "com ícones diferentes conforme a superfície"
    )


# --------------------------------------------------------------------------
# Contrato de NOME — é o que impede a regressão de 27/06 de voltar em silêncio
# --------------------------------------------------------------------------


def test_tray_pede_nome_simbolico():
    from hefesto_dualsense4unix.app.tray import (
        TRAY_ICON_FALLBACK,
        TRAY_ICON_NAME,
        TRAY_ICON_NAME_LEGADO,
    )

    assert TRAY_ICON_NAME.endswith("-symbolic")
    assert SIMBOLICO.stem == TRAY_ICON_NAME
    assert TRAY_ICON_NAME_LEGADO == "hefesto-dualsense4unix"
    assert TRAY_ICON_FALLBACK == "input-gaming"


def test_applet_rust_pede_nome_simbolico():
    fonte = APPLET_RS.read_text(encoding="utf-8")
    achado = re.search(r'const ICON_APP: &str = "([^"]+)"', fonte)
    assert achado is not None, "ICON_APP sumiu de app.rs"
    assert achado.group(1).endswith("-symbolic")
    assert achado.group(1) == SIMBOLICO_APPLET.stem


def test_desktop_do_applet_pede_nome_simbolico():
    linha = [
        ln
        for ln in APPLET_DESKTOP.read_text(encoding="utf-8").splitlines()
        if ln.startswith("Icon=")
    ]
    assert linha, "o .desktop do applet perdeu a linha Icon="
    assert linha[0].removeprefix("Icon=").endswith("-symbolic")


def test_instaladores_levam_e_removem_o_simbolico():
    """Não basta o `install.sh` CITAR o arquivo — tem de COPIÁ-LO.

    A primeira versão deste teste só procurava o caminho do arquivo no texto do
    script, e passava com a linha de cópia arrancada: o caminho continuava lá,
    na variável e na mensagem de aviso. Um teste que passa com a cura arrancada
    não testa nada. Agora a asserção é sobre a linha que copia.
    """
    instala = INSTALL_SH.read_text(encoding="utf-8")
    assert "assets/simbolico/hefesto-dualsense4unix-symbolic.svg" in instala
    copias = [
        ln.strip()
        for ln in instala.splitlines()
        if ln.strip().startswith(("cp ", "cp -f", "install -D"))
        and "${ICON_SIMBOLICO_DIR}/${APP_ID}-symbolic.svg" in ln
    ]
    assert copias, (
        "install.sh não copia o simbólico para symbolic/apps — a bandeja dela "
        "cai no ícone colorido e ninguém vê o pedido de 07/08 atendido"
    )

    desinstala = UNINSTALL_SH.read_text(encoding="utf-8")
    assert 'symbolic/apps/${APP_ID}-symbolic.svg' in desinstala, (
        "sem esta linha, desinstalar deixa lixo de ícone — e lixo de ícone "
        "reaparece na próxima instalação como 'não mudou nada'"
    )


def test_a_linha_que_apaga_svg_no_install_nao_alcanca_o_simbolico():
    """`install.sh` apaga `scalable/apps/${APP_ID}.svg` (placeholder da v3.4.2).

    Se alguém generalizar esse alvo para `${APP_ID}*.svg`, o simbólico é
    apagado a cada instalação e o sintoma é um joystick genérico na barra dela.
    """
    instala = INSTALL_SH.read_text(encoding="utf-8")
    apagam = [
        ln.strip()
        for ln in instala.splitlines()
        if ln.strip().startswith("rm -f") and ".svg" in ln and "ICON_HICOLOR_BASE" in ln
    ]
    assert apagam, "a linha que apaga SVG mudou de forma — reveja este teste"
    for ln in apagam:
        assert "*" not in ln, f"alvo com curinga apagaria o simbólico: {ln}"
        assert "symbolic" not in ln, f"esta linha alcança o simbólico: {ln}"


# --------------------------------------------------------------------------
# A queda em três degraus — o que a barra dela mostra quando falta arquivo
# --------------------------------------------------------------------------


def _tray_com_tema(monkeypatch: pytest.MonkeyPatch, instalados: set[str]):
    """Aparelha `app.tray.Gtk` com um tema de ícones de mentira."""
    import hefesto_dualsense4unix.app.tray as apptray_mod

    tema = SimpleNamespace(has_icon=lambda nome: nome in instalados)
    monkeypatch.setattr(
        apptray_mod,
        "Gtk",
        SimpleNamespace(IconTheme=SimpleNamespace(get_default=lambda: tema)),
    )
    return apptray_mod


def test_preferred_icon_pede_o_simbolico_quando_ele_existe(
    monkeypatch: pytest.MonkeyPatch,
):
    mod = _tray_com_tema(
        monkeypatch, {"hefesto-dualsense4unix-symbolic", "hefesto-dualsense4unix"}
    )
    assert mod.AppTray._preferred_icon() == "hefesto-dualsense4unix-symbolic"


def test_preferred_icon_cai_no_colorido_em_instalacao_antiga(
    monkeypatch: pytest.MonkeyPatch,
):
    """Instalação anterior a 07/08 não tem o simbólico no disco.

    Cair direto no joystick genérico seria trocar um ícone certo por um errado
    — e o relato dela seria "sumiu o Hefesto da barra", sem pista da causa.
    """
    mod = _tray_com_tema(monkeypatch, {"hefesto-dualsense4unix"})
    assert mod.AppTray._preferred_icon() == "hefesto-dualsense4unix"


def test_preferred_icon_cai_no_generico_sem_nada_instalado(
    monkeypatch: pytest.MonkeyPatch,
):
    mod = _tray_com_tema(monkeypatch, set())
    assert mod.AppTray._preferred_icon() == "input-gaming"


def test_preferred_icon_sem_tema_nenhum(monkeypatch: pytest.MonkeyPatch):
    import hefesto_dualsense4unix.app.tray as apptray_mod

    monkeypatch.setattr(
        apptray_mod,
        "Gtk",
        SimpleNamespace(IconTheme=SimpleNamespace(get_default=lambda: None)),
    )
    assert apptray_mod.AppTray._preferred_icon() == "input-gaming"
