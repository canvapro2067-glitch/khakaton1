# Netlify + GitHub

Репозиторий: **https://github.com/canvapro2067-glitch/khakaton1**

Netlify собирает только **фронт** (`frontend`). API — на **Render** (файл `render.yaml` в корне) или туннель с ПК.

## 1. API на Render (рекомендуется)

1. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint** → подключите GitHub → репозиторий `khakaton1`.
2. Render создаст сервис `moloko-api`. Дождитесь **Live**.
3. Скопируйте URL вида `https://moloko-api-xxxx.onrender.com` (без `/` в конце).
4. В **Environment** на Render при необходимости добавьте `YANDEX_MAPS_API_KEY` из `.env`.

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