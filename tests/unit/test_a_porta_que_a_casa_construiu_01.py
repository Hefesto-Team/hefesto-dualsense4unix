"""A-PORTA-QUE-A-CASA-CONSTRUIU-01 — os instrumentos batem na porta certa.

O DEFEITO QUE ESTES TESTES IMPEDEM DE VOLTAR
--------------------------------------------
Medido em 15/08/2026, com a mesa 2+2 montada (dois DualSense no cabo, dois no
rádio): **nenhum dos quatro controles físicos podia ser aberto por um processo
dela**. Os quatro gamepads virtuais podiam. `scripts/capture_blueprint.py`
falhava com `'/dev/hidraw8' inacessível ([Errno 13] Permission denied)`, o
censo dos dezessete feature reports não pôde ser feito, e a leitura da cor
esbarrava na mesma porta.

**A causa não é a que parecia, e a diferença importa muito.** A leitura fácil
— e um relatório daquele dia a fez — era que a regra udev não cobria
o Bluetooth. Está errada, e mandaria consertar o lugar errado:
`assets/70-ps5-controller.rules` está instalada, idêntica à árvore, e PEGOU
(`CURRENT_TAGS=:seat:uaccess:`). Quem tira a ACL é **o próprio Hefesto**, de
propósito — `broker/hidraw_broker.py`, `setfacl -b` + `chmod 0600` — para que o
jogo veja só o vpad. Não é bug: é o produto funcionando.

E a casa **já tinha construído a porta**: o broker devolve um descritor
`O_RDWR` do nó escondido, por `SCM_RIGHTS`, no socket
`/run/hefesto-hidraw-broker/broker.sock`. O defeito era que os instrumentos
não a usavam.

AS TRÊS MORDIDAS
----------------
1. o instrumento que abre o nó escondido (a principal: é a que impede o
   próximo instrumento de nascer cego);
2. a queda silenciosa para `open()` direto;
3. o zero que vem do grab, e não do aparelho.

O QUE ESTES TESTES **NÃO** PROVAM: que o broker devolve o fd certo. Isso já
tem dono e teste próprios (`test_hidraw_broker_protocol.py`,
`test_hidraw_broker_client.py`). O que estas mordidas provam é que os
instrumentos **pedem por ali**.
"""
from __future__ import annotations

import ast
import errno
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
    GRAB_DE_TERCEIRO,
    GRAB_LIVRE,
    GRAB_SEM_NO,
    GRAB_SEM_PERMISSAO,
    PORTA_BROKER,
    PORTA_DIRETA,
    PortaFechadaError,
    abrir_hidraw,
    estado_do_grab,
    leitura_de_zero,
    linha_da_porta,
)

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "scripts"


_PREFIXOS_QUE_NAO_SAO_O_NO = ("/sys/", "/proc/", "/dev/input")

EXCECOES: dict[str, str] = {
    "install_udev.sh": (
        "escreve a REGRA udev; a única menção é a linha de instrução "
        "'ls -l /dev/hidraw*' que ele imprime para a pessoa conferir. Não abre nó."
    ),
    "install-host-udev.sh": (
        "mesmo caso do install_udev.sh: instala a regra no host e imprime "
        "'Confira com: ls -l /dev/hidraw*'. Não abre nó."
    ),
    "doctor.sh": (
        "LISTA nós (`[[ -e ]]` e `ls`, que não fazem open(2)) para dizer quantos "
        "existem. Quando precisa de um fd de verdade — o teste funcional do "
        "fd-injection — pede ao BROKER pelo cmd `open`/SCM_RIGHTS, em "
        "check_hidraw_broker, e declara a porta na tela."
    ),
    "regra_do_no_aberta.sh": (
        "escreve por `sed` a variante ABERTA do 73-hefesto-ps5-controller.rules, para "
        "quem instala a regra sem o broker. A menção a /dev/hidraw está no "
        "comentário que explica as duas metades da cura. Não abre nó."
    ),
    "disable_steam_input.sh": (
        "edita arquivos .vdf da Steam; as menções a hidraw descrevem o que a "
        "STEAM faz com o nó, não o que este script faz. Não abre nó."
    ),
    "banco_de_prova/sonda_plastico.py": (
        "abre o /dev/uhid para CRIAR um DualSense de mentira (UHID_CREATE2), no "
        "runner do CI ou numa VM; não abre o nó de controle nenhum, e nunca roda "
        "na máquina do usuário, onde o uhid é do produto."
    ),
    "banco_de_prova/sonda.sh": (
        "LISTA os nós (`ls -l` e `getfacl`, que não fazem open(2)) para gravar a ACL "
        "que o runner do CI dá ao aparelho de mentira. Não abre nó, e nunca roda na "
        "máquina do usuário."
    ),
}

