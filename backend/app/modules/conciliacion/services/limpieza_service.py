"""Servicio de limpieza selectiva de registros."""
from dataclasses import dataclass, field

from app.core.database import db
from app.modules.conciliacion.models import (
    AplicacionPago,
    AsociacionDepositante,
    AsociacionFacturaPropiedad,
    AsociacionMovimiento,
    Cartola,
    CuentaBancaria,
    DetalleFactura,
    Factura,
    HistorialAplicacionPago,
    HistorialAsociacion,
    HistorialAsociacionFactura,
    IdentidadTributaria,
    ImportacionFactura,
    MovimientoBancario,
)


@dataclass
class LimpiezaResult:
    ok: bool = False
    eliminados: dict = field(default_factory=dict)
    errores: list[str] = field(default_factory=list)


class LimpiezaService:
    def limpiar(
        self,
        movimientos: bool,
        cartolas: bool,
        cuentas: bool,
        asociaciones: bool,
        facturas: bool = False,
    ) -> LimpiezaResult:
        result = LimpiezaResult()

        if cartolas and not movimientos:
            result.errores.append(
                "Para borrar cartolas también debes borrar los movimientos."
            )
            return result

        if cuentas and not cartolas:
            result.errores.append(
                "Para borrar cuentas también debes borrar las cartolas."
            )
            return result

        try:
            # 1. Facturas (borra detalles, aplicaciones, importaciones asociadas)
            if facturas:
                n = Factura.query.count()
                # Primero aplicaciones de pago (FK CASCADE con facturas)
                HistorialAplicacionPago.query.delete(synchronize_session=False)
                AplicacionPago.query.delete(synchronize_session=False)
                # Asociaciones factura↔propiedad
                AsociacionFacturaPropiedad.query.delete(synchronize_session=False)
                # Historial de asociaciones de facturas
                HistorialAsociacionFactura.query.delete(synchronize_session=False)
                # Detalles y facturas
                DetalleFactura.query.delete(synchronize_session=False)
                Factura.query.delete(synchronize_session=False)
                # Importaciones (lotes)
                ImportacionFactura.query.delete(synchronize_session=False)
                result.eliminados["facturas"] = n

            # 2. Movimientos bancarios
            if movimientos:
                n = MovimientoBancario.query.count()
                # Aplicaciones que dependen de movimientos (ya borradas si facturas=True,
                # pero por si acaso se piden movimientos sin facturas)
                HistorialAplicacionPago.query.delete(synchronize_session=False)
                AplicacionPago.query.delete(synchronize_session=False)
                HistorialAsociacion.query.delete(synchronize_session=False)
                AsociacionMovimiento.query.delete(synchronize_session=False)
                MovimientoBancario.query.delete(synchronize_session=False)
                result.eliminados["movimientos"] = n

            # 3. Cartolas
            if cartolas:
                n = Cartola.query.count()
                Cartola.query.delete(synchronize_session=False)
                result.eliminados["cartolas"] = n

            # 4. Cuentas bancarias
            if cuentas:
                n = CuentaBancaria.query.count()
                CuentaBancaria.query.delete(synchronize_session=False)
                result.eliminados["cuentas"] = n

            # 5. Asociaciones aprendidas (identidades + depositantes)
            if asociaciones:
                n_ident = IdentidadTributaria.query.count()
                n_dep = AsociacionDepositante.query.count()
                IdentidadTributaria.query.delete(synchronize_session=False)
                AsociacionDepositante.query.delete(synchronize_session=False)
                result.eliminados["identidades_tributarias"] = n_ident
                result.eliminados["asociaciones_depositantes"] = n_dep

            db.session.commit()
            result.ok = True
            return result
        except Exception as exc:
            db.session.rollback()
            result.errores.append(f"Error inesperado: {exc}")
            return result