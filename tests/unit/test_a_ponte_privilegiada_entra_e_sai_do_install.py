"""A ponte privilegiada entra pelo install, sai pelo uninstall, e a regra é estreita.

Este arquivo cobra a INFRAESTRUTURA da ponte — o que o `install.sh` grava, o que
o `uninstall.sh` tira, e a forma do `/etc/sudoers.d/49-hefesto-bt-ponte`. A
validação de entrada do script está no arquivo irmão
(`test_a_ponte_privilegiada_recusa_entrada_suja.py`).

TRÊS COISAS QUE JÁ CUSTARAM CARO NESTA CASA, e que aqui viram portão:

  1. RESÍDUO DE PRIVILÉGIO. "SIMETRIA-INSTALL-02" mediu o que o install deixa
     para trás. Resíduo de `.desktop` é sujeira; resíduo de `sudoers.d` é
     privilégio de root concedido a um caminho que talvez nem exista mais;
  2. A CASA SABE E O PRODUTO NÃO FAZ. A regra pode estar perfeita no disco e o
     sudo não reconhecê-la. Por isso o install pergunta ao PRÓPRIO sudo
     (`sudo -l`) em vez de se contentar com o arquivo gravado — e este portão
     cobra que ele pergunte;
  3. REGRA MAIS LARGA QUE O SCRIPT. O dono único do texto do sudoers é o verbo
     `regra-sudo` do próprio script. Se um verbo novo entrar no `case` e não na
     regra, a janela não o alcança; se entrar na regra e não no `case`, a regra
     está prometendo o que não existe. O teste da paridade abaixo lê as DUAS
     pontas por caminhos diferentes — o `case` por texto, a regra RODANDO o
     script — justamente para não iterar a mesma lista duas vezes.

PROVA DE MORDIDA (22/08/2026), quatro arrancadas, todas devolvidas em seguida
(controle: 15 verdes):

  a) apagada da regra a linha do `descobrir` com `[0-9][0-9]` — reprovou
     `test_a_regra_cobre_uma_janela_de_busca_de_dois_digitos`. É a arrancada
     mais sutil: a regra continua válida no `visudo -c`, e o buraco só
     apareceria no dia em que alguém pedisse uma janela de 30 segundos;
  b) trocada a forma do MAC por `*` — **2 reprovações**:
     `test_a_regra_nao_tem_curinga` e `test_a_regra_so_aceita_mac_com_forma_de_mac`;
  c) apagado do `uninstall.sh` o `rm` de `/etc/sudoers.d/49-hefesto-bt-ponte` —
     reprovou `test_tudo_que_o_install_grava_o_uninstall_tira`, nomeando o
     caminho que ficou para trás;
  d) invertida no `install.sh` a ordem `visudo -cqf` / `install -Dm440` —
     reprovou `test_nada_vai_para_o_sudoers_sem_passar_pelo_visudo`
     (`assert 2696 < 2389`).
"""
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