USAM_O_CLIENTE = (
    "capture_blueprint.py",
    "ensaio_rumble_um_bit_por_vez.py",
    "ensaio_o_keepalive_mata_o_rumble.py",
    "ensaios/censo_features.py",
)

DECLARAM_A_PORTA: dict[str, str] = {
    "capture_blueprint.py": "declaracao_da_porta()",
    "ensaio_rumble_um_bit_por_vez.py": "declaracao_da_porta()",
    "ensaio_o_keepalive_mata_o_rumble.py": "declaracao_da_porta()",
    "ensaio_rumble_em_par.py": "declaracao_da_porta()",
    "ensaios/censo_features.py": "cabecalho_do_instrumento(",
    "ensaios/taxa_de_entrada.py": "cabecalho_do_instrumento(",
    "record_hid_capture.py": "declaracao_da_porta()",
    "doctor.sh": "porta: broker (SCM_RIGHTS)",
    "disable_steam_input.sh": "este script NÃO ABRE /dev/hidraw*",
}


def _aberturas_diretas_em_python(caminho: Path) -> list[tuple[int, str]]:
    """`(linha, expressão)` de cada `open()` cujo caminho é um nó de aparelho."""
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    except (OSError, SyntaxError):  # pragma: no cover - script quebrado é outro teste
        return []
    achados: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or not no.args:
            continue
        alvo = no.func
        nome = ""
        if isinstance(alvo, ast.Name):
            nome = alvo.id
        elif isinstance(alvo, ast.Attribute):
            nome = alvo.attr
        if nome not in ("open", "fdopen"):
            continue
        expressao = ast.unparse(no.args[0])
        baixo = expressao.lower()
        if any(prefixo in baixo for prefixo in _PREFIXOS_QUE_NAO_SAO_O_NO):
            continue
        if "hidraw" in baixo or "/dev/" in baixo:
            achados.append((no.lineno, expressao))
    return achados


def _mencoes_em_shell(caminho: Path) -> list[int]:
    """Linhas de um `.sh` que mencionam `/dev/hidraw` — comentário incluído."""
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover
        return []
    return [
        numero
        for numero, linha in enumerate(texto.splitlines(), start=1)
        if "/dev/hidraw" in linha
    ]


def _relativo(caminho: Path) -> str:
    return caminho.relative_to(SCRIPTS).as_posix()


def test_mordida_1_nenhum_instrumento_abre_dev_hidraw_por_conta_propria() -> None:
    """Ninguém em `scripts/` faz `open()` de um nó de aparelho sem justificar."""
    infratores: list[str] = []
    for arquivo in sorted(SCRIPTS.rglob("*.py")):
        if "__pycache__" in arquivo.parts:
            continue
        relativo = _relativo(arquivo)
        for linha, expressao in _aberturas_diretas_em_python(arquivo):
            if relativo in EXCECOES:
                continue
            infratores.append(f"scripts/{relativo}:{linha} — open({expressao})")
    assert not infratores, (
        "instrumento abrindo o nó do aparelho por conta própria:\n  "
        + "\n  ".join(infratores)
        + "\n\nA porta é o broker: use `abrir_no_hidraw` (scripts/ensaios/comum.py),"
        " que cai para `open()` DECLARANDO a queda. Se este arquivo de fato não"
        " abre o nó, ponha-o em EXCECOES com o motivo por escrito."
    )


