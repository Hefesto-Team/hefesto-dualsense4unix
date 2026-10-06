"""UMA-FAIXA-NÃO-É-UM-FABRICANTE-01 — o Pro dela parou de ser a definição de Pro."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.linhagem_nintendo import (
    OUIS_CLONE,
    OUIS_LINHAGEM_COM_DOIS_PONTOS,
    OUIS_NINTENDO_VISTAS,
    e_clone_conhecido,
    _e_da_linhagem_nintendo,
    e_pro_genuino,
    normalizar_oui,
    parece_pro,
)
from hefesto_dualsense4unix.daemon.subsystems.external_identity import ExternalImuEnabler

RAIZ = Path(__file__).resolve().parents[2]

OUI_CLONE_LITERAL = "e4:17:d8"

MAC_PRO_DE_OUTRA_SAFRA = "aa:bb:cc:00:00:11"

MAC_CLONE = f"{OUI_CLONE_LITERAL}:00:00:22"

MAC_PRO_DE_OUTRA_SAFRA_2 = "3c:9d:07:00:00:33"

_NOME_PRO = "Nintendo Co., Ltd. Pro Controller"


class TestPredicadoDaLinhagem:
    def test_a_lista_do_clone_continua_sendo_a_lista_completa(self) -> None:
        """A regra por negativa só se sustenta enquanto a 8BitDo tiver UMA faixa."""
        assert {o.replace(":", "") for o in (OUI_CLONE_LITERAL,)} == set(OUIS_CLONE)

    def test_a_forma_com_dois_pontos_e_derivada_nunca_redigitada(self) -> None:
        """Duas cópias da mesma faixa com pontuação diferente se separam."""
        derivada = {
            f"{o[0:2]}:{o[2:4]}:{o[4:6]}" for o in (OUIS_CLONE | OUIS_NINTENDO_VISTAS)
        }
        assert set(OUIS_LINHAGEM_COM_DOIS_PONTOS) == derivada
        assert OUI_CLONE_LITERAL in OUIS_LINHAGEM_COM_DOIS_PONTOS

    def test_pro_de_faixa_desconhecida_e_genuino(self) -> None:
        """O coração da sprint: uma faixa que esta casa nunca viu é um Pro."""
        for mac in (MAC_PRO_DE_OUTRA_SAFRA, MAC_PRO_DE_OUTRA_SAFRA_2):
            assert e_pro_genuino(uniq=mac, nome=_NOME_PRO, vid="057e", pid="2009"), mac

    def test_o_clone_nunca_e_genuino(self) -> None:
        """Mesmo nome, mesmo VID:PID — só a OUI o denuncia, e ela basta."""
        assert not e_pro_genuino(
            uniq=MAC_CLONE, nome=_NOME_PRO, vid="057e", pid="2009"
        )
        assert e_clone_conhecido(MAC_CLONE)

    def test_a_faixa_desta_bancada_continua_genuina(self) -> None:
        """A cura não pode quebrar o que JÁ funcionava — o Pro daqui."""
        daqui = sorted(OUIS_NINTENDO_VISTAS)[0]
        mac = f"{daqui[0:2]}:{daqui[2:4]}:{daqui[4:6]}:00:00:44"
        assert e_pro_genuino(uniq=mac, nome=_NOME_PRO, vid="057e", pid="2009")

    def test_sem_endereco_a_resposta_e_nao(self) -> None:
        """Sem OUI não dá para descartar o clone — a negativa é o lado seguro."""
        for vazio in (None, "", "   ", "nao-e-um-mac"):
            assert not e_pro_genuino(
                uniq=vazio, nome=_NOME_PRO, vid="057e", pid="2009"
            ), vazio

    def test_dualsense_nunca_recebe_tratamento_de_pro(self) -> None:
        """Um subcomando de hid-nintendo num DualSense seria o pior desfecho."""
        assert not parece_pro(nome="DualSense Wireless Controller", vid="054c", pid="0ce6")
        assert not e_pro_genuino(
            uniq="aa:bb:cc:00:00:55",
            nome="DualSense Wireless Controller",
            vid="054c",
            pid="0ce6",
        )

    def test_8bitdo_em_modo_xinput_nao_e_pro(self) -> None:
        """"8BitDo Pro 2" em X-input é gamepad comum — VID de fora, some."""
        assert not parece_pro(nome="8BitDo Pro 2", vid="2dc8", pid="3106")

    def test_normalizar_aceita_as_duas_formas_que_circulam(self) -> None:
        """`uniq` cru do sysfs e key canônica do registro dão a MESMA faixa."""
        assert normalizar_oui("aa:bb:cc:00:00:11") == "aabbcc"
        assert normalizar_oui("aabbcc000011") == "aabbcc"
        assert normalizar_oui("AA-BB-CC-00-00-11") == "aabbcc"
        assert normalizar_oui("aabb") is None
        assert normalizar_oui("zz:zz:zz:00:00:11") is None

    def test_a_linhagem_do_alias_inclui_o_clone_de_proposito(self) -> None:
        """Pergunta DIFERENTE: os dois leem o nome do host, então os dois contam."""
        assert _e_da_linhagem_nintendo(nome=_NOME_PRO, uniq=MAC_CLONE)
        assert _e_da_linhagem_nintendo(nome=_NOME_PRO, uniq=MAC_PRO_DE_OUTRA_SAFRA)
        assert _e_da_linhagem_nintendo(nome="Pro Controller", uniq=None)
        assert not _e_da_linhagem_nintendo(
            nome="DualSense Wireless Controller", uniq="aa:bb:cc:00:00:66"
        )


def _entrada(uniq: str, *, bus: str = "usb") -> dict[str, Any]:
    return {
        "name": _NOME_PRO,
        "vid": "057e",
        "pid": "2009",
        "bus": bus,
        "uniq": uniq,
        "driver": "nintendo",
        "evdev_path": "/dev/input/event7",
        "hidraw": "/dev/hidraw5",
    }


@pytest.fixture()
def escritas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Captura `enable_imu` — nunca toca hidraw de verdade."""
    import hefesto_dualsense4unix.core.external_leds as leds

    vistas: list[str] = []
    monkeypatch.setattr(
        leds, "enable_imu", lambda hidraw, *, packet_num=0: (vistas.append(hidraw), True)[1]
    )
    return vistas


