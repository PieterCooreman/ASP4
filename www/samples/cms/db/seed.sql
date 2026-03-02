PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  site_title TEXT NOT NULL DEFAULT 'ASP4 CMS',
  site_slogan TEXT NOT NULL DEFAULT '',
  palette_name TEXT NOT NULL DEFAULT 'ocean',
  color_primary TEXT NOT NULL DEFAULT '#0ea5e9',
  color_secondary TEXT NOT NULL DEFAULT '#64748b',
  color_success TEXT NOT NULL DEFAULT '#16a34a',
  color_danger TEXT NOT NULL DEFAULT '#dc2626',
  color_warning TEXT NOT NULL DEFAULT '#f59e0b',
  color_info TEXT NOT NULL DEFAULT '#0891b2',
  color_light TEXT NOT NULL DEFAULT '#f8fafc',
  color_dark TEXT NOT NULL DEFAULT '#0f172a',
  font_body TEXT NOT NULL DEFAULT 'Inter',
  font_heading TEXT NOT NULL DEFAULT 'Merriweather',
  font_button TEXT NOT NULL DEFAULT 'Poppins',
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('draft','published')) DEFAULT 'draft',
  body_html TEXT NOT NULL DEFAULT '',
  menu_title TEXT,
  is_home INTEGER NOT NULL DEFAULT 0,
  menu_order INTEGER NOT NULL DEFAULT 9999,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS media (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_name TEXT NOT NULL,
  original_name TEXT NOT NULL,
  rel_path TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  ext TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  width INTEGER,
  height INTEGER,
  uploaded_by INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pages_slug ON pages(slug);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(status);
CREATE INDEX IF NOT EXISTS idx_pages_menu_order ON pages(menu_order);
CREATE INDEX IF NOT EXISTS idx_media_created ON media(created_at);

INSERT OR IGNORE INTO settings (id) VALUES (1);

INSERT INTO users (name, email, password_hash, is_admin, created_at)
VALUES (
  'Administrator',
  'admin@example.com',
  '$2b$12$Eq470BnPc29vbZN8xWndtOvJqtEIXO9m1lkMHYsVcvw8lLpD/Wh72',
  1,
  datetime('now')
)
ON CONFLICT(email) DO UPDATE SET
  name = excluded.name,
  password_hash = excluded.password_hash,
  is_admin = excluded.is_admin,
  updated_at = datetime('now');

INSERT OR IGNORE INTO pages (id, title, slug, status, body_html, menu_title, is_home, menu_order, created_at)
VALUES (
  1,
  'Home',
  'home',
  'published',
  '<h1>Welcome</h1><p>Your CMS is ready.</p>',
  'Home',
  1,
  1,
  datetime('now')
);