def test_mordida_1_todo_shell_que_fala_de_hidraw_tem_motivo_escrito() -> None:
    """Cada `.sh` que menciona `/dev/hidraw` está na lista, com motivo."""
    sem_motivo: list[str] = []
    for arquivo in sorted(SCRIPTS.rglob("*.sh")):
        relativo = _relativo(arquivo)
        linhas = _mencoes_em_shell(arquivo)
        if linhas and relativo not in EXCECOES:
            sem_motivo.append(f"scripts/{relativo}: linhas {linhas}")
    assert not sem_motivo, (
        "shell mencionando /dev/hidraw sem justificativa na lista de exceções:\n  "
        + "\n  ".join(sem_motivo)
    )


def test_mordida_1_a_lista_de_excecoes_nao_acumula_entrada_morta() -> None:
    """Exceção que já não corresponde a nada some — senão vira permissão geral."""
    mortas: list[str] = []
    for relativo, motivo in EXCECOES.items():
        arquivo = SCRIPTS / relativo
        assert motivo.strip(), f"exceção sem motivo escrito: {relativo}"
        if not arquivo.exists():
            mortas.append(f"{relativo}: o arquivo não existe mais")
            continue
        if arquivo.suffix == ".sh":
            if not _mencoes_em_shell(arquivo):
                mortas.append(f"{relativo}: já não menciona /dev/hidraw")
        elif not _aberturas_diretas_em_python(arquivo):
            mortas.append(f"{relativo}: já não abre nó por conta própria")
    assert not mortas, "entradas mortas em EXCECOES:\n  " + "\n  ".join(mortas)


@pytest.mark.parametrize("relativo", USAM_O_CLIENTE)
def test_mordida_1_os_instrumentos_usam_o_cliente_unico(relativo: str) -> None:
    """Quem abre hidraw abre pelo cliente do broker — não por `open()`."""
    fonte = (SCRIPTS / relativo).read_text(encoding="utf-8")
    assert "abrir_no_hidraw(" in fonte, (
        f"scripts/{relativo} deveria abrir o hidraw por `abrir_no_hidraw`, o "
        "cliente único (scripts/ensaios/comum.py → integrations/"
        "hidraw_broker_client.abrir_hidraw)."
    )


def test_mordida_2_sem_broker_a_queda_para_open_direto_e_declarada(
    tmp_path: Path,
) -> None:
    """Broker inexistente ⇒ abre por `open()` E DIZ que foi por `open()`."""
    alvo = tmp_path / "nao-e-hidraw-mas-abre.bin"
    alvo.write_bytes(b"")
    aberto = abrir_hidraw(
        str(alvo), escrita=False, socket_path=str(tmp_path / "broker-que-nao-existe.sock")
    )
    try:
        assert aberto.porta == PORTA_DIRETA
        assert aberto.motivo.strip(), "queda sem motivo é queda silenciosa"
        assert PORTA_DIRETA in aberto.linha_de_relatorio
        assert "broker-que-nao-existe.sock" in aberto.motivo, (
            "o motivo tem de dizer QUAL socket faltou — 'não achei o broker' sem "
            "o caminho manda a próxima pessoa procurar no lugar errado"
        )
    finally:
        aberto.fechar()


def test_mordida_2_com_broker_a_porta_declarada_e_a_do_broker(tmp_path: Path) -> None:
    """Broker que serve o fd ⇒ a porta declarada é a do broker, não a direta."""
    alvo = tmp_path / "servido-pelo-broker.bin"
    alvo.write_bytes(b"")
    fd = os.open(alvo, os.O_RDONLY)

    class ClienteDeMentira:
        def abrir_no(self, no: str) -> tuple[int, str]:
            return fd, f"o broker serviu o fd (nó hidden) para {no}"

        def close(self) -> None:  # pragma: no cover - o dublê não abre socket
            pass

    aberto = abrir_hidraw(str(alvo), cliente=ClienteDeMentira())
    try:
        assert aberto.porta == PORTA_BROKER
        assert PORTA_BROKER in aberto.linha_de_relatorio
    finally:
        aberto.fechar()


