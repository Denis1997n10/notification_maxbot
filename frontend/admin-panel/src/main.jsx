import React from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const API = import.meta.env.VITE_ADMIN_API_BASE_URL || ''

const errorMessages = {
  forbidden: 'Недостаточно прав для этой операции.',
  not_found: 'Объект больше не доступен. Обновите список.',
  public_code_conflict: 'Такой публичный код уже используется.',
  required_fields: 'Заполните обязательные поля.',
  invalid_public_code: 'Публичный код может содержать только буквы, цифры, "-" и "_".',
  user_id_required: 'Укажите MAX user ID.',
  invalid_credentials: 'Неверный логин или пароль.',
}

function describeError(data, fallback = 'Не удалось выполнить операцию.') {
  return errorMessages[data?.error] || fallback
}

async function jsonRequest(path, options = {}) {
  const response = await fetch(`${API}${path}`, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(describeError(data))
    error.status = response.status
    throw error
  }
  return data
}

function Login({ onAuthenticated }) {
  const [message, setMessage] = React.useState('')
  const [busy, setBusy] = React.useState(false)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    const form = new FormData(event.currentTarget)
    try {
      const data = await jsonRequest('/api/v1/admin/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login: form.get('login'), password: form.get('password') }),
      })
      onAuthenticated(data.token)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  return <div className='login-shell'>
    <div className='login-brand'>
      <span className='brand-mark'>RN</span>
      <p className='eyebrow'>Resident Notifications</p>
      <h1>Управление уведомлениями жителей</h1>
      <p className='muted'>Справочник объектов, публичные страницы и проверка канала MAX в одной панели.</p>
    </div>
    <form className='login-card' onSubmit={submit}>
      <p className='eyebrow'>Администрирование</p>
      <h2>Вход в панель</h2>
      <label>Логин<input name='login' autoComplete='username' required /></label>
      <label>Пароль<input name='password' type='password' autoComplete='current-password' required /></label>
      {message && <p className='alert error' role='alert'>{message}</p>}
      <button className='primary' disabled={busy}>{busy ? 'Входим...' : 'Войти'}</button>
    </form>
  </div>
}

function Empty({ children }) {
  return <p className='empty'>{children}</p>
}

