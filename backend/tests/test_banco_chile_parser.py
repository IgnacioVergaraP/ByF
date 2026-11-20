"""Regresiones de cartolas: alinear por posición, sin inferir el tipo por texto."""
import io
import unittest
from datetime import date
from pathlib import Path

import fitz

from app.modules.conciliacion.parsers import BancoChileParser


PDF_CARTOLA = Path(__file__).resolve().parents[2] / "data" / "CartolaEmitida.pdf"


class BancoChileParserTest(unittest.TestCase):
    def parse_pdf(self, data=None):
        return BancoChileParser().parse(io.BytesIO(
            PDF_CARTOLA.read_bytes() if data is None else data
        ))

    def test_cartola_completa_conserva_fechas_descripciones_y_montos(self):
        cartola = self.parse_pdf()
        esperados = [
            (1, "Cristina Andrea Valdov", 3240),
            (2, "VICENTE IGNACIO SEPULV", 1640),
            (3, "COMERCIAL E INDUSTRIAL", 3533710),
            (4, "FERNANDEZ DELGADO CHRI", 20000),
            (4, "SERVICIOS GASTRONOMICO", 2486256),
            (4, "CONSTRUCTORA, INMOBILI", 8914371),
            (4, "FERNANDEZ DELGADO CHRI", 20000),
            (7, "Sandra Pamela Salazar", 80000),
            (7, "COMERCIAL PODECA LIMIT", 1882714),
            (7, "DEPOSITO EN EFECTIVO", 68390),
            (8, "EL PAPAS SPA", 2390980),
            (9, "CLAUDIA ANDREA JARA SI", 30000),
            (10, "WEP CERVECERA SPA", 3328267),
            (11, "Claudio Enrique Ruiz G", 1057760),
            (11, "RICHARD FABIAN SILVA R", 15470),
            (11, "SOCIEDAD COMERCIAL DE", 2124938),
            (11, "PAGO:PROVEEDORES 0898072002", 6768724),
            (11, "ANDRES JONATHAN VIDAL", 80000),
            (11, "RUKACURA SPA", 1929710),
            (14, "INVERSIONES XKISITO SP", 1205890),
            (14, "INVERSIONES XKISITO SP", 1200000),
            (15, "PIZZERIA HENRIQUEZ Y P", 1488390),
            (15, "PIZZERIA HENRIQUEZ Y P", 1500000),
            (17, "Sandra Pamela Salazar", 80000),
            (17, "CLAUDIA ANDREA JARA SI", 30000),
            (21, "COMERCIAL ENERFIT SPA", 940127),
            (21, "WEP CERVECERA SPA", 4000000),
            (24, "CLAUDIA ANDREA JARA SI", 30000),
            (30, "CONSTRUCTORA, INMOBILI", 7500000),
            (30, "INMOBILIARIA E INVERSI", 9000000),
        ]
        self.assertEqual(cartola.errores, [])
        self.assertEqual(len(cartola.movimientos), len(esperados))
        for movimiento, (dia, detalle, monto) in zip(cartola.movimientos, esperados):
            with self.subTest(dia=dia, detalle=detalle, monto=monto):
                self.assertEqual(movimiento.fecha, date(2026, 9, dia))
                self.assertIn(detalle, movimiento.descripcion_original)
                self.assertEqual(movimiento.monto, monto)
        self.assertEqual(sum(m.monto for m in cartola.movimientos), 61710577)
        self.assertEqual([sum(m.pagina_origen == p for m in cartola.movimientos)
                          for p in (1, 2, 3)], [13, 10, 7])

    def test_metadatos_y_resumen_coinciden_con_la_cartola(self):
        cartola = self.parse_pdf()
        self.assertEqual(cartola.numero_cuenta, "8280003905")
        self.assertEqual(cartola.numero_cartola, "9")
        self.assertEqual(cartola.periodo_desde, date(2026, 8, 31))
        self.assertEqual(cartola.periodo_hasta, date(2026, 9, 30))
        self.assertEqual(cartola.total_abonos_informado, 61710577)
        self.assertEqual(cartola.total_cargos_informado, 64370141)
        self.assertEqual(cartola.saldo_inicial_informado, 4178082)
        self.assertEqual(cartola.saldo_final_informado, 1518518)
        self.assertEqual(cartola.saldo_inicial_informado
                         + cartola.total_abonos_informado
                         - cartola.total_cargos_informado,
                         cartola.saldo_final_informado)

    def test_extrae_cargos_y_su_suma_coincide_con_el_resumen(self):
        cartola = self.parse_pdf()
        self.assertEqual(len(cartola.cargos), 56)
        self.assertEqual(
            sum(m.monto for m in cartola.cargos),
            cartola.total_cargos_informado,
        )

    def test_descripciones_desconocidas_no_cambian_tipo_ni_alineacion(self):
        with fitz.open(PDF_CARTOLA) as doc:
            for pagina, original, reemplazo in (
                (1, "PAGO:PROVEEDORES 0898072002", "ABONO SIN PREFIJO"),
                (0, "TRASPASO A:Catalina Seguel Parra", "TRASPASO DE:FALSO"),
            ):
                page = doc[pagina]
                rect = page.search_for(original)[0]
                page.add_redact_annot(rect, fill=(1, 1, 1))
                page.apply_redactions()
                page.insert_text((rect.x0, rect.y1 - 2), reemplazo, fontsize=7)
            cartola = self.parse_pdf(doc.tobytes())
        self.assertEqual(cartola.errores, [])
        self.assertEqual(len(cartola.movimientos), 30)
        self.assertEqual(sum(m.monto for m in cartola.movimientos), 61710577)
        desconocido = next(m for m in cartola.movimientos
                           if "ABONO SIN PREFIJO" in m.descripcion_original)
        self.assertEqual(desconocido.monto, 6768724)
        self.assertFalse(any("FALSO" in m.descripcion_original
                             for m in cartola.movimientos))

    def test_pdf_invalido_devuelve_error(self):
        cartola = self.parse_pdf(b"no es un PDF")
        self.assertTrue(cartola.errores)
        self.assertEqual(cartola.movimientos, [])


if __name__ == "__main__":
    unittest.main()
