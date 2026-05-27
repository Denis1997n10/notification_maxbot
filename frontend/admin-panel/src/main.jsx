import React from 'react'
import { createRoot } from 'react-dom/client'

const API = import.meta.env.VITE_ADMIN_API_BASE_URL || ''

function App(){
  const [token,setToken]=React.useState(localStorage.getItem('jwt')||'')
  const [role,setRole]=React.useState('')
  const [msg,setMsg]=React.useState('')
  const [testUserId,setTestUserId]=React.useState('')

  async function login(e){
    e.preventDefault()
    const form=new FormData(e.target)
    const r=await fetch(`${API}/api/v1/admin/auth/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({login:form.get('login'),password:form.get('password')})})
    if(!r.ok){setMsg('Ошибка входа');return}
    const d=await r.json(); localStorage.setItem('jwt',d.token); setToken(d.token)
  }

  async function loadMe(){
    const r=await fetch(`${API}/api/v1/admin/me`,{headers:{Authorization:`Bearer ${token}`}})
    if(r.ok){const d=await r.json(); setRole(d.role||'')}
  }

  async function sendTestNotification(){
    const r=await fetch(`${API}/api/v1/admin/test-notification`,{
      method:'POST',
      headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},
      body:JSON.stringify({user_id:testUserId,subject_title:'Test entrance'})
    })
    const d=await r.json()
    setMsg(d.sent ? 'Test notification sent' : `Test notification failed: ${d.error || 'not sent'}`)
  }

  React.useEffect(()=>{ if(token) loadMe() },[token])
  if(!token) return <form onSubmit={login}><h1>Вход</h1><input name='login' placeholder='Логин'/><input name='password' placeholder='Пароль' type='password'/><button>Войти</button><p>{msg}</p></form>

  const superAdmin = role === 'super_admin'
  return <main style={{fontFamily:'sans-serif'}}>
    <h1>Admin panel</h1><p>Роль: {role || '...'}</p>
    <section><h2>Districts CRUD</h2><button>Создать район</button></section>
    <section><h2>Houses CRUD</h2><button>Создать дом</button></section>
    <section><h2>Entrances CRUD</h2><button>Создать подъезд</button><p>Показывать public_code и URL публичной страницы</p></section>
    <section><h2>Deactivation</h2><button>Деактивировать объект</button></section>
    {superAdmin && <>
      <section><h2>Admin users</h2><button>Управлять администраторами</button></section>
      <section><h2>Feature flags</h2><button>Управлять фичами</button></section>
      <section><h2>Test notification</h2><input value={testUserId} onChange={e=>setTestUserId(e.target.value)} placeholder='MAX user ID'/><button onClick={sendTestNotification}>Send test</button><p>{msg}</p></section>
    </>}
    {!superAdmin && <p>Доступны только назначенные районы.</p>}
  </main>
}

createRoot(document.getElementById('root')).render(<App />)
