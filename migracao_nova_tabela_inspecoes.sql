-- Substitui a tabela inspecoes por uma tabela limpa com a mesma estrutura.
-- A tabela atual é preservada como inspecoes_antiga (nada é apagado).
-- Executar no console SQL do NeonDB, de uma vez, com o app sem uso.

BEGIN;

ALTER TABLE inspecoes RENAME TO inspecoes_antiga;

DO $$
DECLARE
    n_itens integer;
    i integer;
BEGIN
    -- Número de itens do checklist, lido das colunas q1..qN da tabela antiga.
    SELECT count(*) INTO n_itens
      FROM information_schema.columns
     WHERE table_schema = current_schema()
       AND table_name = 'inspecoes_antiga'
       AND column_name ~ '^q[0-9]+$';

    CREATE TABLE inspecoes (
        id               serial      PRIMARY KEY,
        mes_referencia   text        NOT NULL,
        setor            text        NOT NULL,
        responsavel_area text,
        data_execucao    timestamp   NOT NULL,
        cipeiro          text        NOT NULL,
        acompanhantes    text,
        status           text        NOT NULL CHECK (status IN ('Realizada', 'Justificada')),
        obs_geral        text,
        foto_geral       text
    );

    FOR i IN 1..n_itens LOOP
        EXECUTE format('ALTER TABLE inspecoes ADD COLUMN %I text', 'q' || i);
        EXECUTE format('ALTER TABLE inspecoes ADD COLUMN %I text', 'obs' || i);
        EXECUTE format('ALTER TABLE inspecoes ADD COLUMN %I text', 'foto_q' || i);
    END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS ix_inspecoes_data_execucao_nova ON inspecoes (data_execucao DESC);

COMMIT;

-- Conferência: deve listar as colunas q1..qN, obs1..obsN e foto_q1..foto_qN.
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'inspecoes' ORDER BY ordinal_position;

-- OPCIONAL: copiar da tabela antiga apenas registros reais (ajustar os ids após revisar a tabela antiga).
-- SELECT id, mes_referencia, setor, cipeiro, data_execucao, acompanhantes FROM inspecoes_antiga ORDER BY id;
--
-- DO $$
-- DECLARE colunas text;
-- BEGIN
--     SELECT string_agg(quote_ident(column_name), ', ') INTO colunas
--       FROM information_schema.columns
--      WHERE table_schema = current_schema() AND table_name = 'inspecoes_antiga' AND column_name <> 'id';
--     EXECUTE format('INSERT INTO inspecoes (%1$s) SELECT %1$s FROM inspecoes_antiga WHERE id IN (55)', colunas);
-- END $$;
