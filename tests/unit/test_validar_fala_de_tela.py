"""Z6-04 — o portão `validar-fala-de-tela.py`, nos dois sentidos.

As seis mordidas, cada uma arrancada de propósito NUM CSV/árvore DE MENTIRA
(nunca na árvore real) e vista reprovar, contra o CLI de verdade via
subprocesso — o mesmo molde de `test_check_paridade_transporte.py`: um portão
que só sabe passar não é portão.

MORDIDA 1 é a que o aceite da sprint nomeia: "É o defeito de 17/08
reproduzido como teste" — a frase de `app/audio_saida.py` dizia "no rádio não
existe alto-falante" enquanto o mapa dizia `existe=tem`, e os três portões de
23/08/2026 passavam verdes com ela plantada (medido em §2.9 da sprint). Este
teste planta o EQUIVALENTE (uma `Fala` com `AFIRMA_NAO_EXISTE` na mesma
chave) numa árvore de mentira e prova que ESTE portão a pega.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"
FALA_DO_MAPA_REAL = RAIZ_REAL / "src" / "hefesto_dualsense4unix" / "app" / "fala_do_mapa.py"

APP_RELATIVO = Path("src") / "hefesto_dualsense4unix" / "app"


def _serializa_fatos(fatos: dict[str, dict[str, Any]]) -> str:
    linhas = [
        '"""fatos_do_mapa.py de MENTIRA — só para teste."""',
        "from __future__ import annotations",
        "",
        "from typing import Final",
        "",
        "FATOS: Final[dict[str, dict[str, object]]] = " + repr(fatos),
        "",
    ]
    return "\n".join(linhas)


def monta_arvore(
    tmp_path: Path,
    fatos: dict[str, dict[str, Any]],
    arquivos_app: dict[str, str],
) -> Path:
    destino = tmp_path / APP_RELATIVO
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "fala_do_mapa.py").write_text(
        FALA_DO_MAPA_REAL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (destino / "fatos_do_mapa.py").write_text(_serializa_fatos(fatos), encoding="utf-8")
    for relativo, conteudo in arquivos_app.items():
        caminho = destino / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
    return tmp_path


def rodar(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), *args],
        capture_output=True,
        text=True,
        check=False,
    )


#: Um `FATOS` mínimo, com a MESMA forma do da árvore real: `audio.alto_falante`
#: existe (`tem`) e aciona por rádio; a cor não aciona por rádio por causa do
#: aparelho.
FATOS_BASE = {
    "audio.alto_falante@dualsense": {
        "existe": "tem",
        "cabo": {"aciona": "sim", "de_onde_sei": "medido", "por_que_nao_aciona": ""},
        "radio": {"aciona": "sim", "de_onde_sei": "medido", "por_que_nao_aciona": ""},
    },
    "identidade.cor_do_aparelho@dualsense": {
        "existe": "tem",
        "cabo": {"aciona": "sim", "de_onde_sei": "medido", "por_que_nao_aciona": ""},
        "radio": {
            "aciona": "não",
            "de_onde_sei": "medido",
            "por_que_nao_aciona": "o-aparelho-recusa",
        },
    },
    "audio.saida_dedicada@dualsense": {
        "existe": "tem",
        "cabo": {"aciona": "", "de_onde_sei": "", "por_que_nao_aciona": ""},
        "radio": {"aciona": "", "de_onde_sei": "incerto", "por_que_nao_aciona": ""},
    },
}


def test_baseline_sem_fala_passa(tmp_path: Path) -> None:
    raiz = monta_arvore(tmp_path, FATOS_BASE, {})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 0, processo.stdout
    assert "0 `Fala`" in processo.stdout


def test_fala_correta_passa(tmp_path: Path) -> None:
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_ACIONA, Fala

DICA = Fala(
    chave="audio.alto_falante@dualsense",
    lado="radio",
    aba="Status",
    texto="O alto-falante toca também por rádio.",
    afirma=AFIRMA_ACIONA,
)
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"widgets/dica.py": arquivo})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 0, processo.stdout


# --------------------------------------------------------------------------
# MORDIDA 1 — o defeito de 17/08 reproduzido como teste
# --------------------------------------------------------------------------
def test_afirma_nao_existe_contra_existe_tem_reprova_nomeando_endereco(tmp_path: Path) -> None:
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NAO_EXISTE, Fala

TEXTO_SONO_SEM_PLACA = Fala(
    chave="audio.alto_falante@dualsense",
    lado="radio",
    aba="Status",
    texto="Sem placa de som do controle (no rádio não existe alto-falante)",
    afirma=AFIRMA_NAO_EXISTE,
)
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"audio_saida.py": arquivo})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 1
    assert "audio_saida.py" in processo.stdout
    assert "audio.alto_falante@dualsense" in processo.stdout
    assert "existe='tem'" in processo.stdout or 'existe="tem"' in processo.stdout


# --------------------------------------------------------------------------
# MORDIDA 3 — "a medição chegou"
# --------------------------------------------------------------------------
def test_medicao_chegou_com_pendencia_aberta_reprova(tmp_path: Path) -> None:
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NADA, NAO_MEDIDO, Fala, Pendencia

DICA_SOM_DEDICADO = Fala(
    chave="audio.saida_dedicada@dualsense",
    lado="radio",
    aba="Status",
    texto=NAO_MEDIDO,
    afirma=AFIRMA_NADA,
    pendente=Pendencia(
        aberta_em="2026-08-24",
        prazo_dias=30,
        quem_fecha="a bancada",
        o_que_falta="o conteúdo do payload",
    ),
)
'''
    fatos_com_medicao = {
        **FATOS_BASE,
        "audio.saida_dedicada@dualsense": {
            "existe": "tem",
            "cabo": {"aciona": "", "de_onde_sei": "", "por_que_nao_aciona": ""},
            # a medição CHEGOU — igual à real, ainda diz NAO_MEDIDO
            "radio": {"aciona": "sim", "de_onde_sei": "medido", "por_que_nao_aciona": ""},
        },
    }
    raiz = monta_arvore(tmp_path, fatos_com_medicao, {"audio_saida.py": arquivo})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 1
    assert "a medição chegou" in processo.stdout
    assert "audio.saida_dedicada@dualsense" in processo.stdout


def test_pendencia_com_placeholder_ainda_aberto_nao_reprova(tmp_path: Path) -> None:
    """O contraste: `de_onde_sei` continua NÃO medido — nada a reprovar."""
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NADA, NAO_MEDIDO, Fala, Pendencia

DICA_SOM_DEDICADO = Fala(
    chave="audio.saida_dedicada@dualsense",
    lado="radio",
    aba="Status",
    texto=NAO_MEDIDO,
    afirma=AFIRMA_NADA,
    pendente=Pendencia(
        aberta_em="2026-08-24",
        prazo_dias=30,
        quem_fecha="a bancada",
        o_que_falta="o conteúdo do payload",
    ),
)
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"audio_saida.py": arquivo})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 0, processo.stdout


# --------------------------------------------------------------------------
# MORDIDA 4 — prazo vencido: --all avisa, --exigir-prazo reprova
# --------------------------------------------------------------------------
def test_prazo_vencido_all_avisa_exigir_prazo_reprova(tmp_path: Path) -> None:
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NADA, NAO_MEDIDO, Fala, Pendencia

DICA = Fala(
    chave="audio.saida_dedicada@dualsense",
    lado="radio",
    aba="Status",
    texto=NAO_MEDIDO,
    afirma=AFIRMA_NADA,
    pendente=Pendencia(
        aberta_em="2026-01-01",
        prazo_dias=1,
        quem_fecha="a bancada",
        o_que_falta="x",
    ),
)
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"audio_saida.py": arquivo})

    todos = rodar(raiz, "--all", "--hoje", "2026-08-24")
    assert todos.returncode == 0, todos.stdout
    assert "AVISO" in todos.stdout
    assert "venceu" in todos.stdout

    release = rodar(raiz, "--exigir-prazo", "--hoje", "2026-08-24")
    assert release.returncode == 1
    assert "FALHA" in release.stdout


def test_prazo_dentro_do_prazo_nao_avisa(tmp_path: Path) -> None:
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NADA, NAO_MEDIDO, Fala, Pendencia

DICA = Fala(
    chave="audio.saida_dedicada@dualsense",
    lado="radio",
    aba="Status",
    texto=NAO_MEDIDO,
    afirma=AFIRMA_NADA,
    pendente=Pendencia(
        aberta_em="2026-08-24",
        prazo_dias=30,
        quem_fecha="a bancada",
        o_que_falta="x",
    ),
)
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"audio_saida.py": arquivo})
    processo = rodar(raiz, "--exigir-prazo", "--hoje", "2026-08-24")
    assert processo.returncode == 0, processo.stdout


# --------------------------------------------------------------------------
# AFIRMA_NAO_ACIONA e a causa (Z6-05 encostando em Z6-04)
# --------------------------------------------------------------------------
def test_afirma_nao_aciona_com_causa_de_fora_passa(tmp_path: Path) -> None:
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NAO_ACIONA, Fala

DICA_DA_COR_NO_RADIO = Fala(
    chave="identidade.cor_do_aparelho@dualsense",
    lado="radio",
    aba="Início",
    texto="No rádio o controle recusa o pedido da cor. Escolha na lista.",
    afirma=AFIRMA_NAO_ACIONA,
)
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"widgets/external_card.py": arquivo})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 0, processo.stdout


def test_afirma_nao_aciona_com_causa_nossa_reprova_e_oferece_afirma_nada(tmp_path: Path) -> None:
    """`by_que_nao_aciona = divida` é causa NOSSA — reprova e diz o que fazer."""
    fatos = {
        **FATOS_BASE,
        "identidade.cor_do_aparelho@dualsense": {
            "existe": "tem",
            "cabo": {"aciona": "sim", "de_onde_sei": "medido", "por_que_nao_aciona": ""},
            "radio": {"aciona": "não", "de_onde_sei": "medido", "por_que_nao_aciona": "divida"},
        },
    }
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NAO_ACIONA, Fala

DICA_DA_COR_NO_RADIO = Fala(
    chave="identidade.cor_do_aparelho@dualsense",
    lado="radio",
    aba="Início",
    texto="No rádio o controle recusa o pedido da cor. Escolha na lista.",
    afirma=AFIRMA_NAO_ACIONA,
)
'''
    raiz = monta_arvore(tmp_path, fatos, {"widgets/external_card.py": arquivo})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 1
    assert "causa NOSSA" in processo.stdout
    assert "AFIRMA_NADA" in processo.stdout


def test_afirma_nao_aciona_com_decisao_tomada_tambem_reprova(tmp_path: Path) -> None:
    """`decisao-tomada` na linha da cor: a MESMA reprovação (mordida 3 de Z6-05)."""
    fatos = {
        **FATOS_BASE,
        "identidade.cor_do_aparelho@dualsense": {
            "existe": "tem",
            "cabo": {"aciona": "sim", "de_onde_sei": "medido", "por_que_nao_aciona": ""},
            "radio": {
                "aciona": "não",
                "de_onde_sei": "medido",
                "por_que_nao_aciona": "decisao-tomada",
            },
        },
    }
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NAO_ACIONA, Fala

DICA_DA_COR_NO_RADIO = Fala(
    chave="identidade.cor_do_aparelho@dualsense",
    lado="radio",
    aba="Início",
    texto="No rádio o controle recusa o pedido da cor.",
    afirma=AFIRMA_NAO_ACIONA,
)
'''
    raiz = monta_arvore(tmp_path, fatos, {"widgets/external_card.py": arquivo})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 1
    assert "causa NOSSA" in processo.stdout


# --------------------------------------------------------------------------
# --fila
# --------------------------------------------------------------------------
def test_fila_lista_placeholder_aberto_e_esvazia_quando_fecha(tmp_path: Path) -> None:
    arquivo_com_pendencia = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NADA, NAO_MEDIDO, Fala, Pendencia

DICA = Fala(
    chave="audio.saida_dedicada@dualsense",
    lado="radio",
    aba="Status",
    texto=NAO_MEDIDO,
    afirma=AFIRMA_NADA,
    pendente=Pendencia(
        aberta_em="2026-08-24",
        prazo_dias=30,
        quem_fecha="a bancada",
        o_que_falta="o conteúdo do payload",
    ),
)
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"audio_saida.py": arquivo_com_pendencia})
    aberto = rodar(raiz, "--fila")
    assert "1 placeholder" in aberto.stdout
    assert "audio.saida_dedicada@dualsense" in aberto.stdout
    assert "audio_saida.py" in aberto.stdout

    arquivo_fechado = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_ACIONA, Fala

DICA = Fala(
    chave="audio.saida_dedicada@dualsense",
    lado="radio",
    aba="Status",
    texto="Toca também por rádio.",
    afirma=AFIRMA_ACIONA,
)
'''
    raiz2 = monta_arvore(tmp_path / "fechado", FATOS_BASE, {"audio_saida.py": arquivo_fechado})
    fechado = rodar(raiz2, "--fila")
    assert "nenhum placeholder" in fechado.stdout


# --------------------------------------------------------------------------
# MORDIDA 6 — a população vem do AST, e o teto é do arquivo de teste
# --------------------------------------------------------------------------
def test_populacao_de_fala_e_a_contagem_exata_e_nao_derivada(tmp_path: Path) -> None:
    """3 `Fala` plantadas, 3 encontradas — o `3` é literal AQUI, nunca lido
    de volta do que o portão contou (a lição de
    `test_o_mapa_separa_divida_de_decisao.py`: um teto que se mede pela mesma
    régua que o gerou nunca reprova).
    """
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_ACIONA, AFIRMA_NAO_ACIONA, Fala

UM = Fala(chave="audio.alto_falante@dualsense", lado="radio", aba="Status",
          texto="a", afirma=AFIRMA_ACIONA)
DOIS = Fala(chave="audio.alto_falante@dualsense", lado="cabo", aba="Status",
            texto="b", afirma=AFIRMA_ACIONA)
TRES = Fala(chave="identidade.cor_do_aparelho@dualsense", lado="radio", aba="Início",
            texto="c", afirma=AFIRMA_NAO_ACIONA)
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"varios.py": arquivo})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 0, processo.stdout
    assert "3 `Fala`" in processo.stdout


def test_fala_dinamica_nao_e_engolida_em_silencio(tmp_path: Path) -> None:
    """`afirma` construído em runtime (não um `AFIRMA_*` nem literal) reprova
    em vez de ser contado como se estivesse tudo certo — declarar
    dinamicamente é o mesmo defeito que a `Fala.__post_init__` da Z6-03
    recusa em runtime; este portão recusa em tempo de portão.
    """
    arquivo = '''
from hefesto_dualsense4unix.app.fala_do_mapa import Fala

def _monta(valor):
    return Fala(chave="audio.alto_falante@dualsense", lado="radio", aba="Status",
                texto="a", afirma=valor)
'''
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"dinamico.py": arquivo})
    processo = rodar(raiz, "--all")
    assert processo.returncode == 1
    assert "não é um AFIRMA_* conhecido" in processo.stdout


# --------------------------------------------------------------------------
# Os dois módulos que este portão importa não têm dependência pesada
# --------------------------------------------------------------------------
def test_os_dois_modulos_de_registro_nao_tem_dependencia_pesada() -> None:
    """`import gi`/`Gtk` em `fala_do_mapa.py` faria este portão ImportError em
    qualquer runner sem GUI — exatamente o modo de falha que o cabeçalho do
    script recusa.
    """
    fonte = FALA_DO_MAPA_REAL.read_text(encoding="utf-8")
    proibidos = ("import gi", "from gi", "Gtk", "gi.repository")
    for termo in proibidos:
        assert termo not in fonte, f"{termo!r} em fala_do_mapa.py — dependência pesada"
