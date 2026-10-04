"""OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01 — nenhum nó de som carrega o endereço.

A causa, medida em 02/10/2026: o nome de cada nó do servidor de som nascia do
endereço do controle em seis lugares, por seis contas (o rabo de seis hex em
quatro, o `uniq` cru em dois), e a marca do aparelho, sem chave, voltava ao
endereço em 27 segundos com a lista dos prefixos da Sony.

A cura: a marca do aparelho é uma HMAC dos doze dígitos com a chave da máquina,
e um dono só monta cada nome com ela. A escolha que ela gravou no nome velho
de um controle passa ao nome novo DAQUELE controle, uma vez.

Endereços da faixa forjada (`02:fe:`), com os octetos 4 e 5 não nulos, para as
réguas de forma da casa terem o que procurar.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.formas_do_endereco import formas_do_endereco
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as eleicao
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import laco_de_audio
from hefesto_dualsense4unix.integrations import monitor_do_microfone as retorno
from hefesto_dualsense4unix.integrations import som_do_controle_na_tv as na_tv

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

#: P1 a P4, cabo ou rádio: o nome é do aparelho, não do transporte.
JOGADORES = ("02:fe:00:12:34:01", "02:fe:00:56:78:02", "02:fe:00:9a:bc:03", "02:fe:00:de:f1:04")

SEIS_HEX = re.compile(r"[0-9a-fA-F]{6,}")


def _o_check_de_radio() -> Any:
    caminho = RAIZ / "scripts" / "check_endereco_de_radio.py"
    spec = importlib.util.spec_from_file_location("check_endereco_de_radio_m15", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["check_endereco_de_radio_m15"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


class _LoopbackDeMentira:
    def __init__(self, argv: list[str]) -> None:
        self.argv = argv

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        return 0


def _nomes_dos_lacos(monkeypatch: pytest.MonkeyPatch, uniq: str) -> list[str]:
    """Os `--name` que os dois laços (o retorno do mic e o som na TV) dão ao nó."""
    nascidos: list[_LoopbackDeMentira] = []

    def _popen(argv: list[str], *_a: Any, **_k: Any) -> _LoopbackDeMentira:
        p = _LoopbackDeMentira(list(argv))
        nascidos.append(p)
        return p

    monkeypatch.setattr(laco_de_audio.subprocess, "Popen", _popen)
    monkeypatch.setattr(laco_de_audio.shutil, "which", lambda _n: "/usr/bin/pw-loopback")
    retorno._LACOS._vivos.clear()
    na_tv._LACOS._vivos.clear()
    try:
        assert retorno.ligar(uniq, canal.nome_do_canal(uniq)), "o retorno do mic recusou"
        assert na_tv.ligar(uniq), "o som na TV recusou"
    finally:
        retorno._LACOS._vivos.clear()
        na_tv._LACOS._vivos.clear()
    return [p.argv[p.argv.index("--name") + 1] for p in nascidos]


def _os_nomes(monkeypatch: pytest.MonkeyPatch, uniq: str) -> dict[str, str]:
    """Todo nome de nó de UM controle, pelos donos — o construtor ao lado do nome."""
    no_bt = bt.NoDualSenseBT(caminho="/dev/hidraw7", uniq=uniq, produto=0x0CE6)
    retorno_do_mic, som_na_tv = _nomes_dos_lacos(monkeypatch, uniq)
    return {
        "alto_falante_bt.nome_do_sink": af.nome_do_sink(uniq),
        "canal_do_microfone.nome_do_canal": canal.nome_do_canal(uniq),
        "dualsense_bt_audio.nome_curto": f"{bt.PREFIXO_SOURCE_PONTE_BT}{no_bt.nome_curto}",
        "alto_falante_bt.rotulo_do_gravador(som)": af.rotulo_do_gravador(uniq=uniq, papel="som"),
        "alto_falante_bt.rotulo_do_gravador(haptica)": af.rotulo_do_gravador(
            uniq=uniq, papel="haptica"
        ),
        "monitor_do_microfone (laço)": retorno_do_mic,
        "som_do_controle_na_tv (laço)": som_na_tv,
        "endpoint_de_haptica.nome_do_endpoint": eh.nome_do_endpoint(uniq),
    }


@pytest.mark.parametrize("uniq", JOGADORES, ids=["P1", "P2", "P3", "P4"])
def test_nenhum_construtor_de_nome_leva_o_endereco(
    monkeypatch: pytest.MonkeyPatch, uniq: str
) -> None:
    """Régua 1. MORDIDA: o rabo hex de volta em qualquer dono → reprova e o nomeia."""
    check = _o_check_de_radio()
    octetos = tuple(uniq.split(":"))
    pedacos = check.pedacos_dos_acusados([octetos])
    formas = {f.lower() for f in formas_do_endereco(octetos)}
    assert formas, "o endereço da régua não tem o que esconder: a régua não mede"
    for dono, nome in _os_nomes(monkeypatch, uniq).items():
        assert nome, f"{dono} não deu nome nenhum"
        assert bt.marca_do_aparelho(uniq) in nome, f"{dono} não leva a marca: {nome!r}"
        assert not SEIS_HEX.search(nome), f"{dono} tem seis hex seguidos: {nome!r}"
        assert not any(f in nome.lower() for f in formas), f"{dono} entrega o endereço"
        assert check.acusa_no(nome) == [], f"{dono}: a régua de forma acusa {nome!r}"
        assert check.acusa_pedaco(nome, pedacos) == [], f"{dono} tem pedaço do endereço"


def test_o_laco_recusa_chave_com_cara_de_endereco(monkeypatch: pytest.MonkeyPatch) -> None:
    """O dono dos laços não deixa um chamador novo pôr o endereço no `--name`."""
    monkeypatch.setattr(laco_de_audio.shutil, "which", lambda _n: "/usr/bin/pw-loopback")
    lacos = laco_de_audio.Lacos("regua")
    assert not lacos.ligar("02fe00123401", captura="x.monitor")
    assert not lacos.ligar("hefesto_123401", captura="x.monitor")


#: O que, num f-string, faz dele um nome de nó do servidor de som.
_CARA_DE_NOME_DE_NO = re.compile(
    r"hefesto_(?:som|mic|dualsense_bt|haptica)_|node\.name=|sink_name=|source_name="
)
_OPCOES_DE_NOME = {"--name", "--client-name"}
_IDENTIDADES_CRUAS = {"uniq", "mac", "endereco"}


def _usa_o_endereco(expr: ast.AST) -> bool:
    for n in ast.walk(expr):
        if isinstance(n, ast.Name) and n.id in _IDENTIDADES_CRUAS:
            return True
        if isinstance(n, ast.Attribute) and n.attr in _IDENTIDADES_CRUAS:
            return True
    return False


def _fstring_com_endereco(no: ast.AST) -> bool:
    return isinstance(no, ast.JoinedStr) and any(
        isinstance(v, ast.FormattedValue) and _usa_o_endereco(v.value) for v in no.values
    )


def nomes_montados_com_o_endereco(arvore: ast.AST) -> list[int]:
    """As linhas onde um nome de nó é montado direto do endereço, sem o dono."""
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if _fstring_com_endereco(no):
            assert isinstance(no, ast.JoinedStr)
            literal = "".join(
                v.value
                for v in no.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
            if _CARA_DE_NOME_DE_NO.search(literal):
                linhas.append(no.lineno)
        if isinstance(no, (ast.List, ast.Tuple)):
            for antes, depois in zip(no.elts, no.elts[1:], strict=False):
                if (
                    isinstance(antes, ast.Constant)
                    and antes.value in _OPCOES_DE_NOME
                    and _fstring_com_endereco(depois)
                ):
                    linhas.append(depois.lineno)
    return linhas


def test_todo_nome_de_no_de_src_passa_pelo_dono() -> None:
    """Régua 2. MORDIDA: um f-string novo com o `uniq` num nome de nó → reprova."""
    achados = []
    for caminho in sorted(SRC.rglob("*.py")):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        relativo = caminho.relative_to(RAIZ)
        achados += [f"{relativo}:{n}" for n in nomes_montados_com_o_endereco(arvore)]
    assert achados == [], f"nome de nó montado do endereço, sem a marca: {achados}"


def test_a_regua_dos_nomes_acha_o_que_procura() -> None:
    """A régua 2 contra as formas que ela tem de pegar, para não medir o vazio."""
    fonte = (
        'a = f"hefesto_som_{uniq[-6:]}"\n'
        'b = ["pw-loopback", "--name", f"hefesto-retorno-{self.uniq}"]\n'
        'c = f"sink_name=x_{mac}"\n'
        'd = f"hefesto_som_{marca}"\n'
    )
    assert nomes_montados_com_o_endereco(ast.parse(fonte)) == [1, 2, 3]


def test_a_marca_tem_a_chave_da_maquina() -> None:
    """Régua 3. A mesma chave dá a mesma marca no cabo e no rádio; outra chave, outra.

    MORDIDA: a marca sem a chave (o SHA-256 cru dos dígitos) → as duas chaves
    dão a mesma marca e reprova.
    """
    chave_a, chave_b = b"\x01" * 32, b"\x02" * 32
    for uniq in JOGADORES:
        hexa = uniq.replace(":", "")
        no_cabo = bt.marca_do_aparelho(uniq, chave=chave_a)
        no_radio = bt.marca_do_aparelho(uniq.upper(), chave=chave_a)
        assert no_cabo == no_radio == bt.marca_do_aparelho(hexa, chave=chave_a)
        assert no_cabo != bt.marca_do_aparelho(uniq, chave=chave_b), (
            "a marca não depende da chave: ela volta ao endereço fora desta máquina"
        )
    marcas = {bt.marca_do_aparelho(u, chave=chave_a) for u in JOGADORES}
    assert len(marcas) == len(JOGADORES), "dois controles com a mesma marca"


def test_a_chave_vem_do_machine_id_e_sem_ele_fica_guardada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A receita de chave por aplicativo; sem `machine-id`, uma chave do estado, 0600."""
    id_da_maquina = tmp_path / "machine-id"
    id_da_maquina.write_text("0123456789abcdef0123456789abcdef\n", encoding="ascii")
    assert bt._machine_id((str(id_da_maquina),)) == bytes.fromhex(
        "0123456789abcdef0123456789abcdef"
    )
    assert bt._machine_id((str(tmp_path / "nao-existe"),)) is None

    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "state_dir", lambda ensure=False: tmp_path)
    primeira = bt._chave_guardada()
    assert primeira == bt._chave_guardada(), "a chave guardada mudou na segunda leitura"
    arquivo = tmp_path / bt._NOME_DA_CHAVE_GUARDADA
    assert arquivo.stat().st_mode & 0o777 == 0o600


