"""N-IGUAL-A-UM-01 — o prefixo vai no adaptador certo, e são TRÊS.

Sprint: `docs/process/sprints/2026-08-22-N-IGUAL-A-UM-01-*.md`, entrega E2.

O DEFEITO, MEDIDO em 22/08/2026 na bancada de três adaptadores
-----------------------------------------------------------------

`scripts/bt_active_mode.sh` escolhia UM adaptador — o primeiro do glob do sysfs,
com `return 0` na primeira volta — e prefixava `Nintendo` só nele. Na mesa dela
o Pro Controller vive no segundo, e o prefixo ficava no primeiro, que não
hospeda Nintendo nenhum::

    hci0  D8:44:89:...  alias "Nintendo MeowSystem"  ->  1 DualSense, zero Pro
    hci1  AC:A7:F1:...  alias "MeowSystem #2"        ->  1 DualSense + o PRO
    hci2  AC:A7:F1:...  alias "MeowSystem #3"        ->  2 DualSense

Com UM adaptador a escolha sempre acertou, e é por isso que ninguém viu. Com
três, acerta uma vez em três — e a vigia reexecuta o script a cada 2 min, então
a escolha errada se reafirma sozinha, para sempre.

AS QUATRO MORDIDAS
-------------------

1. devolva o `return 0` da primeira volta de `_adaptadores` (ou troque o laço
   da seção 1 por `${ADAPTADORES[0]}`) e
   `test_so_o_adaptador_que_hospeda_o_pro_recebe_o_prefixo` reprova nas duas
   pontas: o prefixo aparece no `hci0`, que não devia, e some do `hci1`, que
   devia;
2. apague a segunda fonte de `_hci_com_nintendo` (a árvore de bonds) e
   `test_o_bond_em_disco_basta_com_o_bluetoothd_ainda_povoando` reprova — é o
   caso do `ExecStartPost`, em que o `bluetoothd` ainda não publicou os objetos
   de device e o Pro AINDA NÃO CONECTOU. MEDIDO em 22/08/2026: nesse instante o
   sysfs vivo do `apelido_do_dongle` devolve conjunto VAZIO, porque ele só
   enxerga controle conectado;
3. tire o laço do SNIFF default (volte ao `${HCI}` escalar) e
   `test_o_sniff_default_volta_em_todos_os_adaptadores` reprova nomeando os
   adaptadores que ficaram de fora;
4. troque uma faixa de `OUIS_LINHAGEM` no shell e
   `test_a_regra_da_linhagem_e_a_mesma_do_dono_dela` reprova — a regra tem UM
   dono (`core/linhagem_nintendo.py`) e esta cópia em shell é PINADA nele.

POR QUE UMA CÓPIA EM SHELL, E NÃO UMA CHAMADA AO MÓDULO
--------------------------------------------------------

O script roda no `ExecStartPost` do `bluetooth.service`, como root, num instante
em que o venv da casa pode não existir. Importar Python ali é depender de coisa
que pode não estar de pé exatamente quando o Pro conecta. A cópia é o preço; o
portão de paridade abaixo é o que a impede de virar uma segunda verdade.

NADA AQUI ENCOSTA NO BARRAMENTO DELA
-------------------------------------

Bancada inteira de mentira: `HEFESTO_SYS_BLUETOOTH` e `HEFESTO_BT_LIB` desviam
as duas raízes, e `busctl`, `hciconfig`, `hcitool` e `id` são dublês num `PATH`
montado à mão. Nenhum adaptador vivo é lido, e nenhum é renomeado.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.linhagem_nintendo import (
    NOMES_LINHAGEM,
    OUIS_CLONE,
    OUIS_NINTENDO_VISTAS,
    com_dois_pontos,
)
from hefesto_dualsense4unix.integrations.apelido_do_dongle import (
    PREFIXO_NINTENDO,
    TETO_DE_BYTES,
)

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "bt_active_mode.sh"
SCRIPTS_BT = [*sorted(RAIZ.glob("scripts/bt_*.sh")), RAIZ / "scripts" / "doctor.sh"]

#: A OUI do Pro sai do PRODUTO, nunca escrita aqui — mesma guarda de
#: `test_a_oui_separa_o_clone_do_genuino.py`: forma de MAC em `tests/` só nas
#: faixas forjadas, e OUI real não é faixa forjada.
_OUI_PRO = sorted(com_dois_pontos(OUIS_NINTENDO_VISTAS))[0]
#: Máscara da casa (octetos 4 e 5 zerados) sobre a OUI do produto.
MAC_PRO = f"{_OUI_PRO}:00:00:53".upper()

#: Faixa sintética da casa para tudo o que não precisa ser real.
ADAPTADORES = {
    "hci0": "AA:BB:CC:00:00:01",
    "hci1": "AA:BB:CC:00:00:02",
    "hci2": "AA:BB:CC:00:00:03",
}
DUALSENSE = {
    "hci0": ["AA:BB:CC:00:00:11"],
    "hci1": ["AA:BB:CC:00:00:12"],
    "hci2": ["AA:BB:CC:00:00:13", "AA:BB:CC:00:00:14"],
}
#: O Pro mora no SEGUNDO adaptador — é a bancada dela, e é o caso que o
#: `head -1` errava.
HOSPEDEIRO_DO_PRO = "hci1"

NOME_DUALSENSE = "DualSense Wireless Controller"
NOME_PRO = "Pro Controller"

#: Nomes dela, com acento de propósito: o alias trafega por `busctl`, `sed` e
#: `printf`, e um UTF-8 mutilado no caminho é um alias que o BlueZ recusa.
ALIAS_INICIAL = {"hci0": "Sala", "hci1": "Sofá", "hci2": "Quarto"}


# ---------------------------------------------------------------------------
# A bancada de mentira
# ---------------------------------------------------------------------------
def _executavel(caminho: Path, corpo: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return caminho


def _mapa(nome: str, pares: dict[str, str]) -> str:
    corpo = " ".join(f'["{k}"]="{v}"' for k, v in pares.items())
    return f"declare -A {nome}=({corpo})\n"


class Bancada:
    """Três adaptadores, cinco controles, e um registro do que foi escrito."""

    def __init__(
        self,
        tmp: Path,
        *,
        alias: dict[str, str] | None = None,
        com_pro: bool = True,
        dbus_ve_devices: bool = True,
        bond_tem_pro: bool = True,
        sniff_no_default: bool = False,
    ) -> None:
        self.tmp = tmp
        self.alias = dict(alias or ALIAS_INICIAL)
        self.fakes = tmp / "fakes"
        self.escritas = tmp / "set-property.tsv"
        self.lp = tmp / "link-policy.tsv"
        self.log = tmp / "diario.log"
        self.sys_bt = tmp / "sys-class-bluetooth"
        self.lib = tmp / "var-lib-bluetooth"

        # sysfs: os três adaptadores + a entrada de CONEXÃO, que o kernel cria
        # como "hci1:1" e que o filtro `^hci[0-9]+$` tem de descartar.
        for nome in [*ADAPTADORES, "hci1:1"]:
            (self.sys_bt / nome).mkdir(parents=True)

        # árvore de bonds em disco
        for hci, endereco in ADAPTADORES.items():
            for mac in DUALSENSE[hci]:
                self._bond(endereco, mac, NOME_DUALSENSE)
            if hci == HOSPEDEIRO_DO_PRO and com_pro and bond_tem_pro:
                self._bond(endereco, MAC_PRO, NOME_PRO)

        caminhos: list[str] = [f"/org/bluez/{h}" for h in ADAPTADORES]
        nomes: dict[str, str] = {}
        if dbus_ve_devices:
            for hci in ADAPTADORES:
                macs = list(DUALSENSE[hci])
                if hci == HOSPEDEIRO_DO_PRO and com_pro:
                    macs.append(MAC_PRO)
                for mac in macs:
                    caminho = f"/org/bluez/{hci}/dev_" + mac.replace(":", "_")
                    caminhos.append(caminho)
                    nomes[caminho] = NOME_PRO if mac == MAC_PRO else NOME_DUALSENSE

        _executavel(self.fakes / "id", "echo 0\n")
        _executavel(
            self.fakes / "busctl",
            _mapa("ALIAS", {f"/org/bluez/{h}": a for h, a in self.alias.items()})
            + _mapa("ENDERECO", {f"/org/bluez/{h}": e for h, e in ADAPTADORES.items()})
            + _mapa("NOME", nomes)
            + f"""
