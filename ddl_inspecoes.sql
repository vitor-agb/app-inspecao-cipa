-- DDL da tabela inspecoes (PostgreSQL / NeonDB).
-- Colunas e tipos conferidos contra information_schema.columns do banco de produção em 16/11/2026
-- (31 itens; id integer com sequência; todas as demais colunas text, exceto data_execucao timestamp).
-- Restrições (CHECK de status), chave primária e índices não foram conferidos.
-- n_itens deve ser igual ao número de entradas de lista_perguntas_cipa em st.secrets.

CREATE TABLE IF NOT EXISTS inspecoes (
    id               serial      PRIMARY KEY,
    mes_referencia  text        NOT NULL,   -- formato 'Mes/AAAA'
    setor            text        NOT NULL,
    responsavel_area text,
    data_execucao    timestamp   NOT NULL,   -- data informada + hora de gravação (naive)
    cipeiro          text        NOT NULL,
    acompanhantes    text,
    status           text        NOT NULL CHECK (status IN ('Realizada', 'Justificada')),
    obs_geral        text,                   -- motivo da não realização quando status = 'Justificada'
    foto_geral       text                    -- URLs Cloudinary separadas por ', '
);

-- Colunas por item: qN (S | N | N/A | Justificado), obsN, foto_qN (URLs separadas por ', ').
DO $$
DECLARE
    n_itens integer := 31;  -- ajustar ao tamanho de lista_perguntas_cipa
    i integer;
BEGIN
    FOR i IN 1..n_itens LOOP
        EXECUTE format('ALTER TABLE inspecoes ADD COLUMN IF NOT EXISTS %I text', 'q' || i);
        EXECUTE format('ALTER TABLE inspecoes ADD COLUMN IF NOT EXISTS %I text', 'obs' || i);
        EXECUTE format('ALTER TABLE inspecoes ADD COLUMN IF NOT EXISTS %I text', 'foto_q' || i);
    END LOOP;
END $$;

-- Ordenação usada por carregar_dados().
CREATE INDEX IF NOT EXISTS idx_inspecoes_data_execucao ON inspecoes (data_execucao DESC);