@pytest.fixture
def wireplumber() -> Any:
    """Um WirePlumber de mentira: a escolha gravada e o `pactl` que a muda."""

    class _WP:
        def __init__(self) -> None:
            self.gravado: dict[str, str] = {}
            self.pedidos: list[list[str]] = []

        def ler(self, chave: str) -> str | None:
            return self.gravado.get(chave)

        def rodar(self, argv: list[str]) -> tuple[int, str]:
            self.pedidos.append(argv)
            return 0, ""

    eleicao._ESCOLHAS_JA_PASSADAS.clear()
    yield _WP()
    eleicao._ESCOLHAS_JA_PASSADAS.clear()


def test_a_escolha_gravada_passa_ao_nome_novo_do_mesmo_controle(wireplumber: Any) -> None:
    """Régua 4. A fonte gravada no nome velho do P2: o P1 não a toma; o P2 a passa.

    MORDIDA: sem a passagem, a escolha dela fica num nome que não existe mais e
    o WirePlumber dá a fonte padrão a outro nó.
    """
    p1, p2 = JOGADORES[0], JOGADORES[1]
    nome_velho_do_p2 = f"{canal.PREFIXO_CANAL}{p2[-8:].replace(':', '')}"
    wireplumber.gravado[eleicao.CHAVE_DA_FONTE_GRAVADA] = nome_velho_do_p2

    def _nasce(uniq: str) -> bool:
        return eleicao.passar_a_escolha_gravada_ao_nome_novo(
            uniq,
            canal.nome_do_canal(uniq),
            prefixo=canal.PREFIXO_CANAL,
            ler=wireplumber.ler,
            rodar=wireplumber.rodar,
        )

    assert not _nasce(p1), "o P1 tomou a escolha que era do P2"
    assert wireplumber.pedidos == []
    assert _nasce(p2)
    assert wireplumber.pedidos == [["pactl", "set-default-source", canal.nome_do_canal(p2)]]
    assert not _nasce(p2), "a passagem é uma vez só"
    assert len(wireplumber.pedidos) == 1


