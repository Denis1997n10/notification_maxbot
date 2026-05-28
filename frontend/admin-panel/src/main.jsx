import React from 'react'
import { createRoot } from 'react-dom/client'
import QRCode from 'qrcode'
import * as XLSX from 'xlsx'
import './styles.css'

const API = import.meta.env.VITE_ADMIN_API_BASE_URL || ''

const errorMessages = {
  forbidden: 'Недостаточно прав для этой операции.',
  not_found: 'Объект больше не доступен. Обновите список.',
  public_code_conflict: 'Такой публичный код уже используется.',
  login_conflict: 'Администратор с таким логином уже существует.',
  required_fields: 'Заполните обязательные поля.',
  invalid_public_code: 'Публичный код может содержать только буквы, цифры, "-" и "_".',
  invalid_admin_user: 'Укажите логин, роль и пароль длиной минимум 12 символов.',
  district_required: 'Для районного администратора выберите хотя бы один район.',
  cannot_deactivate_self: 'Нельзя деактивировать собственную учётную запись.',
  city_required: 'Сначала привяжите район к городу.',
  user_id_required: 'Укажите MAX user ID.',
  invalid_credentials: 'Неверный логин или пароль.',
  import_has_errors: 'В файле есть ошибки. Исправьте строки перед импортом.',
  regioncity_unavailable: 'RegionCity временно недоступен или вернул ошибку.',
}

const ADDRESS_COLUMNS = [
  'city',
  'district',
  'street',
  'house_number',
  'building',
  'entrance_number',
  'public_code',
  'regioncity_map_object_id',
]

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
      <button type='submit' className='primary' disabled={busy}>{busy ? 'Входим...' : 'Войти'}</button>
    </form>
  </div>
}

function Empty({ children }) {
  return <p className='empty'>{children}</p>
}

function QrCodeImage({ value }) {
  const [src, setSrc] = React.useState('')

  React.useEffect(() => {
    let active = true
    if (!value) {
      setSrc('')
      return undefined
    }
    QRCode.toDataURL(value, { margin: 1, width: 132 })
      .then((dataUrl) => {
        if (active) setSrc(dataUrl)
      })
      .catch(() => {
        if (active) setSrc('')
      })
    return () => {
      active = false
    }
  }, [value])

  if (!value || !src) return null
  return <img className='qr-code small' src={src} alt='QR-код MAX' />
}

function downloadWorkbook(filename, rows) {
  const worksheet = XLSX.utils.json_to_sheet(rows.length ? rows : [Object.fromEntries(ADDRESS_COLUMNS.map((key) => [key, '']))], {
    header: ADDRESS_COLUMNS,
  })
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'addresses')
  XLSX.writeFile(workbook, filename)
}

async function readWorkbookRows(file) {
  const buffer = await file.arrayBuffer()
  const workbook = XLSX.read(buffer)
  const sheet = workbook.Sheets[workbook.SheetNames[0]]
  return XLSX.utils.sheet_to_json(sheet, { defval: '' })
}

