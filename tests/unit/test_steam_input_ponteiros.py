"""STEAM-INPUT-01, entregas 1 e 9 — a frase falsa e os dois ponteiros errados."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_steam_input_ponteiros: importa código da janela GTK")

import ast
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    format_game_broken_result,
)
from hefesto_dualsense4unix.integrations import storm_doctor as sd

_RAIZ = Path(__file__).resolve().parents[2]
_PACOTE = _RAIZ / "src" / "hefesto_dualsense4unix"
_DAEMON_ACTIONS = _PACOTE / "app" / "actions" / "daemon_actions.py"
_GUIA_MASCARAS = _RAIZ / "docs" / "usage" / "jogos-e-mascaras.md"

_ROTULO_CITADO = re.compile(r"'([^']{3,40})'")
_ABA_CITADA = re.compile(r"aba \*{0,2}([A-ZÁÉÍÓÚÃÕÂÊÔÇ][a-záéíóúãõâêôç]+)")


_BOTAO = re.compile(r"<button\b[^>]*>(.*?)</button>", re.S)
_DEGRAU = re.compile(
    r'<span class="degrau"[^>]*\bdata-gesto="[^"]+"[^>]*>(.*?)</span>', re.S)
_ABA_NA_BARRA = re.compile(
    r'<a[^>]*class="aba(?:\s[^"]*)?"[^>]*href="([^"]+)"[^>]*>([^<]+)')
_TAGS = re.compile(r"<[^>]+>")


def _publicadas() -> list[Path]:
    """As dez páginas que o produto renderiza, na ordem do nome."""
    pasta = _PACOTE / "interface" / "paginas"  # noqa-acento (nome de pasta)
    return sorted(pasta.glob("[0-9][0-9]-*.html"))


def _nome_das_abas() -> dict[str, str]:
    """{arquivo: nome da aba}, lido da BARRA que as dez compartilham."""
    for arq in _publicadas():
        achados = _ABA_NA_BARRA.findall(arq.read_text(encoding="utf-8"))
        if achados:
            return {href: nome.strip() for href, nome in achados}
    raise AssertionError("nenhuma página publicada tem a barra das abas")


def _paginas() -> list[tuple[str, str]]:
    """[(nome da aba, HTML da página)] das dez publicadas."""
    nomes = _nome_das_abas()
    saida = []
    for arq in _publicadas():
        nome = nomes.get(arq.name)
        if nome:
            saida.append((nome, arq.read_text(encoding="utf-8")))
    assert saida, "as páginas publicadas sumiram da árvore"
    return saida


def _rotulo_do_botao(bruto: str) -> str | None:
    """O texto que a pessoa LÊ no botão, sem a marcação de dentro."""
    texto = _TAGS.sub("", bruto).strip()
    return texto or None


def _aba_do_botao(rotulo: str) -> str | None:
    """Nome da aba onde mora o botão de rótulo ``rotulo``, ou None."""
    for aba, html in _paginas():
        for bruto in (*_BOTAO.findall(html), *_DEGRAU.findall(html)):
            if _rotulo_do_botao(bruto) == rotulo:
                return aba
    return _rotulos_do_cartao().get(rotulo)


_ROTULOS_QUE_NASCEM_NO_CARTAO = (
    "EXCLUIR_ROTULO",
)


def _rotulos_do_cartao() -> dict[str, str]:
    """{rótulo: nome da aba} dos botões que o cartão da Steam monta na hora."""
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    aba = _nome_das_abas().get("07-lancadores.html", "Lançadores")
    return {getattr(dl, n): aba for n in _ROTULOS_QUE_NASCEM_NO_CARTAO}


def _rotulos_de_botao() -> set[str]:
    """O universo dos alvos válidos: a tela que o LANÇADOR abre, e só ela."""
    achados = {
        _rotulo_do_botao(bruto)
        for _aba, html in _paginas()
        for bruto in (*_BOTAO.findall(html), *_DEGRAU.findall(html))
    }
    return {r for r in achados if r} | set(_rotulos_do_cartao())


def _corpo_de_funcao(caminho: Path, nome: str) -> str:
    """Texto-fonte de uma função/método, por AST (sem importar GTK)."""
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return ast.get_source_segment(fonte, no) or ""
    raise AssertionError(f"{nome}() não existe em {caminho.name}")


_GESTO_NA_STEAM = re.compile(r"Propriedades\s*(?:→|->)\s*Control")


def _fontes_de_texto_de_interface() -> list[Path]:
    """Todo arquivo que PINTA texto de interface: o pacote e as dez páginas."""
    arquivos = sorted(_PACOTE.rglob("*.py"))
    arquivos.extend(_publicadas())
    return arquivos


def test_nenhum_texto_da_janela_ensina_o_gesto_na_steam() -> None:
    """Entrega 1: a instrução de ir na Steam mexer no controle do jogo SAIU."""
    culpados = [
        f"{caminho.relative_to(_RAIZ)}:{n}"
        for caminho in _fontes_de_texto_de_interface()
        for n, linha in enumerate(
            caminho.read_text(encoding="utf-8").splitlines(), start=1
        )
        if _GESTO_NA_STEAM.search(linha)
    ]
    assert not culpados, (
        "texto de interface voltou a ensinar o gesto na Steam "
        f"(Propriedades -> Controle): {culpados}"
    )


@pytest.mark.parametrize("status", ["adicionado", "ja_estava"])
def test_toast_do_jogo_marcado_nao_manda_ninguem_a_steam(status: str) -> None:
    msg = format_game_broken_result(status=status, appid=2111190)
    assert "Propriedades" not in msg
    assert "Ativar" not in msg


@pytest.mark.parametrize("status", ["adicionado", "ja_estava"])
def test_toast_do_jogo_marcado_nao_deixa_vazio(status: str) -> None:
    """Tirar a frase falsa não pode virar silêncio."""
    msg = format_game_broken_result(status=status, appid=2111190)
    assert "Feche e abra o jogo" in msg
    citados = re.findall(r"\bdocs/[\w./-]+\.md\b", msg)
    assert citados, f"o toast não aponta destino nenhum: {msg!r}"
    for rel in citados:
        assert (_RAIZ / rel).is_file(), f"o toast cita {rel}, que não existe"


def _warn_steam_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A mensagem de WARN do ``check_steam_input``, com fixtures no disco."""
    vdf = tmp_path / ".steam/steam/userdata/123/config/localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text('\t\t\t\t"SteamController_PSSupport"\t\t"2"\n', encoding="utf-8")
    monkeypatch.setattr(sd, "_allowlist_path", lambda: tmp_path / "allowlist-vazia.txt")
    tag, msg = sd.check_steam_input(tmp_path)
    assert tag == sd.WARN
    return msg


