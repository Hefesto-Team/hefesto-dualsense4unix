"""O instrumento, o portão e o manual têm de continuar apontando um para o outro.

Três arquivos nasceram no mesmo dia (29/08/2026), em três frentes diferentes, e
cada um só serve se souber dos outros dois:

* ``scripts/regua_de_tela.py`` — a BIBLIOTECA que dirige o ``WebView`` por
  dentro. É com ela que se escreve régua nova sobre a interface do produto.
* ``scripts/check_regua_de_tela.py`` — o PORTÃO do ``pre-commit``, que pergunta
  pela régua quando o commit mexe na tela.
* ``docs/process/2026-08-29-A-REGUA-DE-TELA-como-se-prova-a-interface.md`` — o
  MANUAL, que é o que o portão manda ler.

O elo é frágil por natureza: são três caminhos escritos à mão, em três arquivos
que ninguém edita junto. Um ``git mv`` do documento, ou um teclado errado no
nome, deixa o portão mandando ler um arquivo que não existe — e o aviso, que já
não bloqueia nada, vira ruído puro. Este teste é o que impede isso, e custa
milissegundos.

O QUE ELE PROVA, E O QUE ELE NÃO PROVA
--------------------------------------
Ele prova que os **endereços casam** e que o portão **credita** o instrumento
como régua. Ele NÃO prova que o manual esteja certo, nem que a régua morda —
isso é a matriz de mordidas de ``test_regua_de_tela_a_aba_controles.py`` e a de
``test_o_gancho_induz_a_regua_de_tela.py``.

A parte de conteúdo aqui é deliberadamente magra e só cobre o que o pedido dela
fixou: o manual tem de ter **um caso por defeito de tela já pago**. Se alguém
apagar um caso, o documento deixa de ser o que foi encomendado, e isso é
verificável sem adivinhar prosa.
"""

from __future__ import annotations

import pathlib
import types

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "regua_de_tela.py"
PORTAO = RAIZ / "scripts" / "check_regua_de_tela.py"


def _carregar(caminho: pathlib.Path) -> types.ModuleType:
    """Compila o TEXTO do arquivo, sem passar por bytecode.

    Cicatriz de 29/08/2026, medida na bancada do portão: o
    ``spec_from_file_location`` valida o ``.pyc`` por mtime-em-SEGUNDOS mais
    tamanho. Uma sabotagem do mesmo tamanho, devolvida dentro do mesmo segundo,
    fez o import trazer o bytecode VELHO — a sabotagem ficou verde e a
    devolução vermelha, as duas mentindo. ``compile()`` do texto não tem cache.
    """
    fonte = caminho.read_text(encoding="utf-8")
    modulo = types.ModuleType(caminho.stem)
    modulo.__file__ = str(caminho)
    exec(compile(fonte, str(caminho), "exec"), modulo.__dict__)
    return modulo


# --------------------------------------------------------------- os endereços


def test_o_portao_e_o_instrumento_nomeiam_o_mesmo_manual() -> None:
    """Dois arquivos, duas constantes, um caminho só.

    Cada um precisa do manual por um motivo diferente — o portão para mandar
    ler, o instrumento para o ``--limites`` dizer como se escreve a próxima —,
    e por isso a constante está nos dois. Divergir é o defeito.
    """
    portao = _carregar(PORTAO)
    manual_do_instrumento = _manual_do_instrumento()
    assert manual_do_instrumento == portao.O_MANUAL, (
        f"o portão manda ler {portao.O_MANUAL!r} e o instrumento anuncia "
        f"{manual_do_instrumento!r}. Um dos dois vai mandar alguém a lugar nenhum."
    )


def _manual_do_instrumento() -> str:
    """A constante do instrumento, lida SEM importar o módulo.

    Importar ``regua_de_tela`` puxa ``gi``/``WebKit2``, que numa árvore sem o
    binding não existe — e a checagem de endereço não precisa de janela nenhuma.
    """
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
    """O elo que, faltando, faz o portão cobrar régua de quem escreveu uma.

    ``scripts/`` está em ``PASTAS_DE_REGUA`` por causa deste arquivo: ele nasceu
    fora de ``novo-layout/`` de propósito, porque aquela pasta é `.gitignore` e
    não viaja em worktree.
    """
    portao = _carregar(PORTAO)
    assert portao.e_regua(portao.O_INSTRUMENTO)
    assert portao.O_INSTRUMENTO in portao.reguas_no_disco(RAIZ)


# ------------------------------------------------------------------- o aviso


