"""A bandeja do produto é o TRAY, e ele sobe sozinho — 19/09/2026.

Decisão dela: *"desabilitamos o applet pela complexidade. o tray faz o mesmo
mas melhor."*

A troca tem DUAS metades, e uma sozinha estraga o produto:

1. o applet sai do default do `install.sh` — senão a decisão dela não chega a
   máquina nenhuma;
2. o tray ganha autostart — senão a barra dela fica VAZIA, porque o applet era
   plugin do `cosmic-panel` (subia com a sessão) e o tray é processo comum.

Estas réguas medem as duas, e medem o ARQUIVO, não a intenção.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"
RUN = RAIZ / "run.sh"
AUTOSTART = RAIZ / "packaging" / "hefesto-dualsense4unix-tray.desktop"


def _chaves(texto: str) -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in texto.splitlines():
        if linha.startswith("#") or "=" not in linha or linha.startswith("["):
            continue
        chave, _, valor = linha.partition("=")
        saida[chave.strip()] = valor.strip()
    return saida


def test_o_autostart_do_tray_existe_versionado() -> None:
    assert AUTOSTART.is_file(), (
        f"{AUTOSTART.relative_to(RAIZ)} não existe. Sem ele o `install.sh` não "
        "tem o que copiar, e a barra dela fica vazia depois de o applet sair."
    )


def test_o_autostart_chama_o_tray_e_nao_a_janela() -> None:
    chaves = _chaves(AUTOSTART.read_text(encoding="utf-8"))
    exec_ = chaves.get("Exec", "")
    assert "--tray" in exec_, (
        f"o Exec= do autostart é {exec_!r} e não pede o tray. Um autostart que "
        "abre a JANELA faria a interface inteira nascer a cada login — na "
        "frente dela."
    )
    assert "@RAIZ@" in exec_, (
        "o arquivo versionado tem de trazer @RAIZ@; caminho de máquina aqui "
        "quebra na máquina de qualquer outra pessoa."
    )


def test_o_autostart_valida_limpo() -> None:
    if not shutil.which("desktop-file-validate"):
        return
    fim = subprocess.run(
        ["desktop-file-validate", str(AUTOSTART)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert not fim.stdout.strip() and not fim.stderr.strip(), (
        "o validador reclamou do autostart — e ele decide pela SAÍDA, não pelo "
        f"rc (que é 0 mesmo com aviso):\n{fim.stdout}{fim.stderr}"
    )


def test_o_install_escreve_o_autostart() -> None:
    texto = INSTALL.read_text(encoding="utf-8")
    assert '_AUTOSTART_TARGET="${_AUTOSTART_DIR}/${APP_ID}-tray.desktop"' in texto, (
        "o install.sh não escreve o autostart do tray. Tirar o applet sem isto "
        "deixa a barra dela vazia."
    )
    assert "${ROOT_DIR}/packaging/${APP_ID}-tray.desktop" in texto, (
        "o install.sh tem de COPIAR o arquivo versionado, e não escrever um "
        ".desktop à mão — foi assim que o GenericName existiu num e não no "
        "outro."
    )


def test_o_uninstall_remove_o_autostart() -> None:
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert 'AUTOSTART_TARGET="${HOME}/.config/autostart/' in texto, (
        "o uninstall.sh não conhece o autostart — o tray voltaria a subir em "
        "toda sessão depois de o produto ter sido desinstalado."
    )
    assert '"${AUTOSTART_TARGET}"' in texto.split("for path in", 1)[-1], (
        "a constante existe mas ninguém a remove."
    )


def test_o_run_sh_entende_tray() -> None:
    texto = RUN.read_text(encoding="utf-8")
    assert '--tray)   MODE="tray"' in texto, "o run.sh não entende --tray"
    assert 'if [[ "$MODE" == "tray" ]]; then' in texto, (
        "o run.sh aceita --tray mas não faz nada com ele — cairia no modo gui "
        "e abriria a JANELA a cada login."
    )


def test_o_applet_so_entra_quando_pedido() -> None:
    texto = INSTALL.read_text(encoding="utf-8")
    condicao = re.search(
        r"^if \[\[ \"\$\{ENABLE_COSMIC_APPLET\}\".*?^fi$",
        texto,
        re.M | re.S,
    )
    assert condicao, (
        "não achei a condição do passo 9 começando por ENABLE_COSMIC_APPLET. "
        "Ela é o que aposenta o applet: antes de 19/09 ela começava por "
        "DISABLE_ e tinha DESKTOP_IS_COSMIC no meio."
    )
    corpo = condicao.group(0)
    assert "DESKTOP_IS_COSMIC" not in corpo, (
        "DESKTOP_IS_COSMIC voltou à condição do applet — com ele, a máquina "
        "DELA instala o applet de novo a cada install, que é exatamente o que "
        "ela mandou parar."
    )
    assert "_applet_installed" not in corpo, (
        "o braço `_applet_installed` voltou: uma vez instalado, o applet se "
        "reinstalaria para sempre, inclusive depois de ela mandar parar."
    )


def test_o_applet_ja_instalado_e_anunciado_e_nao_apagado() -> None:
    texto = INSTALL.read_text(encoding="utf-8")
    assert 'há um applet instalado de antes' in texto, (
        "o install não avisa sobre um applet parado de antes. Binário parado "
        "não se anuncia, e dois ícones na barra seriam lidos como defeito novo."
    )
    passo9 = texto.split('step "9/11"', 1)[-1].split('step "10/', 1)[0]
    # Um `rm` EXECUTADO, não a palavra: o passo 9 IMPRIME a linha `sudo rm ...`
    # para ela copiar, e isso é o contrário de apagar sozinho.
    executa = [
        linha
        for linha in passo9.splitlines()
        if re.match(r"\s*(sudo\s+)?rm\b", linha) and not linha.lstrip().startswith("#")
    ]
    assert not executa, (
        "o passo 9 apagando arquivo: o install não desfaz o que não instalou "
        f"nesta corrida. A remoção é do ./uninstall.sh.\n{executa}"
    )


# ---------------------------------------------------------------------------
# O DOCTOR MEDE A BANDEJA, e não a saúde de um componente aposentado
# ---------------------------------------------------------------------------
# O `check_applet` auditava o `.desktop` do applet COSMIC — com um `fail`
# armado. Depois de 19/09 isso derrubaria o diagnóstico de quem tivesse o
# binário velho parado no disco, por um componente que ninguém deve usar.
#
# Medido na máquina dela em 19/09: o diagnóstico caiu de 9 avisos para 7, e os
# dois que saíram eram exatamente as duas linhas do validador sobre o
# `Categories=COSMIC;` do applet instalado em 16h30.

DOCTOR = RAIZ / "scripts" / "doctor.sh"


def test_o_doctor_mede_a_bandeja_e_nao_audita_o_applet() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    assert "check_bandeja()" in texto, "a função check_bandeja não existe"
    chamadas = [
        linha
        for linha in texto.splitlines()
        if "check_applet" in linha and not linha.lstrip().startswith("#")
    ]
    assert not chamadas, (
        "check_applet ainda é chamado — ele audita um componente aposentado, "
        f"e tinha um `fail` armado:\n{chamadas}"
    )


def test_o_check_da_bandeja_mede_os_tres_elos() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    corpo = texto.split("check_bandeja() {", 1)[-1].split("\n}\n", 1)[0]
    for agulha, porque in (
        (
            "autostart/hefesto-dualsense4unix-tray.desktop",
            "sem o autostart o ícone não sobe no login",
        ),
        (
            "org.kde.StatusNotifierWatcher",
            "sem o hospedeiro o ícone não tem onde aparecer",
        ),
        ("pgrep", "e o terceiro elo é o processo estar de pé"),
    ):
        assert agulha in corpo, f"check_bandeja não mede {agulha!r}: {porque}"


def test_o_applet_parado_e_recado_e_nunca_falha() -> None:
    texto = DOCTOR.read_text(encoding="utf-8")
    corpo = texto.split("check_bandeja() {", 1)[-1].split("\n}\n", 1)[0]
    trecho = corpo.split("APPLET_DESKTOP", 1)[-1]
    assert "fail " not in trecho, (
        "um applet aposentado parado no disco não pode derrubar o diagnóstico "
        "dela — o recado é `info`, com a linha para remover."
    )
    assert "./uninstall.sh" in trecho, (
        "o recado tem de dizer COMO remover; binário parado não se anuncia."
    )


# ---------------------------------------------------------------------------
# A FLAG QUE TIRA SÓ O RESTO — `--so-o-applet`, 19/09/2026
# ---------------------------------------------------------------------------
# Pedido dela depois de o passo 9 do install passar a apenas ANUNCIAR o binário
# parado: *"Cria a flag"*. Sem ela, tirar 23 MB de applet exigia o uninstall
# INTEIRO — que para o daemon, apaga as regras udev, desliga o Steam Input e
# derruba o DKMS. Pagar o preço do wipe por um resto é o que faz a pessoa
# deixar o resto lá.


def test_a_flag_do_applet_existe_e_e_anunciada() -> None:
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert "--so-o-applet)" in texto, "o parser não conhece --so-o-applet"
    assert "SO_O_APPLET=0" in texto, (
        "a flag precisa de default explícito; sob `set -u` uma variável não "
        "declarada mata o script em quem NÃO passou a flag."
    )
    ajuda = texto.split("FIM\n}", 1)[0]
    assert "--so-o-applet" in ajuda, "a flag não aparece no --help"


def test_a_flag_sai_antes_de_o_wipe_comecar() -> None:
    texto = UNINSTALL.read_text(encoding="utf-8")
    saida = texto.index('if [[ "${SO_O_APPLET}" -eq 1 ]]; then')
    for marco, porque in (
        ('log "parando daemon', "o daemon dela seria parado"),
        ('log "matando processos hefesto', "os processos seriam mortos"),
        ("removendo ${path}", "os arquivos dela sairiam do disco"),
    ):
        onde = texto.index(marco)
        assert saida < onde, (
            f"o early-exit de --so-o-applet vem DEPOIS de {marco!r}: {porque}. "
            "Meio wipe é pior que wipe nenhum."
        )


def test_a_flag_e_o_wipe_usam_a_mesma_funcao() -> None:
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert texto.count("remover_o_applet() {") == 1, (
        "duas definições de remover_o_applet — uma delas vai divergir"
    )
    chamadas = len(
        [
            linha
            for linha in texto.splitlines()
            if linha.strip() == "remover_o_applet"
        ]
    )
    assert chamadas == 2, (
        f"remover_o_applet é chamada {chamadas}x; esperadas 2 (o --so-o-applet "
        "e o wipe completo). Duplicar a lista dos cinco caminhos é como o "
        "ícone simbólico já ficou para trás uma vez."
    )


def test_o_painel_so_e_derrubado_se_o_applet_estiver_na_lista() -> None:
    texto = UNINSTALL.read_text(encoding="utf-8")
    corpo = texto.split("remover_o_applet() {", 1)[-1].split("\n}\n", 1)[0]
    assert "killall cosmic-panel" in corpo, (
        "sem recarregar o painel, o applet fica fantasma na lista de "
        "Miniaplicativos mesmo depois de os arquivos saírem."
    )
    guarda = corpo.split("killall cosmic-panel", 1)[0]
    assert "esta_na_lista" in guarda, (
        "o painel dela é derrubado CEGO: bastava o binário existir. Na máquina "
        "dela o applet nunca esteve na lista, então não há fantasma a limpar — "
        "e derrubar o painel de quem está usando a máquina é caro."
    )