def test_mordida_2_as_duas_portas_fechadas_nunca_viram_silencio(tmp_path: Path) -> None:
    """Sem broker e sem permissão: erro que NOMEIA as duas tentativas."""
    with pytest.raises(PortaFechadaError) as capturado:
        abrir_hidraw(
            str(tmp_path / "nao-existe-em-lugar-nenhum"),
            socket_path=str(tmp_path / "broker-que-nao-existe.sock"),
        )
    mensagem = str(capturado.value)
    assert PORTA_BROKER in mensagem
    assert PORTA_DIRETA in mensagem
    assert "escondendo o físico" in mensagem


def test_mordida_2_o_relatorio_do_instrumento_contem_a_porta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O relatório de um instrumento REAL nomeia a porta que ele usou."""
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(tmp_path / "sem-broker.sock"))
    modulo = _carregar_script("capture_blueprint.py")
    modulo.main("hidraw-que-nao-existe-neste-teste")
    saida = capsys.readouterr().out
    assert PORTA_DIRETA in saida, (
        "o cabeçalho do instrumento não declarou a porta. Um relatório que não "
        "diz por onde mediu não pode ser comparado com o do outro braço do 2+2."
    )
    assert "sem-broker.sock" in saida


def test_mordida_2_a_linha_da_porta_sempre_carrega_a_porta() -> None:
    """O formato único da declaração — um só, em toda a casa."""
    linha = linha_da_porta(PORTA_BROKER, "o broker responde em /run/x.sock")
    assert PORTA_BROKER in linha
    assert "porta" in linha


class _IoctlFalso:
    """Um `fcntl.ioctl` de mentira que grava o que lhe pediram."""

    def __init__(self, *, ocupado: bool) -> None:
        self.ocupado = ocupado
        self.chamadas: list[tuple[int, int]] = []

    def __call__(self, fd: int, requisicao: int, argumento: int) -> int:
        self.chamadas.append((requisicao, argumento))
        if self.ocupado and argumento == 1:
            raise OSError(errno.EBUSY, "Device or resource busy")
        return 0


def test_mordida_3_grab_de_terceiro_e_distinguivel_de_grab_livre(
    tmp_path: Path,
) -> None:
    """`EBUSY` no EVIOCGRAB vira "PEGO", não "livre" e não silêncio."""
    no = tmp_path / "event999"
    no.write_bytes(b"")
    ocupado = _IoctlFalso(ocupado=True)
    livre = _IoctlFalso(ocupado=False)
    assert estado_do_grab(str(no), ioctl=ocupado) == GRAB_DE_TERCEIRO
    assert estado_do_grab(str(no), ioctl=livre) == GRAB_LIVRE


def test_mordida_3_o_grab_tomado_e_devolvido_no_mesmo_instante(
    tmp_path: Path,
) -> None:
    """Se o nó estava LIVRE, o instrumento solta o que pegou. Sempre."""
    no = tmp_path / "event998"
    no.write_bytes(b"")
    livre = _IoctlFalso(ocupado=False)
    assert estado_do_grab(str(no), ioctl=livre) == GRAB_LIVRE
    argumentos = [argumento for _requisicao, argumento in livre.chamadas]
    assert argumentos == [1, 0], (
        "o grab foi tomado e NÃO devolvido — o instrumento passaria a ser ele "
        f"o terceiro que cala o nó de todo mundo (chamadas: {livre.chamadas})"
    )


def test_mordida_3_no_inexistente_e_sem_permissao_sao_respostas_diferentes(
    tmp_path: Path,
) -> None:
    """Três impossibilidades distintas, três frases distintas."""
    assert estado_do_grab(str(tmp_path / "nao-existe")) == GRAB_SEM_NO

    def _sem_permissao(_caminho: str, _flags: int) -> int:
        raise PermissionError(errno.EACCES, "Permission denied")

    no = tmp_path / "event997"
    no.write_bytes(b"")
    assert estado_do_grab(str(no), abrir=_sem_permissao) == GRAB_SEM_PERMISSAO


def test_mordida_3_zero_com_grab_nao_e_o_mesmo_zero_sem_grab() -> None:
    """"O controle não emitiu" e "eu não posso ler" saem DIFERENTES na tela."""
    calado = leitura_de_zero(GRAB_LIVRE)
    escondido = leitura_de_zero(GRAB_DE_TERCEIRO)
    assert calado != escondido
    assert "EVIOCGRAB" in escondido
    assert "não emitiu" in calado
    assert "EVIOCGRAB" not in calado


def test_mordida_3_o_instrumento_de_evdev_pergunta_o_grab_em_vez_de_inferir() -> None:
    """`taxa_de_entrada.py` MEDE o grab; não o deduz do daemon estar vivo."""
    fonte = (SCRIPTS / "ensaios" / "taxa_de_entrada.py").read_text(encoding="utf-8")
    assert "estado_do_grab(" in fonte
    assert "leitura_de_zero(" in fonte
    assert "and daemon.rodando" not in fonte, (
        "a decisão de 'MUDO' voltou a ser inferida do daemon estar vivo, em vez "
        "de perguntada ao nó"
    )


def test_mordida_3_o_valor_da_celula_muda_com_o_grab() -> None:
    """A célula da tabela de `taxa_de_entrada.py`, exercitada de verdade."""
    pytest.importorskip("evdev")
    modulo = _carregar_script("ensaios/taxa_de_entrada.py")
    contagem = modulo.Contagem("/dev/input/event999", "DualSense", _dono_de_mentira())
    contagem.segundos = 5.0
    assert modulo._valor(contagem, 0, GRAB_DE_TERCEIRO) != modulo._valor(
        contagem, 0, GRAB_LIVRE
    )
    assert "EVIOCGRAB" in modulo._valor(contagem, 0, GRAB_DE_TERCEIRO)


@pytest.mark.parametrize(("relativo", "trecho"), sorted(DECLARAM_A_PORTA.items()))
def test_e3_todo_instrumento_declara_a_porta_no_relatorio(
    relativo: str, trecho: str
) -> None:
    """A regra da casa vale para a porta como vale para a biblioteca."""
    fonte = (SCRIPTS / relativo).read_text(encoding="utf-8")
    assert trecho in fonte, (
        f"scripts/{relativo} deixou de declarar a porta no relatório "
        f"(esperava encontrar {trecho!r})"
    )


def test_e3_o_cabecalho_dos_ensaios_traz_porta_e_grab(tmp_path: Path) -> None:
    """O bloco compartilhado imprime a porta, e o grab de cada nó de evdev."""
    comum = _carregar_script("ensaios/comum.py")
    no = tmp_path / "event996"
    no.write_bytes(b"")
    texto = comum.cabecalho_do_instrumento(
        "teste.py",
        "o cabeçalho declara a porta?",
        bibliotecas=["os"],
        nos_evdev=[str(no)],
    )
    assert "porta ..." in texto
    assert "grab do evdev ...." in texto
    assert str(no) in texto


def _carregar_script(relativo: str) -> types.ModuleType:
    """Importa um script de `scripts/` pelo caminho, sem instalá-lo."""
    caminho = SCRIPTS / relativo
    nome = "instrumento_" + relativo.replace("/", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _dono_de_mentira() -> object:
    """Um `Aparelho` mínimo — a célula só olha o apelido e o transporte."""
    comum = _carregar_script("ensaios/comum.py")
    return comum.Aparelho(
        hidraw="hidraw999",
        caminho_hidraw="/dev/hidraw999",
        dir_device="/sys/class/hidraw/hidraw999/device",
        mac="",
        nome="DualSense de mentira",
        transporte=comum.CABO,
        e_vpad=False,
        rotulo="",
    )


_PRINCIPAL = "aa:bb:cc:00:00:01"


def _estado_do_daemon(grab: str, *, emulando: bool = True) -> dict[str, object]:
    return {
        "gamepad_emulation": {"enabled": emulando},
        "primary_grab_state": grab,
        "controllers": [{"uniq": _PRINCIPAL, "connected": True, "is_primary": True}],
    }


def _perguntas() -> tuple[dict[str, list[object]], dict[str, object]]:
    feitas: dict[str, list[object]] = {"porta": [], "grab": []}

    def porta() -> tuple[str, str]:
        feitas["porta"].append(True)
        return PORTA_BROKER, "o broker responde em /run/de-mentira.sock"

    def grab(caminho: str, *, abrir: object) -> str:
        feitas["grab"].append((caminho, callable(abrir)))
        return GRAB_DE_TERCEIRO

    def nos() -> dict[str, str]:
        return {_PRINCIPAL.upper(): "/dev/input/event-de-mentira"}

    return feitas, {"porta": porta, "grab": grab, "nos": nos}


def test_o_exame_da_08_diz_a_causa_do_controle_que_o_hefesto_nao_segura(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Com o grab que FALHOU, o exame pergunta à porta e ao nó, escreve as duas"""
    from hefesto_dualsense4unix.app.actions.home_actions import AVISO_DE_GRAB_LINHA
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    feitas, dubles = _perguntas()
    item = a08_conexoes._conferencia_da_leitura(_estado_do_daemon("failed"), **dubles)
    assert item is not None
    assert item.chave == a08_conexoes.CHAVE_DA_LEITURA
    assert item.estado == "atencao"  # (noqa-acento): chave de máquina do exame
    assert item.porque == f"{AVISO_DE_GRAB_LINHA}."
    assert feitas["porta"] and feitas["grab"] == [("/dev/input/event-de-mentira", True)]
    diario = capsys.readouterr().err
    assert linha_da_porta(PORTA_BROKER, "o broker responde em /run/de-mentira.sock") in diario
    assert "grab do evdev .... /dev/input/event-de-mentira: " + GRAB_DE_TERCEIRO in diario
    assert leitura_de_zero(GRAB_DE_TERCEIRO) in diario


