"""BT-SNAPSHOT-SANDBOX-01 — o sandbox tem de cobrir o que os ganchos escrevem.

Sprint: docs/process/sprints/2026-08-04-BT-SNAPSHOT-SANDBOX-01-*.md

O DEFEITO, MEDIDO no crash de 03/08 às 23:58:

    23:58:07  bluetooth.service: Main process exited, code=dumped, status=6/ABRT
    23:58:07  bt_bonds_snapshot.sh:105:
              /var/lib/hefesto-dualsense4unix/bt-bonds/.lock:
              Sistema de arquivos somente para leitura

O `ExecStopPost=` HERDA o sandbox da unit hospedeira. O `bluetooth.service` do
bluez roda com `ProtectSystem=strict` e `ReadWritePaths=` vazio: `/var` inteiro
é somente-leitura para tudo o que corre dentro dele. O salva-vidas de bonds
falhava **exatamente** na parada por crash — o único momento em que importa — e
o `-` do `ExecStopPost` engolia a falha.

O QUE A SPRINT PEDIU POR ESCRITO, e é este arquivo:

    "Um teste que leia o drop-in e exija `ReadWritePaths` cobrindo TODO caminho
    que os `ExecStopPost` dele escrevem. Arrancar a linha faz reprovar. Sem esse
    teste, a próxima pessoa que acrescentar um `ExecStopPost` que escreve noutro
    lugar reabre isto — e só descobre no próximo naufrágio."

POR QUE A LISTA É DERIVADA, e não escrita à mão: uma lista à mão caduca no
próximo caminho novo e volta a mentir — o portão fica verde enquanto o defeito
volta. Aqui os caminhos saem de LER os scripts que as units chamam: cada
operação de escrita (`install`, `cp`, `mkdir`, `chmod`, redirecionamento...) tem
o alvo resolvido contra as atribuições do próprio script, e o que sobra é
confrontado com o `ReadWritePaths` declarado.

AS MORDIDAS:

  1. acrescente ao `bt_bonds_snapshot.sh` uma escrita fora do `ReadWritePaths`
     (`install -d /var/lib/outro-lugar`, por exemplo) e
     `test_todo_caminho_escrito_esta_no_readwritepaths` reprova, nomeando a unit
     e o caminho;
  2. apague `ReadWritePaths=/var/lib/hefesto-dualsense4unix` do drop-in — que é
     literalmente a cura de 04/08 — e o mesmo teste reprova;
  3. quebre o extrator (faça-o devolver vazio) e
     `test_o_extrator_enxerga_o_que_o_snapshot_escreve` reprova. Sem essa régua
     o portão acima ficaria verde por não enxergar nada, que é o
     "portão que não mede o que promete" de 19/08.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_DIR = REPO_ROOT / "assets" / "systemd"
SCRIPT_DIR = REPO_ROOT / "scripts"

#: Onde o install.sh põe os scripts da casa. É o prefixo que aparece dentro das
#: units e dentro dos próprios scripts quando um chama o outro.
PREFIXO_INSTALADO = "/usr/local/lib/hefesto-dualsense4unix"


@dataclass(frozen=True)
class Hospedeira:
    """O sandbox da unit de TERCEIRO em que a casa pendura um drop-in.

    É a peça que não dá para derivar do nosso repositório — ela mora no pacote
    de outra pessoa. Fica aqui com a medição que a sustenta, e o
    `test_a_hospedeira_declarada_bate_com_a_maquina` a confronta com o systemd
    vivo quando há um.
    """

    unit: str
    protect_system: str
    #: `StateDirectory=` da hospedeira: o systemd o cria e o deixa gravável
    #: mesmo sob `ProtectSystem=strict`.
    state_directory: tuple[str, ...] = ()
    private_tmp: bool = False


#: MEDIDO em 04/08/2026 e reconferido em 22/08/2026 com
#: `systemctl cat bluetooth.service` (bluez 5.86, Pop!_OS 24.04):
#: ProtectSystem=strict, StateDirectory=bluetooth, ReadWritePaths ausente.
HOSPEDEIRAS = {
    "bluetooth-dropin-10-hefesto-resilience.conf": Hospedeira(
        unit="bluetooth.service",
        protect_system="strict",
        state_directory=("bluetooth",),
        private_tmp=True,
    ),
}

#: Subárvores de API que o `ProtectSystem=` nunca torna somente-leitura.
SEMPRE_GRAVAVEIS = ("/dev", "/proc", "/sys")

#: O que o `ProtectSystem=full`/`yes` tranca (o `strict` tranca tudo).
TRANCADO_POR_FULL = ("/usr", "/boot", "/efi", "/etc")

#: Comandos cuja ÚLTIMA operando é o destino.
CMD_ULTIMO_ALVO = {"cp", "mv", "ln", "rsync"}
#: Comandos em que TODA operando não-opção é alvo de escrita.
CMD_TODOS_ALVOS = {"mkdir", "rmdir", "touch", "chmod", "chown", "chgrp", "rm", "tee", "truncate"}
#: Tokens que o `find -exec` deixa no fim da linha e não são caminho.
LIXO_DE_EXEC = {"\\;", ";", "+", "{}"}

_ATRIBUICAO = re.compile(
    r"^\s*(?:local\s+|readonly\s+|export\s+|declare\s+-\w+\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$"
)
#: Redirecionamento de saída, com ou sem descritor à frente (`9>`, `2>`, `>>`).
_REDIRECIONAMENTO = re.compile(r"(?<![0-9<>&])[0-9]*>>?\s*([^\s;&|)<>]+)")
#: Um token que É um redirecionamento (`2>/dev/null`) não é operando de comando.
_REDIRECAO_NUA = re.compile(r"^[0-9]*[<>]")


# ---------------------------------------------------------------------------
# Leitura das units
# ---------------------------------------------------------------------------
def _diretivas_do_service(texto: str) -> dict[str, list[str]]:
    """`chave -> [valores]` da seção `[Service]` (drop-in = seção única)."""
    fora: dict[str, list[str]] = {}
    secao = "[Service]"
    for linha in texto.splitlines():
        nua = linha.strip()
        if not nua or nua.startswith(("#", ";")):
            continue
        if nua.startswith("["):
            secao = nua
            continue
        if secao != "[Service]" or "=" not in nua:
            continue
        chave, _, valor = nua.partition("=")
        fora.setdefault(chave.strip(), []).append(valor.strip())
    return fora


def _lista(diretivas: dict[str, list[str]], chave: str) -> list[str]:
    """Valores de uma diretiva que aceita lista separada por espaço."""
    fora: list[str] = []
    for bruto in diretivas.get(chave, []):
        for item in bruto.split():
            fora.append(item.lstrip("-+").strip('"'))
    return fora


def _programa_do_exec(valor: str) -> str:
    """O argv[0] de uma linha `Exec*=`, sem os modificadores `-`, `+`, `!`, `@`, `:`."""
    return valor.lstrip("-+!@:").split()[0] if valor.strip() else ""


# ---------------------------------------------------------------------------
# Leitura dos scripts: o que eles ESCREVEM
# ---------------------------------------------------------------------------
def _tokens(linha: str) -> list[str]:
    """Divide uma linha de shell em palavras, respeitando aspas e `$(...)`."""
    fora: list[str] = []
    atual: list[str] = []
    aspas = ""
    profundidade = 0
    i = 0
    while i < len(linha):
        c = linha[i]
        if profundidade:
            atual.append(c)
            if c == "(":
                profundidade += 1
            elif c == ")":
                profundidade -= 1
            i += 1
        elif aspas:
            if c == aspas:
                aspas = ""
            else:
                atual.append(c)
            i += 1
        elif c in "\"'":
            aspas = c
            i += 1
        elif linha.startswith("$(", i):
            atual.append("$(")
            profundidade = 1
            i += 2
        elif c.isspace():
            if atual:
                fora.append("".join(atual))
                atual = []
            i += 1
        else:
            atual.append(c)
            i += 1
    if atual:
        fora.append("".join(atual))
    return fora


def _expandir(corpo: str, tabela: dict[str, str], nivel: int) -> str:
    nome, sep, padrao = corpo.partition(":-")
    if nome in tabela:
        return tabela[nome]
    if sep:
        return _resolver(padrao, tabela, nivel + 1)
    return "${" + corpo + "}"


def _resolver(valor: str, tabela: dict[str, str], nivel: int = 0) -> str:
    """Troca `${VAR}` e `${VAR:-padrão}` pelo que o script já atribuiu."""
    if nivel > 10 or "${" not in valor:
        return valor
    fora: list[str] = []
    i = 0
    while i < len(valor):
        if valor.startswith("${", i):
            j, aninhado = i + 2, 1
            while j < len(valor) and aninhado:
                if valor[j] == "{":
                    aninhado += 1
                elif valor[j] == "}":
                    aninhado -= 1
                j += 1
            if aninhado:  # chave sem fecho: não é nossa briga
                fora.append(valor[i:])
                break
            fora.append(_expandir(valor[i + 2 : j - 1], tabela, nivel))
            i = j
        else:
            fora.append(valor[i])
            i += 1
    return "".join(fora)


def _prefixo_util(caminho: str) -> str | None:
    """O maior prefixo ABSOLUTO e certo de um alvo de escrita.

    O que sobra de `${VAR}` sem valor conhecido (um MAC, um timestamp) vira
    corte: `/var/lib/.../bt-bonds/$(date ...)-$$` -> `/var/lib/.../bt-bonds`.
    É o prefixo que a cobertura precisa, e ele não depende de adivinhar o resto.
    """
    if not caminho.startswith("/"):
        return None
    cortou = "$" in caminho or "*" in caminho or "?" in caminho
    corte = re.split(r"[$*?]", caminho, maxsplit=1)[0]
    if cortou:
        corte = corte.rsplit("/", 1)[0]
    corte = corte.rstrip("/")
    if corte.count("/") < 2:  # "/" ou "/var": raso demais para significar algo
        return None
    return corte


def _alvos_da_linha(tokens: list[str]) -> list[str]:
    """Os operandos que a linha ESCREVE, ainda por resolver."""
    alvos: list[str] = []
    for pos, tok in enumerate(tokens):
        base = tok.rsplit("/", 1)[-1]
        resto = [
            t
            for t in tokens[pos + 1 :]
            if t not in LIXO_DE_EXEC and not _REDIRECAO_NUA.match(t)
        ]
        naoopcao = [t for t in resto if not t.startswith("-")]
        if base == "install":
            if "-d" in resto:
                alvos.extend(naoopcao)
            elif naoopcao:
                alvos.append(naoopcao[-1])
        elif base in CMD_ULTIMO_ALVO:
            if naoopcao:
                alvos.append(naoopcao[-1])
        elif base in CMD_TODOS_ALVOS:
            alvos.extend(naoopcao)
    return alvos


def _caminhos_escritos(texto: str) -> set[str]:
    """Tudo o que um script shell escreve, em prefixos absolutos."""
    tabela: dict[str, str] = {}
    escritos: set[str] = set()
    for linha in texto.splitlines():
        if linha.lstrip().startswith("#") or not linha.strip():
            continue
        codigo = linha.split(" #", 1)[0]
        atribuicao = _ATRIBUICAO.match(codigo)
        if atribuicao:
            nome, bruto = atribuicao.group(1), atribuicao.group(2).strip()
            tokens = _tokens(bruto)
            tabela[nome] = _resolver(tokens[0], tabela) if tokens else ""
            continue
        brutos = _alvos_da_linha(_tokens(codigo))
        brutos += [
            alvo.strip("\"'")
            for alvo in _REDIRECIONAMENTO.findall(codigo)
            if alvo.strip("\"'") not in ("/dev/null", "/dev/stderr", "/dev/stdout")
        ]
        for bruto in brutos:
            util = _prefixo_util(_resolver(bruto, tabela))
            if util:
                escritos.add(util)
    # Fica só o prefixo mais curto de cada família: quem já está dentro de
    # outro caminho do conjunto não acrescenta nada à pergunta da cobertura, e
    # atrapalha a leitura da mensagem de falha.
    return {c for c in escritos if not any(c != o and _sob(c, o) for o in escritos)}


def _sob(caminho: str, raiz: str) -> bool:
    """`caminho` é a própria `raiz` ou está dentro dela."""
    raiz = raiz.rstrip("/")
    return caminho == raiz or caminho.startswith(raiz + "/")


def _script_do_repo(programa: str) -> Path | None:
    """O arquivo NO REPO que corresponde a um programa instalado, se for nosso."""
    if not programa.startswith(PREFIXO_INSTALADO + "/"):
        return None
    candidato = SCRIPT_DIR / programa.rsplit("/", 1)[-1]
    if not candidato.is_file():
        return None
    if not candidato.read_text(encoding="utf-8", errors="replace").startswith("#!"):
        return None
    return candidato


def _escritas_transitivas(programas: list[str]) -> tuple[set[str], set[str], list[str]]:
    """Segue os scripts que os `Exec*=` chamam — e os que ELES chamam."""
    fila = list(programas)
    vistos: set[str] = set()
    escritos: set[str] = set()
    seguidos: set[str] = set()
    ignorados: list[str] = []
    while fila:
        programa = fila.pop()
        if programa in vistos:
            continue
        vistos.add(programa)
        script = _script_do_repo(programa)
        if script is None:
            ignorados.append(programa)
            continue
        seguidos.add(script.name)
        texto = script.read_text(encoding="utf-8")
        escritos |= _caminhos_escritos(texto)
        for chamado in re.findall(rf"{re.escape(PREFIXO_INSTALADO)}/[\w.-]+", texto):
            fila.append(chamado)
    return escritos, seguidos, ignorados


# ---------------------------------------------------------------------------
# O confronto
# ---------------------------------------------------------------------------
@dataclass
class Alvo:
    nome: str
    protect_system: str
    gravaveis: list[str]
    somente_leitura: list[str]
    escritos: set[str]
    seguidos: set[str] = field(default_factory=set)


def _coberto(caminho: str, permitidos: list[str]) -> bool:
    return any(_sob(caminho, p) for p in permitidos)


def _alvos() -> list[Alvo]:
    fora: list[Alvo] = []
    for unit in sorted(UNIT_DIR.iterdir()):
        if not unit.is_file():
            continue
        diretivas = _diretivas_do_service(unit.read_text(encoding="utf-8"))
        hospedeira = HOSPEDEIRAS.get(unit.name)
        programas = [
            _programa_do_exec(v)
            for chave, valores in diretivas.items()
            if chave.startswith("Exec")
            for v in valores
        ]
        escritos, seguidos, _ = _escritas_transitivas([p for p in programas if p])
        gravaveis = [*SEMPRE_GRAVAVEIS, *_lista(diretivas, "ReadWritePaths")]
        gravaveis += [f"/var/lib/{d}" for d in _lista(diretivas, "StateDirectory")]
        gravaveis += [f"/run/{d}" for d in _lista(diretivas, "RuntimeDirectory")]
        gravaveis += [f"/var/log/{d}" for d in _lista(diretivas, "LogsDirectory")]
        gravaveis += [f"/var/cache/{d}" for d in _lista(diretivas, "CacheDirectory")]
        protect = (diretivas.get("ProtectSystem") or ["no"])[-1]
        tmp_privado = (diretivas.get("PrivateTmp") or ["no"])[-1] in ("yes", "true", "1")
        if hospedeira is not None:
            protect = hospedeira.protect_system
            gravaveis += [f"/var/lib/{d}" for d in hospedeira.state_directory]
            tmp_privado = tmp_privado or hospedeira.private_tmp
        if tmp_privado:
            gravaveis += ["/tmp", "/var/tmp"]
        fora.append(
            Alvo(
                nome=unit.name,
                protect_system=protect,
                gravaveis=gravaveis,
                somente_leitura=_lista(diretivas, "ReadOnlyPaths"),
                escritos=escritos,
                seguidos=seguidos,
            )
        )
    return fora


ALVOS = _alvos()
COM_GANCHO_NOSSO = [a for a in ALVOS if a.escritos or a.seguidos]


# ---------------------------------------------------------------------------
# A régua do instrumento — sem ela, o portão abaixo passa por cegueira
# ---------------------------------------------------------------------------
class TestOExtratorEnxerga:
    def test_o_extrator_enxerga_o_que_o_snapshot_escreve(self) -> None:
        """O `bt_bonds_snapshot.sh` grava no acervo — e o extrator tem de ver.

        Esta é a contagem independente do instrumento (lição de 19/08: cada
        portão precisa da sua régua). Se o extrator devolver vazio, o portão de
        cobertura fica verde sem medir nada.
        """
        texto = (SCRIPT_DIR / "bt_bonds_snapshot.sh").read_text(encoding="utf-8")
        escritos = _caminhos_escritos(texto)
        assert "/var/lib/hefesto-dualsense4unix/bt-bonds" in escritos, (
            f"o extrator não achou o acervo nas escritas do snapshot: {sorted(escritos)}"
        )

    def test_o_extrator_enxerga_as_duas_escritas_do_autorestore(self) -> None:
        """A volta automática escreve nos DOIS lugares — e é isso que o drop-in
        precisa ter aberto: o acervo (ledger) e o storage do BlueZ."""
        texto = (SCRIPT_DIR / "bt_bonds_autorestore.sh").read_text(encoding="utf-8")
        escritos = _caminhos_escritos(texto)
        for raiz in ("/var/lib/bluetooth", "/var/lib/hefesto-dualsense4unix/bt-bonds"):
            assert any(_sob(c, raiz) for c in escritos), (
                f"o extrator não achou escrita em {raiz}: {sorted(escritos)}"
            )

    def test_o_extrator_acha_uma_escrita_plantada(self, tmp_path: Path) -> None:
        """Controle positivo: caminho novo, fora de qualquer lista, é achado."""
        roteiro = (
            '#!/usr/bin/env bash\n'
            'ALVO="${HEFESTO_TESTE_RAIZ:-/var/lib/lugar-inventado}"\n'
            'install -d -m 700 "${ALVO}/${SEJA_LA_O_QUE_FOR}"\n'
            'printf x > "${ALVO}/marca"\n'
        )
        assert _caminhos_escritos(roteiro) == {"/var/lib/lugar-inventado"}

    def test_o_extrator_nao_confunde_leitura_com_escrita(self) -> None:
        """`2>/dev/null` e a FONTE de um `cp` não são escrita.

        Sem isto o portão exigiria `ReadWritePaths` para `/var/lib/bluetooth` na
        unit do snapshot periódico — que lê o storage e o declara
        `ReadOnlyPaths` de propósito.
        """
        roteiro = (
            '#!/usr/bin/env bash\n'
            'FONTE=/var/lib/bluetooth\n'
            'DESTINO=/var/lib/hefesto-dualsense4unix/bt-bonds\n'
            'cp -a "${FONTE}/algo" "${DESTINO}/" 2>/dev/null\n'
        )
        assert _caminhos_escritos(roteiro) == {"/var/lib/hefesto-dualsense4unix/bt-bonds"}

    def test_os_ganchos_do_dropin_foram_mesmo_lidos(self) -> None:
        """O drop-in tem três `Exec*` nossos; o extrator tem de ter aberto os três."""
        alvo = next(a for a in ALVOS if a.nome in HOSPEDEIRAS)
        assert alvo.seguidos >= {
            "bt_bonds_snapshot.sh",
            "bt_bonds_autorestore.sh",
            "bt_active_mode.sh",
        }, f"scripts lidos: {sorted(alvo.seguidos)}"


# ---------------------------------------------------------------------------
# O portão que a sprint pediu
# ---------------------------------------------------------------------------
class TestSandboxCobreAsEscritas:
    @pytest.mark.parametrize("alvo", COM_GANCHO_NOSSO, ids=lambda a: a.nome)
    def test_todo_caminho_escrito_esta_no_readwritepaths(self, alvo: Alvo) -> None:
        """Sob `ProtectSystem=strict`, escrever fora do `ReadWritePaths` é EROFS.

        ARRANQUE A CURA: apague `ReadWritePaths=/var/lib/hefesto-dualsense4unix`
        do drop-in — a linha exata de 04/08 — e este teste reprova apontando o
        acervo de bonds. Ou acrescente ao snapshot uma escrita em lugar novo:
        reprova apontando o lugar novo.
        """
        if alvo.protect_system not in ("strict", "full", "yes", "true"):
            pytest.skip(f"{alvo.nome}: sem ProtectSystem — /var já é gravável")
        exigidos = sorted(
            c
            for c in alvo.escritos
            if alvo.protect_system == "strict" or c.startswith(TRANCADO_POR_FULL)
        )
        descobertos = [c for c in exigidos if not _coberto(c, alvo.gravaveis)]
        assert not descobertos, (
            f"{alvo.nome}: os ganchos escrevem em {descobertos}, e o sandbox "
            f"(ProtectSystem={alvo.protect_system}) só abre {sorted(alvo.gravaveis)}. "
            "É o BT-SNAPSHOT-SANDBOX-01: a unit sobe bem e só recusa a escrita na "
            "hora do naufrágio, com o `-` do ExecStopPost engolindo o erro."
        )

    @pytest.mark.parametrize("alvo", COM_GANCHO_NOSSO, ids=lambda a: a.nome)
    def test_nenhuma_escrita_cai_num_readonlypaths(self, alvo: Alvo) -> None:
        """A outra ponta: declarar somente-leitura o que o próprio gancho grava.

        O `hefesto-bt-bonds-snapshot.service` declara
        `ReadOnlyPaths=/var/lib/bluetooth` de propósito — o snapshot só LÊ o
        storage. No dia em que alguém puser ali uma escrita, o erro é o mesmo
        EROFS de 03/08, e este teste o pega antes do naufrágio.
        """
        presos = sorted(
            c
            for c in alvo.escritos
            if _coberto(c, alvo.somente_leitura)
            and not any(
                _coberto(c, [g]) and len(g) > max(len(r) for r in alvo.somente_leitura)
                for g in alvo.gravaveis
            )
        )
        assert not presos, (
            f"{alvo.nome}: escreve em {presos}, que a própria unit declara "
            f"ReadOnlyPaths={alvo.somente_leitura}"
        )


class TestAHospedeiraNaoEnvelheceCalada:
    """A `Hospedeira` é o único dado deste arquivo que vem de fora do repo."""

    def test_a_hospedeira_declarada_bate_com_a_maquina(self) -> None:
        """Segunda régua: o systemd vivo confirma o `ProtectSystem` da tabela.

        Pula onde não há systemd nem bluez (CI headless, contêiner). Onde há,
        é o que impede a tabela de envelhecer em silêncio quando o pacote do
        BlueZ afrouxar ou apertar o sandbox numa atualização.
        """
        if shutil.which("systemctl") is None:
            pytest.skip("sem systemctl")
        for hospedeira in HOSPEDEIRAS.values():
            proc = subprocess.run(
                ["systemctl", "show", hospedeira.unit, "-p", "ProtectSystem"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            vivo = proc.stdout.strip().partition("=")[2]
            if proc.returncode != 0 or not vivo:
                pytest.skip(f"{hospedeira.unit} não existe nesta máquina")
            assert vivo == hospedeira.protect_system, (
                f"{hospedeira.unit} roda com ProtectSystem={vivo}, e a tabela "
                f"deste teste diz {hospedeira.protect_system}. Atualize a tabela "
                "— e confira se o `ReadWritePaths` do nosso drop-in ainda basta."
            )

    def test_o_dropin_abre_os_dois_lugares_que_a_volta_escreve(self) -> None:
        """Regressão nomeada: as duas linhas de `ReadWritePaths` de hoje.

        O acervo veio do BT-SNAPSHOT-SANDBOX-01 (04/08); o `/var/lib/bluetooth`
        veio do gatilho da volta (15/08) e está escrito mesmo vindo de graça do
        `StateDirectory=bluetooth` do bluez — para que a dependência esteja no
        arquivo e não num detalhe do pacote alheio.
        """
        texto = (UNIT_DIR / "bluetooth-dropin-10-hefesto-resilience.conf").read_text(
            encoding="utf-8"
        )
        declarados = _lista(_diretivas_do_service(texto), "ReadWritePaths")
        assert "/var/lib/hefesto-dualsense4unix" in declarados
        assert "/var/lib/bluetooth" in declarados
