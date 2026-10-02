'use strict';
/**
 * Parses ../queries.sql into { name: sqlString } so server.js can run
 * db.query(queries.someName, params) instead of embedding SQL as inline
 * template strings. Each query block in the file starts with a
 * `-- @name: <identifier>` marker comment and runs until the next marker
 * (or end of file); everything before the first marker (header comments,
 * `USE spotify_db;`) is ignored.
 */

const fs = require('fs');

function loadQueries(filePath) {
  const text = fs.readFileSync(filePath, 'utf8');
  const blocks = text.split(/^-- @name: */m).slice(1);

  const queries = {};
  for (const block of blocks) {
    const newlineIndex = block.indexOf('\n');
    const name = block.slice(0, newlineIndex).trim();
    const sql = block
      .slice(newlineIndex + 1)
      .trim()
      .replace(/;$/, '');
    queries[name] = sql;
  }
  return queries;
}

module.exports = { loadQueries };
