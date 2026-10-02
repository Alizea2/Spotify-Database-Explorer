'use strict';
/**
 * Shared MySQL2 connection pool.
 * Connects as spotify_reader — a least-privilege, SELECT-only user.
 * Override with env vars: DB_HOST, DB_USER, DB_PASS, DB_NAME
 */

const mysql = require('mysql2/promise');

const pool = mysql.createPool({
  host:               process.env.DB_HOST || '127.0.0.1',
  user:               process.env.DB_USER || 'spotify_reader',
  password:           process.env.DB_PASS || 'spotify_secure_2024',
  database:           process.env.DB_NAME || 'spotify_db',
  waitForConnections: true,
  connectionLimit:    10,
  queueLimit:          0,
  charset:             'utf8mb4',
});

/** Run a parameterised query and return all rows. */
async function query(sql, params = []) {
  const [rows] = await pool.execute(sql, params);
  return rows;
}

module.exports = { pool, query };
