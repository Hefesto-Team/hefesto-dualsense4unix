"""O recibo do ensaio diz DE QUE BANCADA cada foto saiu — Z0-5.

O DEFEITO ORIGINAL, medido em 24/08/2026 (§2.2/M5 da sprint Z0-01). O
`PROVA-DA-FOTO.txt` já registrava `ensaio` e a soma sha256 de cada PNG, mas
nenhuma linha dizia qual dos modos rodou nem qual arquivo alimentou os
dublês — e as fotos SÃO dublê desde sempre, por decisão de privacidade. Quem
lê a imagem sem ler o recibo não tem como separar o que foi medido do que foi
encenado. Foi exatamente esse buraco que custou dez briefings errados em 23/08.

O RECIBO TROCOU DE DONO — 08/09/2026, e a dúvida que ele resolve é OUTRA
-------------------------------------------------------------------------

**A CAUSA MEDIDA:** quem escrevia o recibo era
`scripts/gui-captura/retratar_abas.py`, o retratista da JANELA GTK. **A janela
saiu inteira em 06/09/2026** (`D-0609-GTK-LEVA-INTEIRA`) e o Passo 2 da
`GTK-3` apagou o script; o Passo 1 ("os 62 testes, um a um") não alcançou este
arquivo. Os três testes daqui ficaram vermelhos importando um caminho que não
existe — e o recibo no disco ficou órfão, **nomeando um programa apagado** e
listando dezesseis fotos que nenhum instrumento vivo refaz.

**O fato não caducou; a AMBIGUIDADE que ele desfaz é que mudou de forma**, e
essa distinção é o trabalho inteiro deste arquivo:

| | a pergunta que o recibo respondia |
| --- | --- |
| janela GTK | *esta foto é medição ou dublê?* — as onze abas aceitavam IPC vivo ou fixture |
| interface HTML | *esta foto é do PRODUTO ou da BANCADA?* |

Na tela de hoje a primeira pergunta não tem como existir: a foto é sempre de
uma página do repositório, e quem trava isso é
`test_retrato_das_abas_nao_vaza_dado_real`. A segunda é a armadilha mais cara
do `COMO-OLHAR-A-TELA.md`, e reincidiu quatro vezes só em 31/08:

    interface/olhar.py --todas               # a BANCADA (mockup/)
    interface/olhar.py --todas --publicado   # o PRODUTO (interface/paginas/)

As duas gravam PNG com o MESMO NOME. Uma foto da bancada em
`docs/usage/assets/` documenta uma tela que o produto não renderiza, e nada na
imagem denuncia isso — só o recibo.

O QUE MORREU COM A JANELA, e não tem herdeiro porque não tem mais objeto
------------------------------------------------------------------------

`fixture:` nomeava `tests/fixtures/state_full_quatro_controles.json`, que
alimentava o modo `--mesa-cheia` — um modo da JANELA, que montava widget e
pedia estado. Não há fixture nenhum na foto de hoje: a página HTML é o dado.
O campo saiu do recibo, e no lugar dele entrou `origem:`, que responde a
pergunta que existe (*de que pasta as páginas foram lidas*).

A MORDIDA
---------

Aplicadas em 08/09/2026, as três, e as três reprovaram:

* `test_o_recibo_do_publicado_declara_o_produto` — chame
  `_gravar_prova_da_foto` com `modo="--todas --doc"` (a bancada) e o teste
  reprova, porque o recibo deixaria de dizer que a foto é do produto. É a
  mordida literal do aceite: o dublê sabe RECUSAR, não só aprovar.
* `test_o_recibo_nomeia_quem_o_escreveu_sem_digitar_o_nome` — ponha o literal
  `scripts/gui-captura/retratar_abas.py` no lugar do autor e ele reprova.
  **ESTA LINHA JÁ FOI FALSA:** até 08/09/2026 a régua dava VERDE nessa mordida
  — a única forma que o defeito de fato teve —, porque conferia
  `_meu_endereco()` isolada em vez de ler o recibo gravado. O docstring dela
  tem as quatro medições e a causa.
* `test_o_modo_doc_grava_recibo` — arranque o `if para_a_doc:` que chama
  `_gravar_prova_da_foto` e ele reprova. Sem ela as duas de cima poderiam estar
  certas sobre uma função que ninguém chama — foi assim que
  `_fotografar_o_cabecalho` viveu dez dias escrita e nunca ligada.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]

#: QUEM ESCREVE O RECIBO HOJE. Não puxa GTK — é Playwright sobre HTML —, e por
#: isso este arquivo não precisa mais do `exigir_gi_real` que o encabeçava.
SCRIPT = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "olhar.py"


def _retrato() -> Any:
    """Importa o retratista como módulo, sem rodar o `main`.

    Ele faz `sys.path.insert` do próprio diretório para achar o `onde`, então
    o import basta — nenhum navegador abre, e `playwright` só é importado
    dentro das funções que fotografam.
    """
    assert SCRIPT.is_file(), (
        f"{SCRIPT} sumiu. Se o retratista mudou de casa, este portão muda com "
        "ele — sem recibo ninguém separa a foto do produto da foto da bancada."
    )
    spec = importlib.util.spec_from_file_location("_retrato_do_recibo", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_retrato_do_recibo"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _bancada_com_fotos(tmp_path: Path, retrato: Any) -> Path:
    """Uma pasta com dois PNGs de mentira — o suficiente para gravar recibo.

    Os nomes seguem `PREFIXO_NOVO` porque é por ele que o retratista acha o que
    somar: um recibo que somasse qualquer `*.png` da pasta acabaria somando as
    `readme_*.png` da janela aposentada, que nenhum instrumento vivo refaz.
    """
    saida = tmp_path / "bancada"
    saida.mkdir()
    (saida / f"{retrato.PREFIXO_NOVO}01-jogar.png").write_bytes(b"\x89PNG-de-mentira-1")
    (saida / f"{retrato.PREFIXO_NOVO}02-controles.png").write_bytes(b"\x89PNG-de-mentira-2")
    # Uma foto da JANELA na mesma pasta: ela não pode entrar na conta.
    (saida / "readme_inicio.png").write_bytes(b"\x89PNG-da-janela-aposentada")
    return saida


def test_o_recibo_do_publicado_declara_o_produto(tmp_path: Path) -> None:
    """Rodado sobre o publicado, o recibo tem de dizer que a foto é do produto.

    É a MORDIDA do aceite, virada para a ambiguidade de hoje: a bancada e o
    produto gravam PNG com o mesmo nome, e a imagem não denuncia de qual das
    duas ela saiu.
    """
    retrato = _retrato()
    saida = _bancada_com_fotos(tmp_path, retrato)

    retrato._gravar_prova_da_foto(
        saida,
        modo="--todas --publicado --doc",
        origem="src/hefesto_dualsense4unix/interface/paginas",
    )

    texto = (saida / retrato.NOME_DA_PROVA).read_text(encoding="utf-8")
    assert "modo:    --todas --publicado --doc" in texto, texto
    assert "origem:  src/hefesto_dualsense4unix/interface/paginas" in texto, (
        "o recibo não nomeia a pasta de onde as páginas foram lidas. Sem ela, "
        "uma foto da bancada em docs/usage/assets/ é indistinguível de uma foto "
        f"do produto. Texto gravado:\n{texto}"
    )
    assert "PÁGINA DO REPOSITÓRIO" in texto, (
        "o recibo não repete, com todas as letras, que a imagem é de página do "
        "repositório e não medição de máquina nenhuma — a frase que o aceite "
        "da Z0-01 pede para matar a confusão entre foto e medição"
    )


def test_o_recibo_conta_so_as_fotos_deste_retratista(tmp_path: Path) -> None:
    """A soma é das DEZ, não de tudo o que houver na pasta.

    `docs/usage/assets/` guarda três famílias — as `aba-*.png` de hoje, as
    `readme_*.png` da janela e os cinco diálogos. Um recibo que somasse todas
    afirmaria ter refeito o que nenhum instrumento vivo refaz, e a próxima
    pessoa leria a data do ensaio como data das dezesseis.
    """
    retrato = _retrato()
    saida = _bancada_com_fotos(tmp_path, retrato)

    retrato._gravar_prova_da_foto(saida, modo="--todas --doc", origem="mockup")

    texto = (saida / retrato.NOME_DA_PROVA).read_text(encoding="utf-8")
    assert "abas:    2" in texto, f"a conta não bate com as fotos deste retratista:\n{texto}"
    assert "readme_inicio.png" not in texto, (
        "o recibo somou uma foto da janela aposentada. Ele afirmaria ter "
        f"refeito o que nenhum instrumento vivo refaz. Texto:\n{texto}"
    )


def test_o_recibo_nomeia_quem_o_escreveu_sem_digitar_o_nome(tmp_path: Path) -> None:
    """O autor NOMEADO NO RECIBO GRAVADO é o programa que de fato o escreveu.

    ESTA RÉGUA JÁ FOI FALSA, e a correção é de 08/09/2026. Ela nasceu como
    troféu do laudo que a escreveu — *"é a mordida do defeito que ACHEI"* — e
    não mordia onde dizia morder. Quatro medições, com o recibo do disco lido
    depois de cada uma:

    | o que se punha no lugar do autor | a régua velha dizia |
    | --- | --- |
    | `scripts/gui-captura/retratar_abas.py` — O DEFEITO HISTÓRICO | VERDE |
    | `scripts/retratar_tudo.py` | VERDE |
    | `src/hefesto_dualsense4unix/interface/olhar.py` | reprovava |
    | a linha do autor ARRANCADA INTEIRA | VERDE |

    **A CAUSA, e são duas metades que nunca se tocavam:** a primeira chamava
    `_meu_endereco()` ISOLADA e conferia que ela terminava em `olhar.py`, sem
    nunca perguntar se o recibo a usava; a segunda varria literais do fonte e só
    pegava os que casavam `endswith(".py") and "olhar" in s`. Junto, isso pega o
    autor que se nomeia CERTO e deixa passar exatamente o autor que nomeia um
    programa apagado — a única forma que o defeito de fato teve. E deixava
    `_meu_endereco` escrita e nunca ligada, que é o destino contra o qual o
    `test_o_modo_doc_grava_recibo` logo abaixo foi escrito.

    **A cura:** medir o RECIBO QUE FOI ESCRITO, não a função isolada. Grava-se
    um recibo de verdade, lê-se o texto do disco, e cobra-se que o autor
    nomeado exista nesta árvore E seja este mesmo arquivo. A segunda metade
    fica, porque é ela que impede o endereço CERTO de ser digitado — e um nome
    certo digitado é só um nome errado esperando o arquivo se mover.

    As quatro mordidas acima reprovam agora, e uma quinta cobre a segunda
    cobrança sozinha: pôr um programa que EXISTE mas é outro
    (`interface/onde.py`) passa pelo `is_file()` e morre no `resolve()`, com
    *"credita 'src/…/onde.py', mas quem o escreveu foi 'src/…/olhar.py'"*.
    """
    retrato = _retrato()
    saida = _bancada_com_fotos(tmp_path, retrato)

    retrato._gravar_prova_da_foto(
        saida,
        modo="--todas --publicado --doc",
        origem="src/hefesto_dualsense4unix/interface/paginas",
    )
    texto = (saida / retrato.NOME_DA_PROVA).read_text(encoding="utf-8")

    nomeados = re.findall(r"gerado por (\S+)", texto)
    assert len(nomeados) == 1, (
        "o recibo GRAVADO não nomeia exatamente um autor — encontrados: "
        f"{nomeados}. Sem a linha do autor ninguém sabe que programa refaz "
        "estas fotos, e arrancá-la inteira era o que deixava esta régua verde "
        f"sobre nada. Texto gravado:\n{texto}"
    )
    autor = nomeados[0]

    assert (RAIZ / autor).is_file(), (
        f"o recibo GRAVADO diz ter sido gerado por {autor!r}, que não existe "
        "nesta árvore. É exatamente o estado em que ele foi encontrado em "
        "08/09/2026 — dois dias creditando um retratista que a leva `GTK-3` "
        "apagou junto com a janela, em 06/09."
    )
    assert (RAIZ / autor).resolve() == SCRIPT.resolve(), (
        f"o recibo GRAVADO credita {autor!r}, mas quem o escreveu foi "
        f"{SCRIPT.relative_to(RAIZ)}. Um recibo que credita outro programa "
        "manda a próxima pessoa rodar a ferramenta errada para refazer as "
        "fotos."
    )

    # E o nome não pode estar digitado em lugar nenhum do fonte.
    arvore = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    docs = {
        id(no.body[0].value)
        for no in ast.walk(arvore)
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef))
        and no.body
        and isinstance(no.body[0], ast.Expr)
        and isinstance(no.body[0].value, ast.Constant)
        and isinstance(no.body[0].value.value, str)
    }
    literais = [
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant)
        and isinstance(no.value, str)
        and id(no) not in docs
    ]
    cravados = [s for s in literais if s.endswith(".py") and "olhar" in s]
    assert not cravados, (
        f"o endereço do retratista está digitado no fonte: {cravados}. É como o "
        "recibo velho passou dois dias nomeando um programa apagado."
    )


def test_o_modo_doc_grava_recibo() -> None:
    """O `--doc` chama a função — senão as réguas acima medem código morto.

    Verificação por AST: dentro de `_todas` tem de haver uma chamada a
    `_gravar_prova_da_foto`, e ela tem de passar `modo=` e `origem=`. Sem esta
    régua, `_gravar_prova_da_foto` poderia estar perfeita e nunca ser chamada —
    que é o defeito mais caro desta casa, e o `_fotografar_o_cabecalho` do
    retratista velho viveu dez dias exatamente assim.
    """
    arvore = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    todas = next(
        (
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.FunctionDef) and no.name == "_todas"
        ),
        None,
    )
    assert todas is not None, "o `_todas` sumiu do retratista"

    chamadas = [
        no
        for no in ast.walk(todas)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Name)
        and no.func.id == "_gravar_prova_da_foto"
    ]
    assert chamadas, (
        "o `_todas` parou de chamar `_gravar_prova_da_foto` — as fotos "
        "publicadas voltariam a nascer sem proveniência, e o portão das fotos "
        "(`test_as_fotos_acompanham_a_versao`) perderia a segunda porta que o "
        "tira do estado sem saída"
    )
    for chamada in chamadas:
        nomes_das_keywords = {kw.arg for kw in chamada.keywords}
        faltando = {"modo", "origem"} - nomes_das_keywords
        assert not faltando, (
            f"a chamada de `_gravar_prova_da_foto` na linha {chamada.lineno} "
            f"não passa {sorted(faltando)} — o recibo voltaria a nascer sem "
            "proveniência"
        )