def test_a_saida_gravada_passa_e_a_escolha_que_nao_e_de_controle_fica(wireplumber: Any) -> None:
    """A saída gravada num alto-falante de controle passa; a webcam dela não se toca."""
    p3 = JOGADORES[2]
    gravado = wireplumber.gravado
    gravado[eleicao.CHAVE_DA_SAIDA_GRAVADA] = f"{af.PREFIXO_SINK_DO_SOM}{p3[-8:].replace(':', '')}"
    gravado[eleicao.CHAVE_DA_FONTE_GRAVADA] = "alsa_input.usb-Webcam_C920-02.analog-stereo"
    assert eleicao.passar_a_escolha_gravada_ao_nome_novo(
        p3, af.nome_do_sink(p3), prefixo=af.PREFIXO_SINK_DO_SOM, saida=True,
        ler=wireplumber.ler, rodar=wireplumber.rodar,
    )
    assert not eleicao.passar_a_escolha_gravada_ao_nome_novo(
        p3, canal.nome_do_canal(p3), prefixo=canal.PREFIXO_CANAL,
        ler=wireplumber.ler, rodar=wireplumber.rodar,
    )
    assert wireplumber.pedidos == [["pactl", "set-default-sink", af.nome_do_sink(p3)]]


#: O estado do WirePlumber de um lar de mentira: as linhas nossas e as dela.
_DEFAULT_NODES = (
    "[default-nodes]\n"
    "default.configured.audio.sink=alsa_output.pci-0000_00_1f.3.hdmi-stereo\n"
    "default.configured.audio.sink.0=hefesto_som_000012\n"
    "default.configured.audio.sink.1=alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller-00.HiFi__Speaker__sink\n"
    "default.configured.audio.sink.3=alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller_HEFESTOLUGAR1-00.HiFi__Speaker__sink\n"
    "default.configured.audio.source=hefesto_mic_APARELHOKUKTZP\n"
    "default.configured.audio.source.0=alsa_input.usb-Webcam_C920-02.analog-stereo\n"
)
_STREAM_PROPERTIES = (
    "[stream-properties]\n"
    "Audio/Sink:node.name:hefesto_som_000012={\"volume\":1.0}\n"
    "Audio/Sink:node.name:alsa_output.usb-Sony_Interactive_Entertainment_DualSense_"
    "Wireless_Controller-00.HiFi__Speaker__sink={\"volume\":0.5}\n"
    "Input/Audio:application.id:br.dev.hefesto.luz_do_mic={\"mute\":false}\n"
    "Input/Audio:application.name:Firefox={\"volume\":0.8}\n"
    "Input/Audio:media.name:hefesto-retorno-do-mic-APARELHOKUKTZP\\sinput={\"mute\":false}\n"
    "Output/Audio:media.role:Notification={\"volume\":0.3}\n"
)
#: O que é dela, e tem de ficar byte a byte.
_DELA = {
    "default-nodes": [
        "[default-nodes]",
        "default.configured.audio.sink=alsa_output.pci-0000_00_1f.3.hdmi-stereo",
        "default.configured.audio.sink.1=alsa_output.usb-Sony_Interactive_Entertainment_"
        "DualSense_Wireless_Controller-00.HiFi__Speaker__sink",
        "default.configured.audio.source.0=alsa_input.usb-Webcam_C920-02.analog-stereo",
    ],
    "stream-properties": [
        "[stream-properties]",
        "Audio/Sink:node.name:alsa_output.usb-Sony_Interactive_Entertainment_DualSense_"
        "Wireless_Controller-00.HiFi__Speaker__sink={\"volume\":0.5}",
        "Input/Audio:application.name:Firefox={\"volume\":0.8}",
        "Output/Audio:media.role:Notification={\"volume\":0.3}",
    ],
}


