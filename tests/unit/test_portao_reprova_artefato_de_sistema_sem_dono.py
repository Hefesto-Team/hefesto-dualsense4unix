"""O portão reprova artefato de sistema que nenhum caminho de instalação alcança.

`A-CASA-SABE-E-O-PRODUTO-NAO-FAZ-01` — a seção "artefato de sistema sem dono" de
`scripts/check_packaging_parity.sh`.

MEDIDO em 12/08/2026, antes de a seção existir: das dezessete seções daquele
portão, só DUAS eram genéricas — o laço das regras udev e o das confs de
modprobe. As outras quinze eram blocos escritos à mão, um por cura já paga. O
furo que sobrava: as TREZE unidades systemd de `assets/` e `assets/systemd/` não
tinham laço nenhum (só o broker era citado, à mão), e o mesmo valia para
`assets/wireplumber/`, `assets/NetworkManager/` e `assets/appimage/`. Uma unit
nova entrava na árvore e instalador nenhum era cobrado por ela.

O que estes testes seguram é o PORTÃO, não o instalador: um artefato de mentira
sem dono tem de fazer o script sair != 0, e — tão importante quanto — os três
caminhos legítimos de alcance têm de continuar contando, senão a seção grita com
quem está certo e é desligada na primeira semana.

Técnica: a mesma de `tests/unit/test_check_packaging_parity.py` — pytest +
subprocess num repo fake em `tmp_path`, sem bats-core e sem depender do estado do
repositório real.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_REL_PATH = "scripts/check_packaging_parity.sh"

#: Cabeçalho da seção: é por ele que os testes recortam a saída, para não
#: confundir um [FAIL] desta seção com o de qualquer outra.
CABECALHO = "== artefato de sistema sem dono"

#: O artefato de mentira. `.service` de propósito: unidade systemd é justamente
#: a família que não tinha laço nenhum antes desta seção.
ARTEFATO = "assets/systemd/hefesto-artefato-de-mentira.service"


def _semeia_simbolico(raiz: Path) -> None:
    """O par de simbólicos que a seção do applet exige (APPLET-MONOCROMÁTICO-01).

    Sem eles, todo caso de "passa" reprovaria por uma seção que não é o alvo
    daqui — e a saída começaria a acusar no lugar errado.
    """
    desenho = '<svg viewBox="0 0 16 16"><title>fake</title></svg>\n'
    alvos = (
        raiz / "assets" / "simbolico" / "hefesto-dualsense4unix-symbolic.svg",
        raiz
        / "packaging"
        / "cosmic-applet"
        / "data"
        / "icons"
        / "hicolor"
        / "symbolic"
        / "apps"
        / "com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg",
    )
    for alvo in alvos:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(desenho, encoding="utf-8")


@pytest.fixture
def repo_com_artefato(tmp_path: Path) -> Path:
    """Repo fake mínimo: o script, um `install.sh` e UM artefato de sistema.

    Nasce SEM dono de propósito — cada teste escreve o caminho de alcance que
    quer exercitar. Não há regra udev nem conf de modprobe aqui: as duas
    famílias são delegadas aos laços genéricos que já existiam, e um repo com
    elas faria a saída falar de outra seção.
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    (tmp_path / "scripts").mkdir()
    (tmp_path / "assets" / "systemd").mkdir(parents=True)
    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    (tmp_path / ARTEFATO).write_text(
        "[Unit]\nDescription=artefato de mentira\n", encoding="utf-8"
    )
    (tmp_path / "install.sh").write_text("# instalador de mentira\n", encoding="utf-8")
    (tmp_path / "uninstall.sh").write_text("# removedor de mentira\n", encoding="utf-8")
    _semeia_simbolico(tmp_path)
    return tmp_path


