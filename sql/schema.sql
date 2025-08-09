CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE,
  eth_address TEXT,
  referrer_id INT NULL,
  license_status VARCHAR(20) DEFAULT 'inactive',
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE payments (
  id SERIAL PRIMARY KEY,
  tx_hash TEXT,
  payer_address TEXT,
  amount NUMERIC,
  reference TEXT,
  status VARCHAR(20) DEFAULT 'pending',
  user_id INT NULL REFERENCES users(id),
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE referrals (
  id SERIAL PRIMARY KEY,
  referrer_user_id INT REFERENCES users(id),
  referred_user_id INT REFERENCES users(id),
  amount NUMERIC,
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE payouts (
  id SERIAL PRIMARY KEY,
  referrer_user_id INT REFERENCES users(id),
  amount NUMERIC,
  tx_hash TEXT NULL,
  status VARCHAR(20) DEFAULT 'queued',
  created_at TIMESTAMP DEFAULT now()
);
