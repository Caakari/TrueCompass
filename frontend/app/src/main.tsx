import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './estilos/base.css'
import './estilos/mapa.css'
import './estilos/folha.css'
import './estilos/telas.css'

ReactDOM.createRoot(document.getElementById('raiz')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