def _estado_do_wireplumber(pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "default-nodes").write_text(_DEFAULT_NODES, encoding="utf-8")
    (pasta / "stream-properties").write_text(_STREAM_PROPERTIES, encoding="utf-8")
    return pasta


def test_o_estado_do_wireplumber_perde_so_as_chaves_nossas(tmp_path: Path) -> None:
    """Régua 5, a metade do dono. MORDIDA: «nosso» por «contém DualSense» → as dela somem."""
    from hefesto_dualsense4unix.utils import memoria_dos_controles as m

    pasta = _estado_do_wireplumber(tmp_path / "wireplumber")
    achadas = m.chaves_nossas_do_wireplumber(pasta)
    assert {k: len(v) for k, v in achadas.items()} == {
        "default-nodes": 3, "stream-properties": 3,
    }
    assert m.tirar_as_chaves_nossas_do_wireplumber(pasta) == 6
    for nome, linhas in _DELA.items():
        assert (pasta / nome).read_text(encoding="utf-8").splitlines() == linhas, nome
    assert m.chaves_nossas_do_wireplumber(pasta) == {}
    assert m.tirar_as_chaves_nossas_do_wireplumber(pasta) == 0


def test_o_limpa_lista_as_chaves_nossas_do_wireplumber(tmp_path: Path) -> None:
    """O «limpa?» enxerga o rastro no estado do WirePlumber, e cala quando ele sai."""
    from dataclasses import replace

    from hefesto_dualsense4unix.utils import memoria_dos_controles as m

    raizes = m.Raizes(
        lar=tmp_path, config=tmp_path / ".config", estado=tmp_path / ".local/state",
        dados=tmp_path / ".local/share", cache=tmp_path / ".cache",
        execucao=tmp_path / "run", bluez=tmp_path / "bluez", varlib=tmp_path / "varlib",
        guardado_do_root=tmp_path / "guardado", sistema=tmp_path / "sistema",
    )
    pasta = _estado_do_wireplumber(raizes.estado / "wireplumber")
    rastros = [r for r in m.conferir_a_casa(raizes) if "WirePlumber" in r.o_que]
    assert sorted(Path(r.onde).name for r in rastros) == ["default-nodes", "stream-properties"]
    m.tirar_as_chaves_nossas_do_wireplumber(pasta)
    assert [r for r in m.conferir_a_casa(replace(raizes)) if "WirePlumber" in r.o_que] == []


