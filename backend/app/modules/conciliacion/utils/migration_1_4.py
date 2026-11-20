"""Migración idempotente Subetapa 1.4.

Solo normaliza estados antiguos. No destruye datos.
Ejecutar:
    cd backend
    source venv/bin/activate
    python -m app.modules.conciliacion.utils.migration_1_4
"""
from app import create_app
from app.core.database import db
from app.modules.conciliacion.models import MovimientoBancario


def migrar() -> None:
    app = create_app()
    with app.app_context():
        # Cualquier movimiento con estado desconocido -> pendiente.
        # Cualquier 'asociado' legado -> asociado_manual.
        q = MovimientoBancario.query.filter(
            ~MovimientoBancario.estado.in_(
                ["pendiente", "asociado_manual", "asociado_automatico"]
            )
        )
        for mov in q.all():
            mov.estado = "asociado_manual" if mov.estado == "asociado" else "pendiente"
        db.session.commit()
        print("Migración 1.4 aplicada.")


if __name__ == "__main__":
    migrar()