case "$1" in
  tree) printf '%s\\n' {" ".join(f"'{c}'" for c in caminhos)} ;;
  get-property)
    case "$4" in
      org.bluez.Adapter1)
        case "$5" in
          Alias)   printf 's "%s"\\n' "${{ALIAS[$3]:-}}" ;;
          Address) printf 's "%s"\\n' "${{ENDERECO[$3]:-}}" ;;
        esac ;;
      org.bluez.Device1)
        case "$5" in
          Alias)     printf 's "%s"\\n' "${{NOME[$3]:-}}" ;;
          Connected) echo 'b false' ;;
        esac ;;
    esac ;;
  set-property) printf '%s\\t%s\\n' "$3" "$7" >> '{self.escritas}' ;;
esac
exit 0
""",
        )
        politica = "RSWITCH HOLD SNIFF PARK" if sniff_no_default else "RSWITCH HOLD PARK"
        _executavel(
            self.fakes / "hciconfig",
            f"""
if [[ "${{2:-}}" == "lp" && -z "${{3:-}}" ]]; then
    echo 'Link policy: {politica}'
    exit 0
fi
[[ "${{2:-}}" == "lp" ]] && printf '%s\\t%s\\n' "$1" "$3" >> '{self.lp}'
exit 0
""",
        )
        _executavel(self.fakes / "hcitool", "exit 0\n")

    def _bond(self, adaptador: str, controle: str, nome: str) -> None:
        pasta = self.lib / adaptador / controle
        pasta.mkdir(parents=True)
        (pasta / "info").write_text(
            f"[General]\nName={nome}\n\n[LinkKey]\nKey=00\n", encoding="utf-8"
        )

    def rodar(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT), "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={
                "PATH": ":".join([str(self.fakes), "/usr/bin", "/bin"]),
                "HOME": str(self.tmp),
                "LANG": os.environ.get("LANG", "pt_BR.UTF-8"),
                "HEFESTO_SYS_BLUETOOTH": str(self.sys_bt),
                "HEFESTO_BT_LIB": str(self.lib),
                "HEFESTO_BT_LOG_DEST": str(self.log),
            },
        )

    def aliases_escritos(self) -> dict[str, str]:
        """`hciN -> alias novo`, do que o `set-property` realmente recebeu."""
        if not self.escritas.exists():
            return {}
        fora: dict[str, str] = {}
        for linha in self.escritas.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            caminho, _, valor = linha.partition("\t")
            fora[caminho.rsplit("/", 1)[-1]] = valor
        return fora

    def sniff_devolvido_em(self) -> set[str]:
        if not self.lp.exists():
            return set()
        return {
            linha.split("\t")[0]
            for linha in self.lp.read_text(encoding="utf-8").splitlines()
            if linha.strip()
        }


# ---------------------------------------------------------------------------
# E2 — o prefixo vai só onde a linhagem mora, e vai em TODOS onde ela mora
# ---------------------------------------------------------------------------
def test_so_o_adaptador_que_hospeda_o_pro_recebe_o_prefixo(tmp_path: Path) -> None:
    """A mordida principal: um acerto em três virava zero acerto.

    As duas asserções são as duas pontas do mesmo defeito, e o `head -1` de
    ontem reprova nas duas: escreve onde não devia, e não escreve onde devia.
    """
    banca = Bancada(tmp_path)
    banca.rodar()
    escritos = banca.aliases_escritos()

    assert escritos.get(HOSPEDEIRO_DO_PRO) == f"{PREFIXO_NINTENDO} Sofá", (
        "o adaptador que hospeda o Pro tem de sair com o prefixo — sem ele o "
        f"controle cai sob carga. Escritas: {escritos}"
    )
    intrusos = {h: v for h, v in escritos.items() if h != HOSPEDEIRO_DO_PRO}
    assert not intrusos, (
        "prefixo escrito em adaptador que não hospeda Nintendo nenhum: "
        f"{intrusos}. O `apelido_do_dongle` nunca subtrai, então a palavra vira "
        "parte permanente do nome que ela escreveu."
    )


def test_o_bond_em_disco_basta_com_o_bluetoothd_ainda_povoando(tmp_path: Path) -> None:
    """A fonte que responde ANTES do link — e é a única que responde ali.

    No `ExecStartPost` o `bluetoothd` ainda não publicou os objetos de device, e
    o Pro nem conectou. O sysfs vivo do `apelido_do_dongle` devolve vazio nesse
    instante (medido em 22/08/2026: sem o Pro ligado, nenhum nó `hidraw` dele
    existe). Só o bond em disco sabe onde ele mora.
    """
    banca = Bancada(tmp_path, dbus_ve_devices=False)
    banca.rodar()
    assert banca.aliases_escritos() == {
        HOSPEDEIRO_DO_PRO: f"{PREFIXO_NINTENDO} Sofá"
    }, banca.aliases_escritos()


def test_com_o_pro_fora_da_mesa_ninguem_e_prefixado(tmp_path: Path) -> None:
    """O controle negativo. Sem esta linha o teste acima passaria com um
    script que prefixa todo mundo — que é a outra forma de errar."""
    banca = Bancada(tmp_path, com_pro=False)
    banca.rodar()
    assert banca.aliases_escritos() == {}, banca.aliases_escritos()


def test_o_prefixo_nao_cresce_a_cada_tique_da_vigia(tmp_path: Path) -> None:
    """A vigia roda a cada 2 min: sem idempotência o nome cresceria sem teto."""
    ja_costurado = dict(ALIAS_INICIAL)
    ja_costurado[HOSPEDEIRO_DO_PRO] = f"{PREFIXO_NINTENDO} Sofá"
    banca = Bancada(tmp_path, alias=ja_costurado)
    banca.rodar()
    assert banca.aliases_escritos() == {}, (
        "alias já protegido foi reescrito — é assim que 'Nintendo Nintendo "
        f"Sofá' nasce: {banca.aliases_escritos()}"
    )


def test_bond_de_dongle_que_saiu_da_mesa_nao_derruba_o_resto(tmp_path: Path) -> None:
    """`/var/lib/bluetooth` guarda o bond de dongle que já foi desplugado.

    O diretório fica lá para sempre — é assim que o bond sobrevive a trocar o
    dongle de porta. O endereço dele não casa com adaptador nenhum de hoje, e
    isso não pode nem inventar um alvo nem interromper a varredura antes do
    adaptador seguinte.
    """
    banca = Bancada(tmp_path, dbus_ve_devices=False)
    fantasma = banca.lib / "AA:BB:CC:00:00:99" / MAC_PRO
    fantasma.mkdir(parents=True)
    (fantasma / "info").write_text(
        f"[General]\nName={NOME_PRO}\n", encoding="utf-8"
    )
    banca.rodar()
    assert banca.aliases_escritos() == {
        HOSPEDEIRO_DO_PRO: f"{PREFIXO_NINTENDO} Sofá"
    }, banca.aliases_escritos()


def test_nome_que_nao_cabe_com_o_prefixo_e_recusado_com_motivo(tmp_path: Path) -> None:
    """Acima do teto o BlueZ recusa a chamada inteira — e calar é o pior.

    O shell não tem como cortar UTF-8 em fronteira de caractere sem depender de
    ferramenta que pode não existir no boot, então o script não corta: ele diz
    que não coube, e diz em qual adaptador.
    """
    comprido = dict(ALIAS_INICIAL)
    comprido[HOSPEDEIRO_DO_PRO] = "á" * ((TETO_DE_BYTES // 2) + 1)
    banca = Bancada(tmp_path, alias=comprido)
    banca.rodar()
    diario = banca.log.read_text(encoding="utf-8") if banca.log.exists() else ""
    assert banca.aliases_escritos() == {}, banca.aliases_escritos()
    assert f"NÃO prefixei o alias de {HOSPEDEIRO_DO_PRO}" in diario, diario


def test_o_sniff_default_volta_em_todos_os_adaptadores(tmp_path: Path) -> None:
    """A operação (2) tem escopo DIFERENTE da (1), e a razão está no script.

    Devolver o default do kernel não escolhe favorecido: o 8BitDo pareia em
    qualquer adaptador e a probe dele morre em qualquer um que esteja sem
    SNIFF. E a entrada de conexão `hci1:1` do sysfs não é adaptador — se ela
    aparecer aqui, o filtro `^hci[0-9]+$` caiu.
    """
    banca = Bancada(tmp_path)
    banca.rodar()
    assert banca.sniff_devolvido_em() == set(ADAPTADORES), banca.sniff_devolvido_em()


def test_o_sniff_default_nao_e_mexido_em_quem_ja_o_tem(tmp_path: Path) -> None:
    """Régua do teste acima: com SNIFF já no default, o registro fica VAZIO.

    Sem este controle, um dublê de `hciconfig` que gravasse sempre faria o
    teste anterior passar por preguiça do instrumento.
    """
    banca = Bancada(tmp_path, sniff_no_default=True)
    banca.rodar()
    assert banca.sniff_devolvido_em() == set(), banca.sniff_devolvido_em()


def test_o_diario_nomeia_o_adaptador_que_recebeu_o_prefixo(tmp_path: Path) -> None:
    """`alias do adaptador -> 'X'` falava pelo rádio inteiro (lição A5)."""
    banca = Bancada(tmp_path)
    banca.rodar()
    diario = banca.log.read_text(encoding="utf-8") if banca.log.exists() else ""
    assert f"alias do adaptador {HOSPEDEIRO_DO_PRO} ->" in diario, diario


# ---------------------------------------------------------------------------
# UM DONO SÓ — a regra é do `core/linhagem_nintendo`; o shell é cópia PINADA
# ---------------------------------------------------------------------------
def _lista_do_shell(nome: str) -> tuple[str, ...]:
    texto = SCRIPT.read_text(encoding="utf-8")
    achado = re.search(rf"^{nome}=\((.*)\)$", texto, re.M)
    assert achado, (
        f"o `bt_active_mode.sh` não declara mais `{nome}` — sem ela o portão de "
        "paridade abaixo não mede nada"
    )
    return tuple(re.findall(r'"([^"]*)"', achado.group(1)))


def test_a_regra_da_linhagem_e_a_mesma_do_dono_dela() -> None:
    """Dois escritores do mesmo alias, e por isso UMA regra só.

    `integrations/apelido_do_dongle.py` escreve o alias pelo lado da GUI; este
    script escreve pelo lado do root. Se as duas listas divergirem, um desfaz o
    outro a cada tique da vigia — que é exatamente o ciclo que a sprint mediu.
    """
    esperadas = com_dois_pontos(OUIS_NINTENDO_VISTAS | OUIS_CLONE)
    assert set(_lista_do_shell("OUIS_LINHAGEM")) == esperadas, (
        "as faixas do shell se separaram de `core/linhagem_nintendo`: "
        f"{sorted(_lista_do_shell('OUIS_LINHAGEM'))} contra {sorted(esperadas)}"
    )
    assert _lista_do_shell("NOMES_LINHAGEM") == NOMES_LINHAGEM, (
        f"{_lista_do_shell('NOMES_LINHAGEM')} contra {NOMES_LINHAGEM}"
    )


def test_o_prefixo_e_o_teto_batem_com_o_outro_escritor() -> None:
    texto = SCRIPT.read_text(encoding="utf-8")
    assert f'"{PREFIXO_NINTENDO} ${{ALIAS_ATUAL}}"' in texto, (
        "a caixa do prefixo tem de ser a mesma dos dois lados, ou cada escritor "
        "re-prefixa o que o outro escreveu"
    )
    achado = re.search(r"^TETO_DE_BYTES=(\d+)$", texto, re.M)
    assert achado, "o script não declara mais `TETO_DE_BYTES`"
    assert int(achado.group(1)) == TETO_DE_BYTES


def test_a_regua_da_paridade_enxerga_o_que_promete() -> None:
    """Contagem independente: as listas lidas não podem estar vazias.

    Duas listas vazias comparadas com duas listas vazias dão verde e não medem
    nada — é o "portão que não mede o que promete" de 19/08.
    """
    assert len(_lista_do_shell("OUIS_LINHAGEM")) >= 2
    assert len(_lista_do_shell("NOMES_LINHAGEM")) >= 2
    assert len(com_dois_pontos(OUIS_NINTENDO_VISTAS | OUIS_CLONE)) >= 2


# ---------------------------------------------------------------------------
# O portão da CLASSE — barato, e mata a reincidência em vez do caso
# ---------------------------------------------------------------------------
#: `#` só abre comentário no começo da linha ou depois de espaço. Sem isso
#: `${VAR#prefixo}` viraria "comentário" e o portão ficaria cego no meio da
#: linha.
_COMENTARIO = re.compile(r"(?:^|(?<=\s))#.*$")
#: Um `hciN` LITERAL. A classe de caracteres `hci[0-9]+` das regex do produto
#: não casa aqui, e é por isso que a régua é `hci` seguido de DÍGITO.
_HCI_LITERAL = re.compile(r"hci[0-9]")
#: Uma fonte que devolve N adaptadores.
_FONTE_PLURAL = re.compile(
    r"(_adaptadores|_bt_adaptadores|/sys/class/bluetooth|busctl\s+tree"
    r"|btmgmt\s+info|hciconfig\s*\|)"
)
_CORTE = re.compile(r"\|\s*head\s+-(?:1|n\s*1|n1)\b")


def _reclamacoes(texto: str, nome: str = "<memória>") -> list[str]:
    fora: list[str] = []
    for n, linha in enumerate(texto.splitlines(), 1):
        codigo = _COMENTARIO.sub("", linha)
        if not codigo.strip():
            continue
        if _HCI_LITERAL.search(codigo):
            fora.append(f"{nome}:{n}: hciN literal em código: {linha.strip()}")
        if _FONTE_PLURAL.search(codigo) and _CORTE.search(codigo):
            fora.append(f"{nome}:{n}: fonte plural cortada no primeiro: {linha.strip()}")
    return fora


@pytest.mark.parametrize("arquivo", SCRIPTS_BT, ids=lambda p: p.name)
def test_nenhum_script_de_bluetooth_fala_por_um_adaptador_so(arquivo: Path) -> None:
    """`hci0` literal e `head -1` sobre fonte PLURAL.

    O `bt_health_watchdog.sh:158` já carrega a cicatriz por escrito desde 23/07
    — *"Concatenar 'hci0' fazia a vigia virar no-op MUDO num adaptador hci1"* —
    e mesmo assim o `hci0` literal seguiu vivo noutros arquivos por um mês.
    Cicatriz que não vira portão é cicatriz que a casa relê e não aplica.

    ESCOPO: `scripts/bt_*.sh` **e o `doctor.sh`**. A frente que escreveu este
    portão o declarou só sobre os `bt_*`, porque o `doctor.sh` era território de
    outra pessoa e um portão que reprova pelo arquivo alheio é um portão que
    alguém desliga. A razão era certa e caducou no mesmo dia: os dois `head -1`
    do achado A5 foram curados em 22/08, e o exame agora confere TODOS os
    adaptadores. Deixar o doctor fora do escopo depois disso seria guardar a
    porta que já está fechada e deixar aberta a que acabou de fechar.
    """
    reclamacoes = _reclamacoes(arquivo.read_text(encoding="utf-8"), arquivo.name)
    assert not reclamacoes, (
        "o produto pergunta a UM adaptador e responde pelo rádio inteiro:\n  "
        + "\n  ".join(reclamacoes)
        + "\n\nVer N-IGUAL-A-UM-01. Se a linha é sobre o adaptador PADRÃO do "
        "sistema, escolher um é certo — diga isso num comentário e o portão "
        "não a enxerga."
    )


def test_o_portao_da_classe_acha_as_duas_formas_plantadas() -> None:
    """Régua do portão acima: verde por cegueira é o defeito mais caro daqui."""
    plantado = (
        "#!/usr/bin/env bash\n"
        "# hci0 em comentário não conta\n"
        'disc="$(_dbus_bt_prop /org/bluez/hci0 org.bluez.Adapter1 Discovering)"\n'
        '_adp="$(_bt_adaptadores | head -1)"\n'
        'nome="${caminho#/org/bluez/}"\n'
    )
    achados = _reclamacoes(plantado, "plantado.sh")
    assert len(achados) == 2, achados
    assert "hciN literal" in achados[0]
    assert "fonte plural cortada" in achados[1]


def test_o_portao_da_classe_esta_olhando_para_alguma_coisa() -> None:
    assert len(SCRIPTS_BT) >= 8, [p.name for p in SCRIPTS_BT]