class TestEnableImuNaMaquinaDeOutraPessoa:
    def test_pro_de_outra_safra_recebe_o_enable(self, escritas: list[str]) -> None:
        """O giroscópio de quem não tem o Pro DESTA bancada deixa de ficar mudo."""
        ExternalImuEnabler().tick([_entrada(MAC_PRO_DE_OUTRA_SAFRA)], now=0.0)
        assert escritas == ["/dev/hidraw5"]

    def test_clone_com_o_mesmo_nome_e_o_mesmo_vidpid_nao_recebe(
        self, escritas: list[str]
    ) -> None:
        """A contraprova obrigatória — sem ela a cura vira regressão do clone."""
        ExternalImuEnabler().tick([_entrada(MAC_CLONE)], now=0.0)
        assert escritas == []

    def test_os_dois_no_mesmo_inventario_separam_certo(
        self, escritas: list[str]
    ) -> None:
        """Na mesa real eles chegam juntos, e é aí que um predicado fraco falha."""
        inventario = [
            _entrada(MAC_CLONE),
            {**_entrada(MAC_PRO_DE_OUTRA_SAFRA), "hidraw": "/dev/hidraw9"},
        ]
        ExternalImuEnabler().tick(inventario, now=0.0)
        assert escritas == ["/dev/hidraw9"]

    def test_bluetooth_continua_bloqueado(self, escritas: list[str]) -> None:
        """FASE 1 não mudou: a cura é sobre QUEM, não sobre por onde."""
        ExternalImuEnabler().tick(
            [_entrada(MAC_PRO_DE_OUTRA_SAFRA, bus="bluetooth")], now=0.0
        )
        assert escritas == []

    def test_dualsense_no_inventario_nao_recebe_subcomando_de_nintendo(
        self, escritas: list[str]
    ) -> None:
        """O pior desfecho possível desta cura, medido para nunca acontecer."""
        ds = {
            **_entrada("aa:bb:cc:00:00:77"),
            "name": "DualSense Wireless Controller",
            "vid": "054c",
            "pid": "0ce6",
            "driver": "playstation",
        }
        ExternalImuEnabler().tick([ds], now=0.0)
        assert escritas == []


_CASA_UNICA = "src/hefesto_dualsense4unix/core/linhagem_nintendo.py"

_TRIPLA = re.compile(r"(?<![0-9a-fA-F:])([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){2})(?![0-9a-fA-F:])")


def _registro_de_ouis_reais() -> frozenset[str]:
    """As OUIs de hardware REAL que a casa vigia — lidas de OUTRO arquivo."""
    texto = (RAIZ / "scripts/check_anonymity.sh").read_text(encoding="utf-8")
    bloco = re.search(r"^OUIS = \((.*?)\)$", texto, re.S | re.M)
    assert bloco is not None, "o registro de OUIs sumiu do check_anonymity.sh"
    achadas = re.findall(r'"([0-9a-f]{6})"', bloco.group(1))
    assert len(achadas) >= 4, f"registro pequeno demais para ser o certo: {achadas}"
    return frozenset(achadas)


