"""O censo do gabinete não inventa gabinete — e declara quando as fontes brigam."""

import json
import re

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.config`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import censo_do_gabinete as cg
from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho, Censo
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import NoDeEntrada
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, Mesa


_MOLDE = """Handle 0x{handle:04X}, DMI type 8, 9 bytes
Port Connector Information
\tInternal Reference Designator: {interna}
\tInternal Connector Type: {tipo_interno}
\tExternal Reference Designator: {externa}
\tExternal Connector Type: {tipo_externo}
\tPort Type: {porta}
"""

_PREAMBULO = "# dmidecode 3.5\nGetting SMBIOS data from sysfs.\nSMBIOS 3.3.0 present.\n\n"


def _bloco(handle, *, interna="Not Specified", tipo_interno="None",
           externa="Not Specified", tipo_externo="None", porta="None"):
    return _MOLDE.format(
        handle=handle, interna=interna, tipo_interno=tipo_interno,
        externa=externa, tipo_externo=tipo_externo, porta=porta,
    )


def _tabela(blocos):
    return _PREAMBULO + "\n".join(blocos)


_USB_DESTA_PLACA = (
    ("J1500", "Access Bus (USB)", "USB 3.0"),
    ("J1501", "Access Bus (USB)", "USB 3.0"),
    ("J1502", "USB Type-C Receptacle", "USB-C"),
    ("J1503", "Access Bus (USB)", "USB 3.0"),
    ("J1504", "Access Bus (USB)", "USB 3.1"),
)

TABELA_8_DESTA_PLACA = _tabela(
    [
        _bloco(0x0C + i, externa=designacao, tipo_externo=tipo_externo, porta=porta)
        for i, (designacao, tipo_externo, porta) in enumerate(_USB_DESTA_PLACA)
    ]
    + [_bloco(0x20 + i) for i in range(13)]
)

TABELA_8_SO_DE_GABARITO = _tabela([_bloco(0x0C + i) for i in range(18)])

TABELA_8_AUSENTE = _PREAMBULO

PLACA_DESTA_BANCADA = {
    "fabricante": {"valor": "Gigabyte Technology Co., Ltd.", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    "modelo": {"valor": "B450M S2H", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    "bios": {"valor": "F68a", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    "tipo_de_chassi": {"valor": 3, "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    "movel": {"valor": False, "de_onde_sei": cg.LIDO_DO_FIRMWARE},
}


def _no(hub, numero, *, par="", encaixe="hotplug", aparelho=""):
    return NoDeEntrada(
        no=f"{hub}-port{numero}",
        caminho_sysfs=f"/sys/bus/usb/devices/{hub}/{hub}-port{numero}",
        hub=hub,
        numero=numero,
        estado="configured" if aparelho else "not attached",
        tipo_de_encaixe=encaixe,
        par=par,
        aparelho=aparelho,
    )


def entradas_desta_bancada():
    """Os 22 nós de raiz TRANSCRITOS da bancada em 25/08/2026, 21h18."""
    nos = []
    for n in range(1, 11):
        par = f"usb2-port{n - 4}" if 5 <= n <= 7 else ""
        nos.append(_no("usb1", n, par=par, aparelho="1-3" if n == 3 else ""))
    for n in range(1, 5):
        nos.append(_no("usb2", n, par=f"usb1-port{n + 4}" if n <= 3 else ""))
    for n in range(1, 5):
        nos.append(_no("usb3", n, par=f"usb4-port{n}", encaixe="unknown",
                       aparelho="3-1" if n == 1 else ""))
    for n in range(1, 5):
        nos.append(_no("usb4", n, par=f"usb3-port{n}", encaixe="unknown",
                       aparelho="4-1" if n == 1 else ""))
    return tuple(nos)


MAXCHILD_DESTA_BANCADA = {"usb1": 10, "usb2": 4, "usb3": 4, "usb4": 4}


def censo_desta_bancada(dmidecode=TABELA_8_DESTA_PLACA):
    return cg.montar_censo(
        dmidecode=dmidecode,
        entradas=entradas_desta_bancada(),
        maxchild=MAXCHILD_DESTA_BANCADA,
        placa=dict(PLACA_DESTA_BANCADA),
        entradas_da_tabela_8=18,
        agora="2026-08-25T21:18:00-03:00",
    )


def test_a_fixture_reproduz_a_bancada_medida():
    """Antes de medir o produto, medir a régua."""
    entradas = entradas_desta_bancada()
    assert len(entradas) == 22
    assert sum(MAXCHILD_DESTA_BANCADA.values()) == 22
    kernel = cg.censo_do_kernel(entradas, MAXCHILD_DESTA_BANCADA)
    assert kernel["soquetes"]["valor"] == 22
    assert kernel["buracos"]["valor"] == 15
    assert kernel["buracos_de_encaixe"]["valor"] == 11
    assert kernel["reguas_concordam"] is True
    assert cg.blocos_da_tabela_8(TABELA_8_DESTA_PLACA) == 18
    assert len(cg.conectores_do_dmidecode(TABELA_8_DESTA_PLACA)) == 5


@pytest.mark.parametrize(
    "texto,apelido",
    [
        (TABELA_8_AUSENTE, "sem tabela nenhuma"),
        (TABELA_8_SO_DE_GABARITO, "18 blocos de gabarito"),
        ("", "dmidecode ausente ou sem root"),
    ],
    ids=["sem-tabela", "so-gabarito", "sem-dmidecode"],
)
def test_placa_sem_tabela_8_nao_inventa_gabinete(texto, apelido):
    """**A MORDIDA.** Firmware que não respondeu não vira gabinete de mentira."""
    censo = censo_desta_bancada(dmidecode=texto)
    assert censo["faces"] == [], f"{apelido}: inventou face"
    assert censo["de_onde_sei"] == cg.NAO_RESPONDEU, apelido
    assert censo["firmware"]["tabela_8_respondeu"] is False, apelido
    assert censo["firmware"]["conectores"] == [], apelido
    assert censo["firmware"]["conectores_usb"] == {
        "valor": None,
        "de_onde_sei": cg.NAO_RESPONDEU,
    }, apelido
    assert censo["contagens"]["divergem"] is False, apelido
    assert censo["contagens"]["precisa_da_palavra_dela"] is True, apelido


def test_zero_conectores_nao_e_a_mesma_coisa_que_nao_perguntei():
    """A recusa que o dublê tem de saber: ``None`` com selo, nunca ``0``."""
    censo = censo_desta_bancada(dmidecode=TABELA_8_SO_DE_GABARITO)
    for caminho, fato in _todos_os_fatos(censo):
        if fato["valor"] is None:
            assert fato["de_onde_sei"] == cg.NAO_RESPONDEU, caminho
        else:
            assert fato["de_onde_sei"] != cg.NAO_RESPONDEU, caminho


def test_faces_nascem_vazias_mesmo_com_a_bios_falante():
    """Nem a BIOS mais loquaz produz uma face."""
    censo = censo_desta_bancada()
    assert censo["firmware"]["tabela_8_respondeu"] is True
    assert censo["faces"] == []
    assert "física" not in censo["por_que_faces_vazias"]
    assert censo["por_que_faces_vazias"].strip()


def test_tabela_8_que_contradiz_o_kernel_nao_vence_sozinha():
    """**A MORDIDA.** As três contagens ficam gravadas, e a briga é declarada."""
    contagens = censo_desta_bancada()["contagens"]
    assert contagens["firmware"] == {"valor": 5, "de_onde_sei": cg.LIDO_DO_FIRMWARE}
    assert contagens["kernel_soquetes"] == {"valor": 22, "de_onde_sei": cg.LIDO_DO_KERNEL}
    assert contagens["kernel_buracos"] == {"valor": 15, "de_onde_sei": cg.LIDO_DO_KERNEL}
    assert contagens["divergem"] is True
    assert "5" in contagens["pergunta"] and "15" in contagens["pergunta"]
    assert contagens["pergunta"].endswith("?")


def test_quando_as_contas_batem_nao_ha_divergencia_a_declarar():
    """A outra metade da régua: ela precisa saber ficar CALADA."""
    contagens = cg.declarar_divergencia(firmware=15, soquetes=22, buracos=15)
    assert contagens["divergem"] is False
    assert contagens["precisa_da_palavra_dela"] is True


def test_uma_fonte_sozinha_nao_diverge_de_nada():
    """Sem segunda régua não há briga — e inventar uma seria ruído."""
    assert cg.declarar_divergencia(firmware=5, soquetes=None, buracos=None)["divergem"] is False
    assert cg.declarar_divergencia(firmware=None, soquetes=22, buracos=15)["divergem"] is False


def test_a_pergunta_diz_o_que_faltou_em_cada_caso():
    """Três silêncios diferentes, três frases diferentes."""
    muda = cg.declarar_divergencia(firmware=None, soquetes=None, buracos=None)["pergunta"]
    so_kernel = cg.declarar_divergencia(firmware=None, soquetes=22, buracos=15)["pergunta"]
    briga = cg.declarar_divergencia(firmware=5, soquetes=22, buracos=15)["pergunta"]
    assert len({muda, so_kernel, briga}) == 3
    assert "nem a BIOS" in muda


def test_censo_de_outra_placa_nao_serve():
    """**A MORDIDA.** ``gabinete.json`` que veio de outro PC é recusado."""
    censo = censo_desta_bancada()
    assert cg.serve_para_esta_placa(censo, dict(PLACA_DESTA_BANCADA)) is True
    outra = {
        "fabricante": {"valor": "ASUSTeK COMPUTER INC.", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
        "modelo": {"valor": "PRIME B450M-A", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    }
    assert cg.serve_para_esta_placa(censo, outra) is False


def test_placa_que_nao_sabe_quem_e_tambem_e_recusa():
    """Não saber quem é a placa não autoriza a dizer que serve."""
    censo = censo_desta_bancada()
    anonima = {
        "fabricante": {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU},
        "modelo": {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU},
    }
    assert cg.serve_para_esta_placa(censo, anonima) is False
    assert cg.serve_para_esta_placa({}, dict(PLACA_DESTA_BANCADA)) is False


def _censo_com_a_palavra_dela():
    """O arquivo depois de ela responder na aba: faces declaradas e a contagem."""
    antigo = censo_desta_bancada()
    antigo["faces"] = [
        {"nome": "traseira", "entradas": 6, "de_onde_sei": cg.DECLARADO_POR_ELA},
        {"nome": "frente", "entradas": 2, "de_onde_sei": cg.DECLARADO_POR_ELA},
    ]
    antigo["contagens"]["declarado_por_ela"] = {
        "valor": 8,
        "de_onde_sei": cg.DECLARADO_POR_ELA,
    }
    return antigo


def test_o_install_nao_apaga_o_que_ela_ensinou():
    """**A MORDIDA.** A segunda instalação não pode zerar a resposta dela."""
    antigo = _censo_com_a_palavra_dela()
    novo = censo_desta_bancada(dmidecode="")
    herdado = cg.preservar_o_que_ela_disse(novo, antigo, dict(PLACA_DESTA_BANCADA))
    assert len(herdado["faces"]) == 2
    assert herdado["contagens"]["declarado_por_ela"]["valor"] == 8
    assert herdado["contagens"]["declarado_por_ela"]["de_onde_sei"] == cg.DECLARADO_POR_ELA
    assert herdado["contagens"]["precisa_da_palavra_dela"] is False
    assert herdado["de_onde_sei"] == cg.NAO_RESPONDEU


def test_a_declaracao_de_outra_placa_nao_pega_carona():
    """A recusa: faces de outro gabinete descreveriam um metal que não é este."""
    outra = {
        "fabricante": {"valor": "ASUSTeK COMPUTER INC.", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
        "modelo": {"valor": "PRIME B450M-A", "de_onde_sei": cg.LIDO_DO_FIRMWARE},
    }
    herdado = cg.preservar_o_que_ela_disse(_censo_com_a_palavra_dela(), {}, outra)
    assert "substituiu_outra_placa" not in herdado

    herdado = cg.preservar_o_que_ela_disse(
        censo_desta_bancada(), _censo_com_a_palavra_dela(), outra
    )
    assert herdado["faces"] == []
    assert herdado["substituiu_outra_placa"] is True


def test_arquivo_ausente_ou_quebrado_nao_derruba_o_install(tmp_path):
    """Primeira instalação, JSON truncado, formato de outra versão: tudo é ``{}``."""
    assert cg.ler_do_disco(str(tmp_path / "nao-existe.json")) == {}
    quebrado = tmp_path / "quebrado.json"
    quebrado.write_text('{"faces": [', encoding="utf-8")
    assert cg.ler_do_disco(str(quebrado)) == {}
    lista = tmp_path / "lista.json"
    lista.write_text("[1, 2, 3]", encoding="utf-8")
    assert cg.ler_do_disco(str(lista)) == {}
    inteiro = tmp_path / "bom.json"
    cg.gravar(_censo_com_a_palavra_dela(), str(inteiro))
    assert len(cg.ler_do_disco(str(inteiro))["faces"]) == 2


def test_o_que_o_firmware_disse_vem_com_selo():
    """Todo ``valor`` deste arquivo tem um ``de_onde_sei`` ao lado, e ele é válido."""
    fatos = _todos_os_fatos(censo_desta_bancada())
    assert len(fatos) >= 15, "a varredura não achou os campos — a régua quebrou"
    for caminho, fato in fatos:
        assert fato["de_onde_sei"] in cg.SELOS, f"{caminho}: selo desconhecido"
    censo = censo_desta_bancada()
    assert censo["kernel"]["soquetes"]["de_onde_sei"] == cg.LIDO_DO_KERNEL
    assert censo["firmware"]["conectores_usb"]["de_onde_sei"] == cg.LIDO_DO_FIRMWARE
    for conector in censo["firmware"]["conectores"]:
        assert conector["de_onde_sei"] == cg.LIDO_DO_FIRMWARE


def test_o_selo_de_ela_existe_e_o_censo_nunca_o_grava():
    """``declarado-por-ela`` é do vocabulário, e é da ABA — não deste módulo."""
    assert cg.DECLARADO_POR_ELA in cg.SELOS
    selos = {fato["de_onde_sei"] for _, fato in _todos_os_fatos(censo_desta_bancada())}
    assert cg.DECLARADO_POR_ELA not in selos


def test_o_hub_da_mesa_nao_entra_no_gabinete():
    """O gabinete é o CHASSI. O hub que ela pendurou não muda o metal."""
    do_hub = tuple(_no("3-1", n) for n in range(1, 5)) + tuple(_no("3-1.1", n) for n in range(1, 5))
    com_hub = entradas_desta_bancada() + do_hub
    assert len(com_hub) == 30
    assert len(cg.soquetes_de_raiz(com_hub)) == 22
    assert cg.censo_do_kernel(com_hub, MAXCHILD_DESTA_BANCADA)["buracos"]["valor"] == 15


def test_o_buraco_3x_conta_uma_vez_so():
    """Um furo USB 3.x publica DOIS nós, e é UM furo."""
    kernel = cg.censo_do_kernel(entradas_desta_bancada(), MAXCHILD_DESTA_BANCADA)
    assert kernel["soquetes"]["valor"] == 22
    assert kernel["buracos"]["valor"] == 15
    assert kernel["buracos"]["valor"] < kernel["soquetes"]["valor"]


def test_as_duas_reguas_do_kernel_se_conferem():
    """Contar nós e ler ``maxchild`` são dois caminhos, e o censo diz se batem."""
    entradas = entradas_desta_bancada()
    assert cg.censo_do_kernel(entradas, MAXCHILD_DESTA_BANCADA)["reguas_concordam"] is True
    mentiroso = dict(MAXCHILD_DESTA_BANCADA, usb1=4)
    torto = cg.censo_do_kernel(entradas, mentiroso)
    assert torto["reguas_concordam"] is False
    assert torto["soquetes"]["valor"] == 22 and torto["maxchild"]["valor"] == 16
    assert cg.censo_do_kernel(entradas, {})["reguas_concordam"] is None


def test_barramento_mudo_nao_vira_gabinete_sem_buracos():
    """``/sys`` ausente — contêiner, sandbox — é ``None``, nunca zero buracos."""
    kernel = cg.censo_do_kernel((), {})
    assert kernel["soquetes"] == {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU}
    assert kernel["buracos"] == {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU}


def test_o_parser_le_os_cinco_campos_de_cada_conector():
    """A palavra do fabricante é o dado, e sai verbatim."""
    primeiro = cg.conectores_do_dmidecode(TABELA_8_DESTA_PLACA)[0]
    assert primeiro.designacao_externa == "J1500"
    assert primeiro.tipo_externo == "Access Bus (USB)"
    assert primeiro.tipo_de_porta == "USB 3.0"
    assert primeiro.e_usb is True and primeiro.externo is True


def test_usb_sai_do_tipo_e_nunca_da_designacao():
    """``J1500`` não diz protocolo; ``Access Bus (USB)`` diz."""
    serigrafia = cg.Conector(designacao_externa="USB1", tipo_externo="Mini Jack (headphones)")
    assert serigrafia.e_usb is False
    for rotulo in ("USB", "USB 3.0", "USB-C", "Access Bus (USB)", "USB Type-C Receptacle"):
        assert cg.Conector(tipo_de_porta=rotulo).e_usb is True


def test_conector_interno_nao_vira_buraco_do_gabinete():
    """Cabeçote de placa-mãe é fato, e não é buraco que ela alcança."""
    interno = _bloco(0x30, interna="F_USB1", tipo_interno="Access Bus (USB)", porta="USB")
    censo = censo_desta_bancada(dmidecode=TABELA_8_DESTA_PLACA + "\n" + interno)
    conectores = censo["firmware"]["conectores"]
    assert len(conectores) == 6, "o cabeçote tem de FICAR gravado"
    assert conectores[-1]["externo"] is False and conectores[-1]["usb"] is True
    assert censo["firmware"]["conectores_usb"]["valor"] == 5, "e não pode CONTAR"


def test_bloco_de_outro_tipo_nao_confunde_o_parser():
    """A recusa: só ``DMI type 8`` entra, mesmo recebendo o ``dmidecode`` inteiro."""
    tipo_9 = (
        "Handle 0x0040, DMI type 9, 17 bytes\n"
        "System Slot Information\n"
        "\tDesignation: PCIEX16\n"
        "\tExternal Reference Designator: J9999\n"
        "\tPort Type: USB\n"
    )
    misturado = TABELA_8_DESTA_PLACA + "\n" + tipo_9
    conectores = cg.conectores_do_dmidecode(misturado)
    assert len(conectores) == 5
    assert "J9999" not in {c.designacao_externa for c in conectores}
    assert cg.blocos_da_tabela_8(misturado) == 18


def test_a_contagem_bruta_da_tabela_conta_o_gabarito_tambem():
    """18 blocos com zero conteúdo é uma afirmação — sobre o fabricante."""
    assert cg.blocos_da_tabela_8(TABELA_8_SO_DE_GABARITO) == 18
    assert cg.conectores_do_dmidecode(TABELA_8_SO_DE_GABARITO) == ()
    assert cg.blocos_da_tabela_8("") == 0


def test_a_tabela_existe_mesmo_sem_root_para_le_la():
    """O diretório do ``/sys`` é listável; o ``raw`` de cada entrada não é."""
    falso = ["8-0", "8-1", "8-2", "1-0", "4-0", "17-3"]
    assert cg.entradas_no_sysfs(raiz_dmi="/qualquer", listar=lambda _: falso) == 3
    assert cg.entradas_no_sysfs(raiz_dmi="/qualquer", listar=lambda _: []) == 0

    def _explode(_):
        raise OSError("sem /sys")

    assert cg.entradas_no_sysfs(raiz_dmi="/qualquer", listar=_explode) is None


def test_gabarito_de_fabricante_nao_vira_modelo():
    """``Default string`` no ``board_version`` é medido NESTA placa, hoje."""
    campos = {
        "board_vendor": "Gigabyte Technology Co., Ltd.",
        "board_name": "Default string",
        "bios_version": "F68a",
        "chassis_type": "3",
    }
    placa = cg.ler_a_placa(raiz_dmi_id="/x", ler=lambda c: campos[c.rsplit("/", 1)[-1]])
    assert placa["modelo"] == {"valor": None, "de_onde_sei": cg.NAO_RESPONDEU}
    assert placa["fabricante"]["valor"] == "Gigabyte Technology Co., Ltd."
    assert placa["movel"]["valor"] is False


@pytest.mark.parametrize(
    "tipo,movel",
    [("3", False), ("10", True), ("9", True), ("7", False), ("2", None), ("", None)],
)
def test_notebook_e_desktop_se_separam_e_o_resto_e_nao_sei(tipo, movel):
    """Três estados, e o terceiro é o que impede mandar um notebook achar rack."""
    campos = {"board_vendor": "X", "board_name": "Y", "bios_version": "Z", "chassis_type": tipo}
    placa = cg.ler_a_placa(raiz_dmi_id="/x", ler=lambda c: campos[c.rsplit("/", 1)[-1]])
    assert placa["movel"]["valor"] is movel


def test_gravar_e_atomico_e_nao_deixa_sobra(tmp_path):
    """Escrita por troca de nome — JSON pela metade é aba sem gabinete e sem porquê."""
    alvo = tmp_path / "estado" / cg.NOME_DO_ARQUIVO
    escrito = cg.gravar(censo_desta_bancada(), str(alvo))
    assert escrito == str(alvo)
    assert json.loads(alvo.read_text(encoding="utf-8"))["versao_do_censo"] == cg.VERSAO_DO_CENSO
    assert not (tmp_path / "estado" / f"{cg.NOME_DO_ARQUIVO}.novo").exists()
    cg.gravar(censo_desta_bancada(dmidecode=""), str(alvo))
    assert json.loads(alvo.read_text(encoding="utf-8"))["de_onde_sei"] == cg.NAO_RESPONDEU


def test_o_caminho_padrao_le_o_home_na_chamada(tmp_path):
    """CANARIO-FS-01: constante de módulo apontaria para a pasta REAL dela."""
    caminho = cg.caminho_padrao(home=str(tmp_path))
    assert caminho.startswith(str(tmp_path))
    assert caminho.endswith("/.local/state/hefesto-dualsense4unix/gabinete.json")
    fonte = (cg.__file__ or "").replace(".pyc", ".py")
    with open(fonte, encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, 1):
            if re.match(r"^[A-Z_]+\s*=.*(expanduser|Path\.home|os\.environ)", linha):
                pytest.fail(f"censo_do_gabinete.py:{numero} lê o HOME na importação")


def test_o_resumo_diz_o_que_nao_soube():
    """A linha que o install imprime não pode ficar bonita quando faltou dado."""
    assert "DIVERGEM" in cg.resumo(censo_desta_bancada())
    mudo = cg.resumo(censo_desta_bancada(dmidecode=""))
    assert "não respondeu" in mudo and "DIVERGEM" not in mudo


def test_a_maquina_de_verdade_responde_sem_root():
    """O censo roda contra o ``/sys`` desta máquina, como o install vai rodar."""
    censo = cg.ler_o_gabinete(dmidecode="")
    assert censo["faces"] == []
    assert censo["de_onde_sei"] == cg.NAO_RESPONDEU
    kernel = censo["kernel"]
    if kernel["soquetes"]["valor"] is None:
        pytest.skip("sem /sys/bus/usb nesta máquina — a ausência é resposta")
    assert kernel["buracos"]["valor"] <= kernel["soquetes"]["valor"]
    assert kernel["buracos_de_encaixe"]["valor"] <= kernel["buracos"]["valor"]
    assert kernel["reguas_concordam"] is not False, (
        "contar nós e ler maxchild discordaram nesta máquina — "
        f"{kernel['soquetes']['valor']} contra {kernel['maxchild']['valor']}"
    )


def _todos_os_fatos(no, caminho=""):
    """Todo dicionário com ``valor`` na árvore, com o caminho até ele."""
    achados = []
    if isinstance(no, dict):
        if "valor" in no:
            assert "de_onde_sei" in no, f"{caminho}: valor sem de_onde_sei"
            return [(caminho, no)]
        for chave, filho in no.items():
            achados += _todos_os_fatos(filho, f"{caminho}.{chave}" if caminho else str(chave))
    elif isinstance(no, list):
        for indice, filho in enumerate(no):
            achados += _todos_os_fatos(filho, f"{caminho}[{indice}]")
    return achados


_PCI_DO_HUB = "0000:0c:00.3"
_PCI_DA_PLACA = "0000:03:00.0"


def _bancada_dos_tres_adaptadores():
    """O arranjo medido em 22/08/2026: três adaptadores, DOIS pais, um hub."""
    def _hub(no, pai, pci):
        return Aparelho(
            no=no, nome_do_kernel=no.rsplit("/", 1)[-1], pai=pai,
            controlador_pci=pci, e_hub=True,
        )

    censo = Censo(
        aparelhos=(
            Aparelho(no="/sys/usb1", nome_do_kernel="usb1",
                     controlador_pci=_PCI_DA_PLACA, e_hub=True, e_raiz=True),
            Aparelho(no="/sys/usb3", nome_do_kernel="usb3",
                     controlador_pci=_PCI_DO_HUB, e_hub=True, e_raiz=True),
            _hub("/sys/3-3", "/sys/usb3", _PCI_DO_HUB),
            _hub("/sys/3-3.1", "/sys/3-3", _PCI_DO_HUB),
            Aparelho(no="/sys/3-3.1.1", nome_do_kernel="3-3.1.1", pai="/sys/3-3.1",
                     controlador_pci=_PCI_DO_HUB, atras_de_hub=True),
            Aparelho(no="/sys/3-3.1.2", nome_do_kernel="3-3.1.2", pai="/sys/3-3.1",
                     controlador_pci=_PCI_DO_HUB, atras_de_hub=True),
            Aparelho(no="/sys/3-3.2", nome_do_kernel="3-3.2", pai="/sys/3-3",
                     controlador_pci=_PCI_DO_HUB, atras_de_hub=True),
        )
    )
    mesa = Mesa(
        adaptadores=(
            Adaptador(interface="hci0", no="/sys/3-3.1.1", busnum=3, devpath="3.1.1",
                      atras_de_hub=True),
            Adaptador(interface="hci1", no="/sys/3-3.1.2", busnum=3, devpath="3.1.2",
                      atras_de_hub=True),
            Adaptador(interface="hci2", no="/sys/3-3.2", busnum=3, devpath="3.2",
                      atras_de_hub=True),
        )
    )
    return mesa, censo


def _entradas(hub, quantas, *, encaixe="hotplug"):
    """``quantas`` entradas VAZIAS neste hub — nenhum ``peer``, um nó por buraco."""
    return tuple(
        _no(hub, numero, encaixe=encaixe) for numero in range(1, quantas + 1)
    )


