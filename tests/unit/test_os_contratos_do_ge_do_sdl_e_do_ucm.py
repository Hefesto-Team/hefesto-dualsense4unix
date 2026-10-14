"""Os contratos do GE, do SDL e do UCM: cada um dispara fora do contrato e cala dentro.

OS-CONTRATOS-DO-GE-DO-SDL-E-DO-UCM-GANHAM-REGUA-E-AVISO-01. O GE-Proton e o SDL mudam o que o
jogo vê do controle SEM mudar porta nenhuma (a lista por appid que virou
`PROTON_SONY_AUTO_XINPUT=1`; o 054c:0df2 que o SDL 3.4 passou a tratar como Edge), e o
alsa-ucm-conf 1.2.15 traz o UCM do DualSense por cima do nosso. As versões aqui são de
mentira, numa Steam e num `/usr` de `tmp_path`: nada do que está instalado é lido.

A MORDIDA: tirar de `docs/data/contratos-de-fora.csv` a linha de um dos quatro contratos
reprova `test_o_censo_tem_a_linha_de_cada_contrato`; subir `GE_ULTIMO_MEDIDO` sem medir reprova
`test_ge_depois_do_ultimo_medido_avisa`; tirar o guarda do `install_ucm_dualsense.sh` reprova
`test_o_roteiro_do_ucm_nao_grava_por_cima_do_upstream`.
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import contratos_de_fora as cf

RAIZ = Path(__file__).resolve().parents[2]
CENSO = RAIZ / "docs" / "data" / "contratos-de-fora.csv"
ROTEIRO = RAIZ / "scripts" / "install_ucm_dualsense.sh"
IDS = ("ge-por-versao", "proton-da-valve-sem-som", "sdl-por-versao", "ucm-de-um-dono-so")


def _contrato(ident: str) -> cf.Contrato:
    return next(c for c in cf.CONTRATOS if c.id == ident)


def _linha(amb: cf.Ambiente, ident: str) -> tuple[str, str]:
    ((tag, mensagem),) = cf.linhas_do_doctor(amb, [_contrato(ident)])
    return tag, mensagem


class _Casa:
    """Uma casa de mentira com a Steam nativa e um `/usr` por baixo."""

    def __init__(self, base: Path) -> None:
        self.home = base / "casa"
        self.usr = base / "raiz"
        self.steam = self.home / ".steam" / "steam"
        (self.steam / "config").mkdir(parents=True)
        (self.steam / "steamapps" / "common").mkdir(parents=True)
        (self.steam / "compatibilitytools.d").mkdir()
        self.usr.mkdir()
        self.mapa: dict[str, str] = {}

    @property
    def amb(self) -> cf.Ambiente:
        return cf.Ambiente(home=self.home, env={}, raiz=self.usr)

    def ge(self, pasta: str, *, version: str | None = None) -> Path:
        alvo = self.steam / "compatibilitytools.d" / pasta
        alvo.mkdir()
        if version is not None:
            (alvo / "version").write_text(version, encoding="utf-8")
        return alvo

    def valve(self, pasta: str, *, com_env: bool, com_script: bool = True) -> Path:
        alvo = self.steam / "steamapps" / "common" / pasta
        alvo.mkdir()
        if com_script:
            texto = f'env["{cf.ENV_DA_PILHA_DE_SOM}"] = "1"\n' if com_env else "# sem a env\n"
            (alvo / "proton").write_text(texto, encoding="utf-8")
        return alvo

    def jogo(self, appid: str, nome: str, ferramenta: str) -> None:
        (self.steam / "steamapps" / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n'
            f'\t"installdir"\t\t"{nome}"\n}}\n',
            encoding="utf-8",
        )
        self.mapa[appid] = ferramenta
        linhas = [
            '"InstallConfigStore"', "{", '\t"Software"', "\t{", '\t\t"Valve"', "\t\t{",
            '\t\t\t"Steam"', "\t\t\t{", '\t\t\t\t"CompatToolMapping"', "\t\t\t\t{",
        ]
        for app, nome_da_ferramenta in self.mapa.items():
            linhas += [
                f'\t\t\t\t\t"{app}"', "\t\t\t\t\t{",
                f'\t\t\t\t\t\t"name"\t\t"{nome_da_ferramenta}"',
                '\t\t\t\t\t\t"config"\t\t""', '\t\t\t\t\t\t"priority"\t\t"250"',
                "\t\t\t\t\t}",
            ]
        linhas += ["\t\t\t\t}", "\t\t\t}", "\t\t}", "\t}", "}"]
        vdf = self.steam / "config" / "config.vdf"
        vdf.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    def sdl(self, onde: str, versao: str) -> None:
        pasta = self.usr / onde if not onde.startswith("steam:") else (
            self.steam / "steamapps" / "common" / "SteamLinuxRuntime_4" / onde[6:]
            / "files" / "lib" / "x86_64-linux-gnu"
        )
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"libSDL3.so.0.{versao}").write_bytes(b"")


@pytest.fixture
def casa(tmp_path: Path) -> _Casa:
    return _Casa(tmp_path)


# ---------------------------------------------------------------------------
# O GE-Proton por versão.


@pytest.mark.parametrize("pasta", ["GE-Proton11-4-x86_64", "GE-Proton11-7-x86_64"])
def test_ge_dentro_da_faixa_calada(casa: _Casa, pasta: str) -> None:
    casa.ge(pasta)
    assert _linha(casa.amb, "ge-por-versao")[0] == "[ OK ]"


def test_ge_11_8_avisa_o_que_mudou(casa: _Casa) -> None:
    casa.ge("GE-Proton11-8-x86_64")
    tag, mensagem = _linha(casa.amb, "ge-por-versao")
    assert tag == "[WARN]", mensagem
    assert "GE-Proton11-8-x86_64" in mensagem
    assert "PROTON_SONY_AUTO_XINPUT=1" in mensagem and "lista por appid" in mensagem
    assert "máscara escolhida" in mensagem
    assert "cat ~/.steam/steam/compatibilitytools.d/GE-Proton*/version" in mensagem


def test_ge_depois_do_ultimo_medido_avisa(casa: _Casa) -> None:
    casa.ge("GE-Proton11-9-x86_64")
    tag, mensagem = _linha(casa.amb, "ge-por-versao")
    assert tag == "[WARN]" and "posterior ao último GE que o Hefesto mediu" in mensagem, mensagem


def test_ge_antes_da_pilha_do_controle_avisa(casa: _Casa) -> None:
    casa.ge("GE-Proton11-3-x86_64")
    tag, mensagem = _linha(casa.amb, "ge-por-versao")
    assert tag == "[WARN]" and "anterior ao 11-4" in mensagem, mensagem


def test_ge_com_nome_que_nao_diz_a_versao_le_o_arquivo_version(casa: _Casa) -> None:
    casa.ge("GE-Proton-meu", version="1789520217 GE-Proton11-9\n")
    assert _linha(casa.amb, "ge-por-versao")[0] == "[WARN]"
    casa.ge("GE-Proton-outro", version="lixo\n")
    assert "GE-Proton-outro" not in _linha(casa.amb, "ge-por-versao")[1]


def test_o_ge_bom_ao_lado_nao_apaga_o_aviso_do_outro(casa: _Casa) -> None:
    casa.ge("GE-Proton11-7-x86_64")
    casa.ge("GE-Proton11-8-x86_64")
    tag, mensagem = _linha(casa.amb, "ge-por-versao")
    assert tag == "[WARN]" and "GE-Proton11-8-x86_64" in mensagem, mensagem
    assert "GE-Proton11-7-x86_64" not in mensagem, mensagem


def test_sem_ge_ou_sem_steam_e_informacao(casa: _Casa, tmp_path: Path) -> None:
    assert _linha(casa.amb, "ge-por-versao")[0] == "[INFO]"
    vazia = cf.Ambiente(home=tmp_path / "ninguem", env={}, raiz=tmp_path / "raiz")
    assert _linha(vazia, "ge-por-versao")[0] == "[INFO]"


# ---------------------------------------------------------------------------
# O Proton da Valve, que não traz a pilha de som do controle.


def test_jogo_no_proton_da_valve_sem_a_env_avisa_o_nome_e_o_que_se_perde(casa: _Casa) -> None:
    casa.valve("Proton 10.0", com_env=False)
    casa.jogo("111", "Jogo Um", "proton_10")
    casa.jogo("222", "Jogo Dois", "GE-Proton11-7-x86_64")
    tag, mensagem = _linha(casa.amb, "proton-da-valve-sem-som")
    assert tag == "[WARN]", mensagem
    assert "Proton 10.0: Jogo Um" in mensagem and "Jogo Dois" not in mensagem
    assert "vibração pelo som" in mensagem and "device KS" in mensagem


def test_proton_da_valve_que_traz_a_env_cala(casa: _Casa) -> None:
    casa.valve("Proton 10.0", com_env=True)
    casa.jogo("111", "Jogo Um", "proton_10")
    assert _linha(casa.amb, "proton-da-valve-sem-som")[0] == "[ OK ]"


def test_proton_da_valve_sem_jogo_nenhum_nao_tira_nada_de_ninguem(casa: _Casa) -> None:
    casa.valve("Proton Hotfix", com_env=False)
    casa.jogo("222", "Jogo Dois", "GE-Proton11-7-x86_64")
    assert _linha(casa.amb, "proton-da-valve-sem-som")[0] == "[ OK ]"


@pytest.mark.parametrize(
    ("pasta", "chave"),
    [
        ("Proton 10.0", "proton_10"),
        ("Proton Hotfix", "proton_hotfix"),
        ("Proton - Experimental", "proton_experimental"),
        ("Proton 11.0", "proton_11"),
    ],
)
def test_o_nome_da_pasta_vira_o_nome_do_mapa_da_steam(casa: _Casa, pasta: str, chave: str) -> None:
    assert cf._chave_do_proton_da_valve(pasta) == chave
    casa.valve(pasta, com_env=False)
    casa.jogo("333", "Terceiro Jogo", chave)
    assert _linha(casa.amb, "proton-da-valve-sem-som")[0] == "[WARN]"


def test_residuo_sem_o_script_nao_e_proton_instalado(casa: _Casa) -> None:
    casa.valve("Proton 11.0", com_env=False, com_script=False)
    assert _linha(casa.amb, "proton-da-valve-sem-som")[0] == "[INFO]"


# ---------------------------------------------------------------------------
# O SDL por versão.


def test_sdl_3_4_no_runtime_da_steam_e_o_medido(casa: _Casa) -> None:
    casa.sdl("steam:steamrt4_platform_4.0.20260928.262390", "4.16")
    assert _linha(casa.amb, "sdl-por-versao")[0] == "[ OK ]"


def test_sdl_depois_do_3_4_avisa_onde_achou(casa: _Casa) -> None:
    casa.sdl("steam:steamrt4_platform_4.0.20260928.262390", "5.0")
    tag, mensagem = _linha(casa.amb, "sdl-por-versao")
    assert tag == "[WARN]", mensagem
    assert "SDL 3.5.0" in mensagem and "054c:0df2" in mensagem and "paddles" in mensagem


def test_sdl_do_sistema_depois_do_3_4_tambem_avisa(casa: _Casa) -> None:
    casa.sdl("usr/lib/x86_64-linux-gnu", "6.2")
    assert _linha(casa.amb, "sdl-por-versao")[0] == "[WARN]"


def test_sdl_antes_do_3_4_cala(casa: _Casa) -> None:
    casa.sdl("usr/lib64", "2.30")
    assert _linha(casa.amb, "sdl-por-versao")[0] == "[ OK ]"


def test_so_o_runtime_mais_novo_vale(casa: _Casa) -> None:
    casa.sdl("steam:steamrt4_platform_4.0.20260316.216358", "5.0")
    casa.sdl("steam:steamrt4_platform_4.0.20260928.262390", "4.16")
    assert _linha(casa.amb, "sdl-por-versao")[0] == "[ OK ]"


def test_sem_libsdl3_e_informacao(casa: _Casa) -> None:
    assert _linha(casa.amb, "sdl-por-versao")[0] == "[INFO]"


# ---------------------------------------------------------------------------
# O UCM de um dono só.


def _ucm(casa: _Casa, *, upstream: bool, hefesto: bool) -> None:
    raiz = casa.usr / "usr" / "share" / "alsa" / "ucm2" / "USB-Audio"
    raiz.mkdir(parents=True, exist_ok=True)
    if upstream:
        (raiz / "DualSense-PS5-HiFi.conf").write_text("Syntax 4\n", encoding="utf-8")
    if hefesto:
        (raiz / "Hefesto").mkdir(exist_ok=True)
        (raiz / "Hefesto" / "DualSense-HiFi.conf").write_text("Syntax 4\n", encoding="utf-8")


def test_os_dois_ucm_juntos_avisam_e_dizem_como_tirar_o_nosso(casa: _Casa) -> None:
    _ucm(casa, upstream=True, hefesto=True)
    tag, mensagem = _linha(casa.amb, "ucm-de-um-dono-so")
    assert tag == "[WARN]", mensagem
    assert "DualSense-PS5-HiFi.conf" in mensagem
    assert "install_ucm_dualsense.sh --remover" in mensagem


@pytest.mark.parametrize(("upstream", "hefesto"), [(True, False), (False, True), (False, False)])
def test_um_dono_so_ou_nenhum_cala(casa: _Casa, upstream: bool, hefesto: bool) -> None:
    _ucm(casa, upstream=upstream, hefesto=hefesto)
    assert _linha(casa.amb, "ucm-de-um-dono-so")[0] == "[ OK ]"


def test_sem_alsa_ucm_conf_e_informacao(casa: _Casa) -> None:
    assert _linha(casa.amb, "ucm-de-um-dono-so")[0] == "[INFO]"


def _roteiro(base: Path, *, upstream: bool) -> tuple[subprocess.CompletedProcess[str], Path]:
    ucm = base / "ucm2"
    (ucm / "conf.d" / "USB-Audio").mkdir(parents=True)
    (ucm / "ucm.conf").write_text('Directory "conf.d/${var:Driver}"\n', encoding="utf-8")
    if upstream:
        (ucm / "USB-Audio" / "DualSense-PS5-HiFi.conf").parent.mkdir(exist_ok=True)
        (ucm / "USB-Audio" / "DualSense-PS5-HiFi.conf").write_text("Syntax 4\n", encoding="utf-8")
    sysfs = base / "sys"
    hub = sysfs / "devices" / "pci0000:00" / "0000:0c:00.3" / "usb1"
    hub.mkdir(parents=True)
    dispositivos = sysfs / "bus" / "usb" / "devices"
    dispositivos.mkdir(parents=True)
    (dispositivos / "usb1").symlink_to(hub)
    feito = subprocess.run(
        ["bash", str(ROTEIRO), "--raiz-ucm", str(ucm), "--sysfs", str(sysfs)],
        capture_output=True, text=True, check=False, timeout=60,
    )
    return feito, ucm


def test_o_roteiro_do_ucm_nao_grava_por_cima_do_upstream(tmp_path: Path) -> None:
    feito, ucm = _roteiro(tmp_path, upstream=True)
    assert feito.returncode == 0, feito.stderr
    assert "DualSense-PS5-HiFi.conf" in feito.stdout, feito.stdout
    assert not (ucm / "USB-Audio" / "Hefesto").exists()
    assert not list((ucm / "conf.d" / "USB-Audio").glob("*.conf"))


def test_sem_o_upstream_o_roteiro_grava_como_sempre(tmp_path: Path) -> None:
    feito, ucm = _roteiro(tmp_path, upstream=False)
    assert feito.returncode == 0, feito.stderr
    assert (ucm / "USB-Audio" / "Hefesto" / "DualSense-HiFi.conf").is_file()
    assert list((ucm / "conf.d" / "USB-Audio").glob("*.conf"))


# ---------------------------------------------------------------------------
# O censo e o doctor.


def test_o_censo_tem_a_linha_de_cada_contrato() -> None:
    with CENSO.open(encoding="utf-8", newline="") as fh:
        linhas = list(csv.DictReader(fh))
    citados = {li["como_o_doctor_ve"] for li in linhas}
    for ident in IDS:
        assert f"contrato:{ident}" in citados, f"o censo perdeu a linha de {ident}"
    versao = {li["como_o_doctor_ve"] for li in linhas if li["pergunta"] == "versão"}
    assert {"contrato:ge-por-versao", "contrato:sdl-por-versao"} <= versao
    for li in linhas:
        if li["como_o_doctor_ve"] in {f"contrato:{i}" for i in IDS[:3]}:
            assert li["motivo"] and li["sprint_filha"], li


def test_os_quatro_contratos_estao_no_doctor_e_dizem_o_que_conferir() -> None:
    for ident in IDS:
        contrato = _contrato(ident)
        assert contrato.conferir and contrato.promessa
    fonte = Path(cf.__file__).read_text(encoding="utf-8")
    assert "A EXCEÇÃO À REGRA DA CAPACIDADE" in fonte and "`pergunta=versão`" in fonte