def _literais_executaveis(caminho: Path) -> list[tuple[int, str]]:
    """Strings de um `.py` que CHEGAM À EXECUÇÃO — docstrings de fora."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    docs = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            corpo = getattr(no, "body", None)
            if (
                corpo
                and isinstance(corpo[0], ast.Expr)
                and isinstance(corpo[0].value, ast.Constant)
                and isinstance(corpo[0].value.value, str)
            ):
                docs.add(id(corpo[0].value))
    return [
        (no.lineno, no.value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant)
        and isinstance(no.value, str)
        and id(no) not in docs
    ]


class TestPortaoDaFaixaUnica:
    """O portão que vale mais que a cura: impede o PRÓXIMO."""

    def test_nenhuma_faixa_oui_escrita_a_mao_fora_da_casa_unica(self) -> None:
        """Toda faixa em `src/` vem de `core/linhagem_nintendo`, ou reprova."""
        registro = _registro_de_ouis_reais()
        culpados: list[str] = []
        for arquivo in sorted((RAIZ / "src").rglob("*.py")):
            relativo = arquivo.relative_to(RAIZ).as_posix()
            if relativo == _CASA_UNICA:
                continue
            for linha, valor in _literais_executaveis(arquivo):
                cru = valor.strip().lower()
                if cru.replace(":", "").replace("-", "") in registro and len(cru) <= 17:
                    culpados.append(f"{relativo}:{linha}: {valor!r}")
                    continue
                for achado in _TRIPLA.finditer(valor):
                    if any(c in "abcdef" for c in achado.group(1).lower()):
                        culpados.append(f"{relativo}:{linha}: {achado.group(1)}")
        assert not culpados, (
            "faixa OUI escrita à mão fora da casa única.\n"
            f"A casa única é {_CASA_UNICA} — importe de lá.\n"
            "Uma faixa é a identidade de UMA unidade; usá-la como identidade de\n"
            "MODELO é o defeito que a UMA-FAIXA-NÃO-É-UM-FABRICANTE-01 curou.\n"
            + "\n".join(culpados)
        )

    def test_nenhuma_oui_real_nova_entra_em_script_ou_regra(self) -> None:
        """`scripts/` e `assets/` só podem citar faixas que o produto declara."""
        declaradas = set(OUIS_CLONE) | set(OUIS_NINTENDO_VISTAS)
        registro = _registro_de_ouis_reais()
        culpados: list[str] = []
        for pasta, sufixos in (
            ("scripts", (".py", ".sh")),
            ("assets", (".rules", ".conf")),
        ):
            for arquivo in sorted((RAIZ / pasta).rglob("*")):
                if not arquivo.is_file() or arquivo.suffix not in sufixos:
                    continue
                relativo = arquivo.relative_to(RAIZ).as_posix()
                if relativo.endswith("check_anonymity.sh") or "/dkms/" in relativo:
                    continue
                if arquivo.suffix == ".py":
                    pares = _literais_executaveis(arquivo)
                else:
                    pares = [
                        (n, linha)
                        for n, linha in enumerate(
                            arquivo.read_text(encoding="utf-8").splitlines(), 1
                        )
                        if not linha.lstrip().startswith("#")
                    ]
                for linha, valor in pares:
                    for achado in _TRIPLA.finditer(valor):
                        faixa = achado.group(1).lower().replace(":", "")
                        if faixa in registro and faixa not in declaradas:
                            culpados.append(f"{relativo}:{linha}: {achado.group(1)}")
        assert not culpados, (
            "OUI de hardware real citada em script/regra sem estar declarada em\n"
            f"{_CASA_UNICA}. Registre-a lá — é de lá que o produto decide.\n"
            + "\n".join(culpados)
        )


_REGRA_84 = "assets/84-nintendo-pro-variant.rules"
_CHAVE = re.compile(r'(\w+)(?:\{(\w+)\})?\s*(==|!=|\+=|=)\s*"([^"]*)"')


def _regras_da_84() -> list[list[tuple[str, str, str]]]:
    """Cada linha de regra como lista de ``(chave, operador, valor)``."""
    saida = []
    for linha in (RAIZ / _REGRA_84).read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        saida.append(
            [
                (interno or chave, op, valor)
                for chave, interno, op, valor in _CHAVE.findall(linha)
            ]
        )
    return saida


def _variante_atribuida(
    regras: list[list[tuple[str, str, str]]], device: dict[str, str]
) -> list[str]:
    """As variantes que as regras CASADAS atribuiriam a este device."""
    atribuidas = []
    for regra in regras:
        casou = True
        for chave, op, valor in regra:
            if op not in ("==", "!="):
                continue
            atual = device.get(chave)
            if atual is None:
                casou = False
                break
            bate = atual in valor.split("|")
            if (op == "==" and not bate) or (op == "!=" and bate):
                casou = False
                break
        if not casou:
            continue
        for chave, op, valor in regra:
            if op == "=" and chave == "HEFESTO_CONTROLLER_VARIANT":
                atribuidas.append(valor)
    return atribuidas


def _device(bcd: str, subsistema: str) -> dict[str, str]:
    return {
        "ACTION": "add",
        "SUBSYSTEM": subsistema,
        "DEVTYPE": "usb_device",
        "idVendor": "057e",
        "idProduct": "2009",
        "bcdDevice": bcd,
    }


class TestRegra84SabeDizerNaoSei:
    @pytest.mark.parametrize("subsistema", ["usb", "hid", "hidraw", "input"])
    @pytest.mark.parametrize(
        ("bcd", "esperado"),
        [
            ("0210", "nintendo-pro"),
            ("0200", "8bitdo-pro-clone"),
            ("0211", "nintendo-pro-desconhecido"),
            ("0301", "nintendo-pro-desconhecido"),
        ],
    )
    def test_toda_revisao_recebe_exatamente_uma_variante(
        self, subsistema: str, bcd: str, esperado: str
    ) -> None:
        """Nenhuma revisão de firmware fica sem resposta — nem com duas."""
        atribuidas = _variante_atribuida(_regras_da_84(), _device(bcd, subsistema))
        assert atribuidas == [esperado], (
            f"{subsistema} / bcdDevice={bcd}: esperava exatamente "
            f"['{esperado}'], veio {atribuidas}"
        )

    def test_o_desconhecido_nao_cria_symlink(self) -> None:
        """"Não sei" não pode virar palpite: symlink com nome de modelo afirma."""
        texto = (RAIZ / _REGRA_84).read_text(encoding="utf-8")
        for linha in texto.splitlines():
            if "nintendo-pro-desconhecido" in linha and not linha.lstrip().startswith("#"):
                assert "SYMLINK" not in linha, linha


class TestNenhumCaminhoDeCasaNaArvore:
    def test_o_retrato_deduz_a_raiz_do_proprio_arquivo(self) -> None:
        """Quem clonar o repo tem de conseguir rodar."""
        retratista = RAIZ / "src/hefesto_dualsense4unix/interface/olhar.py"
        dono_da_raiz = RAIZ / "src/hefesto_dualsense4unix/interface/onde.py"

        for alvo in (retratista, dono_da_raiz):
            assert alvo.is_file(), (
                f"{alvo.relative_to(RAIZ)} sumiu. Se o retratista mudou de casa "
                "de novo, este teste muda com ele — apagá-lo devolve o defeito "
                "de 22/08/2026, em que só a máquina dela rodava o script."
            )
            for linha, valor in _literais_executaveis(alvo):
                assert not valor.startswith("/home/"), (
                    f"{alvo.name}:{linha}: {valor!r}"
                )

        codigo = dono_da_raiz.read_text(encoding="utf-8")
        assert "parents[3]" in codigo, (
            "o `onde.py` deixou de deduzir a raiz de `__file__`. Ele é o único "
            "lugar onde as duas pastas de página têm endereço; uma raiz cravada "
            "aqui reescreveria o mockup DELA a partir de qualquer cópia — foi o "
            "que se mediu em 28/08/2026, em oito arquivos."
        )
        assert dono_da_raiz.resolve().parents[3] == RAIZ.resolve()
        assert (RAIZ / "pyproject.toml").exists()

    def test_nenhum_script_traz_o_home_dela_como_padrao(self) -> None:
        """A varredura inteira, para o defeito não voltar por outro arquivo.

        **A VARREDURA CRESCEU DUAS VEZES EM 08/09/2026, e a segunda é a que
        importa.** Ela olhava `scripts/` e mais nada — desenhada quando todo
        instrumento desta casa morava lá. A interface mudou para dentro do
        `src/` em 01/09, e com ela o retratista, os dez geradores e o dono das
        duas pastas de página; a primeira volta de hoje acrescentou
        `interface/` para alcançá-los.

        **PAROU NA PASTA ERRADA, e o conferente mediu o preço.** Ele plantou o
        mesmo literal que a cura de hoje tirou — um caminho absoluto de `$HOME`
        apontando para um SVG — em três arquivos, `count() == 1` conferido em
        cada um:

        ===============================  =======================================
        arquivo                          contra a régua de antes
        ===============================  =======================================
        `interface/monta.py`             reprova (o alcance recém-ganho)
        `app/gui_prefs.py`               **VERDE**
        `daemon/ipc_handlers.py`         **VERDE**
        ===============================  =======================================

        **As duas últimas estão dentro do que o wheel empacota** —
        `[tool.hatch.build.targets.wheel] packages = ["src/hefesto_dualsense4unix"]`
        leva o pacote INTEIRO —, e era esse o argumento do achado original:
        quem instalasse o Hefesto receberia o caminho da casa de outra pessoa.
        *A régua ficava verde porque o defeito mudava de pasta*, e continuaria
        verdadeira uma mudança de pasta adiante. Por isso o alvo agora é o
        pacote inteiro: a fronteira que importa é a do WHEEL, não a de uma
        subpasta.

        **O CUSTO FOI MEDIDO ANTES DE ALARGAR, e é zero.** A varredura do
        `src/` inteiro acusa **0 ocorrências** hoje — inclusive com um padrão
        mais largo que este (sem exigir barra final e casando em qualquer ponto
        da string). Não há uma única ocorrência legítima a declarar, e portanto
        nenhuma isenção foi aberta: se aparecer uma amanhã, ela se declara
        sozinha, com a razão, nunca em bloco.

        **O QUE ESTA RÉGUA NÃO É:** a companheira dela em
        `test_luz_cega_e8_o_berco_nao_vaza.py` (RÉGUA 1) varre o `src/` inteiro
        desde sempre, mas só enxerga `Path.home()` / `expanduser()` chamados no
        NÍVEL DO MÓDULO — e isso está certo, é a definição do defeito dela
        (constante avaliada na importação, fora do alcance das fixtures). As
        duas passavam verdes sobre o mesmo literal, cada uma por metade: aquela
        vê a chamada e não o literal, esta via o literal e não a pasta. Só esta
        se alarga; alargar aquela seria trocar o defeito que ela mede.
        """
        culpados = []
        pastas = (RAIZ / "scripts", RAIZ / "src" / "hefesto_dualsense4unix")
        for pasta in pastas:
            for arquivo in sorted(pasta.rglob("*.py")):
                for linha, valor in _literais_executaveis(arquivo):
                    if re.match(r"^/home/[^/]+/", valor):
                        culpados.append(
                            f"{arquivo.relative_to(RAIZ).as_posix()}:{linha}: {valor!r}"
                        )
        assert not culpados, (
            "caminho absoluto de $HOME no pacote ou nos scripts:\n"
            + "\n".join(culpados)
            + "\n\nO `src/hefesto_dualsense4unix` inteiro vai para o wheel: "
            "quem instalar o Hefesto recebe este caminho, que é a casa de uma "
            "pessoa só. Resolva na CHAMADA (`pathlib.Path.home() / ...`), "
            "nunca no literal."
        )


class TestRotuloDoVerBotao:
    """`scripts/ver_botao.py` roda na frente do usuário, e mentia o nome do aparelho."""

    @staticmethod
    def _rotulo(nome: str, uniq: str | None) -> str:
        import importlib.util

        caminho = RAIZ / "scripts/ver_botao.py"
        spec = importlib.util.spec_from_file_location("_ver_botao_sob_teste", caminho)
        assert spec is not None and spec.loader is not None
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)

        class _Dubl:
            def __init__(self) -> None:
                self.name = nome
                self.uniq = uniq

        return str(modulo.rotulo(_Dubl()))

    def test_pro_de_outra_safra_nao_e_apresentado_como_clone(self) -> None:
        """O defeito visível da A1: o Pro genuíno de outra faixa lido em voz alta."""
        assert self._rotulo(_NOME_PRO, MAC_PRO_DE_OUTRA_SAFRA) == "Pro (Nintendo)"

    def test_o_clone_continua_sendo_chamado_de_clone(self) -> None:
        assert "8BitDo" in self._rotulo(_NOME_PRO, MAC_CLONE)

    def test_sem_endereco_o_rotulo_nao_afirma(self) -> None:
        """Por cabo o `uniq` pode vir vazio — e aí não se sabe, e diz-se isso."""
        assert self._rotulo(_NOME_PRO, "") == "Pro (indistinguível)"
