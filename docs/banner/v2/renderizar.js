// Renderiza o banner em PDF vetorial de 90 x 120 cm e confere o encaixe:
// cada coluna tem de terminar ANTES do rodapé (senão invade).
const path = require('path')
const { chromium } = require('playwright')
;(async () => {
  const [html, pdf] = process.argv.slice(2).map((a) => path.resolve(a))
  const b = await chromium.launch(); const p = await b.newPage()
  await p.goto('file://' + html); await p.waitForTimeout(1500)
  await p.evaluate(() => document.fonts.ready)
  const m = await p.evaluate(() => {
    const cm = (v) => +(v / 37.7953).toFixed(1)
    const rodape = cm(document.querySelector('.rodape').getBoundingClientRect().top)
    const colunas = [...document.querySelectorAll('.col')].map((c) => cm(c.lastElementChild.getBoundingClientRect().bottom))
    const cab = cm(document.querySelector('.autores').getBoundingClientRect().bottom)
    const fontes = [...document.fonts].filter((f) => f.status === 'loaded').length
    const tamanhos = {}
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest('svg')) continue
      if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue
      const pt = Math.round(parseFloat(getComputedStyle(el).fontSize) * 0.75)
      tamanhos[pt] = (tamanhos[pt] || 0) + 1
    }
    return { cabecalho_texto_fim: cab, colunas_fim: colunas, rodape_inicio: rodape, fontes_carregadas: fontes, tamanhos_pt: tamanhos }
  })
  console.log(JSON.stringify(m))
  for (const [i, fim] of m.colunas_fim.entries()) if (fim > m.rodape_inicio - 1) console.log(`  <<< coluna ${i + 1} invade o rodapé (${fim} cm)`)
  await p.pdf({ path: pdf, width: '90cm', height: '120cm', printBackground: true, preferCSSPageSize: true })
  await b.close()
})()
