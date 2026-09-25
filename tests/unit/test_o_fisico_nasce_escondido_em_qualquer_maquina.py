"""O-FISICO-NASCE-ESCONDIDO-EM-QUALQUER-MAQUINA-01 — a regra do Hefesto fala por último.

A QUEIXA DELA, 25/09/2026, 09h40: *«4 controles conectados, lightbar do player
3 apagado e do player 4 também. nossas soluções estão ocorrendo para todos os
players, certo?»*

O QUE FOI MEDIDO NA MESA DELA, só lendo: a Steam segurava o hidraw FÍSICO do
P2, do P3 e do P4, e o banco do udev desses três nós tinha a tag corrente
`uaccess` (`Q:uaccess`) sem a `seat` — a impressão digital de uma regra que
devolve o `uaccess` DEPOIS da `71-seat.rules`. É a
`/usr/lib/udev/rules.d/71-sony-controllers.rules`, do pacote
`game-devices-udev`, que todo Pop!_OS de desktop traz. A regra do Hefesto se
chamava `70-ps5-controller.rules`, fechava o nó, e a 71 o reabria: o nó nascia
`0660` com a ACL da sessão, e a Steam o abria no instante do nascimento.

A RÉGUA ANTIGA ERA CEGA POR CONSTRUÇÃO: o udev de bolso de
`test_o_no_nasce_fechado.py` rodava SÓ o asset, começando do estado «como o
steam-devices o deixa», e nunca o que vem depois dele. Esta roda a CADEIA:
as regras de `/etc`, `/run`, `/usr/local/lib` e `/usr/lib` ordenadas juntas
pelo nome do arquivo (o de `/etc` sombreia o de mesmo nome), com as regras de
terceiros DE VERDADE copiadas como dublê em `tests/fixtures/udev/de-terceiros/`
(o LEIA de lá diz de onde vêm), e o `73-seat-late.rules` do systemd decidindo,
como decide no aparelho, se o `RUN{builtin}+="uaccess"` entra na fila.

AS MORDIDAS, medidas em 25/09/2026:
  - o asset de volta ao nome `70-ps5-controller.rules` → as seis linhas do
    físico com a `71-sony` reprovam (a 71 reabre);
  - o `MODE:=` de volta a `MODE=` → a régua da regra posterior com `0666`
    reprova;
  - o `DEVPATH` tirado da linha do vpad → o Edge físico pelo cabo sai aberto.

Nada aqui toca `/dev`, `/sys`, `/run/udev` nem o udev vivo: é tudo texto.
"""

from __future__ import annotations

import fnmatch
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ASSETS = RAIZ / "assets"
TERCEIROS = RAIZ / "tests" / "fixtures" / "udev" / "de-terceiros"

#: O nome de antes (até 25/09/2026) — o da mordida.
NOME_DE_ANTES = "70-ps5-controller.rules"

#: Os diretórios do udev, na ordem de PRIORIDADE para o mesmo nome de arquivo
#: (man 7 udev, «RULES FILES»): /etc sombreia /run, que sombreia /usr/local/lib
#: e /usr/lib. A ORDEM DE EXECUÇÃO é outra coisa: todos juntos, pelo nome.
DIRETORIOS = ("etc", "run", "usr/local/lib", "usr/lib")


def a_regra_do_no() -> Path:
    """O asset que fecha o hidraw do DualSense físico, achado pelo CONTEÚDO.

    Pelo conteúdo, e não pelo nome, de propósito: a mordida desta régua é
    justamente o nome. Se o teste digitasse o nome, renomear o asset de volta
    ao 70 quebraria o teste por «arquivo não existe» — e não pela razão certa.
    """
    achados = [
        p
        for p in sorted(ASSETS.glob("[0-9][0-9]-*.rules"))
        if 'KERNELS=="0005:054C:0CE6.*"' in p.read_text(encoding="utf-8")
        and 'SUBSYSTEM=="hidraw"' in p.read_text(encoding="utf-8")
    ]
    assert len(achados) == 1, achados
    return achados[0]


# ---------------------------------------------------------------------------
# O udev de bolso
# ---------------------------------------------------------------------------

