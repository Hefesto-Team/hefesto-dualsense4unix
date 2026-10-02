"""O instrumento, o portão e o manual têm de continuar apontando um para o outro."""

from __future__ import annotations

import pathlib
import types

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "regua_de_tela.py"
PORTAO = RAIZ / "scripts" / "check_regua_de_tela.py"


def _carregar(caminho: pathlib.Path) -> types.ModuleType:
    """Compila o TEXTO do arquivo, sem passar por bytecode."""
    fonte = caminho.read_text(encoding="utf-8")
    modulo = types.ModuleType(caminho.stem)
    modulo.__file__ = str(caminho)
    exec(compile(fonte, str(caminho), "exec"), modulo.__dict__)
    return modulo


def test_o_portao_e_o_instrumento_nomeiam_o_mesmo_manual() -> None:
    """Dois arquivos, duas constantes, um caminho só."""
    portao = _carregar(PORTAO)
    manual_do_instrumento = _manual_do_instrumento()
    assert manual_do_instrumento == portao.O_MANUAL, (
        f"o portão manda ler {portao.O_MANUAL!r} e o instrumento anuncia "
        f"{manual_do_instrumento!r}. Um dos dois vai mandar alguém a lugar nenhum."
    )


def _manual_do_instrumento() -> str:
    """A constante do instrumento, lida SEM importar o módulo."""
    for linha in INSTRUMENTO.read_text(encoding="utf-8").splitlines():
        if linha.startswith("O_MANUAL = "):
            return linha.split("=", 1)[1].strip().strip('"')
    raise AssertionError(
        "scripts/regua_de_tela.py perdeu a constante O_MANUAL — o `--limites` "
        "deixou de dizer como se escreve a próxima régua."
    )


def test_o_manual_existe_no_disco() -> None:
    portao = _carregar(PORTAO)
    assert (RAIZ / portao.O_MANUAL).is_file(), (
        f"o portão manda ler {portao.O_MANUAL}, e o arquivo não está na árvore. "
        "Um aviso que aponta para o nada é pior que aviso nenhum."
    )


def test_o_portao_nomeia_o_instrumento_e_ele_existe() -> None:
    portao = _carregar(PORTAO)
    assert portao.O_INSTRUMENTO == "scripts/regua_de_tela.py"
    assert (RAIZ / portao.O_INSTRUMENTO).is_file()


def test_o_portao_credita_o_instrumento_como_regua() -> None:
    """O elo que, faltando, faz o portão cobrar régua de quem escreveu uma."""
    portao = _carregar(PORTAO)
    assert portao.e_regua(portao.O_INSTRUMENTO)
    assert portao.O_INSTRUMENTO in portao.reguas_no_disco(RAIZ)


def _aviso() -> str:
    portao = _carregar(PORTAO)
    return portao._bloco(
        RAIZ,
        ["src/hefesto_dualsense4unix/interface/cartao_do_controle.py"],
        ["Controles"],
    )


def test_o_aviso_manda_ler_o_manual() -> None:
    assert _carregar(PORTAO).O_MANUAL in _aviso()


def test_o_aviso_separa_a_biblioteca_das_reguas_do_mockup() -> None:
    """Listar sete arquivos em fila é um enigma, não uma indução."""
    aviso = _aviso()
    assert "A BIBLIOTECA" in aviso
    assert "AS RÉGUAS DO MOCKUP" in aviso
    corpo = aviso[aviso.index("A BIBLIOTECA") :]
    biblioteca, mockup = corpo.split("AS RÉGUAS DO MOCKUP", 1)
    assert "scripts/regua_de_tela.py" in biblioteca
    assert "scripts/regua_de_tela.py" not in mockup


OS_CASOS_PAGOS = {
    "o `or 128`": "or 128",
    "a geometria assimétrica dos sticks": "translate(-50%,-50%)",
    "a prova de gesto que dava verde sobre botões mortos": "clicar_e_ouvir",
    "o hexadecimal da barra de luz no título do Touchpad": "de-quem",
    "a guarda de carga que matava a janela": "guarda de carga",
    "os 84 filtros SVG mortos": "84 filtros",
    "a régua de pop-up medida contra a viewport": "position:fixed",
}


def test_o_manual_traz_um_caso_por_defeito_ja_pago() -> None:
    """É contra defeito conhecido que se prova instrumento."""
    portao = _carregar(PORTAO)
    texto = (RAIZ / portao.O_MANUAL).read_text(encoding="utf-8")
    faltando = [nome for nome, marca in OS_CASOS_PAGOS.items() if marca not in texto]
    assert not faltando, (
        "o manual perdeu o caso de: " + " · ".join(faltando)
    )


def test_o_manual_ensina_os_dois_instrumentos_e_a_diferenca() -> None:
    """Escolher o instrumento errado é o verde falso mais barato de produzir."""
    portao = _carregar(PORTAO)
    texto = (RAIZ / portao.O_MANUAL).read_text(encoding="utf-8")
    for exigido in ("Playwright", "WebKitGTK", portao.O_INSTRUMENTO):
        assert exigido in texto, f"o manual não fala de {exigido}"


def test_o_manual_exige_que_a_regua_morda_e_viva_no_tempo() -> None:
    """As duas regras que valem para toda régua nova, e as duas são medidas."""
    texto = (RAIZ / _carregar(PORTAO).O_MANUAL).read_text(encoding="utf-8")
    assert "MORDER" in texto
    assert "VIVER NO TEMPO" in texto or "vive no tempo" in texto


def test_o_instrumento_declara_que_nao_sente_o_gerador() -> None:
    """MEDIDO em 29/08, e é o tipo de limite que produz verde falso calado."""
    texto = INSTRUMENTO.read_text(encoding="utf-8")
    inicio = texto.index("O_QUE_ELE_NAO_FAZ = (")
    lista = texto[inicio : texto.index("\n)\n", inicio)]
    assert "GERADOR" in lista, (
        "o instrumento parou de declarar que não sente o gerador, só a página "
        "gerada — e esse é um verde falso que ninguém descobre olhando a régua."
    )
