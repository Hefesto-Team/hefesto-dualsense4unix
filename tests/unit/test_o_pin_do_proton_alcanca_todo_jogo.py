"""O pin do Proton alcança todo jogo instalado (O-PIN-DO-PROTON-ALCANCA-TODO-JOGO-INSTALADO-01).

D-3010-O-PIN-DO-PROTON-VALE-PARA-TODO-JOGO: o dono é `proton_pin.apontar_os_lancadores_para_o_pino`,
e o que não se fixa vai à aba Lançadores. A casa, a Steam, o Heroic e a extensão são de mentira.
"""
from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import jogos_locais
from hefesto_dualsense4unix.integrations import proton_pin as pp
from hefesto_dualsense4unix.integrations import qualificar_proton as qp
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
from tests.unit.test_o_pino_chega_a_qualquer_computador import (
    PINO,
    _config_vdf,
    _jogo,
    _pino_na,
    _steam_de_verdade,
    _tarball,
    trava_da_rede,  # noqa: F401
)
from tests.unit.test_o_proton_novo_so_entra_se_passar import _proton_de_mentira
from tests.conftest import exigir_caixa_do_bwrap

RAIZ = Path(__file__).resolve().parents[2]
NATIVO = ".config/heroic"
FLATPAK = ".var/app/com.heroicgameslauncher.hgl/config/heroic"
VELHO = "GE-Proton9-20"
MAIS_NOVO = "GE-Proton11-10"
SEM_A_STRING = "x86_64-windows/mmdevapi.dll:PROTON_ENABLE_MHWILDS_USB_AUDIO"


@pytest.fixture()
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "lar"
    casa.mkdir()
    monkeypatch.setenv("HOME", str(casa))
    for nome, rel in (("XDG_CONFIG_HOME", ".config"), ("XDG_CACHE_HOME", ".cache"),
                      ("XDG_DATA_HOME", ".local/share"), ("XDG_STATE_HOME", ".local/state")):
        monkeypatch.setenv(nome, str(casa / rel))
    monkeypatch.setattr(pp, "steam_running", lambda: False)
    monkeypatch.setattr(pp, "steam_game_running", lambda: False)
    monkeypatch.setattr(censo, "heroic_aberto", lambda: False)
    monkeypatch.setattr(censo, "bottles_aberto", lambda: False)
    monkeypatch.setattr(censo, "lancadores_das_extensoes", lambda lugares=None: ())
    monkeypatch.setattr(jogos_locais, "pastas_de_atalhos",
                        lambda: [casa / ".local/share/applications", casa / "sistema/applications"])

    def _sem_rede(_url: str, _destino: Path) -> None:
        raise AssertionError("a régua foi à rede")

    monkeypatch.setattr(pp, "baixar_a_release", _sem_rede)
    return casa


@pytest.fixture()
def conf(tmp_path: Path, lar: Path) -> dict[str, str]:
    tarball = _tarball(tmp_path / "release")
    cache = lar / ".cache/hefesto-dualsense4unix/proton"
    cache.mkdir(parents=True)
    shutil.copy2(tarball, cache / tarball.name)
    return {"name": PINO, "url": "https://exemplo.invalido/x.tar.gz",
            "sha256": pp.sha256_of_file(tarball)}


def _escrever(arquivo: Path, dado: object) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dado), encoding="utf-8")


def _jogo_do_heroic(pasta: Path, app: str, ferramenta: dict[str, str]) -> Path:
    arquivo = pasta / "GamesConfig" / f"{app}.json"
    _escrever(arquivo, {app: {"wineVersion": ferramenta, "winePrefix": "/p"}, "version": "v0"})
    return arquivo


def _ferramenta(arquivo: Path, app: str) -> dict[str, str]:
    ferramenta: dict[str, str] = json.loads(arquivo.read_text(encoding="utf-8"))[app]["wineVersion"]
    return ferramenta


def _proton(onde: str, nome: str = VELHO) -> dict[str, str]:
    return {"bin": f"{onde}/{nome}/proton", "name": f"Proton - {nome}", "type": "proton"}


