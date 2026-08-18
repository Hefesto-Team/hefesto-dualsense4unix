"""PILHA-TRUNCADA-01 — a limpeza do state levava o histórico inteiro junto.

MEDIDO em 06/08/2026, no WirePlumber 0.5.12 instalado nesta máquina.

`remove_configured_dualsense` existia para tirar UMA entrada do state do
WirePlumber (a fonte padrão persistida que aponta para o mic do controle), e o
comentário dela prometia *"preserva o resto do state"*. O que estava escrito
era::

    sed -i.bak '/^default\\.configured\\.audio\\.source=.*[Dd]ual[Ss]ense/Id'

O `=` logo depois de `source` faz o padrão casar a chave-BASE e NÃO casar
`...source.0=` / `...source.1=`. E o histórico não é um conjunto de chaves
independentes: é uma PILHA CONTÍGUA, lida assim em
``/usr/share/wireplumber/scripts/default-nodes/state-default-nodes.lua``
(``collectStored``, linhas 141-155)::

    key = key_base
    repeat
      local v = state_table [key]
      table.insert (stored, v)
      key = key_base .. "." .. tostring (index)
      index = index + 1
    until v == nil                      -- PARA no primeiro buraco

Daí os DOIS defeitos da mesma linha, os dois presentes no state real dela:

- base NÃO é o DualSense (o caso de hoje) -> o `sed` não casa nada e a função é
  um NO-OP: as entradas do DualSense que ela existe para tirar ficam onde
  estavam;
- base É o DualSense -> casa, apaga a base, e a leitura para na primeira volta:
  `.0` e `.1` ficam inalcançáveis e o histórico INTEIRO some.

Nenhum dos dois aparecia no log: os dois terminavam devolvendo 0.

GRAU: MEDIDO no código dos dois lados. O efeito em produção é SUSPEITA COM
MECANISMO — a função edita o arquivo com o WirePlumber VIVO, e o próprio script
documenta (em `unmute_dualsense_routes`) que ele regrava o estado ao sair. Essa
ordem NÃO foi mexida: virou item de sprint.

Nenhum teste deste arquivo toca o state de verdade — tudo em `tmp_path`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "fix_wireplumber_default_source.sh"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """HOME de mentira.

    O script roda com `set -u` e monta `STATE_FILE` a partir do HOME já no
    carregamento. Apontá-lo para o HOME de verdade seria pedir para um teste
    olhar o state de áudio de quem roda a suíte — e o canário de FS desta casa
    existe exatamente para isso não acontecer. Nada é escrito aqui: só o
    `source` precisa da variável existir.
    """
    h = tmp_path / "home"
    h.mkdir()
    return h


DS_MIC = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.iec958-stereo"
)
DS_SINK = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
ONBOARD = "alsa_input.pci-0000_0c_00.4.analog-stereo"
WEBCAM = "alsa_input.usb-046d_HD_Pro_Webcam_C920-02.analog-stereo"


def _pilha(state: str, home: Path) -> str:
    """Executa a função shell REAL, via source (o dispatch não roda)."""
    res = subprocess.run(
        ["bash", "-c", 'set --; source "$SCRIPT"; _pilha_sem_dualsense'],
        input=state,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={
            "SCRIPT": str(SCRIPT),
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "HOME": str(home),
        },
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


def _fontes(saida: str) -> list[str]:
    """A pilha de SOURCE como o `collectStored` do WirePlumber a leria."""
    mapa = dict(
        linha.split("=", 1) for linha in saida.splitlines() if "=" in linha
    )
    base = "default.configured.audio.source"
    lidas: list[str] = []
    chave = base
    i = 0
    while chave in mapa:
        lidas.append(mapa[chave])
        chave = f"{base}.{i}"
        i += 1
    return lidas


#: O state REAL desta máquina em 06/08/2026 (`~/.local/state/wireplumber/
#: default-nodes`), copiado sem alteração. A `.1` é a assinatura de "um monitor
#: já foi fonte padrão aqui": a camada pulse resolve `<sink>.monitor` para o nó
#: SINK, e o WirePlumber grava o nome do nó.
STATE_REAL = f"""\
[default-nodes]
default.configured.audio.sink=alsa_output.pci-0000_0a_00.1.hdmi-stereo
default.configured.audio.sink.0={DS_SINK}
default.configured.audio.sink.1=alsa_output.pci-0000_0c_00.4.analog-stereo
default.configured.audio.source={ONBOARD}
default.configured.audio.source.0={DS_MIC}
default.configured.audio.source.1={DS_SINK}
"""

#: O outro caso: a base É o DualSense. É aqui que o `sed` antigo destruía.
STATE_BASE_E_O_CONTROLE = f"""\
[default-nodes]
default.configured.audio.source={DS_MIC}
default.configured.audio.source.0={ONBOARD}
default.configured.audio.source.1={WEBCAM}
"""


class TestOHistoricoSobrevive:
    def test_base_e_o_controle_o_resto_da_pilha_sobrevive(self, home: Path) -> None:
        """O defeito que destruía: apagar a base tornava `.0` e `.1` órfãs."""
        lidas = _fontes(_pilha(STATE_BASE_E_O_CONTROLE, home))
        assert lidas == [ONBOARD, WEBCAM], (
            "o histórico de preferência de microfone dela foi truncado: o "
            f"WirePlumber leria {lidas}"
        )

    def test_a_pilha_fica_contigua(self, home: Path) -> None:
        """Sem renumerar, sobra um buraco e o `collectStored` para nele."""
        saida = _pilha(STATE_BASE_E_O_CONTROLE, home)
        assert "default.configured.audio.source=" + ONBOARD in saida, saida
        assert "default.configured.audio.source.0=" + WEBCAM in saida, saida
        assert "default.configured.audio.source.1=" not in saida, (
            "sobrou um degrau a mais na pilha:\n" + saida
        )

    def test_no_estado_real_as_duas_entradas_do_controle_saem(self, home: Path) -> None:
        """O outro lado do defeito: antes, aqui, a função não fazia NADA."""
        lidas = _fontes(_pilha(STATE_REAL, home))
        assert lidas == [ONBOARD], lidas
        assert not any("DualSense" in v for v in lidas), lidas

    def test_a_pilha_de_sink_nao_e_tocada(self, home: Path) -> None:
        """`source` é o alvo; o histórico de SAÍDA é escolha dela, não nossa.

        Inclusive a entrada do DualSense na pilha de sink: quem desliga o mic
        não está pedindo para esquecer o alto-falante do controle.
        """
        saida = _pilha(STATE_REAL, home)
        for linha in STATE_REAL.splitlines():
            if ".audio.sink" in linha:
                assert linha in saida, f"linha de sink perdida: {linha}"

    def test_o_cabecalho_e_as_outras_chaves_ficam(self, home: Path) -> None:
        assert "[default-nodes]" in _pilha(STATE_REAL, home)

    def test_sem_dualsense_nenhum_o_state_sai_identico(self, home: Path) -> None:
        """Idempotência: o que não tem o defeito não pode ser reescrito."""
        state = (
            "[default-nodes]\n"
            f"default.configured.audio.source={ONBOARD}\n"
            f"default.configured.audio.source.0={WEBCAM}\n"
        )
        assert _pilha(state, home) == state


class TestOCasamentoPegaAPilhaInteira:
    def test_o_grep_da_funcao_ve_as_chaves_indexadas(self) -> None:
        """O `grep` guarda o portão: se ele não casar `.0`, nada roda.

        Era o buraco literal do padrão antigo — `source=` não casa `source.0=`,
        e a função saía sem fazer nada com o defeito na tela.
        """
        texto = SCRIPT.read_text(encoding="utf-8")
        i = texto.index("remove_configured_dualsense() {")
        corpo = texto[i : texto.index("\n}\n", i)]
        assert "audio\\.source(\\.[0-9]+)?=" in corpo, (
            "o casamento voltou a ignorar as chaves indexadas da pilha:\n" + corpo
        )
