"""O som lê o `pactl` em JSON, por campo nomeado, e acha os módulos pela porta.

O texto longo do `pactl list` era lido por rótulo e por posição: um rótulo
traduzido, uma linha a mais ou a ordem trocada derrubavam o leitor calados.
O `--format=json` entrega campos NOMEADOS. Estas réguas montam um `pactl` de
mentira com os rótulos trocados e a ordem trocada, e a leitura tem de dar o
mesmo — e, sem a porta do JSON, tem de dizer «não sei» em vez de adivinhar
pelo texto longo.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import porta_do_som as pds

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

SINKS = [
    {
        "index": 51, "state": "SUSPENDED", "name": "alsa_output.pci-0000_01_00.1.hdmi-stereo",
        "description": "(null)", "driver": "PipeWire",
        "sample_specification": "s32le 2ch 48000Hz", "mute": False,
        "volume": {"front-left": {"value": 65536, "value_percent": "100%", "db": "0.00 dB"},
                   "front-right": {"value": 32768, "value_percent": "50%", "db": "-18.06 dB"}},
        "balance": 0.0,
        "properties": {"device.description": "Navi HDMI", "sysfs.path": "/devices/pci0000:00/x"},
    },
    {
        "index": 52, "state": "RUNNING", "name": "hefesto_hap_0000a1",
        "description": "Háptica", "driver": "PipeWire",
        "sample_specification": "float32le 4ch 48000Hz", "mute": True,
        "volume": {"front-left": {"value": 65536, "value_percent": "100%", "db": "0.00 dB"}},
        "balance": 0.1,
        "properties": {"node.name": "hefesto_hap_0000a1"},
    },
]

SOURCES = [
    {"index": 61, "state": "SUSPENDED", "name": "alsa_input.usb-Sony.mono",
     "description": "DualSense", "driver": "PipeWire", "sample_specification": "s16le 1ch 48000Hz",
     "mute": False, "properties": {"alsa.card": "3", "sysfs.path": "/devices/usb1/1-2"}},
    {"index": 62, "name": "hefesto_mic_0000a1", "properties": {}},
    {"index": 63, "name": "so.monitor", "properties": {"alsa.card": ""}},
]

FLUXOS = [
    {"index": 901, "sink": 52, "client": "77", "driver": "PipeWire",
     "sample_specification": "float32le 4ch 48000Hz", "corked": False, "mute": False,
     "properties": {"application.name": "Jogo", "application.process.id": "4242"}},
    {"index": 902, "sink": 51, "client": None, "properties": {}},
]


def _servidor(respostas: dict[tuple[str, ...], str | None]) -> Any:
    chamadas: list[tuple[str, ...]] = []

    def ler(argv: list[str]) -> str | None:
        chamadas.append(tuple(argv))
        return respostas.get(tuple(argv))

    ler.chamadas = chamadas  # type: ignore[attr-defined]
    return ler


def _json(*partes: str) -> tuple[str, ...]:
    return ("pactl", "--format=json", "list", *partes)


def test_o_no_vem_por_campo_nomeado_e_a_ordem_dos_campos_nao_conta() -> None:
    texto = json.dumps([dict(reversed(list(o.items()))) for o in SINKS])
    ler = _servidor({_json("sinks"): texto})
    hdmi, hap = pds.ler_nos("sinks", ler) or ()
    assert (hdmi.indice, hdmi.nome, hdmi.estado) == (51, "alsa_output.pci-0000_01_00.1.hdmi-stereo",
                                                     "SUSPENDED")
    assert hdmi.porcentos == [100, 50]
    assert hdmi.mudo is False and hap.mudo is True
    assert hap.formato == "float32le 4ch 48000Hz" and hap.balanco == "balance 0.10"
    assert ler.chamadas == [_json("sinks")]


def test_o_acento_que_o_pactl_nao_escreve_vira_vazio_e_a_descricao_recua() -> None:
    """`pactl` 16.1 imprime `(null)` no campo com acento: vazio, nunca a palavra «(null)»."""
    (hdmi, hap) = pds.ler_nos("sinks", _servidor({_json("sinks"): json.dumps(SINKS)})) or ()
    assert hdmi.descricao == "Navi HDMI"
    assert hap.descricao == "Háptica"
    assert "(null)" not in "".join(n.descricao for n in (hdmi, hap))


def test_sem_a_porta_do_json_a_resposta_e_nao_sei_e_nunca_o_texto_longo() -> None:
    longo = "Sink #51\n\tState: SUSPENDED\n\tName: alsa_output.x\n"
    for resposta in (None, "", longo, "pactl: opção desconhecida '--format=json'", "{}"):
        ler = _servidor({_json("sinks"): resposta, _json("sources"): resposta})
        assert pds.ler_nos("sinks", ler) is None
        assert pds.sysfs_por_no("sources", ler) is None
        assert pds.placa_de_cada_fonte(ler) is None
        assert pds.volumes_do_no("sinks", "x", ler) is None


def test_lista_vazia_e_resposta_e_nao_e_nao_sei() -> None:
    ler = _servidor({_json("sinks"): "[]"})
    assert pds.ler_nos("sinks", ler) == ()


def test_o_sysfs_e_a_placa_saem_de_propriedade_e_o_no_virtual_entra_vazio() -> None:
    ler = _servidor({_json("sources"): json.dumps(SOURCES)})
    assert pds.sysfs_por_no("sources", ler) == {
        "alsa_input.usb-Sony.mono": "/devices/usb1/1-2",
        "hefesto_mic_0000a1": "",
        "so.monitor": "",
    }
    assert pds.placa_de_cada_fonte(ler) == {"alsa_input.usb-Sony.mono": "3"}


def test_o_volume_de_um_no_pelo_nome() -> None:
    ler = _servidor({_json("sinks"): json.dumps(SINKS)})
    assert pds.volumes_do_no("sinks", "alsa_output.pci-0000_01_00.1.hdmi-stereo", ler) == [100, 50]
    assert pds.volumes_do_no("sinks", "nao-existe", ler) is None


def test_o_fluxo_diz_para_onde_vai_e_quem_o_abriu() -> None:
    ler = _servidor({_json("sink-inputs"): json.dumps(FLUXOS)})
    jogo, solto = pds.ler_fluxos("sink-inputs", ler) or ()
    assert (jogo.indice, jogo.alvo, jogo.cliente) == (901, "52", "77")
    assert jogo.carrega("Jogo") and not jogo.carrega("Outro") and not jogo.carrega("")
    assert solto.alvo == "51" and solto.cliente == ""


def test_o_tipo_errado_e_erro_de_quem_chama() -> None:
    ler = _servidor({})
    with pytest.raises(ValueError):
        pds.ler_nos("sink-inputs", ler)
    with pytest.raises(ValueError):
        pds.ler_fluxos("sinks", ler)
    assert ler.chamadas == []


@pytest.mark.parametrize(("argv", "json_pedido"), [
    (["pactl", "--format=json", "list", "sinks"], True),
    (["pactl", "-f", "json", "list", "sinks"], True),
    (["pactl", "--format", "json", "list", "sinks"], True),
    (["pactl", "list", "sinks"], False),
    (["pactl", "list", "sinks", "short"], False),
])
def test_o_pedido_de_json_se_reconhece_em_todas_as_grafias(
        argv: list[str], json_pedido: bool) -> None:
    resto, pedido = pds.sem_o_formato(argv)
    assert pedido is json_pedido
    assert resto == ["pactl", "list", "sinks", *(["short"] if "short" in argv else [])]


def test_o_curto_e_o_json_dao_os_mesmos_nos_na_parte_que_o_curto_conhece() -> None:
    json_nos = pds.nos_do_texto(json.dumps(SINKS))
    curto = "\n".join(
        f"{n.indice}\t{n.nome}\t{n.driver}\t{n.formato}\t{n.estado}" for n in json_nos)
    curtos = pds.nos_do_texto(curto)
    assert [(n.indice, n.nome, n.estado) for n in curtos] == [
        (n.indice, n.nome, n.estado) for n in json_nos]


# ---------------------------------------------------------------------------
# A pasta dos módulos do PipeWire


def _esquecer() -> None:
    """A pasta lembrada é do processo; a régua a esquece pelo estado do módulo."""
    with pds._TRAVA_DOS_DIRETORIOS:
        pds._DIRETORIOS_ACHADOS = None


@pytest.fixture(autouse=True)
def _sem_lembranca() -> Any:
    _esquecer()
    yield
    _esquecer()


def test_o_ambiente_manda_e_o_pkg_config_completa(tmp_path: Path) -> None:
    mais = tmp_path / "mais"
    mais.mkdir()
    perguntas: list[list[str]] = []

    def perguntar(argv: list[str]) -> str | None:
        perguntas.append(argv)
        return "/usr/lib/x/pipewire-0.3\n"

    achados = pds.diretorios_de_modulos(perguntar, {pds.AMBIENTE_DO_DIRETORIO: str(mais)})
    assert achados == [str(mais), "/usr/lib/x/pipewire-0.3"]
    assert perguntas == [["pkg-config", "--variable=moduledir", "libpipewire-0.3"]]


def test_sem_pkg_config_a_pasta_vem_do_ldconfig_e_da_versao_instalada() -> None:
    saida = (
        "\t12 libs found in cache `/etc/ld.so.cache'\n"
        "\tlibpipewire-0.3.so.0 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libpipewire-0.3.so.0\n"
        "\tlibpulse.so.0 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libpulse.so.0\n")

    def perguntar(argv: list[str]) -> str | None:
        return saida if argv[0] == "ldconfig" else None

    assert pds.diretorios_de_modulos(perguntar, {}) == ["/usr/lib/x86_64-linux-gnu/pipewire-0.3"]


def test_sem_nenhuma_pista_a_lista_e_vazia_e_nada_e_inventado() -> None:
    assert pds.diretorios_de_modulos(lambda _a: None, {}) == []
    assert pds.tem_modulo("libpipewire-module-pipe-tunnel.so", []) is False


def test_tem_modulo_olha_o_arquivo_na_pasta_dada(tmp_path: Path) -> None:
    (tmp_path / "libpipewire-module-pipe-tunnel.so").write_bytes(b"")
    assert pds.tem_modulo("libpipewire-module-pipe-tunnel.so", [str(tmp_path)]) is True
    assert pds.tem_modulo("libpipewire-module-outro.so", [str(tmp_path)]) is False


def test_o_produto_lembra_a_pasta_e_a_regua_esquece(monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Path) -> None:
    monkeypatch.setenv(pds.AMBIENTE_DO_DIRETORIO, str(tmp_path))
    assert pds.diretorios_de_modulos()[0] == str(tmp_path)
    monkeypatch.delenv(pds.AMBIENTE_DO_DIRETORIO)
    assert pds.diretorios_de_modulos()[0] == str(tmp_path), "o produto perguntou duas vezes"
    _esquecer()
    assert str(tmp_path) not in pds.diretorios_de_modulos()


# ---------------------------------------------------------------------------
# O `pactl` de mentira DE VERDADE: rótulos trocados, ordem trocada, processo de fato


def test_o_pactl_de_mentira_com_os_rotulos_trocados_da_o_mesmo(tmp_path: Path) -> None:
    """Um servidor que só fala JSON, com os campos fora de ordem; o texto longo ele recusa."""
    texto = json.dumps([dict(reversed(list(o.items()))) for o in SINKS])
    (tmp_path / "sinks.json").write_text(texto, encoding="utf-8")
    script = tmp_path / "pactl"
    script.write_text(
        "#!/usr/bin/env bash\n"
        f'case "$*" in "--format=json list sinks") cat {tmp_path}/sinks.json;;\n'
        '  *) echo "Estado: ?" ; exit 1;; esac\n', encoding="utf-8")
    script.chmod(0o755)

    def ler(argv: list[str]) -> str | None:
        proc = subprocess.run([str(script), *argv[1:]], capture_output=True, text=True,
                              timeout=5, check=False)
        return proc.stdout if proc.returncode == 0 else None

    hdmi, hap = pds.ler_nos("sinks", ler) or ()
    assert hdmi.nome.endswith("hdmi-stereo") and hap.nome == "hefesto_hap_0000a1"
    assert pds.ler_nos("sources", ler) is None, "servidor que recusou virou lista vazia"


# ---------------------------------------------------------------------------
# A trava: nada em src/ volta a ler o texto longo, e os módulos não têm caminho de distro


_LONGO = re.compile(
    r"""["']pactl["']\s*,\s*["']list["']\s*,\s*["'](sinks|sources|sink-inputs|source-outputs)["']\s*[\]\)]""")
_CAMINHO = re.compile(r"/usr/lib/(x86_64-linux-gnu/)?pipewire-0\.3|/usr/lib64/pipewire")


def _fontes() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if p.name != "porta_do_som.py")


def test_ninguem_em_src_pede_o_texto_longo_do_pactl() -> None:
    quem = [f"{p.relative_to(RAIZ)}:{n}"
            for p in _fontes()
            for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if _LONGO.search(linha)]
    assert not quem, f"leitura do `pactl list` em texto longo: {quem}"


def test_ninguem_em_src_crava_a_pasta_dos_modulos_do_pipewire() -> None:
    quem = [f"{p.relative_to(RAIZ)}:{n}"
            for p in _fontes()
            for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if _CAMINHO.search(linha)]
    assert not quem, f"pasta de módulos escrita à mão: {quem}"


def test_o_curador_do_device_ks_roda_sozinho_e_le_o_json(tmp_path: Path) -> None:
    """O `install.sh` copia `audio_ks_dualsense.py` SOZINHO para `bin/`: sem o pacote ao lado.

    Por isso ele não importa a porta do pacote; lê o mesmo JSON por conta própria.
    Copiado para uma pasta vazia e rodado com `python3 -I`, ele tem de abrir.
    """
    copia = tmp_path / "hefesto-audio-ks"
    copia.write_bytes((SRC / "integrations" / "audio_ks_dualsense.py").read_bytes())
    proc = subprocess.run(
        ["python3", "-I", str(copia), "--help"], capture_output=True, text=True,
        timeout=20, check=False, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "Traceback" not in proc.stderr