def _warn_snd_quirk(tmp_path: Path) -> str:
    tag, msg = sd.check_snd_quirk(
        quirk_flags_text="", conf_path=tmp_path / "ausente.conf"
    )
    assert tag == sd.WARN
    return msg


def test_botao_citado_pelo_diagnostico_existe_na_janela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Todo rótulo entre aspas nas mensagens do doctor é botão de verdade."""
    rotulos = _rotulos_de_botao()
    for msg in (
        _warn_steam_input(tmp_path, monkeypatch),
        _warn_snd_quirk(tmp_path),
    ):
        for citado in _ROTULO_CITADO.findall(msg):
            assert citado in rotulos, (
                f"a mensagem {msg!r} manda procurar o botão {citado!r}, "
                "que não existe na janela"
            )


def test_aba_citada_e_a_aba_onde_o_botao_mora(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rótulo certo na aba errada continua sendo ponteiro errado."""
    msg = _warn_steam_input(tmp_path, monkeypatch)
    citados = _ROTULO_CITADO.findall(msg)
    assert citados, f"a mensagem parou de nomear o botão: {msg!r}"
    abas = _ABA_CITADA.findall(msg)
    assert abas, f"a mensagem parou de nomear a aba: {msg!r}"
    assert _aba_do_botao(citados[0]) == abas[0]


_MODO_NO_EDITOR = re.compile(r'data-hef="editor\.modo"[^>]*>([^<]+)')


def _nomes_de_modo() -> set[str]:
    """Rótulos dos segmentos de `editor.modo` — nomes de ESTADO, não de destino."""
    nomes: set[str] = set()
    for _aba, html in _paginas():
        nomes.update(m.strip() for m in _MODO_NO_EDITOR.findall(html))
    return nomes


def test_a_isencao_de_nome_de_modo_nao_passa_do_editor_de_modo() -> None:
    """A isenção alcança só o que a razão dela sustenta: a aba Perfis."""
    isentos = _nomes_de_modo()
    assert not isentos, (
        "`editor.modo` voltou a uma página publicada. A isenção de nome de modo "
        "foi escrita para o editor da aba Perfis, e o quadro saiu de lá por "
        f"ordem dela em 11/09/2026: {isentos!r}. Se o endereço ressuscitou "
        "noutra aba, a razão da isenção precisa ser reescrita para ELA — a "
        "razão é semântica (nome de ESTADO, não de destino) e não viaja sozinha."
    )

    rotulos = _rotulos_de_botao()
    forasteiros = {
        nome: _aba_do_botao(nome)
        for nome in isentos
        if nome in rotulos and _aba_do_botao(nome) != "Perfis"
    }
    assert not forasteiros, (
        "a isenção de nome de modo alcançou botão que não é do editor de modo: "
        f"{forasteiros!r}. A razão dela é que os segmentos de `editor.modo` "
        "nomeiam um ESTADO do perfil e a prosa os cita como estado; um botão "
        "de outra aba citado no guia continua devendo o endereço dele."
    )


def test_guia_das_mascaras_aponta_o_botao_e_a_aba_que_existem() -> None:
    """``docs/usage/jogos-e-mascaras.md`` mandava usar um opt-in inexistente."""
    texto = _GUIA_MASCARAS.read_text(encoding="utf-8")
    paragrafos = texto.split("\n\n")

    com_ponteiro: list[str] = []
    for trecho in paragrafos:
        citados = re.findall(r'"([^"]{3,40})"', trecho)
        botao = next((c for c in citados if c in _rotulos_de_botao()), None)
        if botao is None:
            continue
        com_ponteiro.append(trecho)
        abas = _ABA_CITADA.findall(trecho)
        if botao in _nomes_de_modo() and not abas:
            continue
        assert abas, f"o guia cita {botao!r} e não diz em que aba ele mora: {trecho!r}"
        assert _aba_do_botao(botao) == abas[0], (
            f"o guia manda procurar {botao!r} na aba {abas[0]!r}, que não é "
            f"onde ele mora ({_aba_do_botao(botao)!r}): {trecho!r}"
        )

    assert any("exceção por jogo" in t or "marcar" in t for t in com_ponteiro), (
        "nenhum parágrafo do guia liga a exceção por jogo a um botão que "
        f"exista na janela — os que citam botão são {com_ponteiro!r}"
    )