def _apontar(lar: Path, conf: dict[str, str], **k: object) -> censo.FixadoNoLancador:
    return pp.apontar_os_lancadores_para_o_pino(
        lar, conf=conf, compat_dir=lar / ".steam/steam/compatibilitytools.d",
        cache_dir=lar / ".cache/hefesto-dualsense4unix/proton", **k)  # type: ignore[arg-type]


def test_o_minimo_e_o_11_7_e_o_conf_do_produto_o_cumpre() -> None:
    """D-3010-O-PIN-DO-PROTON-VALE-PARA-TODO-JOGO: o mínimo é o GE-Proton 11.7."""
    assert pp.PROTON_MINIMO == (11, 7)
    vendido = pp.parse_pin_conf((RAIZ / "assets" / "proton-pin.conf").read_text(encoding="utf-8"))
    assert qp.ordem_da_versao(vendido["name"]) >= pp.PROTON_MINIMO, vendido["name"]


def test_steam_todo_jogo_e_o_atalho_de_fora_vao_ao_pino(lar: Path, conf: dict[str, str]) -> None:
    raiz = _steam_de_verdade(lar)
    _pino_na(raiz)
    _jogo(raiz, "9949958")
    vdf = raiz / "config" / "config.vdf"
    vdf.write_text(_config_vdf({"9949958": "proton_9", "3456789012": VELHO}), encoding="utf-8")
    pp.lock_proton_for_all_games(conf=conf, home=lar, config_vdf=vdf,
                                 state_path=lar / "lock.json", todos=True,
                                 compat_dir=raiz / "compatibilitytools.d")
    mapa = pp.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))
    assert mapa == {"0": PINO, "9949958": PINO, "3456789012": PINO}, mapa


def test_o_heroic_nativo_vai_ao_pino_mesmo_com_o_proton_proprio(
        lar: Path, conf: dict[str, str]) -> None:
    """D-3010-O-PIN-DO-PROTON-VALE-PARA-TODO-JOGO. Mordida: trocar só o Proton da Steam reprova."""
    raiz = _steam_de_verdade(lar)
    pino = _pino_na(raiz)
    heroic = lar / NATIVO
    jogo = _jogo_do_heroic(heroic, "abc", _proton(f"{heroic}/tools/proton"))
    _escrever(heroic / "config.json", {"defaultSettings": {"wineVersion": {
        "bin": "/opt/wine/bin/wine", "name": "Wine - 9", "type": "wine"}}})

    feito = _apontar(lar, conf)

    assert _ferramenta(jogo, "abc")["bin"] == f"{pino}/proton"
    assert _ferramenta(jogo, "abc")["name"] == f"Proton - {PINO}"
    padrao = json.loads((heroic / "config.json").read_text(encoding="utf-8"))
    assert padrao["defaultSettings"]["wineVersion"]["bin"] == f"{pino}/proton", (
        "o jogo instalado depois nasce do padrão, e o padrão ficou no Wine")
    assert feito.reescritas == 2 and feito.fora == ()
    assert list(heroic.glob("**/*.bak.hefesto-proton-*"))


def test_o_heroic_do_flatpak_ganha_o_pino_dentro_da_caixa(
        lar: Path, conf: dict[str, str]) -> None:
    """Mordida: a caixa do Flatpak não enxerga a pasta da Steam; o pino nasce dentro da caixa."""
    raiz = _steam_de_verdade(lar)
    _pino_na(raiz)
    caixa = lar / FLATPAK
    jogo = _jogo_do_heroic(caixa, "xyz", _proton(f"{caixa}/tools/proton"))

    feito = _apontar(lar, conf)

    dentro = caixa / "tools" / "proton" / PINO
    assert pp.pinned_proton_installed(PINO, caixa / "tools" / "proton")
    assert _ferramenta(jogo, "xyz")["bin"] == f"{dentro}/proton"
    assert feito.fora == ()


