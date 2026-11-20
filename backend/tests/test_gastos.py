"""Regresiones del flujo de gastos y sus reglas persistentes."""
import unittest
import hashlib
from datetime import date
from io import BytesIO
from unittest.mock import patch

from flask import Flask

from app.core.database import db
from app.modules.conciliacion.models import (
    Cartola, CentroCosto, CuentaBancaria, GastoAsociacion, GastoEgreso,
    GastoDocumento, GastoRegla,
)
from app.modules.conciliacion.services.gastos_service import GastosService
from app.modules.conciliacion.services.cartola_service import CartolaService
from app.modules.conciliacion.routes import bp
from app.modules.conciliacion.parsers.base_factura_parser import ParsedFactura
from app.modules.conciliacion.parsers.base_parser import ParsedCartola, ParsedMovimiento


class GastosServiceTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
        db.init_app(app)
        self.context = app.app_context()
        self.context.push()
        app.register_blueprint(bp, url_prefix="/api/conciliacion")
        db.create_all()
        self.client = app.test_client()

        self.centro = CentroCosto(
            codigo="ENTIDAD-1", nombre_original="Entidad 1", nombre_normalizado="entidad 1",
        )
        self.otro_centro = CentroCosto(
            codigo="ENTIDAD-2", nombre_original="Entidad 2", nombre_normalizado="entidad 2",
        )
        cuenta = CuentaBancaria(banco="Banco de Chile", numero_cuenta="123")
        db.session.add_all([self.centro, self.otro_centro, cuenta])
        db.session.flush()
        self.cartola = Cartola(
            cuenta_id=cuenta.id, centro_costo_id=self.centro.id,
            archivo_nombre="cartola.pdf", archivo_hash="cartola-1",
        )
        self.otra_cartola = Cartola(
            cuenta_id=cuenta.id, centro_costo_id=self.otro_centro.id,
            archivo_nombre="cartola-2.pdf", archivo_hash="cartola-2",
        )
        db.session.add_all([self.cartola, self.otra_cartola])
        db.session.flush()
        self.indice_egreso = 0
        self.egreso = self.crear_egreso(self.cartola.id, self.centro.id)
        db.session.commit()
        self.service = GastosService()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def crear_egreso(self, cartola_id, centro_id, descripcion="PAGO SERVICIO EMPRESA NORTE"):
        self.indice_egreso += 1
        egreso = GastoEgreso(
            cartola_id=cartola_id,
            centro_costo_id=centro_id,
            fecha=date(2026, 9, 10),
            descripcion_original=descripcion,
            descripcion_normalizada=descripcion.lower(),
            monto=125000,
            pagina_origen=1,
            orden_en_pagina=1,
            huella_movimiento=f"{cartola_id}-{self.indice_egreso}-{descripcion}",
        )
        db.session.add(egreso)
        db.session.flush()
        return egreso

    def test_categoria_fija_requiere_subcategoria_de_catalogo(self):
        with self.assertRaises(ValueError):
            self.service.clasificar(
                self.egreso, "fijo", "Operaciones", "No existe", False,
            )
        self.assertIsNone(self.egreso.tipo_gasto)

    def test_variable_no_requiere_categoria_y_regla_queda_limitada_a_entidad(self):
        self.service.clasificar(self.egreso, "variable", None, None, True)
        db.session.commit()
        self.assertEqual(GastoRegla.query.count(), 1)

        misma_entidad = self.crear_egreso(
            self.cartola.id, self.centro.id, "PAGO SERVICIO EMPRESA NORTE"
        )
        self.service._aplicar_regla(misma_entidad)
        otra_entidad = self.crear_egreso(
            self.otra_cartola.id, self.otro_centro.id, "PAGO SERVICIO EMPRESA NORTE"
        )
        self.service._aplicar_regla(otra_entidad)
        self.assertEqual(misma_entidad.tipo_gasto, "variable")
        self.assertEqual(misma_entidad.clasificacion_origen, "automatica")
        self.assertIsNone(otra_entidad.tipo_gasto)

    def test_corregir_clasificacion_actualiza_regla_solo_si_se_solicita(self):
        self.service.clasificar(
            self.egreso, "fijo", "Operaciones", "Servicio de aseo", True,
        )
        regla = GastoRegla.query.one()
        self.service.clasificar(self.egreso, "variable", None, None, False)
        self.assertEqual(regla.tipo_gasto, "fijo")
        self.service.clasificar(self.egreso, "variable", None, None, True)
        self.assertEqual(regla.tipo_gasto, "variable")
        self.assertIsNone(regla.categoria)

    def test_coincidencia_parcial_es_sugerencia_no_clasificacion(self):
        self.service.clasificar(
            self.egreso, "fijo", "Operaciones", "Servicio de aseo", True,
        )
        db.session.flush()
        similar = self.crear_egreso(
            self.cartola.id, self.centro.id, "PAGO SERVICIO EMPRESA NORTE SUCURSAL"
        )
        self.service._aplicar_regla(similar)
        self.assertIsNone(similar.tipo_gasto)
        self.assertEqual(similar.sugerencia_tipo, "fijo")
        self.assertIsNotNone(similar.sugerencia_regla_id)

    def test_documento_sugerido_no_se_considera_pagado_hasta_confirmar(self):
        factura = ParsedFactura(
            folio="123", rut_emisor="76123456-7", fecha_emision=date(2026, 9, 10),
            neto=105042, iva=19958, total=125000,
        )
        with patch(
            "app.modules.conciliacion.parsers.factura_chile_parser.FacturaChileParser.parse",
            return_value=factura,
        ):
            documento, duplicada = self.service.subir_documento(
                self.centro.id, "factura.pdf", b"contenido", "application/pdf",
            )
        self.assertFalse(duplicada)
        self.assertEqual(
            self.service.egreso_dict(self.egreso)["estado_conciliacion"], "sugerido",
        )
        self.assertEqual(
            self.service.listar_documentos()[0]["estado"], "pendiente_pago",
        )
        asociacion = GastoAsociacion.query.filter_by(
            egreso_id=self.egreso.id, documento_id=documento.id,
        ).one()
        asociacion.estado = "confirmada"
        db.session.commit()
        self.assertEqual(
            self.service.egreso_dict(self.egreso)["estado_conciliacion"], "conciliado",
        )
        self.assertEqual(self.service.listar_documentos()[0]["estado"], "pagado")

    def test_reimportar_documento_no_duplica_en_la_misma_entidad(self):
        contenido = b"respaldo"
        factura = ParsedFactura(folio="123", rut_emisor="76123456-7", total=125000)
        with patch(
            "app.modules.conciliacion.parsers.factura_chile_parser.FacturaChileParser.parse",
            return_value=factura,
        ):
            _, duplicada = self.service.subir_documento(
                self.centro.id, "uno.pdf", contenido, "application/pdf",
            )
            _, segunda_duplicada = self.service.subir_documento(
                self.centro.id, "otro-nombre.pdf", contenido, "application/pdf",
            )
            _, otra_entidad_duplicada = self.service.subir_documento(
                self.otro_centro.id, "otro.pdf", contenido, "application/pdf",
            )
        self.assertFalse(duplicada)
        self.assertTrue(segunda_duplicada)
        self.assertFalse(otra_entidad_duplicada)
        self.assertEqual(GastoDocumento.query.count(), 2)

    @staticmethod
    def excel_bytes(filas):
        from openpyxl import Workbook
        libro = Workbook()
        hoja = libro.active
        hoja.append(['FECHA', 'DESTINATARIO', 'RUT', 'BANCO', 'ID TRANSACCION', 'ESTADO', 'MONTO', 'OBSERVACION'])
        for nombre, monto in filas:
            hoja.append([date(2026, 9, 10), nombre, '123-4', 'Banco', 123, 'Aceptada', monto, 'Sueldo'])
        salida = BytesIO()
        libro.save(salida)
        return salida.getvalue()

    def cargar_excel(self, filas):
        contenido = self.excel_bytes(filas)
        respuesta = self.client.post('/api/conciliacion/gastos/documentos', data={
            'file': (BytesIO(contenido), 'gastos.xlsx'), 'centro_costo_id': self.centro.id,
        })
        self.assertEqual(respuesta.status_code, 200, respuesta.get_json())
        return respuesta.get_json(), contenido

    def test_excel_monto_unico_concilia_automaticamente_y_descarga_original(self):
        resultado, contenido = self.cargar_excel([('Empresa Norte', 125000)])
        self.assertEqual(resultado['conciliados'], 1)
        self.assertEqual(resultado['cantidad_gastos'], 1)
        documento = self.service.listar_documentos()[0]
        self.assertEqual(documento['destinatario'], 'Empresa Norte')
        self.assertEqual(documento['fila'], 2)
        self.assertEqual(documento['estado'], 'pagado')
        descarga = self.client.get(f"/api/conciliacion/gastos/documentos/{documento['id']}/descargar")
        self.assertEqual(descarga.data, contenido)

    def test_excel_montos_repetidos_sugiere_nombre_y_requiere_aprobacion(self):
        self.egreso.descripcion_original = 'TRANSFERENCIA SILVA RUIZ RÍCHARD'
        otro = self.crear_egreso(self.cartola.id, self.centro.id, 'PAGO ANA PEREZ')
        db.session.commit()
        resultado, _ = self.cargar_excel([('Richard Silva Ruiz', 125000), ('Ana Perez', 125000)])
        self.assertEqual(resultado['conciliados'], 0)
        self.assertEqual(resultado['pendientes_aprobacion'], 2)
        self.assertEqual(GastoAsociacion.query.count(), 2)
        asociacion = GastoAsociacion.query.filter_by(egreso_id=self.egreso.id).one()
        self.assertEqual(asociacion.estado, 'sugerida')
        confirmar = self.client.post(f'/api/conciliacion/gastos/asociaciones/{asociacion.id}/confirmar')
        self.assertEqual(confirmar.status_code, 200)
        self.assertEqual(self.service.egreso_dict(self.egreso)['estado_conciliacion'], 'conciliado')
        self.assertEqual(self.service.egreso_dict(otro)['estado_conciliacion'], 'sugerido')

    def test_excel_duplicados_sin_nombre_no_asigna_por_orden(self):
        self.crear_egreso(self.cartola.id, self.centro.id, 'TRANSFERENCIA GENERICA')
        db.session.commit()
        resultado, _ = self.cargar_excel([('Richard Silva', 125000), ('Ana Perez', 125000)])
        self.assertEqual(resultado['sin_coincidencia'], 2)
        self.assertEqual(GastoAsociacion.query.count(), 0)

    def test_excel_dos_filas_un_egreso_no_concilia_automaticamente(self):
        resultado, _ = self.cargar_excel([('Empresa Norte', 125000), ('Empresa Norte', 125000)])
        self.assertEqual(resultado['conciliados'], 0)
        self.assertEqual(resultado['pendientes_aprobacion'], 2)
        asociaciones = GastoAsociacion.query.all()
        self.service.asociar(asociaciones[0].egreso_id, asociaciones[0].documento_id, True)
        self.assertEqual(GastoAsociacion.query.count(), 1)
        otro_documento = next(d for d in self.service.listar_documentos()
                              if d['id'] != asociaciones[0].documento_id)
        with self.assertRaises(ValueError):
            self.service.asociar(self.egreso.id, otro_documento['id'], True)

    def test_excel_reimportacion_mismo_archivo_otro_nombre_no_duplica(self):
        _, contenido = self.cargar_excel([('Empresa Norte', 125000)])
        resultado = self.service.importar_excel(self.centro.id, 'renombrado.xlsx', contenido)
        self.assertTrue(resultado['duplicada'])
        self.assertEqual(GastoDocumento.query.count(), 1)
        self.assertEqual(GastoAsociacion.query.count(), 1)

    def test_excel_no_cruza_entidades_ni_fechas_lejanas(self):
        self.egreso.fecha = date(2025, 1, 1)
        self.crear_egreso(self.otra_cartola.id, self.otro_centro.id)
        db.session.commit()
        resultado, _ = self.cargar_excel([('Empresa Norte', 125000)])
        self.assertEqual(resultado['sin_coincidencia'], 1)
        self.assertEqual(GastoAsociacion.query.count(), 0)

    def test_excel_antes_de_cartola_se_concilia_al_crear_cargos(self):
        resultado, _ = self.cargar_excel([('Nuevo proveedor', 123456)])
        self.assertEqual(resultado['sin_coincidencia'], 1)
        self.service.crear_cargos(self.cartola.id, self.centro.id, [ParsedMovimiento(
            fecha=date(2026, 9, 10), descripcion_original='TRANSFERENCIA NUEVO PROVEEDOR',
            depositante_original=None, monto=123456, pagina_origen=2, orden_en_pagina=1,
        )])
        db.session.commit()
        self.assertEqual(GastoAsociacion.query.one().estado, 'confirmada')

    def test_excel_rechaza_pdf_y_archivo_invalido(self):
        for nombre, contenido in [('gasto.pdf', b'pdf'), ('gasto.xlsx', b'invalido')]:
            respuesta = self.client.post('/api/conciliacion/gastos/documentos', data={
                'file': (BytesIO(contenido), nombre), 'centro_costo_id': self.centro.id,
            })
            self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(GastoDocumento.query.count(), 0)

    def test_excel_fila_invalida_no_guarda_importacion_parcial(self):
        respuesta = self.client.post('/api/conciliacion/gastos/documentos', data={
            'file': (BytesIO(self.excel_bytes([('Empresa Norte', 125000), ('Ana', -10)])), 'gastos.xlsx'),
            'centro_costo_id': self.centro.id,
        })
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('fila 3', respuesta.get_json()['error'])
        self.assertEqual(GastoDocumento.query.count(), 0)

    def test_excel_confirmacion_manual_rechaza_monto_distinto(self):
        self.cargar_excel([('Empresa Norte', 123456)])
        documento = self.service.listar_documentos()[0]
        respuesta = self.client.post(f'/api/conciliacion/gastos/{self.egreso.id}/asociaciones',
            json={'documento_id': documento['id'], 'confirmar': True})
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(GastoAsociacion.query.count(), 0)

    def test_listar_archivos_filtra_entidad(self):
        self.cargar_excel([('Empresa Norte', 125000)])
        self.crear_egreso(self.otra_cartola.id, self.otro_centro.id)
        db.session.commit()
        respuesta = self.client.get('/api/conciliacion/gastos/archivos',
                                    query_string={'centro_costo_id': self.centro.id})
        datos = respuesta.get_json()
        self.assertEqual(len(datos['cartolas']), 1)
        self.assertEqual(datos['cartolas'][0]['id'], self.cartola.id)
        self.assertEqual(datos['excels'][0]['cantidad'], 1)

    def test_borrar_excel_elimina_todas_filas_y_conciliaciones_permite_recargar(self):
        from app.modules.conciliacion.models import GastoExcel, GastoExcelFila
        resultado, contenido = self.cargar_excel([('Empresa Norte', 125000), ('Otro', 111)])
        otro = self.service.importar_excel(self.otro_centro.id, 'otro.xlsx', contenido)
        respuesta = self.client.delete(f"/api/conciliacion/gastos/excels/{resultado['id']}")
        self.assertEqual(respuesta.status_code, 200, respuesta.get_json())
        self.assertEqual(respuesta.get_json()['cantidad_eliminada'], 2)
        self.assertIsNone(db.session.get(GastoExcel, resultado['id']))
        self.assertEqual(GastoExcelFila.query.count(), 2)  # Conserva la otra entidad.
        self.assertEqual(GastoDocumento.query.filter_by(centro_costo_id=self.centro.id).count(), 0)
        self.assertIsNotNone(db.session.get(GastoExcel, otro['id']))
        self.assertEqual(GastoAsociacion.query.count(), 0)
        self.assertIsNotNone(db.session.get(GastoEgreso, self.egreso.id))
        recarga = self.service.importar_excel(self.centro.id, 'gastos.xlsx', contenido)
        self.assertFalse(recarga['duplicada'])
        self.assertEqual(recarga['conciliados'], 1)

    def test_borrar_cartola_solo_gastos_conserva_abonos_y_excel(self):
        from app.modules.conciliacion.models import MovimientoBancario
        self.cargar_excel([('Empresa Norte', 125000)])
        abono = MovimientoBancario(cartola_id=self.cartola.id, centro_costo_id=self.centro.id,
            fecha=date(2026, 9, 10), descripcion_original='ABONO', monto=1000,
            pagina_origen=1, orden_en_pagina=1, huella_movimiento='abono-prueba')
        db.session.add(abono)
        otro_egreso = self.crear_egreso(self.otra_cartola.id, self.otro_centro.id)
        db.session.commit()
        cartola_id, abono_id, egreso_id = self.cartola.id, abono.id, self.egreso.id
        respuesta = self.client.delete(f'/api/conciliacion/gastos/cartolas/{cartola_id}')
        self.assertEqual(respuesta.status_code, 200, respuesta.get_json())
        self.assertTrue(respuesta.get_json()['conserva_abonos'])
        db.session.expire_all()
        self.assertIsNone(db.session.get(GastoEgreso, egreso_id))
        self.assertIsNotNone(db.session.get(MovimientoBancario, abono_id))
        self.assertIsNotNone(db.session.get(Cartola, cartola_id))
        self.assertIsNotNone(db.session.get(GastoEgreso, otro_egreso.id))
        self.assertEqual(GastoAsociacion.query.count(), 0)
        self.assertEqual(self.service.listar_documentos()[0]['estado'], 'pendiente_pago')

    def test_borrar_cartola_sin_abonos_elimina_cartola_y_cargos(self):
        cartola_id = self.cartola.id
        respuesta = self.client.delete(f'/api/conciliacion/gastos/cartolas/{cartola_id}')
        self.assertEqual(respuesta.status_code, 200, respuesta.get_json())
        self.assertFalse(respuesta.get_json()['conserva_abonos'])
        self.assertIsNone(db.session.get(Cartola, cartola_id))
        self.assertEqual(GastoEgreso.query.count(), 0)

    def test_borrar_archivo_inexistente_no_cambia_datos(self):
        for tipo in ('cartolas', 'excels'):
            respuesta = self.client.delete(f'/api/conciliacion/gastos/{tipo}/no-existe')
            self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(GastoEgreso.query.count(), 1)

    def test_api_revertir_asociacion_deja_documento_pendiente_de_pago(self):
        documento = GastoDocumento(
            centro_costo_id=self.centro.id,
            archivo_nombre="respaldo.pdf",
            archivo_hash="respaldo-1",
            content_type="application/pdf",
            contenido=b"pdf",
        )
        db.session.add(documento)
        db.session.commit()
        asociacion = GastosService.asociar(
            self.egreso.id, documento.id, confirmar=True,
        )

        respuesta = self.client.delete(
            f"/api/conciliacion/gastos/asociaciones/{asociacion.id}"
        )

        self.assertEqual(respuesta.status_code, 200)
        egreso = self.client.get("/api/conciliacion/gastos").get_json()["items"][0]
        self.assertEqual(egreso["estado_conciliacion"], "sin_documento")
        documento_actualizado = self.client.get(
            "/api/conciliacion/gastos/documentos"
        ).get_json()["items"][0]
        self.assertEqual(documento_actualizado["estado"], "pendiente_pago")
        self.assertEqual(documento_actualizado["asociaciones"], [])

    def test_api_revertir_clasificacion_deja_egreso_sin_clasificar(self):
        self.service.clasificar(self.egreso, "variable", None, None, True)
        db.session.commit()

        respuesta = self.client.delete(
            f"/api/conciliacion/gastos/{self.egreso.id}/clasificacion"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.get_json()["tipo_gasto"])
        self.assertIsNone(respuesta.get_json()["categoria"])
        self.assertIsNone(respuesta.get_json()["subcategoria"])
        self.assertEqual(GastoRegla.query.count(), 1)

    def test_reimportar_cartola_existente_completa_cargos_que_faltaban(self):
        data = b"cartola previamente importada"
        db.session.delete(self.egreso)
        self.cartola.archivo_hash = hashlib.sha256(data).hexdigest()
        db.session.commit()
        cargo = ParsedMovimiento(
            fecha=date(2026, 9, 10),
            descripcion_original="PAGO SERVICIO EMPRESA NORTE",
            depositante_original=None,
            monto=125000,
            pagina_origen=1,
            orden_en_pagina=1,
        )
        parsed = ParsedCartola(
            banco="Banco de Chile",
            numero_cuenta="123",
            numero_cartola="1",
            periodo_desde=None,
            periodo_hasta=date(2026, 9, 30),
            total_abonos_informado=0,
            total_cargos_informado=125000,
            saldo_inicial_informado=None,
            saldo_final_informado=None,
            cargos=[cargo],
        )
        with patch(
            "app.modules.conciliacion.services.cartola_service.BancoChileParser.parse",
            return_value=parsed,
        ):
            resultado = CartolaService().import_pdf(
                BytesIO(data), "cartola.pdf", self.centro.id,
            )
        self.assertTrue(resultado.duplicada)
        self.assertEqual(resultado.cantidad_cargos, 1)
        self.assertEqual(GastoEgreso.query.filter_by(cartola_id=self.cartola.id).count(), 1)


if __name__ == "__main__":
    unittest.main()
