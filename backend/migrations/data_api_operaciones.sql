-- Actualiza una instalación preparada con data_api.sql.
BEGIN;

CREATE TABLE inmobiliaria.revision_conciliacion (
    id boolean PRIMARY KEY DEFAULT true CHECK (id),
    revision bigint NOT NULL DEFAULT 0
);

INSERT INTO inmobiliaria.revision_conciliacion DEFAULT VALUES;
REVOKE ALL ON inmobiliaria.revision_conciliacion FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON inmobiliaria.revision_conciliacion TO service_role;

CREATE FUNCTION inmobiliaria.tablas_conciliacion()
RETURNS text[]
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog
AS $$
    SELECT ARRAY[
        'arrendatarios', 'centros_costo', 'conceptos', 'cuentas_bancarias',
        'importaciones_facturas', 'asociaciones_depositantes', 'cartolas', 'facturas',
        'gasto_reglas', 'gastos_documentos', 'gastos_excels', 'identidades_tributarias',
        'propiedades', 'asociaciones_factura_propiedad', 'detalles_factura',
        'gastos_egresos', 'gastos_excel_filas', 'historial_asociaciones_factura',
        'movimientos_bancarios', 'propiedades_arrendatarios', 'propiedades_conceptos',
        'aplicaciones_pago', 'asociaciones_movimientos', 'gastos_asociaciones',
        'historial_asociaciones', 'historial_aplicaciones_pago'
    ]::text[];
$$;

CREATE FUNCTION inmobiliaria.avanzar_revision_conciliacion()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(643490220);
    UPDATE inmobiliaria.revision_conciliacion SET revision = revision + 1 WHERE id;
    RETURN NULL;
END;
$$;

DO $$
DECLARE
    tabla text;
BEGIN
    FOREACH tabla IN ARRAY inmobiliaria.tablas_conciliacion() LOOP
        EXECUTE format(
            'CREATE TRIGGER avanzar_revision BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE ON inmobiliaria.%I
             FOR EACH STATEMENT EXECUTE FUNCTION inmobiliaria.avanzar_revision_conciliacion()',
            tabla
        );
    END LOOP;
END;
$$;

CREATE FUNCTION inmobiliaria.datos_conciliacion()
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SET search_path = pg_catalog
SET timezone = 'UTC'
AS $$
DECLARE
    tabla text;
    campos text;
    datos jsonb;
    filas jsonb := '{}'::jsonb;
    actual bigint;
BEGIN
    SELECT revision INTO STRICT actual FROM inmobiliaria.revision_conciliacion WHERE id;

    FOREACH tabla IN ARRAY inmobiliaria.tablas_conciliacion() LOOP
        SELECT string_agg(format('%I', attname), ', ' ORDER BY attnum)
        INTO campos
        FROM pg_attribute
        WHERE attrelid = format('inmobiliaria.%I', tabla)::regclass
          AND attnum > 0 AND NOT attisdropped AND atttypid <> 'bytea'::regtype;

        EXECUTE format(
            'SELECT coalesce(jsonb_agg(to_jsonb(f)), ''[]''::jsonb)
             FROM (SELECT %s FROM inmobiliaria.%I) f',
            campos, tabla
        ) INTO datos;
        filas := filas || jsonb_build_object(tabla, datos);
    END LOOP;

    RETURN jsonb_build_object('revision', actual, 'filas', filas);
END;
$$;

CREATE FUNCTION inmobiliaria.guardar_conciliacion(p_revision bigint, p_cambios jsonb)
RETURNS bigint
LANGUAGE plpgsql
SET search_path = pg_catalog
SET timezone = 'UTC'
AS $$
DECLARE
    actual bigint;
    cambio jsonb;
    tabla text;
    id_fila text;
    datos jsonb;
    campos text;
