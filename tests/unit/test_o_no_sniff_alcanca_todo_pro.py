"""O no-sniff da BORDA do connect alcança todo Pro, não só o desta bancada.

UMA-FAIXA-NÃO-É-UM-FABRICANTE-01 / E1, a metade que faltava (25/08/2026).

O QUE ESTAVA ERRADO
--------------------
``scripts/bt_nosniff_now.sh`` decidia "é um Pro genuíno?" com um
``[[ "${MAC^^}" != "E0:F6:B5"* ]] && exit 0``, e ``assets/82-*.rules`` só o
chamava para essa mesma faixa. ``E0:F6:B5`` é a faixa do Pro DESTA casa; a
Nintendo tem oitenta e duas registradas e a 8BitDo tem UMA (medido contra
``/usr/share/ieee-data/oui.csv`` em 22/08/2026). Quem tem um Pro de outra safra
não recebia a cura da borda — o link caindo sob carga, e nem a linha de journal
que o script escreve quando falha, porque o ``exit 0`` era MUDO.

A cura do lado do produto (``core/linhagem_nintendo.py``, a pergunta por
negativa) entrou em 22/08 e alcançou o daemon, a tela e o ``bt_active_mode.sh``.
Os dois caminhos da BORDA ficaram para trás, e são justamente os que agem no
instante em que o link nasce.

O QUE ESTE ARQUIVO GUARDA — três coisas, e nenhuma é a outra
-------------------------------------------------------------
1. **A cópia em shell não se separa do dono.** O helper roda pelo udev, como
   root, na borda do connect: importar Python ali seria depender de um venv que
   pode não estar de pé. Então a regra existe duas vezes — e um portão lê os
   dois lados. Cópia PINADA, não cópia solta.
2. **Quem recebe o tratamento, medido rodando o script DE VERDADE**, com um
   ``hcitool`` dublê no ``PATH``. Não é leitura de fonte: o script decide, e o
   teste olha se ele chamou ou não chamou.
3. **As recusas são palavras DIFERENTES** (defeito de forma F7, decisão
   ``D-O-QUE-O-PRODUTO-DIZ-SEM-SABER`` de 25/08/2026): *"você não declarou o
   nome"* é ausência de DECLARAÇÃO, do chamador; *"o nome que você declarou não
   é de um Pro"* é ausência de CASAMENTO, medida aqui. Um ``exit 0`` mudo dizia
   as duas com a mesma cara — que é nenhuma.

A RÉGUA É INDEPENDENTE, e vale nomear como
-------------------------------------------
Nada aqui faz ``monkeypatch`` na lista que confere. O ``hcitool`` dublê não sabe
de OUI nenhuma: ele só anota o que recebeu. A faixa de "outra safra" é LITERAL
neste arquivo e o teste cobra que ela NÃO esteja em nenhuma das listas do
produto — se alguém a adicionar para fazer o teste passar, o teste reprova por
esse motivo, com essa palavra.

SEM APARELHO: nada aqui pareia, conecta ou escreve em rádio. O ``hcitool`` de
verdade nunca é chamado — o dublê vem antes no ``PATH``. Medido em 25/08/2026
com ``/sys/class/bluetooth/`` VAZIO (o hub USB dela fora do barramento).

ANONIMATO: os endereços são montados com os octetos 4 e 5 zerados, a máscara da
casa. As faixas ``e0:f6:b5`` e ``e4:17:d8`` vêm das constantes do produto; a de
"outra safra" é uma MA-L real da Nintendo que esta bancada nunca viu, e é
justamente por não ser daqui que ela serve.

MORDE? Devolva o ``[[ "${MAC^^}" != "E0:F6:B5"* ]] && exit 0`` ao helper, ou
tire a rota por nome da regra 82: cada um reprova um teste distinto deste
arquivo. As duas mordidas estão coladas no relatório da frente D3.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.linhagem_nintendo import (
    NOMES_PRO,
    OUIS_CLONE,
    OUIS_NINTENDO_VISTAS,
    com_dois_pontos,
)

RAIZ = Path(__file__).resolve().parents[2]
HELPER = RAIZ / "scripts" / "bt_nosniff_now.sh"
REGRA = RAIZ / "assets" / "82-nintendo-pro-nosniff.rules"

#: Uma MA-L REAL da Nintendo que esta bancada nunca viu — a faixa é o ponto: se
#: o teste usasse o hardware da casa, ele passaria verde exatamente no defeito
#: que a sprint mediu. Sufixo com a máscara da casa.
OUI_DE_OUTRA_SAFRA = "5c:52:1e"
MAC_DE_OUTRA_SAFRA = f"{OUI_DE_OUTRA_SAFRA}:00:00:44"

#: O nome com que o Pro se anuncia por rádio. O clone anuncia o MESMO — é essa
#: colisão que obriga a decisão a passar pela OUI.
NOME_PRO = "Pro Controller"
NOME_PRO_PELO_CABO = "Nintendo Co., Ltd. Pro Controller"

#: Pelo CABO o `HID_UNIQ` do Pro é o serial, e o clone mente o mesmo serial
#: (`assets/84-nintendo-pro-variant.rules`). Não é endereço, e cabo não tem link
#: BR/EDR para tirar do sniff.
SERIAL_DO_CABO = "000000000001"


def _mascarado(oui_com_dois_pontos: str, ultimo: int) -> str:
    """``OUI:00:00:NN`` — a máscara da casa, montada a partir da OUI dada."""
    return f"{oui_com_dois_pontos}:00:00:{ultimo:02x}"


def _mac_do_clone() -> str:
    return _mascarado(next(iter(com_dois_pontos(OUIS_CLONE))), 0x22)


def _mac_da_faixa_conhecida() -> str:
    return _mascarado(next(iter(com_dois_pontos(OUIS_NINTENDO_VISTAS))), 0x11)


# ---------------------------------------------------------------------------
# A bancada de mentira: um `hcitool` que só anota
# ---------------------------------------------------------------------------


class Desfecho:
    """O que o helper fez: se chamou o `hcitool`, e o que escreveu no diário."""

    def __init__(self, chamadas: list[str], diario: str, codigo: int) -> None:
        self.chamadas = chamadas
        self.diario = diario
        self.codigo = codigo

    @property
    def aplicou(self) -> bool:
        return any("RSWITCH" in c for c in self.chamadas)


@pytest.fixture()
def rodar(tmp_path: Path):
    """Roda o helper DE VERDADE, com um `hcitool` dublê antes no `PATH`.

    O dublê é o que torna o teste executável sem aparelho: ele não sabe de OUI
    nenhuma, não escreve em rádio nenhum, e só registra o argv que recebeu. Quem
    decide continua sendo o script de produção.
    """
    binario = tmp_path / "bin"
    binario.mkdir()
    registro = tmp_path / "hcitool.txt"
    dublê = binario / "hcitool"
    dublê.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$HEFESTO_TESTE_HCITOOL\"\nexit 0\n",
        encoding="utf-8",
    )
    dublê.chmod(0o755)

    def _rodar(mac: str, nome: str | None = None, *, nome_no_ambiente: str = "") -> Desfecho:
        registro.write_text("", encoding="utf-8")
        diario = tmp_path / "diario.txt"
        diario.write_text("", encoding="utf-8")
        ambiente = dict(os.environ)
        ambiente["PATH"] = f"{binario}{os.pathsep}{ambiente.get('PATH', '')}"
        ambiente["HEFESTO_TESTE_HCITOOL"] = str(registro)
        ambiente["HEFESTO_BT_LOG_DEST"] = str(diario)
        ambiente.pop("HID_NAME", None)
        if nome_no_ambiente:
            ambiente["HID_NAME"] = nome_no_ambiente
        argv = ["bash", str(HELPER), mac]
        if nome is not None:
            argv.append(nome)
        proc = subprocess.run(argv, env=ambiente, capture_output=True, text=True, timeout=30)
        return Desfecho(
            [ln for ln in registro.read_text(encoding="utf-8").splitlines() if ln],
            diario.read_text(encoding="utf-8"),
            proc.returncode,
        )

    return _rodar


# ---------------------------------------------------------------------------
# 1. A cópia em shell é PINADA no dono
# ---------------------------------------------------------------------------


def _lista_do_shell(nome: str) -> list[str]:
    """Lê um array bash literal (`NOME=("a" "b")`) do helper."""
    texto = HELPER.read_text(encoding="utf-8")
    achado = re.search(rf"^{nome}=\(([^)]*)\)", texto, re.MULTILINE)
    assert achado, f"o helper não declara mais o array `{nome}`"
    return re.findall(r'"([^"]*)"', achado.group(1))


class TestACopiaEmShellNaoSeSeparaDoDono:
    """`core/linhagem_nintendo.py` é o dono; o shell é cópia, e é PINADA.

    Sem este portão, o dia em que uma faixa nova de clone entrar em
    `OUIS_CLONE` o helper continua sem saber dela — e a cura da borda passa a
    envenenar a probe de um aparelho que precisa do sniff, calada.
    """

    def test_a_faixa_do_clone_e_a_mesma_dos_dois_lados(self) -> None:
        do_shell = {o.replace(":", "").lower() for o in _lista_do_shell("OUIS_CLONE")}
        assert do_shell == set(OUIS_CLONE), (
            f"o helper conhece as faixas de clone {sorted(do_shell)} e o produto "
            f"conhece {sorted(OUIS_CLONE)}. A recusa do clone é a CURA dele (a "
            "probe morre em ret=-110 sem sniff): os dois lados discordando "
            "significa que um controle recebe o tratamento do outro"
        )

    def test_as_faixas_ja_vistas_sao_as_mesmas_dos_dois_lados(self) -> None:
        do_shell = {
            o.replace(":", "").lower() for o in _lista_do_shell("OUIS_NINTENDO_VISTAS")
        }
        assert do_shell == set(OUIS_NINTENDO_VISTAS), (
            f"o helper vê {sorted(do_shell)} e o produto vê "
            f"{sorted(OUIS_NINTENDO_VISTAS)} como faixa já conhecida"
        )

    def test_os_nomes_de_pro_sao_os_mesmos_dos_dois_lados(self) -> None:
        do_shell = tuple(n.lower() for n in _lista_do_shell("NOMES_PRO"))
        assert do_shell == tuple(n.lower() for n in NOMES_PRO), (
            f"o helper casa os nomes {do_shell} e o produto casa {NOMES_PRO} — "
            "é por AQUI que o Pro de outra safra entra, e os dois lados "
            "discordando o deixam de fora de um dos caminhos"
        )

    def test_a_faixa_de_outra_safra_deste_teste_nao_e_conhecida_pelo_produto(
        self,
    ) -> None:
        """A régua tem de continuar apontando para fora da bancada.

        Se alguém "consertar" um vermelho daqui adicionando `5c:52:1e` às
        listas, o teste inteiro vira medição de si mesmo. Este é o portão do
        portão.
        """
        colada = OUI_DE_OUTRA_SAFRA.replace(":", "")
        assert colada not in OUIS_NINTENDO_VISTAS, (
            f"`{OUI_DE_OUTRA_SAFRA}` entrou em OUIS_NINTENDO_VISTAS. Ela existe "
            "neste arquivo para representar as 81 faixas Nintendo que esta "
            "bancada NUNCA viu — conhecê-la desarma todo teste abaixo"
        )
        assert colada not in OUIS_CLONE


# ---------------------------------------------------------------------------
# 2. Quem recebe o tratamento — rodando o script de verdade
# ---------------------------------------------------------------------------


class TestQuemRecebeONoSniff:
    def test_o_pro_de_outra_safra_recebe_o_no_sniff(self, rodar) -> None:
        """O DEFEITO DA SPRINT, em um teste.

        MORDIDA: devolva ao helper o `[[ "${MAC^^}" != "E0:F6:B5"* ]] && exit 0`
        e este teste reprova — que é o que acontece hoje, calado, na máquina de
        quem não tem o Pro desta casa.
        """
        desfecho = rodar(MAC_DE_OUTRA_SAFRA, NOME_PRO)
        assert desfecho.aplicou, (
            "um Pro Controller numa faixa Nintendo que esta bancada nunca viu "
            "NÃO recebeu o no-sniff da borda. É o link caindo sob carga na "
            f"máquina de outra pessoa.\nDiário: {desfecho.diario}"
        )
        assert MAC_DE_OUTRA_SAFRA in desfecho.chamadas[0]

    def test_o_clone_com_o_mesmo_nome_continua_de_fora(self, rodar) -> None:
        """A contraprova obrigatória: a cura não pode virar regressão do clone.

        O 8BitDo em modo Switch mente VID, PID, serial e nome — anuncia-se com o
        MESMO "Pro Controller". Se a regra passasse a valer por nome sozinho, ele
        entraria; e o no-sniff é VENENO para ele (A/B de 23/07/2026: a probe
        morre em `Failed to get joycon info; ret=-110`).
        """
        desfecho = rodar(_mac_do_clone(), NOME_PRO)
        assert not desfecho.aplicou, (
            "o clone 8BitDo recebeu o no-sniff: a probe dele morre em ret=-110 "
            "sem sniff, e a cura do Pro virou o defeito do 8BitDo"
        )
        assert "clone" in desfecho.diario.lower(), (
            "o clone foi recusado sem dizer que é o clone — a recusa dele é a "
            f"CURA, e quem lê o journal precisa saber disso.\n{desfecho.diario}"
        )

    def test_a_faixa_conhecida_nao_passa_a_depender_do_nome(self, rodar) -> None:
        """Não-regressão: nada que já funcionava passa a exigir um dado novo.

        A regra 82 passa o nome pelo AMBIENTE, e ambiente é coisa que falta.
        Quem já recebia a cura pela faixa continua recebendo sem nome nenhum.
        """
        desfecho = rodar(_mac_da_faixa_conhecida())
        assert desfecho.aplicou, (
            "o Pro da faixa já conhecida deixou de receber o no-sniff quando o "
            "chamador não declara o nome — a cura de 24/07 regrediu"
        )

    def test_o_nome_pode_vir_do_ambiente_como_o_udev_o_entrega(self, rodar) -> None:
        """O udev exporta as propriedades do device; `HID_NAME` é uma delas.

        É por isso que o `RUN+=` da regra 82 não precisou mudar: pôr
        `$env{HID_NAME}` na linha de comando quebraria o nome em cinco
        argumentos, porque o udev separa o argv por espaço DEPOIS de substituir.

        MORDIDA: troque `NOME="${2:-${HID_NAME:-}}"` por `NOME="${2:-}"` e este
        teste reprova — e com ele a cura inteira, porque em produção quem chama
        é o udev e ele não passa nome nenhum no argv.
        """
        desfecho = rodar(MAC_DE_OUTRA_SAFRA, None, nome_no_ambiente=NOME_PRO_PELO_CABO)
        assert desfecho.aplicou, (
            "o helper ignorou o `HID_NAME` do ambiente. Em produção quem o chama "
            "é o udev, que entrega o nome por ali e não no argv: sem isto a cura "
            f"só funciona quando alguém a chama à mão.\nDiário: {desfecho.diario}"
        )

    def test_o_serial_do_cabo_nao_vira_endereco(self, rodar) -> None:
        """Pelo cabo não há link BR/EDR — e o `HID_UNIQ` ali é o serial.

        Preço de a regra passar a casar por NOME: o Pro no CABO também se chama
        "Pro Controller". Sem a guarda de forma, ele chegaria ao `hcitool lp`
        contra um "endereço" que não é endereço, e o journal registraria uma
        falha que não é falha.
        """
        desfecho = rodar(SERIAL_DO_CABO, NOME_PRO_PELO_CABO)
        assert not desfecho.chamadas, (
            "o helper tentou mudar link policy de um SERIAL de USB: "
            f"{desfecho.chamadas}"
        )
        assert "forma de endereço" in desfecho.diario, (
            f"a recusa não disse que o problema é a FORMA.\n{desfecho.diario}"
        )

    def test_sem_endereco_nenhum_o_helper_recusa_e_diz_como_se_usa(
        self, rodar
    ) -> None:
        desfecho = rodar("")
        assert desfecho.codigo == 2
        assert not desfecho.chamadas


class TestAsDuasRecusasSaoPalavrasDiferentes:
    """F7: "não medi" e "você não declarou" não são a mesma frase.

    `D-O-QUE-O-PRODUTO-DIZ-SEM-SABER` (25/08/2026). Um `exit 0` mudo dizia as
    duas com a mesma cara — e quem lia o journal não tinha como saber se o
    caminho a seguir era declarar o nome ou trocar de controle.
    """

    def test_sem_nome_declarado_a_recusa_acusa_quem_chama(self, rodar) -> None:
        desfecho = rodar(MAC_DE_OUTRA_SAFRA)
        assert not desfecho.aplicou
        assert "NÃO DECLAROU" in desfecho.diario, (
            "a faixa é desconhecida e o nome não veio: isto é 'não dá para saber "
            "se é um Pro', e a linha do journal tem de dizer QUEM pode resolver "
            f"— quem chama.\n{desfecho.diario}"
        )

    def test_com_nome_que_nao_e_de_pro_a_recusa_acusa_o_nome_recebido(self, rodar) -> None:
        desfecho = rodar(MAC_DE_OUTRA_SAFRA, "DualSense Wireless Controller")
        assert not desfecho.aplicou
        assert "DualSense Wireless Controller" in desfecho.diario, (
            "a recusa não repetiu o nome que recebeu — sem ele quem lê não sabe "
            f"o que o produto viu.\n{desfecho.diario}"
        )

    def test_as_duas_recusas_nao_sao_a_mesma_frase(self, rodar) -> None:
        """MORDIDA: colapse os dois `_recusar` num só e este teste reprova."""
        sem_nome = rodar(MAC_DE_OUTRA_SAFRA).diario
        com_nome_errado = rodar(MAC_DE_OUTRA_SAFRA, "Xbox Wireless Controller").diario
        assert sem_nome.strip() and com_nome_errado.strip()
        assert sem_nome.split("hefesto-bt:", 1)[-1] != com_nome_errado.split(
            "hefesto-bt:", 1
        )[-1], (
            "ausência de DECLARAÇÃO (do chamador) e ausência de CASAMENTO "
            "(medida aqui) saíram com a mesma frase. É o defeito de forma F7: "
            "duas situações com ações diferentes, uma palavra só"
        )


# ---------------------------------------------------------------------------
# 3. A regra 82 — o chamador em produção
# ---------------------------------------------------------------------------


def _linhas_de_regra() -> list[str]:
    return [
        ln.strip()
        for ln in REGRA.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


class TestARegra82ChamaOHelperParaTodoPro:
    """A cura do helper é INERTE se a regra só o chamar para uma faixa.

    É o padrão que mais custa nesta casa: *a casa sabe e o produto não faz*.
    O helper aprendeu a decidir em 25/08; sem esta metade, ele continuaria sendo
    chamado só para o Pro desta bancada e nada mudaria na máquina de ninguém.
    """

    def test_a_regra_casa_por_nome_e_nao_so_por_faixa(self) -> None:
        """MORDIDA: apague a linha de `HID_NAME` e este teste reprova."""
        linhas = _linhas_de_regra()
        por_nome = [ln for ln in linhas if "HID_NAME" in ln]
        assert por_nome, (
            "a regra 82 voltou a escopar SÓ por faixa de endereço. O helper "
            "sabe decidir sobre um Pro de qualquer safra e nunca é chamado para "
            "um: cura escrita e não ligada"
        )
        assert any("[Pp]ro [Cc]ontroller" in ln for ln in por_nome), (
            "a rota por nome não casa 'Pro Controller' nas duas caixas — o "
            f"`HID_NAME` chega ora de um jeito ora de outro.\n{por_nome}"
        )

    def test_a_rota_por_nome_exige_forma_de_endereco(self) -> None:
        """Pelo cabo o `HID_UNIQ` é o serial, e o nome é o mesmo.

        MORDIDA: tire o `ENV{HID_UNIQ}!="??:??:??:??:??:??"` e o Pro no cabo
        passa a chamar o helper a cada `add`.
        """
        assert any(
            "??:??:??:??:??:??" in ln for ln in _linhas_de_regra()
        ), (
            "a rota por nome não confere mais se o `HID_UNIQ` tem FORMA de "
            "endereço: pelo cabo ele é o serial `000000000001`, e cabo não tem "
            "link BR/EDR para tirar do sniff"
        )

    def test_a_faixa_ja_conhecida_continua_tendo_rota_propria(self) -> None:
        """Nada que já funcionava passa a depender do nome ter sido resolvido."""
        faixas = {
            "".join(ch for ch in m.lower() if ch in "0123456789abcdef")
            for m in re.findall(
                r'ENV\{HID_UNIQ\}=="([0-9A-Fa-f:]+):\*"', REGRA.read_text(encoding="utf-8")
            )
        }
        assert faixas == set(OUIS_NINTENDO_VISTAS), (
            f"a regra escopa as faixas {sorted(faixas)} e o produto conhece "
            f"{sorted(OUIS_NINTENDO_VISTAS)} — a rota que não depende do nome "
            "tem de cobrir exatamente as faixas já vistas"
        )

    def test_o_pro_desta_bancada_nao_chama_o_helper_duas_vezes(self) -> None:
        """Duas rotas para o mesmo aparelho seriam dois `RUN+=` por connect.

        Quem impede é o `GOTO`: a rota da faixa salta direto para o `LABEL` que
        aplica, sem passar pela rota do nome.
        """
        linhas = _linhas_de_regra()
        com_run = [ln for ln in linhas if "RUN+=" in ln]
        assert len(com_run) == 1, (
            f"a regra 82 tem {len(com_run)} linhas de `RUN+=`. Com mais de uma, "
            "um Pro que case as duas rotas chama o helper duas vezes por "
            f"connect e o journal ganha duas linhas para um evento.\n{com_run}"
        )
        assert any(ln.startswith("LABEL=") for ln in linhas), (
            "sumiu o `LABEL` do desvio — sem ele as rotas não se excluem"
        )

    def test_a_regra_nao_casa_a_faixa_do_clone_por_endereco(self) -> None:
        """Quem recusa o clone é o helper, pela OUI — mas a regra não o convida
        por faixa: convidá-lo por faixa seria escrever a faixa dele num arquivo
        que decide quem recebe a cura, e a cura dele é a RECUSA."""
        texto = "\n".join(_linhas_de_regra()).lower()
        for oui in OUIS_CLONE:
            com_dois = ":".join(oui[i : i + 2] for i in (0, 2, 4))
            assert com_dois not in texto, (
                f"a regra 82 passou a casar `{com_dois}` por endereço — é o "
                "veneno do clone, não a cura dele"
            )

    @pytest.mark.skipif(shutil.which("udevadm") is None, reason="sem udevadm nesta máquina")
    def test_o_udev_aprova_a_sintaxe_e_a_regua_nao_e_no_op(self, tmp_path: Path) -> None:
        """`udevadm verify` sobre a regra de verdade — e sobre uma quebrada.

        A segunda metade é o que separa uma régua de um carimbo: se o `verify`
        aprovasse qualquer coisa, aprovar a nossa não significaria nada.
        """
        ok = subprocess.run(
            ["udevadm", "verify", str(REGRA)], capture_output=True, text=True, timeout=60
        )
        assert ok.returncode == 0, (
            f"o udev recusou a regra 82:\n{ok.stdout}\n{ok.stderr}"
        )

        quebrada = tmp_path / "82-quebrada.rules"
        quebrada.write_text(
            'ACTION=="add", SUBSYSTEM=="hid", CHAVE_QUE_NAO_EXISTE=="x", RUN+="/bin/true"\n',
            encoding="utf-8",
        )
        ruim = subprocess.run(
            ["udevadm", "verify", str(quebrada)], capture_output=True, text=True, timeout=60
        )
        assert ruim.returncode != 0, (
            "o `udevadm verify` aprovou uma chave inventada: a régua não está "
            "medindo nada, e o verde da regra de verdade não vale"
        )