def test_sem_steam_o_heroic_recebe_o_pino_do_cache(lar: Path, conf: dict[str, str]) -> None:
    heroic = lar / NATIVO
    jogo = _jogo_do_heroic(heroic, "abc", _proton("/outro/lugar"))
    _apontar(lar, conf)
    assert _ferramenta(jogo, "abc")["bin"] == f"{heroic}/tools/proton/{PINO}/proton"
    assert not (lar / ".steam").exists(), "a casa da Steam nasceu sem a Steam"


@pytest.mark.parametrize("rel", [NATIVO, FLATPAK], ids=["nativo", "flatpak"])
def test_o_ge_mais_novo_da_casa_do_heroic_que_passa_na_ficha_e_o_pino_da_casa(
        lar: Path, conf: dict[str, str], rel: str) -> None:
    """O-PINO-DO-HEROIC-E-O-MAIS-NOVO-DA-CASA-DELE-01. Mordida: o pino só da Steam rebaixa."""
    _pino_na(_steam_de_verdade(lar))
    casa = lar / rel
    novo = _proton_de_mentira(casa / "tools" / "proton" / MAIS_NOVO)
    fica = _jogo_do_heroic(casa, "fica", _proton(f"{casa}/tools/proton", MAIS_NOVO))
    antes = fica.read_bytes()
    sobe = _jogo_do_heroic(casa, "sobe", _proton("/outro"))

    feito = _apontar(lar, conf)

    assert fica.read_bytes() == antes
    assert _ferramenta(sobe, "sobe")["bin"] == f"{novo}/proton"
    assert feito.reescritas == 1 and feito.fora == ()
    assert not pp.pinned_proton_installed(PINO, casa / "tools" / "proton"), (
        "a casa com um GE que passa extraiu o do cache")
    assert _apontar(lar, conf).reescritas == 0


@pytest.mark.parametrize("rel", [NATIVO, FLATPAK], ids=["nativo", "flatpak"])
def test_o_ge_mais_novo_da_casa_que_reprova_na_ficha_vai_ao_pino(
        lar: Path, conf: dict[str, str], rel: str) -> None:
    """Mordida: aceitar o GE da casa sem a ficha deixa o jogo num Proton que reprova."""
    raiz = _steam_de_verdade(lar)
    pino = _pino_na(raiz)
    casa = lar / rel
    _proton_de_mentira(casa / "tools" / "proton" / "GE-Proton11-9", sem=SEM_A_STRING)
    jogo = _jogo_do_heroic(casa, "j", _proton(f"{casa}/tools/proton", "GE-Proton11-9"))

    feito = _apontar(lar, conf)

    onde = pino if rel == NATIVO else casa / "tools" / "proton" / PINO
    assert _ferramenta(jogo, "j")["bin"] == f"{onde}/proton"
    assert feito.reescritas == 1 and feito.fora == ()


def test_o_jogo_pelo_wine_fica_e_e_dito(lar: Path, conf: dict[str, str]) -> None:
    """Trocar o Wine por Proton estragaria o prefixo do jogo: ele fica, e a aba diz."""
    _pino_na(_steam_de_verdade(lar))
    heroic = lar / NATIVO
    wine = {"bin": "/opt/wine/bin/wine", "name": "Wine - 9", "type": "wine"}
    jogo = _jogo_do_heroic(heroic, "w", wine)
    antes = jogo.read_bytes()

    feito = _apontar(lar, conf)

    assert jogo.read_bytes() == antes
    assert feito.fora == (censo.ForaDoPino("heroic", "w", censo.PORQUE_PELO_WINE),)


