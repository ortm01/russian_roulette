CREATE TABLE users (
    telegram_id   BIGINT PRIMARY KEY,
    username      TEXT,
    balance       NUMERIC(12,2) NOT NULL DEFAULT 100.00 CHECK (balance >= 0),
    last_bonus_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE games (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES users(telegram_id),
    mode             SMALLINT NOT NULL CHECK (mode IN (1, 2)),
    bullets          SMALLINT NOT NULL CHECK (bullets BETWEEN 1 AND 5),
    bet              NUMERIC(12,2) NOT NULL CHECK (bet >= 1),
    step             SMALLINT NOT NULL DEFAULT 0,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'won', 'lost', 'cashed_out')),
    payout           NUMERIC(12,2),
    bullet_positions SMALLINT[],
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ
);

CREATE UNIQUE INDEX one_active_game_per_user
    ON games (user_id) WHERE status = 'active';

CREATE INDEX idx_users_balance ON users (balance DESC);
