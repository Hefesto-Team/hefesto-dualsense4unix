"""A folha do microfone: o nó pelo ENDEREÇO, o byte em `common[6]`, e o pico sem disco.

A folha (`scripts/ensaios/a_folha_do_microfone_por_controle.py`) decide três
perguntas na bancada dela — MIC-OS-QUATRO-01 (o nó sobe e capta?),
MIC-VOLUME-02 (o byte do aparelho muda a captura?) e a TARJA que diz *"O
sistema não publica um microfone para este controle"* sobre um controle que tem
o nó publicado. O aparelho é dela, na mesa. O que se prova aqui é a parte que
já enganou esta casa, e as quatro famílias são estas:

1. **O NÓ CASADO PELO NÚMERO.** Medido na mesa em 09/09/2026, quando o
   `os_nos_de_som_por_controle` procurava a descrição «Microfone do Controle N»:
   o mesmo `hefesto_mic_<hex6>` foi dado ao controle do CABO numa corrida e ao
   do RÁDIO na seguinte, sem nada ter mudado no áudio — o N anda com a mesa. **O
   censo foi curado em 12/09/2026** (TRES-CONTAS-PARA-UM-NUMERO-01 §6): os dois
   casam pelo NOME de dentro. A folha já casava por ENDEREÇO, pelo dono da
   pergunta no produto (`canal_do_microfone.nome_do_canal`).
2. **O BYTE NA POSIÇÃO ERRADA, ou o bit esquecido.** `common[6]` com o flag0
   `0x40`; um `[5]` mediria o alto-falante achando que mede o microfone.
3. **A FRASE QUE AFIRMA SOBRE O QUE NÃO MEDIU.** A linha 6 dizia *"o daemon
   não respondeu"* antes de alguém perguntar — pego ao dirigir a folha, com o
   daemon de pé.
4. **O PICO INDO PARA DISCO.** Ela está com o microfone aberto na sala: o
   pedaço vira um `float` e morre.

MORDE (provado antes de entregar, arrancando cada cura):
* `COMMON_MIC_VOLUME` -> `5` em `common_do_byte`;
* apagar o `c[0] |= VALID_FLAG0_MIC_VOLUME`;
* casar o nó pela descrição («Microfone do Controle N») em vez do endereço;
* devolver `perguntou=True` sempre em `veredito_da_tarja`;
* trocar o `32768` do pico por `32767`, ou tirar o corte do quadro ímpar.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. A folha monta
# `Gtk.Window`, então o módulo inteiro depende do PyGObject de verdade.
exigir_gi_real("a folha do microfone por controle")

import csv
import importlib.util
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ENSAIOS = RAIZ / "scripts" / "ensaios"

#: ENDEREÇOS SINTÉTICOS, na máscara da casa (octetos 4 e 5 zerados). Nenhum MAC
#: real entra em arquivo versionado, e os dois portões de anonimato reprovam —
#: um deles pega por FORMA, sem consultar OUI nenhum.
MAC_DO_CABO = "aa:bb:cc:00:00:11"
MAC_DO_RADIO = "aa:bb:cc:00:00:22"


@pytest.fixture(scope="module")
def folha():
    """O instrumento, carregado do arquivo — ele não é um pacote importável."""
    if str(ENSAIOS) not in sys.path:
        sys.path.insert(0, str(ENSAIOS))
    caminho = ENSAIOS / "a_folha_do_microfone_por_controle.py"
    spec = importlib.util.spec_from_file_location("folha_do_microfone", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["folha_do_microfone"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@dataclass
class AlvoDeMentira:
    """O mínimo que a folha pergunta a um aparelho: quem é e por onde fala."""

    mac: str
    transporte: str
    hidraw: str = "hidraw9"
    caminho_hidraw: str = "/dev/hidraw9"


# ---------------------------------------------------------------------------
# 1 · O byte, e o bit que o autoriza
# ---------------------------------------------------------------------------
def test_o_byte_vai_no_common6_com_o_flag0_0x40_e_mais_nada(folha):
    """MORDE: `COMMON_MIC_VOLUME` -> 5 mede o alto-falante; sem o bit, nada sai."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    c = folha.common_do_byte(0x20)
    assert len(c) == rep.COMMON_LEN == 47
    assert c[rep.COMMON_MIC_VOLUME] == 0x20
    assert rep.COMMON_MIC_VOLUME == 6, "o byte do microfone é o common[6]"
    assert c[0] & rep.VALID_FLAG0_MIC_VOLUME == rep.VALID_FLAG0_MIC_VOLUME == 0x40
    # E MAIS NADA: um common cheio de estado faria de cada passo uma medição
    # diferente — a lição do `corpo_do_degrau.py`.
    resto = [i for i, v in enumerate(c) if v and i not in (0, rep.COMMON_MIC_VOLUME)]
    assert resto == [], f"a folha escreveu bytes que não são do ensaio: {resto}"


