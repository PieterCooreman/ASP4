PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  original_name TEXT NOT NULL,
  file_name TEXT NOT NULL,
  rel_path TEXT NOT NULL,
  thumb_path TEXT NOT NULL,
  width INTEGER,
  height INTEGER,
  size_bytes INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_images_created ON images(created_at);
