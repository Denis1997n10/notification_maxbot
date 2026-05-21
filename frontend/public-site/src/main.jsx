import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, useParams } from 'react-router-dom'

const API = import.meta.env.VITE_PUBLIC_API_BASE_URL || ''

function EntrancePage() {
  const { publicCode } = useParams()
  const [state, setState] = React.useState({ loading: true, error: '', data: null })

  const load = React.useCallback(async () => {
    setState({ loading: true, error: '', data: null })
    try {
      const r = await fetch(`${API}/api/v1/public/entrances/${publicCode}`)
      if (r.status === 404 || r.status === 410) {
        setState({ loading: false, error: 'unavailable', data: null }); return
      }
      if (!r.ok) throw new Error('api')
      const data = await r.json()
      setState({ loading: false, error: '', data })
    } catch {
      setState({ loading: false, error: 'retry', data: null })
    }
  }, [publicCode])

  React.useEffect(() => { load() }, [load])

  if (state.loading) return <p>Загрузка...</p>
  if (state.error === 'unavailable') return <p>Страница подъезда недоступна.</p>
  if (state.error) return <div><p>Не удалось загрузить данные. Попробуйте снова.</p><button onClick={load}>Повторить</button></div>

  const d = state.data || {}
  const events = (d.events || []).slice(0, 10)
  return <main style={{maxWidth: 760, margin:'0 auto', fontFamily:'sans-serif'}}>
    <h1>{d.district} / {d.house} / {d.entrance}</h1>
    <p>{d.address}</p>
    <a href={d.max_bot_link || '#'}>Получать уведомления в MAX</a>
    <h2>Последние уборки</h2>
    <ul>{events.map((e, i) => <li key={e.id || i}><b>{e.title}</b><div>{e.description}</div><small>{e.occurred_at}</small>{Array.isArray(e.images)&&e.images.length>0?<div>{e.images.map((img,j)=><img key={j} src={img.url||img} alt='' width='120'/>)}</div>:null}</li>)}</ul>
  </main>
}

createRoot(document.getElementById('root')).render(<BrowserRouter><Routes><Route path='/e/:publicCode' element={<EntrancePage />} /></Routes></BrowserRouter>)