@pytest.mark.parametrize(("grab", "emulando"), [
    ("held", True), ("pending", True), ("off", True), ("failed", False),
])
def test_sem_o_aviso_do_dono_o_exame_nao_toca_no_no(grab: str, emulando: bool) -> None:
    """O grab que o Hefesto segura, o que ainda abre, e o modo sem o controle do"""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    feitas, dubles = _perguntas()
    estado = _estado_do_daemon(grab, emulando=emulando)
    assert a08_conexoes._conferencia_da_leitura(estado, **dubles) is None
    assert feitas == {"porta": [], "grab": []}


def test_o_interrogacao_e_a_sugestao_sao_as_duas_metades_do_dono() -> None:
    """O `?` leva o porquê e o cartão da dica leva o que fazer — as duas"""
    from hefesto_dualsense4unix.app.actions.home_actions import AVISO_DE_GRAB_PORQUE
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    _feitas, dubles = _perguntas()
    item = a08_conexoes._conferencia_da_leitura(_estado_do_daemon("failed"), **dubles)
    porque, cura = a08_conexoes._o_porque_e_a_cura_do_dono()
    assert cura and cura.lower() in AVISO_DE_GRAB_PORQUE.lower()
    assert porque.rstrip(".") in AVISO_DE_GRAB_PORQUE and cura not in porque
    dica = a08_conexoes._dica_da_linha(item)
    assert porque.split(",")[0] in dica and dica.count(cura.split(",")[-1].strip()) == 1
    cartao = a08_conexoes._o_painel_das_dicas([item], None).visiveis[0]
    assert cartao.cura.endswith(cura), "o cartão perdeu o «o que fazer» do dono"


