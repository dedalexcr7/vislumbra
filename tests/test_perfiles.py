# SPDX-License-Identifier: GPL-3.0-or-later
"""Pruebas de ``vislumbra.perfiles``.

Siempre en una carpeta temporal (``tmp_path``): nunca tocan el ``%APPDATA%`` real.
"""

import json
import os

import pytest

from vislumbra import perfiles
from vislumbra.color import Ajuste, AjusteCanal
from vislumbra.perfiles import Configuracion, ErrorPerfil, NORMAL, Perfil, PerfilNoEncontrado


def oscuro():
    return Perfil("Oscuro", Ajuste.uniforme(0.0, 7.5, 1.7), vinculado=True)


def codigo():
    a = Ajuste(AjusteCanal(-20, 5, 1.0), AjusteCanal(-10, 5, 1.1), AjusteCanal(0, 5, 1.2), 6000)
    return Perfil("Código", a, vinculado=False)


@pytest.fixture
def conf():
    c = Configuracion()
    c.guardar(oscuro())
    c.guardar(codigo())
    return c


# --- Modelo -------------------------------------------------------------------------------------
def test_arranca_con_normal_activo_y_nada_mas():
    c = Configuracion()
    assert c.nombres() == [NORMAL] and c.activo().es_normal and c.perfiles == []
    assert c.todos()[0].ajuste == Ajuste()


def test_normal_no_se_guarda_ni_se_renombra_ni_se_borra(conf):
    with pytest.raises(ErrorPerfil, match="fijo"):
        conf.guardar(Perfil("Normal", Ajuste.uniforme(0, 0, 1.2)))
    with pytest.raises(ErrorPerfil, match="fijo"):
        conf.guardar(Perfil("normal", Ajuste()))
    with pytest.raises(ErrorPerfil, match="fijo"):
        conf.renombrar("Normal", "Otro")
    with pytest.raises(ErrorPerfil, match="fijo"):
        conf.borrar("Normal")


@pytest.mark.parametrize("nombre", ["", "   ", "x" * 41, "con\nsalto", "Normal", " NORMAL "])
def test_nombres_no_validos(conf, nombre):
    with pytest.raises(ErrorPerfil):
        conf.validar_nombre(nombre)


def test_nombres_validos_y_limpios(conf):
    assert conf.validar_nombre("  Cine  ") == "Cine"
    assert conf.validar_nombre("x" * 40) == "x" * 40


def test_nombres_unicos_sin_distinguir_mayusculas(conf):
    with pytest.raises(ErrorPerfil, match="ya existe"):
        conf.validar_nombre("oscuro")
    assert conf.validar_nombre("OSCURO", excepto="Oscuro") == "OSCURO"  # al renombrar el propio


def test_guardar_reemplaza_el_del_mismo_nombre(conf):
    conf.guardar(Perfil("oscuro", Ajuste.uniforme(0, 0, 2.0)))
    assert len(conf.perfiles) == 2
    assert conf.obtener("Oscuro").ajuste.r.gamma == 2.0


def test_guardar_rechaza_un_ajuste_que_no_se_podria_aplicar(conf):
    with pytest.raises(Exception):
        conf.guardar(Perfil("Roto", Ajuste.uniforme(0, 0, 9.0)))
    with pytest.raises(Exception):
        conf.guardar(Perfil("Ilegible", Ajuste.uniforme(-100, 0, 0.5)))
    assert conf.nombres() == [NORMAL, "Oscuro", "Código"]


def test_obtener_sin_distinguir_mayusculas_y_perfil_inexistente(conf):
    assert conf.obtener("CÓDIGO").nombre == "Código"
    with pytest.raises(PerfilNoEncontrado):
        conf.obtener("No existe")


def test_nombre_libre(conf):
    assert conf.nombre_libre() == "Perfil 1"
    conf.guardar(Perfil("Perfil 1", Ajuste()))
    assert conf.nombre_libre() == "Perfil 2"


