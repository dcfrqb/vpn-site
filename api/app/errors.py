import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

log = logging.getLogger(__name__)

# User-facing texts: Russian, informal, no letter "yo".
MESSAGES = {
    "invalid_request": "Проверь данные в форме",
    "forbidden": "Нет доступа",
    "invalid_email": "Похоже, в email ошибка",
    "weak_password": "Пароль должен быть от 10 до 128 символов и не совпадать с email",
    "email_taken": "Этот email уже занят. Попробуй войти или восстановить пароль",
    "invalid_credentials": "Неверный email или пароль",
    "unauthorized": "Нужно войти в аккаунт",
    "wrong_password": "Текущий пароль указан неверно",
    "invalid_token": "Ссылка устарела или уже использована. Запроси новую",
    "telegram_invalid": "Не получилось проверить вход через Telegram. Попробуй еще раз",
    "telegram_expired": "Данные от Telegram устарели. Войди через Telegram заново",
    "telegram_taken": "Этот Telegram уже привязан к другому аккаунту",
    "telegram_unavailable": "Вход через Telegram пока не настроен",
    "last_login_method": "Нельзя убрать последний способ входа. Сначала добавь другой",
    "passkey_invalid": "Паскей не подошел. Попробуй еще раз",
    "passkey_exists": "Этот паскей уже добавлен",
    "bad_origin": "Запрос отклонен. Обнови страницу и попробуй снова",
    "rate_limited": "Слишком много попыток. Подожди немного и попробуй снова",
    "not_found": "Не нашли такую страницу",
    "method_not_allowed": "Так делать нельзя",
    "device_not_found": "Такого устройства уже нет в подписке",
    "bot_unavailable": "Бот сейчас не отвечает. Обнови страницу через минуту",
    "unavailable": "Сервис временно недоступен, попробуй позже",
    "internal": "Что-то сломалось на нашей стороне. Попробуй позже",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, *, headers: dict | None = None, **extra):
        self.status, self.code, self.headers, self.extra = status, code, headers, extra


def error_response(status: int, code: str, headers: dict | None = None, **extra) -> JSONResponse:
    body = {"error": code, "message": MESSAGES.get(code, MESSAGES["internal"]), **extra}
    return JSONResponse(body, status_code=status, headers=headers)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return error_response(e.status, e.code, e.headers, **e.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        return error_response(422, "invalid_request")

    @app.exception_handler(HTTPException)
    async def _http(_: Request, e: HTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(e.status_code, "invalid_request")
        return error_response(e.status_code, code)

    @app.exception_handler(Exception)
    async def _crash(request: Request, e: Exception):
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return error_response(500, "internal")