def _aviso() -> str:
    portao = _carregar(PORTAO)
    return portao._bloco(
        RAIZ,
        ["src/hefesto_dualsense4unix/app/widgets/controller_card.py"],
        ["Controles"],
    )


def test_o_aviso_manda_ler_o_manual() -> None:
    assert _carregar(PORTAO).O_MANUAL in _aviso()


def test_o_aviso_separa_a_biblioteca_das_reguas_do_mockup() -> None:
    """Listar sete arquivos em fila é um enigma, não uma indução.

    Quem lê o aviso é justamente quem ainda não sabe por onde começar. As réguas
    de ``novo-layout/_ferramentas/`` são Playwright sobre o mockup e NÃO
    alcançam o ``WebView`` do produto; a versionada é biblioteca e se importa de
    um ``tests/unit/test_*.py``. O aviso tem de dizer qual é qual.
    """
    aviso = _aviso()
    assert "A BIBLIOTECA" in aviso
    assert "AS RÉGUAS DO MOCKUP" in aviso
    corpo = aviso[aviso.index("A BIBLIOTECA") :]
    biblioteca, mockup = corpo.split("AS RÉGUAS DO MOCKUP", 1)
    assert "scripts/regua_de_tela.py" in biblioteca
    assert "scripts/regua_de_tela.py" not in mockup


# ------------------------------------------------------- o conteúdo encomendado


#: Os defeitos de tela que esta casa pagou e que o manual tem de ensinar a
#: pegar — foram nomeados por ela no enunciado do trabalho, um por um. Cada
#: entrada é um pedaço de texto que só aparece se o caso continuar escrito.
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
    """É contra defeito conhecido que se prova instrumento.

    Este teste não julga a prosa — só confere que nenhum dos sete casos sumiu do
    documento. Um manual de régua sem os defeitos que a motivaram vira teoria.
    """
    portao = _carregar(PORTAO)
    texto = (RAIZ / portao.O_MANUAL).read_text(encoding="utf-8")
    faltando = [nome for nome, marca in OS_CASOS_PAGOS.items() if marca not in texto]
    assert not faltando, (
        "o manual perdeu o caso de: " + " · ".join(faltando)
    )


def test_o_manual_ensina_os_dois_instrumentos_e_a_diferenca() -> None:
    """Escolher o instrumento errado é o verde falso mais barato de produzir.

    Régua de comportamento escrita no Playwright NÃO PODE falhar: no mockup não
    há ninguém do outro lado do clique. O manual tem de dizer isso.
    """
    portao = _carregar(PORTAO)
    texto = (RAIZ / portao.O_MANUAL).read_text(encoding="utf-8")
    for exigido in ("Playwright", "WebKitGTK", portao.O_INSTRUMENTO):
        assert exigido in texto, f"o manual não fala de {exigido}"


def test_o_manual_exige_que_a_regua_morda_e_viva_no_tempo() -> None:
    """As duas regras que valem para toda régua nova, e as duas são medidas.

    Um teste que passa com a cura arrancada não testa nada; e uma régua que roda
    o tique uma vez mede um instante, não um comportamento.
    """
    texto = (RAIZ / _carregar(PORTAO).O_MANUAL).read_text(encoding="utf-8")
    assert "MORDER" in texto
    assert "VIVER NO TEMPO" in texto or "vive no tempo" in texto


# ----------------------------------------------------- o limite recém-medido


def test_o_instrumento_declara_que_nao_sente_o_gerador() -> None:
    """MEDIDO em 29/08, e é o tipo de limite que produz verde falso calado.

    Arrancado o ``transform:translate(-50%,-50%)`` do ``.stick .p`` no gerador
    da aba (``aba02.py``), os 17 testes da régua ficaram VERDES; o mesmo
    arranque no ``02-controles.html`` deu 3 vermelhos, com -43,50/+52,50 px. A
    régua mede a página GERADA, e o CSS do gerador só chega lá depois do
    ``regerar.py``.

    Um limite que só existe na cabeça de quem mediu não protege ninguém: ele
    tem de sair no ``--limites``.
    """
    texto = INSTRUMENTO.read_text(encoding="utf-8")
    inicio = texto.index("O_QUE_ELE_NAO_FAZ = (")
    lista = texto[inicio : texto.index("\n)\n", inicio)]
    assert "GERADOR" in lista, (
        "o instrumento parou de declarar que não sente o gerador, só a página "
        "gerada — e esse é um verde falso que ninguém descobre olhando a régua."
    )