def _o_passo_do_uninstall() -> str:
    """O bloco do `uninstall.sh` que tira as chaves — só ele, nunca o roteiro inteiro."""
    texto = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
    inicio = texto.index("# OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01")
    fim = texto.index("# DROPIN-AMBIGUO-01", inicio)
    return texto[inicio:fim]


def test_o_uninstall_para_o_wireplumber_antes_de_reescrever(tmp_path: Path) -> None:
    """Régua 5, a metade do roteiro: o passo do uninstall num lar de mentira.

    O `systemctl` é um dublê que anota a chamada e o que o estado tinha naquela
    hora: no `stop` as nossas ainda estão lá (a escrita veio depois), no
    `start` já saíram, e as dela ficam byte a byte.
    """
    import subprocess

    lar = tmp_path / "lar"
    pasta = _estado_do_wireplumber(lar / ".local/state/wireplumber")
    dubles = tmp_path / "bin"
    dubles.mkdir()
    diario = tmp_path / "systemctl.txt"
    systemctl = dubles / "systemctl"
    systemctl.write_text(
        "#!/bin/sh\n"
        f'printf "%s %s\\n" "$*" "$(grep -c hefesto_ {pasta}/default-nodes)" >> {diario}\n',
        encoding="utf-8",
    )
    systemctl.chmod(0o755)
    roteiro = 'log() { printf "%s\\n" "$*"; }\n' + _o_passo_do_uninstall()
    ambiente = {
        "PATH": f"{dubles}:/usr/bin:/bin",
        "HOME": str(lar),
        "XDG_STATE_HOME": str(lar / ".local/state"),
        "ROOT_DIR": str(RAIZ),
        "LC_ALL": "C",
    }
    feito = subprocess.run(
        ["bash", "-c", roteiro], env=ambiente, capture_output=True, text=True, timeout=60
    )
    assert feito.returncode == 0, feito.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines()
    assert chamadas == ["--user stop wireplumber 2", "--user start wireplumber 0"], chamadas
    for nome, linhas in _DELA.items():
        assert (pasta / nome).read_text(encoding="utf-8").splitlines() == linhas, nome
