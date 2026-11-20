-- Esquema inicial para un proyecto Supabase nuevo. Este archivo contiene solo DDL.
BEGIN;

CREATE SCHEMA inmobiliaria;

CREATE TABLE inmobiliaria.centros_costo (
	codigo VARCHAR(64) NOT NULL, 
	nombre_original VARCHAR(255) NOT NULL, 
	nombre_normalizado VARCHAR(255) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_centros_costo_nombre_normalizado ON inmobiliaria.centros_costo (nombre_normalizado);

CREATE UNIQUE INDEX ix_centros_costo_codigo ON inmobiliaria.centros_costo (codigo);

CREATE TABLE inmobiliaria.arrendatarios (
	nombre_original VARCHAR(255) NOT NULL, 
	nombre_normalizado VARCHAR(255) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_arrendatarios_nombre_normalizado ON inmobiliaria.arrendatarios (nombre_normalizado);

CREATE TABLE inmobiliaria.conceptos (
	nombre VARCHAR(128) NOT NULL, 
	nombre_normalizado VARCHAR(128) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_conceptos_nombre_normalizado ON inmobiliaria.conceptos (nombre_normalizado);

CREATE UNIQUE INDEX ix_conceptos_nombre ON inmobiliaria.conceptos (nombre);

CREATE TABLE inmobiliaria.cuentas_bancarias (
	banco VARCHAR(128) NOT NULL, 
	numero_cuenta VARCHAR(64) NOT NULL, 
	moneda VARCHAR(16) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_cuentas_bancarias_numero_cuenta ON inmobiliaria.cuentas_bancarias (numero_cuenta);

CREATE TABLE inmobiliaria.importaciones_facturas (
	archivos_recibidos INTEGER NOT NULL, 
	facturas_procesadas INTEGER NOT NULL, 
	facturas_validas INTEGER NOT NULL, 
	facturas_duplicadas INTEGER NOT NULL, 
	facturas_con_error INTEGER NOT NULL, 
	detalle_json TEXT, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE inmobiliaria.propiedades (
	nombre_original VARCHAR(255) NOT NULL, 
	nombre_normalizado VARCHAR(255) NOT NULL, 
	centro_costo_id VARCHAR(36) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_propiedad_cc_nombre_norm UNIQUE (centro_costo_id, nombre_normalizado), 
	FOREIGN KEY(centro_costo_id) REFERENCES inmobiliaria.centros_costo (id) ON DELETE RESTRICT
);

CREATE INDEX ix_propiedades_nombre_normalizado ON inmobiliaria.propiedades (nombre_normalizado);

CREATE INDEX ix_propiedades_centro_costo_id ON inmobiliaria.propiedades (centro_costo_id);

CREATE TABLE inmobiliaria.cartolas (
	cuenta_id VARCHAR(36) NOT NULL, 
	centro_costo_id VARCHAR(36), 
	numero_cartola VARCHAR(64), 
	periodo_desde DATE, 
	periodo_hasta DATE, 
	fecha_emision DATE, 
	archivo_nombre VARCHAR(255) NOT NULL, 
	archivo_hash VARCHAR(64) NOT NULL, 
	total_abonos_informado BIGINT, 
	total_cargos_informado BIGINT, 
	saldo_inicial_informado BIGINT, 
	saldo_final_informado BIGINT, 
	total_abonos_extraido BIGINT, 
	cantidad_movimientos INTEGER NOT NULL, 
	validacion_ok BOOLEAN NOT NULL, 
	validacion_mensaje TEXT, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cuenta_id) REFERENCES inmobiliaria.cuentas_bancarias (id) ON DELETE RESTRICT, 
	FOREIGN KEY(centro_costo_id) REFERENCES inmobiliaria.centros_costo (id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX ix_cartolas_archivo_hash ON inmobiliaria.cartolas (archivo_hash);

CREATE INDEX ix_cartolas_cuenta_id ON inmobiliaria.cartolas (cuenta_id);

CREATE INDEX ix_cartolas_numero_cartola ON inmobiliaria.cartolas (numero_cartola);

CREATE INDEX ix_cartolas_centro_costo_id ON inmobiliaria.cartolas (centro_costo_id);

CREATE TABLE inmobiliaria.asociaciones_depositantes (
	depositante_original VARCHAR(255) NOT NULL, 
	depositante_normalizado VARCHAR(255) NOT NULL, 
	arrendatario_id VARCHAR(36) NOT NULL, 
	vigente BOOLEAN NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_asociacion_depositante_arrendatario UNIQUE (depositante_normalizado, arrendatario_id), 
	FOREIGN KEY(arrendatario_id) REFERENCES inmobiliaria.arrendatarios (id) ON DELETE RESTRICT
);

CREATE INDEX ix_asociaciones_depositantes_depositante_normalizado ON inmobiliaria.asociaciones_depositantes (depositante_normalizado);

CREATE INDEX ix_asociaciones_depositantes_arrendatario_id ON inmobiliaria.asociaciones_depositantes (arrendatario_id);

CREATE INDEX ix_asociaciones_depositantes_vigente ON inmobiliaria.asociaciones_depositantes (vigente);

CREATE TABLE inmobiliaria.facturas (
	importacion_id VARCHAR(36), 
	tipo_documento VARCHAR(32) NOT NULL, 
	folio VARCHAR(32) NOT NULL, 
	rut_emisor VARCHAR(16), 
	rut_emisor_normalizado VARCHAR(16), 
	razon_social_emisor VARCHAR(255), 
	rut_receptor VARCHAR(16), 
	rut_receptor_normalizado VARCHAR(16), 
	razon_social_receptor VARCHAR(255), 
	fecha_emision DATE, 
	fecha_vencimiento DATE, 
	neto BIGINT, 
	exento BIGINT, 
	iva BIGINT, 
	total BIGINT, 
	archivo_nombre VARCHAR(255) NOT NULL, 
	archivo_hash VARCHAR(64) NOT NULL, 
	estado VARCHAR(32) NOT NULL, 
	estado_asociacion VARCHAR(32) NOT NULL, 
	validacion_ok BOOLEAN NOT NULL, 
	validacion_mensaje TEXT, 
	errores_json TEXT, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_factura_identidad_tributaria UNIQUE (rut_emisor_normalizado, tipo_documento, folio), 
	FOREIGN KEY(importacion_id) REFERENCES inmobiliaria.importaciones_facturas (id) ON DELETE SET NULL
);

CREATE INDEX ix_facturas_importacion_id ON inmobiliaria.facturas (importacion_id);

CREATE INDEX ix_facturas_folio ON inmobiliaria.facturas (folio);

CREATE INDEX ix_facturas_rut_receptor_normalizado ON inmobiliaria.facturas (rut_receptor_normalizado);

CREATE INDEX ix_facturas_rut_emisor ON inmobiliaria.facturas (rut_emisor);

CREATE UNIQUE INDEX ix_facturas_archivo_hash ON inmobiliaria.facturas (archivo_hash);

CREATE INDEX ix_facturas_rut_emisor_normalizado ON inmobiliaria.facturas (rut_emisor_normalizado);

CREATE INDEX ix_facturas_estado_asociacion ON inmobiliaria.facturas (estado_asociacion);

CREATE TABLE inmobiliaria.identidades_tributarias (
	rut_receptor_normalizado VARCHAR(16) NOT NULL, 
	razon_social_original VARCHAR(255), 
	arrendatario_id VARCHAR(36) NOT NULL, 
	vigente BOOLEAN NOT NULL, 
	origen VARCHAR(16) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(arrendatario_id) REFERENCES inmobiliaria.arrendatarios (id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX ix_identidades_tributarias_rut_receptor_normalizado ON inmobiliaria.identidades_tributarias (rut_receptor_normalizado);

CREATE INDEX ix_identidades_tributarias_arrendatario_id ON inmobiliaria.identidades_tributarias (arrendatario_id);

CREATE INDEX ix_identidades_tributarias_vigente ON inmobiliaria.identidades_tributarias (vigente);

CREATE TABLE inmobiliaria.gastos_documentos (
	centro_costo_id VARCHAR(36) NOT NULL, 
	archivo_nombre VARCHAR(255) NOT NULL, 
	archivo_hash VARCHAR(64) NOT NULL, 
	content_type VARCHAR(120) NOT NULL, 
	contenido BYTEA NOT NULL, 
	fecha_documento DATE, 
	monto BIGINT, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_gasto_documento_entidad_hash UNIQUE (centro_costo_id, archivo_hash), 
	FOREIGN KEY(centro_costo_id) REFERENCES inmobiliaria.centros_costo (id) ON DELETE RESTRICT
);

CREATE INDEX ix_gastos_documentos_archivo_hash ON inmobiliaria.gastos_documentos (archivo_hash);

CREATE INDEX ix_gastos_documentos_monto ON inmobiliaria.gastos_documentos (monto);

CREATE INDEX ix_gastos_documentos_centro_costo_id ON inmobiliaria.gastos_documentos (centro_costo_id);

CREATE INDEX ix_gastos_documentos_fecha_documento ON inmobiliaria.gastos_documentos (fecha_documento);

CREATE TABLE inmobiliaria.gasto_reglas (
	centro_costo_id VARCHAR(36) NOT NULL, 
	campo VARCHAR(32) NOT NULL, 
	valor_normalizado VARCHAR(512) NOT NULL, 
	tipo_gasto VARCHAR(16) NOT NULL, 
	categoria VARCHAR(100), 
	subcategoria VARCHAR(255), 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_gasto_regla_entidad_valor UNIQUE (centro_costo_id, campo, valor_normalizado), 
	FOREIGN KEY(centro_costo_id) REFERENCES inmobiliaria.centros_costo (id) ON DELETE CASCADE
);

CREATE INDEX ix_gasto_reglas_centro_costo_id ON inmobiliaria.gasto_reglas (centro_costo_id);

CREATE TABLE inmobiliaria.gastos_excels (
	centro_costo_id VARCHAR(36) NOT NULL, 
	archivo_nombre VARCHAR(255) NOT NULL, 
	archivo_hash VARCHAR(64) NOT NULL, 
	contenido BYTEA NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (centro_costo_id, archivo_hash), 
	FOREIGN KEY(centro_costo_id) REFERENCES inmobiliaria.centros_costo (id)
);

CREATE TABLE inmobiliaria.propiedades_arrendatarios (
	propiedad_id VARCHAR(36) NOT NULL, 
	arrendatario_id VARCHAR(36) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_propiedad_arrendatario UNIQUE (propiedad_id, arrendatario_id), 
	FOREIGN KEY(propiedad_id) REFERENCES inmobiliaria.propiedades (id) ON DELETE CASCADE, 
	FOREIGN KEY(arrendatario_id) REFERENCES inmobiliaria.arrendatarios (id) ON DELETE CASCADE
);

CREATE INDEX ix_propiedades_arrendatarios_propiedad_id ON inmobiliaria.propiedades_arrendatarios (propiedad_id);

CREATE INDEX ix_propiedades_arrendatarios_arrendatario_id ON inmobiliaria.propiedades_arrendatarios (arrendatario_id);

CREATE TABLE inmobiliaria.propiedades_conceptos (
	propiedad_id VARCHAR(36) NOT NULL, 
	concepto_id VARCHAR(36) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_propiedad_concepto UNIQUE (propiedad_id, concepto_id), 
	FOREIGN KEY(propiedad_id) REFERENCES inmobiliaria.propiedades (id) ON DELETE CASCADE, 
	FOREIGN KEY(concepto_id) REFERENCES inmobiliaria.conceptos (id) ON DELETE CASCADE
);

CREATE INDEX ix_propiedades_conceptos_propiedad_id ON inmobiliaria.propiedades_conceptos (propiedad_id);

CREATE INDEX ix_propiedades_conceptos_concepto_id ON inmobiliaria.propiedades_conceptos (concepto_id);

CREATE TABLE inmobiliaria.movimientos_bancarios (
	cartola_id VARCHAR(36) NOT NULL, 
	centro_costo_id VARCHAR(36), 
	fecha DATE NOT NULL, 
	descripcion_original TEXT NOT NULL, 
	depositante_original VARCHAR(255), 
	depositante_normalizado VARCHAR(255), 
	monto BIGINT NOT NULL, 
	pagina_origen INTEGER NOT NULL, 
	orden_en_pagina INTEGER NOT NULL, 
	huella_movimiento VARCHAR(64) NOT NULL, 
	estado VARCHAR(32) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_movimiento_cartola_huella UNIQUE (cartola_id, huella_movimiento), 
	FOREIGN KEY(cartola_id) REFERENCES inmobiliaria.cartolas (id) ON DELETE CASCADE, 
	FOREIGN KEY(centro_costo_id) REFERENCES inmobiliaria.centros_costo (id) ON DELETE RESTRICT
);

CREATE INDEX ix_movimientos_bancarios_centro_costo_id ON inmobiliaria.movimientos_bancarios (centro_costo_id);

CREATE INDEX ix_movimientos_bancarios_depositante_normalizado ON inmobiliaria.movimientos_bancarios (depositante_normalizado);

CREATE INDEX ix_movimientos_bancarios_fecha ON inmobiliaria.movimientos_bancarios (fecha);

CREATE INDEX ix_movimientos_bancarios_huella_movimiento ON inmobiliaria.movimientos_bancarios (huella_movimiento);

CREATE INDEX ix_movimientos_bancarios_cartola_id ON inmobiliaria.movimientos_bancarios (cartola_id);

CREATE TABLE inmobiliaria.detalles_factura (
	factura_id VARCHAR(36) NOT NULL, 
	codigo VARCHAR(64), 
	descripcion VARCHAR(255), 
	cantidad NUMERIC(12, 3), 
	unidad VARCHAR(16), 
	precio_unitario NUMERIC(18, 2), 
	descuento BIGINT, 
	total_linea BIGINT, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(factura_id) REFERENCES inmobiliaria.facturas (id) ON DELETE CASCADE
);

CREATE INDEX ix_detalles_factura_factura_id ON inmobiliaria.detalles_factura (factura_id);

CREATE TABLE inmobiliaria.asociaciones_factura_propiedad (
	factura_id VARCHAR(36) NOT NULL, 
	propiedad_id VARCHAR(36) NOT NULL, 
	centro_costo_id VARCHAR(36), 
	conceptos_json TEXT NOT NULL, 
	estado VARCHAR(32) NOT NULL, 
	metodo VARCHAR(32) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_asociacion_factura_propiedad UNIQUE (factura_id, propiedad_id), 
	FOREIGN KEY(factura_id) REFERENCES inmobiliaria.facturas (id) ON DELETE CASCADE, 
	FOREIGN KEY(propiedad_id) REFERENCES inmobiliaria.propiedades (id) ON DELETE RESTRICT, 
	FOREIGN KEY(centro_costo_id) REFERENCES inmobiliaria.centros_costo (id) ON DELETE RESTRICT
);

CREATE INDEX ix_asociaciones_factura_propiedad_propiedad_id ON inmobiliaria.asociaciones_factura_propiedad (propiedad_id);

CREATE INDEX ix_asociaciones_factura_propiedad_centro_costo_id ON inmobiliaria.asociaciones_factura_propiedad (centro_costo_id);

CREATE INDEX ix_asociaciones_factura_propiedad_factura_id ON inmobiliaria.asociaciones_factura_propiedad (factura_id);

CREATE TABLE inmobiliaria.historial_asociaciones_factura (
	factura_id VARCHAR(36) NOT NULL, 
	accion VARCHAR(32) NOT NULL, 
	detalle_json TEXT, 
	usuario VARCHAR(128), 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(factura_id) REFERENCES inmobiliaria.facturas (id) ON DELETE CASCADE
);

CREATE INDEX ix_historial_asociaciones_factura_factura_id ON inmobiliaria.historial_asociaciones_factura (factura_id);

CREATE TABLE inmobiliaria.gastos_egresos (
	cartola_id VARCHAR(36) NOT NULL, 
	centro_costo_id VARCHAR(36) NOT NULL, 
	fecha DATE NOT NULL, 
	descripcion_original TEXT NOT NULL, 
	descripcion_normalizada VARCHAR(512) NOT NULL, 
	beneficiario VARCHAR(255), 
	monto BIGINT NOT NULL, 
	pagina_origen INTEGER NOT NULL, 
	orden_en_pagina INTEGER NOT NULL, 
	huella_movimiento VARCHAR(64) NOT NULL, 
	tipo_gasto VARCHAR(16), 
	categoria VARCHAR(100), 
	subcategoria VARCHAR(255), 
	clasificacion_origen VARCHAR(16) NOT NULL, 
	regla_id VARCHAR(36), 
	sugerencia_tipo VARCHAR(16), 
	sugerencia_categoria VARCHAR(100), 
	sugerencia_subcategoria VARCHAR(255), 
	sugerencia_regla_id VARCHAR(36), 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_gasto_cartola_huella UNIQUE (cartola_id, huella_movimiento), 
	FOREIGN KEY(cartola_id) REFERENCES inmobiliaria.cartolas (id) ON DELETE CASCADE, 
	FOREIGN KEY(centro_costo_id) REFERENCES inmobiliaria.centros_costo (id) ON DELETE RESTRICT, 
	FOREIGN KEY(regla_id) REFERENCES inmobiliaria.gasto_reglas (id) ON DELETE SET NULL, 
	FOREIGN KEY(sugerencia_regla_id) REFERENCES inmobiliaria.gasto_reglas (id) ON DELETE SET NULL
);

CREATE INDEX ix_gastos_egresos_centro_costo_id ON inmobiliaria.gastos_egresos (centro_costo_id);

CREATE INDEX ix_gastos_egresos_fecha ON inmobiliaria.gastos_egresos (fecha);

CREATE INDEX ix_gastos_egresos_cartola_id ON inmobiliaria.gastos_egresos (cartola_id);

CREATE INDEX ix_gastos_egresos_descripcion_normalizada ON inmobiliaria.gastos_egresos (descripcion_normalizada);

CREATE TABLE inmobiliaria.gastos_excel_filas (
	documento_id VARCHAR(36) NOT NULL, 
	excel_id VARCHAR(36) NOT NULL, 
	hoja VARCHAR(255) NOT NULL, 
	fila INTEGER NOT NULL, 
	destinatario TEXT NOT NULL, 
	observacion TEXT NOT NULL, 
	rut VARCHAR(32) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (documento_id), 
	FOREIGN KEY(documento_id) REFERENCES inmobiliaria.gastos_documentos (id) ON DELETE CASCADE, 
	FOREIGN KEY(excel_id) REFERENCES inmobiliaria.gastos_excels (id)
);

CREATE INDEX ix_gastos_excel_filas_excel_id ON inmobiliaria.gastos_excel_filas (excel_id);

CREATE TABLE inmobiliaria.asociaciones_movimientos (
	movimiento_id VARCHAR(36) NOT NULL, 
	asociacion_id VARCHAR(36) NOT NULL, 
	propiedad_id VARCHAR(36) NOT NULL, 
	conceptos_json TEXT NOT NULL, 
	estado VARCHAR(32) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_asociacion_movimiento_propiedad UNIQUE (movimiento_id, propiedad_id), 
	FOREIGN KEY(movimiento_id) REFERENCES inmobiliaria.movimientos_bancarios (id) ON DELETE CASCADE, 
	FOREIGN KEY(asociacion_id) REFERENCES inmobiliaria.asociaciones_depositantes (id) ON DELETE RESTRICT, 
	FOREIGN KEY(propiedad_id) REFERENCES inmobiliaria.propiedades (id) ON DELETE RESTRICT
);

CREATE INDEX ix_asociaciones_movimientos_asociacion_id ON inmobiliaria.asociaciones_movimientos (asociacion_id);

CREATE INDEX ix_asociaciones_movimientos_movimiento_id ON inmobiliaria.asociaciones_movimientos (movimiento_id);

CREATE INDEX ix_asociaciones_movimientos_propiedad_id ON inmobiliaria.asociaciones_movimientos (propiedad_id);

CREATE TABLE inmobiliaria.historial_asociaciones (
	movimiento_id VARCHAR(36) NOT NULL, 
	accion VARCHAR(32) NOT NULL, 
	detalle_json TEXT, 
	usuario VARCHAR(128), 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(movimiento_id) REFERENCES inmobiliaria.movimientos_bancarios (id) ON DELETE CASCADE
);

CREATE INDEX ix_historial_asociaciones_movimiento_id ON inmobiliaria.historial_asociaciones (movimiento_id);

CREATE TABLE inmobiliaria.aplicaciones_pago (
	movimiento_id VARCHAR(36) NOT NULL, 
	factura_id VARCHAR(36) NOT NULL, 
	monto_aplicado BIGINT NOT NULL, 
	metodo VARCHAR(16) NOT NULL, 
	activa BOOLEAN NOT NULL, 
	fecha_aplicacion DATE NOT NULL, 
	responsable VARCHAR(128), 
	llave_idempotencia VARCHAR(128) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(movimiento_id) REFERENCES inmobiliaria.movimientos_bancarios (id) ON DELETE CASCADE, 
	FOREIGN KEY(factura_id) REFERENCES inmobiliaria.facturas (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_aplicacion_activa_mov_fact ON inmobiliaria.aplicaciones_pago (movimiento_id, factura_id) WHERE activa IS TRUE;

CREATE UNIQUE INDEX ix_aplicaciones_pago_llave_idempotencia ON inmobiliaria.aplicaciones_pago (llave_idempotencia);

CREATE INDEX ix_aplicaciones_pago_movimiento_id ON inmobiliaria.aplicaciones_pago (movimiento_id);

CREATE INDEX ix_aplicaciones_pago_activa ON inmobiliaria.aplicaciones_pago (activa);

CREATE INDEX ix_aplicaciones_pago_factura_id ON inmobiliaria.aplicaciones_pago (factura_id);

CREATE TABLE inmobiliaria.gastos_asociaciones (
	egreso_id VARCHAR(36) NOT NULL, 
	documento_id VARCHAR(36) NOT NULL, 
	estado VARCHAR(16) NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_gasto_asociacion UNIQUE (egreso_id, documento_id), 
	FOREIGN KEY(egreso_id) REFERENCES inmobiliaria.gastos_egresos (id) ON DELETE CASCADE, 
	FOREIGN KEY(documento_id) REFERENCES inmobiliaria.gastos_documentos (id) ON DELETE CASCADE
);

CREATE INDEX ix_gastos_asociaciones_egreso_id ON inmobiliaria.gastos_asociaciones (egreso_id);

CREATE INDEX ix_gastos_asociaciones_documento_id ON inmobiliaria.gastos_asociaciones (documento_id);

CREATE TABLE inmobiliaria.historial_aplicaciones_pago (
	aplicacion_id VARCHAR(36) NOT NULL, 
	accion VARCHAR(32) NOT NULL, 
	detalle_json TEXT, 
	responsable VARCHAR(128), 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(aplicacion_id) REFERENCES inmobiliaria.aplicaciones_pago (id) ON DELETE CASCADE
);

CREATE INDEX ix_historial_aplicaciones_pago_aplicacion_id ON inmobiliaria.historial_aplicaciones_pago (aplicacion_id);

REVOKE ALL ON SCHEMA inmobiliaria FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA inmobiliaria FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA inmobiliaria TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA inmobiliaria TO service_role;

CREATE FUNCTION inmobiliaria.importar_sqlite(p_filas jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog
SET timezone = 'UTC'
AS $importar$
DECLARE
    tablas CONSTANT text[] := ARRAY[
        'arrendatarios',
        'centros_costo',
        'conceptos',
        'cuentas_bancarias',
        'importaciones_facturas',
        'asociaciones_depositantes',
        'cartolas',
        'facturas',
        'gasto_reglas',
        'gastos_documentos',
        'gastos_excels',
        'identidades_tributarias',
        'propiedades',
        'asociaciones_factura_propiedad',
        'detalles_factura',
        'gastos_egresos',
        'gastos_excel_filas',
        'historial_asociaciones_factura',
        'movimientos_bancarios',
        'propiedades_arrendatarios',
        'propiedades_conceptos',
        'aplicaciones_pago',
        'asociaciones_movimientos',
        'gastos_asociaciones',
        'historial_asociaciones',
        'historial_aplicaciones_pago'
    ];
    tabla text;
    no_vacia boolean;
    numero integer;
    resultado jsonb := '{}'::jsonb;
BEGIN
    IF jsonb_typeof(p_filas) IS DISTINCT FROM 'object' OR
       (SELECT count(*) FROM jsonb_object_keys(p_filas)) <> cardinality(tablas) THEN
        RAISE EXCEPTION 'El conjunto de tablas no coincide con el esquema de destino'
            USING ERRCODE = '22023';
    END IF;

    FOREACH tabla IN ARRAY tablas LOOP
        IF jsonb_typeof(p_filas -> tabla) IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'Faltan las filas de %', tabla USING ERRCODE = '22023';
        END IF;
        EXECUTE format('LOCK TABLE inmobiliaria.%I IN SHARE ROW EXCLUSIVE MODE', tabla);
        EXECUTE format('SELECT EXISTS (SELECT FROM inmobiliaria.%I)', tabla) INTO no_vacia;
        IF no_vacia THEN
            RAISE EXCEPTION 'La tabla % ya contiene datos', tabla USING ERRCODE = '23505';
        END IF;
    END LOOP;

    FOREACH tabla IN ARRAY tablas LOOP
        EXECUTE format(
            'INSERT INTO inmobiliaria.%I SELECT * FROM jsonb_populate_recordset(NULL::inmobiliaria.%I, $1)',
            tabla, tabla
        ) USING p_filas -> tabla;
        GET DIAGNOSTICS numero = ROW_COUNT;
        IF numero <> jsonb_array_length(p_filas -> tabla) THEN
            RAISE EXCEPTION 'No se copiaron todas las filas de %', tabla;
        END IF;
        resultado := resultado || jsonb_build_object(tabla, numero);
    END LOOP;

    RETURN resultado;
END;
$importar$;

REVOKE EXECUTE ON FUNCTION inmobiliaria.importar_sqlite(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION inmobiliaria.importar_sqlite(jsonb) TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