def test_a_linha_da_leitura_entra_no_check_up_e_nao_na_aba_jogar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O exame completo a acrescenta à tira da 08; o contrato da Jogar"""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    leitura = Item(chave=a08_conexoes.CHAVE_DA_LEITURA, rotulo="x",
                   estado="atencao",  # (noqa-acento): chave de máquina do exame
                   porque="y.")
    monkeypatch.setattr(a08_conexoes, "_conferencias", lambda: [])
    monkeypatch.setattr(a08_conexoes, "_EXTRAS", (leitura,))
    monkeypatch.setattr(a08_conexoes, "_ULTIMO_ESTADO", _estado_do_daemon("failed"))
    assert leitura in a08_conexoes._itens_da_tela()
    assert all(i.get("porque") != "y." for i in a08_conexoes._exame())


def test_o_exame_completo_pergunta_pela_leitura(monkeypatch: pytest.MonkeyPatch) -> None:
    """O «Examinar» (e a entrada na aba) corre o exame completo, e é ele que"""
    from hefesto_dualsense4unix.integrations import exame_da_mesa
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    for nome in ("_reler_a_declaracao", "_dispensadas_do_disco", "_mesa_do_radio",
                 "_dongles", "_entradas", "_gabinete", "_leitura_das_ordens_da_maquina"):
        monkeypatch.setattr(a08_conexoes, nome, lambda *_a, **_k: None)
    monkeypatch.setattr(a08_conexoes, "_mesa_declarada", lambda _d: {})
    outra = exame_da_mesa.Item(chave="energia_do_radio", rotulo="r", estado="certo",
                               porque="p.")
    monkeypatch.setattr(exame_da_mesa, "exame", lambda **_k: [outra])
    monkeypatch.setattr(a08_conexoes, "_nos_dos_controles", lambda: {})
    monkeypatch.setattr(broker, "porta_provavel",
                        lambda: (PORTA_DIRETA, "não há socket de broker aqui"))
    monkeypatch.setattr(a08_conexoes, "_EXTRAS", ())
    monkeypatch.setattr(a08_conexoes, "_ULTIMO_ESTADO", _estado_do_daemon("failed"))
    a08_conexoes._correr_o_exame_completo()
    chaves = [i.chave for i in a08_conexoes._EXTRAS]
    assert chaves == ["energia_do_radio", a08_conexoes.CHAVE_DA_LEITURA]

    monkeypatch.setattr(a08_conexoes, "_ULTIMO_ESTADO", _estado_do_daemon("held"))
    a08_conexoes._correr_o_exame_completo()
    assert [i.chave for i in a08_conexoes._EXTRAS] == ["energia_do_radio"]


def test_a_linha_da_leitura_sai_quando_o_daemon_volta_a_segurar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O grab que falhou volta sozinho (o daemon tenta de 2 em 2 s). A linha"""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    leitura = Item(chave=a08_conexoes.CHAVE_DA_LEITURA, rotulo="x",
                   estado="atencao",  # (noqa-acento): chave de máquina do exame
                   porque="y.")
    monkeypatch.setattr(a08_conexoes, "_conferencias", lambda: [])
    monkeypatch.setattr(a08_conexoes, "_EXTRAS", (leitura,))
    monkeypatch.setattr(a08_conexoes, "_ULTIMO_ESTADO", _estado_do_daemon("failed"))
    assert leitura in a08_conexoes._itens_da_tela()
    for voltou in (_estado_do_daemon("held"), _estado_do_daemon("failed", emulando=False)):
        monkeypatch.setattr(a08_conexoes, "_ULTIMO_ESTADO", voltou)
        assert leitura not in a08_conexoes._itens_da_tela(), voltou