function Dashboard({ token, role, onLogout }) {
  const [districts, setDistricts] = React.useState([])
  const [districtId, setDistrictId] = React.useState('')
  const [houses, setHouses] = React.useState([])
  const [houseId, setHouseId] = React.useState('')
  const [entrances, setEntrances] = React.useState([])
  const [loading, setLoading] = React.useState(true)
  const [busy, setBusy] = React.useState(false)
  const [notice, setNotice] = React.useState('')
  const [error, setError] = React.useState('')
  const [testUserId, setTestUserId] = React.useState('')

  const headers = React.useMemo(() => ({ Authorization: `Bearer ${token}` }), [token])
  const district = districts.find(item => item.id === districtId)
  const house = houses.find(item => item.id === houseId)
  const isSuperAdmin = role === 'super_admin'

  async function request(path, options = {}) {
    try {
      return await jsonRequest(path, { ...options, headers: { ...headers, ...(options.headers || {}) } })
    } catch (requestError) {
      if (requestError.status === 401) {
        onLogout('Сессия истекла. Войдите снова.')
      }
      throw requestError
    }
  }

  async function loadDistricts(preferredId = districtId) {
    const data = await request('/api/v1/admin/districts')
    const items = data.items || []
    setDistricts(items)
    const nextId = items.some(item => item.id === preferredId) ? preferredId : (items[0]?.id || '')
    setDistrictId(nextId)
    if (!nextId) {
      setHouses([])
      setHouseId('')
      setEntrances([])
    }
  }

  async function loadHouses(selectedDistrictId, preferredId = houseId) {
    if (!selectedDistrictId) return
    const data = await request(`/api/v1/admin/districts/${selectedDistrictId}/houses`)
    const items = data.items || []
    setHouses(items)
    const nextId = items.some(item => item.id === preferredId) ? preferredId : (items[0]?.id || '')
    setHouseId(nextId)
    if (!nextId) setEntrances([])
  }

  async function loadEntrances(selectedHouseId) {
    if (!selectedHouseId) return
    const data = await request(`/api/v1/admin/houses/${selectedHouseId}/entrances`)
    setEntrances(data.items || [])
  }

  React.useEffect(() => {
    setLoading(true)
    loadDistricts().catch(requestError => setError(requestError.message)).finally(() => setLoading(false))
  }, [])

  React.useEffect(() => {
    if (districtId) loadHouses(districtId).catch(requestError => setError(requestError.message))
  }, [districtId])

  React.useEffect(() => {
    if (houseId) loadEntrances(houseId).catch(requestError => setError(requestError.message))
  }, [houseId])

  async function mutate(action, successMessage) {
    setBusy(true)
    setNotice('')
    setError('')
    try {
      const result = await action()
      setNotice(successMessage)
      return result
    } catch (requestError) {
      setError(requestError.message)
      return null
    } finally {
      setBusy(false)
    }
  }

  async function createDistrict(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const name = new FormData(formElement).get('name')
    const result = await mutate(
      () => request('/api/v1/admin/districts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      }),
      'Район создан.',
    )
    if (result) {
      formElement.reset()
      await loadDistricts(result.item.id)
    }
  }

  async function createHouse(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = Object.fromEntries(new FormData(formElement).entries())
    const result = await mutate(
      () => request(`/api/v1/admin/districts/${districtId}/houses`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      }),
      'Дом создан.',
    )
    if (result) {
      formElement.reset()
      await loadHouses(districtId, result.item.id)
    }
  }

  async function createEntrance(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = Object.fromEntries(new FormData(formElement).entries())
    const result = await mutate(
      () => request(`/api/v1/admin/houses/${houseId}/entrances`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      }),
      'Подъезд создан.',
    )
    if (result) {
      formElement.reset()
      await loadEntrances(houseId)
    }
  }

  async function deactivate(kind, id, title) {
    if (!window.confirm(`Деактивировать ${title}? Публичный доступ и уведомления по объекту будут отключены.`)) return
    const result = await mutate(
      () => request(`/api/v1/admin/${kind}/${id}/deactivate`, { method: 'PATCH' }),
      'Объект деактивирован.',
    )
    if (!result) return
    if (kind === 'districts') await loadDistricts('')
    if (kind === 'houses') await loadHouses(districtId, '')
    if (kind === 'entrances') await loadEntrances(houseId)
  }

  async function sendTestNotification(event) {
    event.preventDefault()
    const result = await mutate(
      () => request('/api/v1/admin/test-notification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: testUserId, subject_title: 'Тестовое уведомление платформы' }),
      }),
      'Тестовое уведомление отправлено.',
    )
    if (result && !result.sent) {
      setNotice('')
      setError('MAX не подтвердил отправку. Проверьте токен бота и user ID.')
    }
  }

  return <div className='app-shell'>
    <header className='topbar'>
      <div className='brand'><span className='brand-mark compact'>RN</span><div><strong>Resident Notifications</strong><small>Панель управления</small></div></div>
      <div className='profile'><span className='role'>{isSuperAdmin ? 'Super admin' : 'District admin'}</span><button className='ghost' onClick={() => onLogout()}>Выйти</button></div>
    </header>

    <main className='workspace'>
      <section className='hero'>
        <div>
          <p className='eyebrow'>Каталог объектов</p>
          <h1>Управление подписками и адресами</h1>
          <p className='muted'>Создавайте объекты справочника, выдавайте публичные ссылки для QR и проверяйте доставку в MAX.</p>
        </div>
        <div className='metrics'>
          <div><strong>{districts.length}</strong><span>районов</span></div>
          <div><strong>{houses.length}</strong><span>домов</span></div>
          <div><strong>{entrances.length}</strong><span>подъездов</span></div>
        </div>
      </section>

      {(notice || error) && <div className={`alert ${error ? 'error' : 'success'}`} role='status'>{error || notice}</div>}

      <div className='directory-grid' aria-busy={busy || loading}>
        <section className='panel'>
          <div className='panel-title'><h2>Районы</h2>{isSuperAdmin && <span className='tag'>создание доступно</span>}</div>
          {loading ? <Empty>Загрузка...</Empty> : districts.length === 0 ? <Empty>Районов пока нет.</Empty> : <ul className='select-list'>
            {districts.map(item => <li key={item.id} className={item.id === districtId ? 'selected' : ''}>
              <button className='select' onClick={() => setDistrictId(item.id)}>{item.name}</button>
              <button className='danger-link' onClick={() => deactivate('districts', item.id, `район "${item.name}"`)} disabled={busy}>Отключить</button>
            </li>)}
          </ul>}
          {isSuperAdmin && <form className='edit-form' onSubmit={createDistrict}>
            <h3>Новый район</h3>
            <input name='name' placeholder='Название района' required />
            <button className='primary' disabled={busy}>Добавить район</button>
          </form>}
        </section>

        <section className='panel'>
          <div className='panel-title'><h2>Дома</h2><span className='tag'>{district?.name || 'выберите район'}</span></div>
          {!district ? <Empty>Сначала выберите район.</Empty> : houses.length === 0 ? <Empty>Домов пока нет.</Empty> : <ul className='select-list'>
            {houses.map(item => <li key={item.id} className={item.id === houseId ? 'selected' : ''}>
              <button className='select' onClick={() => setHouseId(item.id)}>
                <strong>{item.street}, {item.house_number}{item.building ? ` к${item.building}` : ''}</strong>
                <small>{item.city}</small>
              </button>
              <button className='danger-link' onClick={() => deactivate('houses', item.id, 'дом')} disabled={busy}>Отключить</button>
            </li>)}
          </ul>}
          {district && <form className='edit-form' onSubmit={createHouse}>
            <h3>Новый дом</h3>
            <div className='split'><input name='city' placeholder='Город' required /><input name='street' placeholder='Улица' required /></div>
            <div className='split small'><input name='house_number' placeholder='Дом' required /><input name='building' placeholder='Корпус' /></div>
            <button className='primary' disabled={busy}>Добавить дом</button>
          </form>}
        </section>

        <section className='panel'>
          <div className='panel-title'><h2>Подъезды</h2><span className='tag'>{house ? house.house_number : 'выберите дом'}</span></div>
          {!house ? <Empty>Сначала выберите дом.</Empty> : entrances.length === 0 ? <Empty>Подъездов пока нет.</Empty> : <ul className='select-list entrances'>
            {entrances.map(item => <li key={item.id}>
              <div className='entrance-details'>
                <strong>Подъезд {item.entrance_number}</strong>
                <small>Код: {item.public_code}</small>
                {item.public_url && <a href={item.public_url} target='_blank' rel='noreferrer'>Открыть публичную страницу</a>}
              </div>
              <button className='danger-link' onClick={() => deactivate('entrances', item.id, 'подъезд')} disabled={busy}>Отключить</button>
            </li>)}
          </ul>}
          {house && <form className='edit-form' onSubmit={createEntrance}>
            <h3>Новый подъезд</h3>
            <div className='split'><input name='entrance_number' placeholder='Номер' required /><input name='public_code' placeholder='Публичный код (авто)' /></div>
            <input name='regioncity_external_ref' placeholder='RegionCity mapObjectID (опционально)' />
            <button className='primary' disabled={busy}>Добавить подъезд</button>
          </form>}
        </section>
      </div>

      {isSuperAdmin && <section className='panel notification-panel'>
        <div>
          <p className='eyebrow'>Проверка интеграции</p>
          <h2>Тестовое уведомление MAX</h2>
          <p className='muted'>Отправляет диагностическое событие выбранному пользователю без создания подписки.</p>
        </div>
        <form className='notification-form' onSubmit={sendTestNotification}>
          <input value={testUserId} onChange={event => setTestUserId(event.target.value)} placeholder='MAX user ID' required />
          <button className='primary' disabled={busy}>Отправить тест</button>
        </form>
      </section>}
    </main>
  </div>
}

function App() {
  const [token, setToken] = React.useState(localStorage.getItem('jwt') || '')
  const [role, setRole] = React.useState('')
  const [sessionError, setSessionError] = React.useState('')
  const [validating, setValidating] = React.useState(Boolean(token))

  function logout(message = '') {
    localStorage.removeItem('jwt')
    setToken('')
    setRole('')
    setSessionError(message)
  }

  function authenticated(nextToken) {
    localStorage.setItem('jwt', nextToken)
    setToken(nextToken)
    setSessionError('')
  }

  React.useEffect(() => {
    if (!token) {
      setValidating(false)
      return
    }
    setValidating(true)
    jsonRequest('/api/v1/admin/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(data => setRole(data.role || ''))
      .catch(() => logout('Сессия истекла. Войдите снова.'))
      .finally(() => setValidating(false))
  }, [token])

  if (!token) return <><Login onAuthenticated={authenticated} />{sessionError && <p className='session-error'>{sessionError}</p>}</>
  if (validating || !role) return <div className='loading-page'>Проверяем сессию...</div>
  return <Dashboard token={token} role={role} onLogout={logout} />
}

createRoot(document.getElementById('root')).render(<App />)