def test_a_dica_diz_o_titulo_do_jogo_e_nao_a_chave(lar: Path, conf: dict[str, str]) -> None:
    """MORDIDA: devolva a chave crua ao ``ForaDoPino`` do ``fixar_o_heroic``."""
    _pino_na(_steam_de_verdade(lar))
    heroic = lar / NATIVO
    _jogo_do_heroic(heroic, "k9f2", {"bin": "/opt/wine/bin/wine", "name": "W", "type": "wine"})
    _jogo_do_heroic(heroic, "semtitulo", {"bin": "/opt/wine/bin/wine", "name": "W", "type": "wine"})
    _escrever(heroic / "store_cache/legendary_library.json", {"library": [
        {"app_name": "k9f2", "title": "Corrida de Inverno", "is_installed": True}]})
    _escrever(heroic / "legendaryConfig/legendary/installed.json",
              {"k9f2": {"app_name": "k9f2", "install_path": "/j", "platform": "Windows"}})

    feito = _apontar(lar, conf)

    assert sorted(f.jogo for f in feito.fora) == ["Corrida de Inverno", "semtitulo"], feito.fora


def test_o_jogo_nativo_do_linux_nao_conta(lar: Path, conf: dict[str, str]) -> None:
    _pino_na(_steam_de_verdade(lar))
    heroic = lar / NATIVO
    _escrever(heroic / "gog_store" / "installed.json", {"installed": [
        {"appName": "nat", "platform": "linux", "install_path": "/j"}]})
    jogo = _jogo_do_heroic(heroic, "nat", {"bin": "", "name": "", "type": "wine"})
    feito = _apontar(lar, conf)
    assert feito.fora == () and _ferramenta(jogo, "nat")["bin"] == ""


