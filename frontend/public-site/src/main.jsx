import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes, useLocation, useParams } from 'react-router-dom'
import QRCode from 'qrcode'
import './styles.css'

const API = import.meta.env.VITE_PUBLIC_API_BASE_URL || ''

async function apiGet(path) {
  const response = await fetch(`${API}${path}`)
  if (!response.ok) throw new Error('api')
  return response.json()
}

function asItems(data) {
  return Array.isArray(data) ? data : data?.items || []
}

function AppShell({ children }) {
  return (
    <main className="page">
      <header className="brand">
        <div className="logo">RN</div>
        <div>
          <strong>Resident Notifications</strong>
          <span>Уведомления по объектам справочника</span>
        </div>
      </header>
      {children}
    </main>
  )
}

function SearchField({ id, label, value, options, disabled, placeholder, onChange }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        value={value}
        list={id}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
      <datalist id={id}>
        {options.map((option) => (
          <option key={option.id} value={option.label} />
        ))}
      </datalist>
    </label>
  )
}

function QrCodeImage({ value }) {
  const [src, setSrc] = React.useState('')

  React.useEffect(() => {
    let active = true
    if (!value) {
      setSrc('')
      return undefined
    }
    QRCode.toDataURL(value, { margin: 1, width: 180 })
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
  return <img className="qr-code" src={src} alt="QR-код для перехода в MAX" />
}

function AddressPicker() {
  const [cities, setCities] = React.useState([])
  const [districts, setDistricts] = React.useState([])
  const [streets, setStreets] = React.useState([])
  const [houses, setHouses] = React.useState([])
  const [entrances, setEntrances] = React.useState([])
  const [selected, setSelected] = React.useState({
    cityText: '',
    cityId: '',
    districtText: '',
    districtId: '',
    streetText: '',
    streetId: '',
    houseText: '',
    houseId: '',
    entranceText: '',
    entrance: null,
  })
  const [status, setStatus] = React.useState({ loading: true, error: '', message: '' })

  React.useEffect(() => {
    apiGet('/api/v1/public/cities')
      .then((data) => {
        setCities(asItems(data))
        setStatus({ loading: false, error: '', message: '' })
      })
      .catch(() => setStatus({ loading: false, error: 'Не удалось загрузить города.', message: '' }))
  }, [])

  const cityOptions = cities.map((item) => ({ id: item.id, label: item.name }))
  const districtOptions = districts.map((item) => ({ id: item.id, label: item.name }))
  const streetOptions = streets.map((item) => ({ id: item.id, label: item.name }))
  const houseOptions = houses.map((item) => ({
    id: item.id,
    label: `${item.house_number}${item.building ? ` к${item.building}` : ''}`,
  }))
  const entranceOptions = entrances.map((item) => ({ id: item.id, label: `Подъезд ${item.entrance_number}`, item }))

  async function chooseCity(value) {
    const city = cityOptions.find((item) => item.label === value)
    setSelected({
      cityText: value,
      cityId: city?.id || '',
      districtText: '',
      districtId: '',
      streetText: '',
      streetId: '',
      houseText: '',
      houseId: '',
      entranceText: '',
      entrance: null,
    })
    setDistricts([])
    setStreets([])
    setHouses([])
    setEntrances([])
    if (city) {
      setDistricts(asItems(await apiGet(`/api/v1/public/cities/${city.id}/districts`)))
    }
  }

  async function chooseDistrict(value) {
    const district = districtOptions.find((item) => item.label === value)
    setSelected((state) => ({
      ...state,
      districtText: value,
      districtId: district?.id || '',
      streetText: '',
      streetId: '',
      houseText: '',
      houseId: '',
      entranceText: '',
      entrance: null,
    }))
    setStreets([])
    setHouses([])
    setEntrances([])
    if (district) {
      setStreets(asItems(await apiGet(`/api/v1/public/districts/${district.id}/streets`)))
    }
  }

  async function chooseStreet(value) {
    const street = streetOptions.find((item) => item.label === value)
    setSelected((state) => ({
      ...state,
      streetText: value,
      streetId: street?.id || '',
      houseText: '',
      houseId: '',
      entranceText: '',
      entrance: null,
    }))
    setHouses([])
    setEntrances([])
    if (street) {
      setHouses(asItems(await apiGet(`/api/v1/public/streets/${street.id}/houses`)))
    }
  }

  async function chooseHouse(value) {
    const house = houseOptions.find((item) => item.label === value)
    setSelected((state) => ({
      ...state,
      houseText: value,
      houseId: house?.id || '',
      entranceText: '',
      entrance: null,
    }))
    setEntrances([])
    if (house) {
      setEntrances(asItems(await apiGet(`/api/v1/public/houses/${house.id}/entrances`)))
    }
  }

  function chooseEntrance(value) {
    const entrance = entranceOptions.find((item) => item.label === value)
    setSelected((state) => ({
      ...state,
      entranceText: value,
      entrance: entrance?.item || null,
    }))
  }

  const address = [
    selected.cityText,
    selected.districtText,
    selected.streetText,
    selected.houseText,
    selected.entranceText,
  ]
    .filter(Boolean)
    .join(', ')

  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Выбор адреса</p>
        <h1>Найдите свой подъезд</h1>
        <p>Выберите адрес из объектов, которые уже заведены в системе. Квартиру указывать не нужно.</p>
      </section>

      <section className="picker-card">
        {status.loading && cities.length === 0 ? <p className="muted">Загрузка адресов...</p> : null}
        {status.error && cities.length === 0 ? <p className="error">{status.error}</p> : null}
        <div className="picker-grid">
          <SearchField id="cities" label="Город" value={selected.cityText} options={cityOptions} placeholder="Начните вводить город" onChange={chooseCity} />
          <SearchField
            id="districts"
            label="Район"
            value={selected.districtText}
            options={districtOptions}
            disabled={!selected.cityId}
            placeholder={selected.cityId ? 'Начните вводить район' : 'Сначала выберите город'}
            onChange={chooseDistrict}
          />
          <SearchField
            id="streets"
            label="Улица"
            value={selected.streetText}
            options={streetOptions}
            disabled={!selected.districtId}
            placeholder={selected.districtId ? 'Начните вводить улицу' : 'Сначала выберите район'}
            onChange={chooseStreet}
          />
          <SearchField
            id="houses"
            label="Дом"
            value={selected.houseText}
            options={houseOptions}
            disabled={!selected.streetId}
            placeholder={selected.streetId ? 'Выберите дом' : 'Сначала выберите улицу'}
            onChange={chooseHouse}
          />
          <SearchField
            id="entrances"
            label="Подъезд"
            value={selected.entranceText}
            options={entranceOptions}
            disabled={!selected.houseId}
            placeholder={selected.houseId ? 'Выберите подъезд' : 'Сначала выберите дом'}
            onChange={chooseEntrance}
          />
        </div>

        <div className="result">
          <span>Выбранный адрес</span>
          <strong>{address || 'Адрес пока не выбран'}</strong>
          {selected.entrance ? (
            <div className="address-actions">
              <QrCodeImage value={selected.entrance.max_bot_url} />
              <div className="button-row">
                <a className={`link-button ${selected.entrance.max_bot_url ? '' : 'disabled'}`} href={selected.entrance.max_bot_url || undefined}>
                  Перейти в MAX
                </a>
                <a className="link-button secondary-link" href={selected.entrance.public_url || `/e/${selected.entrance.public_code}`}>
                  Открыть страницу адреса
                </a>
              </div>
            </div>
          ) : null}
          {status.message ? <p className="success">{status.message}</p> : null}
          {status.error && cities.length > 0 ? <p className="error">{status.error}</p> : null}
        </div>
      </section>
    </AppShell>
  )
}

function EntrancePage() {
  const { publicCode } = useParams()
  const [state, setState] = React.useState({ loading: true, error: '', data: null })

  const load = React.useCallback(async () => {
    setState({ loading: true, error: '', data: null })
    try {
      const data = await apiGet(`/api/v1/public/entrances/${publicCode}`)
      if (data.error === 'not_found') {
        setState({ loading: false, error: 'unavailable', data: null })
        return
      }
      setState({ loading: false, error: '', data })
    } catch {
      setState({ loading: false, error: 'retry', data: null })
    }
  }, [publicCode])

  React.useEffect(() => {
    load()
  }, [load])

  if (state.loading) return <AppShell><p aria-live="polite">Загрузка...</p></AppShell>
  if (state.error === 'unavailable') return <AppShell><p>Страница подъезда недоступна.</p></AppShell>
  if (state.error) {
    return (
      <AppShell>
        <p>Не удалось загрузить данные. Попробуйте снова.</p>
        <button onClick={load}>Повторить</button>
      </AppShell>
    )
  }

  const d = state.data || {}
  const events = (d.events || []).slice(0, 10)
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">{d.district}</p>
        <h1>{d.house}</h1>
        <p>{d.address}</p>
        <div className="button-row">
          {d.max_bot_url ? <a className="link-button" href={d.max_bot_url}>Перейти в MAX</a> : null}
          <Link className="link-button secondary-link" to="/?view=select">Выбрать другой адрес</Link>
        </div>
      </section>
      <section className="picker-card qr-panel">
        <h2>Подписка через MAX</h2>
        <p className="muted">Отсканируйте QR-код или нажмите «Перейти в MAX». Бот получит команду с адресом автоматически.</p>
        <QrCodeImage value={d.max_bot_url} />
      </section>
      <section className="picker-card">
        <h2>Последние события</h2>
        {events.length ? (
          <ul className="events">
            {events.map((event, index) => (
              <li key={event.id || index}>
                <b>{event.title}</b>
                <div>{event.description}</div>
                <small>{event.occurred_at}</small>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Событий пока нет.</p>
        )}
      </section>
    </AppShell>
  )
}

function HomeRouter() {
  const location = useLocation()
  if (new URLSearchParams(location.search).get('view') === 'select') {
    return <AddressPicker />
  }
  return <AddressPicker />
}

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<HomeRouter />} />
      <Route path="/select" element={<AddressPicker />} />
      <Route path="/e/:publicCode" element={<EntrancePage />} />
    </Routes>
  </BrowserRouter>,
)