#: Verbos que existem no `case` mas NÃO entram na regra, com a razão. Manter
#: curto: cada entrada aqui é um verbo que a janela não vai conseguir chamar.
FORA_DA_REGRA = {
    #: gera texto, não muda nada, e é o install quem o roda — nunca a janela.
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
    """O corpo da função com os `local X=/caminho` já substituídos.

    O `install.sh` escreve os caminhos UMA vez, no topo da função, e usa
    `${_ponte_regra}` depois — que é o certo. Uma régua que procurasse o
    literal na linha do `install -Dm440` não acharia nada e passaria verde por
    vacuidade. Aqui a expansão é feita antes de medir.
    """
    corpo = _corpo_da_funcao(texto_do_instalador(), FUNCAO)
    for nome, valor in re.findall(r'^\s*local (\w+)=([^\s"]+)$', corpo, re.M):
        corpo = corpo.replace("${" + nome + "}", valor)
    return corpo


def _caminhos_gravados() -> set[str]:
    """Só o que o install de fato ESCREVE — as linhas de `install -D`.

    Recortar por linha de escrita, em vez de varrer o corpo inteiro, evita
    contar caminho que aparece só dentro de mensagem de aviso.
    """
    achados: set[str] = set()
    for linha in _corpo_expandido().splitlines():
        if "install -D" not in linha:
            continue
        achados.update(re.findall(r"/(?:etc|usr/local)/[\w./-]+", linha))
    return achados


def _regra(usuaria: str = USUARIA) -> str:
    env = dict(os.environ)
    env["HEFESTO_BT_LOG_DEST"] = "none"
    #: Alvo fixo: é o próprio script sob teste, nunca um comando montado.
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
    """Os rótulos do `case` de despacho — a lista REAL de verbos do script.

    Lidos do texto do script, não digitados aqui: uma lista digitada mediria
    apenas a si mesma. O recorte é o bloco entre `case "${VERBO}" in` e o
    `esac`, e cada rótulo é o que vem antes do `)` numa linha de rótulo.
    """
    texto = PONTE.read_text(encoding="utf-8")
    bloco = texto[texto.index('case "${VERBO}" in') : texto.rindex("esac")]
    rotulos: set[str] = set()
    for linha in bloco.splitlines():
        casado = re.match(r"^\s{4}([A-Za-z0-9|_-]+)\)\s*$", linha)
        if casado:
            rotulos.update(casado.group(1).split("|"))
    return rotulos


# --- a regra do sudoers -----------------------------------------------------


def test_o_case_tem_os_verbos_que_o_cabecalho_promete() -> None:
    """Trava de encolhimento: se o parser do `case` quebrar, tudo abaixo vira vácuo.

    Um portão que lê zero verbos passa verde em qualquer coisa. Esta é a única
    lista digitada deste arquivo, e existe só para provar que a leitura funciona.
    """
    verbos = _verbos_do_case()
    assert {"adaptadores", "bonds", "renomear", "esquecer", "descobrir", "parear"} <= verbos


def test_todo_verbo_que_muda_algo_esta_na_regra_do_sudoers() -> None:
    """Paridade entre o `case` (texto) e a regra (script rodando).

    As duas pontas vêm por caminhos diferentes de propósito. Verbo novo no
    `case` sem entrada na regra = botão que pede senha; entrada na regra sem
    verbo = promessa vazia.
    """
    regra = _regra()
    for verbo in sorted(_verbos_do_case() - FORA_DA_REGRA):
        assert f"{ALVO} {verbo}" in regra, f"o verbo '{verbo}' não está na regra do sudoers"
    #: E o contrário: a regra não pode citar verbo que o `case` não conhece.
    citados = set(re.findall(rf"{re.escape(ALVO)} ([a-z-]+)", regra))
    assert citados <= _verbos_do_case()


def test_a_regra_nao_tem_curinga() -> None:
    """`*` no sudoers casa espaço em branco — é como NOPASSWD estreito vira largo.

    Só as linhas de comando importam: os comentários em português podem ter o
    que quiserem.
    """
    for linha in _regra().splitlines():
        if ALVO not in linha:
            continue
        assert "*" not in linha, f"curinga na regra: {linha.strip()}"
        assert "?" not in linha, f"curinga de um caractere na regra: {linha.strip()}"


def test_a_regra_so_aceita_mac_com_forma_de_mac() -> None:
    """Cada posição de MAC é seis pares de classe hexadecimal, e nada mais."""
    par = re.escape(r"[0-9A-Fa-f][0-9A-Fa-f]")
    forma = par + (re.escape(r"\:") + par) * 5
    regra = _regra()
    for verbo in ("bonds", "renomear"):
        assert re.search(rf"{re.escape(ALVO)} {verbo} {forma},", regra), verbo
    for verbo in ("esquecer", "parear"):
        assert re.search(rf"{re.escape(ALVO)} {verbo} {forma} {forma},", regra), verbo


def test_a_regra_cobre_uma_janela_de_busca_de_dois_digitos() -> None:
    """`descobrir` recebe segundos, e 1, 2 e 3 dígitos precisam de linha própria.

    Sem curinga, cada largura é uma entrada. Faltando a de dois dígitos, a
    janela pediria senha justamente no caso comum (`descobrir <MAC> 30`).
    """
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
    """Caminho na regra ≠ caminho instalado = NOPASSWD que nunca casa.

    Os dois lados são lidos das suas fontes: a regra rodando o script, o
    caminho instalado do corpo da função do `install.sh`.
    """
    caminhos = {c for c in _caminhos_gravados() if c.startswith("/usr/local/")}
    assert caminhos == {ALVO}, caminhos
    assert ALVO in _regra()


@pytest.mark.skipif(shutil.which("visudo") is None, reason="visudo ausente nesta máquina")
def test_a_regra_gerada_passa_no_visudo(tmp_path: Path) -> None:
    """Sudoers inválido derruba o sudo da máquina INTEIRA — inclusive o que
    consertaria. O install nunca grava sem esta conferência; aqui ela roda sobre
    o texto de verdade, com um nome de usuária de verdade.
    """
    arquivo = tmp_path / "49-hefesto-bt-ponte"
    arquivo.write_text(_regra(), encoding="utf-8")
    #: Binário do sistema, argumentos nossos.
    resultado = subprocess.run(
        ["visudo", "-cqf", str(arquivo)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


# --- o que o install faz ----------------------------------------------------


def test_nada_vai_para_o_sudoers_sem_passar_pelo_visudo() -> None:
    """A ordem importa: conferir DEPOIS de gravar não conserta nada."""
    corpo = _corpo_expandido()
    assert "visudo" in corpo, "a função não confere o sudoers antes de gravá-lo"
    posicao_visudo = corpo.index("visudo -cqf")
    grava = re.search(rf"install -Dm440[^\n]*{re.escape(REGRA)}", corpo)
    assert grava is not None, "a função não grava a regra em " + REGRA
    posicao_grava = grava.start()
    assert posicao_visudo < posicao_grava, "o visudo -c roda DEPOIS da gravação"
    #: E a ausência do visudo tem de ABORTAR o passo, não seguir em frente.
    assert "command -v visudo" in corpo


def test_o_install_confere_no_proprio_sudo_e_nao_so_no_disco() -> None:
    """"A casa sabe e o produto não faz" — arquivo gravado não é permissão dada.

    `#includedir` ausente do `/etc/sudoers`, nome de arquivo com ponto, ordem de
    leitura: há três jeitos de o arquivo existir e a regra não valer. Quem sabe
    responder é o sudo.
    """
    corpo = _corpo_da_funcao(texto_do_instalador(), FUNCAO)
    assert re.search(r"sudo -n -l -U", corpo), "o install não pergunta ao sudo se a regra pegou"


def test_o_install_grava_o_sudoers_com_o_modo_que_o_sudo_exige() -> None:
    """0440 root:root. Com qualquer outro modo o sudo ignora o arquivo calado."""
    corpo = _corpo_expandido()
    assert re.search(rf"install -Dm440 -o root -g root .*{re.escape(REGRA)}", corpo)
    #: E o helper é root:root 755 — se a usuária pudesse escrevê-lo, o NOPASSWD
    #: sobre ele seria root para qualquer coisa.
    assert re.search(rf"install -Dm755 -o root -g root .*{re.escape(ALVO)}", corpo)


def test_o_install_nao_abre_a_ponte_para_root() -> None:
    """Sem saber para QUEM, não se grava regra nenhuma."""
    corpo = _corpo_da_funcao(texto_do_instalador(), FUNCAO)
    assert 'SUDO_USER:-$(id -un)' in corpo
    assert '== "root"' in corpo


# --- o que o uninstall desfaz -----------------------------------------------


def test_tudo_que_o_install_grava_o_uninstall_tira() -> None:
    """Simetria derivada, não digitada.

    Os caminhos absolutos saem do CORPO da função do install; o uninstall tem
    de citar cada um deles num `rm`. Caminho novo no install sem saída no
    uninstall reprova sozinho, que é o ponto.
    """
    gravados = _caminhos_gravados()
    assert gravados == {ALVO, REGRA}, gravados

    texto = UNINSTALL.read_text(encoding="utf-8")
    for caminho in sorted(gravados):
        assert re.search(rf"sudo rm -f[^\n]*{re.escape(caminho)}", texto), (
            f"o uninstall.sh não remove {caminho}"
        )


def test_o_uninstall_pede_sudo_quando_a_ponte_existe() -> None:
    """Sem entrar na conta do `_NEEDS_SUDO`, o bloco de remoção nem roda.

    É o modo silencioso de deixar resíduo: o uninstall termina "com sucesso" e o
    privilégio fica no disco.
    """
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert re.search(rf"\[\[ -e {re.escape(REGRA)} \]\] && _NEEDS_SUDO=1", texto)
    assert re.search(rf"\[\[ -e {re.escape(ALVO)} \]\] && _NEEDS_SUDO=1", texto)


def test_o_uninstall_avisa_quando_nao_consegue_tirar_a_ponte() -> None:
    """Sem sudo, o privilégio FICA — e isso tem de ser dito, com a receita."""
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert "ponte privilegiada FICOU" in texto
    assert f"sudo rm {REGRA} {ALVO}" in texto
