"""Regressão das versões rançosas e da semeadura de presets no Flatpak.

VERSOES-RANCOSAS-01 (30/07). Três artefatos anunciavam versão errada ao mesmo
tempo, e nenhum era visto por portão nenhum:

  - `assets/appimage/entrypoint.sh` imprimia "v3.0.0" e mandava instalar
    `hefesto-dualsense4unix_3.0.0_amd64.deb`, nome que o build_deb.sh não gera
    mais (hoje é `_<versão>_amd64_py<tag>.deb`). Esse banner é o PRIMEIRO texto
    que alguém novo lê.
  - `flatpak/br.andrefarias.Hefesto.metainfo.xml` tinha como release mais
    recente a 3.13.3 de 14/07 e nenhuma 0.x — a loja anunciava duas semanas de
    atraso.
  - `packaging/cosmic-applet/Cargo.toml` estava em 0.1.0 (e com e-mail pessoal
    real no campo `authors`, que nem o check_anonymity.sh nem o
    check_test_data.sh alcançam).

FIX-FLATPAK-PRESET-SEED-01 (30/07). O manifesto Flatpak não instalava
`assets/profiles_default` em nenhum dos três lugares onde o
`profiles/loader.py` procura os presets, então quem instalava pelo Flatpak
abria a janela sem perfil nenhum. O `scripts/build_appimage_gui.sh` faz essa
cópia desde 25/07 (FIX-APPIMAGE-PRESET-SEED-01) e a cura nunca foi portada.

Estratégia dos testes de portão: o mesmo molde de
tests/unit/test_check_anonymity.py e test_check_packaging_parity.py — pytest +
subprocess num repo FAKE em tmp_path, para provar que o portão reprova de
verdade sem depender do estado do repo real. Além disso, cada alvo novo é
conferido contra o arquivo REAL: arrancar a cura (voltar o Cargo.toml para
0.1.0, requotar o heredoc do banner, tirar a linha do profiles_default do
manifesto) derruba estes testes.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]

GATE_REL = "scripts/check_version_consistency.py"
ENTRYPOINT_REL = "assets/appimage/entrypoint.sh"
METAINFO_REL = "flatpak/br.andrefarias.Hefesto.metainfo.xml"
CARGO_REL = "packaging/cosmic-applet/Cargo.toml"
CARGO_LOCK_REL = "packaging/cosmic-applet/Cargo.lock"
MANIFESTO_REL = "flatpak/br.andrefarias.Hefesto.yml"
BUILD_GUI_REL = "scripts/build_appimage_gui.sh"

#: Alvos que este sprint acrescentou ao portão, com um conteúdo mínimo válido
#: (`{v}` = versão) para montar o repo fake. Fica junto do teste de propósito:
#: se alguém trocar a sintaxe no arquivo real, o teste contra o arquivo real
#: falha e este molde continua documentando o que o portão espera.
_ALVOS_NOVOS: tuple[tuple[str, str], ...] = (
    (ENTRYPOINT_REL, 'HEFESTO_VERSION_FALLBACK="{v}"\n'),
    (METAINFO_REL, '<releases>\n  <release version="{v}" date="2026-07-28"/>\n</releases>\n'),
    (CARGO_REL, '[package]\nname = "x"\nversion = "{v}"\n\n'
                '[dependencies]\ntokio = {{ version = "1" }}\n'),
    # O lock tem centenas de `version =`, uma por dependência: o molde põe uma
    # ANTES da nossa, para que um regex sem a âncora do `name` case a errada.
    (CARGO_LOCK_REL,
     '[[package]]\nname = "libcosmic"\nversion = "0.1.0"\n\n'
     '[[package]]\nname = "hefesto-dualsense4unix-applet"\nversion = "{v}"\n'),
)


def _versao_canonica() -> str:
    """Lê pyproject.toml — a mesma fonte de verdade que o portão usa."""
    try:
        import tomllib
    except ImportError:  # pragma: no cover — 3.10
        import tomli as tomllib
    dados = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return str(dados["project"]["version"])


def _portao():
    """Importa o portão real sem executá-lo."""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import check_version_consistency as gate
    finally:
        sys.path.pop(0)
    return gate


def _targets_do_portao() -> list[tuple[str, str, str]]:
    """Lê `_TARGETS` do portão real sem executá-lo."""
    return list(_portao()._TARGETS)


def _esperado_no_alvo(relpath: str) -> str:
    """A versão que o portão exige NAQUELE alvo.

    Não é sempre a canônica literal: o Cargo não aceita quatro componentes, e o
    portão traduz (`versao_para_cargo`). Perguntar ao portão em vez de repetir a
    regra aqui é o que impede este teste de virar uma segunda fonte de verdade —
    se a tradução mudar, o teste acompanha em vez de brigar.
    """
    gate = _portao()
    canonica = _versao_canonica()
    return gate._TRADUTORES.get(relpath, lambda v: v)(canonica)


# --------------------------------------------------------------------------
# 1) Os três alvos entraram no portão — e casam no arquivo REAL.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relpath", [ENTRYPOINT_REL, METAINFO_REL, CARGO_REL, CARGO_LOCK_REL]
)
def test_alvo_novo_esta_no_portao(relpath: str) -> None:
    """O portão de release precisa VER os três artefatos."""
    caminhos = {alvo[1] for alvo in _targets_do_portao()}
    assert relpath in caminhos, (
        f"{relpath} não é alvo de {GATE_REL} — voltou a poder envelhecer em "
        "silêncio (VERSOES-RANCOSAS-01)"
    )


@pytest.mark.parametrize(
    "relpath", [ENTRYPOINT_REL, METAINFO_REL, CARGO_REL, CARGO_LOCK_REL]
)
def test_regex_do_alvo_extrai_a_versao_canonica_do_arquivo_real(relpath: str) -> None:
    """Cada sintaxe é diferente (shell, XML, semver) — o regex tem que pegar.

    Este é o teste que morde no arquivo real: com o Cargo.toml de volta em
    0.1.0, ou o metainfo com a 3.13.3 na frente, ele falha.
    """
    esperado = _esperado_no_alvo(relpath)
    padrao = next(alvo[2] for alvo in _targets_do_portao() if alvo[1] == relpath)
    texto = (REPO / relpath).read_text(encoding="utf-8")
    achado = re.search(padrao, texto, re.MULTILINE)
    assert achado is not None, f"regex do portão não casa nada em {relpath}"
    assert achado.group(1) == esperado


def test_portao_real_passa_no_repo_real() -> None:
    """Acrescentar alvos só vale se o repo está consistente AGORA."""
    proc = subprocess.run(
        [sys.executable, GATE_REL], cwd=REPO, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK:" in proc.stdout


# --------------------------------------------------------------------------
# 2) O portão MORDE: repo fake com o alvo defasado precisa reprovar.
# --------------------------------------------------------------------------


def _repo_fake(tmp_path: Path, versao: str, relpath: str, versao_alvo: str) -> Path:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / GATE_REL, tmp_path / GATE_REL)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "fake"\nversion = "{versao}"\n', encoding="utf-8"
    )
    molde = next(molde for rel, molde in _ALVOS_NOVOS if rel == relpath)
    destino = tmp_path / relpath
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(molde.format(v=versao_alvo), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("relpath", [rel for rel, _ in _ALVOS_NOVOS])
def test_portao_reprova_alvo_novo_defasado(tmp_path: Path, relpath: str) -> None:
    repo = _repo_fake(tmp_path, versao="9.9.9", relpath=relpath, versao_alvo="0.0.1")
    proc = subprocess.run(
        [sys.executable, GATE_REL], cwd=repo, capture_output=True, text=True
    )
    assert proc.returncode == 1, (
        f"o portão PASSOU com {relpath} em 0.0.1 contra 9.9.9: "
        + proc.stdout
        + proc.stderr
    )
    assert relpath in proc.stdout
    assert "0.0.1" in proc.stdout


@pytest.mark.parametrize("relpath", [rel for rel, _ in _ALVOS_NOVOS])
def test_portao_aprova_alvo_novo_em_dia(tmp_path: Path, relpath: str) -> None:
    repo = _repo_fake(tmp_path, versao="9.9.9", relpath=relpath, versao_alvo="9.9.9")
    proc = subprocess.run(
        [sys.executable, GATE_REL], cwd=repo, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 alvo" in proc.stdout


# --------------------------------------------------------------------------
# 2-bis) QUATRO-COMPONENTES-02 (14/08): o portão exigia do Cargo uma string que
# o Cargo não aceita, e o applet parou de compilar em silêncio.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("canonica", "esperada"),
    [
        ("0.9.4.2", "0.9.4+2"),   # o caso real que quebrou a release
        ("0.9.4", "0.9.4"),       # três componentes atravessa intacto
        ("1.0.0.10", "1.0.0+10"),  # a quarta casa pode ter mais de um dígito
    ],
)
def test_versao_para_cargo_traduz_a_quarta_casa(canonica: str, esperada: str) -> None:
    """`X.Y.Z.W` vira `X.Y.Z+W`; `X.Y.Z` não é tocada."""
    assert _portao().versao_para_cargo(canonica) == esperada


def test_a_traducao_nao_usa_pre_release() -> None:
    """`-W` também compila e está ERRADO: inverteria a ordem da história.

    Build metadata (`+W`) não conta na precedência SemVer, então `0.9.4+2`
    ordena igual a `0.9.4`; `0.9.4-2` é pre-release e ordena ANTES dela.
    """
    assert "-" not in _portao().versao_para_cargo("0.9.4.2")


@pytest.mark.parametrize("relpath", [CARGO_REL, CARGO_LOCK_REL])
def test_portao_reprova_o_cargo_com_a_canonica_literal(
    tmp_path: Path, relpath: str
) -> None:
    """MORDE: escrever `9.9.9.9` no Cargo é exatamente o que quebrou o build.

    Era a menor edição que deixava o portão verde antes desta correção — e
    custou o applet. Agora reprova.
    """
    repo = _repo_fake(
        tmp_path, versao="9.9.9.9", relpath=relpath, versao_alvo="9.9.9.9"
    )
    proc = subprocess.run(
        [sys.executable, GATE_REL], cwd=repo, capture_output=True, text=True
    )
    assert proc.returncode == 1, (
        f"o portão APROVOU {relpath} com a canônica literal de quatro "
        "componentes, que o Cargo rejeita: " + proc.stdout + proc.stderr
    )
    assert "9.9.9+9" in proc.stdout, "a mensagem não diz a forma que ele espera"


@pytest.mark.parametrize("relpath", [CARGO_REL, CARGO_LOCK_REL])
def test_portao_aprova_o_cargo_traduzido(tmp_path: Path, relpath: str) -> None:
    """E o outro lado: com `9.9.9+9` no arquivo, passa."""
    repo = _repo_fake(
        tmp_path, versao="9.9.9.9", relpath=relpath, versao_alvo="9.9.9+9"
    )
    proc = subprocess.run(
        [sys.executable, GATE_REL], cwd=repo, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@pytest.mark.skipif(
    shutil.which("cargo") is None, reason="cargo ausente (CI sem toolchain Rust)"
)
def test_o_cargo_de_verdade_aceita_o_manifesto_real() -> None:
    """A prova final: quem julga o Cargo.toml é o Cargo, não o nosso regex.

    Sem isto o projeto volta a poder escrever uma versão que só o portão
    aprova — foi assim que `0.9.4.2` entrou e o applet parou de compilar.
    """
    proc = subprocess.run(
        ["cargo", "verify-project", "--manifest-path", CARGO_REL],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "o Cargo REJEITA o manifesto do applet: " + proc.stdout + proc.stderr
    )


def test_cargo_toml_e_lock_declaram_a_mesma_versao() -> None:
    """O lock ficou em `9.3.2` sem ninguém ver — o comentário pedia, e pedir
    não é portão."""
    def _versao(rel: str, padrao: str) -> str | None:
        achado = re.search(
            padrao, (REPO / rel).read_text(encoding="utf-8"), re.MULTILINE
        )
        return achado.group(1) if achado else None

    do_toml = _versao(CARGO_REL, r'^version\s*=\s*"([^"]+)"')
    do_lock = _versao(
        CARGO_LOCK_REL,
        r'^name = "hefesto-dualsense4unix-applet"\nversion = "([^"]+)"',
    )
    assert do_toml == do_lock, (
        f"Cargo.toml diz {do_toml!r} e Cargo.lock diz {do_lock!r} — o "
        "`cargo build` corrigiria sozinho, sujando a árvore no meio do release"
    )


def test_regex_do_cargo_ignora_a_versao_das_dependencias(tmp_path: Path) -> None:
    """Sem a âncora `^`, o regex casaria o `version = "1"` do tokio dentro de
    [dependencies] e o portão julgaria pela linha errada."""
    repo = _repo_fake(tmp_path, versao="9.9.9", relpath=CARGO_REL, versao_alvo="9.9.9")
    conteudo = (repo / CARGO_REL).read_text(encoding="utf-8")
    assert 'version = "1"' in conteudo, "o molde perdeu a linha de dependência"
    proc = subprocess.run(
        [sys.executable, GATE_REL], cwd=repo, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --------------------------------------------------------------------------
# 3) O banner do AppImage não pode voltar a ter versão digitada.
# --------------------------------------------------------------------------


def test_banner_do_appimage_deriva_a_versao() -> None:
    texto = (REPO / ENTRYPOINT_REL).read_text(encoding="utf-8")
    assert "'BANNER'" not in texto, (
        "o heredoc voltou a ser quoted (<<'BANNER'): dentro dele "
        "${HEFESTO_VERSION} sairia literal, sem expandir"
    )
    achado = re.search(r"cat <<'?BANNER'? >&2\n(.*?)\nBANNER\n", texto, re.DOTALL)
    assert achado is not None, "heredoc BANNER não encontrado no entrypoint"
    corpo = achado.group(1)
    assert "${HEFESTO_VERSION}" in corpo, "o banner não usa a versão derivada"
    assert re.search(r"v\d+\.\d+\.\d+", corpo) is None, (
        f"versão digitada de volta no banner: {corpo!r}"
    )


def test_deb_sugerido_pelo_banner_casa_o_nome_que_o_build_deb_gera() -> None:
    """O nome sugerido era `..._3.0.0_amd64.deb`, que não existe no formato
    atual: o build_deb.sh gera `_<versão>_amd64_py<tag>.deb`."""
    texto = (REPO / ENTRYPOINT_REL).read_text(encoding="utf-8")
    linha = next(ln for ln in texto.splitlines() if "apt install" in ln and "$" in ln)
    assert "${HEFESTO_VERSION}" in linha
    assert "_amd64_py" in linha, (
        "a sugestão perdeu a tag de Python do nome — o arquivo sugerido não "
        f"existe: {linha.strip()!r}"
    )
    build_deb = (REPO / "scripts/build_deb.sh").read_text(encoding="utf-8")
    assert "_amd64_${PYTAG}.deb" in build_deb, (
        "o build_deb.sh mudou o padrão do nome; a sugestão do banner precisa "
        "acompanhar"
    )


def test_fallback_do_banner_e_o_unico_literal_de_versao() -> None:
    texto = (REPO / ENTRYPOINT_REL).read_text(encoding="utf-8")
    esperado = _versao_canonica()
    # QUATRO-COMPONENTES-01 (13/08/2026): a versão canônica passou a ter
    # QUATRO componentes (0.9.4.2) por decisão dela — a série 0.9.4.x marca
    # o avanço do mapeamento dentro da mesma alfa. O regex de três casava
    # ZERO literais aqui e a asserção reprovava dizendo que o fallback
    # sumira, quando ele estava na linha 26, intacto. O `{1,2}` aceita as
    # duas formas sem afrouxar o que a regra cobra: continua sendo UM
    # literal, e continua tendo de ser o canônico.
    literais = re.findall(r'"(\d+\.\d+\.\d+(?:\.\d+)?)"', texto)
    assert literais == [esperado], (
        f"literais de versão em {ENTRYPOINT_REL}: {literais} "
        f"(esperado apenas o fallback {esperado})"
    )


# --------------------------------------------------------------------------
# 4) Metainfo: a release mais recente é a corrente.
# --------------------------------------------------------------------------


def test_metainfo_tem_a_versao_corrente_e_a_linha_0x() -> None:
    from xml.etree import ElementTree

    raiz = ElementTree.parse(REPO / METAINFO_REL).getroot()
    releases = raiz.find("releases")
    assert releases is not None
    versoes = [r.get("version") for r in releases.findall("release")]
    assert versoes[0] == _versao_canonica(), (
        f"a primeira <release> é {versoes[0]} — é essa que a loja anuncia. "
        f"Lista: {versoes[:4]}"
    )
    assert any(v is not None and v.startswith("0.") for v in versoes), (
        "nenhuma release 0.x no metainfo (a numeração voltou para 0.x em 24/07)"
    )


def test_metainfo_releases_em_ordem_decrescente_sem_linha_3x() -> None:
    """Réplica local do portão do .github/workflows/flatpak.yml.

    METAINFO-ORDEM-DAS-RELEASES-01: acrescentar a 0.3.0 mantendo as entradas
    3.x fazia o `appstreamcli validate` reprovar com
    `releases-not-in-order 0.1.0 << 3.13.3` (medido: exit 3), e pior — o
    AppStream compara versões, então uma loja com a 3.13.3 na lista entende que
    o mais novo do projeto é a 3.13.3 e nunca oferece a 0.3.0. A história das
    3.x vive no CHANGELOG.md.
    """
    from xml.etree import ElementTree

    raiz = ElementTree.parse(REPO / METAINFO_REL).getroot()
    releases = raiz.find("releases")
    assert releases is not None
    versoes = [r.get("version") or "" for r in releases.findall("release")]

    def como_tupla(v: str) -> tuple[int, ...]:
        return tuple(int(parte) for parte in v.split("."))

    tuplas = [como_tupla(v) for v in versoes]
    assert tuplas == sorted(tuplas, reverse=True), (
        f"releases fora de ordem decrescente: {versoes} — o appstreamcli "
        "reprova com releases-not-in-order"
    )
    assert all(t[0] == 0 for t in tuplas), (
        f"release pré-0.x de volta no metainfo: {versoes}. Com uma 3.x na "
        "lista a loja nunca oferece a 0.3.0 como atualização."
    )


def test_appstreamcli_valida_o_metainfo() -> None:
    """O mesmo comando do CI (job `validate-manifest` do flatpak.yml)."""
    if shutil.which("appstreamcli") is None:
        pytest.skip("appstreamcli ausente (o CI instala o pacote `appstream`)")
    proc = subprocess.run(
        ["appstreamcli", "validate", "--no-net", METAINFO_REL],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_metainfo_e_xml_valido_e_cada_release_tem_descricao() -> None:
    from xml.etree import ElementTree

    raiz = ElementTree.parse(REPO / METAINFO_REL).getroot()
    releases = raiz.find("releases")
    assert releases is not None
    for rel in releases.findall("release"):
        assert rel.get("date"), f"release {rel.get('version')} sem data"
        assert rel.find("description") is not None, (
            f"release {rel.get('version')} sem <description> — o AppStream "
            "mostra entrada vazia na loja"
        )


# --------------------------------------------------------------------------
# 5) Cargo.toml do applet: sem e-mail pessoal.
# --------------------------------------------------------------------------


def test_cargo_do_applet_nao_expoe_email_pessoal() -> None:
    """Nem o check_anonymity.sh (não procura e-mail) nem o check_test_data.sh
    (só varre tests/) enxergam este arquivo — este teste é o único portão."""
    texto = (REPO / CARGO_REL).read_text(encoding="utf-8")
    achados = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", texto)
    assert achados == [], f"e-mail pessoal de volta em {CARGO_REL}: {achados}"
    assert "[REDACTED]" in texto, (
        "o campo authors perdeu a redação no padrão do PKGBUILD"
    )


def test_pkgbuild_e_cargo_usam_o_mesmo_padrao_de_redacao() -> None:
    pkgbuild = (REPO / "packaging/arch/PKGBUILD").read_text(encoding="utf-8")
    assert "[REDACTED]" in pkgbuild, "o PKGBUILD deixou de ser a referência"
    cargo = (REPO / CARGO_REL).read_text(encoding="utf-8")
    assert re.search(r'authors\s*=\s*\["Vitoria Maria <\[REDACTED\]>"\]', cargo)


# --------------------------------------------------------------------------
# 6) Flatpak semeia os presets — no lugar em que o loader procura.
# --------------------------------------------------------------------------


def _comandos_do_modulo_hefesto() -> list[str]:
    manifesto = yaml.safe_load((REPO / MANIFESTO_REL).read_text(encoding="utf-8"))
    modulo = next(
        m
        for m in manifesto["modules"]
        if isinstance(m, dict) and m.get("name") == "hefesto"
    )
    return [" ".join(str(c).split()) for c in modulo["build-commands"]]


def _destino_do_loader_no_sandbox() -> str:
    """Onde o loader procura os presets quando sys.prefix é /app."""
    from hefesto_dualsense4unix.profiles.loader import _DEFAULT_SEED_SOURCE_DIRS

    relativo = _DEFAULT_SEED_SOURCE_DIRS[1].relative_to(sys.prefix)
    return str(Path("/app") / relativo)


def test_flatpak_semeia_presets_no_caminho_que_o_loader_procura() -> None:
    destino = _destino_do_loader_no_sandbox()
    comandos = _comandos_do_modulo_hefesto()
    casando = [c for c in comandos if "profiles_default" in c]
    assert casando, (
        "o manifesto Flatpak não instala assets/profiles_default — quem "
        "instala pelo Flatpak abre a janela sem perfil nenhum "
        "(FIX-FLATPAK-PRESET-SEED-01)"
    )
    assert any(destino in c for c in casando), (
        f"instala presets, mas fora de {destino} (o segundo candidato do "
        f"profiles/loader.py). Comandos: {casando}"
    )
    assert any("assets/profiles_default/*.json" in c for c in casando), (
        "a origem não é o glob de assets/profiles_default/*.json — um preset "
        f"novo ficaria de fora. Comandos: {casando}"
    )


def test_flatpak_e_appimage_gui_semeiam_o_mesmo_conjunto() -> None:
    """Paridade com o FIX-APPIMAGE-PRESET-SEED-01: os dois usam glob, então um
    preset novo em assets/ entra nos dois de graça."""
    gui = (REPO / BUILD_GUI_REL).read_text(encoding="utf-8")
    assert "profiles_default" in gui, (
        "o build_appimage_gui.sh perdeu a semeadura de presets — era a cura de "
        "referência deste sprint"
    )
    assert 'profiles_default/"*.json' in gui or "profiles_default/*.json" in gui
    presets = sorted(p.name for p in (REPO / "assets/profiles_default").glob("*.json"))
    assert presets, "assets/profiles_default está vazio"
    assert "fallback.json" in presets


def test_manifesto_flatpak_continua_instalando_os_glyphs() -> None:
    """Guarda de não-regressão: a linha nova entrou colada na dos glyphs."""
    comandos = _comandos_do_modulo_hefesto()
    assert any("assets/glyphs/*.svg" in c for c in comandos)
