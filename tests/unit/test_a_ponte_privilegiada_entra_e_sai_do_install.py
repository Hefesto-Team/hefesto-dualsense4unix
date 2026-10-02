"""A ponte privilegiada entra pelo install, sai pelo uninstall, e a regra é estreita."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.fonte_do_instalador import texto_do_instalador

RAIZ = Path(__file__).resolve().parents[2]
PONTE = RAIZ / "scripts" / "bt_ponte_privilegiada.sh"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"

FUNCAO = "install_bt_ponte_privilegiada_host"
ALVO = "/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"
REGRA = "/etc/sudoers.d/49-hefesto-bt-ponte"

USUARIA = "usuariadeteste"

FORA_DA_REGRA = {
    "regra-sudo",
    "ajuda",
    "--help",
    "-h",
}


def _corpo_da_funcao(texto: str, nome: str) -> str:
    """O corpo de uma função de shell, do `nome() {` até o `}` na coluna zero."""
    inicio = texto.index(f"{nome}() {{")
    resto = texto[inicio:]
    fim = resto.index("\n}\n")
    return resto[: fim + 3]


def _corpo_expandido() -> str:
    """O corpo da função com os `local X=/caminho` já substituídos."""
    corpo = _corpo_da_funcao(texto_do_instalador(), FUNCAO)
    for nome, valor in re.findall(r'^\s*local (\w+)=([^\s"]+)$', corpo, re.M):
        corpo = corpo.replace("${" + nome + "}", valor)
    return corpo


def _caminhos_gravados() -> set[str]:
    """Só o que o install de fato ESCREVE — as linhas de `install -D`."""
    achados: set[str] = set()
    for linha in _corpo_expandido().splitlines():
        if "install -D" not in linha:
            continue
        achados.update(re.findall(r"/(?:etc|usr/local)/[\w./-]+", linha))
    return achados


def _regra(usuaria: str = USUARIA) -> str:
    env = dict(os.environ)
    env["HEFESTO_BT_LOG_DEST"] = "none"
    resultado = subprocess.run(
        ["bash", str(PONTE), "regra-sudo", usuaria],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout


def _verbos_do_case() -> set[str]:
    """Os rótulos do `case` de despacho — a lista REAL de verbos do script."""
    texto = PONTE.read_text(encoding="utf-8")
    bloco = texto[texto.index('case "${VERBO}" in') : texto.rindex("esac")]
    rotulos: set[str] = set()
    for linha in bloco.splitlines():
        casado = re.match(r"^\s{4}([A-Za-z0-9|_-]+)\)\s*$", linha)
        if casado:
            rotulos.update(casado.group(1).split("|"))
    return rotulos


def test_o_case_tem_os_verbos_que_o_cabecalho_promete() -> None:
    """Trava de encolhimento: se o parser do `case` quebrar, tudo abaixo vira vácuo."""
    verbos = _verbos_do_case()
    assert {
        "adaptadores",
        "bonds",
        "renomear",
        "esquecer",
        "descobrir",
        "parear",
        "desconectar",
    } <= verbos


def test_todo_verbo_que_muda_algo_esta_na_regra_do_sudoers() -> None:
    """Paridade entre o `case` (texto) e a regra (script rodando)."""
    regra = _regra()
    for verbo in sorted(_verbos_do_case() - FORA_DA_REGRA):
        assert f"{ALVO} {verbo}" in regra, f"o verbo '{verbo}' não está na regra do sudoers"
    citados = set(re.findall(rf"{re.escape(ALVO)} ([a-z-]+)", regra))
    assert citados <= _verbos_do_case()


def test_a_regra_nao_tem_curinga() -> None:
    """`*` no sudoers casa espaço em branco — é como NOPASSWD estreito vira largo."""
    for linha in _regra().splitlines():
        if ALVO not in linha:
            continue
        assert "*" not in linha, f"curinga na regra: {linha.strip()}"
        assert "?" not in linha, f"curinga de um caractere na regra: {linha.strip()}"


def test_a_regra_nao_aceita_endereco() -> None:
    """A regra casa o verbo, e nenhum endereço: ele vem pelo stdin."""
    regra = _regra()
    for verbo in ("bonds", "renomear", "esquecer", "parear", "desconectar"):
        assert re.search(rf"^\s*{re.escape(ALVO)} {verbo}, \\$", regra, re.M), verbo
    for linha in regra.splitlines():
        if ALVO not in linha or linha.lstrip().startswith("#"):
            continue
        assert "A-F" not in linha and "\\:" not in linha, f"classe de endereço: {linha.strip()}"
        resto = linha.strip().rstrip("\\").strip().rstrip(",").split()[1:]
        if resto[0] == "descobrir":
            assert len(resto) == 2 and re.fullmatch(r"(\[0-9\]){1,3}", resto[1]), linha
        else:
            assert len(resto) == 1, f"argumento além do verbo: {linha.strip()}"


def test_a_regra_cobre_uma_janela_de_busca_de_dois_digitos() -> None:
    """`descobrir` recebe segundos, e 1, 2 e 3 dígitos precisam de linha própria."""
    regra = _regra()
    for classe in ("[0-9]", "[0-9][0-9]", "[0-9][0-9][0-9]"):
        assert " descobrir " in regra
        assert regra.count(f" {classe}\n") + regra.count(f" {classe},") >= 1, classe


def test_a_regra_e_nominal_e_nao_para_todo_mundo() -> None:
    regra = _regra()
    assert f"{USUARIA} ALL=(root) NOPASSWD: HEFESTO_BT_PONTE" in regra
    assert "ALL ALL=" not in regra
    assert "NOPASSWD: ALL" not in regra


def test_a_regra_aponta_para_o_caminho_que_o_install_de_fato_instala() -> None:
    """Caminho na regra ≠ caminho instalado = NOPASSWD que nunca casa."""
    caminhos = {c for c in _caminhos_gravados() if c.startswith("/usr/local/")}
    assert caminhos == {ALVO}, caminhos
    assert ALVO in _regra()


@pytest.mark.skipif(shutil.which("visudo") is None, reason="visudo ausente nesta máquina")
def test_a_regra_gerada_passa_no_visudo(tmp_path: Path) -> None:
    """Sudoers inválido derruba o sudo da máquina INTEIRA — inclusive o que"""
    arquivo = tmp_path / "49-hefesto-bt-ponte"
    arquivo.write_text(_regra(), encoding="utf-8")
    resultado = subprocess.run(
        ["visudo", "-cqf", str(arquivo)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_nada_vai_para_o_sudoers_sem_passar_pelo_visudo() -> None:
    """A ordem importa: conferir DEPOIS de gravar não conserta nada."""
    corpo = _corpo_expandido()
    assert "visudo" in corpo, "a função não confere o sudoers antes de gravá-lo"
    posicao_visudo = corpo.index("visudo -cqf")
    grava = re.search(rf"install -Dm440[^\n]*{re.escape(REGRA)}", corpo)
    assert grava is not None, "a função não grava a regra em " + REGRA
    posicao_grava = grava.start()
    assert posicao_visudo < posicao_grava, "o visudo -c roda DEPOIS da gravação"
    assert "command -v visudo" in corpo


def test_o_install_confere_no_proprio_sudo_e_nao_so_no_disco() -> None:
    """"A casa sabe e o produto não faz" — arquivo gravado não é permissão dada."""
    corpo = _corpo_da_funcao(texto_do_instalador(), FUNCAO)
    assert re.search(r"sudo -n -l -U", corpo), "o install não pergunta ao sudo se a regra pegou"


def test_o_install_grava_o_sudoers_com_o_modo_que_o_sudo_exige() -> None:
    """0440 root:root. Com qualquer outro modo o sudo ignora o arquivo calado."""
    corpo = _corpo_expandido()
    assert re.search(rf"install -Dm440 -o root -g root .*{re.escape(REGRA)}", corpo)
    assert re.search(rf"install -Dm755 -o root -g root .*{re.escape(ALVO)}", corpo)


def test_o_install_nao_abre_a_ponte_para_root() -> None:
    """Sem saber para QUEM, não se grava regra nenhuma."""
    corpo = _corpo_da_funcao(texto_do_instalador(), FUNCAO)
    assert 'SUDO_USER:-$(id -un)' in corpo
    assert '== "root"' in corpo


def test_tudo_que_o_install_grava_o_uninstall_tira() -> None:
    """Simetria derivada, não digitada."""
    gravados = _caminhos_gravados()
    assert gravados == {ALVO, REGRA}, gravados

    texto = UNINSTALL.read_text(encoding="utf-8")
    for caminho in sorted(gravados):
        assert re.search(rf"sudo rm -f[^\n]*{re.escape(caminho)}", texto), (
            f"o uninstall.sh não remove {caminho}"
        )


def test_o_uninstall_pede_sudo_quando_a_ponte_existe() -> None:
    """Sem entrar na conta do `_NEEDS_SUDO`, o bloco de remoção nem roda."""
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert re.search(rf"\[\[ -e {re.escape(REGRA)} \]\] && _NEEDS_SUDO=1", texto)
    assert re.search(rf"\[\[ -e {re.escape(ALVO)} \]\] && _NEEDS_SUDO=1", texto)


def test_o_uninstall_avisa_quando_nao_consegue_tirar_a_ponte() -> None:
    """Sem sudo, o privilégio FICA — e isso tem de ser dito, com a receita."""
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert "ponte privilegiada FICOU" in texto
    assert f"sudo rm {REGRA} {ALVO}" in texto
