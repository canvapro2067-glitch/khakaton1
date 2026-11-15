# Netlify + GitHub

Репозиторий: **https://github.com/canvapro2067-glitch/khakaton1**

Netlify собирает только **фронт** (`frontend`). Для входа и данных нужен **backend API** (Python на Render / туннель с ПК) — без него на Netlify будет только «оболочка».

### Проще всего для защиты (без Render)

1. На ПК: `start.ps1` (API + локальный фронт) **или** только API + `npx localtunnel --port 8000`.
2. Netlify: переменная `VITE_API_URL` = URL туннеля, **Trigger deploy**.
3. Пока идёт демо — **ПК и туннель включены**.

Render можно не использовать, если не нужен API «в облаке без вашего компьютера».

## 1. API на Render (опционально)

1. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint** → подключите GitHub → репозиторий `khakaton1`.
2. Render создаст сервис `moloko-api`. Дождитесь **Live**.
3. Скопируйте URL вида `https://moloko-api-xxxx.onrender.com` (без `/` в конце).
4. В **Environment** на Render:
   - `YANDEX_MAPS_API_KEY` (и при желании `YANDEX_ROUTING_API_KEY`) — карта и точный грузовой маршрут;
   - `SKIP_ROUTE_GEOMETRY` = `0` (в `render.yaml` уже так): иначе на карте **прямые линии** и пробег без дорожной геометрии.

## 2. Netlify

1. [app.netlify.com](https://app.netlify.com) → **Add new site** → **Import an existing project** → **GitHub**.
2. Если просит доступ — [настройки установки GitHub](https://github.com/settings/installations) → **Netlify** → разрешить нужные репозитории.
3. Выберите репозиторий **canvapro2067-glitch/khakaton1**. Настройки из `netlify.toml`.
4. **Site configuration → Environment variables** → **Add a variable**:
   - Key: `VITE_API_URL`
   - Value: URL Render, например `https://moloko-api-xxxx.onrender.com`
5. **Deploys → Trigger deploy → Deploy site** (переменные Vite применяются при сборке).

Не задавайте `VITE_STATIC_HOST=tiiny` — на Netlify используется обычный `BrowserRouter` и `_redirects`.

## 3. Яндекс.Карты

В HTTP Referer ключа: `https://ваш-сайт.netlify.app/*`

## 4. Логины

- Диспетчер: `dispatcher` / `dispatcher`
- Водитель: `driver1` / `driver`

После смены `VITE_API_URL` нажмите **Trigger deploy** в Netlify.