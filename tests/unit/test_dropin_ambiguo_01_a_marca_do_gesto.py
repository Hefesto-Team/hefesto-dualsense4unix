"""DROPIN-AMBIGUO-01 — a ausência do drop-in era indistinguível de escolha dela.

O arquivo `~/.config/wireplumber/wireplumber.conf.d/51-hefesto-dualsense-no-default-source.conf`
**não existia** na máquina dela em 04/08/2026. Sem ele o WirePlumber promoveu o
DualSense a microfone padrão do sistema, e daí saíram os sintomas que ela
reportou como *"não funciona nem mic, nem os botões de sons do jogo"*.

A causa-raiz é **um estado com dois significados**. O terceiro degrau de
`doctor.sh:_prefere_mic_do_dualsense` fazia, literalmente:

    [[ -f "${conf}/51-hefesto-dualsense-no-default-source.conf" ]] && return 1
    return 0

— e o comentário ao lado dizia que a ausência do 51 *"é a promoção
explícita"*. Mas a ausência tem **duas origens** e o disco não as distingue:

- *"ela pediu para promover o mic do controle"* (`mic promote`), decisão a
  honrar;
- *"o uninstall removeu e a instalação seguinte não rearmou"*, cura desarmada,
  a reparar.

Máquina curada e máquina quebrada eram o MESMO estado. Quem teve a cura
desarmada recebia `[OK]` no meio do defeito — e o doctor ainda ELEGIA o mic do
controle a fonte padrão, com `pass` na tela; quem promoveu de propósito recebia
FALHA a cada execução e aprendia a ignorar o aviso.

**A cura é marcar o GESTO, nunca o estado** (E1/E2 da sprint de 04/08): quem
liga o mic grava um carimbo com data, em arquivo próprio; quem faz o gesto
contrário apaga; e o degrau 3 passa a LER a marca em vez de inferir. Sem marca
e sem o 51 o veredito é **"não sei"**, que é o que o disco de fato diz.

**A migração é a CONSERVADORA (E4, opção (b)), e está escrita em voz alta**
porque escolher em silêncio seria reescrever a escolha dela: máquina que
promoveu ANTES desta cura existir não tem marca nenhuma e passa a ser tratada
como "não sei" — perde a preferência automática, ganha um aviso que diz o
comando exato, e o caminho de volta é um gesto só. A opção (a) — assumir a
promoção e registrar o que assumiu — foi recusada porque é exatamente o `[OK]`
em cima do defeito que custou a noite de 04/08.

Nenhum teste deste arquivo toca o áudio da máquina, o WirePlumber ou o `HOME`
de quem roda a suíte: as funções shell REAIS dos dois scripts são executadas
por `source`, com `HOME` e `XDG_STATE_HOME` apontando para `tmp_path`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
FIX = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"

TEXTO_DOCTOR = DOCTOR.read_text(encoding="utf-8") if DOCTOR.exists() else ""
TEXTO_FIX = FIX.read_text(encoding="utf-8") if FIX.exists() else ""
TEXTO_INSTALL = INSTALL.read_text(encoding="utf-8") if INSTALL.exists() else ""
TEXTO_UNINSTALL = UNINSTALL.read_text(encoding="utf-8") if UNINSTALL.exists() else ""

pytestmark = pytest.mark.skipif(
    not (TEXTO_DOCTOR and TEXTO_FIX), reason="scripts do microfone ausentes"
)

#: O nome da marca. Ele aparece em TRÊS arquivos (o doctor lê, o fix escreve, o
#: uninstall apaga) e é isso que `TestONomeDaMarcaEUmSo` cobra.
NOME_DA_MARCA = "mic-do-dualsense-pedido.conf"
DROPIN_51 = "51-hefesto-dualsense-no-default-source.conf"
DROPIN_52 = "52-hefesto-dualsense-disable-source.conf"


# ---------------------------------------------------------------------------
# A máquina de mentira
# ---------------------------------------------------------------------------


class Maquina:
    """Um `HOME` inteiro em `tmp_path`: drop-ins do WirePlumber e a marca.

    Sem `XDG_STATE_HOME` apontando para cá, um teste que grave a marca
    escreveria em `~/.local/state` de quem roda a suíte — e a suíte passaria a
    curar a máquina dela pelas costas.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.home = tmp_path / "home"
        self.state = tmp_path / "state"
        self.conf = self.home / ".config" / "wireplumber" / "wireplumber.conf.d"
        self.conf.mkdir(parents=True)
        self.state.mkdir(parents=True)
        self.marca = self.state / "hefesto-dualsense4unix" / NOME_DA_MARCA

    def com_dropin(self, nome: str) -> Maquina:
        (self.conf / nome).write_text("# dublê\n", encoding="utf-8")
        return self

    def com_marca(self, data: str = "2026-08-04T00:37:00-03:00") -> Maquina:
        self.marca.parent.mkdir(parents=True, exist_ok=True)
        self.marca.write_text(
            f"# MARCA DO GESTO — dublê\ngesto=promote-source\ndata={data}\n",
            encoding="utf-8",
        )
        return self

    def _env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.home),
            "XDG_STATE_HOME": str(self.state),
            "DOCTOR_SH": str(DOCTOR),
            "FIX_SH": str(FIX),
        }
        env.update(extra or {})
        return env

    def doctor(
        self, chamada: str, *, fonte: str | None = None, extra: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Roda uma função do doctor com `source` — a função REAL, não uma cópia."""
        alvo = str(DOCTOR)
        if fonte is not None:
            alvo = str(self.home.parent / "doctor_alterado.sh")
            Path(alvo).write_text(fonte, encoding="utf-8")
        return subprocess.run(
            [BASH, "-c", f'set --; source "{alvo}"; {chamada}'],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=self._env(extra),
        )

    def fix(
        self, funcao: str, *, extra: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Roda uma função do `fix_wireplumber_default_source.sh` por `source`.

        O `source` sem `--` não despacha (o próprio script devolve antes do
        `case`), então nada de `systemctl`, `wpctl` ou `pactl` roda aqui.
        """
        return subprocess.run(
            [BASH, "-c", f'set --; source "{FIX}"; {funcao}'],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=self._env(extra),
        )


@pytest.fixture
def maquina(tmp_path: Path) -> Maquina:
    return Maquina(tmp_path)


# ---------------------------------------------------------------------------
# A MORDIDA — o degrau 3 do doctor
# ---------------------------------------------------------------------------


class TestAAusenciaSemMarcaNaoEEscolha:
    """A cena de 04/08/2026: sem o 51 e sem ninguém ter pedido nada."""

    def test_ausencia_sem_marca_nao_e_escolha(self, maquina: Maquina) -> None:
        """A MORDIDA. Máquina sem o 51 e sem marca: o doctor NÃO diz [OK].

        Arrancada a cura (o degrau 5 voltando a `return 0`), esta mesma cena
        volta a sair `[ OK ]` — é literalmente o `doctor.sh` de ontem, e é o
        `test_a_mordida_...` logo abaixo que prova.
        """
        r = maquina.doctor("check_dropin_do_mic_armado")
        assert "[ OK ]" not in r.stdout, (
            "verde sobre uma máquina com a cura do microfone desarmada e "
            f"ninguém tendo pedido a promoção:\n{r.stdout}"
        )
        assert "[WARN]" in r.stdout, r.stdout

    def test_o_aviso_diz_os_dois_caminhos(self, maquina: Maquina) -> None:
        """A ambiguidade é do DISCO, então o aviso oferece as duas saídas.

        Quem teve a cura desarmada precisa do comando de rearmar; quem quer o
        mic do controle precisa do comando que GRAVA a marca — sem ele, o
        aviso viraria aquele que se aprende a ignorar, que é pior que nenhum.
        """
        saida = maquina.doctor("check_dropin_do_mic_armado").stdout
        assert "--install" in saida, saida
        assert "mic promote" in saida, saida

    def test_o_predicado_recusa_sem_marca(self, maquina: Maquina) -> None:
        """O degrau em si: "não sei" nunca é "ela pediu"."""
        r = maquina.doctor("_prefere_mic_do_dualsense")
        assert r.returncode == 1, (
            "sem o 51 e sem marca o doctor ainda diz que o mic do DualSense "
            "foi pedido — é a ausência sendo lida como decisão"
        )

    def test_a_mordida_sem_a_leitura_da_marca_a_cena_volta_a_ser_verde(
        self, maquina: Maquina
    ) -> None:
        """Arrancada a cura, a cena de 04/08 volta a sair `[ OK ]`."""
        alvo = "    return 1\n}"
        corpo = _funcao_bash(TEXTO_DOCTOR, "_prefere_mic_do_dualsense")
        assert corpo.endswith(alvo), (
            f"o degrau final mudou de forma; fim da função:\n{corpo[-120:]}"
        )
        arrancado = TEXTO_DOCTOR.replace(corpo, corpo[: -len(alvo)] + "    return 0\n}")
        assert arrancado != TEXTO_DOCTOR
        r = maquina.doctor("check_dropin_do_mic_armado", fonte=arrancado)
        assert "[ OK ]" in r.stdout, (
            "com a cura arrancada a cena de 04/08 devia voltar a ser verde — "
            f"se não voltou, esta régua não está medindo.\n{r.stdout}"
        )


class TestOsSinaisExplicitosContinuamValendo:
    """A cura não pode ter custado nenhum dos três sinais que já existiam."""

    def test_com_o_51_no_lugar_a_politica_esta_armada(self, maquina: Maquina) -> None:
        maquina.com_dropin(DROPIN_51)
        r = maquina.doctor("check_dropin_do_mic_armado")
        assert "[ OK ]" in r.stdout, r.stdout
        assert "[WARN]" not in r.stdout, r.stdout
        assert maquina.doctor("_prefere_mic_do_dualsense").returncode == 1

    def test_o_52_vence_tudo(self, maquina: Maquina) -> None:
        """O mic desligado de propósito não tem política de eleição a armar."""
        maquina.com_dropin(DROPIN_52).com_marca()
        r = maquina.doctor("check_dropin_do_mic_armado")
        assert "[WARN]" not in r.stdout, r.stdout
        assert maquina.doctor("_prefere_mic_do_dualsense").returncode == 1

    def test_a_env_continua_sendo_opt_in(self, maquina: Maquina) -> None:
        env = {"HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED": "1"}
        r = maquina.doctor("_prefere_mic_do_dualsense", extra=env)
        assert r.returncode == 0, "a env explícita dela parou de valer"
        saida = maquina.doctor("check_dropin_do_mic_armado", extra=env).stdout
        assert "[ OK ]" in saida, saida
        assert "DUALSENSE_MIC_INTENDED" in saida, (
            f"o [OK] tem de dizer QUAL sinal o produziu:\n{saida}"
        )


class TestComAMarcaOPedidoEHonrado:
    """A outra metade do defeito: quem promoveu a dedo levava FALHA."""

    def test_a_marca_faz_o_predicado_aceitar(self, maquina: Maquina) -> None:
        maquina.com_marca()
        assert maquina.doctor("_prefere_mic_do_dualsense").returncode == 0

    def test_o_check_diz_a_data_do_gesto(self, maquina: Maquina) -> None:
        """Sem a data, a marca só diz "alguém pediu" — e não quando."""
        maquina.com_marca(data="2026-08-04T00:37:00-03:00")
        saida = maquina.doctor("check_dropin_do_mic_armado").stdout
        assert "[ OK ]" in saida, saida
        assert "2026-08-04T00:37:00-03:00" in saida, saida

    def test_o_mic_ativo_com_a_marca_nao_e_mais_falha(self, maquina: Maquina) -> None:
        """`check_wireplumber_source` parava de acusar só pela presença do 51.

        Quem promoveu de propósito (`mic promote`) fica SEM o 51 por desenho, e
        levava `[FAIL]` a cada doctor. Aviso que se aprende a ignorar é pior
        que aviso nenhum.
        """
        maquina.com_marca()
        cur = (
            "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
            "Controller-00.iec958-stereo"
        )
        # Dublê de `pactl` que responde o mic do controle como fonte ativa.
        binario = maquina.home.parent / "bin"
        binario.mkdir(exist_ok=True)
        stub = binario / "pactl"
        stub.write_text(
            "#!/bin/sh\n"
            'case "$*" in\n'
            f'  "get-default-source") printf "%s\\n" "{cur}" ;;\n'
            "  *) : ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        r = maquina.doctor("check_wireplumber_source", extra={"PATH": f"{binario}:/usr/bin:/bin"})
        assert "[FAIL]" not in r.stdout, (
            "quem promoveu o mic a dedo continua levando FALHA a cada "
            f"execução do doctor:\n{r.stdout}"
        )
        assert "[ OK ]" in r.stdout, r.stdout


# ---------------------------------------------------------------------------
# Quem ESCREVE a marca — o gesto, nunca o estado
# ---------------------------------------------------------------------------


class TestAMarcaEDoGesto:
    def test_ligar_o_mic_grava_a_marca(self, maquina: Maquina) -> None:
        r = maquina.fix("_marca_do_gesto_gravar enable-mic")
        assert r.returncode == 0, r.stderr
        assert maquina.marca.is_file(), r.stdout
        texto = maquina.marca.read_text(encoding="utf-8")
        assert "gesto=enable-mic" in texto, texto
        assert re.search(r"^data=\S+", texto, re.MULTILINE), (
            f"a marca precisa do CARIMBO COM DATA — sem ele ela só diz que existe:\n{texto}"
        )

    def test_a_data_do_primeiro_pedido_fica(self, maquina: Maquina) -> None:
        """Regravar a cada `--enable-mic` apagaria a única informação que a
        marca carrega além da própria existência: QUANDO ela pediu."""
        maquina.com_marca(data="2026-08-04T00:37:00-03:00")
        maquina.fix("_marca_do_gesto_gravar enable-mic")
        assert "2026-08-04T00:37:00-03:00" in maquina.marca.read_text(encoding="utf-8")

    def test_o_gesto_contrario_apaga(self, maquina: Maquina) -> None:
        maquina.com_marca()
        r = maquina.fix("_marca_do_gesto_apagar")
        assert r.returncode == 0, r.stderr
        assert not maquina.marca.exists(), (
            "a marca sobreviveu ao gesto contrário — marca que não se apaga "
            "virou estado, que é o defeito que ela cura"
        )

    def test_apagar_o_que_nao_existe_e_silencioso(self, maquina: Maquina) -> None:
        r = maquina.fix("_marca_do_gesto_apagar")
        assert r.returncode == 0, r.stderr

    def test_a_promocao_carimba_antes_de_apagar_o_51(self) -> None:
        """A ORDEM importa, e é o ponto inteiro da cura.

        `--promote-source` apaga o 51; é a partir daí que a ausência precisa
        de alguém dizendo de onde ela veio. Carimbar depois deixaria uma
        janela — e um `Ctrl-C` no meio produziria exatamente o estado
        ambíguo que esta sprint existe para matar.
        """
        corpo = _funcao_bash(TEXTO_FIX, "enable_mic_dualsense")
        assert "_marca_do_gesto_gravar" in corpo, "o gesto de ligar o mic parou de deixar marca"
        pos_marca = corpo.index("_marca_do_gesto_gravar")
        pos_dropins = corpo.index("_arma_dropins_do_mic")
        assert pos_marca < pos_dropins, (
            "a marca é gravada DEPOIS de o 51 sair: entre uma coisa e outra a "
            "máquina fica no estado ambíguo de 04/08"
        )

    def test_o_gesto_de_ligar_nao_toca_no_audio(self, maquina: Maquina) -> None:
        """SÓ ARQUIVOS, como o `_arma_dropins_do_mic` ao lado.

        É o que permite este portão exercitar a função DE VERDADE num HOME de
        mentira, em vez de reimplementá-la aqui — e régua que reimplementa o
        produto é como esta casa já produziu alarme convincente e falso.
        """
        for nome in ("_marca_do_gesto_gravar", "_marca_do_gesto_apagar"):
            corpo = _funcao_bash(TEXTO_FIX, nome)
            for verbo in ("systemctl", "wpctl", "pactl"):
                assert verbo not in corpo, f"{nome}() executa `{verbo}`"


class TestOsDoisGestosContrariosApagam:
    """`--install` e `--disable-source` decidem o OPOSTO de ligar o mic."""

    @pytest.mark.parametrize("modo", ["install", "disable"])
    def test_o_ramo_do_case_apaga_a_marca(self, modo: str) -> None:
        corpo = re.search(rf"^    {modo}\)\n(?P<c>(?:.*\n)*?)        ;;$", TEXTO_FIX, re.MULTILINE)
        assert corpo is not None, f"o ramo `{modo})` sumiu do despacho"
        assert "_marca_do_gesto_apagar" in corpo.group("c"), (
            f"o ramo `{modo})` não apaga a marca — o disco ficaria com dois "
            f"sinais dizendo coisas opostas:\n{corpo.group('c')}"
        )


class TestOInstaladorEODesinstaladorSabemDaMarca:
    """A regra da casa de 08/08: toda cura entra no install, sem flag."""

    def test_o_keep_dualsense_mic_carimba(self) -> None:
        """`--keep-dualsense-mic` É o pedido explícito, e passa a ser escrito.

        Sem isto, este ramo terminava idêntico a uma máquina que nunca
        instalou nada — que é o estado ambíguo inteiro.
        """
        assert "--marcar-gesto-do-mic" in TEXTO_INSTALL, (
            "o `--keep-dualsense-mic` voltou a terminar sem carimbo: o doctor "
            "não tem como distinguir esse pedido de uma cura desarmada"
        )
        trecho = TEXTO_INSTALL[TEXTO_INSTALL.index("--marcar-gesto-do-mic") - 1500 :]
        assert "keep-dualsense-mic" in trecho[:1500], (
            "o carimbo saiu do ramo do `--keep-dualsense-mic`"
        )

    def test_o_uninstall_apaga_a_marca(self) -> None:
        assert NOME_DA_MARCA in TEXTO_UNINSTALL, (
            "o uninstall deixa a marca para trás — a instalação seguinte "
            "herdaria uma promoção que ninguém pediu nesta vida"
        )
        assert 'rm -f "${MARCA_MIC_PEDIDO}"' in TEXTO_UNINSTALL, TEXTO_UNINSTALL[:0]

    def test_o_modo_novo_e_so_arquivo(self) -> None:
        """`--marcar-gesto-do-mic` não pode reiniciar o áudio dela.

        Ele roda no fim de uma instalação que pediu para NÃO mexerem no som —
        derrubar o WirePlumber ali seria mexer.
        """
        ramo = re.search(
            r"^    marcar-gesto\)\n(?P<c>(?:.*\n)*?)        ;;$", TEXTO_FIX, re.MULTILINE
        )
        assert ramo is not None, "o modo `--marcar-gesto-do-mic` sumiu do despacho"
        for verbo in ("systemctl", "wpctl", "pactl", "install_dropin"):
            assert verbo not in ramo.group("c"), f"o modo executa `{verbo}`"


class TestONomeDaMarcaEUmSo:
    """Três arquivos falam da mesma marca; um nome divergente a apaga em
    silêncio — o doctor leria um caminho que ninguém escreve, e o veredito
    voltaria a ser "não sei" para sempre."""

    def test_os_tres_arquivos_dizem_o_mesmo_nome(self) -> None:
        for rotulo, texto in (
            ("doctor.sh", TEXTO_DOCTOR),
            ("fix_wireplumber_default_source.sh", TEXTO_FIX),
            ("uninstall.sh", TEXTO_UNINSTALL),
        ):
            assert NOME_DA_MARCA in texto, f"{rotulo} não conhece a marca"

    def test_o_caminho_honra_o_xdg_state_home(self) -> None:
        for rotulo, texto in (
            ("doctor.sh", TEXTO_DOCTOR),
            ("fix_wireplumber_default_source.sh", TEXTO_FIX),
            ("uninstall.sh", TEXTO_UNINSTALL),
        ):
            linhas = texto.splitlines()
            i = next(n for n, ln in enumerate(linhas) if NOME_DA_MARCA in ln)
            vizinhanca = "\n".join(linhas[max(0, i - 2) : i + 3])
            assert "XDG_STATE_HOME" in vizinhanca, (
                f"{rotulo} ancora a marca fora do XDG_STATE_HOME: a marca "
                f"escrita por um caminho não seria lida pelo outro.\n{vizinhanca}"
            )

    def test_o_doctor_le_e_nao_escreve(self) -> None:
        """O diagnóstico confere e NÃO cura: criar a marca aqui seria o doctor
        decidindo, em silêncio, o que só ela pode decidir."""
        corpo = _funcao_bash(TEXTO_DOCTOR, "_marca_do_gesto_do_mic")
        for verbo in ("mkdir", "touch", ">", "rm "):
            assert verbo not in corpo, f"o doctor ESCREVE a marca (`{verbo}`)"


# ---------------------------------------------------------------------------


def _funcao_bash(fonte: str, nome: str) -> str:
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada"
    fim = re.search(r"^\}$", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end()]
