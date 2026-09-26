/* Mention Finder — spelling-variant engine.
 * Turns a name or website ("bestbuy.com", "Trader Joe's") into the ways people
 * actually type it on Reddit: bare name, with/without TLD, spaced/joined/hyphenated,
 * "dot com", initials, and common misspellings.
 * Works in the browser (window.MentionVariants) and in Node (module.exports).
 */
(function (root) {
  'use strict';

  const TLDS = ['com', 'net', 'org', 'io', 'co', 'app', 'ai', 'us', 'gov', 'edu', 'info', 'biz', 'me', 'tv', 'co.uk', 'ca', 'de'];
  const ALT_TLDS = ['com', 'net', 'org', 'co', 'io'];
  const STOP = new Set(['the', 'a', 'an', 'of', 'and', '&', 'for', 'in', 'on', 'at', 'to']);
  const VOWELS = 'aeiou';
  // Sound-alike swaps people make when spelling from memory.
  const PHONETIC = [
    ['ph', 'f'], ['ck', 'k'], ['ck', 'c'], ['c', 'k'], ['s', 'z'], ['ie', 'ei'], ['y', 'i'],
    ['ee', 'ea'], ['oo', 'u'], ['x', 'ks'], ['qu', 'kw'], ['er', 'or'], ['or', 'er'],
    ['ai', 'ay'], ['tion', 'sion'], ['able', 'ible'], ['ence', 'ance'], ['ou', 'ow'],
  ];

  /** Parse raw input into a domain (if any), words and the compact core name. */
  function parse(input) {
    let raw = String(input || '').trim();
    let s = raw.toLowerCase()
      .replace(/^[a-z]+:\/\//, '')
      .replace(/^www\d?\./, '')
      .replace(/[/?#].*$/, '');

    // "example dot com" -> "example.com"; drop sentence punctuation that dictation adds
    s = s.replace(/\s+dot\s+/g, '.').replace(/[.!?,;:]+$/, '').trim();

    let domain = null, tld = null, label = s;
    const tldMatch = s.match(/^([a-z0-9][a-z0-9.-]*?)\.((?:co\.uk)|[a-z]{2,12})$/);
    if (tldMatch && !/\s/.test(s)) {
      domain = s;
      label = tldMatch[1].split('.').pop(); // drop subdomains: "shop.example" -> "example"
      tld = tldMatch[2];
    } else {
      // "best buy.com" (often from speech): the words form the name, joined they form the domain
      const spaced = s.match(new RegExp(`^([a-z0-9][a-z0-9 '’&-]*?)\\s*\\.\\s*(${TLDS.map(t => t.replace('.', '\\.')).join('|')})$`));
      if (spaced) {
        label = spaced[1];
        tld = spaced[2];
        domain = label.replace(/[^a-z0-9&-]/g, '') + '.' + tld;
      }
    }

    const words = label
      .replace(/['’]/g, '')
      .split(/[\s\-_.]+/)
      .map(w => w.replace(/[^a-z0-9&]/g, ''))
      .filter(Boolean);
    const core = words.join('');
    return { raw, domain, tld, label, words, core, hasApostrophe: /['’]/.test(raw) };
  }

  /**
   * Realistic single-mistake misspellings, each with a plausibility score.
   * People almost never fumble the first letter, so edits start at index 1.
   */
  function typoCandidates(word) {
    const out = new Map();
    const put = (t, kind, score) => {
      if (t === word) return;
      const prev = out.get(t);
      if (!prev || prev.score < score) out.set(t, { t, kind, score });
    };
    const n = word.length;
    const isL = c => /[a-z]/.test(c);
    for (let i = 1; i < n; i++) {
      const c = word[i];
      if (!isL(c)) continue;
      // collapsed double letter ("reddit" -> "redit") — the most common slip
      if (word[i - 1] === c) put(word.slice(0, i) + word.slice(i + 1), 'double letter', 9);
      // doubled a consonant that sits between vowels ("chewy" -> "chewwy" is rare, "amazon" -> "ammazon" too)
      else if (!VOWELS.includes(c) && VOWELS.includes(word[i - 1]) && VOWELS.includes(word[i + 1] || '')) {
        put(word.slice(0, i) + c + word.slice(i), 'double letter', 5);
      }
      // swapped neighbours, not at the very end of short words
      if (i < n - 1 && isL(word[i + 1]) && word[i] !== word[i + 1]) {
        put(word.slice(0, i) + word[i + 1] + word[i] + word.slice(i + 2), 'swapped letters', i < n - 2 ? 7 : 6);
      }
      // dropped letter — dropped vowels in the middle are the usual culprit
      if (i < n - 1 && word[i - 1] !== c) {
        put(word.slice(0, i) + word.slice(i + 1), 'missing letter', VOWELS.includes(c) ? 6 : 4);
      }
    }
    for (const [a, b] of PHONETIC) {
      let idx = word.indexOf(a, 1);
      while (idx !== -1) {
        put(word.slice(0, idx) + b + word.slice(idx + a.length), 'sounds-alike', a.length > 1 ? 8 : 3);
        idx = word.indexOf(a, idx + 1);
      }
    }
    return [...out.values()].sort((x, y) => y.score - x.score);
  }

  /**
   * Build the variant list. Each entry: { text, kind, on } where `on` says whether it
   * should be searched by default. Ordered most-important first.
   */
  function generate(input, opts) {
    opts = Object.assign({ maxTypos: 14 }, opts);
    const p = parse(input);
    if (!p.core) return { parsed: p, variants: [] };

    const list = [];
    const seen = new Set();
    const add = (text, kind, on = true) => {
      text = String(text).trim().toLowerCase();
      if (!text || text.length < 2 || seen.has(text)) return;
      seen.add(text);
      list.push({ text, kind, on });
    };

    const { words, core, domain, tld } = p;
    const multi = words.length > 1;
    const spaced = words.join(' ');

    // Exact forms
    if (domain) add(domain, 'website');
    add(multi ? spaced : core, 'name');
    if (multi) {
      add(core, 'joined');
      add(words.join('-'), 'hyphenated');
    }
    if (p.hasApostrophe && multi) {
      // "trader joe's" -> keep the possessive form people write
      add(p.label.replace(/’/g, "'").replace(/\s+/g, ' '), 'name');
    }

    // Website forms
    const baseTld = tld || 'com';
    add(`${core}.${baseTld}`, 'website');
    add(`www.${core}.${baseTld}`, 'website', false);
    add(`${core} dot ${baseTld}`, 'website');
    if (multi) add(`${words.join('-')}.${baseTld}`, 'website', false);
    for (const t of ALT_TLDS) if (t !== baseTld) add(`${core}.${t}`, 'other domain', false);

    // Initials for multi-word names ("Best Buy" -> "bb") — ambiguous, off by default
    const sig = words.filter(w => !STOP.has(w));
    if (sig.length >= 2) {
      add(sig.map(w => w[0]).join(''), 'abbreviation', false);
      if (sig.length >= 3) add(sig.map(w => w[0]).join('.') + '.', 'abbreviation', false);
    }

    // Plural / possessive for single names
    if (!multi && core.length >= 4 && /[a-z]$/.test(core)) {
      add(core.endsWith('s') ? core.slice(0, -1) : core + 's', 'plural', false);
    }

    // Misspellings — only meaningful for names long enough not to collide with real words
    if (core.length >= 5) {
      const typos = typoCandidates(core);
      if (multi) {
        // misspell one word but keep the phrase: "trader joes" -> "trader jeos"
        words.forEach((w, i) => {
          if (w.length < 5) return;
          typoCandidates(w).slice(0, 2).forEach(c => {
            const ws = words.slice(); ws[i] = c.t;
            typos.push({ t: ws.join(' '), kind: c.kind, score: c.score - 1 });
          });
        });
        typos.sort((x, y) => y.score - x.score);
      }
      let n = 0;
      for (const { t, kind, score } of typos) {
        if (n >= opts.maxTypos) break;
        const before = list.length;
        // The most plausible handful are searched by default; the rest are one click away.
        add(t, kind, n < 5 && score >= 6);
        if (list.length > before) n++;
      }
    }

    return { parsed: p, variants: list };
  }

  /** Reddit search terms: quote anything with spaces or punctuation. */
  function toSearchTerm(v) {
    return /^[a-z0-9]+$/.test(v) ? v : `"${v.replace(/"/g, '')}"`;
  }

  /** Pack terms into OR-queries under Reddit's practical query length. */
  function batchQueries(terms, maxLen) {
    maxLen = maxLen || 400;
    const batches = [];
    let cur = [];
    let len = 0;
    for (const term of terms) {
      const t = toSearchTerm(term);
      const extra = (cur.length ? 4 : 0) + t.length;
      if (cur.length && len + extra > maxLen) {
        batches.push(cur);
        cur = []; len = 0;
      }
      cur.push(t);
      len += (cur.length > 1 ? 4 : 0) + t.length;
    }
    if (cur.length) batches.push(cur);
    return batches.map(b => b.join(' OR '));
  }

  /** Edit distance counting a swap of neighbouring letters as one edit; stops early past `max`. */
  function levenshtein(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    let prev2 = null;
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const cur = [i];
      let rowMin = i;
      for (let j = 1; j <= b.length; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
        if (prev2 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
          cur[j] = Math.min(cur[j], prev2[j - 2] + 1);
        }
        rowMin = Math.min(rowMin, cur[j]);
      }
      if (rowMin > max) return max + 1;
      prev2 = prev;
      prev = cur;
    }
    return prev[b.length];
  }

  const escapeRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  /**
   * Find which variants appear in a piece of text. Also catches near-misses of the
   * core name we didn't list explicitly (edit distance 1, or 2 for long names).
   * Returns [{ term, index, length, fuzzy }].
   */
  function findMatches(text, variants, core) {
    const lower = String(text || '').toLowerCase();
    const hits = [];
    const taken = [];
    const overlaps = (i, len) => taken.some(([a, b]) => i < b && i + len > a);

    const sorted = variants.slice().sort((a, b) => b.length - a.length);
    for (const v of sorted) {
      // Letters/digits must not continue on either side, so "bb" won't match inside "hobby".
      const re = new RegExp(`(^|[^a-z0-9])(${escapeRe(v)})(?=$|[^a-z0-9])`, 'g');
      let m;
      while ((m = re.exec(lower))) {
        const idx = m.index + m[1].length;
        if (!overlaps(idx, v.length)) {
          hits.push({ term: v, index: idx, length: v.length, fuzzy: false });
          taken.push([idx, idx + v.length]);
        }
        re.lastIndex = idx + 1;
      }
    }

    if (core && core.length >= 5) {
      const max = core.length >= 9 ? 2 : 1;
      const toks = [];
      const re = /[a-z0-9][a-z0-9'-]*/g;
      let m;
      while ((m = re.exec(lower))) toks.push({ i: m.index, s: m[0], c: m[0].replace(/['-]/g, '') });
      const tryHit = (idx, len, compact) => {
        if (overlaps(idx, len) || hits.length > 40) return;
        if (Math.abs(compact.length - core.length) > max) return;
        if (levenshtein(compact, core, max) <= max) {
          hits.push({ term: lower.slice(idx, idx + len), index: idx, length: len, fuzzy: true });
          taken.push([idx, idx + len]);
        }
      };
      for (let k = 0; k < toks.length; k++) {
        const a = toks[k], b = toks[k + 1];
        // "Best Buy" / "best-buy" written as two words when the name is one ("bestbuy")
        if (b && /^\s+$/.test(lower.slice(a.i + a.s.length, b.i))) tryHit(a.i, b.i + b.s.length - a.i, a.c + b.c);
        tryHit(a.i, a.s.length, a.c);
      }
    }
    return hits.sort((a, b) => a.index - b.index);
  }

  /**
   * Parse a search like  bestbuy.com AND "tv sale" NOT refund OR "best buy"  into OR-groups.
   * In each group, the words before the first operator are the name we expand into spellings.
   * AND terms must also appear, and NOT terms (or -word) must not. Operators are upper-case,
   * so names like "Barnes and Noble" keep working. The symbols | & and - also work.
   */
  function parseQuery(input) {
    const tokens = [];
    const re = /(-?)"([^"]*)"?|(\S+)/g;
    let m;
    const src = String(input || '').replace(/[“”]/g, '"');
    while ((m = re.exec(src))) {
      if (m[2] !== undefined) {
        if (m[1]) tokens.push({ op: 'NOT' });
        if (m[2].trim()) tokens.push({ text: m[2].trim(), quoted: true });
        continue;
      }
      const w = m[3];
      if (w === 'OR' || w === '|' || w === '||') tokens.push({ op: 'OR' });
      else if (w === 'AND' || w === '&' || w === '&&' || w === '+') tokens.push({ op: 'AND' });
      else if (w === 'NOT' || w === '-') tokens.push({ op: 'NOT' });
      else if (/^-["\w]/.test(w) && w.length > 1) { tokens.push({ op: 'NOT' }); tokens.push({ text: w.slice(1).replace(/"/g, ''), quoted: false }); }
      else tokens.push({ text: w, quoted: false });
    }

    const groups = [];
    let g = null, mode = 'main', mainParts = [];
    const close = () => {
      if (g) { g.main = mainParts.join(' ').trim(); if (g.main || g.also.length) groups.push(g); }
      g = { main: '', also: [], not: [] }; mode = 'main'; mainParts = [];
    };
    close();
    for (const t of tokens) {
      if (t.op === 'OR') { close(); continue; }
      if (t.op === 'AND') { mode = 'and'; continue; }
      if (t.op === 'NOT') { mode = 'not'; continue; }
      const text = t.text.toLowerCase();
      if (mode === 'main') mainParts.push(t.text);
      else if (mode === 'not') { g.not.push(text); mode = 'and'; } // NOT covers one word or "phrase"
      else g.also.push(text);
    }
    close();
    // A group like  AND wine  with no name: promote its first required term to be the name.
    groups.forEach(gr => { if (!gr.main && gr.also.length) gr.main = gr.also.shift(); });
    return groups.filter(gr => gr.main);
  }

  /** True when `term` appears in `text` as whole word(s). */
  function containsTerm(text, term) {
    return new RegExp(`(^|[^a-z0-9])${escapeRe(term)}(?=$|[^a-z0-9])`).test(String(text || '').toLowerCase());
  }

  /**
   * Turn a spoken search into query syntax:
   *   "best buy dot com but not refunds"  -> best buy dot com NOT refunds
   *   "chewy or petco"                    -> chewy OR petco
   *   "quote price match end quote"       -> "price match"
   * A spoken "and" between two capitalised words ("Barnes and Noble") stays part of the name.
   */
  function speechToQuery(transcript) {
    const words = String(transcript || '').replace(/[,;!?]+/g, ' ').replace(/\.+(\s|$)/g, '$1').trim().split(/\s+/).filter(Boolean);
    const out = [];
    let inQuote = false;
    const lw = i => (words[i] || '').toLowerCase();
    const cap = w => /^[A-Z0-9]/.test(w || '');
    for (let i = 0; i < words.length; i++) {
      const w = lw(i);
      if (w === 'quote' && !inQuote) { out.push('"'); inQuote = true; continue; }
      if (inQuote && (w === 'unquote' || ((w === 'end' || w === 'close') && lw(i + 1) === 'quote'))) {
        if (w !== 'unquote') i++;
        out.push('"'); inQuote = false; continue;
      }
      if (inQuote) { out.push(words[i]); continue; }
      if ((w === 'but' || w === 'and') && lw(i + 1) === 'not') { out.push('NOT'); i++; continue; }
      if (w === 'but' && lw(i + 1) === 'without') { out.push('NOT'); i++; continue; }
      if (['not', 'without', 'excluding', 'except', 'minus'].includes(w) && out.length) { out.push('NOT'); continue; }
      if (w === 'or') { out.push('OR'); continue; }
      if (w === 'and' && lw(i + 1) === 'also') { out.push('AND'); i++; continue; }
      if (w === 'plus' && out.length) { out.push('AND'); continue; }
      if (w === 'and') {
        out.push(cap(words[i - 1]) && cap(words[i + 1]) ? 'and' : 'AND');
        continue;
      }
      out.push(words[i]);
    }
    if (inQuote) out.push('"');
    // Spoken words after AND / NOT belong together: "without two buck chuck" -> NOT "two buck chuck"
    const grouped = [];
    for (let i = 0; i < out.length; i++) {
      grouped.push(out[i]);
      if (out[i] !== 'AND' && out[i] !== 'NOT') continue;
      let j = i + 1;
      while (j < out.length && !['AND', 'OR', 'NOT', '"'].includes(out[j])) j++;
      if (j - i > 2) { grouped.push('"' + out.slice(i + 1, j).join(' ') + '"'); i = j - 1; }
    }
    return grouped.join(' ').replace(/" (.*?) "/g, '"$1"').replace(/\s+/g, ' ').trim();
  }

  const api = { parse, generate, parseQuery, containsTerm, speechToQuery, toSearchTerm, batchQueries, findMatches, levenshtein, TLDS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MentionVariants = api;
})(typeof window !== 'undefined' ? window : globalThis);
