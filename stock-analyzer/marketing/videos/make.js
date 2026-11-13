// Rendu image par image (25 i/s) puis assemblage MP4 vertical 1080×1920
const { chromium } = require('playwright'); const fs = require('fs'); const { execSync } = require('child_process')
;(async () => {
  const [html, out] = process.argv.slice(2); const dir = out + '.frames'; fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir)
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } })
  await p.goto('file://' + html); await p.evaluate(() => document.fonts.ready)
  const total = await p.evaluate(() => window.TOTAL), fps = 25
  for (let i = 0; i < total * fps; i++) {
    await p.evaluate((t) => window.render(t), i / fps)
    await p.screenshot({ path: `${dir}/${String(i).padStart(5, '0')}.jpg`, type: 'jpeg', quality: 92 })
  }
  await b.close()
  execSync(`ffmpeg -y -loglevel error -framerate ${fps} -i ${dir}/%05d.jpg -f lavfi -t ${total} -i anullsrc=r=44100:cl=stereo -shortest -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -movflags +faststart ${out}`)
  fs.rmSync(dir, { recursive: true, force: true }); console.log('ok', out)
})()
