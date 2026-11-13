-- Mandatos da CIPA por pessoa e por ano (PostgreSQL / NeonDB).
-- Uma linha por usuário e ano de mandato; reeleição = nova linha, sem apagar as anteriores.
-- Executar uma vez no console SQL do banco, depois de ddl_usuarios_cipa.sql.

CREATE TABLE IF NOT EXISTS mandatos_cipa (
    login text    NOT NULL REFERENCES usuarios_cipa (login) ON DELETE CASCADE,
    ano   integer NOT NULL,
    PRIMARY KEY (login, ano)
);

-- Mandato do ano corrente para os usuários já cadastrados que participam das inspeções.
INSERT INTO mandatos_cipa (login, ano)
SELECT login, EXTRACT(YEAR FROM now())::integer
  FROM usuarios_cipa
 WHERE inspetor
ON CONFLICT DO NOTHING;