def test_renombrar_actualiza_las_asignaciones_y_el_activo(conf):
    conf.activar("Oscuro")
    conf.asignar("mon-A", "Oscuro")
    conf.asignar("mon-B", None)
    assert conf.renombrar("Oscuro", "Noche") == "Noche"
    assert conf.perfil_activo == "Noche"
    assert conf.asignacion("mon-A") == "Noche" and conf.asignacion("mon-B") is None
    assert conf.nombres() == [NORMAL, "Noche", "Código"]
    with pytest.raises(ErrorPerfil, match="ya existe"):
        conf.renombrar("Noche", "código")


def test_borrar_pasa_los_fijos_a_activo_y_el_activo_a_normal(conf):
    conf.activar("Código")
    conf.asignar("mon-A", "Código")
    conf.asignar("mon-B", "Oscuro")
    conf.borrar("Código")
    assert conf.perfil_activo == NORMAL and conf.asignacion("mon-A") is None
    assert conf.asignacion("mon-B") == "Oscuro"
    assert conf.nombres() == [NORMAL, "Oscuro"]


def test_siguiente_da_la_vuelta(conf):
    vistos = [conf.siguiente().nombre for _ in range(4)]
    assert vistos == ["Oscuro", "Código", NORMAL, "Oscuro"]
    assert Configuracion().siguiente().es_normal  # con solo Normal se queda en Normal


def test_perfil_de_monitor_sigue_al_activo_o_es_fijo(conf):
    conf.activar("Oscuro")
    conf.asignar("mon-1", None)
    conf.asignar("mon-3", "Código")
    assert conf.perfil_de_monitor("mon-1").nombre == "Oscuro"
    assert conf.perfil_de_monitor("mon-3").nombre == "Código"
    assert conf.perfil_de_monitor("monitor-nuevo").nombre == "Oscuro"  # sin asignación: sigue al activo
    conf.activar("Normal")
    assert conf.perfil_de_monitor("mon-3").nombre == "Código"  # el fijo no cambia
    assert conf.perfil_de_monitor("mon-1").es_normal


def test_asignar_perfil_inexistente(conf):
    with pytest.raises(PerfilNoEncontrado):
        conf.asignar("mon-1", "Nada")


# --- Archivo -----------------------------------------------------------------------------------------
def test_guardar_y_leer_de_ida_y_vuelta(tmp_path, conf):
    conf.activar("Código")
    conf.asignar("mon-A", None)
    conf.asignar("mon-B", "Oscuro")
    ruta = tmp_path / "carpeta" / "config.json"
    perfiles.guardar_en(conf, ruta)
    leida, avisos = perfiles.cargar(ruta)
    assert avisos == []
    assert leida.perfiles == conf.perfiles
    assert leida.perfil_activo == "Código" and leida.monitores == {"mon-A": None, "mon-B": "Oscuro"}


def test_el_archivo_es_json_legible_con_version_1(tmp_path, conf):
    ruta = perfiles.guardar_en(conf, tmp_path / "c.json")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["version"] == 1 and [p["nombre"] for p in datos["perfiles"]] == ["Oscuro", "Código"]
    assert "Normal" not in [p["nombre"] for p in datos["perfiles"]]
    assert "Código" in ruta.read_text(encoding="utf-8")  # sin escapes ó


def test_escritura_atomica_no_deja_temporales_ni_pisa_el_archivo_si_falla(tmp_path, conf, monkeypatch):
    ruta = tmp_path / "config.json"
    perfiles.guardar_en(conf, ruta)
    antes = ruta.read_bytes()

    def falla(*_):
        raise OSError("disco lleno")

    monkeypatch.setattr(perfiles.os, "replace", falla)
    conf.guardar(Perfil("Nuevo", Ajuste()))
    with pytest.raises(OSError):
        perfiles.guardar_en(conf, ruta)
    assert ruta.read_bytes() == antes
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"]


def test_sin_archivo_arranca_con_normal_sin_avisos(tmp_path):
    c, avisos = perfiles.cargar(tmp_path / "no_existe.json")
    assert c.nombres() == [NORMAL] and avisos == []


