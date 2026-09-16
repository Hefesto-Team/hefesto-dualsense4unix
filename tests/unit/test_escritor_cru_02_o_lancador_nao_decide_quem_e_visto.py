"""ESCRITOR-CRU-02 — quem joga fora da Steam também tem um escritor cru.

O `core/escritor_cru` nasceu enxergando UM escritor: o cliente Steam. Ele nunca
escondeu isso — a própria docstring declarava o ponto cego::

    "Só reconhece a Steam. A varredura é restrita aos PIDs dela (…) Um segundo
    escritor cru — um jogo fora do Steam, outro daemon de controle — passa
    despercebido. Varrer `/proc/*/fd` inteiro seria caro e indiscreto, e a
    Steam é o escritor que a mesa dela mediu."

**ORDEM DELA, 16/09/2026**, e é ela que derruba a última linha:

    "O app deveria construir tudo independente de qual jogo ou launcher. (…) é
    um app que será focado pra acessibilidade. Isso não pode se repetir."

AS TRÊS RAZÕES, MEDIDAS — e duas caíram
----------------------------------------
1. **"seria caro"**: varrer TODOS os processos custou **9,5 · 10,8 · 12,8 ms**
   em três voltas nesta máquina (122 processos legíveis, 4.139 fds), contra os
   ~6 ms da varredura restrita. A sonda já é rate-limitada e nunca roda no
   event loop. CAIU.
2. **"a Steam é o escritor que a mesa dela mediu"**: verdadeiro e insuficiente.
   A mesa dela é uma; o produto é de outras pessoas. CAIU.
3. **"indiscreto"**: DE PÉ, e virou disciplina — o alvo do symlink que não
   começa com `/dev/hidraw` morre na mesma linha em que é lido, sem ser
   guardado, logado ou devolvido. Esta régua trava isso.

E A ARMADILHA QUE A CURA CRIA, que é por que o default não é a varredura nua
----------------------------------------------------------------------------
**O daemon segura o próprio hidraw** — medido nesta máquina: quatro fds no
mesmo PID. Uma sentinela alimentada pela varredura nua veria a si mesma, a
borda dispararia na primeira volta, e o veredito passaria a acusar escritor
alheio para sempre. Por isso o default é `escritores_crus_alheios`.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core import escritor_cru as ec

FONTE = Path(ec.__file__).read_text(encoding="utf-8")

#: O fonte com as quebras de linha e o prefixo `#:` achatados. A medição é o
#: que importa; ONDE a linha quebrou não é — e uma régua que dependesse disso
#: reprovaria quem só reformatou um comentário.
FONTE_CORRIDA = " ".join(
    FONTE.replace("#:", " ").replace("*", " ").split()
)


class TestAVarreduraAmplaVeAlemDaSteam:
    def test_ve_um_processo_que_nao_e_a_steam(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """**O CASO QUE ORIGINOU ESTA RÉGUA** — o jogo por Lutris/Heroic.

        MORDIDA: trocar `holders_de_hidraw_de_qualquer_um` de volta por
        `holders_de_hidraw` e o nó do jogo some do mapa.
        """
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {"4242": {"3": "/dev/hidraw6"}},  # um PID qualquer, sem ser Steam
        )
        mapa = ec.holders_de_hidraw_de_qualquer_um()
        assert mapa == {"/dev/hidraw6": [4242]}, (
            "o escritor cru fora da Steam continua invisível"
        )

    def test_o_filtro_por_no_continua_valendo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Só os nós que interessam voltam — um teclado HID não é assunto."""
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {"4242": {"3": "/dev/hidraw6", "4": "/dev/hidraw9"}},
        )
        assert ec.holders_de_hidraw_de_qualquer_um(["/dev/hidraw6"]) == {
            "/dev/hidraw6": [4242]
        }

    def test_nada_que_nao_seja_hidraw_atravessa(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A DISCRIÇÃO, e ela é a razão 3 que ficou de pé.

        A sonda lê o alvo de cada symlink de `/proc/<pid>/fd` — inclusive os
        arquivos privados de quem estiver aberto na máquina. O que ela pode
        fazer com isso é UMA coisa: descartar na hora.

        MORDIDA: apagar o `if not target.startswith("/dev/hidraw"): continue` e
        este caso devolve o caminho do arquivo pessoal no mapa.
        """
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {
                "4242": {
                    "3": "/dev/hidraw6",
                    "4": "/home/alguem/Documentos/carta-pessoal.odt",
                    "5": "socket:[12345]",
                }
            },
        )
        mapa = ec.holders_de_hidraw_de_qualquer_um()
        assert mapa == {"/dev/hidraw6": [4242]}
        assert not any("carta-pessoal" in str(v) for v in mapa.values())

    def test_processo_ilegivel_degrada_sem_derrubar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Processo de outro usuário: `/proc/<pid>/fd` dá `OSError`.

        Degradar é a regra da casa aqui — ausência é "não sondado", nunca
        "ninguém segura". O que NÃO pode é a varredura inteira morrer por um.
        """
        _proc_de_mentira(
            tmp_path, monkeypatch, {"4242": {"3": "/dev/hidraw6"}, "9999": None}
        )
        assert ec.holders_de_hidraw_de_qualquer_um() == {"/dev/hidraw6": [4242]}


class TestNaoAcusamosANosMesmos:
    def test_o_proprio_daemon_sai_da_lista(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ARMADILHA DA CURA: o daemon segura o próprio hidraw.

        Medido nesta máquina: QUATRO fds do mesmo nó, no mesmo PID. Sem este
        filtro a sentinela acusaria escritor alheio para sempre.

        MORDIDA: devolver `holders_de_hidraw_de_qualquer_um` direto de
        `escritores_crus_alheios`.
        """
        eu = os.getpid()
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {str(eu): {"3": "/dev/hidraw6", "4": "/dev/hidraw6"}},
        )
        assert ec.escritores_crus_alheios(["/dev/hidraw6"]) == {}

    def test_o_alheio_sobrevive_ao_filtro(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """E o nó que TEM os dois volta só com o alheio."""
        eu = os.getpid()
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {str(eu): {"3": "/dev/hidraw6"}, "4242": {"3": "/dev/hidraw6"}},
        )
        assert ec.escritores_crus_alheios(["/dev/hidraw6"]) == {
            "/dev/hidraw6": [4242]
        }

    def test_no_so_com_o_nosso_pid_nao_vira_chave_vazia(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chave com lista VAZIA leria como "sondado e tem alguém" no consumidor.

        MORDIDA: tirar o `if (alheios := ...)` do dicionário por compreensão.
        """
        eu = os.getpid()
        _proc_de_mentira(
            tmp_path,
            monkeypatch,
            {str(eu): {"3": "/dev/hidraw0"}, "4242": {"3": "/dev/hidraw6"}},
        )
        mapa = ec.escritores_crus_alheios()
        assert "/dev/hidraw0" not in mapa, "nó só nosso virou chave"
        assert mapa == {"/dev/hidraw6": [4242]}


class TestASentinelaEstaLIGADA:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def test_o_default_da_sentinela_e_a_visao_ampla(self) -> None:
        """MORDIDA: devolver o default a `holders_de_hidraw`.

        Sem isto a função nova existiria e ninguém a chamaria — que foi
        exatamente o que aconteceu com a `sentinela_do_wrapper`, entregue com
        19 testes e zero chamadores.
        """
        s = ec.SentinelaDeEscritorCru()
        assert s._sonda is ec.escritores_crus_alheios, (
            "a sentinela voltou a enxergar só a Steam"
        )

    def test_a_sonda_injetada_continua_vencendo(self) -> None:
        """O default não pode tirar de ninguém o direito de injetar a sua."""
        marca: list[object] = []

        def minha_sonda(nos=None):
            marca.append(nos)
            return {}

        s = ec.SentinelaDeEscritorCru(sonda=minha_sonda)
        s.sondar(["/dev/hidraw6"], agora=1.0)
        assert marca, "a sonda injetada não foi chamada"

    def test_o_caminho_da_janela_continua_restrito(self) -> None:
        """DE PROPÓSITO, e a razão está escrita no fonte.

        `ipc_handlers._steam_hidraw_holders` alimenta a frase da aba Status, que
        NOMEIA a Steam. Trocar a sonda ali trocaria o texto da tela sem ninguém
        pedir — e texto de tela é palavra dela (PROVA-DE-TELA-01).
        """
        janela = Path(
            "src/hefesto_dualsense4unix/daemon/ipc_handlers.py"
        ).read_text(encoding="utf-8")
        assert "holders_de_hidraw_de_qualquer_um" not in janela
        assert "from hefesto_dualsense4unix.core.escritor_cru import holders_de_hidraw" in janela


class TestOCustoEstaMedidoNoFonte:
    def test_o_orcamento_existe_e_nao_e_infinito(self) -> None:
        """Varredura sem teto trava o chamador quando o `/proc` engasga."""
        assert 0.0 < ec.ORCAMENTO_DA_VARREDURA_AMPLA_S <= 2.0

    def test_a_medicao_esta_escrita_junto_do_numero(self) -> None:
        """Número de orçamento sem a medição ao lado envelhece calado.

        MORDIDA: apague os milissegundos medidos do comentário.
        """
        assert "4.139 fds" in FONTE_CORRIDA, "a medição que justifica o teto sumiu"
        assert "122 processos legíveis" in FONTE_CORRIDA
        assert "12,8" in FONTE_CORRIDA, "as voltas medidas sumiram"


# --------------------------------------------------------------------------
# O /proc de mentira — e ele é de MENTIRA porque o de verdade não se controla
# --------------------------------------------------------------------------
def _proc_de_mentira(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    processos: dict[str, dict[str, str] | None],
) -> None:
    """Monta `/proc/<pid>/fd/<n>` como symlinks de verdade, num tmp.

    Symlink DE VERDADE e não um dublê de `os.readlink`: a sonda usa
    `os.listdir` + `os.readlink` + `str.startswith`, e um dublê que devolvesse
    strings puláría justamente a parte que pode quebrar (um `fd` que some entre
    o `listdir` e o `readlink`). `None` = processo ilegível (outro usuário).
    """
    raiz = tmp_path / "proc"
    raiz.mkdir()
    ilegiveis: set[str] = set()
    for pid, fds in processos.items():
        d = raiz / pid / "fd"
        d.mkdir(parents=True)
        if fds is None:
            ilegiveis.add(str(d))
            continue
        for n, alvo in fds.items():
            (d / n).symlink_to(alvo)

    listdir_real = os.listdir

    def listdir(caminho, *a, **k):
        s = str(caminho)
        if s in ilegiveis:
            raise PermissionError(s)
        if s == "/proc":
            return listdir_real(raiz)
        if s.startswith("/proc/"):
            return listdir_real(str(raiz) + s[len("/proc"):])
        return listdir_real(caminho, *a, **k)

    readlink_real = os.readlink

    def readlink(caminho, *a, **k):
        s = str(caminho)
        if s.startswith("/proc/"):
            return readlink_real(str(raiz) + s[len("/proc"):])
        return readlink_real(caminho, *a, **k)

    monkeypatch.setattr(ec.os, "listdir", listdir)
    monkeypatch.setattr(ec.os, "readlink", readlink)