BEGIN
    PERFORM pg_advisory_xact_lock(643490220);
    SELECT revision INTO STRICT actual FROM inmobiliaria.revision_conciliacion WHERE id;
    IF actual IS DISTINCT FROM p_revision THEN
        RAISE EXCEPTION 'La revisión de conciliación cambió' USING ERRCODE = '40001';
    END IF;

    FOR cambio IN SELECT value FROM jsonb_array_elements(p_cambios) LOOP
        tabla := cambio ->> 'tabla';
        id_fila := cambio ->> 'id';
        datos := cambio -> 'datos';
        IF tabla IS NULL OR tabla <> ALL(inmobiliaria.tablas_conciliacion()) OR id_fila IS NULL THEN
            RAISE EXCEPTION 'Tabla o identificador de conciliación inválido' USING ERRCODE = '22023';
        END IF;

        CASE cambio ->> 'operacion'
            WHEN 'INSERT' THEN
                EXECUTE format(
                    'INSERT INTO inmobiliaria.%I
                     SELECT * FROM jsonb_populate_record(NULL::inmobiliaria.%I, $1)',
                    tabla, tabla
                ) USING datos || jsonb_build_object('id', id_fila);
            WHEN 'UPDATE' THEN
                SELECT string_agg(format('%1$I = nuevos.%1$I', attname), ', ' ORDER BY attnum)
                INTO campos
                FROM pg_attribute
                WHERE attrelid = format('inmobiliaria.%I', tabla)::regclass
                  AND attnum > 0 AND NOT attisdropped AND attname <> 'id'
                  AND datos ? attname::text;
                IF campos IS NOT NULL THEN
                    EXECUTE format(
                        'UPDATE inmobiliaria.%I AS destino SET %s
                         FROM jsonb_populate_record(NULL::inmobiliaria.%I, $1) AS nuevos
                         WHERE destino.id = $2',
                        tabla, campos, tabla
                    ) USING datos, id_fila;
                END IF;
            WHEN 'DELETE' THEN
                EXECUTE format('DELETE FROM inmobiliaria.%I WHERE id = $1', tabla) USING id_fila;
            ELSE
                RAISE EXCEPTION 'Operación de conciliación inválida' USING ERRCODE = '22023';
        END CASE;
    END LOOP;

    RETURN (SELECT revision FROM inmobiliaria.revision_conciliacion WHERE id);
END;
$$;

CREATE FUNCTION inmobiliaria.archivo_conciliacion(p_revision bigint, p_tabla text, p_id text)
RETURNS text
LANGUAGE plpgsql
STABLE
SET search_path = pg_catalog
AS $$
DECLARE
    archivo text;
BEGIN
    IF (SELECT revision FROM inmobiliaria.revision_conciliacion WHERE id) IS DISTINCT FROM p_revision THEN
        RAISE EXCEPTION 'La revisión de conciliación cambió' USING ERRCODE = '40001';
    END IF;
    IF p_tabla IS NULL OR p_tabla NOT IN ('gastos_documentos', 'gastos_excels') THEN
        RAISE EXCEPTION 'Tabla de archivos inválida' USING ERRCODE = '22023';
    END IF;

    EXECUTE format('SELECT encode(contenido, ''hex'') FROM inmobiliaria.%I WHERE id = $1', p_tabla)
    INTO STRICT archivo USING p_id;
    RETURN archivo;
END;
$$;

REVOKE EXECUTE ON FUNCTION inmobiliaria.avanzar_revision_conciliacion() FROM PUBLIC, anon, authenticated, service_role;
REVOKE EXECUTE ON FUNCTION inmobiliaria.tablas_conciliacion() FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION inmobiliaria.datos_conciliacion() FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION inmobiliaria.guardar_conciliacion(bigint, jsonb) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION inmobiliaria.archivo_conciliacion(bigint, text, text) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION inmobiliaria.tablas_conciliacion() TO service_role;
GRANT EXECUTE ON FUNCTION inmobiliaria.datos_conciliacion() TO service_role;
GRANT EXECUTE ON FUNCTION inmobiliaria.guardar_conciliacion(bigint, jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION inmobiliaria.archivo_conciliacion(bigint, text, text) TO service_role;

NOTIFY pgrst, 'reload schema';
COMMIT;