def roda(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def secao(saida: str) -> str:
    """Recorta só o pedaço desta seção — o resto da saída não é assunto daqui."""
    partes = saida.split(CABECALHO, 1)
    assert len(partes) == 2, f"seção ausente na saída do script:\n{saida}"
    return partes[1].split("─", 1)[0]


def test_artefato_sem_nenhum_dono_reprova_nomeando_o_arquivo(
    repo_com_artefato: Path,
) -> None:
    """A MORDIDA: unit versionada que instalador nenhum alcança derruba o portão.

    Era exatamente isto que passava batido: `assets/systemd/` não estava sob
    laço nenhum, e só o broker era citado à mão.
    """
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    corpo = secao(resultado.stdout)
    assert f"[FAIL] {ARTEFATO}" in corpo, corpo
    # A mensagem tem de dizer o que FAZER, não só o que está errado.
    assert "ESCREVA a instalação dele" in corpo, corpo
    assert "_ARTEFATO_SEM_DONO_HOJE" in corpo, corpo


def test_dono_pelo_nome_no_install_passa(repo_com_artefato: Path) -> None:
    (repo_com_artefato / "install.sh").write_text(
        'sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout
    assert "[ OK ] artefatos de sistema: 1 com dono" in secao(resultado.stdout)


def test_dono_pelo_diretorio_copiado_inteiro_passa(repo_com_artefato: Path) -> None:
    """Um `cp -r assets/systemd` serve todo arquivo de lá — e tem de contar.

    É o caso real do `scripts/build_appimage.sh:56` (`cp -r "$APPDIR_SRC/."`),
    que é o único dono do `.desktop` de `assets/appimage/`. Sem este caminho, o
    portão nasceria acusando quem está instalado.
    """
    (repo_com_artefato / "install.sh").write_text(
        'cp -r "${ROOT_DIR}/assets/systemd" "${STAGING}/etc/systemd/system/"\n',
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout


def test_dono_por_glob_do_diretorio_passa(repo_com_artefato: Path) -> None:
    """Idem para o laço por glob — o molde do `assets/[0-9][0-9]-*.rules`."""
    (repo_com_artefato / "install.sh").write_text(
        'for u in "${ROOT_DIR}/assets/systemd/"*.service; do\n'
        '    sudo install -Dm644 "${u}" "/etc/systemd/system/$(basename "${u}")"\n'
        "done\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout


def test_diretorio_citado_com_o_nome_vindo_de_variavel_nao_conta(
    repo_com_artefato: Path,
) -> None:
    """O VÁCUO que esta seção não pode ter, e que o primeiro desenho tinha.

    `install.sh:1733` instala `assets/systemd/${_btres_u}` — o diretório aparece
    inteiro no texto, mas quem escolhe o arquivo é a variável, e ela percorre
    uma lista de QUATRO nomes. Um `grep` de prefixo daria alcance de graça a
    todo arquivo de `assets/systemd/` — inclusive a unit que ninguém instala,
    que é justamente o defeito que esta seção existe para acusar.
    """
    (repo_com_artefato / "install.sh").write_text(
        "for u in hefesto-outra.service hefesto-terceira.service; do\n"
        '    sudo install -Dm644 "${ROOT_DIR}/assets/systemd/${u}" \\\n'
        '        "/etc/systemd/system/${u}"\n'
        "done\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    assert f"[FAIL] {ARTEFATO}" in secao(resultado.stdout)


def test_citacao_so_em_comentario_nao_conta(repo_com_artefato: Path) -> None:
    """Só linha de CÓDIGO conta — a armadilha do `grep -qF FastConnectable`.

    Um comentário que EXPLICA a instalação satisfaria um grep ingênuo, e o
    portão viraria decoração no dia em que a instalação fosse arrancada e o
    comentário ficasse para trás.
    """
    (repo_com_artefato / "install.sh").write_text(
        "# instala assets/systemd/hefesto-artefato-de-mentira.service\n"
        "# (o passo foi arrancado numa refatoração e este comentário sobrou)\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    assert f"[FAIL] {ARTEFATO}" in secao(resultado.stdout)


def test_dono_por_helper_de_scripts_que_o_install_chama_passa(
    repo_com_artefato: Path,
) -> None:
    """Caminho 3: quem instala é o helper, e o install só o chama.

    Caso real de `assets/wireplumber/5{1,2,3}-*.conf`, instalados por
    `scripts/fix_wireplumber_default_source.sh` (install.sh:1139 e :1143).
    """
    (repo_com_artefato / "scripts" / "instala_unit.sh").write_text(
        'sudo install -Dm644 "assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    (repo_com_artefato / "install.sh").write_text(
        'bash "${ROOT_DIR}/scripts/instala_unit.sh"\n', encoding="utf-8"
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout


def test_helper_que_o_install_nao_chama_nao_conta(repo_com_artefato: Path) -> None:
    """Helper existente e nunca chamado não instala nada — é o mesmo defeito.

    A casa já pagou por isto: a cura escrita e nunca ligada
    (`ENTREGA-QUE-NAO-LIGOU-01`). Um helper solto em `scripts/` que cita o
    arquivo prova só que alguém escreveu o passo, não que ele roda.
    """
    (repo_com_artefato / "scripts" / "instala_unit.sh").write_text(
        'sudo install -Dm644 "assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    assert f"[FAIL] {ARTEFATO}" in secao(resultado.stdout)


def test_arte_nao_e_artefato_de_sistema(repo_com_artefato: Path) -> None:
    """Um PNG/SVG solto não é cobrado aqui — o portão de ícones já o cobra.

    A régua desta seção é o arquivo que o produto põe num lugar do SISTEMA e que
    um programa de fora do Hefesto lê. Cobrar arte aqui duplicaria a seção de
    ícones e daria dois veredictos sobre o mesmo arquivo.
    """
    (repo_com_artefato / "install.sh").write_text(
        'sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    (repo_com_artefato / "assets" / "sem-dono-nenhum.png").write_bytes(b"\x89PNG\r\n")
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout
    assert "sem-dono-nenhum.png" not in resultado.stdout


def test_regra_udev_e_delegada_ao_laco_que_ja_existia(
    repo_com_artefato: Path,
) -> None:
    """Sem contar duas vezes: `.rules` e modprobe ficam com os laços genéricos.

    Eles já são cobrados lá com régua MAIS dura (paridade em todo instalador,
    não "alguém instala"). Repetir aqui daria duas linhas para o mesmo arquivo e
    dois veredictos diferentes — a `75-*.rules` é opt-in por decisão registrada
    e apareceria aqui como coberta, ensinando a ler o portão errado.
    """
    (repo_com_artefato / "install.sh").write_text(
        'sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    (repo_com_artefato / "assets" / "89-orfa-de-mentira.rules").write_text(
        'ACTION=="add", SUBSYSTEM=="hidraw", MODE="0660"\n', encoding="utf-8"
    )
    resultado = roda(repo_com_artefato)
    corpo = secao(resultado.stdout)
    assert "89-orfa-de-mentira.rules" not in corpo, corpo
    assert "+1 nos laços de udev/modprobe acima" in corpo, corpo


def test_lacuna_declarada_cala_o_portao_e_nao_envelhece_calada(
    repo_com_artefato: Path,
) -> None:
    """Declarar é honesto — e a lápide reprova no dia em que a dívida é paga.

    Sem a segunda metade, `_ARTEFATO_SEM_DONO_HOJE` viraria o lugar onde se
    esconde o que incomoda, e a próxima pessoa leria a lista como se fosse a
    dívida de hoje.
    """
    script = repo_com_artefato / SCRIPT_REL_PATH
    texto = script.read_text(encoding="utf-8")
    assert "_ARTEFATO_SEM_DONO_HOJE=()" in texto, "a lista mudou de forma"
    script.write_text(
        texto.replace(
            "_ARTEFATO_SEM_DONO_HOJE=()",
            f'_ARTEFATO_SEM_DONO_HOJE=(\n    "{ARTEFATO}:razão de mentira, 12/08/2026"\n)',
        ),
        encoding="utf-8",
    )

    # Declarado e ainda órfão: o portão cala.
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout
    assert "1 lacuna(s) declarada(s)" in secao(resultado.stdout)

    # Dívida paga e lápide esquecida: o portão cobra a limpeza.
    (repo_com_artefato / "install.sh").write_text(
        'sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    corpo = secao(resultado.stdout)
    assert "lacuna declarada que já não vale" in corpo, corpo
    assert "ganhou dono" in corpo, corpo


def test_checkout_sem_install_fica_silencioso(repo_com_artefato: Path) -> None:
    """Sem instalador não há quem julgar — a seção cala, e não acusa.

    Mesmo critério de "gateado pelo asset" das seções acima, do lado do DONO em
    vez do lado do artefato: os repositórios sintéticos dos outros testes deste
    portão trazem só `assets/` e `scripts/`, e cobrar deles a instalação de um
    asset de mentira seria o portão acusando o instrumento, não o produto.
    """
    (repo_com_artefato / "install.sh").unlink()
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout
    corpo = secao(resultado.stdout)
    assert "[FAIL]" not in corpo, corpo
    assert "sem install.sh neste checkout" in corpo, corpo


def test_no_repo_real_a_secao_esta_verde() -> None:
    """Na árvore de verdade, nenhum artefato de sistema está órfão.

    MEDIDO em 12/08/2026: 46 artefatos (`.rules .service .timer .path .socket
    .conf .desktop .policy`), 26 nesta seção e 20 delegados aos laços de
    udev/modprobe, ZERO órfãos. A seção não cobra dívida velha — ela impede a
    próxima.
    """
    repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / SCRIPT_REL_PATH).exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")
    resultado = subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    corpo = secao(resultado.stdout)
    assert "[FAIL]" not in corpo, corpo
    assert "[ OK ] artefatos de sistema:" in corpo, corpo