def _cargar_texto(tmp_path, texto):
    ruta = tmp_path / "config.json"
    ruta.write_text(texto, encoding="utf-8")
    return ruta, *perfiles.cargar(ruta)


def _perfil_json(**cambios):
    d = {"nombre": "P", "vinculado": True,
         "canales": {c: {"brillo": 0, "contraste": 0, "gamma": 1.2} for c in "rgb"}, "temperatura": 6500}
    d.update(cambios)
    return {"version": 1, "perfiles": [d], "perfil_activo": "P", "monitores": {}}


@pytest.mark.parametrize("texto", [
    "esto no es json",
    "[]",
    '{"version": 2}',
    json.dumps({"version": 1, "perfiles": "no"}),
    json.dumps(_perfil_json(canales={"r": {}})),
    json.dumps(_perfil_json(nombre=5)),
    json.dumps(_perfil_json(vinculado="sí")),
    json.dumps(_perfil_json(temperatura="caliente")),
    json.dumps(_perfil_json(canales={c: {"gamma": 9.0} for c in "rgb"})),  # fuera de rango
    json.dumps(_perfil_json(temperatura=100000)),
    json.dumps(_perfil_json(canales={c: {"brillo": -100, "gamma": 0.5} for c in "rgb"})),  # ilegible
    json.dumps(_perfil_json(temperatura=3300, canales={c: {"brillo": -45} for c in "rgb"})),  # límite de Windows
    json.dumps(_perfil_json(nombre="Normal")),
    json.dumps({**_perfil_json(), "perfiles": [_perfil_json()["perfiles"][0]] * 2}),  # repetido
    '{"version": 1, "perfiles": [{"nombre": "P", "canales": {"r": {"gamma": NaN}, "g": {}, "b": {}}}]}',
])
def test_archivo_danado_se_aparta_y_se_arranca_con_normal(tmp_path, texto):
    ruta, conf, avisos = _cargar_texto(tmp_path, texto)
    assert conf.nombres() == [NORMAL] and conf.perfil_activo == NORMAL
    assert len(avisos) == 1 and "no era válida" in avisos[0] and "dañado" in avisos[0]
    assert not ruta.exists()
    copias = [p.name for p in tmp_path.iterdir()]
    assert len(copias) == 1 and copias[0].startswith("config.dañado-") and copias[0].endswith(".json")
    assert (tmp_path / copias[0]).read_text(encoding="utf-8") == texto  # el original se conserva


def test_dos_archivos_danados_no_se_pisan(tmp_path):
    for _ in range(2):
        _cargar_texto(tmp_path, "roto")
    assert len(list(tmp_path.glob("config.dañado-*.json"))) == 2


def test_perfil_activo_y_fijo_inexistentes_se_arreglan_sin_danar(tmp_path):
    d = _perfil_json()
    d["perfil_activo"] = "Borrado"
    d["monitores"] = {"m": {"asignacion": "fijo", "perfil": "Borrado"}, "n": {"asignacion": "activo"}}
    _, conf, avisos = _cargar_texto(tmp_path, json.dumps(d))
    assert avisos == [] and conf.perfil_activo == NORMAL
    assert conf.monitores == {"m": None, "n": None}


def test_perfil_vinculado_con_canales_distintos_se_unifica(tmp_path):
    d = _perfil_json()
    d["perfiles"][0]["canales"]["g"]["gamma"] = 2.0
    _, conf, avisos = _cargar_texto(tmp_path, json.dumps(d))
    assert avisos == [] and conf.obtener("P").ajuste.g.gamma == 1.2


def test_la_carpeta_por_defecto_es_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert perfiles.ruta_config() == tmp_path / "Vislumbra" / "config.json"
    assert not (tmp_path / "Vislumbra").exists()  # no se crea hasta guardar
    monkeypatch.delenv("APPDATA")
    assert perfiles.ruta_config().parts[-2:] == ("Vislumbra", "config.json")
