"""El circuito completo: ajustas fuera, se sube al repo, Hydra se queda con TUS valores.

Se prueban las dos formas de que lleguen (subirlos a mano y traerlos del repo) y,
sobre todo, la que muerde sin avisar: **recompilar el bot**. Al recompilar, el
.algo vuelve con los valores de fábrica, y si el preset no se vuelve a aplicar
Hydra pasa a gestionar con números que nadie usa — sin error, sin aviso, sin nada
que mirar.
"""
import gzip
import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.store import Store
from app.web import create_app

PRESET = """<?xml version="1.0" encoding="utf-8"?>
<ParametersRoot><Parameters>
  <Parameter Name="UseBreakEven" Value="true" />
  <Parameter Name="BreakEvenTriggerPips" Value="12" />
</Parameters></ParametersRoot>"""


def algo_bytes(nombre="Confluence Bot", be_trigger=20):
    meta = {"Types": [{"FriendlyName": nombre, "TypeName": "ConfluenceAlertBotV2",
                       "Parameters": [
        {"PropertyName": "UseBreakEven", "FriendlyName": "Usar break even",
         "GroupName": "Gestión", "DefaultValue": "false",
         "ParameterType": "System.Boolean"},
        {"PropertyName": "BreakEvenTriggerPips", "FriendlyName": "Pips para BE",
         "GroupName": "Gestión", "DefaultValue": be_trigger,
         "ParameterType": "System.Int32"}]}], "ApiVersion": 1}
    return b"algo" + b"\0" * 5 + gzip.compress(json.dumps(meta).encode()) + b"DLL" * 50


@pytest.fixture
def hydra(tmp_path, monkeypatch):
    bots = tmp_path / "cAlgo"
    (bots / "bin" / "Debug").mkdir(parents=True)
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "algo_dir", str(bots))
    cli = TestClient(create_app(Store(tmp_path / "brain.db"), None, None, None))
    return cli, bots


def importar(cli, bots, be_trigger=20):
    f = bots / "bin" / "Debug" / "Confluence Bot.algo"
    f.write_bytes(algo_bytes(be_trigger=be_trigger))
    r = cli.post("/algo/import", content=f.read_bytes(),
                 headers={"content-type": "application/octet-stream"})
    assert r.json()["ok"], r.json()
    return f


def be(cli, bot="Confluence Bot"):
    """Los pips de break-even con los que Hydra gestionaría AHORA MISMO."""
    d = cli.get(f"/manage/policy/{bot}").json()
    return (d.get("policy") or {}).get("breakeven", {}).get("trigger_pips")


def test_uploading_your_preset_changes_what_hydra_manages_with(hydra):
    """Sin esto se gestiona con 20 pips teniendo tú 12 puestos, y no salta nada."""
    cli, bots = hydra
    importar(cli, bots)
    assert be(cli) == 20                       # de fábrica

    r = cli.post("/algo/bots/Confluence Bot/preset", content=PRESET.encode())
    assert r.json()["ok"] and r.json()["n_matched"] == 2
    assert be(cli) == 12                       # el tuyo


def test_it_tells_you_what_differs_from_the_factory_values(hydra):
    cli, bots = hydra
    importar(cli, bots)
    d = cli.post("/algo/bots/Confluence Bot/preset", content=PRESET.encode()).json()
    assert [c["name"] for c in d["changed"]] == ["UseBreakEven", "BreakEvenTriggerPips"]


def test_a_preset_from_another_bot_is_rejected_as_suspect(hydra):
    cli, bots = hydra
    importar(cli, bots)
    otro = PRESET.replace("UseBreakEven", "OtraCosa").replace(
        "BreakEvenTriggerPips", "YOtraMas")
    d = cli.post("/algo/bots/Confluence Bot/preset", content=otro.encode()).json()
    assert d["suspect"] and d["n_matched"] == 0


def test_garbage_is_refused_instead_of_wiping_your_settings(hydra):
    cli, bots = hydra
    importar(cli, bots)
    cli.post("/algo/bots/Confluence Bot/preset", content=PRESET.encode())
    r = cli.post("/algo/bots/Confluence Bot/preset", content=b"esto no es un preset")
    assert r.status_code == 400
    assert be(cli) == 12, "un archivo malo se llevó por delante los valores buenos"


def test_recompiling_the_bot_does_not_lose_your_values(hydra):
    """EL caso que muerde. Tocas el bot en cTrader, se recompila, el .algo vuelve
    con los de fábrica — y tus 12 pips tienen que seguir ahí."""
    cli, bots = hydra
    f = importar(cli, bots)
    cli.post("/algo/bots/Confluence Bot/preset", content=PRESET.encode())
    assert be(cli) == 12

    f.write_bytes(algo_bytes(be_trigger=30))   # recompilado, otro valor de fábrica
    assert cli.post("/algo/refresh").json()["ok"]
    assert be(cli) == 12, "el recompilado se llevó tus valores"


def test_a_preset_next_to_the_algo_is_picked_up_by_itself(hydra):
    """Es lo que permite que vengan del REPO: guardas el .cbotset al lado, haces
    pull, y Hydra los recoge sin que subas nada."""
    cli, bots = hydra
    f = bots / "bin" / "Debug" / "Confluence Bot.algo"
    f.write_bytes(algo_bytes())
    (bots / "Confluence Bot.cbotset").write_text(PRESET)
    assert cli.post("/algo/scan").json()["ok"]
    assert be(cli) == 12


def test_removing_the_preset_goes_back_to_the_factory_values(hydra):
    cli, bots = hydra
    importar(cli, bots)
    cli.post("/algo/bots/Confluence Bot/preset", content=PRESET.encode())
    assert be(cli) == 12
    assert cli.delete("/algo/bots/Confluence Bot/preset").json()["ok"]
    assert be(cli) == 20


def test_pull_brings_the_presets_from_the_repo(hydra, tmp_path):
    """El circuito entero: en otra conversación se ajusta el bot y se sube; aquí se
    pulsa actualizar y Hydra se queda con esos valores."""
    cli, bots = hydra
    if not subprocess.run(["git", "--version"], capture_output=True).returncode == 0:
        pytest.skip("sin git")
    importar(cli, bots)
    assert be(cli) == 20

    # un repo remoto de mentira con el preset dentro
    remoto = tmp_path / "remoto"
    subprocess.run(["git", "init", "-q", "--bare", str(remoto)], check=True)
    trabajo = tmp_path / "trabajo"
    subprocess.run(["git", "clone", "-q", str(remoto), str(trabajo)], check=True)
    (trabajo / "Confluence Bot.cbotset").write_text(PRESET)
    for cmd in (["add", "-A"],
                ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "preset"],
                ["push", "-q", "origin", "HEAD:master"]):
        subprocess.run(["git", "-C", str(trabajo)] + cmd, check=True)

    # la carpeta de bots ES el repo
    subprocess.run(["git", "clone", "-q", str(remoto), str(bots / "repo")], check=True)
    algo = bots / "repo" / "Confluence Bot.algo"
    algo.write_bytes(algo_bytes())
    from app.config import settings as s
    s.algo_dir = str(bots / "repo")
    cli.post("/algo/import", content=algo.read_bytes(),
             headers={"content-type": "application/octet-stream"})

    r = cli.post("/algo/pull").json()
    assert r["ok"], r
    assert be(cli) == 12, "el pull no trajo tus valores"