def test_o_heroic_aberto_nao_e_escrito_e_e_dito(
        lar: Path, conf: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    _pino_na(_steam_de_verdade(lar))
    jogo = _jogo_do_heroic(lar / NATIVO, "abc", _proton("/outro"))
    antes = jogo.read_bytes()
    monkeypatch.setattr(censo, "heroic_aberto", lambda: True)

    feito = _apontar(lar, conf)

    assert jogo.read_bytes() == antes and feito.reescritas == 0
    assert censo.ForaDoPino("heroic", "", censo.PORQUE_HEROIC_ABERTO) in feito.fora


def test_so_medir_nao_escreve_e_diz_quem_esta_fora(lar: Path, conf: dict[str, str]) -> None:
    """É o que a aba lê: `escrever=False` não toca arquivo nem extrai o pino."""
    _pino_na(_steam_de_verdade(lar))
    caixa = lar / FLATPAK
    jogo = _jogo_do_heroic(lar / NATIVO, "abc", _proton("/outro"))
    _jogo_do_heroic(caixa, "xyz", _proton("/outro"))
    antes = jogo.read_bytes()

    medida = _apontar(lar, conf, escrever=False)

    assert jogo.read_bytes() == antes
    assert not (caixa / "tools").exists()
    assert set(medida.fora) == {
        censo.ForaDoPino("heroic", "abc", censo.PORQUE_AINDA_NAO),
        censo.ForaDoPino("heroic", "", censo.PORQUE_SEM_O_PINO)}


def test_o_que_nao_se_le_ou_nao_se_extrai_e_dito(lar: Path, conf: dict[str, str],
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """Mordida: a pasta que não se lê e a extração que falha não somem da aba em silêncio."""
    _jogo_do_heroic(lar / NATIVO, "abc", _proton("/outro"))

    def _sem_disco(*_a: object, **_k: object) -> None:
        raise PermissionError(13, "Permissão negada")

    monkeypatch.setattr(pp, "ensure_pinned_proton", _sem_disco)
    assert _apontar(lar, conf).fora == (
        censo.ForaDoPino("heroic", "", censo.PORQUE_SEM_O_PINO),)

    monkeypatch.setattr(censo, "pastas_que_existem", _sem_disco)
    assert _apontar(lar, conf).fora == (
        censo.ForaDoPino("heroic", "", censo.PORQUE_ILEGIVEL),)
    assert pp.quem_usa_o_proton(lar) == ()


FIXADOR = textwrap.dedent("""\
    import json, os, pathlib
    jogos = pathlib.Path(os.environ["HOME"]) / ".config/lutris/games"
    fixados = 0
    for yml in sorted(jogos.glob("*.yml")):
        texto = yml.read_text()
        nome = os.environ["HEFESTO_PROTON_NOME"]
        novo = texto.replace("version: GE-Proton9-20", "version: " + nome)
        if novo != texto:
            yml.write_text(novo)
            fixados += 1
    fora = [{"nome": "Um do Wine", "porque": "roda pelo Wine"}]
    print(json.dumps({"fixados": fixados, "fora": fora}))
""")


def _extensao_do_lutris(lar: Path, monkeypatch: pytest.MonkeyPatch, *,
                        com_fixador: bool) -> Path:
    pasta = lar / ".local/share/hefesto-dualsense4unix/mods/lutris"
    pasta.mkdir(parents=True)
    (pasta / "fixar.py").write_text(FIXADOR, encoding="utf-8")
    bloco: dict[str, object] = {"rotulo": "Lutris", "comandos": ["lutris"],
                                "leitor": {"executar": ["python3", "ler.py"]}}
    if com_fixador:
        bloco["fixador"] = {"executar": ["python3", "fixar.py"], "fontes": [".config/lutris"]}
    lido = censo.lancador_da_modificacao("lutris", bloco, pasta)
    monkeypatch.setattr(censo, "lancadores_das_extensoes",
                        lambda lugares=None: (censo.LancadorDaExtensao(lido),))
    monkeypatch.setattr(censo, "ler_por_processo", lambda leitor, **_k: censo.BibliotecaDoLancador(
        "Lutris", censo.LIDO, None, [censo.JogoDoLancador("j1", "Um Jogo", proton=VELHO)]))
    yml = lar / ".config/lutris/games/um-jogo.yml"
    yml.parent.mkdir(parents=True)
    yml.write_text(f"game:\n  exe: /x\nwine:\n  version: {VELHO}\n", encoding="utf-8")
    return yml


@pytest.mark.parametrize("caixa", [False, True], ids=["sem-bwrap", "na-caixa-do-bwrap"])
def test_o_lutris_pela_extensao_fixa_pelo_manifesto(
        lar: Path, conf: dict[str, str], monkeypatch: pytest.MonkeyPatch, caixa: bool) -> None:
    """D-3010-O-PIN-DO-PROTON-VALE-PARA-TODO-JOGO. Mordida: tire o laço das extensões."""
    if caixa:
        exigir_caixa_do_bwrap()
    _pino_na(_steam_de_verdade(lar))
    yml = _extensao_do_lutris(lar, monkeypatch, com_fixador=True)

    feito = _apontar(lar, conf, bwrap=caixa)

    assert f"version: {PINO}" in yml.read_text(encoding="utf-8")
    assert feito.reescritas == 1
    assert feito.fora == (censo.ForaDoPino("lutris", "Um do Wine", "roda pelo Wine"),)


def test_a_extensao_sem_fixador_e_dita_na_aba(
        lar: Path, conf: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    _pino_na(_steam_de_verdade(lar))
    yml = _extensao_do_lutris(lar, monkeypatch, com_fixador=False)
    antes = yml.read_bytes()
    feito = _apontar(lar, conf)
    assert yml.read_bytes() == antes
    assert feito.fora == (censo.ForaDoPino("lutris", "Um Jogo", censo.PORQUE_SEM_FIXADOR),)


def test_o_lutris_no_disco_sem_a_extensao_e_dito(lar: Path, conf: dict[str, str]) -> None:
    _pino_na(_steam_de_verdade(lar))
    (lar / ".config/lutris/games").mkdir(parents=True)
    feito = _apontar(lar, conf)
    assert feito.fora == (censo.ForaDoPino("lutris", "", censo.PORQUE_SEM_A_EXTENSAO),)


def test_o_fixador_do_manifesto_e_conferido() -> None:
    base = {"rotulo": "Lutris", "comandos": ["lutris"]}
    for ruim in ({"executar": ["fixar.py"]}, {"executar": ["fixar.py"], "fontes": ["/etc"]},
                 {"executar": ["fixar.py"], "fontes": ["../fora"]}):
        with pytest.raises(ValueError, match="fixador"):
            censo.lancador_da_modificacao("lutris", {**base, "fixador": ruim}, Path("/x"))


def test_o_jogo_instalado_depois_entra_na_volta_do_vigia(
        lar: Path, conf: dict[str, str], tmp_path: Path) -> None:
    """Mordida: o `--manter` que para sem Steam deixa o jogo novo do Heroic no Proton antigo."""
    heroic = lar / NATIVO
    _jogo_do_heroic(heroic, "primeiro", _proton("/outro"))
    arquivo_conf = tmp_path / "proton-pin.conf"
    arquivo_conf.write_text("".join(f"{k}={v}\n" for k, v in conf.items()), encoding="utf-8")
    argv = ["--manter", "--conf", str(arquivo_conf), "--state", str(lar / "estado.json")]
    assert pp.main(argv) == 0

    novo = _jogo_do_heroic(heroic, "depois", _proton("/outro"))
    assert pp.main(argv) == 0

    assert _ferramenta(novo, "depois")["bin"] == f"{heroic}/tools/proton/{PINO}/proton"


def test_o_cartao_diz_quantos_jogos_ficaram_fora_e_por_que() -> None:
    """Mordida: sem a linha, o jogo fora do pino some em silêncio da aba Lançadores."""
    item = next(x for x in desenho.procurados(()) if x.chave == "heroic")
    fora = (("w", censo.PORQUE_PELO_WINE), ("", censo.PORQUE_HEROIC_ABERTO))
    cartao = desenho.cartao_sem_censo(item, "/casa/.config/heroic",
                                      desenho.DoDisco(fora_do_pino=(("heroic", fora),)))
    assert cartao.selo == "warn"
    assert "1 fora do Proton fixado" in cartao.diz
    assert f"w: {censo.PORQUE_PELO_WINE}" in cartao.diz
    limpo = desenho.cartao_sem_censo(item, "/casa/.config/heroic", desenho.DoDisco())
    assert limpo.selo == "localizado" and "Proton" not in limpo.diz


def test_a_linha_do_lancador_na_aba_mostra_o_que_ficou_fora() -> None:
    """Mordida: a fila sem o `fora_do_pino` esconde o jogo fora, porque a aba mostra só a linha."""
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    fora = (("w", censo.PORQUE_PELO_WINE),)
    lida = desenho.Leitura(onde_estao=(("heroic", "/casa/.config/heroic"),),
                           do_disco=desenho.DoDisco(fora_do_pino=(("heroic", fora),)))
    linhas = {f.chave: exp.fila_html(f) for f in a07._fila_de(desenho.cartoes(lida))}
    assert "1 fora do Proton fixado" in linhas["heroic"], linhas["heroic"]
    assert censo.PORQUE_PELO_WINE in linhas["heroic"]
    assert "Proton fixado" not in linhas["steam"]
    exemplo = next(f for f in exp.LANCADORES if f.chave == "lutris")
    assert exemplo.fora_do_pino == desenho.fora_do_pino_html(
        (("Corrida de Inverno", censo.PORQUE_PELO_WINE),)), "o desenho não é o que o produto pinta"


def test_a_aba_agrupa_o_que_ficou_fora_por_cartao(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    medida = censo.FixadoNoLancador(0, (
        censo.ForaDoPino("heroic", "w", censo.PORQUE_PELO_WINE),
        censo.ForaDoPino("lutris", "", censo.PORQUE_SEM_FIXADOR),
        censo.ForaDoPino("heroic", "abc", censo.PORQUE_AINDA_NAO)))
    pedidos: list[bool] = []

    def _medir(**k: object) -> censo.FixadoNoLancador:
        pedidos.append(bool(k.get("escrever", True)))
        return medida

    monkeypatch.setattr(pp, "apontar_os_lancadores_para_o_pino", _medir)
    assert a07._fora_do_pino() == (
        ("heroic", (("w", censo.PORQUE_PELO_WINE), ("abc", censo.PORQUE_AINDA_NAO))),
        ("lutris", (("", censo.PORQUE_SEM_FIXADOR),)))
    assert pedidos == [False], "a pintura escreveu no disco"
