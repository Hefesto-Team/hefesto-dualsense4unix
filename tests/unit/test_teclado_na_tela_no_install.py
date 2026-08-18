"""TECLADO-QUE-NAO-DIGITA-01 — o teclado na tela passa a ser do PRODUTO.

O DEFEITO, medido na máquina dela em 09-10/08/2026:

    command -v onboard wvkbd-mobintl         ->  NENHUM DOS DOIS
    grep -c onboard install.sh               ->  0
    grep -c onboard packaging/debian/control ->  0

O mapa de fábrica do teclado emulado dá ao L3 o token ``__OPEN_OSK__``
(``core/keyboard_mappings.py``) e o daemon o cumpre abrindo um teclado na tela
do SISTEMA (``daemon/subsystems/keyboard.py``). Só que nenhum instalador,
nenhum empacotamento e nenhum doctor desta casa o instalava, declarava ou
conferia. E o preço não é um gesto a menos: nenhum dos nove atalhos de fábrica
digita uma LETRA (Super, PrintScreen, Alt+Tab, Alt+Shift+Tab, Enter, Delete,
Backspace e os dois tokens de OSK), então sem o teclado na tela a frase "o
teclado emulado não digita" era literalmente verdade.

O pedido dela, em 10/08: *"pera, isso não deveria estar no install então? tipo
sem flag?"* — e a regra que ela fixou em 08/08: *"toda cura entra no install,
sem flag; nada à mão, nada opt-in"*.

O que este arquivo tranca, em quatro frentes:

1. o install instala em TODO formato — dos dois lados do ``exit 0`` que separa
   os formatos de pacote do fluxo native;
2. a ESCOLHA do programa segue a sessão gráfica, e segue igual nos três lugares
   que precisam concordar (instalador, doctor e daemon);
3. o doctor CONFERE e não cura, e distingue as quatro histórias que produzem o
   mesmo ``command -v`` vazio — a armadilha do commit 108b711;
4. o uninstall NÃO remove o pacote (é do sistema) e remove só a sentinela.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
DONO = RAIZ / "scripts" / "install_osk.sh"
KEYBOARD = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "subsystems" / "keyboard.py"

TEXTO_INSTALL = INSTALL.read_text(encoding="utf-8")
TEXTO_UNINSTALL = UNINSTALL.read_text(encoding="utf-8")


def _sem_comentarios(texto: str) -> str:
    """Descarta linhas de comentário.

    Não é preciosismo: nesta casa já houve portão satisfeito pelo próprio
    comentário que EXPLICAVA a regra (a seção do BlueZ em
    ``check_packaging_parity.sh`` documenta o caso). Só linha de código conta.
    """
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")
    )


# ---------------------------------------------------------------------------
# 1. O install instala — dos DOIS lados da cerca
# ---------------------------------------------------------------------------


class TestInstalaEmTodoFormato:
    """O `exit 0` do bloco de formatos é uma cerca, e ela já mordeu esta casa.

    `install.sh` faz `exit 0` quando `FORMAT != native`, e doze passos de cura
    ficam para trás. Foi o achado #7 da Onda S (o broker root hide-hidraw
    saía de flatpak/appimage/deb em silêncio) e é exatamente onde um passo novo
    cai se ninguém olhar de que lado da cerca ele está.
    """

    def _blocos(self) -> tuple[str, str]:
        codigo = _sem_comentarios(TEXTO_INSTALL)
        abertura = 'if [[ "${FORMAT}" != "native" ]]; then'
        i = codigo.index(abertura)
        resto = codigo[i:]
        # O bloco dos formatos termina no `exit 0` indentado; o `fi` de coluna
        # zero logo abaixo abre o fluxo native.
        fim = resto.index("\n    exit 0")
        return resto[:fim], resto[fim:]

    def test_o_dono_do_teclado_na_tela_existe(self) -> None:
        assert DONO.is_file(), (
            "scripts/install_osk.sh sumiu — a escolha do programa e o porquê "
            "medido ficariam sem dono, e os três consumidores divergiriam"
        )

    def test_formatos_de_pacote_instalam_o_teclado_na_tela(self) -> None:
        formatos, _ = self._blocos()
        assert re.search(r"^\s*install_osk_host\s*$", formatos, re.MULTILINE), (
            "flatpak/appimage/deb saem pelo 'exit 0' SEM o teclado na tela — "
            "o mesmo furo do broker (achado #7 da Onda S) numa camada nova"
        )

    def test_fluxo_native_instala_o_teclado_na_tela(self) -> None:
        _, native = self._blocos()
        assert re.search(r"^\s*install_osk_host\s*$", native, re.MULTILINE), (
            "o fluxo native — o padrão, o que ela usa — ficou sem o passo"
        )

    def test_e_default_sem_flag_nenhuma(self) -> None:
        """A regra dela de 08/08: nada opt-in.

        A guarda é sobre o SENTIDO da flag: `--no-osk` desliga; não pode
        existir um `--with-osk`/`--enable-osk` que ligue, porque isso seria
        opt-in com outro nome.
        """
        codigo = _sem_comentarios(TEXTO_INSTALL)
        assert "NO_OSK=0" in codigo, "o teclado na tela nasceria desligado"
        assert "--no-osk)" in codigo, "o opt-out não está no parser"
        for opt_in in ("--with-osk", "--enable-osk", "--with-teclado"):
            assert opt_in not in TEXTO_INSTALL, (
                f"{opt_in} transformaria a cura em opt-in — é o que ela recusou"
            )

    def test_o_no_osk_aparece_no_help(self) -> None:
        r = subprocess.run(
            [BASH, str(INSTALL), "--help"],
            capture_output=True, text=True, cwd=str(RAIZ), timeout=60,
        )
        assert r.returncode == 0, r.stderr
        assert "--no-osk" in r.stdout, (
            "flag REAL invisível no --help (BUG-INSTALL-HELP-TRUNCADO-01)"
        )


# ---------------------------------------------------------------------------
# 2. A escolha do programa — o critério, e os três que precisam concordar
# ---------------------------------------------------------------------------


def _roda_dono(
    tmp_path: Path, sessao: str, instalado: str = "nenhum"
) -> dict[str, str]:
    """Executa o dono em dry-run e devolve a sentinela lida como dicionário.

    Nada é instalado e nada da máquina é tocado: `HEFESTO_OSK_DRY_RUN=1` corta
    antes do gerenciador de pacotes, e a sentinela vai para o tmp do teste.

    `instalado` fecha o ÚLTIMO fio solto para a máquina real, e ele custou uma
    reprova: até 10/08/2026 o dublê deixava o `binario_instalado` ler o PATH de
    verdade, e no minuto seguinte ao `apt install wvkbd` na máquina dela o
    `resultado` virou `ja-instalado` — o mesmo teste, o mesmo código, veredito
    diferente porque o DISCO mudou. Um portão assim fica vermelho na máquina de
    quem trabalha e verde na CI, e é o que se aprende a desligar. O default
    "nenhum" é a máquina limpa, que é o cenário que estes testes descrevem.
    """
    sentinela = tmp_path / f"{sessao}.conf"
    env = dict(os.environ)
    env.update({
        "HEFESTO_OSK_STATE": str(sentinela),
        "HEFESTO_OSK_SESSAO": sessao,
        "HEFESTO_OSK_GERENCIADOR": "apt",
        "HEFESTO_OSK_INSTALADO": instalado,
        "HEFESTO_OSK_DRY_RUN": "1",
    })
    r = subprocess.run(
        [BASH, str(DONO)], capture_output=True, text=True, env=env, timeout=60,
    )
    assert r.returncode == 0, f"o dono tem de sair 0 sempre: {r.stderr}"
    return dict(
        linha.split("=", 1)
        for linha in sentinela.read_text(encoding="utf-8").splitlines()
        if "=" in linha and not linha.startswith("#")
    )


class TestEscolhaPelaSessao:
    """Qual pacote, e por quê — o critério medido, não a preferência.

    `onboard` digita por XTEST (`Depends: libxtst6`): numa sessão Wayland ele
    ABRE, via XWayland, e as teclas só chegam a clientes XWayland — a janela
    nativa em foco não recebe nada. Abrir e não digitar é PIOR que não abrir,
    porque parece que funcionou.

    `wvkbd` (binário `wvkbd-mobintl`) é cliente Wayland puro: desenha pelo
    `zwlr_layer_shell_v1` e digita pelo `zwp_virtual_keyboard_manager_v1`.
    Medido em 10/08/2026 na máquina dela (COSMIC/Wayland), o compositor expõe
    EXATAMENTE esses dois protocolos.
    """

    def test_wayland_escolhe_wvkbd(self, tmp_path: Path) -> None:
        sent = _roda_dono(tmp_path, "wayland")
        assert sent["pacote"] == "wvkbd", (
            "em Wayland o teclado escolhido tem de ser o que DIGITA"
        )
        assert sent["binario"] == "wvkbd-mobintl"  # (noqa-acento): chave da sentinela

    def test_x11_escolhe_onboard(self, tmp_path: Path) -> None:
        sent = _roda_dono(tmp_path, "x11")
        assert sent["pacote"] == "onboard", (
            "em X11 o wvkbd nem abre — é cliente Wayland puro"
        )

    def test_sessao_desconhecida_nao_fica_sem_resposta(self, tmp_path: Path) -> None:
        """Install headless (ssh, CI) tem de decidir alguma coisa, e declarar.

        A aposta é a de Wayland — padrão de todo desktop atual — e o doctor,
        que roda DENTRO da sessão dela, corrige o veredito depois.
        """
        sent = _roda_dono(tmp_path, "desconhecida")
        assert sent["pacote"] == "wvkbd"
        assert sent["sessao"] == "desconhecida", (  # (noqa-acento): chave da sentinela
            "a aposta tem de ficar registrada como aposta, não virar certeza"
        )

    def test_a_sentinela_grava_o_que_aconteceu(self, tmp_path: Path) -> None:
        """Sem isto, "o install não instalou" e "ela removeu depois" são iguais."""
        sent = _roda_dono(tmp_path, "wayland")
        assert sent["resultado"] == "dry-run"
        assert sent["data"], "sem data a sentinela não conta história nenhuma"

    def test_os_tres_concordam_no_par_sessao_programa(self) -> None:
        """Instalador, doctor e daemon falando do MESMO binário.

        Se um deles trocar o par, os três continuam coerentes CONSIGO MESMOS —
        e o produto instala um programa e procura outro, sem ninguém perceber.
        """
        for arquivo in (DONO, DOCTOR, KEYBOARD):
            texto = arquivo.read_text(encoding="utf-8")
            assert re.search(r'_?OSK_BIN_WAYLAND[ =]+"wvkbd-mobintl"', texto), (
                f"{arquivo.name} não casa Wayland com wvkbd-mobintl"
            )
            assert re.search(r'_?OSK_BIN_X11[ =]+"onboard"', texto), (
                f"{arquivo.name} não casa X11 com onboard"
            )


class TestOrdemDosCandidatosNoDaemon:
    """A ordem fixa era um defeito, e estava lá desde sempre.

    `_OSK_CANDIDATES` era `("onboard", "wvkbd-mobintl")` — onboard PRIMEIRO.
    Numa sessão Wayland com os dois instalados, o daemon escolheria justamente
    o que não digita fora do XWayland.
    """

    def test_wayland_poe_o_wvkbd_na_frente(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon.subsystems import keyboard

        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        # DISPLAY também setado, que é o caso REAL de toda sessão Wayland com
        # XWayland (nesta máquina, WAYLAND_DISPLAY=wayland-1 e DISPLAY=:1).
        monkeypatch.setenv("DISPLAY", ":1")
        assert keyboard._osk_candidatos()[0] == "wvkbd-mobintl"

    def test_x11_poe_o_onboard_na_frente(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon.subsystems import keyboard

        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        monkeypatch.setenv("DISPLAY", ":0")
        assert keyboard._osk_candidatos()[0] == "onboard"

    def test_o_daemon_publica_se_existe_teclado_na_tela(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A janela não pode perguntar sozinha: num Flatpak ela olha o sandbox.

        Quem responde é o daemon, que é quem enxerga o host e quem vai spawnar
        o processo.
        """
        from hefesto_dualsense4unix.daemon.subsystems import keyboard

        keyboard._OSK_SONDA[0] = (float("-inf"), False)
        monkeypatch.setattr(keyboard.shutil, "which", lambda _n: None)
        assert keyboard.osk_disponivel_no_sistema() is False
        keyboard._OSK_SONDA[0] = (float("-inf"), False)
        monkeypatch.setattr(
            keyboard.shutil,
            "which",
            lambda n: "/usr/bin/wvkbd-mobintl" if n == "wvkbd-mobintl" else None,
        )
        assert keyboard.osk_disponivel_no_sistema() is True

    def test_o_cache_tem_prazo(self) -> None:
        """Instalar o pacote com o daemon no ar tem de passar a valer.

        O cache era eterno (`_resolved_checked` nunca voltava a False): ela
        rodaria `sudo apt install wvkbd`, apertaria o L3 e continuaria não
        acontecendo nada até o próximo start do daemon — e o sintoma é idêntico
        ao de não ter instalado.
        """
        from hefesto_dualsense4unix.daemon.subsystems import keyboard

        assert keyboard._OSK_RESOLVE_TTL_SEG > 0, "o cache do OSK voltou a ser eterno"

    def test_resolve_reve_a_decisao_depois_do_prazo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O teste que MORDE o parágrafo acima: instalar passa a valer.

        Um relógio falso avança além do TTL; o `which` que dizia "não existe"
        passa a dizer "existe". Sem prazo no cache, o segundo `_resolve`
        devolveria None e este teste reprovaria.
        """
        from hefesto_dualsense4unix.daemon.subsystems import keyboard

        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        relogio = {"t": 1000.0}
        monkeypatch.setattr(keyboard.time, "monotonic", lambda: relogio["t"])
        monkeypatch.setattr(keyboard.shutil, "which", lambda _n: None)
        ctrl = keyboard._OSKController()
        assert ctrl._resolve() is None

        monkeypatch.setattr(
            keyboard.shutil,
            "which",
            lambda n: "/usr/bin/wvkbd-mobintl" if n == "wvkbd-mobintl" else None,
        )
        # Ainda dentro do prazo: a resposta velha vale (é o que segura o custo
        # com o state_full a 20 Hz).
        assert ctrl._resolve() is None
        relogio["t"] += keyboard._OSK_RESOLVE_TTL_SEG + 1
        assert ctrl._resolve() == "wvkbd-mobintl", (
            "o daemon nunca reveria a decisão — instalar o pacote com ele no ar "
            "continuaria sem efeito até o próximo start"
        )


# ---------------------------------------------------------------------------
# 3. O doctor confere, não cura, e distingue as quatro ausências
# ---------------------------------------------------------------------------


def _roda_check_doctor(tmp_path: Path, sentinela: str | None, com_binario: str = "") -> str:
    """Roda `check_teclado_na_tela` num HOME e num PATH controlados.

    O PATH é substituído por um diretório do teste com apenas o que a função
    usa (`sed`, `head`) — sem isso, o veredito dependeria de a máquina de quem
    roda a suíte ter (ou não) wvkbd/onboard instalado, e o teste mediria a
    máquina em vez de medir o código.
    """
    lar = tmp_path / "lar"
    binario_dir = tmp_path / "bin"
    (lar / ".local/state/hefesto-dualsense4unix").mkdir(parents=True, exist_ok=True)
    binario_dir.mkdir(exist_ok=True)
    for ferramenta in ("sed", "head"):
        alvo = shutil.which(ferramenta)
        if alvo:
            destino = binario_dir / ferramenta
            if not destino.exists():
                destino.symlink_to(alvo)
    if com_binario:
        falso = binario_dir / com_binario
        falso.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        falso.chmod(0o755)
    if sentinela is not None:
        (lar / ".local/state/hefesto-dualsense4unix/teclado-na-tela.conf").write_text(
            sentinela, encoding="utf-8"
        )
    env = dict(os.environ)
    env.update({
        "HOME": str(lar),
        "PATH": str(binario_dir),
        "WAYLAND_DISPLAY": "wayland-1",
        "DISPLAY": ":1",
    })
    r = subprocess.run(
        [BASH, "-c", f"source '{DOCTOR}'; check_teclado_na_tela"],
        capture_output=True, text=True, env=env, timeout=60,
    )
    return r.stdout


class TestDoctorDistingueAsQuatroAusencias:
    """A armadilha do commit 108b711, em uma frase dele mesmo.

    "install.sh ARMA, uninstall.sh DESARMA, doctor.sh lê a AUSÊNCIA como
    escolha dela — máquina curada e máquina quebrada são o MESMO estado para o
    portão."

    Aqui o `command -v` vazio tem quatro histórias possíveis, e só a sentinela
    as separa. Sem estes quatro testes, o doctor voltaria a dizer só "não tem".
    """

    def test_presente_e_pass(self, tmp_path: Path) -> None:
        saida = _roda_check_doctor(tmp_path, None, com_binario="wvkbd-mobintl")
        assert "[ OK ]" in saida and "wvkbd-mobintl" in saida

    def test_ausente_sem_sentinela_e_fail(self, tmp_path: Path) -> None:
        saida = _roda_check_doctor(tmp_path, None)
        assert "[FAIL]" in saida
        assert "install nunca passou por aqui" in saida

    def test_ausente_por_escolha_dela_nao_e_fail(self, tmp_path: Path) -> None:
        """O único dos quatro que NÃO é falha. É o coração do 108b711."""
        saida = _roda_check_doctor(
            tmp_path, "resultado=pulado\nmotivo=--no-osk\ndata=2026-08-10T00:00:00\n"
        )
        assert "[FAIL]" not in saida, (
            "a escolha dela virou defeito — é o erro que o 108b711 registrou"
        )
        assert "PULADO a pedido" in saida

    def test_ausente_depois_de_instalado_acusa_remocao_de_fora(
        self, tmp_path: Path
    ) -> None:
        saida = _roda_check_doctor(
            tmp_path, "resultado=instalado\npacote=wvkbd\ndata=2026-08-10T00:00:00\n"
        )
        assert "[FAIL]" in saida
        assert "não fomos nós" in saida, (
            "o doctor tem de dizer que o uninstall do Hefesto não remove pacote "
            "de sistema — senão a suspeita cai em nós"
        )

    def test_ausente_por_falha_do_install_diz_o_motivo(self, tmp_path: Path) -> None:
        saida = _roda_check_doctor(
            tmp_path,
            "resultado=falhou\npacote=wvkbd\nmotivo=sem-sudo\ndata=2026-08-10T00:00:00\n",
        )
        assert "[FAIL]" in saida
        assert "sem-sudo" in saida

    def test_o_programa_errado_para_a_sessao_e_aviso_e_nao_pass(
        self, tmp_path: Path
    ) -> None:
        """O caso que mais engana: onboard instalado numa sessão Wayland.

        "Tem teclado na tela" seria verdade e resposta ERRADA — ele abre pelo
        XWayland e as teclas não chegam à janela nativa em foco.
        """
        saida = _roda_check_doctor(tmp_path, None, com_binario="onboard")
        assert "[ OK ]" not in saida, (
            "o doctor deu PASS para um teclado que abre e não digita"
        )
        assert "[WARN]" in saida
        assert "XTEST" in saida


class TestDoctorConfereENaoCura:
    """Regra da casa, com dente: instalar pacote é decisão com senha de root."""

    def test_nenhuma_rota_de_cura_instala_pacote(self) -> None:
        texto = DOCTOR.read_text(encoding="utf-8")
        corpo = re.search(r"^apply_fixes\(\) \{$.*?^\}$", texto, re.MULTILINE | re.DOTALL)
        assert corpo is not None, "apply_fixes sumiu do doctor"
        codigo = _sem_comentarios(corpo.group(0))
        for gestor in ("apt-get install", "apt install", "dnf install", "pacman -S"):
            assert gestor not in codigo, (
                f"o --fix do doctor passou a instalar pacote ({gestor}) — "
                "o doctor confere e não cura"
            )


# ---------------------------------------------------------------------------
# 4. O uninstall não remove o pacote — só a sentinela
# ---------------------------------------------------------------------------


class TestUninstallNaoRemoveOPacote:
    """Precedente da casa: a ponte de mic instala `libopus0` e o uninstall não
    o remove, por decisão. Pacote de sistema pode estar servindo a outra coisa
    da máquina dela — removê-lo seria o Hefesto decidindo sobre software que
    não é dele.
    """

    def test_nao_desinstala_wvkbd_nem_onboard(self) -> None:
        codigo = _sem_comentarios(TEXTO_UNINSTALL)
        padrao = re.compile(
            r"(apt-get|apt|dnf|pacman|rpm)[^\n|]*\b(remove|purge|erase|-R)\b[^\n|]*"
            r"(wvkbd|onboard)"
        )
        assert not padrao.search(codigo), (
            "o uninstall passou a desinstalar o teclado na tela — pacote de "
            "sistema não é nosso para remover (mesma decisão do libopus0)"
        )

    def test_remove_a_sentinela_que_e_nossa(self) -> None:
        codigo = _sem_comentarios(TEXTO_UNINSTALL)
        assert "teclado-na-tela.conf" in codigo, (
            "sem apagar a sentinela, o doctor leria uma máquina JÁ desinstalada "
            "como 'o pacote sumiu depois do install' — diagnóstico de um "
            "produto que não está mais aqui"
        )


# ---------------------------------------------------------------------------
# 5. Os empacotamentos declaram — no campo que o gerenciador lê
# ---------------------------------------------------------------------------


class TestEmpacotamentosDeclaram:
    """Não basta a palavra no arquivo: tem de estar no campo que vale.

    MEDIDO por mutação em 10/08/2026: a primeira versão desta guarda procurava
    "wvkbd" no arquivo inteiro, e arrancar `wvkbd | onboard` do `Recommends:`
    do debian/control passava VERDE — a palavra continuava viva na prosa da
    `Description`. Prosa não instala pacote.
    """

    @pytest.mark.parametrize(
        ("caminho", "regex"),
        [
            ("packaging/debian/control", r"^(Depends|Recommends|Suggests):.*wvkbd"),
            (
                "packaging/fedora/hefesto-dualsense4unix.spec",
                r"^(Requires|Recommends|Suggests):\s*wvkbd",
            ),
            ("packaging/arch/PKGBUILD", r"^\s*'wvkbd:"),
            ("packaging/nix/package.nix", r"makeBinPath.*wvkbd"),
            (
                "flatpak/br.andrefarias.Hefesto.yml",
                r"^\s*-\s*name:\s*wvkbd\s*$",
            ),
        ],
    )
    def test_declara_no_campo_certo(self, caminho: str, regex: str) -> None:
        alvo = RAIZ / caminho
        if not alvo.is_file():
            pytest.skip(f"{caminho} ausente neste checkout")
        codigo = _sem_comentarios(alvo.read_text(encoding="utf-8"))
        assert re.search(regex, codigo, re.MULTILINE), (
            f"{caminho} não declara o teclado na tela onde o gerenciador lê"
        )

    def test_o_flatpak_bundla_porque_o_sandbox_nao_ve_o_host(self) -> None:
        """No Flatpak declarar não basta — tem de vir dentro.

        Este manifesto não pede `--talk-name=org.freedesktop.Flatpak` nem nada
        que permita `flatpak-spawn --host`, então o daemon só enxerga /app. Sem
        o módulo, `shutil.which("wvkbd-mobintl")` devolveria None para sempre,
        por construção — e o formato Flatpak nunca teria como escrever texto.
        """
        manifesto = (RAIZ / "flatpak" / "br.andrefarias.Hefesto.yml").read_text(
            encoding="utf-8"
        )
        assert re.search(r"^\s*-\s*name:\s*wvkbd\s*$", manifesto, re.MULTILINE)
        assert "sha256:" in manifesto.split("name: wvkbd", 1)[1][:800], (
            "módulo sem SHA-256 — o byte que chega deixaria de ser o revisado"
        )


# "A natureza nada faz em vão." — Aristóteles
