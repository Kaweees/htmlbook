// Run with 
// node render_html.js url output_file [book_url chapter.html ...]

'use strict';

const fs = require('fs');

// This function runs in the page, after scripts have generated their links.
function preparePdfLinks(bookUrl, chapterFiles) {
  const chapters = new Set(chapterFiles);
  for (const link of document.querySelectorAll('a[href], area[href]')) {
    const href = link.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('//')) continue;
    const target = new URL(href, location.href);
    // Preserve external URLs and links to chapters included in this PDF.
    if (target.protocol !== 'file:') continue;
    const filename = decodeURIComponent(target.pathname.split('/').pop());
    const directory = new URL('.', target).href;
    if (directory === new URL('.', location.href).href && chapters.has(filename)) {
      continue;
    }
    let publishedHref = href;
    if (href.startsWith('file:')) {
      const localDirectory = new URL('.', location.href).pathname;
      if (!target.pathname.startsWith(localDirectory)) {
        throw new Error('File link is outside the book directory: ' + href);
      }
      publishedHref = target.pathname.slice(localDirectory.length) + target.search + target.hash;
    }
    link.setAttribute('href', new URL(publishedHref, bookUrl).href);
  }
}

async function main() {
  let browser;
  try {
    const puppeteer = require('puppeteer');
    browser = await puppeteer.launch();
    const page = await browser.newPage();
    
    const url = process.argv[2];
    const output_file = process.argv[3];
    await page.goto(url);
    // The load event can precede MathJax's asynchronous font loading/typesetting.
    await page.evaluate(async () => {
      await window.mathTypesetPromise;
      await document.fonts.ready;
    });
    if (process.argv[4]) {
      await page.evaluate(preparePdfLinks, process.argv[4], process.argv.slice(5));
    }
    const html = await page.content();
    fs.writeFileSync(output_file, html);
  } catch (err) {
    console.error(err);
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
  }
}

if (require.main === module) main();
module.exports = {preparePdfLinks};
