const assert = require('node:assert/strict');
const test = require('node:test');
const vm = require('node:vm');
const {preparePdfLinks} = require('./render_html.js');

test('PDF links keep included chapters and resolve other local links to the published book', () => {
  const hrefs = [
    '#equation', 'intro.html#section1', './intro.html?query=1#section2',
    'data/movie.html', 'python/index.html', 'segmentation/example.py',
    'draft.html#section', '/data/plot.html',
    'https://example.net/paper.pdf', 'mailto:author@example.org',
    '//example.net/figure.png', '',
    '../intro.html', 'file:///tmp/rendered/data/movie.html',
  ];
  const links = hrefs.map(href => ({
    href,
    getAttribute() { return this.href; },
    setAttribute(_name, value) { this.href = value; },
  }));
  const ctx = vm.createContext({
    URL,
    location: {href: 'file:///tmp/rendered/index.html'},
    document: {querySelectorAll: () => links},
  });
  vm.runInContext(`(${preparePdfLinks.toString()})('https://book.example/notes/', ['index.html', 'intro.html'])`, ctx);
  assert.deepEqual(links.map(link => link.href), [
    '#equation', 'intro.html#section1', './intro.html?query=1#section2',
    'https://book.example/notes/data/movie.html',
    'https://book.example/notes/python/index.html',
    'https://book.example/notes/segmentation/example.py',
    'https://book.example/notes/draft.html#section',
    'https://book.example/data/plot.html',
    'https://example.net/paper.pdf', 'mailto:author@example.org',
    '//example.net/figure.png', '',
    'https://book.example/intro.html', 'https://book.example/notes/data/movie.html',
  ]);
});
