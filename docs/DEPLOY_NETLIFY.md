# Netlify + GitHub

Netlify собирает только **фронт** из папки `frontend`. API — отдельно (Render, Railway, туннель).

## 1. Репозиторий на GitHub

```powershell
cd D:\Project\ProjectXakaton
git init -b main
git add .
git commit -m "Initial commit"
```

Создайте пустой репозиторий на GitHub (без README), затем:

```powershell
git remote add origin https://github.com/ВАШ_ЛОГИН/ИМЯ_РЕПО.git
git push -u origin main
```

## 2. Netlify

1. [app.netlify.com](https://app.netlify.com) → **Add new site** → **Import an existing project** → **GitHub**.
2. Если просит доступ — [настройки установки GitHub](https://github.com/settings/installations) → **Netlify** → разрешить нужные репозитории.
3. Выберите репозиторий. Настройки подтянутся из `netlify.toml` в корне.
4. **Site configuration → Environment variables** → добавьте:
   - `VITE_API_URL` = `https://ваш-публичный-api` (без слэша в конце)
5. **Deploy**.

Не задавайте `VITE_STATIC_HOST=tiiny` — на Netlify используется обычный `BrowserRouter` и `_redirects`.

## 3. Яндекс.Карты

В HTTP Referer ключа: `https://ваш-сайт.netlify.app/*`

## 4. Логины

- Диспетчер: `dispatcher` / `dispatcher`
- Водитель: `driver1` / `driver`

После смены `VITE_API_URL` нажмите **Trigger deploy** в Netlify.