// Renderiza o banner: PDF vetorial 90x120 cm + medidas para conferir que nada estoura.
const { chromium } = require('playwright')
;(async () => {
  const path = require('path')
  const [html, pdf] = process.argv.slice(2).map((a) => path.resolve(a))
  const b = await chromium.launch(); const p = await b.newPage()
  await p.goto('file://' + html); await p.waitForTimeout(1500)
  await p.evaluate(() => document.fonts.ready)
  const m = await p.evaluate(() => {
    const cm = (v) => (v / 37.7953).toFixed(1)
    const r = (s) => document.querySelector(s).getBoundingClientRect()
    return { conteudo_fim: cm(r('.conteudo').bottom), rodape_inicio: cm(r('.rodape').top), numeros_fim: cm(r('.numeros').bottom),
             como_inicio: cm(r('#como').top), marca_fim: cm(r('.marca').bottom), celular_fim: cm(r('.celular').bottom),
             fontes: [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family + f.weight).join(',') }
  })
  console.log(JSON.stringify(m))
  await p.pdf({ path: pdf, width: '90cm', height: '120cm', printBackground: true, preferCSSPageSize: true })
  await b.close()
})()
