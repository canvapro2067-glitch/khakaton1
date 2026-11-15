# Публикация на tiiny.host

[tiiny.host](https://tiiny.host) размещает **только статику** (HTML/JS/CSS). **FastAPI и SQLite на tiiny не запускаются.** Полноценное приложение = фронт на tiiny + API в интернете.

## Быстрый старт

### 1. Публичный API (обязательно для входа)

Пока демо крутится у вас на ПК:

```powershell
# Терминал 1 — API как обычно
$env:PYTHONPATH = "D:\Project\ProjectXakaton"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Терминал 2 — туннель (пример ngrok)
ngrok http 8000
```

Скопируйте HTTPS-адрес вида `https://abcd-123.ngrok-free.app`.

Можно вместо туннеля выложить backend на [Render](https://render.com), Railway и т.п.

### 2. Собрать ZIP

```powershell
cd D:\Project\ProjectXakaton
.\deploy-tiiny.ps1 -ApiUrl "https://abcd-123.ngrok-free.app"
```

Появится файл `moloko-tiiny.zip`.

### 3. Загрузить на tiiny

1. Войдите в [https://tiiny.host/manage](https://tiiny.host/manage)
2. **Upload** (или замените существующий сайт)
3. Перетащите `moloko-tiiny.zip`
4. Задайте имя ссылки (например `moloko-grodno`)
5. **Publish**

Сайт: `https://moloko-grodno.tiiny.site` (точный URL покажет панель).

### 4. Логины

- Диспетчер: `dispatcher` / `dispatcher`
- Водитель: `driver1` / `driver`

На tiiny адреса с `#`: `https://…tiiny.site/#/login`

### 5. Яндекс.Карты

В [кабинете ключей](https://developer.tech.yandex.ru/) в HTTP Referer добавьте:

`https://ваш-поддомен.tiiny.site/*`

## Ограничения

| Что | Деталь |
|-----|--------|
| Размер | Бесплатно ~**3 MB** на ZIP |
| Содержимое ZIP | `index.html` в **корне** архива, не вложенная папка `dist/` |
| Не класть в ZIP | `package.json`, исходники `src/` |
| Маршруты | HashRouter (`#/driver`, `#/login`) |
| Без `-ApiUrl` | Откроется интерфейс, но API не ответит |

## Обновление

После правок кода снова `.\deploy-tiiny.ps1 -ApiUrl "…"` и в manage загрузите новый ZIP (замена сайта).

## Только витрина без API

```powershell
.\deploy-tiiny.ps1
```

Подойдёт для скриншотов; вход и данные работать не будут.