-- Tabela de usuários do app (PostgreSQL / NeonDB).
-- Executar uma vez no console SQL do banco antes de usar a página Gerenciar Usuários.

CREATE TABLE IF NOT EXISTS usuarios_cipa (
    login             text      PRIMARY KEY,                                   -- minúsculas, sem espaços
    nome              text      NOT NULL,                                      -- nome gravado em inspecoes.cipeiro
    perfil            text      NOT NULL CHECK (perfil IN ('cipeiro', 'gestor', 'admin')),
    senha_hash        text      NOT NULL,                                      -- pbkdf2_sha256$iteracoes$sal$hash
    trocar_senha      boolean   NOT NULL DEFAULT true,                         -- exige nova senha no próximo acesso
    ativo             boolean   NOT NULL DEFAULT true,
    inspetor          boolean   NOT NULL DEFAULT true,                         -- participa da lista e da matriz de engajamento
    tentativas_falhas integer   NOT NULL DEFAULT 0,
    bloqueado_ate     timestamp,                                               -- login bloqueado até este instante (naive, horário do servidor)
    atualizado_em     timestamp NOT NULL DEFAULT now()
);