function Dashboard({ token, principal, onLogout }) {
  const [cities, setCities] = React.useState([])
  const [cityId, setCityId] = React.useState('')
  const [districts, setDistricts] = React.useState([])
  const [districtId, setDistrictId] = React.useState('')
  const [streets, setStreets] = React.useState([])
  const [streetId, setStreetId] = React.useState('')
  const [houses, setHouses] = React.useState([])
  const [houseId, setHouseId] = React.useState('')
  const [entrances, setEntrances] = React.useState([])
  const [unassignedDistricts, setUnassignedDistricts] = React.useState([])
  const [allDistricts, setAllDistricts] = React.useState([])
  const [residents, setResidents] = React.useState([])
  const [admins, setAdmins] = React.useState([])
  const [newAdminRole, setNewAdminRole] = React.useState('district_admin')
  const [testUserId, setTestUserId] = React.useState('')
  const [importRows, setImportRows] = React.useState([])
  const [importPreview, setImportPreview] = React.useState([])
  const [newEntrance, setNewEntrance] = React.useState({ entrance_number: '', public_code: '', regioncity_external_ref: '' })
  const [regionCityCandidates, setRegionCityCandidates] = React.useState([])
  const [regionCityBusy, setRegionCityBusy] = React.useState(false)
  const [loading, setLoading] = React.useState(true)
  const [busy, setBusy] = React.useState(false)
  const [notice, setNotice] = React.useState('')
  const [error, setError] = React.useState('')

  const headers = React.useMemo(() => ({ Authorization: `Bearer ${token}` }), [token])
  const city = cities.find(item => item.id === cityId)
  const district = districts.find(item => item.id === districtId)
  const street = streets.find(item => item.id === streetId)
  const house = houses.find(item => item.id === houseId)
  const isSuperAdmin = principal.role === 'super_admin'

  async function request(path, options = {}) {
    try {
      return await jsonRequest(path, { ...options, headers: { ...headers, ...(options.headers || {}) } })
    } catch (requestError) {
      if (requestError.status === 401) onLogout('Сессия истекла. Войдите снова.')
      throw requestError
    }
  }

  async function loadCities(preferredId = cityId) {
    const data = await request('/api/v1/admin/cities')
    const items = data.items || []
    setCities(items)
    const nextId = items.some(item => item.id === preferredId) ? preferredId : (items[0]?.id || '')
    setCityId(nextId)
    if (!nextId) {
      setDistricts([])
      setDistrictId('')
      setStreets([])
      setStreetId('')
      setHouses([])
      setHouseId('')
      setEntrances([])
    }
  }

  async function loadDistricts(selectedCityId, preferredId = districtId) {
    if (!selectedCityId) return
    const data = await request(`/api/v1/admin/cities/${selectedCityId}/districts`)
    const items = data.items || []
    setDistricts(items)
    const nextId = items.some(item => item.id === preferredId) ? preferredId : (items[0]?.id || '')
    setDistrictId(nextId)
    if (!nextId) {
      setStreets([])
      setStreetId('')
      setHouses([])
      setHouseId('')
      setEntrances([])
    }
  }

  async function loadStreets(selectedDistrictId, preferredId = streetId) {
    if (!selectedDistrictId) return
    const data = await request(`/api/v1/admin/districts/${selectedDistrictId}/streets`)
    const items = data.items || []
    setStreets(items)
    const nextId = items.some(item => item.id === preferredId) ? preferredId : (items[0]?.id || '')
    setStreetId(nextId)
    if (!nextId) {
      setHouses([])
      setHouseId('')
      setEntrances([])
    }
  }

  async function loadHouses(selectedStreetId, preferredId = houseId) {
    if (!selectedStreetId) return
    const data = await request(`/api/v1/admin/streets/${selectedStreetId}/houses`)
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

  async function loadSuperAdminData() {
    if (!isSuperAdmin) return
    const [unassignedData, districtsData, residentsData, adminsData] = await Promise.all([
      request('/api/v1/admin/districts/unassigned'),
      request('/api/v1/admin/districts'),
      request('/api/v1/admin/users'),
      request('/api/v1/admin/admin-users'),
    ])
    setUnassignedDistricts(unassignedData.items || [])
    setAllDistricts(districtsData.items || [])
    setResidents(residentsData.items || [])
    setAdmins(adminsData.items || [])
  }

  React.useEffect(() => {
    setLoading(true)
    Promise.all([loadCities(), loadSuperAdminData()])
      .catch(requestError => setError(requestError.message))
      .finally(() => setLoading(false))
  }, [])

  React.useEffect(() => {
    if (cityId) loadDistricts(cityId).catch(requestError => setError(requestError.message))
  }, [cityId])

  React.useEffect(() => {
    if (districtId) loadStreets(districtId).catch(requestError => setError(requestError.message))
  }, [districtId])

  React.useEffect(() => {
    if (streetId) loadHouses(streetId).catch(requestError => setError(requestError.message))
  }, [streetId])

  React.useEffect(() => {
    if (houseId) loadEntrances(houseId).catch(requestError => setError(requestError.message))
    setNewEntrance({ entrance_number: '', public_code: '', regioncity_external_ref: '' })
    setRegionCityCandidates([])
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

  async function createCity(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const name = new FormData(formElement).get('name')
    const result = await mutate(() => request('/api/v1/admin/cities', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
    }), 'Город создан.')
    if (result) {
      formElement.reset()
      await loadCities(result.item.id)
    }
  }

  async function createDistrict(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const name = new FormData(formElement).get('name')
    const result = await mutate(() => request(`/api/v1/admin/cities/${cityId}/districts`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
    }), 'Район создан.')
    if (result) {
      formElement.reset()
      await Promise.all([loadDistricts(cityId, result.item.id), loadSuperAdminData()])
    }
  }

  async function assignDistrict(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const district_id = new FormData(formElement).get('district_id')
    const result = await mutate(() => request(`/api/v1/admin/cities/${cityId}/districts/assign`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ district_id }),
    }), 'Район привязан к городу.')
    if (result) await Promise.all([loadDistricts(cityId, result.item.id), loadSuperAdminData()])
  }

  async function createStreet(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const name = new FormData(formElement).get('name')
    const result = await mutate(() => request(`/api/v1/admin/districts/${districtId}/streets`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
    }), 'Улица создана.')
    if (result) {
      formElement.reset()
      await loadStreets(districtId, result.item.id)
    }
  }

  async function createHouse(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = Object.fromEntries(new FormData(formElement).entries())
    const result = await mutate(() => request(`/api/v1/admin/streets/${streetId}/houses`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form),
    }), 'Дом создан.')
    if (result) {
      formElement.reset()
      await loadHouses(streetId, result.item.id)
    }
  }

  async function createEntrance(event) {
    event.preventDefault()
    if (!newEntrance.regioncity_external_ref.trim()) {
      setError('Выберите объект RegionCity или укажите mapObjectID.')
      return
    }
    const result = await mutate(() => request(`/api/v1/admin/houses/${houseId}/entrances`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newEntrance),
    }), 'Подъезд создан.')
    if (result) {
      setNewEntrance({ entrance_number: '', public_code: '', regioncity_external_ref: '' })
      setRegionCityCandidates([])
      await loadEntrances(houseId)
    }
  }

  function entranceAddress(entranceNumber = newEntrance.entrance_number) {
    return [
      city?.name,
      district?.name,
      street?.name,
      house ? `дом ${house.house_number}${house.building ? ` к${house.building}` : ''}` : '',
      entranceNumber ? `подъезд ${entranceNumber}` : '',
    ].filter(Boolean).join(', ')
  }

  async function searchRegionCityObjects() {
    const address = entranceAddress()
    if (!address || !newEntrance.entrance_number.trim()) {
      setError('Укажите подъезд перед поиском RegionCity.')
      return
    }
    setRegionCityBusy(true)
    setError('')
    try {
      const data = await request(`/api/v1/admin/regioncity/map-objects/search?address=${encodeURIComponent(address)}`)
      setRegionCityCandidates(data.items || [])
      if ((data.items || []).length === 0) setError('RegionCity не вернул похожих объектов.')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setRegionCityBusy(false)
    }
  }

  async function exportAddresses() {
    const data = await mutate(() => request('/api/v1/admin/address-export'), 'Справочник выгружен.')
    if (data) downloadWorkbook('resident-notifications-addresses.xlsx', data.items || [])
  }

  function downloadTemplate() {
    downloadWorkbook('resident-notifications-address-template.xlsx', [])
  }

  async function previewImport(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const rows = await readWorkbookRows(file)
      setImportRows(rows)
      const data = await request('/api/v1/admin/address-import/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: rows }),
      })
      setImportPreview(data.items || [])
      setNotice('Файл проверен. Примените импорт, если ошибок нет.')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
      event.target.value = ''
    }
  }

  async function applyImport() {
    const result = await mutate(() => request('/api/v1/admin/address-import/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: importRows }),
    }), 'Импорт применён.')
    if (result) {
      setImportPreview(result.items || [])
      await Promise.all([loadCities(), loadSuperAdminData()])
    }
  }

  async function deactivate(kind, id, title) {
    if (!window.confirm(`Деактивировать ${title}? Публичный доступ и уведомления по объекту будут отключены.`)) return
    const result = await mutate(() => request(`/api/v1/admin/${kind}/${id}/deactivate`, { method: 'PATCH' }), 'Объект деактивирован.')
    if (!result) return
    if (kind === 'cities') await Promise.all([loadCities(''), loadSuperAdminData()])
    if (kind === 'districts') await Promise.all([loadDistricts(cityId, ''), loadSuperAdminData()])
    if (kind === 'streets') await loadStreets(districtId, '')
    if (kind === 'houses') await loadHouses(streetId, '')
    if (kind === 'entrances') await loadEntrances(houseId)
  }

  async function deactivateResident(userId) {
    const result = await mutate(() => request(`/api/v1/admin/users/${userId}/deactivate`, { method: 'PATCH' }), 'Пользователь отключён.')
    if (result) await loadSuperAdminData()
  }

  async function createAdmin(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = new FormData(formElement)
    const district_ids = form.getAll('district_ids')
    const result = await mutate(() => request('/api/v1/admin/admin-users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login: form.get('login'), password: form.get('password'), role: newAdminRole, district_ids }),
    }), 'Администратор создан.')
    if (result) {
      formElement.reset()
      setNewAdminRole('district_admin')
      await loadSuperAdminData()
    }
  }

  async function deactivateAdmin(adminId) {
    const result = await mutate(() => request(`/api/v1/admin/admin-users/${adminId}/deactivate`, { method: 'PATCH' }), 'Администратор отключён.')
    if (result) await loadSuperAdminData()
  }

  async function sendTestNotification(event) {
    event.preventDefault()
    const result = await mutate(() => request('/api/v1/admin/test-notification', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: testUserId, subject_title: 'Тестовое уведомление платформы' }),
    }), 'Тестовое уведомление отправлено.')
    if (result && !result.sent) {
      setNotice('')
      setError('MAX не подтвердил отправку. Проверьте webhook, токен бота и user ID.')
    }
  }

  return <div className='app-shell'>
    <header className='topbar'>
      <div className='brand'><span className='brand-mark compact'>RN</span><div><strong>Resident Notifications</strong><small>Панель управления</small></div></div>
      <div className='profile'><span className='role'>{isSuperAdmin ? 'Super admin' : 'District admin'}</span><button type='button' className='ghost' onClick={() => onLogout()}>Выйти</button></div>
    </header>

    <main className='workspace'>
      <section className='hero'>
        <div>
          <p className='eyebrow'>Каталог объектов</p>
          <h1>Управление подписками и адресами</h1>
          <p className='muted'>Иерархия адресов, публичные ссылки для QR и проверка доставки в MAX.</p>
        </div>
        <div className='metrics'>
          <div><strong>{cities.length}</strong><span>городов</span></div>
          <div><strong>{districts.length}</strong><span>районов</span></div>
          <div><strong>{streets.length}</strong><span>улиц</span></div>
          <div><strong>{entrances.length}</strong><span>подъездов</span></div>
        </div>
      </section>

      {(notice || error) && <div className={`alert ${error ? 'error' : 'success'}`} role='status'>{error || notice}</div>}

      <section className='panel tools-panel'>
        <div>
          <p className='eyebrow'>Excel и QR</p>
          <h2>Обмен справочником адресов</h2>
          <p className='muted'>Экспортируйте текущий справочник, скачайте шаблон или загрузите Excel для предварительной проверки.</p>
        </div>
        <div className='tool-actions'>
          <button type='button' className='secondary' onClick={exportAddresses} disabled={busy}>Экспорт Excel</button>
          <button type='button' className='secondary' onClick={downloadTemplate} disabled={busy}>Скачать шаблон</button>
          {isSuperAdmin && <label className='file-button'>
            Импорт Excel
            <input type='file' accept='.xlsx,.xls' onChange={previewImport} disabled={busy} />
          </label>}
        </div>
        {importPreview.length > 0 && <div className='import-preview'>
          <div className='panel-title'><h3>Предпросмотр импорта</h3><span className='tag'>{importPreview.length} строк</span></div>
          <div className='table-scroll'>
            <table>
              <thead><tr><th>Строка</th><th>Действие</th><th>Адрес</th><th>mapObjectID</th><th>Ошибки</th></tr></thead>
              <tbody>
                {importPreview.map(item => <tr key={item.row_number} className={item.errors.length ? 'bad-row' : ''}>
                  <td>{item.row_number}</td>
                  <td>{item.action}</td>
                  <td>{[item.item.city, item.item.district, item.item.street, item.item.house_number, item.item.entrance_number].filter(Boolean).join(', ')}</td>
                  <td>{item.item.regioncity_map_object_id}</td>
                  <td>{item.errors.join(', ') || 'ok'}</td>
                </tr>)}
              </tbody>
            </table>
          </div>
          {isSuperAdmin && <button type='button' className='primary' onClick={applyImport} disabled={busy || importPreview.some(item => item.errors.length)}>
            Применить импорт
          </button>}
        </div>}
      </section>

      <div className='directory-grid' aria-busy={busy || loading}>
        <section className='panel'>
          <div className='panel-title'><h2>Города</h2><span className='tag'>{isSuperAdmin ? 'управление' : 'только выбор'}</span></div>
          {loading ? <Empty>Загрузка...</Empty> : cities.length === 0 ? <Empty>{isSuperAdmin ? 'Создайте первый город.' : 'Доступных городов нет.'}</Empty> : <ul className='select-list'>
            {cities.map(item => <li key={item.id} className={item.id === cityId ? 'selected' : ''}>
              <button type='button' className='select' onClick={() => setCityId(item.id)}>{item.name}</button>
              {isSuperAdmin && <button type='button' className='danger-link' onClick={() => deactivate('cities', item.id, `город "${item.name}"`)} disabled={busy}>Отключить</button>}
            </li>)}
          </ul>}
          {isSuperAdmin && <form className='edit-form' onSubmit={createCity}>
            <h3>Новый город</h3>
            <input name='name' placeholder='Название города' required />
            <button type='submit' className='primary' disabled={busy}>Добавить город</button>
          </form>}
        </section>

        <section className='panel'>
          <div className='panel-title'><h2>Районы</h2><span className='tag'>{city?.name || 'выберите город'}</span></div>
          {!city ? <Empty>Сначала выберите город.</Empty> : districts.length === 0 ? <Empty>В городе нет доступных районов.</Empty> : <ul className='select-list'>
            {districts.map(item => <li key={item.id} className={item.id === districtId ? 'selected' : ''}>
              <button type='button' className='select' onClick={() => setDistrictId(item.id)}>{item.name}</button>
              {isSuperAdmin && <button type='button' className='danger-link' onClick={() => deactivate('districts', item.id, `район "${item.name}"`)} disabled={busy}>Отключить</button>}
            </li>)}
          </ul>}
          {isSuperAdmin && city && <form className='edit-form' onSubmit={createDistrict}>
            <h3>Новый район</h3>
            <input name='name' placeholder='Название района' required />
            <button type='submit' className='primary' disabled={busy}>Добавить район</button>
          </form>}
          {isSuperAdmin && city && unassignedDistricts.length > 0 && <form className='edit-form compact-form' onSubmit={assignDistrict}>
            <h3>Привязать существующий район</h3>
            <select name='district_id' required>{unassignedDistricts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
            <button type='submit' className='secondary' disabled={busy}>Привязать к городу</button>
          </form>}
        </section>

        <section className='panel'>
          <div className='panel-title'><h2>Улицы</h2><span className='tag'>{district?.name || 'выберите район'}</span></div>
          {!district ? <Empty>Сначала выберите район.</Empty> : streets.length === 0 ? <Empty>Улиц пока нет.</Empty> : <ul className='select-list'>
            {streets.map(item => <li key={item.id} className={item.id === streetId ? 'selected' : ''}>
              <button type='button' className='select' onClick={() => setStreetId(item.id)}>{item.name}</button>
              <button type='button' className='danger-link' onClick={() => deactivate('streets', item.id, `улицу "${item.name}"`)} disabled={busy}>Отключить</button>
            </li>)}
          </ul>}
          {district && <form className='edit-form' onSubmit={createStreet}>
            <h3>Новая улица</h3>
            <input name='name' placeholder='Название улицы' required />
            <button type='submit' className='primary' disabled={busy}>Добавить улицу</button>
          </form>}
        </section>

        <section className='panel object-panel'>
          <div className='panel-title'><h2>Дома и подъезды</h2><span className='tag'>{street?.name || 'выберите улицу'}</span></div>
          {!street ? <Empty>Сначала выберите улицу.</Empty> : houses.length === 0 ? <Empty>Домов пока нет.</Empty> : <ul className='select-list houses'>
            {houses.map(item => <li key={item.id} className={item.id === houseId ? 'selected' : ''}>
              <button type='button' className='select' onClick={() => setHouseId(item.id)}><strong>Дом {item.house_number}{item.building ? ` к${item.building}` : ''}</strong></button>
              <button type='button' className='danger-link' onClick={() => deactivate('houses', item.id, 'дом')} disabled={busy}>Отключить</button>
            </li>)}
          </ul>}
          {street && <form className='edit-form inline-form' onSubmit={createHouse}>
            <h3>Новый дом</h3>
            <div className='split small'><input name='house_number' placeholder='Дом' required /><input name='building' placeholder='Корпус' /></div>
            <button type='submit' className='primary' disabled={busy}>Добавить дом</button>
          </form>}
          {house && <div className='entrance-subsection'>
            <h3>Подъезды дома {house.house_number}</h3>
            {entrances.length === 0 ? <Empty>Подъездов пока нет.</Empty> : <ul className='select-list entrances'>
              {entrances.map(item => <li key={item.id}>
                <div className='entrance-details'>
                  <strong>Подъезд {item.entrance_number}</strong>
                  <small>Код: {item.public_code}</small>
                  <small className={item.regioncity_external_ref ? 'ok-text' : 'warn-text'}>
                    {item.regioncity_external_ref ? `RegionCity: ${item.regioncity_external_ref}` : 'Требует привязки RegionCity'}
                  </small>
                  {item.public_url && <a href={item.public_url} target='_blank' rel='noreferrer'>Публичная страница</a>}
                  {item.max_bot_url && <a href={item.max_bot_url} target='_blank' rel='noreferrer'>Открыть MAX</a>}
                </div>
                <QrCodeImage value={item.max_bot_url} />
                <button type='button' className='danger-link' onClick={() => deactivate('entrances', item.id, 'подъезд')} disabled={busy}>Отключить</button>
              </li>)}
            </ul>}
            <form className='edit-form inline-form' onSubmit={createEntrance}>
              <div className='split'>
                <input
                  name='entrance_number'
                  placeholder='Подъезд'
                  required
                  value={newEntrance.entrance_number}
                  onChange={event => setNewEntrance(state => ({ ...state, entrance_number: event.target.value }))}
                />
                <input
                  name='public_code'
                  placeholder='Публичный код (авто)'
                  value={newEntrance.public_code}
                  onChange={event => setNewEntrance(state => ({ ...state, public_code: event.target.value }))}
                />
              </div>
              <div className='regioncity-box'>
                <div>
                  <strong>RegionCity mapObjectID</strong>
                  <p className='muted'>Поиск выполняется по адресу: {entranceAddress() || 'укажите подъезд'}</p>
                </div>
                <div className='split'>
                  <input
                    name='regioncity_external_ref'
                    placeholder='mapObjectID'
                    required
                    readOnly={!isSuperAdmin}
                    value={newEntrance.regioncity_external_ref}
                    onChange={event => setNewEntrance(state => ({ ...state, regioncity_external_ref: event.target.value }))}
                  />
                  <button type='button' className='secondary' onClick={searchRegionCityObjects} disabled={busy || regionCityBusy || !newEntrance.entrance_number}>
                    {regionCityBusy ? 'Ищем...' : 'Найти в RegionCity'}
                  </button>
                </div>
                {regionCityCandidates.length > 0 && <ul className='candidate-list'>
                  {regionCityCandidates.map(candidate => <li key={candidate.map_object_id}>
                    <button type='button' className='select' onClick={() => setNewEntrance(state => ({ ...state, regioncity_external_ref: candidate.map_object_id }))}>
                      <strong>{candidate.map_object_id}</strong>
                      <span>{candidate.address}</span>
                      <small>Совпадение: {Math.round(candidate.score * 100)}%</small>
                    </button>
                  </li>)}
                </ul>}
              </div>
              <button type='submit' className='primary' disabled={busy || !newEntrance.regioncity_external_ref.trim()}>Добавить подъезд</button>
            </form>
          </div>}
        </section>
      </div>

      {isSuperAdmin && <div className='management-grid'>
        <section className='panel management-panel'>
          <div className='panel-title'><h2>Пользователи MAX</h2><span className='tag'>{residents.length}</span></div>
          {residents.length === 0 ? <Empty>Пользователи появятся после взаимодействия с ботом.</Empty> : <ul className='select-list management-list'>
            {residents.map(item => <li key={item.id}>
              <div className='list-copy'><strong>{item.display_name || item.external_user_id}</strong><small>{item.external_user_id}</small></div>
              <button type='button' className='danger-link' onClick={() => deactivateResident(item.id)} disabled={busy}>Отключить</button>
            </li>)}
          </ul>}
        </section>

        <section className='panel management-panel'>
          <div className='panel-title'><h2>Администраторы</h2><span className='tag'>{admins.length}</span></div>
          <ul className='select-list management-list'>
            {admins.map(item => <li key={item.id}>
              <div className='list-copy'><strong>{item.login}</strong><small>{item.role === 'super_admin' ? 'Super admin' : `${item.district_ids.length} район(а)`}</small></div>
              {item.id !== principal.sub && <button type='button' className='danger-link' onClick={() => deactivateAdmin(item.id)} disabled={busy}>Отключить</button>}
            </li>)}
          </ul>
          <form className='edit-form' onSubmit={createAdmin}>
            <h3>Новый администратор</h3>
            <div className='split'><input name='login' placeholder='Логин' required /><input name='password' type='password' placeholder='Пароль, минимум 12' required /></div>
            <select value={newAdminRole} onChange={event => setNewAdminRole(event.target.value)}>
              <option value='district_admin'>Районный администратор</option>
              <option value='super_admin'>Суперадминистратор</option>
            </select>
            {newAdminRole === 'district_admin' && <div className='permission-list'>
              {allDistricts.length === 0 ? <small>Сначала создайте или привяжите районы.</small> : allDistricts.map(item =>
                <label className='checkbox' key={item.id}><input type='checkbox' name='district_ids' value={item.id} />{item.name}</label>
              )}
            </div>}
            <button type='submit' className='primary' disabled={busy}>Создать администратора</button>
          </form>
        </section>
      </div>}

      {isSuperAdmin && <section className='panel notification-panel'>
        <div>
          <p className='eyebrow'>Проверка интеграции</p>
          <h2>Тестовое уведомление MAX</h2>
          <p className='muted'>После регистрации webhook отправьте тест реальному пользователю бота.</p>
        </div>
        <form className='notification-form' onSubmit={sendTestNotification}>
          <input value={testUserId} onChange={event => setTestUserId(event.target.value)} placeholder='MAX user ID' required />
          <button type='submit' className='primary' disabled={busy}>Отправить тест</button>
        </form>
      </section>}
    </main>
  </div>
}

function App() {
  const [token, setToken] = React.useState(localStorage.getItem('jwt') || '')
  const [principal, setPrincipal] = React.useState(null)
  const [sessionError, setSessionError] = React.useState('')
  const [validating, setValidating] = React.useState(Boolean(token))

  function logout(message = '') {
    localStorage.removeItem('jwt')
    setToken('')
    setPrincipal(null)
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
      .then(data => setPrincipal(data))
      .catch(() => logout('Сессия истекла. Войдите снова.'))
      .finally(() => setValidating(false))
  }, [token])

  if (!token) return <><Login onAuthenticated={authenticated} />{sessionError && <p className='session-error'>{sessionError}</p>}</>
  if (validating || !principal) return <div className='loading-page'>Проверяем сессию...</div>
  return <Dashboard token={token} principal={principal} onLogout={logout} />
}

createRoot(document.getElementById('root')).render(<App />)