def test_o_negativo_do_ensaio_manda_o_teto_sem_a_autorizacao(folha):
    """O `--sem-bit` do instrumento irmão, aqui na chave «Assumir» desligada."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    c = folha.common_do_byte(rep.TETO_MIC_VOLUME, com_bit=False)
    assert c[rep.COMMON_MIC_VOLUME] == rep.TETO_MIC_VOLUME == 0x40
    assert c[0] == 0, "sem o bit, o flag0 tem de sair limpo — é o negativo"


def test_o_byte_recusa_valor_acima_do_teto_do_aparelho(folha):
    """`0x41` não é um volume de microfone: o teto é do firmware, não nosso."""
    with pytest.raises(ValueError):
        folha.common_do_byte(0x41)


def test_o_martelo_so_bate_o_que_ela_assumiu_e_a_porta_so_abre_ai(folha, monkeypatch):
    """A porta do hidraw NÃO abre na construção — é o que faz `--listar` inócuo."""

    class EscritorDeMentira:
        def __init__(self, alvo):
            self.alvo = alvo
            self.escritos: list[bytes] = []

        def abrir(self):
            return "porta: dublê"

        def escrever(self, common):
            self.escritos.append(bytes(common))
            return len(common)

        def fechar(self):
            return None

    monkeypatch.setattr(folha, "Escritor", EscritorDeMentira)
    controle = folha.ControleNaFolha(AlvoDeMentira(MAC_DO_CABO, folha.CABO))
    assert controle.escritor is None, "a porta abriu antes de ela assumir"

    controle.escrever_byte(0x20)
    for _ in range(5):
        controle.bater()
    assert controle.escritor is None and controle.escritas == 0

    controle.assumir(True)
    assert controle.escritor is not None
    for _ in range(3):
        controle.bater()
    assert controle.escritas == 3
    ultimo = controle.escritor.escritos[-1]
    assert ultimo[6] == 0x20 and ultimo[0] & 0x40

    controle.devolver()
    assert controle.escritor.escritos[-1] == bytes(47), "devolver não zerou o common"


# ---------------------------------------------------------------------------
# 2 · O nó pelo ENDEREÇO — a família que já atribuiu o nó ao controle errado
# ---------------------------------------------------------------------------
#: A lista viva como o `pactl` a devolve, com UMA armadilha: o nó pertence ao
#: controle do CABO (o sufixo do endereço dele) e a DESCRIÇÃO carrega o número
#: do assento do OUTRO. Foi assim que o censo irmão trocou os dois.
_SOURCES_COM_A_ARMADILHA = """Source #1
\tState: SUSPENDED
\tName: hefesto_mic_000011
\tDescription: Microfone do Controle 2
Source #2
\tState: RUNNING
\tName: alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.2
\tDescription: DualSense wireless controller (PS5)
\t\talsa.card = "3"
"""


def _pactl_de_mentira(*argv: str) -> str:
    if argv[:2] == ("list", "sources"):
        return _SOURCES_COM_A_ARMADILHA
    return ""


def test_o_no_e_do_controle_cujo_endereco_ele_carrega_nao_do_numero_da_descricao(
    folha, monkeypatch
):
    """A MORDIDA DESTE ARQUIVO.

    O nó `hefesto_mic_000011` é do controle `…:11` — os seis hex do fim do
    endereço dele. A descrição diz «Controle 2», que é o assento do OUTRO.
    Casar pela descrição dá o microfone do cabo à coluna do rádio, e foi o que
    aconteceu na mesa em 09/09.
    """
    monkeypatch.setattr(folha, "pactl", _pactl_de_mentira)
    monkeypatch.setattr(folha, "placas_de_dualsense", lambda _alvos: [])
    monkeypatch.setattr(folha, "fonte_de_captura_do_uniq", lambda _uniq: None)

    cabo = AlvoDeMentira(MAC_DO_CABO, folha.CABO, hidraw="hidraw1")
    radio = AlvoDeMentira(MAC_DO_RADIO, folha.RADIO, hidraw="hidraw2")
    leituras = folha.ler_o_sistema([cabo, radio])

    assert leituras[MAC_DO_CABO].canal == "hefesto_mic_000011"
    assert leituras[MAC_DO_CABO].descricao == "Microfone do Controle 2"
    assert leituras[MAC_DO_CABO].publica is True
    assert leituras[MAC_DO_RADIO].canal == "", (
        "o nó do CABO foi parar na coluna do RÁDIO — é o casamento por NÚMERO, "
        "e é exatamente o defeito que esta folha existe para não repetir"
    )
    assert leituras[MAC_DO_RADIO].publica is False


def test_o_nome_do_no_vem_do_dono_da_pergunta_no_produto(folha):
    """Nenhuma régua nova: quem batiza é `canal_do_microfone.nome_do_canal`."""
    from hefesto_dualsense4unix.integrations import canal_do_microfone

    assert folha.no_do_canal(MAC_DO_CABO) == canal_do_microfone.nome_do_canal(MAC_DO_CABO)
    assert folha.no_do_canal("nao-e-um-endereco") == "", (
        "sem endereço inteiro não se batiza canal — `so_hex` de uma palavra "
        "qualquer devolve hex de mentira"
    )


# ---------------------------------------------------------------------------
# 3 · A tarja: o sistema de um lado, o daemon do outro
# ---------------------------------------------------------------------------
def test_a_tarja_que_mente_sai_nomeada_quando_os_dois_discordam(folha):
    """Sistema publica + daemon diz `sem_fonte` = a frase da aba Controles."""
    leitura = folha.LeituraDoSistema(canal="hefesto_mic_000011", placa_usb="alsa_input.x")
    frase = folha.veredito_da_tarja(leitura, {"status": "sem_fonte"}, perguntou=True)
    assert "DISCORDAM" in frase


def test_quando_ninguem_publica_e_o_daemon_diz_sem_fonte_os_dois_concordam(folha):
    """A tarja está CERTA aqui: falta o canal, não a frase."""
    frase = folha.veredito_da_tarja(
        folha.LeituraDoSistema(), {"status": "sem_fonte"}, perguntou=True
    )
    assert "concordam" in frase and "DISCORDAM" not in frase


def test_o_daemon_atendendo_no_no_de_outro_controle_sai_acusado(folha):
    """O defeito que o `por_uniq` existe para confessar, dito na tela dela."""
    leitura = folha.LeituraDoSistema(canal="hefesto_mic_000011", do_produto="hefesto_mic_000011")
    frase = folha.veredito_da_tarja(
        leitura, {"status": "ok", "fonte": "hefesto_mic_000022"}, perguntou=True
    )
    assert "OUTRO NÓ" in frase


def test_antes_da_pergunta_a_folha_nao_acusa_o_daemon_de_silencio(folha):
    """MORDE: devolver `perguntou=True` sempre põe de volta o defeito medido.

    Dirigindo a folha em 09/09, com o daemon de pé e ninguém tendo perguntado
    nada, a linha 6 dizia *"o daemon não respondeu"* nos primeiros dois
    segundos. `None` de resposta antes da pergunta é «não perguntei».
    """
    frase = folha.veredito_da_tarja(folha.LeituraDoSistema(), None, perguntou=False)
    assert "ninguém perguntou ainda" in frase
    assert "não respondeu" not in frase
    # E com a pergunta feita, o silêncio volta a ser silêncio.
    calado = folha.veredito_da_tarja(folha.LeituraDoSistema(), None, perguntou=True)
    assert "não respondeu" in calado


def test_a_linha_seis_carrega_o_corpo_cru_e_nao_so_o_veredito(folha):
    """MORDE: resumir a resposta apaga o `por_uniq` e o `fonte`.

    São eles que dizem em QUAL microfone o daemon mexeu — e o `por_uniq` é a
    única confissão que existe de *"atendi, mas no controle de outra pessoa"*.
    """
    leitura = folha.LeituraDoSistema(canal="hefesto_mic_000011")
    corpo = {"status": "sem_fonte", "fonte": None, "volume": None, "por_uniq": True}
    frase = folha.frase_da_resposta_do_daemon(leitura, corpo, perguntou=True)
    assert "CRU:" in frase
    assert "por_uniq" in frase and "sem_fonte" in frase
    assert "DISCORDAM" in frase, "o veredito tem de vir junto do corpo cru"
    # Antes da pergunta não há corpo nenhum a mostrar, e nem se inventa um.
    assert "CRU:" not in folha.frase_da_resposta_do_daemon(leitura, None, perguntou=False)


# ---------------------------------------------------------------------------
# 4 · O pico — o número, e nada em disco
# ---------------------------------------------------------------------------
def test_o_pico_de_um_pedaco_e_o_maior_modulo_sobre_32768(folha):
    """MORDE: 32767 no lugar de 32768 põe um «aaaa» saturado acima de 1,0."""
    assert folha.pico_do_pedaco(b"") == 0.0
    assert folha.pico_do_pedaco(struct.pack("<4h", 0, 0, 0, 0)) == 0.0
    assert folha.pico_do_pedaco(struct.pack("<2h", 16384, -8192)) == pytest.approx(0.5)
    # O mínimo de um s16 é -32768: por 32767 isto sairia 1.00003.
    assert folha.pico_do_pedaco(struct.pack("<1h", -32768)) == pytest.approx(1.0)


def test_o_quadro_impar_do_corte_do_pedaco_e_descartado(folha):
    """Meio quadro de s16 não é uma amostra — somá-lo inventa pico."""
    inteiro = struct.pack("<2h", 4096, 4096)
    assert folha.pico_do_pedaco(inteiro + b"\xff") == pytest.approx(folha.pico_do_pedaco(inteiro))


def test_o_ouvido_le_do_stdout_conta_o_pico_e_nao_cria_arquivo(folha, monkeypatch, tmp_path):
    """O caminho INTEIRO do pico, com um sinal conhecido e nenhum disco tocado.

    O leitor é trocado por um que emite s16 de pico conhecido: o que se prova é
    o cano (processo -> `stdout` -> thread -> número), sem abrir o microfone
    dela para isso.
    """
    programa = (
        "import sys,struct;"
        "sys.stdout.buffer.write(struct.pack('<2048h', *([16384]*2048)));"
        "sys.stdout.buffer.flush()"
    )
    monkeypatch.setattr(folha.shutil, "which", lambda _nome: "/bin/true")
    monkeypatch.setattr(
        folha.OuvidoDoPico, "argv", staticmethod(lambda _fonte: [sys.executable, "-c", programa])
    )
    monkeypatch.chdir(tmp_path)
    antes = set(tmp_path.iterdir())

    ouvido = folha.OuvidoDoPico("uma_fonte_qualquer")
    assert ouvido.abrir() is None
    for _ in range(200):  # até 2 s; o EOF do emissor é o sinal de "acabou"
        if ouvido.pedacos >= 1 and ouvido._proc is not None and ouvido._proc.poll() is not None:
            break
        import time

        time.sleep(0.01)
    ouvido.fechar()

    assert ouvido.pedacos >= 1, "o ouvido não leu um pedaço sequer"
    assert ouvido.maximo == pytest.approx(0.5), "o pico do sinal conhecido não bateu"
    assert set(tmp_path.iterdir()) == antes, "o ouvido do pico criou arquivo — ele não pode"


def test_o_ouvido_recusa_dizendo_quando_nao_ha_fonte_nem_leitor(folha, monkeypatch):
    """Recusar em silêncio é o que faz um botão morto parecer um mic mudo."""
    assert "peça o canal" in (folha.OuvidoDoPico("").abrir() or "")
    monkeypatch.setattr(folha.shutil, "which", lambda _nome: None)
    motivo = folha.OuvidoDoPico("uma_fonte").abrir() or ""
    assert folha.LEITOR_DO_PICO in motivo


def test_o_codigo_do_ouvido_nao_sabe_escrever_arquivo(folha):
    """A régua LÊ o código: nenhuma porta de disco dentro do medidor de pico.

    Ela está com o microfone aberto na própria sala, e o cabeçalho da folha
    promete que nenhuma amostra sobrevive ao pedaço que a produziu.

    **ESTA RÉGUA LÊ O CÓDIGO, NUNCA O TEXTO — e a primeira versão dela não
    lia.** Ela terminava com um `"wave" not in fonte`, e reprovou na primeira
    corrida contra a DOCSTRING que avisa que não pode haver `wave` ali. *Um
    comentário que descreve o padrão proibido vira a primeira ocorrência dele*
    — é a armadilha de PROSA desta casa, e ela pegou o instrumento escrito
    para não cair nela. As chamadas de verdade vivem na árvore; as palavras da
    docstring, não.
    """
    import ast
    import inspect

    fonte = inspect.getsource(folha.OuvidoDoPico) + inspect.getsource(folha.pico_do_pedaco)
    proibidas = {"open", "mkstemp", "mkdtemp", "NamedTemporaryFile", "makedirs", "wave"}
    achadas = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Call):
            alvo = getattr(no.func, "id", "") or getattr(no.func, "attr", "")
            dono = getattr(getattr(no.func, "value", None), "id", "")
            if alvo in proibidas or dono in proibidas:
                achadas.append(f"{dono}.{alvo}" if dono else alvo)
        elif isinstance(no, (ast.Import, ast.ImportFrom)):
            nome = getattr(no, "module", "") or ""
            achadas += [n.name for n in no.names if n.name in proibidas or nome in proibidas]
    assert achadas == [], f"o medidor de pico ganhou porta de disco: {achadas}"


# ---------------------------------------------------------------------------
# 5 · A mesa, e a tabela que sustenta a folha
# ---------------------------------------------------------------------------
def test_a_folha_diz_com_todas_as_letras_quando_falta_o_par(folha):
    """*"preciso de um no cabo e um no rádio; achei dois no cabo"* — dela, verbatim."""
    dois_cabos = [
        AlvoDeMentira(MAC_DO_CABO, folha.CABO),
        AlvoDeMentira(MAC_DO_RADIO, folha.CABO),
    ]
    frase = folha.frase_da_mesa(dois_cabos)
    assert frase.startswith("FALTA O PAR")
    assert "2 no cabo" in frase and "nenhum no rádio" in frase

    par = [AlvoDeMentira(MAC_DO_CABO, folha.CABO), AlvoDeMentira(MAC_DO_RADIO, folha.RADIO)]
    assert folha.frase_da_mesa(par).startswith("a mesa tem o par")


def test_a_tabela_tem_as_seis_linhas_com_id_unico_e_forma_conhecida(folha):
    """Pergunta nova é LINHA nova: a folha se monta desta tabela, e só dela."""
    ids = [linha.id for linha in folha.LINHAS]
    assert len(ids) == len(set(ids)) == 6
    formas = {"leitura", "pedido", "pico", "byte", "campo", "resposta"}
    assert {linha.forma for linha in folha.LINHAS} == formas
    assert folha.linha_de("o-byte-do-aparelho").sprint == "MIC-VOLUME-02"
    with pytest.raises(KeyError):
        folha.linha_de("linha-que-nao-existe")


def test_toda_linha_aponta_para_uma_linha_viva_do_mapa_de_canais(folha):
    """Uma linha de caderno com `linha_id` que o mapa não tem não responde nada."""
    with open(RAIZ / "docs" / "data" / "mapa-controles.csv", encoding="utf-8", newline="") as f:
        conhecidas = {r["id"] for r in csv.DictReader(f)}
    orfas = [linha.linha_do_mapa for linha in folha.LINHAS if linha.linha_do_mapa not in conhecidas]
    assert orfas == [], f"linhas do mapa que não existem: {orfas}"
