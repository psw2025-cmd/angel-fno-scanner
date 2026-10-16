const { chromium } = require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8001',{waitUntil:'load'});
await page.getByLabel('Relay URL').fill('ws://127.0.0.1:8000/ws');
await page.getByLabel('Access code').fill('ci-only-synthetic-test');
await page.getByRole('button',{name:'Connect'}).click();
await page.getByRole('cell',{name:'SYNTHETIC-CE'}).waitFor({timeout:15000});
await page.getByRole('cell',{name:'0.30'}).first().waitFor();
await page.getByRole('cell',{name:'25',exact:true}).first().waitFor({timeout:15000});
console.log('PASS authenticated browser stream, spread=0.30, volume delta=25');
await page.evaluate(()=>window.__level3_test_drop?.());
if(errors.length)throw Error(errors.join(';'));
console.log('PASS browser page errors=0');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
