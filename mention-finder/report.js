/* Mention Finder — export flagged Reddit items for reporting.
 * Builds records with permalinks, UTC timestamps, capture time and a SHA-256
 * fingerprint, then serialises them as CSV, JSON, plain text or a printable report.
 * Browser: window.MentionReport. Node: module.exports (for tests; hashing needs WebCrypto).
 */
(function (root) {
  'use strict';

  const iso = sec => (sec ? new Date(sec * 1000).toISOString() : '');

  /** Turn a flagged entry into the flat record every export format shares. */
  function toRecord(flag) {
    const it = flag.item;
    return {
      reddit_id: it.id,
      type: it.type,
      permalink: it.url,
      subreddit: 'r/' + it.sub,
      author: it.author === '[deleted]' ? '[deleted]' : 'u/' + it.author,
      author_profile: it.author && it.author !== '[deleted]' ? `https://www.reddit.com/user/${encodeURIComponent(it.author)}/` : '',
      posted_utc: iso(it.created),
      title: it.title || '',
      text: it.body || '',
      linked_url: it.link || '',
      score_at_capture: it.score,
      comments_at_capture: it.type === 'post' ? it.comments : '',
      matched_terms: (flag.matched || []).join('; '),
      search_query: flag.query || '',
      captured_utc: flag.capturedAt || '',
      reporter_note: flag.note || '',
      sha256: '',
    };
  }

  const HASHED = ['reddit_id', 'permalink', 'author', 'posted_utc', 'title', 'text', 'linked_url', 'captured_utc'];

  /** SHA-256 over the content fields (not the editable note), so later copies can be checked. */
  async function fingerprint(rec) {
    const subtle = root.crypto && root.crypto.subtle;
    if (!subtle) return '';
    const canon = JSON.stringify(HASHED.map(k => [k, rec[k]]));
    const buf = await subtle.digest('SHA-256', new TextEncoder().encode(canon));
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
  }

  async function buildRecords(flags) {
    const recs = flags.map(toRecord);
    for (const r of recs) r.sha256 = await fingerprint(r);
    return recs;
  }

  const COLUMNS = ['reddit_id', 'type', 'posted_utc', 'subreddit', 'author', 'permalink', 'title', 'text', 'linked_url',
    'score_at_capture', 'comments_at_capture', 'matched_terms', 'reporter_note', 'search_query', 'captured_utc', 'author_profile', 'sha256'];

  /** RFC 4180 CSV with a UTF-8 BOM so Excel opens accents and emoji correctly. */
  function toCSV(recs) {
    const cell = v => {
      let s = v == null ? '' : String(v);
      // Neutralise spreadsheet formulas coming from untrusted post text.
      if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
      return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    return '﻿' + [COLUMNS.join(','), ...recs.map(r => COLUMNS.map(c => cell(r[c])).join(','))].join('\r\n') + '\r\n';
  }

  function toJSON(recs, meta) {
    return JSON.stringify({
      report: {
        generated_utc: meta.generatedAt,
        tool: 'Mention Finder',
        tool_url: meta.toolUrl,
        source: 'Public Reddit content (posts via reddit.com search, comments via PullPush archive)',
        reporter_summary: meta.summary || '',
        item_count: recs.length,
        hash_algorithm: 'SHA-256 of JSON array of [field, value] pairs for: ' + HASHED.join(', '),
      },
      items: recs,
    }, null, 2);
  }

  /** Plain text, for pasting into the free-text box of an online tip form. */
  function toText(recs, meta) {
    const lines = [
      `REPORT OF PUBLIC REDDIT CONTENT (${recs.length} item${recs.length === 1 ? '' : 's'})`,
      `Compiled: ${meta.generatedAt} (UTC)`,
    ];
    if (meta.summary) lines.push('', 'Summary:', meta.summary);
    recs.forEach((r, i) => {
      lines.push('', `--- Item ${i + 1} of ${recs.length} ---`,
        `Link: ${r.permalink}`,
        `Type: ${r.type} in ${r.subreddit}`,
        `Posted by: ${r.author}${r.author_profile ? ' (' + r.author_profile + ')' : ''}`,
        `Posted at (UTC): ${r.posted_utc}`,
        `Captured at (UTC): ${r.captured_utc}`);
      if (r.title) lines.push(`Title: ${r.title}`);
      if (r.text) lines.push(`Text: ${r.text.length > 1500 ? r.text.slice(0, 1500) + ' […truncated; full text in attached export]' : r.text}`);
      if (r.linked_url) lines.push(`Links to: ${r.linked_url}`);
      if (r.reporter_note) lines.push(`Note: ${r.reporter_note}`);
      if (r.sha256) lines.push(`SHA-256: ${r.sha256}`);
    });
    lines.push('', 'Content was public on Reddit when captured and may since have been edited or deleted.');
    return lines.join('\n');
  }

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /** Standalone printable HTML. Opened in a new tab, the visitor saves it as PDF. */
  function toPrintableHTML(recs, meta) {
    const rows = recs.map((r, i) => `<tr><td>${i + 1}</td><td>${esc(r.posted_utc.replace('T', ' ').replace(/\.\d+Z$/, 'Z'))}</td><td>${esc(r.subreddit)}</td><td>${esc(r.author)}</td><td>${esc(r.type)}</td><td class="u">${esc(r.permalink)}</td></tr>`).join('');
    const items = recs.map((r, i) => `
      <section class="item">
        <h2>Item ${i + 1} of ${recs.length}</h2>
        <table class="kv">
          <tr><th>Link</th><td class="u">${esc(r.permalink)}</td></tr>
          <tr><th>Type / community</th><td>${esc(r.type)} in ${esc(r.subreddit)}</td></tr>
          <tr><th>Posted by</th><td>${esc(r.author)} ${r.author_profile ? `<span class="u">${esc(r.author_profile)}</span>` : ''}</td></tr>
          <tr><th>Posted (UTC)</th><td>${esc(r.posted_utc)}</td></tr>
          <tr><th>Captured (UTC)</th><td>${esc(r.captured_utc)}</td></tr>
          ${r.linked_url ? `<tr><th>Links to</th><td class="u">${esc(r.linked_url)}</td></tr>` : ''}
          <tr><th>Score / comments at capture</th><td>${esc(r.score_at_capture)}${r.comments_at_capture !== '' ? ' / ' + esc(r.comments_at_capture) : ''}</td></tr>
          ${r.matched_terms ? `<tr><th>Matched terms</th><td>${esc(r.matched_terms)}</td></tr>` : ''}
          ${r.reporter_note ? `<tr><th>Reporter note</th><td>${esc(r.reporter_note)}</td></tr>` : ''}
          <tr><th>SHA-256</th><td class="h">${esc(r.sha256 || 'n/a')}</td></tr>
        </table>
        ${r.title ? `<h3>Title</h3><blockquote>${esc(r.title)}</blockquote>` : ''}
        ${r.text ? `<h3>Text</h3><blockquote>${esc(r.text)}</blockquote>` : ''}
      </section>`).join('');
    return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reddit content report ${esc(meta.generatedAt.slice(0, 10))}</title>
<style>
  body{font:13px/1.45 Georgia,"Times New Roman",serif;color:#000;background:#fff;max-width:800px;margin:24px auto;padding:0 16px}
  h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:0 0 8px;border-bottom:1px solid #000;padding-bottom:2px} h3{font-size:12px;margin:10px 0 2px;text-transform:uppercase;letter-spacing:.05em}
  table{border-collapse:collapse;width:100%} th,td{border:1px solid #999;padding:4px 6px;text-align:left;vertical-align:top}
  .kv th{width:30%;background:#f2f2f2;font-weight:600} .u,.h{font-family:Consolas,Menlo,monospace;font-size:11px;word-break:break-all}
  blockquote{margin:0;padding:6px 10px;border-left:3px solid #999;background:#fafafa;white-space:pre-wrap;word-break:break-word}
  .item{margin-top:22px;page-break-inside:avoid} .meta{color:#333} .note{font-size:11px;color:#333;margin-top:24px;border-top:1px solid #999;padding-top:8px}
  .bar{position:sticky;top:0;background:#fff;padding:8px 0;border-bottom:1px solid #ddd;margin-bottom:12px} .bar button{font:inherit;padding:6px 14px}
  @media print{.bar{display:none} body{margin:0}}
</style></head><body>
<div class="bar"><button onclick="window.print()">Print / Save as PDF</button></div>
<h1>Report of public Reddit content</h1>
<div class="meta">Compiled ${esc(meta.generatedAt)} (UTC) · ${recs.length} item${recs.length === 1 ? '' : 's'} · Mention Finder</div>
${meta.summary ? `<h3>Reporter's summary</h3><blockquote>${esc(meta.summary)}</blockquote>` : ''}
<h3>Index</h3>
<table><tr><th>#</th><th>Posted (UTC)</th><th>Community</th><th>Author</th><th>Type</th><th>Link</th></tr>${rows}</table>
${items}
<p class="note">Content was publicly visible on Reddit at the capture time shown and may since have been edited or removed.
Each SHA-256 value covers the ID, link, author, posted time, title, text, linked URL and capture time as recorded, so a copy of this data can be checked for changes.
Compiled by a member of the public using Mention Finder (${esc(meta.toolUrl)}); not an official record from Reddit.</p>
</body></html>`;
  }

  const api = { toRecord, buildRecords, fingerprint, toCSV, toJSON, toText, toPrintableHTML, COLUMNS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MentionReport = api;
})(typeof window !== 'undefined' ? window : globalThis);
