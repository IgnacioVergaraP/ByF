"""Regresiones del adaptador que confirma cambios a través de Supabase."""
from io import BytesIO
import os
import unittest
from unittest.mock import patch

from openpyxl import Workbook

from app import create_app
from app.core.database import db
from app.core.supabase_data_api import ErrorDataAPI


class SupabasePersistenciaTest(unittest.TestCase):
    def setUp(self):
        configuracion = {
            "FLASK_ENV": "production",
            "APP_USERNAME": "prueba",
            "APP_PASSWORD": "local",
        }
        with patch.dict(os.environ, configuracion):
            with patch("app.core.supabase_persistencia.SupabaseDataAPI") as cliente_api:
                self.api = cliente_api.return_value
                self.app = create_app()
        self.cliente = self.app.test_client()
        self.api.rpc.side_effect = self.rpc
        self.guardado = None
        self.conflicto = False

    def rpc(self, nombre, parametros):
        if nombre == "datos_conciliacion":
            return {"revision": 7, "filas": {tabla.name: [] for tabla in db.metadata.tables.values()}}
        if nombre == "guardar_conciliacion":
            self.guardado = parametros
            if self.conflicto:
                raise ErrorDataAPI(500, "40001")
            return 8
        raise AssertionError(nombre)

    def importar_maestro(self):
        wb = Workbook()
        wb.active.append(["CC", "PROPIEDAD", "ARRENDATARIO", "CONCEPTO"])
        wb.active.append(["YORK", "Local 1", "Arrendatario A", "Arriendo"])
        contenido = BytesIO()
        wb.save(contenido)
        contenido.seek(0)
        return self.cliente.post(
            "/api/conciliacion/maestro/import",
            auth=("prueba", "local"),
            data={"file": (contenido, "maestro.xlsx")},
        )

    def test_confirma_todos_los_vinculos_en_una_llamada(self):
        respuesta = self.importar_maestro()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json["imported_rows"], 1)
        self.assertEqual(self.api.rpc.call_count, 2)
        self.assertEqual(self.guardado["p_revision"], 7)
        cambios = self.guardado["p_cambios"]
        self.assertEqual(
            [cambio["tabla"] for cambio in cambios],
            ["centros_costo", "propiedades", "arrendatarios", "propiedades_arrendatarios",
             "conceptos", "propiedades_conceptos"],
        )
        self.assertEqual(cambios[1]["datos"]["centro_costo_id"], cambios[0]["id"])
        self.assertEqual(cambios[3]["datos"]["propiedad_id"], cambios[1]["id"])

    def test_conflicto_de_revision_devuelve_409(self):
        self.conflicto = True
        with self.assertLogs(self.app.logger, level="WARNING"):
            respuesta = self.importar_maestro()
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(self.api.rpc.call_count, 2)
        self.assertTrue(respuesta.cache_control.no_store)

    def test_consulta_solo_carga_y_no_escribe(self):
        respuesta = self.cliente.get("/api/conciliacion/centros-costo", auth=("prueba", "local"))
        self.assertEqual(respuesta.json, {"total": 0, "items": []})
        self.api.rpc.assert_called_once_with("datos_conciliacion", {})
