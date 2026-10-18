// Render exported local HTML only, with one temporary headless browser.
const { chromium } = require(process.argv[2]);
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
(async () => {
  const root = process.argv[3];
  const manifest = JSON.parse(fs.readFileSync(path.join(root,'manifest.json'),'utf8'));
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const page = await browser.newPage();
  const report=[];
  try {
    for (const entry of manifest.pages) {
      await page.setViewportSize({width:entry.width,height:entry.height});
      await page.goto(pathToFileURL(path.join(root,entry.html)).href);
      await page.evaluate(()=>document.fonts.ready);
      const check=await page.evaluate(()=>{
        const clipped=[];
        for (const box of document.querySelectorAll('.box')) {
          let size=parseFloat(getComputedStyle(box).fontSize);
          while ((box.scrollHeight>box.clientHeight+1 || box.scrollWidth>box.clientWidth+1) && size>6) {
            size-=0.5;box.style.fontSize=size+'px';
          }
          if (box.scrollHeight>box.clientHeight+1 || box.scrollWidth>box.clientWidth+1) clipped.push(box.textContent);
        }
        return {boxes:document.querySelectorAll('.box').length,clipped};
      });
      if (check.clipped.length || check.boxes!==entry.text_blocks) throw Error('Manual text layout failed at '+entry.page);
      await page.locator('#page').screenshot({path:path.join(root,entry.image)});
      report.push({page:entry.page,...check});
    }
    fs.writeFileSync(path.join(root,'render-check.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify({rendered:report.length,clipped:0}));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1});