_TERMO = re.compile(
    r'([A-Z_]+(?:\{[^}]*\})?)\s*(==|!=|\+=|-=|:=|=)\s*"((?:[^"\\]|\\.)*)"'
)

#: As chaves que casam no PRÓPRIO aparelho.
_DO_APARELHO = ("ACTION", "KERNEL", "SUBSYSTEM", "DEVPATH", "DRIVER", "TAG", "TEST")
#: As chaves de PAI: numa linha, todas têm de casar no MESMO elo da corrente
#: (o próprio aparelho conta como o primeiro elo) — é a regra do udev.
_DE_PAI = ("KERNELS", "SUBSYSTEMS", "DRIVERS")


@dataclass
class Elo:
    kernel: str
    subsystem: str = ""
    driver: str = ""
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class Aparelho:
    """Um hidraw como o udev o vê, e o que as regras fizeram com ele."""

    devpath: str
    pais: list[Elo]
    acao: str = "add"
    env: dict[str, str] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    modo: str | None = None
    dono: str | None = None
    grupo: str | None = None
    finais: set[str] = field(default_factory=set)
    run: list[tuple[str, str]] = field(default_factory=list)

    @property
    def kernel(self) -> str:
        return self.devpath.rsplit("/", 1)[-1]

    @property
    def corrente(self) -> list[Elo]:
        return [Elo(self.kernel, "hidraw"), *self.pais]

    @property
    def acl_da_sessao(self) -> bool:
        """O `73-seat-late` pôs o builtin `uaccess` na fila: o nó ganha a ACL."""
        return ("builtin", "uaccess") in self.run


def _casa(padrao: str, valor: str) -> bool:
    """O casamento do udev: glob, com `|` separando alternativas."""
    return any(fnmatch.fnmatchcase(valor, p) for p in padrao.split("|"))


