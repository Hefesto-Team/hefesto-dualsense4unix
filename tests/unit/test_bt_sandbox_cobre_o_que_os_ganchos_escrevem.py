"""BT-SNAPSHOT-SANDBOX-01 — o sandbox tem de cobrir o que os ganchos escrevem."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_DIR = REPO_ROOT / "assets" / "systemd"
SCRIPT_DIR = REPO_ROOT / "scripts"
DE_TERCEIROS = REPO_ROOT / "tests" / "fixtures" / "systemd" / "de-terceiros"

PREFIXO_INSTALADO = "/usr/local/lib/hefesto-dualsense4unix"


@dataclass(frozen=True)
class Hospedeira:
    """O sandbox da unit de TERCEIRO em que a casa pendura um drop-in."""

    unit: str
    protect_system: str
    state_directory: tuple[str, ...] = ()
    private_tmp: bool = False


SEMPRE_GRAVAVEIS = ("/dev", "/proc", "/sys")

TRANCADO_POR_FULL = ("/usr", "/boot", "/efi", "/etc")

CMD_ULTIMO_ALVO = {"cp", "mv", "ln", "rsync"}
CMD_TODOS_ALVOS = {"mkdir", "rmdir", "touch", "chmod", "chown", "chgrp", "rm", "tee", "truncate"}
LIXO_DE_EXEC = {"\\;", ";", "+", "{}"}

_ATRIBUICAO = re.compile(
    r"^\s*(?:local\s+|readonly\s+|export\s+|declare\s+-\w+\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$"
)
_REDIRECIONAMENTO = re.compile(r"(?<![0-9<>&])[0-9]*>>?\s*([^\s;&|)<>]+)")
_REDIRECAO_NUA = re.compile(r"^[0-9]*[<>]")


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


def _sim(valor: str) -> bool:
    return valor in ("yes", "true", "1")


def _hospedeira_da_copia(unit: str) -> Hospedeira:
    """O sandbox da hospedeira lido da cópia versionada da unit dela."""
    diretivas = _diretivas_do_service((DE_TERCEIROS / unit).read_text(encoding="utf-8"))
    return Hospedeira(
        unit=unit,
        protect_system=(diretivas.get("ProtectSystem") or ["no"])[-1],
        state_directory=tuple(_lista(diretivas, "StateDirectory")),
        private_tmp=_sim((diretivas.get("PrivateTmp") or ["no"])[-1]),
    )


def _sandbox_vivo(unit: str) -> Hospedeira | None:
    """O sandbox da unit segundo o systemd desta máquina, ou None se ela não está carregada."""
    proc = subprocess.run(
        ["systemctl", "show", unit, "-p", "LoadState", "-p", "ProtectSystem",
         "-p", "PrivateTmp", "-p", "StateDirectory"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    campos = dict(linha.partition("=")[::2] for linha in proc.stdout.splitlines())
    if proc.returncode != 0 or campos.get("LoadState") != "loaded":
        return None
    return Hospedeira(
        unit=unit,
        protect_system=campos.get("ProtectSystem", ""),
        state_directory=tuple(campos.get("StateDirectory", "").split()),
        private_tmp=_sim(campos.get("PrivateTmp", "")),
    )


HOSPEDEIRAS = {
    "bluetooth-dropin-10-hefesto-resilience.conf": _hospedeira_da_copia("bluetooth.service"),
}


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
            if aninhado:
                fora.append(valor[i:])
                break
            fora.append(_expandir(valor[i + 2 : j - 1], tabela, nivel))
            i = j
        else:
            fora.append(valor[i])
            i += 1
    return "".join(fora)


def _prefixo_util(caminho: str) -> str | None:
    """O maior prefixo ABSOLUTO e certo de um alvo de escrita."""
    if not caminho.startswith("/"):
        return None
    cortou = "$" in caminho or "*" in caminho or "?" in caminho
    corte = re.split(r"[$*?]", caminho, maxsplit=1)[0]
    if cortou:
        corte = corte.rsplit("/", 1)[0]
    corte = corte.rstrip("/")
    if corte.count("/") < 2:
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
        tmp_privado = _sim((diretivas.get("PrivateTmp") or ["no"])[-1])
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


class TestOExtratorEnxerga:
    def test_o_extrator_enxerga_o_que_o_snapshot_escreve(self) -> None:
        """O `bt_bonds_snapshot.sh` grava no acervo — e o extrator tem de ver."""
        texto = (SCRIPT_DIR / "bt_bonds_snapshot.sh").read_text(encoding="utf-8")
        escritos = _caminhos_escritos(texto)
        assert "/var/lib/hefesto-dualsense4unix/bt-bonds" in escritos, (
            f"o extrator não achou o acervo nas escritas do snapshot: {sorted(escritos)}"
        )

    def test_o_extrator_enxerga_as_duas_escritas_do_autorestore(self) -> None:
        """A volta automática escreve nos DOIS lugares — e é isso que o drop-in"""
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
        """`2>/dev/null` e a FONTE de um `cp` não são escrita."""
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


class TestSandboxCobreAsEscritas:
    @pytest.mark.parametrize("alvo", COM_GANCHO_NOSSO, ids=lambda a: a.nome)
    def test_todo_caminho_escrito_esta_no_readwritepaths(self, alvo: Alvo) -> None:
        """Sob `ProtectSystem=strict`, escrever fora do `ReadWritePaths` é EROFS."""
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
        """A outra ponta: declarar somente-leitura o que o próprio gancho grava."""
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

    def test_o_portao_mede_sob_o_sandbox_da_copia(self) -> None:
        """A cópia da máquina do usuário chega ao portão, em toda máquina."""
        alvo = next(a for a in ALVOS if a.nome in HOSPEDEIRAS)
        assert alvo.protect_system == "strict", alvo
        assert "/var/lib/bluetooth" in alvo.gravaveis and "/tmp" in alvo.gravaveis, alvo

    def test_o_leitor_nao_toma_unit_ausente_por_hospedeira(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O leitor do systemd vivo, contra um `systemctl` de mentira."""
        dubles = tmp_path / "bin"
        dubles.mkdir()
        monkeypatch.setenv("PATH", f"{dubles}:{os.environ.get('PATH', '')}")

        def systemd_responde(saida: str) -> None:
            falso = dubles / "systemctl"
            falso.write_text(f"#!/bin/sh\ncat <<'FIM'\n{saida}FIM\n", encoding="utf-8")
            falso.chmod(0o755)

        systemd_responde("PrivateTmp=no\nProtectSystem=no\nStateDirectory=\nLoadState=not-found\n")
        assert _sandbox_vivo("bluetooth.service") is None
        systemd_responde(
            "PrivateTmp=yes\nProtectSystem=strict\nStateDirectory=bluetooth\nLoadState=loaded\n"
        )
        assert _sandbox_vivo("bluetooth.service") == HOSPEDEIRAS[
            "bluetooth-dropin-10-hefesto-resilience.conf"
        ]

    def test_a_hospedeira_declarada_bate_com_a_maquina(self) -> None:
        """O systemd vivo confirma a cópia, onde o bluez está carregado."""
        if shutil.which("systemctl") is None:
            pytest.skip("sem systemctl")
        for declarada in HOSPEDEIRAS.values():
            viva = _sandbox_vivo(declarada.unit)
            if viva is None:
                pytest.skip(f"{declarada.unit} não está carregado nesta máquina (LoadState)")
            assert viva == declarada, (
                f"{declarada.unit} roda com {viva}, e a cópia em {DE_TERCEIROS} "
                f"diz {declarada}. Copie a unit de novo (ver o LEIA.md de lá) — e "
                "confira se o `ReadWritePaths` do nosso drop-in ainda basta."
            )

    def test_o_dropin_abre_os_dois_lugares_que_a_volta_escreve(self) -> None:
        """Regressão nomeada: as duas linhas de `ReadWritePaths` de hoje."""
        texto = (UNIT_DIR / "bluetooth-dropin-10-hefesto-resilience.conf").read_text(
            encoding="utf-8"
        )
        declarados = _lista(_diretivas_do_service(texto), "ReadWritePaths")
        assert "/var/lib/hefesto-dualsense4unix" in declarados
        assert "/var/lib/bluetooth" in declarados