def _linhas(arquivo: Path) -> list[tuple[int, str]]:
    texto = arquivo.read_text(encoding="utf-8").replace("\\\n", " ")
    return [
        (n, linha.strip())
        for n, linha in enumerate(texto.splitlines(), start=1)
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


def _substituir(valor: str, ap: Aparelho) -> str:
    return re.sub(r"\$env\{([^}]*)\}", lambda m: ap.env.get(m.group(1), ""), valor)


def _casa_o_elo(elo: Elo, chave: str, op: str, valor: str) -> bool:
    if chave in ("KERNELS",):
        ok = _casa(valor, elo.kernel)
    elif chave == "SUBSYSTEMS":
        ok = _casa(valor, elo.subsystem)
    elif chave == "DRIVERS":
        ok = _casa(valor, elo.driver)
    else:  # ATTRS{x}
        nome = chave[6:-1]
        if nome not in elo.attrs:
            return False
        ok = _casa(valor, elo.attrs[nome])
    return ok if op == "==" else not ok


def _a_linha_casa(ap: Aparelho, termos: list[tuple[str, str, str]], existentes: set[str]) -> bool:
    de_pai: list[tuple[str, str, str]] = []
    for chave, op, valor in termos:
        if op not in ("==", "!="):
            # IMPORT é chave de CASAMENTO no udev: falhar o import é não casar.
            # Só o `cmdline` falha aqui (nenhum `nomodeset`); os outros
            # (`parent`, `builtin`) não mudam nada do que se mede.
            if chave == "IMPORT{cmdline}":
                return False
            continue
        if chave in _DE_PAI or chave.startswith("ATTRS{"):
            de_pai.append((chave, op, valor))
            continue
        if chave == "ACTION":
            ok = _casa(valor, ap.acao)
        elif chave == "KERNEL":
            ok = _casa(valor, ap.kernel)
        elif chave == "SUBSYSTEM":
            ok = _casa(valor, "hidraw")
        elif chave == "DEVPATH":
            ok = _casa(valor, ap.devpath)
        elif chave == "DRIVER":
            ok = _casa(valor, "")
        elif chave == "TAG":
            ok = any(_casa(valor, t) for t in ap.tags)
        elif chave == "TEST":
            ok = valor in existentes
        elif chave.startswith("ENV{"):
            ok = _casa(valor, ap.env.get(chave[4:-1], ""))
        elif chave.startswith("ATTR{"):
            ok = False  # o hidraw não tem os sysattrs que estas regras pedem
        else:  # pragma: no cover — chave nova numa regra: tem de ser ensinada
            raise AssertionError(f"o udev de bolso não conhece a chave {chave}{op}")
        falhou = (not ok) if op == "==" else ok
        if falhou:
            return False
    if de_pai:
        return any(
            all(_casa_o_elo(elo, c, o, v) for c, o, v in de_pai) for elo in ap.corrente
        )
    return True


def _aplicar(ap: Aparelho, termos: list[tuple[str, str, str]]) -> str | None:
    """As atribuições de uma linha que casou. Devolve o GOTO, se houver."""
    goto = None
    for chave, op, valor in termos:
        if op in ("==", "!="):
            continue
        valor = _substituir(valor, ap)
        if chave == "TAG":
            if op == "+=":
                ap.tags.add(valor)
            elif op == "-=":
                ap.tags.discard(valor)
            else:
                ap.tags = {valor}
        elif chave in ("MODE", "OWNER", "GROUP"):
            if chave in ap.finais:
                continue
            setattr(ap, {"MODE": "modo", "OWNER": "dono", "GROUP": "grupo"}[chave], valor)
            if op == ":=":
                ap.finais.add(chave)
        elif chave.startswith("ENV{"):
            ap.env[chave[4:-1]] = valor
        elif chave == "RUN" or chave.startswith("RUN{"):
            tipo = chave[4:-1] if chave.startswith("RUN{") else "program"
            ap.run.append((tipo, valor))
        elif chave == "GOTO":
            goto = valor
        # LABEL, OPTIONS, SYMLINK, IMPORT, ATTR{}=: nada que se meça aqui.
    return goto


def cadeia(raiz: Path) -> list[Path]:
    """Os arquivos que o udev leria nesta raiz, na ORDEM em que ele os roda.

    O nome decide as duas coisas, e são duas: a SOMBRA (mesmo nome: vence o
    diretório de maior prioridade) e a ORDEM (todos juntos, pelo nome,
    comparado byte a byte — `strcmp`).
    """
    por_nome: dict[str, Path] = {}
    for d in DIRETORIOS:
        pasta = raiz / d / "udev" / "rules.d"
        if not pasta.is_dir():
            continue
        for arquivo in pasta.glob("*.rules"):
            por_nome.setdefault(arquivo.name, arquivo)
    return [por_nome[nome] for nome in sorted(por_nome, key=lambda n: n.encode())]


def rodar(ap: Aparelho, raiz: Path, *, existentes: set[str] | None = None) -> Aparelho:
    """O evento inteiro: cada arquivo da cadeia, cada linha, na ordem."""
    existentes = existentes or set()
    ap.env.setdefault("MAJOR", "237")
    ap.env.setdefault("MINOR", ap.kernel.removeprefix("hidraw") or "0")
    ap.env.setdefault("SUBSYSTEM", "hidraw")
    for arquivo in cadeia(raiz):
        pulando_ate: str | None = None
        for _n, linha in _linhas(arquivo):
            termos = _TERMO.findall(linha)
            if pulando_ate is not None:
                if ("LABEL", "=", pulando_ate) in termos:
                    pulando_ate = None
                continue
            if _a_linha_casa(ap, termos, existentes):
                pulando_ate = _aplicar(ap, termos)
    return ap


# --- os aparelhos da matriz dela -------------------------------------------


def pelo_cabo(pid: str, instancia: str = "0005") -> Aparelho:
    hid = f"0003:054C:{pid.upper()}.{instancia}"
    return Aparelho(
        f"/devices/pci0000:00/0000:00:08.1/0000:0c:00.3/usb3/3-4/3-4:1.3/{hid}/hidraw/hidraw4",
        [
            Elo(hid, "hid", "playstation"),
            Elo("3-4:1.3", "usb", "usbhid"),
            Elo("3-4", "usb", "usb", {"idVendor": "054c", "idProduct": pid}),
            Elo("usb3", "usb", "usb", {"idVendor": "1d6b", "idProduct": "0003"}),
        ],
    )


def pelo_radio(pid: str, instancia: str = "000C") -> Aparelho:
    """O físico pelo rádio: o BlueZ o cria por uhid — mora em /devices/virtual."""
    hid = f"0005:054C:{pid.upper()}.{instancia}"
    return Aparelho(
        f"/devices/virtual/misc/uhid/{hid}/hidraw/hidraw6",
        [Elo(hid, "hid", "playstation"), Elo("uhid", "misc")],
    )


def o_vpad(instancia: str = "000D") -> Aparelho:
    """O controle virtual do Hefesto: bus 0003, sem pai USB, em /devices/virtual."""
    hid = f"0003:054C:0DF2.{instancia}"
    return Aparelho(
        f"/devices/virtual/misc/uhid/{hid}/hidraw/hidraw7",
        [Elo(hid, "hid", "playstation"), Elo("uhid", "misc")],
    )


FISICOS = {
    "standard-cabo": lambda: pelo_cabo("0ce6"),
    "edge-cabo": lambda: pelo_cabo("0df2"),
    "standard-radio": lambda: pelo_radio("0ce6"),
    "edge-radio": lambda: pelo_radio("0df2"),
}

#: As combinações de terceiros: a máquina dela (as duas), a do Fedora/Debian só
#: com o `steam-devices`, uma só com o `game-devices-udev`, uma sem nenhuma, e
#: as duas do Arch — onde o pacote `steam` grava a MESMA regra da Valve com o
#: nome `70-steam-input.rules` (conferência de 25/09/2026; o nome vem da
#: memória do PKGBUILD, não de uma máquina Arch medida). Nelas a regra de antes
#: perdia até SEM o `game-devices-udev`: `70-p` < `70-s`.
TERCEIROS_POR_MAQUINA = {
    "as-duas": ("60-steam-input.rules", "71-sony-controllers.rules"),
    "so-steam-devices": ("60-steam-input.rules",),
    "so-game-devices-udev": ("71-sony-controllers.rules",),
    "nenhuma": (),
    "arch-so-steam": ("70-steam-input.rules",),
    "arch-com-game-devices-udev": ("70-steam-input.rules", "71-sony-controllers.rules"),
}

#: O nome que a regra tem na máquina -> a cópia de verdade que lhe dá o conteúdo.
CONTEUDO_DE = {"70-steam-input.rules": "60-steam-input.rules"}


def montar(
    tmp: Path,
    *,
    terceiros: tuple[str, ...] = TERCEIROS_POR_MAQUINA["as-duas"],
    nome_da_regra: str | None = None,
    conteudo_da_regra: str | None = None,
    extra_etc: dict[str, str] | None = None,
    extra_usr: dict[str, str] | None = None,
) -> Path:
    """Uma máquina de mentira: o systemd e os terceiros em /usr/lib, o Hefesto em /etc.

    Como o `install_udev.sh` deixa: TODOS os assets do Hefesto em /etc (a
    regra do nó com o nome e o conteúdo que o teste pedir).
    """
    etc = tmp / "etc" / "udev" / "rules.d"
    usr = tmp / "usr/lib" / "udev" / "rules.d"
    etc.mkdir(parents=True)
    usr.mkdir(parents=True)
    for nome in ("70-uaccess.rules", "71-seat.rules", "73-seat-late.rules", *terceiros):
        shutil.copy(TERCEIROS / CONTEUDO_DE.get(nome, nome), usr / nome)
    regra = a_regra_do_no()
    for asset in sorted(ASSETS.glob("[0-9][0-9]-*.rules")):
        if asset == regra:
            continue
        shutil.copy(asset, etc / asset.name)
    (etc / (nome_da_regra or regra.name)).write_text(
        conteudo_da_regra if conteudo_da_regra is not None else regra.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    for nome, texto in (extra_etc or {}).items():
        (etc / nome).write_text(texto, encoding="utf-8")
    for nome, texto in (extra_usr or {}).items():
        (usr / nome).write_text(texto, encoding="utf-8")
    return tmp


def _a_regra_de_antes() -> str:
    """O conteúdo como a mesa dela o tinha até 25/09: `MODE=`, sem atribuição final."""
    return a_regra_do_no().read_text(encoding="utf-8").replace(
        'MODE:="0600", OWNER:="root", GROUP:="root"', 'MODE="0600", OWNER="root", GROUP="root"'
    )


def _fechado(ap: Aparelho) -> tuple[bool, str]:
    motivo = (
        f"tags={sorted(ap.tags)} modo={ap.modo} dono={ap.dono} grupo={ap.grupo} "
        f"run={ap.run}"
    )
    return (
        not ap.acl_da_sessao
        and "uaccess" not in ap.tags
        and ap.modo == "0600"
        and ap.dono == "root"
        and ap.grupo == "root",
        motivo,
    )


# ---------------------------------------------------------------------------
# 0. O udev de bolso reproduz o defeito medido — o controle positivo
# ---------------------------------------------------------------------------


class TestOUdevDeBolsoReproduzAMesaDela:
    """Uma régua que não reproduz o defeito não prova a cura.

    Com o nome de antes e as duas regras de terceiros que a máquina dela tem,
    o físico TEM de sair aberto: é o que o banco do udev dela mostrou em
    25/09 (`Q:uaccess` nos três nós que a Steam segurava).
    """

    @pytest.mark.parametrize("aparelho", sorted(FISICOS))
    def test_a_regra_de_antes_nasce_aberta_como_na_mesa_dela(
        self, tmp_path: Path, aparelho: str
    ) -> None:
        """A regra como estava instalada até 25/09: o nome 70 e o `MODE=` sem trava."""
        raiz = montar(
            tmp_path, nome_da_regra=NOME_DE_ANTES, conteudo_da_regra=_a_regra_de_antes()
        )
        ap = rodar(FISICOS[aparelho](), raiz)
        assert ap.acl_da_sessao, "o udev de bolso não reproduz a mesa dela"
        assert ap.modo == "0660"

    @pytest.mark.parametrize("aparelho", sorted(FISICOS))
    def test_so_o_nome_de_antes_ja_basta_para_a_acl_voltar(
        self, tmp_path: Path, aparelho: str
    ) -> None:
        """O `MODE:=` sozinho não cura: 0600 com a ACL da sessão abre igual.

        É a mordida escrita: o conteúdo de hoje com o nome de ontem. O modo
        fica travado em 0600, e mesmo assim a `71-sony` repõe a TAG e o
        `73-seat-late` escreve a ACL — quem cura é o LUGAR do arquivo.
        """
        raiz = montar(tmp_path, nome_da_regra=NOME_DE_ANTES)
        ap = rodar(FISICOS[aparelho](), raiz)
        assert ap.acl_da_sessao
        assert ap.modo == "0600"

    @pytest.mark.parametrize("aparelho", ["standard-cabo", "standard-radio"])
    def test_no_arch_a_regra_de_antes_perde_sem_o_game_devices_udev(
        self, tmp_path: Path, aparelho: str
    ) -> None:
        """A `70-steam-input.rules` do Arch corre DEPOIS da `70-ps5` e reabre o 0ce6.

        É o «qualquer máquina» da sprint: o defeito não era da 71-sony do Pop.
        Sem ela, só com a regra da Valve no nome do Arch, o nó nascia aberto.
        """
        raiz = montar(
            tmp_path,
            terceiros=TERCEIROS_POR_MAQUINA["arch-so-steam"],
            nome_da_regra=NOME_DE_ANTES,
            conteudo_da_regra=_a_regra_de_antes(),
        )
        assert rodar(FISICOS[aparelho](), raiz).acl_da_sessao

    def test_a_assinatura_do_banco_dela_e_uaccess_sem_seat(self, tmp_path: Path) -> None:
        """A impressão digital medida: `Q:uaccess` sem `Q:seat` no físico do rádio.

        O `71-seat.rules` só põe `seat` em quem já tem `uaccess` na hora dele.
        Pelo rádio o `60-steam-input` dá o `uaccess`, a 70 o tira ANTES da
        71-seat, e a 71-sony o devolve DEPOIS: sobra `uaccess` sem `seat`.
        """
        raiz = montar(tmp_path, nome_da_regra=NOME_DE_ANTES)
        ap = rodar(pelo_radio("0ce6"), raiz)
        assert "uaccess" in ap.tags
        assert "seat" not in ap.tags


# ---------------------------------------------------------------------------
# 1. A cura: o físico nasce fechado em qualquer máquina, e o vpad não
# ---------------------------------------------------------------------------


class TestOFisicoNasceFechadoEmQualquerMaquina:
    @pytest.mark.parametrize("evento", ["add", "change", "change-pessimista"])
    @pytest.mark.parametrize("maquina", sorted(TERCEIROS_POR_MAQUINA))
    @pytest.mark.parametrize("aparelho", sorted(FISICOS))
    def test_o_fisico_termina_0600_de_root_sem_acl(
        self, tmp_path: Path, aparelho: str, maquina: str, evento: str
    ) -> None:
        """A MORDIDA: o asset de volta ao nome 70 reprova as linhas com a 71-sony.

        O `change` (o trigger do install) roda de dois jeitos. O do udev de
        verdade (systemd ≥ 247): as tags CORRENTES começam vazias a cada
        evento, e as do evento anterior só voltam como pegajosas (`G:`), que o
        `TAG==` não lê. E o pessimista, em que o nó chega com o `uaccess` e o
        `seat` do nascimento anterior como correntes.
        """
        raiz = montar(tmp_path, terceiros=TERCEIROS_POR_MAQUINA[maquina])
        ap = FISICOS[aparelho]()
        ap.acao = evento.removesuffix("-pessimista")
        if evento == "change-pessimista":
            ap.tags = {"uaccess", "seat"}
        ok, motivo = _fechado(rodar(ap, raiz))
        assert ok, motivo

    @pytest.mark.parametrize("evento", ["add", "change"])
    @pytest.mark.parametrize("maquina", sorted(TERCEIROS_POR_MAQUINA))
    def test_o_vpad_continua_com_a_acl_da_sessao(
        self, tmp_path: Path, maquina: str, evento: str
    ) -> None:
        """O vpad é o controle que o Hefesto ENTREGA ao jogo: tem de ficar aberto.

        Também no `change` (o trigger do install), que começa sem tag corrente
        nenhuma: é a regra do nó que tem de devolvê-la, e não a lembrança do
        nascimento.
        """
        raiz = montar(tmp_path, terceiros=TERCEIROS_POR_MAQUINA[maquina])
        ap = o_vpad()
        ap.acao = evento
        ap = rodar(ap, raiz)
        assert ap.acl_da_sessao, ap.run
        assert ap.modo == "0660"

    def test_uma_regra_posterior_com_0666_nao_reabre_o_fisico(self, tmp_path: Path) -> None:
        """O `MODE:=` é final: a receita da internet não vence.

        A MORDIDA: troque `MODE:=` por `MODE=` no asset e o físico sai 0666.
        """
        raiz = montar(
            tmp_path,
            extra_etc={"99-hidraw-permissions.rules": 'KERNEL=="hidraw*", MODE="0666"\n'},
        )
        for aparelho in FISICOS.values():
            ap = rodar(aparelho(), raiz)
            assert ap.modo == "0600", ap

    def test_uma_regra_de_terceiro_entre_nos_e_o_73_seat_late_ainda_reabre(
        self, tmp_path: Path
    ) -> None:
        """O LIMITE da ordem, declarado: o `TAG` não tem atribuição final.

        Um arquivo que ordene entre a nossa e a `73-seat-late.rules` devolve o
        `uaccess` e o nó nasce aberto. Nenhuma máquina medida tem um; quem
        vigia é o doctor (`check_o_no_fisico_nasce_sem_acl`), que lê a tag
        corrente no banco do udev e nomeia a regra. Se este teste passar a
        falhar, a cura ficou MAIS forte — e a nota do asset tem de mudar junto.
        """
        regra = a_regra_do_no().name
        intruso = "73-i-intruso.rules"
        assert regra.encode() < intruso.encode() < b"73-seat-late.rules"
        raiz = montar(
            tmp_path,
            extra_usr={intruso: 'KERNEL=="hidraw*", KERNELS=="*054C:0CE6*", TAG+="uaccess"\n'},
        )
        assert rodar(pelo_radio("0ce6"), raiz).acl_da_sessao


# ---------------------------------------------------------------------------
# 2. O lugar do arquivo: depois de todo 70/71/72, antes da 73-seat-late
# ---------------------------------------------------------------------------


class TestOLugarDoArquivo:
    def test_ordena_depois_de_todo_70_71_72_e_antes_da_73_seat_late(self) -> None:
        """A posição é LEXICAL (`strcmp`), não o número — `int(prefixo) < 73` mentia.

        A régua antiga (`test_o_no_nasce_fechado.py`) reprovaria o nome certo:
        73 não é menor que 73, e mesmo assim `73-h` corre antes de `73-s`.
        """
        nome = a_regra_do_no().name.encode()
        assert nome > b"72-\xff", "a regra do nó corre antes de algum 72-* de terceiro"
        assert nome < b"73-seat-late.rules", "a regra do nó corre depois da 73-seat-late"

    def test_os_terceiros_medidos_ordenam_antes(self) -> None:
        nome = a_regra_do_no().name.encode()
        terceiros = ("60-steam-input.rules", "70-steam-input.rules", "71-sony-controllers.rules")
        for terceiro in terceiros:
            assert terceiro.encode() < nome, terceiro

    def test_o_nome_nao_colide_com_os_descontinuados(self) -> None:
        """As 73/74 do hotplug-GUI saíram em 07/2026 e o install ainda as apaga."""
        assert a_regra_do_no().name not in (
            "73-ps5-controller-hotplug.rules",
            "74-ps5-controller-hotplug-bt.rules",
        )


# ---------------------------------------------------------------------------
# 3. As combinações que os pacotes deixam — a sombra pelo nome
# ---------------------------------------------------------------------------


def _aberta() -> str:
    """A variante que os pacotes gravam em /usr/lib (a do `regra_do_no_aberta.sh`)."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        destino = Path(d) / "aberta.rules"
        subprocess.run(
            [
                "bash",
                str(RAIZ / "scripts" / "regra_do_no_aberta.sh"),
                str(a_regra_do_no()),
                str(destino),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return destino.read_text(encoding="utf-8")


class TestAsCombinacoesDosPacotes:
    def test_a_fechada_em_etc_sombreia_a_aberta_do_pacote(self, tmp_path: Path) -> None:
        """O `.deb`/`.rpm` grava a ABERTA em /usr/lib; o helper, com o broker, a FECHADA em /etc.

        Só funciona com o MESMO nome nos dois lugares.
        """
        regra = a_regra_do_no().name
        raiz = montar(tmp_path, extra_usr={regra: _aberta()})
        for aparelho in FISICOS.values():
            ok, motivo = _fechado(rodar(aparelho(), raiz))
            assert ok, motivo

    def test_so_a_aberta_do_pacote_deixa_o_fisico_aberto(self, tmp_path: Path) -> None:
        """O fail-safe de propósito: sem broker, ninguém abriria um nó fechado."""
        raiz = tmp_path
        (raiz / "usr/lib/udev/rules.d").mkdir(parents=True)
        for nome in ("70-uaccess.rules", "71-seat.rules", "73-seat-late.rules"):
            shutil.copy(TERCEIROS / nome, raiz / "usr/lib/udev/rules.d" / nome)
        destino = raiz / "usr/lib/udev/rules.d" / a_regra_do_no().name
        destino.write_text(_aberta(), encoding="utf-8")
        assert rodar(pelo_radio("0ce6"), raiz).acl_da_sessao

    def test_a_velha_que_sobrou_em_etc_nao_reabre(self, tmp_path: Path) -> None:
        """Um install de antes da troca deixa a 70 em /etc; a 73-h fala por último."""
        velha = a_regra_do_no().read_text(encoding="utf-8")
        raiz = montar(tmp_path, extra_etc={NOME_DE_ANTES: velha})
        ok, motivo = _fechado(rodar(pelo_radio("0df2"), raiz))
        assert ok, motivo

    def test_a_velha_aberta_do_pacote_antigo_nao_reabre(self, tmp_path: Path) -> None:
        """O pacote de antes gravou a 70 ABERTA em /usr/lib; a atualização pode deixá-la."""
        raiz = montar(tmp_path, extra_usr={NOME_DE_ANTES: _aberta()})
        ok, motivo = _fechado(rodar(pelo_cabo("0ce6"), raiz))
        assert ok, motivo
